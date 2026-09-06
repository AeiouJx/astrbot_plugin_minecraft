"""registry.py：server_id -> connection 注册表 + 路由。

同一 AstrBot 可接多个 Minecraft 服务端，以 server_id 区分客户端。
"""

from __future__ import annotations

import asyncio
from typing import Optional

from astrbot.api import logger

from . import protocol
from .connection import BridgeConnection, MockConnection


class Registry:
    """服务端连接注册表 dict[server_id -> BridgeConnection]。"""

    def __init__(self) -> None:
        self._conns: dict[str, BridgeConnection] = {}
        self._pending = protocol.PendingFuture()
        # 提供给上层（平台适配器）的事件通道
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.status_queue: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()

    # ---- 连接管理 ----

    async def register(self, conn: BridgeConnection) -> None:
        """注册一条新连接。若同 server_id 已存在，先关闭旧的。"""
        async with self._lock:
            old = self._conns.pop(conn.server_id, None)
            if old and old is not conn:
                logger.warning(f"[{conn.server_id}] 收到重复连接，关闭旧连接")
                await old.close()
            self._conns[conn.server_id] = conn
            logger.info(f"[{conn.server_id}] 已注册连接，当前在线: {len(self._conns)}")

    async def unregister(self, server_id: str, reason: str = "") -> Optional[BridgeConnection]:
        """移除连接，返回移除的连接（若存在）。"""
        async with self._lock:
            conn = self._conns.pop(server_id, None)
        if conn:
            logger.info(f"[{server_id}] 连接已移除: {reason or 'disconnected'}")
            self._pending.cancel_for(server_id)
        return conn

    def get(self, server_id: str) -> Optional[BridgeConnection]:
        """获取指定实例的连接，无则 None。"""
        return self._conns.get(server_id)

    def get_or_mock(self, server_id: str) -> BridgeConnection:
        """获取指定实例连接；离线时返回 MockConnection。"""
        conn = self._conns.get(server_id)
        if conn is None:
            return MockConnection(server_id, self._pending)
        return conn

    @property
    def connections(self) -> dict[str, BridgeConnection]:
        return dict(self._conns)

    @property
    def server_ids(self) -> list[str]:
        return list(self._conns.keys())

    @property
    def online_count(self) -> int:
        return len(self._conns)

    def get_connection_info(self, server_id: str) -> Optional[dict]:
        """获取连接元数据（用于状态查询）。"""
        conn = self._conns.get(server_id)
        if conn is None:
            return None
        return {
            "server_id": conn.server_id,
            "server_name": conn.server_name,
            "mod_version": conn.mod_version,
            "capabilities": conn.capabilities,
            "connected_at": conn.connected_at,
            "last_seen": conn.last_seen,
        }

    def get_all_connection_info(self) -> list[dict]:
        """获取所有连接元数据。"""
        return [self.get_connection_info(sid) for sid in self._conns]

    @property
    def pending(self) -> protocol.PendingFuture:
        return self._pending

    # ---- RPC 封装 ----

    async def send_task(self, server_id: str, action: str, params: dict = None, timeout: float = 10.0) -> dict:
        """下发任务并等待 task_result。

        返回解析后的 data 字典。失败抛 RuntimeError。
        """
        conn = self.get_or_mock(server_id)
        task_id = protocol.gen_id()
        fut = self._pending.expect(task_id, owner=server_id)
        sent = await conn.send_task(task_id, action, params or {})
        if not sent:
            fut.cancel()
            self._pending.cancel_for(server_id)
            raise RuntimeError(f"实例 [{server_id}] 未连接，无法执行操作")
        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"操作超时: {action} (>{timeout}s，实例 [{server_id}])") from None
        if not result.get("success"):
            raise RuntimeError(result.get("error_message") or f"操作失败: {action}")
        return result.get("data", {})

    async def send_task_fire(self, server_id: str, action: str, params: dict = None) -> bool:
        """下发任务，不等待结果（fire-and-forget）。"""
        conn = self.get_or_mock(server_id)
        task_id = protocol.gen_id()
        sent = await conn.send_task(task_id, action, params or {})
        if not sent:
            raise RuntimeError(f"实例 [{server_id}] 未连接，无法执行操作")
        return True

    async def send_query(self, server_id: str, resource: str, params: dict = None, timeout: float = 10.0) -> dict:
        """下发查询并等待 query_result。"""
        conn = self.get_or_mock(server_id)
        query_id = protocol.gen_id()
        fut = self._pending.expect(query_id, owner=server_id)
        sent = await conn.send_query(query_id, resource, params or {})
        if not sent:
            fut.cancel()
            self._pending.cancel_for(server_id)
            raise RuntimeError(f"实例 [{server_id}] 未连接，无法执行查询")
        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"查询超时: {resource} (>{timeout}s，实例 [{server_id}])") from None
        if not result.get("success"):
            raise RuntimeError(result.get("error_message") or f"查询失败: {resource}")
        return result.get("data", {})

    # ---- 事件分发 ----

    def handle_data_message(self, server_id: str, data: dict) -> None:
        """处理来自连接的业务数据帧（event / task_result / query_result）。"""
        msg_type = data.get("type")
        if msg_type == protocol.MSG_EVENT:
            self._dispatch_event(server_id, data)
        elif msg_type == protocol.MSG_TASK_RESULT:
            self._pending.resolve(
                data.get("task_id", ""),
                bool(data.get("success")),
                error_message=data.get("error_message"),
            )
        elif msg_type == protocol.MSG_QUERY_RESULT:
            self._pending.resolve(
                data.get("query_id", ""),
                bool(data.get("success")),
                data=data.get("data"),
                error_message=data.get("error_message"),
            )
        else:
            logger.debug(f"[{server_id}] 未知消息类型: {msg_type}")

    def _dispatch_event(self, server_id: str, data: dict) -> None:
        """内部事件分发：chat/whisper 进聊天队列；其余进状态队列。"""
        event_type = data.get("event_type")
        event_payload = data.get("data", {})
        if not event_type:
            return
        try:
            self.event_queue.put_nowait({
                "server_id": server_id,
                "event_type": event_type,
                "data": event_payload,
                "timestamp": data.get("timestamp"),
            })
        except Exception as e:  # noqa: BLE001
            logger.error(f"[{server_id}] 事件入队失败: {e}")

    # ---- 心跳监控 ----

    async def monitor(self) -> None:
        """后台监控任务：每 1s 扫描，last_seen 超时 -> 广播离线并移除注册表。"""
        if hasattr(self, '_monitor_running') and self._monitor_running:
            return  # 防止重复启动
        self._monitor_running = True
        try:
            while True:
                await asyncio.sleep(1)
                to_remove = [
                    sid for sid, conn in self._conns.items()
                    if not conn.alive and not conn.closed
                ]
                for sid in to_remove:
                    logger.warning(f"[{sid}] 心跳超时，判定离线")
                    await self._notify_offline(sid)
                    await self.unregister(sid, "heartbeat timeout")
        except asyncio.CancelledError:
            pass
        finally:
            self._monitor_running = False

    async def _notify_offline(self, server_id: str) -> None:
        """向状态队列广播 bot_status offline。"""
        try:
            self.status_queue.put_nowait({
                "server_id": server_id,
                "event_type": protocol.EVENT_BOT_STATUS,
                "data": {"status": "offline"},
                "timestamp": protocol.now(),
            })
        except Exception:  # noqa: BLE001
            pass
