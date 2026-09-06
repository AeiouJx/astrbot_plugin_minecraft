"""消息协议层：消息构造/解析、RPC 关联。

协议规范参考 plane.md 第 3 章。
所有消息为 JSON 文本帧，type 字段区分方向与类别。
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Optional

# ---- 消息类型 ----
MSG_HEARTBEAT = "heartbeat"
MSG_HEARTBEAT_ACK = "heartbeat_ack"
MSG_EVENT = "event"
MSG_TASK = "task"
MSG_QUERY = "query"
MSG_TASK_RESULT = "task_result"
MSG_QUERY_RESULT = "query_result"
MSG_HELLO = "hello"
MSG_HELLO_ACK = "hello_ack"

# ---- 事件类型（游戏侧 G->S）----
EVENT_CHAT = "chat"
EVENT_WHISPER = "whisper"
EVENT_SYSTEM = "system"
EVENT_PLAYER_JOIN = "player_join"
EVENT_PLAYER_LEAVE = "player_leave"
EVENT_BOT_STATUS = "bot_status"
EVENT_DEATH = "death"
EVENT_ACHIEVEMENT = "achievement"

# ---- 任务动作（S->G）----
ACTION_SEND_CHAT = "send_chat"
ACTION_MOVE_TO = "move_to"
ACTION_ATTACK_NEAREST = "attack_nearest"

# ---- 查询资源（S->G）----
RESOURCE_ONLINE_PLAYERS = "online_players"
RESOURCE_BOT_STATUS = "bot_status"
RESOURCE_INVENTORY = "inventory"
RESOURCE_NEARBY_ENTITIES = "nearby_entities"


def gen_id() -> str:
    """生成唯一 task_id / query_id。"""
    return str(uuid.uuid4())


def now() -> float:
    """当前时间戳。"""
    return time.time()


# ---- 消息构造 ----

def build_heartbeat_ack(server_id: str) -> str:
    """G->S heartbeat -> S->G heartbeat_ack。"""
    return json.dumps({
        "type": MSG_HEARTBEAT_ACK,
        "server_id": server_id,
        "timestamp": now(),
    })


def build_hello_ack(server_id: str, capabilities: list[str] = None) -> str:
    """S->G hello_ack：确认握手并返回服务端能力列表。"""
    return json.dumps({
        "type": MSG_HELLO_ACK,
        "server_id": server_id,
        "capabilities": capabilities or [],
        "timestamp": now(),
    })


def build_task(task_id: str, server_id: str, action: str, params: dict) -> str:
    """构造下发给游戏端的任务消息。"""
    return json.dumps({
        "type": MSG_TASK,
        "server_id": server_id,
        "task_id": task_id,
        "action": action,
        "params": params or {},
    })


def build_query(query_id: str, server_id: str, resource: str, params: Optional[dict] = None) -> str:
    """构造查询消息。"""
    return json.dumps({
        "type": MSG_QUERY,
        "server_id": server_id,
        "query_id": query_id,
        "resource": resource,
        "params": params or {},
    })


def parse_message(raw: str) -> Optional[dict]:
    """解析收到的任意 JSON 文本帧。非法返回 None。"""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


class PendingFuture:
    """RPC 关联：task_id/query_id -> asyncio.Future。

    服务端维护 pending: dict[id -> asyncio.Future]，
    收到 task_result/query_result 后按 id 立刻解析。
    """

    def __init__(self, timeout: float = 10.0) -> None:
        self._futures: dict[str, asyncio.Future] = {}
        self._owner: dict[str, str] = {}
        self._timeout = timeout

    def expect(self, req_id: str, owner: str = None) -> asyncio.Future:
        """注册一个等待中的请求，返回 future。owner 用于连接断开时定向清理。"""
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._futures[req_id] = fut
        if owner:
            self._owner[req_id] = owner
        return fut

    async def wait(self, req_id: str) -> dict:
        """等待结果并返回 data 字典；超时抛 asyncio.TimeoutError，失败抛 RuntimeError。"""
        fut = self._futures.get(req_id)
        if fut is None:
            raise RuntimeError(f"未找到对应的请求: {req_id}")
        try:
            result = await asyncio.wait_for(fut, timeout=self._timeout)
        finally:
            self._cleanup(req_id)
        if not result.get("success"):
            raise RuntimeError(result.get("error_message") or "未知错误")
        return result.get("data", {})

    def _cleanup(self, req_id: str) -> None:
        """移除请求记录（可幂等）。"""
        self._futures.pop(req_id, None)
        self._owner.pop(req_id, None)

    def resolve(self, req_id: str, success: bool, data: Any = None, error_message: str = None) -> bool:
        """按 id 解析结果，唤醒等待方。返回是否成功解析。"""
        fut = self._futures.get(req_id)
        if fut is None or fut.done():
            return False
        fut.set_result({
            "success": success,
            "data": data,
            "error_message": error_message,
        })
        self._cleanup(req_id)
        return True

    def cancel_for(self, owner: str) -> None:
        """取消属于指定 owner（server_id）的所有 pending 请求。"""
        for req_id, o in list(self._owner.items()):
            if o != owner:
                continue
            fut = self._futures.get(req_id)
            if fut and not fut.done():
                fut.cancel()
            self._cleanup(req_id)

    def cancel_all(self) -> None:
        """清空所有 pending，置为取消。用于全局兜底。"""
        for fut in self._futures.values():
            if not fut.done():
                fut.cancel()
        self._futures.clear()
        self._owner.clear()

    def __len__(self) -> int:
        return len(self._futures)
