"""MinecraftPlatformAdapter：Minecraft WebSocket 平台适配器。

通过 WebSocket 将 ZenithProxy (Minecraft) 接入 AstrBot 事件系统。
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from astrbot.api.platform import (
    Platform,
    AstrBotMessage,
    MessageMember,
    PlatformMetadata,
    MessageType,
)
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain
from astrbot.core.platform.astr_message_event import MessageSesion
from astrbot.api.platform import register_platform_adapter
from astrbot import logger

from .ws_server import MinecraftWSServer
from .minecraft_platform_event import MinecraftPlatformEvent
from .connection import BridgeConnection
from . import protocol


@register_platform_adapter(
    "minecraft",
    "Minecraft WebSocket Adapter",
    default_config_tmpl={
        "host": "0.0.0.0",
        "port": 8765,
        "path": "/ws",
        "token": "change-me",
        "outbound_max_length": 64,
    },
    config_metadata={
        "host": {
            "description": "WebSocket 监听地址",
            "type": "string",
            "hint": "单机部署保持 0.0.0.0；跨机器连接时改为可被 MC 服务器访问的地址。",
            "default": "0.0.0.0",
        },
        "port": {
            "description": "WebSocket 监听端口",
            "type": "int",
            "hint": "需要与 Minecraft Mod 配置中的 websocketUrl 端口一致。",
            "default": 8765,
        },
        "path": {
            "description": "WebSocket 路径",
            "type": "string",
            "hint": "默认 /ws，需要与 Minecraft Mod 配置中的 websocketUrl 路径一致。",
            "default": "/ws",
        },
        "token": {
            "description": "连接认证 Token",
            "type": "string",
            "secret": True,
            "hint": "Minecraft Mod 连接 AstrBot 时使用，两端必须完全一致。",
            "default": "change-me",
        },
        "outbound_max_length": {
            "description": "MC 单条消息最大长度",
            "type": "int",
            "hint": "发送到 Minecraft 的单条消息最大字符数。2b2t 限制 256，超长会被踢。建议 64。",
            "slider": {"min": 32, "max": 256, "step": 16},
            "default": 64,
        },
    },
)
class MinecraftPlatformAdapter(Platform):
    def __init__(
        self,
        platform_config: dict,
        platform_settings: dict,
        event_queue: asyncio.Queue,
    ) -> None:
        super().__init__(platform_config, event_queue)
        self.config = platform_config
        self.settings = platform_settings
        self._ws_server: Optional[MinecraftWSServer] = None
        self._connections: dict[str, BridgeConnection] = {}
        self._dedup: dict[str, float] = {}

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            "minecraft",
            "Minecraft WebSocket Adapter",
            "minecraft",
        )

    async def run(self) -> None:
        from astrbot import logger
        logger.info("[MC Bridge] run() called, starting WS server...")
        if self._ws_server:
            await self._ws_server.stop()
        self._ws_server = MinecraftWSServer(self)
        await self._ws_server.start()
        logger.info("[MC Bridge] WS server started")

    async def send_by_session(
        self, session: MessageSesion, message_chain: MessageChain
    ) -> None:
        text = self._extract_text(message_chain)
        if not text:
            return

        # sanitize：去 §、控制字符 → 空格，压空白，截断
        import re
        text = text.replace("§", "")
        text = re.sub(r"[\r\n\t\x00-\x1f\x7f]", " ", text)
        text = re.sub(r" {2,}", " ", text).strip()
        max_len = self.config.get("outbound_max_length", 200)
        if len(text) > max_len:
            text = text[:max_len - 3] + "..."
        if not text:
            return

        server_id = session.session_id.split(":")[0] if session.session_id else ""
        conn = self._connections.get(server_id)
        if conn:
            await conn.send_task_action("send_chat", {"message": text})

    # ---- 事件处理管道 ----

    def on_ws_event(self, server_id: str, event_type: str, payload: dict) -> None:
        """WS 服务端收到事件后回调。"""
        if event_type in (protocol.EVENT_CHAT, protocol.EVENT_WHISPER):
            self._handle_chat_event(server_id, event_type, payload)
        else:
            self._handle_system_event(server_id, event_type, payload)

    def _handle_chat_event(
        self, server_id: str, event_type: str, payload: dict
    ) -> None:
        sender = payload.get("sender", "unknown")
        message = payload.get("message", "")
        if not message:
            return

        # 去重
        dedup_key = f"{server_id}:{sender}:{message}"
        now = time.time()
        if now - self._dedup.get(dedup_key, 0) < 2.0:
            return
        self._dedup[dedup_key] = now
        if len(self._dedup) > 500:
            self._dedup.clear()

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

        event = MinecraftPlatformEvent(
            message_str=message,
            message_obj=abm,
            platform_meta=self.meta(),
            session_id=abm.session_id,
            adapter=self,
            server_id=server_id,
            event_type=event_type,
        )
        self.commit_event(event)

    def _handle_system_event(
        self, server_id: str, event_type: str, payload: dict
    ) -> None:
        msg = self._format_event(event_type, payload)
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

        event = MinecraftPlatformEvent(
            message_str=msg,
            message_obj=abm,
            platform_meta=self.meta(),
            session_id=abm.session_id,
            adapter=self,
            server_id=server_id,
            event_type=event_type,
        )
        self.commit_event(event)

    def _format_event(self, event_type: str, payload: dict) -> str:
        player = payload.get("player", "unknown")
        if event_type == protocol.EVENT_PLAYER_JOIN:
            return payload.get("message", f"{player} joined the game")
        elif event_type == protocol.EVENT_PLAYER_LEAVE:
            return payload.get("message", f"{player} left the game")
        elif event_type == protocol.EVENT_DEATH:
            pos = payload.get("position")
            if pos:
                return f"Bot died [{pos.get('x',0)},{pos.get('y',0)},{pos.get('z',0)}]"
            return "Bot died"
        elif event_type == protocol.EVENT_ACHIEVEMENT:
            return f"{player} has made the advancement [{payload.get('achievement', '')}]"
        elif event_type == protocol.EVENT_PLAYER_DEATH:
            victim = payload.get("victim", "unknown")
            killer = payload.get("killer")
            weapon = payload.get("weapon")
            text = f"{victim} was killed"
            if killer:
                text += f" by {killer}"
            if weapon:
                text += f" [{weapon}]"
            return text
        elif event_type == protocol.EVENT_ATTACK:
            x, y, z = payload.get("x", 0), payload.get("y", 0), payload.get("z", 0)
            return f"{player} attacked Bot [{x},{y},{z}]"
        elif event_type == protocol.EVENT_TOTEM_POP:
            remaining = payload.get("totems_remaining", "?")
            return f"Totem popped, {remaining} remaining"
        elif event_type == protocol.EVENT_TOTEM_EMPTY:
            return "No totems left!"
        elif event_type == protocol.EVENT_VISUAL_ENTER:
            x, y, z = payload.get("x", 0), payload.get("y", 0), payload.get("z", 0)
            return f"{player} entered view [{x},{y},{z}]"
        elif event_type == protocol.EVENT_VISUAL_LEAVE:
            x, y, z = payload.get("x", 0), payload.get("y", 0), payload.get("z", 0)
            return f"{player} left view [{x},{y},{z}]"
        elif event_type == protocol.EVENT_VISUAL_LOGOUT:
            x, y, z = payload.get("x", 0), payload.get("y", 0), payload.get("z", 0)
            return f"{player} logged out [{x},{y},{z}]"
        elif event_type == protocol.EVENT_CONNECTION_DENIED:
            reason = payload.get("reason", "unknown")
            ip = payload.get("ip", "?")
            return f"Denied {player} ({reason}, {ip})"
        elif event_type == protocol.EVENT_QUEUE_POSITION:
            pos = payload.get("position", "?")
            return f"Queue position: {pos}"
        elif event_type == protocol.EVENT_QUEUE_COMPLETE:
            dur = payload.get("duration_seconds", "?")
            return f"Queue complete ({dur}s)"
        elif event_type == protocol.EVENT_HEALTH_WARNING:
            hp = payload.get("health", "?")
            return f"Low health: {hp}"
        elif event_type == protocol.EVENT_HEALTH_AUTODISCONNECT:
            return "Auto-disconnected due to low health"
        elif event_type == protocol.EVENT_SCAN_FOUND:
            target = payload.get("target", "?")
            name = payload.get("name", "?")
            x, y, z = payload.get("x", 0), payload.get("y", 0), payload.get("z", 0)
            dist = payload.get("distance", "?")
            return f"Scan found {target}: {name} [{x},{y},{z}] ({dist}m)"
        elif event_type == protocol.EVENT_SYSTEM:
            return payload.get("message", "")
        elif event_type == protocol.EVENT_BOT_STATUS:
            return f"[Bot] {payload.get('status', '')}"
        return ""

    @staticmethod
    def _extract_text(message_chain: MessageChain) -> str:
        parts = []
        for item in message_chain.chain:
            if isinstance(item, Plain):
                parts.append(item.text)
        return "".join(parts).strip()
