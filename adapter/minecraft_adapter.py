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

CONFIG_METADATA = {
    "ws_host": {
        "description": "WebSocket 监听地址",
        "hint": "建议绑定内网地址，如 0.0.0.0 或局域网 IP",
        "type": "string",
    },
    "ws_port": {
        "description": "WebSocket 监听端口",
        "hint": "与 ZenithProxy 插件 bridge.wsPort 一致",
        "type": "int",
    },
    "ws_path": {
        "description": "WebSocket 路径",
        "hint": "默认 /ws，两端需一致",
        "type": "string",
    },
    "shared_token": {
        "description": "共享鉴权 Token",
        "hint": "两端必须完全一致，建议改为随机字符串，勿使用默认值",
        "type": "string",
        "secret": True,
    },
    "default_server_id": {
        "description": "默认服务器实例 ID",
        "hint": "AI 工具未指定 server 时使用的默认实例",
        "type": "string",
    },
    "heartbeat_timeout": {
        "description": "心跳超时秒数",
        "hint": "超过该时间未收到心跳则判定客户端离线",
        "type": "int",
    },
    "rpc_timeout": {
        "description": "RPC 超时秒数",
        "hint": "task/query 等待结果的最大秒数",
        "type": "int",
    },
    "group_id_prefix": {
        "description": "虚拟群 ID 前缀",
        "hint": "生成格式: {prefix}:{server_id}，一般不需要修改",
        "type": "string",
    },
    "bridge_on": {
        "description": "开机自启 WS 服务",
        "hint": "插件加载时自动启动 WebSocket 服务（运行中可用 Dashboard 按钮临时启停）",
        "type": "bool",
    },
    "allowed_groups": {
        "description": "允许使用的群号列表",
        "hint": "留空表示所有群都可用；填写后仅这些群可使用 Minecraft Bridge 命令",
        "type": "list",
    },
    "blocked_groups": {
        "description": "禁止使用的群号列表",
        "hint": "这些群无法使用 Minecraft Bridge 命令（优先级高于白名单）",
        "type": "list",
    },
    "llm_reply_enabled": {
        "description": "启用 LLM 自动回复",
        "hint": "开启后，游戏内玩家聊天会触发 AI 自动回复",
        "type": "bool",
    },
    "llm_reply_weight": {
        "description": "LLM 回复触发权重",
        "hint": "触发概率 = 权重 / 10。权重越高越容易触发 LLM 回复",
        "type": "int",
    },
    "llm_prompt_template": {
        "description": "LLM 回复提示模板",
        "hint": "支持变量: {player_name} = 发言玩家名, {message} = 消息内容",
        "type": "text",
    },
}


def _register_adapter():
    global _registered
    if _registered:
        return
    _registered = True

    @register_platform_adapter(
        "minecraft_bridge",
        "Minecraft Bridge（ZenithProxy WebSocket 桥接）",
        default_config_tmpl={},
        config_metadata=CONFIG_METADATA,
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
                name="minecraft_bridge",
                description="Minecraft Bridge（ZenithProxy WebSocket 桥接）",
                id="minecraft_bridge",
            )

        async def run(self) -> None:
            """阻塞消费 BridgeManager 的 chat 事件队列。"""
            import random
            logger.info("Minecraft Platform Adapter 已启动")
            while True:
                try:
                    item = await self.bridge.event_queue.get()
                    event_type = item.get("event_type")
                    if event_type in (EVENT_CHAT, EVENT_WHISPER):
                        abm = await self.convert_message(item)
                        if abm is not None and not self._is_duplicate(item):
                            await self.handle_msg(abm)
                            # LLM 自动回复
                            if event_type == EVENT_CHAT and self._should_llm_reply():
                                await self._try_llm_reply(item)
                    else:
                        logger.debug(f"忽略非聊天事件: {event_type}")
                except asyncio.CancelledError:
                    break
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Minecraft Adapter 事件处理异常: {e}")

        def _should_llm_reply(self) -> bool:
            """根据权重判断是否触发 LLM 回复。"""
            config = self.bridge.config
            if not config.get("llm_reply_enabled", False):
                return False
            weight = int(config.get("llm_reply_weight", 0))
            if weight <= 0:
                return False
            # 简单概率触发：权重越高越容易触发
            # 权重 1 = 10% 概率，权重 5 = 50% 概率，权重 10 = 100% 概率
            return random.random() < (weight / 10.0)

        async def _try_llm_reply(self, item: dict) -> None:
            """尝试调用 LLM 生成回复。"""
            try:
                payload = item.get("data", {})
                player_name = payload.get("sender", "unknown")
                message = payload.get("message", "")
                server_id = item.get("server_id", "default")

                # 格式化提示模板
                template = self.bridge.config.get("llm_prompt_template", "")
                if not template:
                    return
                prompt = template.replace("{player_name}", player_name).replace("{message}", message)

                # 通过 AstrBot context 调用 LLM
                # 这里我们直接构造一个消息发送到 AstrBot，让 AstrBot 处理 LLM 调用
                # 然后捕获回复发送到游戏
                logger.info(f"[{server_id}] LLM 回复触发: player={player_name}, msg={message[:50]}...")
                # TODO: 接入 AstrBot LLM 调用
            except Exception as e:
                logger.error(f"LLM 回复失败: {e}")

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
    # 检查运行时状态中是否已有实例（热重载存活）
    from ..bridge.runtime_state import get_adapter_instance
    existing = get_adapter_instance("minecraft_bridge")
    if existing is not None:
        logger.debug("从运行时状态恢复适配器实例")
    _register_adapter()
