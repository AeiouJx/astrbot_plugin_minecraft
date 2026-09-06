"""MinecraftPlatformAdapter：minecraft 虚拟平台适配器。

将 BridgeManager 事件队列中的 chat/whisper 事件转换为
AstrBotMessage，包装成 MinecraftEvent 提交到 AstrBot 事件总线。
"""

from __future__ import annotations

import asyncio
import uuid

from astrbot.api import logger
from astrbot.api.platform import (
    Platform,
    AstrBotMessage,
    MessageMember,
    MessageType,
    PlatformMetadata,
    register_platform_adapter,
)
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain
from astrbot.core.platform.message_session import MessageSesion

from ..bridge import BridgeManager
from ..bridge.protocol import EVENT_CHAT, EVENT_WHISPER
from .minecraft_event import MinecraftEvent


_registered = False


def _register_adapter():
    global _registered
    if _registered:
        return
    _registered = True

    @register_platform_adapter(
        "minecraft",
        "Minecraft 虚拟平台（经 ZenithProxy Bridge 桥接）",
        default_config_tmpl={},
    )
    class MinecraftPlatformAdapter(Platform):
        """把游戏内聊天室映射为 AstrBot 的一个虚拟群会话。"""

        def __init__(
            self,
            platform_config: dict,
            platform_settings: dict,
            event_queue: asyncio.Queue,
        ) -> None:
            super().__init__(platform_config, event_queue)
            self.settings = platform_settings
            self.bridge = BridgeManager.get_instance()
            self._dedup_cache: dict[str, float] = {}
            self._dedup_window = 2.0

        def meta(self) -> PlatformMetadata:
            return PlatformMetadata(
                name="minecraft",
                description="Minecraft 虚拟平台（经 ZenithProxy Bridge 桥接）",
                id="minecraft",
            )

        async def run(self) -> None:
            """阻塞消费 BridgeManager 的 chat 事件队列。"""
            logger.info("Minecraft Platform Adapter 已启动")
            while True:
                try:
                    item = await self.bridge.event_queue.get()
                    event_type = item.get("event_type")
                    if event_type in (EVENT_CHAT, EVENT_WHISPER):
                        abm = await self.convert_message(item)
                        if abm is not None and not self._is_duplicate(item):
                            await self.handle_msg(abm)
                    else:
                        logger.debug(f"忽略非聊天事件: {event_type}")
                except asyncio.CancelledError:
                    break
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Minecraft Adapter 事件处理异常: {e}")

        async def convert_message(self, data: dict) -> AstrBotMessage | None:
            """将桥接事件字典转换为 AstrBotMessage。

            data = {"server_id","event_type","data": {...},"timestamp"}
            其中 data.data = {"sender","message","outgoing","receiver",...}
            """
            server_id = data.get("server_id", "default")
            payload = data.get("data", {})
            event_type = data.get("event_type")

            if event_type == EVENT_WHISPER:
                if payload.get("outgoing"):
                    # bot 发出的私聊，忽略避免回路
                    return None
                sender = payload.get("sender", "unknown")
                message = payload.get("message", "")
            else:  # EVENT_CHAT
                sender = payload.get("sender", "unknown")
                message = payload.get("message", "")

            if not message:
                return None

            abm = AstrBotMessage()
            abm.type = MessageType.GROUP_MESSAGE
            group_id = self._group_id(server_id)
            abm.group_id = group_id
            abm.message_str = message
            abm.sender = MessageMember(user_id=sender, nickname=sender)
            abm.message = [Plain(text=message)]
            abm.self_id = f"minecraft:{server_id}"
            abm.session_id = group_id
            abm.message_id = str(uuid.uuid4())
            abm.raw_message = data
            return abm

        async def handle_msg(self, message: AstrBotMessage) -> None:
            """包装为 MinecraftEvent 并提交到事件队列。"""
            server_id = message.self_id.split(":", 1)[1] if ":" in message.self_id else "default"
            message_event = MinecraftEvent(
                message_str=message.message_str,
                message_obj=message,
                platform_meta=self.meta(),
                session_id=message.session_id,
                server_id=server_id,
            )
            self.commit_event(message_event)

        async def send_by_session(self, session: MessageSesion, message_chain: MessageChain) -> None:
            """通过会话 ID 主动推送消息到游戏内。"""
            text = "".join(c.text if isinstance(c, Plain) else "" for c in message_chain.chain)
            text = text.strip()
            if text:
                # session_id 格式为 minecraft:{server_id}
                parts = session.session_id.split(":", 1)
                server_id = parts[1] if len(parts) > 1 else self.bridge.config.get("default_server_id", "default")
                try:
                    await self.bridge.send_chat(server_id, text)
                except Exception as e:  # noqa: BLE001
                    logger.error(f"[{server_id}] 推送失败: {e}")
            await super().send_by_session(session, message_chain)

        # ---- 工具方法 ----

        def _group_id(self, server_id: str) -> str:
            prefix = self.bridge.config.get("group_id_prefix", "minecraft")
            return f"{prefix}:{server_id}"

        def _is_duplicate(self, item: dict) -> bool:
            """防循环去重：同一 server_id + sender + message + 时间窗内丢弃。"""
            if not self._dedup_window:
                return False
            server_id = item.get("server_id")
            payload = item.get("data", {})
            key = f"{server_id}|{payload.get('sender')}|{payload.get('message')}"
            now = asyncio.get_running_loop().time()
            last = self._dedup_cache.get(key)
            if last and (now - last) < self._dedup_window:
                return True
            self._dedup_cache[key] = now
            # 简单清理：超过 200 条清一次
            if len(self._dedup_cache) > 200:
                self._dedup_cache.clear()
            return False


def _ensure_registered():
    """确保适配器已注册（由 main.py 调用）。"""
    _register_adapter()
