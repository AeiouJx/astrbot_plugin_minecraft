"""Minecraft Bridge AI 工具的辅助逻辑。

注意：@filter.llm_tool 必须在 Star 子类方法上使用（import 时自注册），
因此工具定义在 main.py 的插件类中，本模块只提供纯辅助函数。
"""

from __future__ import annotations

from typing import Optional

from astrbot.api.event import AstrMessageEvent

from ..bridge import BridgeManager
from ..bridge import protocol as Pr


def _resolve(server: Optional[str], bridge: BridgeManager) -> str:
    if server:
        return server
    default_id = bridge.config.get("default_server_id", "default")
    if default_id in bridge.registry.server_ids:
        return default_id
    # default 不在，用第一个可用实例
    available = bridge.registry.server_ids
    if available:
        return available[0]
    return default_id


def not_connected_msg(e: Exception, server: str) -> str:
    return f"❌ [{server}] {e}"


async def query_bot_status(bridge: BridgeManager, event: AstrMessageEvent, server: Optional[str] = None):
    """查询 Bot 状态并生成结果文本。"""
    server = _resolve(server, bridge)
    try:
        data = await bridge.send_query(server, Pr.RESOURCE_BOT_STATUS)
        pos = data.get("position", {})
        lines = [
            f"状态: {data.get('status', 'unknown')}",
            f"血量: {data.get('health', 'N/A')}",
            f"饥饿: {data.get('food', 'N/A')}",
            f"坐标: ({pos.get('x')}, {pos.get('y')}, {pos.get('z')})",
        ]
        yield event.plain_result(f"[{server}] " + "\n".join(lines))
    except (RuntimeError, TimeoutError) as e:
        yield event.plain_result(not_connected_msg(e, server))


async def query_online_players(bridge: BridgeManager, event: AstrMessageEvent, server: Optional[str] = None):
    """查询在线玩家并生成结果文本。"""
    server = _resolve(server, bridge)
    try:
        data = await bridge.send_query(server, Pr.RESOURCE_ONLINE_PLAYERS)
        players = [p.get("name") for p in data.get("players", [])]
        count = data.get("count", len(players))
        if not players:
            yield event.plain_result(f"[{server}] 当前没有在线玩家")
        else:
            yield event.plain_result(f"[{server}] 在线玩家({count}): " + ", ".join(players))
    except (RuntimeError, TimeoutError) as e:
        yield event.plain_result(not_connected_msg(e, server))


async def query_inventory(bridge: BridgeManager, event: AstrMessageEvent, server: Optional[str] = None):
    """查询背包并生成结果文本。"""
    server = _resolve(server, bridge)
    try:
        data = await bridge.send_query(server, Pr.RESOURCE_INVENTORY)
        items = data.get("items", [])
        if not items:
            yield event.plain_result(f"[{server}] 背包为空")
        else:
            lines = [f"[{server}] 背包({data.get('count', len(items))}格):"]
            for it in items:
                name = it.get("name") or f"id:{it.get('id')}"
                lines.append(f"  - {name} x{it.get('count', 1)}")
            yield event.plain_result("\n".join(lines))
    except (RuntimeError, TimeoutError) as e:
        yield event.plain_result(not_connected_msg(e, server))


async def query_nearby_entities(bridge: BridgeManager, event: AstrMessageEvent, radius: float, server: Optional[str] = None):
    """查询附近实体并生成结果文本。"""
    server = _resolve(server, bridge)
    try:
        data = await bridge.send_query(server, Pr.RESOURCE_NEARBY_ENTITIES, {"radius": float(radius)})
        entities = data.get("entities", [])
        if not entities:
            yield event.plain_result(f"[{server}] 半径 {radius} 内没有实体")
        else:
            lines = [f"[{server}] 附近实体({data.get('count', len(entities))}) 半径{radius}:"]
            for e in entities:
                lines.append(
                    f"  - #{e.get('entity_id')} {e.get('type')} "
                    f"({e.get('player', '')} 距离{e.get('distance', 0):.1f}m "
                    f"@ {e.get('x')},{e.get('y')},{e.get('z')})"
                )
            yield event.plain_result("\n".join(lines))
    except (RuntimeError, TimeoutError) as e:
        yield event.plain_result(not_connected_msg(e, server))


async def do_move(bridge: BridgeManager, event: AstrMessageEvent, x, y, z, server: Optional[str] = None):
    """下发移动任务并生成结果文本。"""
    server = _resolve(server, bridge)
    try:
        await bridge.send_task(server, Pr.ACTION_MOVE_TO, {"x": int(x), "y": int(y), "z": int(z)})
        yield event.plain_result(f"✅ [{server}] Bot 开始寻路前往 ({x}, {y}, {z})")
    except (RuntimeError, TimeoutError) as e:
        yield event.plain_result(not_connected_msg(e, server))


async def do_attack(bridge: BridgeManager, event: AstrMessageEvent, radius: float, server: Optional[str] = None):
    """下发攻击任务并生成结果文本。"""
    server = _resolve(server, bridge)
    try:
        data = await bridge.send_task(server, Pr.ACTION_ATTACK_NEAREST, {"radius": float(radius)})
        if data:
            target = data.get("target") or data.get("attacked")
            yield event.plain_result(f"✅ [{server}] 已攻击目标: {target}")
        else:
            yield event.plain_result(f"[{server}] 附近没有可攻击的目标")
    except (RuntimeError, TimeoutError) as e:
        yield event.plain_result(not_connected_msg(e, server))


async def do_send_chat(bridge: BridgeManager, event: AstrMessageEvent, message: str, server: Optional[str] = None):
    """下发聊天消息并生成结果文本。"""
    server = _resolve(server, bridge)
    try:
        await bridge.send_chat(server, message)
        yield event.plain_result(f"✅ 已让 [{server}] Bot 发送消息")
    except RuntimeError as e:
        yield event.plain_result(not_connected_msg(e, server))