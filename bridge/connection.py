"""BridgeConnection：单连接封装 + heartbeat 监控。

一个 BridgeConnection 对应一条与某个 Minecraft 服务端(ZenithProxy 客户端)的 WS 连接。
每条连接以 server_id 标识。
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from aiohttp.web import WebSocketResponse

from astrbot.api import logger

from . import protocol
from .protocol import PendingFuture


class BridgeConnection:
    """封装一条已建立的 WebSocket 连接。

    职责：
    - 维护 last_seen 供心跳监控判定离线
    - 发送 task / query / heartbeat_ack
    - 供外部读取原始连接状态
    """

    def __init__(
        self,
        server_id: str,
        ws: WebSocketResponse,
        pending: PendingFuture,
        heartbeat_timeout: float = 15.0,
    ) -> None:
        self.server_id = server_id
        self._ws = ws
        self._pending = pending
        self.heartbeat_timeout = heartbeat_timeout
        self.last_seen: float = protocol.now()
        self.closed: bool = False
        # hello 握手元数据
        self.server_name: str = ""
        self.mod_version: str = ""
        self.capabilities: list[str] = []
        self.connected_at: float = protocol.now()

    @property
    def alive(self) -> bool:
        """是否在心跳超时时间内保持存活。"""
        return (protocol.now() - self.last_seen) < self.heartbeat_timeout

    def touch(self) -> None:
        """更新存活时间（收到任意消息时调用）。"""
        self.last_seen = protocol.now()

    def apply_hello(self, data: dict) -> None:
        """从 hello 消息中提取元数据。"""
        self.server_name = data.get("server_name", "")
        self.mod_version = data.get("mod_version", "")
        self.capabilities = data.get("capabilities", [])

    async def send_text(self, raw: str) -> bool:
        """发送文本帧，失败返回 False。"""
        if self._ws.closed:
            return False
        try:
            await self._ws.send_str(raw)
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"[{self.server_id}] 发送消息失败: {e}")
            return False

    async def send_task(self, task_id: str, action: str, params: Optional[dict] = None) -> bool:
        """下发任务。fire-and-forget 语义，返回是否成功发送。"""
        raw = protocol.build_task(task_id, self.server_id, action, params or {})
        return await self.send_text(raw)

    async def send_query(self, query_id: str, resource: str, params: Optional[dict] = None) -> bool:
        """下发查询。"""
        raw = protocol.build_query(query_id, self.server_id, resource, params or {})
        return await self.send_text(raw)

    async def send_heartbeat_ack(self) -> None:
        """回复心跳确认。"""
        await self.send_text(protocol.build_heartbeat_ack(self.server_id))

    async def send_hello_ack(self, capabilities: list[str] = None) -> None:
        """回复握手确认。"""
        await self.send_text(protocol.build_hello_ack(self.server_id, capabilities))

    async def close(self) -> None:
        """关闭连接并清理。"""
        self.closed = True
        try:
            await self._ws.close()
        except Exception:  # noqa: BLE001
            pass


class MockConnection(BridgeConnection):
    """离线时的占位连接：发送静默失败，仅用于保持接口一致。"""

    def __init__(self, server_id: str, pending: PendingFuture) -> None:
        self.server_id = server_id
        self._ws = None
        self._pending = pending
        self.heartbeat_timeout = 9999.0
        self.last_seen = protocol.now()
        self.closed = True
        self.server_name = ""
        self.mod_version = ""
        self.capabilities = []
        self.connected_at = protocol.now()

    async def send_text(self, raw: str) -> bool:
        return False
