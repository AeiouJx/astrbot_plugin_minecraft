"""消息协议层：消息构造/解析、RPC 关联。

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
MSG_UPDATE_INFO = "update_info"
MSG_UPDATE_INFO_ACK = "update_info_ack"

# ---- 事件类型（游戏侧 G->S）----
EVENT_CHAT = "chat"
EVENT_WHISPER = "whisper"
EVENT_SYSTEM = "system"
EVENT_PLAYER_JOIN = "player_join"
EVENT_PLAYER_LEAVE = "player_leave"
EVENT_BOT_STATUS = "bot_status"
EVENT_DEATH = "death"
EVENT_ACHIEVEMENT = "achievement"
EVENT_PLAYER_DEATH = "player_death"
EVENT_ATTACK = "attack"
EVENT_TOTEM_POP = "totem_pop"
EVENT_TOTEM_EMPTY = "totem_empty"
EVENT_VISUAL_ENTER = "visual_enter"
EVENT_VISUAL_LEAVE = "visual_leave"
EVENT_VISUAL_LOGOUT = "visual_logout"
EVENT_CONNECTION_DENIED = "connection_denied"
EVENT_QUEUE_POSITION = "queue_position"
EVENT_QUEUE_COMPLETE = "queue_complete"
EVENT_HEALTH_WARNING = "health_warning"
EVENT_HEALTH_AUTODISCONNECT = "health_autodisconnect"
EVENT_SCAN_FOUND = "scan_found"

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
    return str(uuid.uuid4())


def now() -> float:
    return time.time()


# ---- 消息构造 ----

def build_heartbeat_ack(server_id: str) -> str:
    return json.dumps({
        "type": MSG_HEARTBEAT_ACK,
        "server_id": server_id,
        "timestamp": now(),
    })


def build_hello_ack(server_id: str, capabilities: list[str] = None) -> str:
    return json.dumps({
        "type": MSG_HELLO_ACK,
        "server_id": server_id,
        "capabilities": capabilities or [],
        "timestamp": now(),
    })


def build_task(task_id: str, server_id: str, action: str, params: dict) -> str:
    return json.dumps({
        "type": MSG_TASK,
        "server_id": server_id,
        "task_id": task_id,
        "action": action,
        "params": params or {},
    })


def build_query(query_id: str, server_id: str, resource: str, params: Optional[dict] = None) -> str:
    return json.dumps({
        "type": MSG_QUERY,
        "server_id": server_id,
        "query_id": query_id,
        "resource": resource,
        "params": params or {},
    })


def parse_message(raw: str) -> Optional[dict]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


class PendingFuture:
    """RPC 关联：task_id/query_id -> asyncio.Future。"""

    def __init__(self, timeout: float = 10.0) -> None:
        self._futures: dict[str, asyncio.Future] = {}
        self._owner: dict[str, str] = {}
        self._timeout = timeout

    def expect(self, req_id: str, owner: str = None) -> asyncio.Future:
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._futures[req_id] = fut
        if owner:
            self._owner[req_id] = owner
        return fut

    def resolve(self, req_id: str, success: bool, data: Any = None, error_message: str = None) -> bool:
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

    def _cleanup(self, req_id: str) -> None:
        self._futures.pop(req_id, None)
        self._owner.pop(req_id, None)

    def cancel_for(self, owner: str) -> None:
        for req_id, o in list(self._owner.items()):
            if o != owner:
                continue
            fut = self._futures.get(req_id)
            if fut and not fut.done():
                fut.cancel()
            self._cleanup(req_id)

    def cancel_all(self) -> None:
        for fut in self._futures.values():
            if not fut.done():
                fut.cancel()
        self._futures.clear()
        self._owner.clear()

    def __len__(self) -> int:
        return len(self._futures)
