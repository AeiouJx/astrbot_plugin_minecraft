"""astrbot_plugin_minecraft_bridge 插件入口。

通过 WebSocket 将 ZenithProxy (Minecraft) 与 AstrBot 深度集成：
- WS 服务端接收 Minecraft 事件上报
- 平台适配器把游戏聊天注入 AstrBot 消息流
- AI 工具（@filter.llm_tool，定义于本类）供 LLM 控制游戏 Bot

@filter.llm_tool 必须在 Star 子类方法上使用（import 时自注册），
工具业务逻辑见 tools/mc_tools.py。
"""

from __future__ import annotations

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star
from astrbot.api import AstrBotConfig, logger

from .bridge import BridgeManager
from .tools import (
    query_bot_status,
    query_online_players,
    query_inventory,
    query_nearby_entities,
    do_move,
    do_attack,
    do_send_chat,
)


class MinecraftBridgePlugin(Star):
    """Minecraft Bridge 插件 - 双向消息桥接 + AI 控制"""

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}
        self.bridge = BridgeManager.configure(dict(self.config))

        # 导入平台适配器模块以触发注册（仅首次）
        from .adapter import _ensure_registered
        _ensure_registered()

        # 是否开启 WS 服务（启动时再 start）
        self._bridge_on = bool(self.config.get("bridge_on", False))

    async def initialize(self):
        """异步初始化：按配置启动 WS 服务。"""
        if self._bridge_on:
            self.bridge.start()
            logger.info("Minecraft Bridge 插件已加载 (自动启动 WS 服务)")

    async def terminate(self):
        """插件卸载/停用时清理。"""
        await self.bridge.stop()
        logger.info("Minecraft Bridge 插件已卸载")

    # ==================== 命令 ====================

    @filter.command("mcbridge")
    async def bridge_command(self, event: AstrMessageEvent):
        """Minecraft Bridge 控制命令。

        用法:
          /mcbridge        查看桥接状态
          /mcbridge on     启动 WS 服务
          /mcbridge off    停止 WS 服务
          /mcbridge list   列出已连接的服务器实例
        """
        args = event.message_str.strip().split()
        op = args[1] if len(args) > 1 else "status"

        if op == "on":
            self._bridge_on = True
            self.bridge.start()
            yield event.plain_result("✅ WS 桥接服务已启动")
        elif op == "off":
            self._bridge_on = False
            await self.bridge.stop()
            yield event.plain_result("🛑 WS 桥接服务已停止")
        elif op == "list":
            servs = self.bridge.registry.server_ids
            if servs:
                yield event.plain_result(f"已连接实例 ({len(servs)}):\n" + "\n".join(f"  - {s}" for s in servs))
            else:
                yield event.plain_result("暂无已连接的 Minecraft 实例")
        else:  # status
            online = self.bridge.registry.online_count
            servs = self.bridge.registry.server_ids
            msg = [
                f"WS 服务: {'✅ 运行中' if self._bridge_on else '❌ 未启动'}",
                f"监听: ws://{self.config.get('ws_host', '0.0.0.0')}:{self.config.get('ws_port', 8765)}",
                f"已连接实例: {online}",
            ]
            if servs:
                msg.append("实例列表: " + ", ".join(servs))
            yield event.plain_result("\n".join(msg))

    @filter.command("mc")
    async def send_chat_command(self, event: AstrMessageEvent):
        """向 Minecraft 服务器发送聊天消息。

        用法: /mc <消息内容> 或 /mc <server_id> <消息内容>
        """
        parts = event.message_str.strip().split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            yield event.plain_result("用法: /mc <消息内容>，或 /mc <server_id> <消息内容>")
            return

        remaining = parts[1].strip()
        first, _, rest = remaining.partition(" ")
        if first in self.bridge.registry.server_ids and rest:
            server_id, message = first, rest.strip()
        else:
            server_id, message = self.config.get("default_server_id", "default"), remaining

        try:
            await self.bridge.send_chat(server_id, message)
            yield event.plain_result(f"✅ 已向 [{server_id}] 发送: {message}")
        except RuntimeError as e:
            yield event.plain_result(f"❌ {e}")

    # ==================== AI 工具（@filter.llm_tool，import 时自注册）====================

    @filter.llm_tool(name="get_server_status")
    async def get_server_status(self, event: AstrMessageEvent, server: str = None) -> MessageEventResult:
        """获取指定 Minecraft 服务器的连接状态，包括在线状态、血量、饥饿值和坐标。

        Args:
            server(string): 服务器实例 ID，默认为 default_server_id。
        """
        async for r in query_bot_status(self.bridge, event, server):
            yield r

    @filter.llm_tool(name="get_online_players")
    async def get_online_players(self, event: AstrMessageEvent, server: str = None) -> MessageEventResult:
        """获取指定 Minecraft 服务器当前在线的玩家名单及人数。

        Args:
            server(string): 服务器实例 ID，默认为 default_server_id。
        """
        async for r in query_online_players(self.bridge, event, server):
            yield r

    @filter.llm_tool(name="get_bot_state")
    async def get_bot_state(self, event: AstrMessageEvent, server: str = None) -> MessageEventResult:
        """获取 Bot 的详细状态，包括在线状态、血量、饥饿值、坐标和手持物品槽位。

        Args:
            server(string): 服务器实例 ID，默认为 default_server_id。
        """
        async for r in query_bot_status(self.bridge, event, server):
            yield r

    @filter.llm_tool(name="get_inventory")
    async def get_inventory(self, event: AstrMessageEvent, server: str = None) -> MessageEventResult:
        """获取 Bot 的背包物品列表及其数量。

        Args:
            server(string): 服务器实例 ID，默认为 default_server_id。
        """
        async for r in query_inventory(self.bridge, event, server):
            yield r

    @filter.llm_tool(name="get_nearby_entities")
    async def get_nearby_entities(self, event: AstrMessageEvent, radius: float = 32.0, server: str = None) -> MessageEventResult:
        """获取 Bot 附近指定半径内的实体列表，按距离升序排列。

        Args:
            radius(number): 搜索半径（方块），默认 32。
            server(string): 服务器实例 ID，默认为 default_server_id。
        """
        async for r in query_nearby_entities(self.bridge, event, radius, server):
            yield r

    @filter.llm_tool(name="move_bot")
    async def move_bot(self, event: AstrMessageEvent, x: float, y: float, z: float, server: str = None) -> MessageEventResult:
        """让 Bot 使用 baritone 寻路移动到指定坐标。

        Args:
            x(number): 目标 X 坐标。
            y(number): 目标 Y 坐标。
            z(number): 目标 Z 坐标。
            server(string): 服务器实例 ID，默认为 default_server_id。
        """
        async for r in do_move(self.bridge, event, x, y, z, server):
            yield r

    @filter.llm_tool(name="attack_nearest")
    async def attack_nearest(self, event: AstrMessageEvent, radius: float = 16.0, server: str = None) -> MessageEventResult:
        """让 Bot 攻击半径内最近的非玩家攻击性实体。

        Args:
            radius(number): 搜索半径（方块），默认 16。
            server(string): 服务器实例 ID，默认为 default_server_id。
        """
        async for r in do_attack(self.bridge, event, radius, server):
            yield r

    @filter.llm_tool(name="send_chat")
    async def send_chat_tool(self, event: AstrMessageEvent, message: str, server: str = None) -> MessageEventResult:
        """让 Bot 在指定 Minecraft 服务器发送一条公共聊天消息。

        Args:
            message(string): 要发送的聊天内容。
            server(string): 服务器实例 ID，默认为 default_server_id。
        """
        async for r in do_send_chat(self.bridge, event, message, server):
            yield r