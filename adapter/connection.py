"""BridgeConnection：单连接封装。

一个 BridgeConnection 对应一条与某个 Minecraft 服务端(ZenithProxy)的 WS 连接。
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Optional

from astrbot.api import logger


class BridgeConnection:
    """封装一条已建立的 WebSocket 连接。"""

    def __init__(self, server_id: str, ws, pending) -> None:
        self.server_id = server_id
        self._ws = ws
        self._pending = pending
        self.last_seen: float = time.time()
        self.closed: bool = False
        # hello 握手元数据
        self.account: str = ""
        self.hwid: str = ""
        self.server_name: str = ""
        self.mod_version: str = ""
        self.capabilities: list[str] = []
        self.connected_at: float = time.time()

    @property
    def alive(self) -> bool:
        return (time.time() - self.last_seen) < 15.0

    def touch(self) -> None:
        self.last_seen = time.time()

    def apply_hello(self, data: dict) -> None:
        self.account = data.get("account", "")
        self.hwid = data.get("hwid", "")
        self.server_name = data.get("server_name", "")
        self.mod_version = data.get("mod_version", "")
        self.capabilities = data.get("capabilities", [])

    async def send_text(self, raw: str) -> bool:
        if self._ws.closed:
            return False
        try:
            await self._ws.send_str(raw)
            return True
        except Exception as e:
            logger.error(f"[{self.server_id}] 发送失败: {e}")
            return False

    async def send_task_action(self, action: str, params: dict) -> bool:
        task_id = str(uuid.uuid4())
        raw = json.dumps({
            "type": "task",
            "task_id": task_id,
            "server_id": self.server_id,
            "action": action,
            "params": params,
        })
        return await self.send_text(raw)

    async def send_hello_ack(self) -> None:
        await self.send_text(json.dumps({
            "type": "hello_ack",
            "server_id": self.server_id,
            "capabilities": self.capabilities,
            "timestamp": time.time(),
        }))

    async def send_heartbeat_ack(self) -> None:
        await self.send_text(json.dumps({
            "type": "heartbeat_ack",
            "server_id": self.server_id,
            "timestamp": time.time(),
        }))

    async def close(self) -> None:
        self.closed = True
        try:
            await self._ws.close()
        except Exception:
            pass
