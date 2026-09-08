"""astrbot_plugin_minecraft_bridge 插件入口。

通过 WebSocket 将 ZenithProxy (Minecraft) 与 AstrBot 深度集成：
- 平台适配器直接启动 WS 服务端，接收 ZenithProxy 连接
- chat/whisper 事件通过 commit_event() 提交到 AstrBot 事件队列
- AstrBot 框架自动路由到 QQ 等平台
- AI 工具供 LLM 控制游戏 Bot
"""
from __future__ import annotations

import asyncio
import collections
import json
import time

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
        self.bridge = BridgeManager.configure(dict(self.config))
        self.bridge.context = context

        # 导入平台适配器模块以触发注册
        from .adapter import MinecraftPlatformAdapter  # noqa: F401

        self._bridge_on = bool(self.config.get("bridge_on", False))

        # Dashboard 消息缓冲 + SSE 订阅者
        self._page_messages: collections.deque = collections.deque(maxlen=200)
        self._page_sse_subscribers: list = []

        # 注册 Web API 端点
        self._register_web_apis()

    def _register_web_apis(self):
        """注册自定义 Web API 端点。"""
        try:
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/status",
                self._api_status, ["GET"], "获取桥接状态信息",
            )
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/servers",
                self._api_servers, ["GET"], "获取已连接服务器列表",
            )
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/start",
                self._api_start, ["POST"], "启动 WS 服务",
            )
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/stop",
                self._api_stop, ["POST"], "停止 WS 服务",
            )
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/config",
                self._api_get_config, ["GET"], "获取当前配置",
            )
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/config/save",
                self._api_save_config, ["POST"], "保存配置",
            )
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/send",
                self._api_send, ["POST"], "发送消息到 Minecraft",
            )
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/events",
                self._api_events, ["GET"], "SSE 实时消息流",
            )
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/players",
                self._api_players, ["GET"], "获取在线玩家列表",
            )
        except Exception as e:
            logger.debug(f"Web API 注册失败（可能不支持）: {e}")

    # ==================== Web API ====================

    async def _api_status(self):
        from astrbot.api.web import json_response
        adapter = self._get_adapter()
        ws_running = adapter is not None
        return json_response({
            "status": "ok",
            "bridge_on": self._bridge_on,
            "ws_running": ws_running,
            "ws_host": self.bridge.config.get("host", "0.0.0.0"),
            "ws_port": self.bridge.config.get("port", 8765),
            "online_count": self.bridge.registry.online_count,
        })

    async def _api_servers(self):
        from astrbot.api.web import json_response
        servers = [info for info in self.bridge.registry.get_all_connection_info() if info]
        return json_response({
            "status": "ok",
            "data": {"servers": servers, "count": len(servers)},
        })

    async def _api_start(self):
        from astrbot.api.web import json_response
        self._bridge_on = True
        self.bridge.start()
        return json_response({"status": "ok", "message": "WS 服务已启动"})

    async def _api_stop(self):
        from astrbot.api.web import json_response
        self._bridge_on = False
        await self.bridge.stop()
        return json_response({"status": "ok", "message": "WS 服务已停止"})

    async def _api_get_config(self):
        from astrbot.api.web import json_response
        config = dict(self.bridge.config)
        return json_response({"status": "ok", "data": config})

    async def _api_save_config(self):
        from astrbot.api.web import json_response
        from astrbot.api.web import Request
        try:
            body = await Request.body()
            new_config = json.loads(body) if body else {}
            ws_changed = (
                new_config.get("host") != self.bridge.config.get("host") or
                new_config.get("port") != self.bridge.config.get("port") or
                new_config.get("token") != self.bridge.config.get("token")
            )
            self.bridge.config.update(new_config)
            self.config.update(new_config)
            if ws_changed and self._bridge_on:
                await self.bridge.stop()
                self.bridge.start()
            return json_response({"status": "ok", "message": "配置已保存"})
        except Exception as e:
            return json_response({"status": "error", "message": str(e)}, status=500)

    async def _api_send(self):
        from astrbot.api.web import json_response
        from astrbot.api.web import Request
        try:
            body = await Request.body()
            data = json.loads(body) if body else {}
            server_id = data.get("server_id")
            message = data.get("message", "")
            if not server_id or not message:
                return json_response({"status": "error", "message": "缺少 server_id 或 message"}, status=400)
            await self.bridge.send_chat(server_id, message)
            return json_response({"status": "ok"})
        except Exception as e:
            return json_response({"status": "error", "message": str(e)}, status=500)

    async def _api_events(self):
        from astrbot.api.web import json_response, StreamingResponse
        import asyncio
        queue = asyncio.Queue()
        self._page_sse_subscribers.append(queue)

        async def event_stream():
            try:
                while True:
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=30)
                        yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                if queue in self._page_sse_subscribers:
                    self._page_sse_subscribers.remove(queue)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    async def _api_players(self):
        from astrbot.api.web import json_response
        result = {}
        for server_id in self.bridge.registry.server_ids:
            try:
                data = await self.bridge.send_query(server_id, "online_players", timeout=5)
                result[server_id] = data
            except Exception:
                result[server_id] = {"players": []}
        return json_response({"status": "ok", "data": result})

    # ==================== Dashboard ====================

    def push_page_message(self, server_id: str, sender: str, content: str, msg_type: str = "chat"):
        """将消息推送到 Dashboard SSE 订阅者。"""
        conn_info = self.bridge.registry.get_connection_info(server_id)
        account = (conn_info or {}).get("account", "") or server_id
        msg = {
            "server_id": server_id,
            "account": account,
            "sender": sender,
            "content": content,
            "time": time.strftime("%H:%M:%S"),
            "type": msg_type,
        }
        self._page_messages.append(msg)
        for q in list(self._page_sse_subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    def _get_adapter(self):
        """获取运行中的 MinecraftPlatformAdapter 实例。"""
        manager = getattr(self.context, "platform_manager", None)
        if not manager:
            return None
        for inst in getattr(manager, "platform_insts", None) or []:
            meta = getattr(inst, "meta", None)
            if callable(meta) and getattr(meta(), "id", None) == "minecraft_bridge":
                return inst
        return None

    # ==================== 生命周期 ====================

    async def initialize(self):
        """异步初始化。"""
        self.bridge.page_push_callback = self.push_page_message
        if self._bridge_on:
            self.bridge.start()
            logger.info("Minecraft Bridge 插件已加载")
        try:
            await self._ensure_platform()
        except Exception as exc:
            logger.warning(f"自动注册 minecraft_bridge 平台失败: {exc}")

    async def _ensure_platform(self):
        """确保 minecraft_bridge 平台已注册并启用。"""
        PLATFORM_TYPE = "minecraft_bridge"
        PLATFORM_ID = "minecraft_bridge"

        manager = getattr(self.context, "platform_manager", None)
        if manager is None:
            return

        for inst in getattr(manager, "platform_insts", None) or []:
            meta = getattr(inst, "meta", None)
            if callable(meta) and getattr(meta(), "id", None) == PLATFORM_ID:
                logger.info(f"minecraft_bridge 平台已在运行 (id={PLATFORM_ID})")
                return

        get_config = getattr(self.context, "get_config", None)
        if not callable(get_config):
            return
        core_config = get_config()
        platforms = core_config.get("platform")
        if not isinstance(platforms, list):
            return

        candidates = [
            entry for entry in platforms
            if isinstance(entry, dict) and entry.get("type") == PLATFORM_TYPE
        ]

        selected = None
        created = False
        if candidates:
            selected = candidates[0]
        else:
            selected = {
                "type": PLATFORM_TYPE,
                "id": PLATFORM_ID,
                "enable": True,
                "host": self.bridge.config.get("host", "0.0.0.0"),
                "port": self.bridge.config.get("port", 8765),
                "path": self.bridge.config.get("path", "/ws"),
                "token": self.bridge.config.get("token", "change-me"),
            }
            platforms.append(selected)
            created = True

        if not selected.get("enable"):
            selected["enable"] = True

        save_config = getattr(core_config, "save_config", None)
        if callable(save_config):
            try:
                saved = save_config()
                import inspect
                if inspect.isawaitable(saved):
                    await saved
            except Exception as exc:
                if created:
                    platforms.remove(selected)
                raise RuntimeError(f"保存平台配置失败: {exc}") from exc

        instances = getattr(manager, "platform_insts", None)
        tasks = getattr(manager, "_platform_tasks", None)
        manager_initialized = (isinstance(instances, list) and instances) or bool(tasks)

        if manager_initialized:
            import inspect
            reload_fn = getattr(manager, "reload", None) or getattr(manager, "load_platform", None)
            if callable(reload_fn):
                result = reload_fn(selected)
                if inspect.isawaitable(result):
                    await result
                logger.info(f"minecraft_bridge 平台已热加载 (id={PLATFORM_ID})")
            else:
                logger.warning("平台管理器不支持 reload/load_platform")
        else:
            logger.info(f"minecraft_bridge 平台已注册，等待 AstrBot 启动 (id={PLATFORM_ID})")

    async def terminate(self):
        """插件卸载/停用时清理。"""
        await self.bridge.stop()
        from .bridge import runtime_state
        runtime_state.set_bridge_manager(None)
        logger.info("Minecraft Bridge 插件已卸载")

    # ==================== LLM 请求拦截 ====================

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, request):
        """动态注入工具提示到 LLM 系统提示。"""
        platform_id = getattr(event, "platform_id", "")
        message_text = (getattr(event, "message_str", "") or "").lower()

        is_minecraft = platform_id == "minecraft_bridge"
        has_keywords = any(kw in message_text for kw in ["mc", "minecraft", "bot", "服务器", "玩家", "背包"])

        if not is_minecraft and not has_keywords:
            return

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
            if hasattr(request, "system_prompt") and request.system_prompt:
                request.system_prompt += "\n\n" + injection
            else:
                request.system_prompt = injection

    # ==================== 命令 ====================

    def _is_group_allowed(self, group_id: str) -> bool:
        """检查群聊是否允许使用 Minecraft Bridge。"""
        if not group_id:
            return True
        group_id_str = str(group_id).strip()
        blocked = [str(g).strip() for g in self.config.get("blocked_groups", [])]
        if blocked and group_id_str in blocked:
            return False
        allowed = [str(g).strip() for g in self.config.get("allowed_groups", [])]
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
        group_id = event.get_group_id()
        sender_id = event.get_sender_id()

        if group_id:
            if not self._is_group_allowed(str(group_id)):
                yield event.plain_result("此群不在白名单中，无法使用此命令")
                return

        args = event.message_str.strip().split()
        op = args[1] if len(args) > 1 else "status"

        if op == "on":
            self._bridge_on = True
            self.bridge.start()
            yield event.plain_result("WS 桥接服务已启动")
        elif op == "off":
            self._bridge_on = False
            await self.bridge.stop()
            yield event.plain_result("WS 桥接服务已停止")
        elif op == "list":
            infos = self.bridge.registry.get_all_connection_info()
            if not infos:
                yield event.plain_result("当前没有已连接的服务器实例")
                return
            lines = []
            for info in infos:
                if info:
                    lines.append(f"- {info['server_id']} (account={info.get('account', '?')}, mod={info.get('mod_version', '?')})")
            yield event.plain_result("已连接的实例:\n" + "\n".join(lines))
        else:
            online = self.bridge.registry.online_count
            yield event.plain_result(
                f"Minecraft Bridge 状态:\n"
                f"- WS 服务: {'运行中' if self.bridge.started else '未启动'}\n"
                f"- 在线实例: {online}\n"
                f"- WS 地址: ws://{self.bridge.config.get('host', '?')}:{self.bridge.config.get('port', '?')}"
            )

    # ==================== LLM 工具 ====================

    @filter.llm_tool(name="get_server_status", desc="查询 Minecraft 服务器连接状态和 Bot 基本信息（血量/饥饿/坐标）")
    async def get_server_status(self, event: AstrMessageEvent, server_id: str = ""):
        """查询 Minecraft 服务器状态。"""
        try:
            result = await query_bot_status(self.bridge, server_id)
            return event.plain_result(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            return event.plain_result(f"查询失败: {e}")

    @filter.llm_tool(name="get_online_players", desc="获取当前在线玩家列表及人数")
    async def get_online_players(self, event: AstrMessageEvent, server_id: str = ""):
        """获取在线玩家列表。"""
        try:
            result = await query_online_players(self.bridge, server_id)
            return event.plain_result(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            return event.plain_result(f"查询失败: {e}")

    @filter.llm_tool(name="get_inventory", desc="获取 Bot 背包物品列表及数量")
    async def get_inventory(self, event: AstrMessageEvent, server_id: str = ""):
        """获取 Bot 背包。"""
        try:
            result = await query_inventory(self.bridge, server_id)
            return event.plain_result(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            return event.plain_result(f"查询失败: {e}")

    @filter.llm_tool(name="get_nearby_entities", desc="获取 Bot 附近实体（可指定搜索半径）")
    async def get_nearby_entities(self, event: AstrMessageEvent, server_id: str = "", radius: int = 16):
        """获取附近实体。"""
        try:
            result = await query_nearby_entities(self.bridge, server_id, radius)
            return event.plain_result(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            return event.plain_result(f"查询失败: {e}")

    @filter.llm_tool(name="move_bot", desc="让 Bot 使用 baritone 寻路移动到指定坐标")
    async def move_bot(self, event: AstrMessageEvent, server_id: str = "", x: float = 0, y: float = 0, z: float = 0):
        """移动 Bot 到指定坐标。"""
        try:
            result = await do_move(self.bridge, server_id, x, y, z)
            return event.plain_result(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            return event.plain_result(f"移动失败: {e}")

    @filter.llm_tool(name="attack_nearest", desc="让 Bot 攻击附近最近的攻击性实体")
    async def attack_nearest(self, event: AstrMessageEvent, server_id: str = ""):
        """攻击最近的实体。"""
        try:
            result = await do_attack(self.bridge, server_id)
            return event.plain_result(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            return event.plain_result(f"攻击失败: {e}")

    @filter.llm_tool(name="send_chat", desc="让 Bot 在 Minecraft 服务器发送公共聊天消息")
    async def send_chat(self, event: AstrMessageEvent, server_id: str = "", message: str = ""):
        """发送聊天消息到 MC 服务器。"""
        try:
            result = await do_send_chat(self.bridge, server_id, message)
            return event.plain_result(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            return event.plain_result(f"发送失败: {e}")
