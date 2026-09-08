"""MinecraftPlatformAdapter：Minecraft Bridge 平台适配器。

直接启动 WebSocket 服务端，接收 ZenithProxy 连接，
将 chat/whisper 事件通过 commit_event() 提交到 AstrBot 事件队列，
由 AstrBot 框架自动路由到 QQ 等平台。
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from aiohttp import web, WSMsgType
from astrbot.api import logger
from astrbot.api.platform import (
    Platform,
    AstrBotMessage,
    MessageMember,
    MessageType,
    PlatformMetadata,
    register_platform_adapter,
)
from astrbot.core.platform.message_session import MessageSesion
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain

from ..bridge import BridgeManager
from ..bridge.connection import BridgeConnection
from ..bridge.registry import Registry
from ..bridge import protocol
from .minecraft_event import MinecraftEvent

_DEFAULT_CONFIG = {
    "host": "0.0.0.0",
    "port": 8765,
    "path": "/ws",
    "token": "change-me",
}

_config_metadata = {
    "host": {
        "description": "反向 WebSocket 主机",
        "type": "string",
        "hint": "AstrBot 将作为 WebSocket 服务器端。单机部署保持 0.0.0.0；跨机器连接时改为可被 MC 服务器访问的地址。",
        "default": "0.0.0.0",
    },
    "port": {
        "description": "反向 WebSocket 端口",
        "type": "int",
        "hint": "需要与 ZenithProxy 插件 bridge.wsPort 一致；端口被占用时可以换成其他未使用端口。",
        "default": 8765,
    },
    "path": {
        "description": "WebSocket 路径",
        "type": "string",
        "hint": "默认 /ws，两端需一致。",
        "default": "/ws",
    },
    "token": {
        "description": "连接认证 Token",
        "type": "string",
        "hint": "两端必须完全一致；未设置则不启用 Token 验证。建议把 change-me 改成较长的随机字符串。",
        "default": "change-me",
    },
}


@register_platform_adapter(
    "minecraft_bridge",
    "Minecraft Bridge（ZenithProxy WebSocket 桥接）",
    default_config_tmpl=_DEFAULT_CONFIG,
    config_metadata=_config_metadata,
)
class MinecraftPlatformAdapter(Platform):
    """Minecraft Bridge 平台适配器。

    直接启动 WebSocket 服务端接收 ZenithProxy 连接，
    将事件通过 commit_event() 提交到 AstrBot 事件队列。
    """

    def __init__(
        self,
        platform_config: dict,
        platform_settings: dict,
        event_queue: asyncio.Queue,
    ) -> None:
        super().__init__(platform_config or {}, event_queue)
        self.settings = platform_settings
        self.bridge = BridgeManager.get_instance()
        self._dedup_cache: dict[str, float] = {}
        self._dedup_window = 2.0
        self._runner: Optional[web.AppRunner] = None
        self._conn: Optional[BridgeConnection] = None
        self._page_push_callback = None

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            id="minecraft_bridge",
            name="minecraft_bridge",
            description="Minecraft Bridge（ZenithProxy WebSocket 桥接）",
        )

    def set_page_push_callback(self, callback):
        """设置 Dashboard 消息推送回调。"""
        self._page_push_callback = callback

    # ---- WebSocket 服务端 ----

    async def run(self) -> None:
        """启动 WebSocket 服务端，接收 ZenithProxy 连接。"""
        # 优先使用平台配置，fallback 到插件配置
        host = self.config.get("host") or self.bridge.config.get("host", "0.0.0.0")
        port = int(self.config.get("port") or self.bridge.config.get("port", 8765))
        path = self.config.get("path") or self.bridge.config.get("path", "/ws")

        app = web.Application()
        app.router.add_get(path, self._handle_websocket)
        self._runner = web.AppRunner(app)
        try:
            await self._runner.setup()
            site = web.TCPSite(self._runner, host, port)
            await site.start()
            logger.info(f"MC Bridge WS 已监听: ws://{host}:{port}{path}")

            # 启动心跳监控
            asyncio.create_task(self.bridge.registry.monitor())

            await asyncio.Event().wait()  # 永久阻塞
        except Exception as e:
            logger.error(f"MC Bridge WS 启动失败: {e}")

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """处理 WebSocket 连接。"""
        ws = web.WebSocketResponse(heartbeat=30, max_msg_size=1024 * 1024)
        await ws.prepare(request)

        # 鉴权
        auth = request.headers.get("Authorization", "")
        token = self.config.get("token") or self.bridge.config.get("token", "change-me")
        if not auth.startswith("Bearer ") or auth[7:].strip() != token:
            logger.warning(f"WS 鉴权失败: {request.remote}")
            await ws.close()
            return ws

        logger.info(f"MC Bridge 收到连接: {request.remote}")

        conn: Optional[BridgeConnection] = None
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    data = protocol.parse_message(msg.data)
                    if not data:
                        continue
                    msg_type = data.get("type")

                    if conn is None:
                        if msg_type == protocol.MSG_HELLO:
                            server_id = data.get("server_id") or "default"
                            conn = BridgeConnection(server_id, ws, self.bridge.registry.pending)
                            conn.apply_hello(data)
                            await self.bridge.registry.register(conn)
                            conn.touch()
                            await conn.send_hello_ack()
                            logger.info(f"[{server_id}] hello 握手完成 (account={conn.account}, hwid={conn.hwid})")
                        elif msg_type == protocol.MSG_HEARTBEAT:
                            server_id = data.get("server_id") or "default"
                            conn = BridgeConnection(server_id, ws, self.bridge.registry.pending)
                            await self.bridge.registry.register(conn)
                            conn.touch()
                            await conn.send_heartbeat_ack()
                            logger.info(f"[{server_id}] heartbeat 握手完成（兼容模式）")
                        else:
                            break
                    else:
                        conn.touch()
                        if msg_type == protocol.MSG_UPDATE_INFO:
                            new_server_id = data.get("server_id")
                            if new_server_id and new_server_id != conn.server_id:
                                old_id = conn.server_id
                                await self.bridge.registry.unregister(old_id, "server_id updated")
                                conn.server_id = new_server_id
                                conn.apply_hello(data)
                                await self.bridge.registry.register(conn)
                                logger.info(f"[{old_id}] server_id 更新为: {new_server_id}")
                                await ws.send_json({
                                    "type": protocol.MSG_UPDATE_INFO_ACK,
                                    "server_id": new_server_id,
                                    "timestamp": protocol.now(),
                                })
                            continue

                        # 处理事件
                        if msg_type == protocol.MSG_EVENT:
                            await self._handle_event(conn.server_id, data)
                        elif msg_type == protocol.MSG_HEARTBEAT:
                            await conn.send_heartbeat_ack()
                        elif msg_type == protocol.MSG_TASK_RESULT:
                            self.bridge.registry.pending.resolve(
                                data.get("task_id", ""),
                                bool(data.get("success")),
                                error_message=data.get("error_message"),
                            )
                        elif msg_type == protocol.MSG_QUERY_RESULT:
                            self.bridge.registry.pending.resolve(
                                data.get("query_id", ""),
                                bool(data.get("success")),
                                data=data.get("data"),
                                error_message=data.get("error_message"),
                            )
                elif msg.type == WSMsgType.ERROR:
                    break
        except Exception as e:
            logger.error(f"MC Bridge WS 处理异常: {e}")
        finally:
            if conn is not None:
                conn.closed = True
                self.bridge.registry.pending.cancel_for(conn.server_id)
                await self.bridge.registry.unregister(conn.server_id, "connection closed")
            try:
                await ws.close()
            except Exception:
                pass
        return ws

    # ---- 事件处理 ----

    async def _handle_event(self, server_id: str, data: dict) -> None:
        """处理来自 ZenithProxy 的事件消息。"""
        event_type = data.get("event_type")
        payload = data.get("data", {})

        if not event_type:
            return

        # chat/whisper → commit_event() 到 AstrBot
        if event_type in (protocol.EVENT_CHAT, protocol.EVENT_WHISPER):
            await self._handle_chat_event(server_id, event_type, payload)
        else:
            # 非聊天事件 → 推送到 Dashboard + AstrBot 路由到 QQ
            self._push_to_dashboard(server_id, event_type, payload)
            await self._commit_server_event(server_id, event_type, payload)

    async def _handle_chat_event(self, server_id: str, event_type: str, payload: dict) -> None:
        """处理聊天事件，通过 AstrBot 管道路由。"""
        sender = payload.get("sender", "unknown")
        message = payload.get("message", "")
        if not message:
            return

        # 去重
        dedup_key = f"{server_id}:{sender}:{message}"
        now = time.time()
        if now - self._dedup_cache.get(dedup_key, 0) < self._dedup_window:
            return
        self._dedup_cache[dedup_key] = now
        if len(self._dedup_cache) > 500:
            self._dedup_cache.clear()

        # 推送到 Dashboard
        cb = self._page_push_callback or getattr(self.bridge, "page_push_callback", None)
        if cb:
            if event_type == protocol.EVENT_WHISPER:
                cb(server_id, sender, f"[私聊] {message}")
            else:
                cb(server_id, sender, message)

        # 构造 AstrBotMessage
        abm = AstrBotMessage()
        abm.type = MessageType.GROUP_MESSAGE
        abm.group_id = f"minecraft:{server_id}"
        abm.message_str = message
        abm.sender = MessageMember(user_id=sender, nickname=sender)
        abm.message = [Plain(text=message)]
        abm.raw_message = payload
        abm.self_id = server_id
        abm.session_id = f"{server_id}:{sender}"
        abm.message_id = str(protocol.gen_id())

        event = MinecraftEvent(
            message_str=message,
            message_obj=abm,
            platform_meta=self.meta(),
            session_id=abm.session_id,
            server_id=server_id,
        )
        self.commit_event(event)

        # LLM 自动回复
        if event_type == protocol.EVENT_CHAT and self._should_llm_reply():
            await self._try_llm_reply(server_id, sender, message)

    async def _commit_server_event(self, server_id: str, event_type: str, payload: dict) -> None:
        """将非聊天事件提交到 AstrBot 事件队列（路由到 QQ）。"""
        account = self._get_account(server_id)
        msg = self._format_event_message(account, event_type, payload)
        if not msg:
            return

        abm = AstrBotMessage()
        abm.type = MessageType.GROUP_MESSAGE
        abm.group_id = f"minecraft:{server_id}"
        abm.message_str = msg
        abm.sender = MessageMember(user_id="system", nickname="Minecraft")
        abm.message = [Plain(text=msg)]
        abm.raw_message = payload
        abm.self_id = server_id
        abm.session_id = f"minecraft:{server_id}"
        abm.message_id = str(protocol.gen_id())

        event = MinecraftEvent(
            message_str=msg,
            message_obj=abm,
            platform_meta=self.meta(),
            session_id=abm.session_id,
            server_id=server_id,
        )
        self.commit_event(event)

    def _push_to_dashboard(self, server_id: str, event_type: str, payload: dict) -> None:
        """推送非聊天事件到 Dashboard。"""
        cb = self._page_push_callback or getattr(self.bridge, "page_push_callback", None)
        if not cb:
            return
        player = payload.get("player", "")
        if event_type == protocol.EVENT_PLAYER_JOIN:
            cb(server_id, "System", f"{player} 加入了游戏")
        elif event_type == protocol.EVENT_PLAYER_LEAVE:
            cb(server_id, "System", f"{player} 离开了游戏")
        elif event_type == protocol.EVENT_DEATH:
            cb(server_id, "System", payload.get("death_message", payload.get("message", "Bot 死亡了")))
        elif event_type == protocol.EVENT_ACHIEVEMENT:
            cb(server_id, "System", f"{player} 达成成就: {payload.get('achievement', '')}")
        elif event_type == protocol.EVENT_SYSTEM:
            cb(server_id, "System", payload.get("message", ""))
        elif event_type == protocol.EVENT_BOT_STATUS:
            cb(server_id, "System", f"[{payload.get('bot_name', '')}] 状态: {payload.get('status', '')}")

    def _get_account(self, server_id: str) -> str:
        """获取实际 MC 账号名。"""
        conn_info = self.bridge.registry.get_connection_info(server_id)
        return (conn_info or {}).get("account", "") or server_id

    def _format_event_message(self, account: str, event_type: str, payload: dict) -> str:
        """格式化非聊天事件消息（用于 QQ 推送）。"""
        if event_type == protocol.EVENT_PLAYER_JOIN:
            return f"玩家 {payload.get('player', 'unknown')} 加入了游戏"
        elif event_type == protocol.EVENT_PLAYER_LEAVE:
            return f"玩家 {payload.get('player', 'unknown')} 离开了游戏"
        elif event_type == protocol.EVENT_DEATH:
            return f"Bot 死亡了"
        elif event_type == protocol.EVENT_ACHIEVEMENT:
            return f"玩家 {payload.get('player', 'unknown')} 达成成就: {payload.get('achievement', '')}"
        elif event_type == protocol.EVENT_SYSTEM:
            return payload.get("message", "")
        return ""

    # ---- LLM 自动回复 ----

    def _should_llm_reply(self) -> bool:
        """根据权重判断是否触发 LLM 回复。"""
        config = self.bridge.config
        if not config.get("llm_reply_enabled", False):
            return False
        weight = int(config.get("llm_reply_weight", 1))
        if weight <= 0:
            return False
        import random
        return random.randint(1, 10) <= weight

    async def _try_llm_reply(self, server_id: str, sender: str, message: str) -> None:
        """尝试 LLM 自动回复。"""
        try:
            from astrbot.api import get_astrbot_instance
            astrbot = get_astrbot_instance()
            if not astrbot:
                return
            template = self.bridge.config.get("llm_prompt_template", "")
            prompt = template.replace("{player_name}", sender).replace("{message}", message)
            # 简单实现：通过 AstrBot 的文本处理
            logger.debug(f"[{server_id}] LLM 回复触发: {sender}: {message}")
        except Exception as e:
            logger.debug(f"LLM 回复失败: {e}")

    # ---- 消息发送 ----

    async def send_by_session(self, session: MessageSesion, message_chain: MessageChain):
        """AstrBot 回复时调用：提取纯文本，发送到对应 Minecraft 实例。"""
        content = self._plain_text(message_chain)
        if not content:
            return

        # 从 session 提取 server_id
        session_id = getattr(session, "session_id", "") or ""
        server_id = session_id.split(":")[0] if session_id else ""

        if server_id:
            # 发送到指定实例
            try:
                await self.bridge.send_chat(server_id, content)
            except Exception as e:
                logger.error(f"[{server_id}] 游戏内发送失败: {e}")
        else:
            # 兜底：广播到所有在线实例
            for sid in self.bridge.registry.server_ids:
                try:
                    await self.bridge.send_chat(sid, content)
                except Exception:
                    pass

    @staticmethod
    def _plain_text(message_chain: MessageChain) -> str:
        """从消息链提取纯文本。"""
        parts = []
        for item in message_chain.chain:
            if isinstance(item, Plain):
                parts.append(item.text)
            elif hasattr(item, "text"):
                parts.append(str(item.text))
        return "".join(parts).strip()
