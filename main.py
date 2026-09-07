"""astrbot_plugin_minecraft_bridge 插件入口。

通过 WebSocket 将 ZenithProxy (Minecraft) 与 AstrBot 深度集成：
- WS 服务端接收 Minecraft 事件上报
- 平台适配器把游戏聊天注入 AstrBot 消息流
- AI 工具（@filter.llm_tool，定义于本类）供 LLM 控制游戏 Bot

@filter.llm_tool 必须在 Star 子类方法上使用（import 时自注册），
工具业务逻辑见 tools/mc_tools.py。
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

        # Dashboard 消息缓冲 + SSE 订阅者
        self._page_messages: collections.deque = collections.deque(maxlen=200)
        self._page_sse_subscribers: list = []

        # 后台事件消费任务（不依赖 AstrBot 启动适配器）
        self._event_consumer_task = None

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
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/send",
                self._api_send,
                ["POST"],
                "发送消息到 Minecraft",
            )
            self.context.register_web_api(
                "/astrbot_plugin_minecraft_bridge/events",
                self._api_events,
                ["GET"],
                "SSE 实时消息流",
            )
        except Exception as e:
            logger.debug(f"Web API 注册失败（可能不支持）: {e}")

    # ==================== Web API 处理器 ====================

    async def _api_status(self):
        """GET /astrbot_plugin_minecraft_bridge/status - 获取桥接状态。"""
        from astrbot.api.web import json_response
        try:
            # 直接检查 WS 服务器是否在运行
            ws_running = self.bridge.ws_server._runner is not None if self.bridge.ws_server else False
            return json_response({
                "status": "ok",
                "data": {
                    "bridge_on": ws_running or self._bridge_on,
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
                    "minecraft_event_group": self.config.get("minecraft_event_group", ""),
                    "chat_push_enabled": self.config.get("chat_push_enabled", False),
                    "server_event_push_enabled": self.config.get("server_event_push_enabled", False),
                    "llm_reply_enabled": self.config.get("llm_reply_enabled", False),
                    "llm_reply_weight": self.config.get("llm_reply_weight", 1),
                    "chat_rate_limit": self.config.get("chat_rate_limit", 5),
                    "chat_rate_window": self.config.get("chat_rate_window", 60),
                    "inbound_max_message_length": self.config.get("inbound_max_message_length", 1000),
                    "outbound_max_message_length": self.config.get("outbound_max_message_length", 1000),
                    "instance_push_config": self.config.get("instance_push_config", {}),
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
                        "heartbeat_timeout", "rpc_timeout", "group_id_prefix", "bridge_on",
                        "minecraft_event_group", "chat_push_enabled", "server_event_push_enabled",
                        "llm_reply_enabled", "llm_reply_weight", "chat_rate_limit", "chat_rate_window",
                        "inbound_max_message_length", "outbound_max_message_length",
                        "instance_push_config"]:
                if key in payload:
                    self.config[key] = payload[key]

            # 应用到 BridgeManager
            self.bridge.config = dict(self.config)
            self.bridge.rpc_timeout = float(self.config.get("rpc_timeout", 10))
            self.bridge.ws_server.apply_config(self.config)

            # 只有 WS 相关配置变更时才重启
            ws_keys = {"ws_host", "ws_port", "ws_path", "shared_token"}
            if ws_keys & set(payload.keys()) and self._bridge_on and self.bridge.started:
                await self.bridge.stop()
                self.bridge.start()

            return json_response({"status": "ok", "message": "Config saved"})
        except Exception as e:
            from astrbot.api.web import error_response
            return error_response(str(e))

    async def _api_send(self):
        """POST /astrbot_plugin_minecraft_bridge/send - 发送消息到 Minecraft。"""
        from astrbot.api.web import json_response, request
        try:
            payload = await request.json(default={})
            server_id = payload.get("server_id", "")
            message = payload.get("message", "")
            if not server_id or not message:
                from astrbot.api.web import error_response
                return error_response("server_id and message required")
            await self.bridge.send_chat(server_id, message)
            # 本地也推一条
            self.push_page_message(server_id, "Bot", message)
            return json_response({"status": "ok"})
        except Exception as e:
            from astrbot.api.web import error_response
            return error_response(str(e))

    async def _api_events(self):
        """GET /astrbot_plugin_minecraft_bridge/events - SSE 实时消息流。"""
        from astrbot.api.web import stream_response
        queue: asyncio.Queue = asyncio.Queue()
        self._page_sse_subscribers.append(queue)

        async def event_stream():
            try:
                # 先发送历史消息
                for msg in self._page_messages:
                    yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                # 持续推送新消息
                while True:
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=30)
                        yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                if queue in self._page_sse_subscribers:
                    self._page_sse_subscribers.remove(queue)

        return stream_response(event_stream())

    def push_page_message(self, server_id: str, sender: str, content: str):
        """将消息推送到 Dashboard SSE 订阅者。"""
        msg = {
            "server_id": server_id,
            "sender": sender,
            "content": content,
            "time": time.strftime("%H:%M:%S"),
        }
        self._page_messages.append(msg)
        for q in list(self._page_sse_subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    async def initialize(self):
        """异步初始化：按配置启动 WS 服务。"""
        # 设置 Dashboard 消息推送回调
        self.bridge.page_push_callback = self.push_page_message
        if self._bridge_on:
            self.bridge.start()
            logger.info("Minecraft Bridge 插件已加载 (自动启动 WS 服务)")
        # 自动注册平台适配器（参照 mineastr-plugin 模式）
        try:
            await self._ensure_platform()
        except Exception as exc:
            logger.warning(f"自动注册 minecraft_bridge 平台失败: {exc}")
        # 启动后台事件消费任务（不依赖 AstrBot 启动适配器）
        self._event_consumer_task = asyncio.create_task(self._consume_events())
        logger.info("后台事件消费任务已启动")

    async def _ensure_platform(self):
        """确保 minecraft_bridge 平台已注册并启用（参照 mineastr-plugin）。"""
        PLATFORM_TYPE = "minecraft_bridge"
        PLATFORM_ID = "minecraft_bridge"

        manager = getattr(self.context, "platform_manager", None)
        if manager is None:
            logger.debug("platform_manager 不可用，跳过平台自动注册")
            return

        # 检查是否已有运行中的实例
        for inst in getattr(manager, "platform_insts", None) or []:
            meta = getattr(inst, "meta", None)
            if callable(meta) and getattr(meta(), "id", None) == PLATFORM_ID:
                logger.info(f"minecraft_bridge 平台已在运行 (id={PLATFORM_ID})")
                return

        # 获取 AstrBot 主配置
        get_config = getattr(self.context, "get_config", None)
        if not callable(get_config):
            logger.debug("Context 不支持 get_config，跳过平台自动注册")
            return
        core_config = get_config()
        platforms = core_config.get("platform")
        if not isinstance(platforms, list):
            logger.debug("主配置 platform 不是列表，跳过")
            return

        # 查找已有的 minecraft_bridge 平台配置
        candidates = [
            entry for entry in platforms
            if isinstance(entry, dict) and entry.get("type") == PLATFORM_TYPE
        ]

        selected = None
        created = False
        if candidates:
            selected = candidates[0]
        else:
            # 创建新的平台配置
            selected = {
                "type": PLATFORM_TYPE,
                "id": PLATFORM_ID,
                "enable": True,
                "host": self.bridge.config.get("ws_host", "0.0.0.0"),
                "port": self.bridge.config.get("ws_port", 8765),
                "path": self.bridge.config.get("ws_path", "/ws"),
                "token": self.bridge.config.get("shared_token", "change-me"),
            }
            platforms.append(selected)
            created = True

        # 确保启用
        if not selected.get("enable"):
            selected["enable"] = True

        # 保存配置
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

        # 热加载平台（如果管理器已初始化）
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

    async def _consume_events(self):
        """后台消费 event_queue，推送事件到 Dashboard 和 QQ 群。"""
        from .bridge.protocol import (
            EVENT_CHAT, EVENT_WHISPER, EVENT_SYSTEM,
            EVENT_PLAYER_JOIN, EVENT_PLAYER_LEAVE,
            EVENT_DEATH, EVENT_ACHIEVEMENT, EVENT_BOT_STATUS,
        )
        while True:
            try:
                item = await self.bridge.event_queue.get()
                event_type = item.get("event_type")
                server_id = item.get("server_id", "default")
                payload = item.get("data", {})
                logger.info(f"[{server_id}] _consume_events: type={event_type}")

                # 推送到 Dashboard
                cb = self.bridge.page_push_callback
                if cb:
                    if event_type == EVENT_CHAT:
                        cb(server_id, payload.get("sender", ""), payload.get("message", ""))
                    elif event_type == EVENT_WHISPER:
                        cb(server_id, payload.get("sender", ""), f"[私聊→{payload.get('receiver', '')}] {payload.get('message', '')}")
                    elif event_type == EVENT_PLAYER_JOIN:
                        cb(server_id, "System", f"{payload.get('player', '')} 加入了游戏")
                    elif event_type == EVENT_PLAYER_LEAVE:
                        cb(server_id, "System", f"{payload.get('player', '')} 离开了游戏")
                    elif event_type == EVENT_DEATH:
                        cb(server_id, "System", payload.get("death_message", payload.get("message", "Bot 死亡了")))
                    elif event_type == EVENT_ACHIEVEMENT:
                        cb(server_id, "System", f"{payload.get('player', '')} 达成成就: {payload.get('achievement', '')}")
                    elif event_type == EVENT_SYSTEM:
                        cb(server_id, "System", payload.get("message", ""))
                    elif event_type == EVENT_BOT_STATUS:
                        cb(server_id, "System", f"[{payload.get('bot_name', '')}] 状态: {payload.get('status', '')}")

                # 推送到 QQ 群
                await self._push_event_to_group(item)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"事件消费异常: {e}")
                await asyncio.sleep(1)

    async def _push_event_to_group(self, item: dict):
        """推送事件到配置的 QQ 群。"""
        from .bridge.protocol import (
            EVENT_CHAT, EVENT_WHISPER, EVENT_SYSTEM,
            EVENT_PLAYER_JOIN, EVENT_PLAYER_LEAVE,
            EVENT_DEATH, EVENT_ACHIEVEMENT,
        )
        event_type = item.get("event_type")
        server_id = item.get("server_id", "default")
        payload = item.get("data", {})

        # 检查推送开关（优先每实例配置，回退全局配置）
        inst_cfg = self.bridge.config.get("instance_push_config", {}).get(server_id, {})
        if event_type in (EVENT_CHAT, EVENT_WHISPER):
            chat_push = inst_cfg.get("chat_push", self.bridge.config.get("chat_push_enabled", False))
            if not chat_push:
                logger.debug(f"[{server_id}] chat_push=False, 跳过")
                return
        else:
            event_push = inst_cfg.get("event_push", self.bridge.config.get("server_event_push_enabled", False))
            if not event_push:
                logger.debug(f"[{server_id}] event_push=False, 跳过")
                return

        event_group = self.bridge.config.get("minecraft_event_group", "")
        if not event_group:
            logger.debug(f"[{server_id}] minecraft_event_group 为空, 跳过")
            return

        # 格式化消息
        msg = None
        if event_type == EVENT_CHAT:
            msg = f"[{server_id}] {payload.get('sender', 'unknown')}: {payload.get('message', '')}"
        elif event_type == EVENT_WHISPER:
            if not payload.get("outgoing"):
                msg = f"[{server_id}] {payload.get('sender', 'unknown')} -> {payload.get('receiver', '')}: {payload.get('message', '')}"
        elif event_type == EVENT_PLAYER_JOIN:
            msg = f"[{server_id}] 玩家 {payload.get('player', 'unknown')} 加入了游戏"
        elif event_type == EVENT_PLAYER_LEAVE:
            msg = f"[{server_id}] 玩家 {payload.get('player', 'unknown')} 离开了游戏"
        elif event_type == EVENT_DEATH:
            msg = f"[{server_id}] Bot 死亡了"
        elif event_type == EVENT_ACHIEVEMENT:
            msg = f"[{server_id}] 玩家 {payload.get('player', 'unknown')} 达成了成就: {payload.get('achievement', '未知成就')}"
        elif event_type == EVENT_SYSTEM:
            system_msg = payload.get("message", "")
            if system_msg:
                msg = f"[{server_id}] 系统: {system_msg}"

        if not msg:
            return

        # 发送到 QQ 群
        try:
            from astrbot.api.event import MessageChain
            from astrbot.api.message_components import Plain
            from astrbot.core.platform.message_type import MessageType
            chain = MessageChain([Plain(text=msg)])

            # 找到 QQ 平台适配器的 platform_id
            qq_platform_id = None
            for platform in self.context.platform_manager.platform_insts:
                if platform.meta().name in ("aiocqhttp", "qqofficial", "qqofficial_webhook"):
                    qq_platform_id = platform.meta().id
                    break
            if not qq_platform_id:
                logger.warning(f"[{server_id}] 未找到 QQ 平台适配器，跳过推送")
                return

            session = f"{qq_platform_id}:GroupMessage:{event_group}"
            logger.info(f"[{server_id}] 尝试推送到 session={session}: {msg[:80]}")
            await self.context.send_message(session, chain)
            logger.info(f"[{server_id}] 已推送到群 {event_group}: {msg[:50]}...")
        except Exception as e:
            logger.warning(f"[{server_id}] 推送到群失败: {e}", exc_info=True)

    async def terminate(self):
        """插件卸载/停用时清理。"""
        if self._event_consumer_task:
            self._event_consumer_task.cancel()
            try:
                await self._event_consumer_task
            except asyncio.CancelledError:
                pass
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
            logger.debug("[_is_group_allowed] group_id 为空，允许")
            return True
        group_id_str = str(group_id).strip()
        blocked = [str(g).strip() for g in self.config.get("blocked_groups", [])]
        if blocked and group_id_str in blocked:
            logger.info(f"[_is_group_allowed] 群 {group_id_str} 在黑名单中，拒绝")
            return False
        allowed = [str(g).strip() for g in self.config.get("allowed_groups", [])]
        if not allowed:
            logger.debug("[_is_group_allowed] 白名单为空，允许所有群")
            return True
        result = group_id_str in allowed
        logger.info(f"[_is_group_allowed] 群={group_id_str}, 白名单={allowed}, 结果={result}")
        return result

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
        logger.info(f"[mcbridge] 收到命令: group_id={group_id!r}, sender_id={sender_id!r}")
        
        if group_id:
            if not self._is_group_allowed(str(group_id)):
                yield event.plain_result("此群不在白名单中，无法使用此命令")
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
        group_id = event.get_group_id()
        sender_id = event.get_sender_id()
        logger.info(f"[mc] 收到命令: group_id={group_id!r}(type={type(group_id).__name__}), sender_id={sender_id!r}, message={event.message_str[:50]!r}")
        
        if group_id:
            allowed = self._is_group_allowed(str(group_id))
            logger.info(f"[mc] 群 {group_id} 白名单检查结果: {allowed}")
            if not allowed:
                yield event.plain_result("此群不在白名单中，无法使用此命令")
                return
        else:
            logger.info(f"[mc] 私聊消息，跳过白名单检查")

        parts = event.message_str.strip().split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            yield event.plain_result("用法: /mc <消息内容>，或 /mc <server_id> <消息内容>")
            return

        remaining = parts[1].strip()
        first, _, rest = remaining.partition(" ")
        if first in self.bridge.registry.server_ids and rest:
            server_id, message = first, rest.strip()
        else:
            # 自动选择服务器：优先用配置的 default_server_id，否则用第一个连接的实例
            server_id = self.config.get("default_server_id", "default")
            if server_id not in self.bridge.registry.server_ids:
                # default 不在，尝试使用第一个可用实例
                available = self.bridge.registry.server_ids
                if available:
                    server_id = available[0]
                else:
                    yield event.plain_result("❌ 没有已连接的 Minecraft 实例")
                    return
            message = remaining

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