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

# 工具提示：根据可用工具动态注入 LLM 系统提示
TOOL_HINTS = {
    "get_server_status": "调用 get_server_status 可查询 Minecraft 服务器连接状态、Bot 血量/饥饿/坐标。",
    "get_online_players": "调用 get_online_players 可获取当前在线玩家列表及人数。",
    "get_bot_state": "调用 get_bot_state 可获取 Bot 详细状态（血量、饥饿值、坐标、手持物品）。",
    "get_inventory": "调用 get_inventory 可获取 Bot 背包物品列表及数量。",
    "get_nearby_entities": "调用 get_nearby_entities 可获取 Bot 附近实体（可指定搜索半径）。",
    "move_bot": "调用 move_bot 可让 Bot 使用 baritone 寻路移动到指定坐标。",
    "attack_nearest": "调用 attack_nearest 可让 Bot 攻击附近最近的攻击性实体。",
    "send_chat": "调用 send_chat 可让 Bot 在 Minecraft 服务器发送公共聊天消息。",
}

SAFETY_HINT = (
    "\n\n[安全提示] Bot 在 Minecraft 世界中执行操作时，请注意："
    "\n- 移动和攻击操作可能消耗游戏资源或触发危险"
    "\n- 建议先查询状态再决定是否执行动作"
    "\n- 避免在没有玩家监督的情况下执行不可逆操作"
)


class MinecraftBridgePlugin(Star):
    """Minecraft Bridge 插件 - 双向消息桥接 + AI 控制"""

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}
        logger.info(f"MinecraftBridgePlugin.__init__: config keys={list(self.config.keys())}, ws_host={self.config.get('ws_host')!r}")
        self.bridge = BridgeManager.configure(dict(self.config))
        self.bridge.context = context  # 传递 context 给 BridgeManager 供 LLM 调用

        # 导入平台适配器模块以触发注册（仅首次）
        from .adapter import _ensure_registered
        _ensure_registered()

        # 是否开启 WS 服务（启动时再 start）
        self._bridge_on = bool(self.config.get("bridge_on", False))

        # 注册 Web API 端点
        self._register_web_apis()

    def _register_web_apis(self):
        """注册自定义 Web API 端点（插件 Pages 面板可访问）。"""
        try:
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/status",
                self._api_status,
                ["GET"],
                "获取桥接状态信息",
            )
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/servers",
                self._api_servers,
                ["GET"],
                "获取已连接服务器列表",
            )
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/start",
                self._api_start,
                ["POST"],
                "启动 WS 服务",
            )
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/stop",
                self._api_stop,
                ["POST"],
                "停止 WS 服务",
            )
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/config",
                self._api_get_config,
                ["GET"],
                "获取当前配置",
            )
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/config/save",
                self._api_save_config,
                ["POST"],
                "保存配置",
            )
        except Exception as e:
            logger.debug(f"Web API 注册失败（可能不支持）: {e}")

    # ==================== Web API 处理器 ====================

    async def _api_status(self):
        """GET /astrbot_plugin_minecraft_bridge/status - 获取桥接状态。"""
        from astrbot.api.web import json_response
        try:
            return json_response({
                "status": "ok",
                "data": {
                    "bridge_on": self._bridge_on,
                    "ws_host": self.config.get("ws_host", "0.0.0.0"),
                    "ws_port": self.config.get("ws_port", 8765),
                    "ws_path": self.config.get("ws_path", "/ws"),
                    "online_count": self.bridge.registry.online_count,
                    "connected_servers": self.bridge.registry.server_ids,
                    "pending_queries": len(self.bridge.registry.pending),
                }
            })
        except Exception as e:
            from astrbot.api.web import error_response
            return error_response(str(e))

    async def _api_servers(self):
        """GET /astrbot_plugin_minecraft_bridge/servers - 获取已连接服务器详情。"""
        from astrbot.api.web import json_response
        try:
            servers = []
            for info in self.bridge.registry.get_all_connection_info():
                if info is not None:
                    servers.append(info)
            return json_response({
                "status": "ok",
                "data": {
                    "servers": servers,
                    "count": len(servers),
                }
            })
        except Exception as e:
            from astrbot.api.web import error_response
            return error_response(str(e))

    async def _api_start(self):
        """POST /astrbot_plugin_minecraft_bridge/start - 启动 WS 服务。"""
        from astrbot.api.web import json_response
        try:
            if self._bridge_on:
                return json_response({"status": "ok", "message": "WS 服务已在运行"})
            self._bridge_on = True
            self.bridge.start()
            return json_response({"status": "ok", "message": "WS 服务已启动"})
        except Exception as e:
            from astrbot.api.web import error_response
            return error_response(str(e))

    async def _api_stop(self):
        """POST /astrbot_plugin_minecraft_bridge/stop - 停止 WS 服务。"""
        from astrbot.api.web import json_response
        try:
            if not self._bridge_on:
                return json_response({"status": "ok", "message": "WS 服务未在运行"})
            self._bridge_on = False
            await self.bridge.stop()
            return json_response({"status": "ok", "message": "WS 服务已停止"})
        except Exception as e:
            from astrbot.api.web import error_response
            return error_response(str(e))

    async def _api_get_config(self):
        """GET /astrbot_plugin_minecraft_bridge/config - 获取当前配置。"""
        from astrbot.api.web import json_response
        try:
            return json_response({
                "status": "ok",
                "data": {
                    "ws_host": self.config.get("ws_host", "0.0.0.0"),
                    "ws_port": self.config.get("ws_port", 8765),
                    "ws_path": self.config.get("ws_path", "/ws"),
                    "shared_token": self.config.get("shared_token", "change-me"),
                    "default_server_id": self.config.get("default_server_id", "default"),
                    "heartbeat_timeout": self.config.get("heartbeat_timeout", 15),
                    "rpc_timeout": self.config.get("rpc_timeout", 10),
                    "group_id_prefix": self.config.get("group_id_prefix", "minecraft"),
                    "bridge_on": self.config.get("bridge_on", False),
                }
            })
        except Exception as e:
            from astrbot.api.web import error_response
            return error_response(str(e))

    async def _api_save_config(self):
        """POST /astrbot_plugin_minecraft_bridge/config/save - 保存配置。"""
        from astrbot.api.web import json_response, request
        try:
            payload = await request.json(default={})
            if not payload:
                from astrbot.api.web import error_response
                return error_response("No config data provided")

            # 更新配置
            for key in ["ws_host", "ws_port", "ws_path", "shared_token", "default_server_id",
                        "heartbeat_timeout", "rpc_timeout", "group_id_prefix", "bridge_on"]:
                if key in payload:
                    self.config[key] = payload[key]

            # 应用到 BridgeManager
            self.bridge.config = dict(self.config)
            self.bridge.rpc_timeout = float(self.config.get("rpc_timeout", 10))
            self.bridge.ws_server.apply_config(self.config)

            # 如果 WS 服务正在运行，重启以应用新配置
            if self._bridge_on and self.bridge.started:
                await self.bridge.stop()
                self.bridge.start()

            return json_response({"status": "ok", "message": "Config saved"})
        except Exception as e:
            from astrbot.api.web import error_response
            return error_response(str(e))

    async def initialize(self):
        """异步初始化：按配置启动 WS 服务。"""
        if self._bridge_on:
            self.bridge.start()
            logger.info("Minecraft Bridge 插件已加载 (自动启动 WS 服务)")

    async def terminate(self):
        """插件卸载/停用时清理。"""
        await self.bridge.stop()
        # 清理运行时状态，避免重载时端口冲突
        from .bridge import runtime_state
        runtime_state.set_bridge_manager(None)
        logger.info("Minecraft Bridge 插件已卸载")

    # ==================== LLM 请求拦截 ====================

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, request):
        """动态注入工具提示到 LLM 系统提示。"""
        # 仅处理来自 minecraft_bridge 平台或包含关键词的消息
        platform_id = getattr(event, "platform_id", "")
        message_text = (getattr(event, "message_str", "") or "").lower()

        is_minecraft = platform_id == "minecraft_bridge"
        has_keywords = any(kw in message_text for kw in ["mc", "minecraft", "bot", "服务器", "玩家", "背包"])

        if not is_minecraft and not has_keywords:
            return

        # 收集可用工具的提示
        available_tools = [
            "get_server_status", "get_online_players", "get_bot_state",
            "get_inventory", "get_nearby_entities", "move_bot",
            "attack_nearest", "send_chat",
        ]
        hints = [TOOL_HINTS[name] for name in available_tools if name in TOOL_HINTS]
        if hints:
            prompt_parts = ["[Minecraft Bridge 工具提示] 你可以使用以下工具与 Minecraft 服务器交互："]
            prompt_parts.extend(hints)
            prompt_parts.append(SAFETY_HINT)
            injection = "\n".join(prompt_parts)
            # 追加到系统提示
            if hasattr(request, "system_prompt") and request.system_prompt:
                request.system_prompt += "\n\n" + injection
            else:
                request.system_prompt = injection

    # ==================== 命令 ====================

    def _is_group_allowed(self, group_id: str) -> bool:
        """检查群聊是否允许使用 Minecraft Bridge。"""
        if not group_id:
            return True
        group_id_str = str(group_id)
        blocked = [str(g) for g in self.config.get("blocked_groups", [])]
        if blocked and group_id_str in blocked:
            return False
        allowed = [str(g) for g in self.config.get("allowed_groups", [])]
        if not allowed:
            return True
        return group_id_str in allowed

    @filter.command("mcbridge")
    async def bridge_command(self, event: AstrMessageEvent):
        """Minecraft Bridge 控制命令。

        用法:
          /mcbridge        查看桥接状态
          /mcbridge on     启动 WS 服务
          /mcbridge off    停止 WS 服务
          /mcbridge list   列出已连接的服务器实例
        """
        group_id = event.group_id if hasattr(event, 'group_id') else None
        logger.debug(f"[mcbridge] group_id={group_id!r}, type={type(group_id).__name__}")
        if group_id and not self._is_group_allowed(group_id):
            logger.debug(f"[mcbridge] group {group_id} not allowed")
            return

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
        group_id = event.group_id if hasattr(event, 'group_id') else None
        logger.debug(f"[mc] group_id={group_id!r}, type={type(group_id).__name__}")
        if group_id and not self._is_group_allowed(group_id):
            logger.debug(f"[mc] group {group_id} not allowed")
            return

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