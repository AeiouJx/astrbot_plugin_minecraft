"""astrbot_plugin_minecraft 插件入口。

通过 WebSocket 将 ZenithProxy (Minecraft) 与 AstrBot 集成：
- 平台适配器启动 WS 服务端，接收 ZenithProxy 连接
- chat 事件通过 commit_event() 提交到 AstrBot 事件队列
- AstrBot 框架自动路由到 QQ 等平台
- AI 工具供 LLM 控制游戏 Bot
"""

from __future__ import annotations

import json
import time

from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star
from astrbot.api import AstrBotConfig, logger
from astrbot.api.message_components import Plain


class MinecraftPlugin(Star):
    """Minecraft 插件 - WebSocket 双向消息桥 + AI 控制"""

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}

        # 导入触发适配器注册
        from .adapter import MinecraftPlatformAdapter  # noqa: F401

        # QQ 推送平台 ID（需与 cmd_config.json 中 aiocqhttp 适配器的 id 一致）
        self._qq_platform_id = "小猫咪NapCat"

        # 内容审核器
        from .moderation import ContentModerator
        self._moderator = ContentModerator(self.config, context)

    # ==================== QQ 推送 ====================

    @filter.event_message_type(filter.EventMessageType.ALL, priority=1000)
    async def on_minecraft_event(self, event: AstrMessageEvent) -> None:
        """拦截 Minecraft 事件，推送到 QQ 群。"""
        if event.get_platform_id() != "minecraft":
            return

        qq_group = self.config.get("minecraft_event_group", "")
        if not qq_group:
            return

        from .adapter import protocol

        etype = getattr(event, "platform_event_type", "")
        msg = event.message_str

        # 根据事件类型和对应开关决定是否推送
        push = False
        if etype == protocol.EVENT_CHAT:
            push = self.config.get("push_chat", False)
        elif etype == protocol.EVENT_WHISPER:
            push = self.config.get("push_whisper", False)
        elif etype == protocol.EVENT_PLAYER_JOIN:
            push = self.config.get("push_player_join", False)
        elif etype == protocol.EVENT_PLAYER_LEAVE:
            push = self.config.get("push_player_leave", False)
        elif etype == protocol.EVENT_DEATH:
            push = self.config.get("push_death", False)
        elif etype == protocol.EVENT_ACHIEVEMENT:
            push = self.config.get("push_achievement", False)
        elif etype in (protocol.EVENT_SYSTEM, protocol.EVENT_BOT_STATUS):
            push = self.config.get("push_system", False)
        else:
            return

        if not push:
            return

        # L1 + L2: 违禁词过滤（同步，快速）
        safe, reason = self._moderator.check(msg)
        if not safe:
            logger.debug(f"[MC→QQ] 拦截: {reason} | {msg}")
            return

        # L3: AI 审核（仅聊天消息，异步）
        if etype == protocol.EVENT_CHAT:
            safe, reason = await self._moderator.ai_check(msg)
            if not safe:
                logger.debug(f"[MC→QQ] AI 拦截: {reason} | {msg}")
                return

        # 格式化消息：sender: message\n[server] [event_type] [HH:MM:SS]
        sender_id = event.message_obj.sender.user_id
        etype_label = {
            protocol.EVENT_CHAT: "chat",
            protocol.EVENT_WHISPER: "whisper",
            protocol.EVENT_PLAYER_JOIN: "join",
            protocol.EVENT_PLAYER_LEAVE: "leave",
            protocol.EVENT_DEATH: "death",
            protocol.EVENT_ACHIEVEMENT: "achievement",
            protocol.EVENT_SYSTEM: "system",
            protocol.EVENT_BOT_STATUS: "status",
        }.get(etype, etype)
        if sender_id != "system":
            text = f"{event.message_obj.sender.nickname}: {msg}\n[{event.server_id}] [{etype_label}] [{time.strftime('%H:%M:%S')}]"
        else:
            text = f"{msg}\n[{event.server_id}] [{etype_label}] [{time.strftime('%H:%M:%S')}]"

        session = f"{self._qq_platform_id}:GroupMessage:{qq_group}"
        chain = MessageChain()
        chain.chain.append(Plain(text=text))
        try:
            await self.context.send_message(session, chain)
        except Exception as e:
            logger.warning(f"[MC→QQ] 推送失败: {e}")

    # ==================== 重点关注玩家推送 ====================

    @filter.event_message_type(filter.EventMessageType.ALL, priority=999)
    async def on_focus_player_event(self, event: AstrMessageEvent) -> None:
        """重点关注玩家事件推送到指定群。"""
        if event.get_platform_id() != "minecraft":
            return

        from .adapter import protocol

        etype = getattr(event, "platform_event_type", "")
        sender_id = event.message_obj.sender.user_id

        if etype not in (protocol.EVENT_CHAT, protocol.EVENT_WHISPER,
                         protocol.EVENT_PLAYER_JOIN, protocol.EVENT_PLAYER_LEAVE,
                         protocol.EVENT_DEATH):
            return

        msg = event.message_str
        ts = time.strftime('%H:%M:%S')

        # 格式化消息
        if etype == protocol.EVENT_PLAYER_JOIN:
            text = f"{sender_id} joined the game\n[{event.server_id}] [join] [{ts}]"
        elif etype == protocol.EVENT_PLAYER_LEAVE:
            text = f"{sender_id} left the game\n[{event.server_id}] [leave] [{ts}]"
        elif etype == protocol.EVENT_DEATH:
            text = f"{msg}\n[{event.server_id}] [death] [{ts}]"
        elif etype == protocol.EVENT_WHISPER:
            text = f"{sender_id}: {msg}\n[{event.server_id}] [whisper] [{ts}]"
        else:
            text = f"{sender_id}: {msg}\n[{event.server_id}] [chat] [{ts}]"

        # 收集所有需要推送的 (group) 对
        target_groups: set[str] = set()

        # 1. 旧版 focus_players + focus_group
        focus_group = self.config.get("focus_group", "")
        focus_players = self.config.get("focus_players", [])
        if focus_group and focus_players:
            if self._match_focus_player(etype, sender_id, msg, focus_players):
                target_groups.add(focus_group)

        # 2. 新版 focus_templates (template_list 格式)
        templates = self.config.get("focus_templates", [])
        if isinstance(templates, list):
            for tpl in templates:
                tpl_group = tpl.get("group", "")
                tpl_players = tpl.get("players", [])
                if not tpl_group or not tpl_players:
                    continue
                # 检查事件类型开关
                if etype == protocol.EVENT_CHAT and not tpl.get("push_chat", True):
                    continue
                if etype == protocol.EVENT_WHISPER and not tpl.get("push_whisper", False):
                    continue
                if etype in (protocol.EVENT_PLAYER_JOIN, protocol.EVENT_PLAYER_LEAVE) and not tpl.get("push_join_leave", True):
                    continue
                if etype == protocol.EVENT_DEATH and not tpl.get("push_death", True):
                    continue
                if self._match_focus_player(etype, sender_id, msg, tpl_players):
                    target_groups.add(tpl_group)

        # 去重推送
        for group in target_groups:
            session = f"{self._qq_platform_id}:GroupMessage:{group}"
            chain = MessageChain()
            chain.chain.append(Plain(text=text))
            try:
                await self.context.send_message(session, chain)
            except Exception as e:
                logger.warning(f"[MC→QQ] 重点关注推送失败: {e}")

    @staticmethod
    def _match_focus_player(etype: str, sender_id: str, msg: str, players: list[str]) -> str:
        """检查事件是否匹配关注玩家，返回匹配到的玩家名。"""
        if etype == protocol.EVENT_DEATH:
            for name in players:
                if name in msg:
                    return name
            return ""
        if sender_id in players:
            return sender_id
        return ""

    # ==================== LLM 自动回复控制 ====================

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent) -> None:
        if event.get_platform_id() != "minecraft":
            return
        if not self.config.get("llm_auto_reply", True):
            event.stop_propagation()

    # ==================== 命令 ====================

    @filter.command("mc")
    async def mc_command(self, event: AstrMessageEvent):
        """Minecraft 控制命令。

        用法:
          /mc          查看连接状态
          /mc list     列出已连接的服务器实例
          /mc chat <msg>  发送消息到默认实例
        """
        args = event.message_str.strip().split()
        op = args[1] if len(args) > 1 else "status"

        adapter = self._get_adapter()

        if op == "list":
            if not adapter or not adapter._connections:
                yield event.plain_result("没有已连接的实例")
                return
            lines = [f"- {sid} (account={c.account})" for sid, c in adapter._connections.items()]
            yield event.plain_result("在线实例:\n" + "\n".join(lines))

        elif op == "chat" and len(args) > 2:
            message = " ".join(args[2:])
            if not adapter or not adapter._connections:
                yield event.plain_result("没有已连接的实例")
                return
            for sid, conn in adapter._connections.items():
                await conn.send_task_action("send_chat", {"message": message})
            yield event.plain_result("已发送")

        else:
            if adapter:
                count = len(adapter._connections)
                yield event.plain_result(
                    f"Minecraft 状态:\n"
                    f"- WS 服务: 运行中\n"
                    f"- 在线实例: {count}\n"
                    f"- WS 地址: ws://{adapter.config.get('host', '?')}:{adapter.config.get('port', '?')}"
                )
            else:
                yield event.plain_result("Minecraft 适配器未运行")

    # ==================== LLM 工具 ====================

    @filter.llm_tool(name="mc_status", desc="查询 Minecraft 服务器连接状态")
    async def mc_status(self, event: AstrMessageEvent, server_id: str = ""):
        """查询 Minecraft 服务器连接状态。"""
        adapter = self._get_adapter()
        if not adapter:
            return event.plain_result("适配器未运行")
        if server_id:
            conn = adapter._connections.get(server_id)
            if conn:
                return event.plain_result(json.dumps({
                    "server_id": conn.server_id,
                    "account": conn.account,
                    "online": True,
                }, ensure_ascii=False))
            return event.plain_result(f"实例 {server_id} 未连接")
        return event.plain_result(json.dumps({
            "online_count": len(adapter._connections),
            "instances": list(adapter._connections.keys()),
        }, ensure_ascii=False))

    @filter.llm_tool(name="mc_send_chat", desc="让 Bot 在 Minecraft 服务器发送公共聊天消息")
    async def mc_send_chat(self, event: AstrMessageEvent, server_id: str = "", message: str = ""):
        """发送聊天消息到 MC 服务器。"""
        adapter = self._get_adapter()
        if not adapter:
            return event.plain_result("适配器未运行")
        if server_id:
            conn = adapter._connections.get(server_id)
            if not conn:
                return event.plain_result(f"实例 {server_id} 未连接")
            await conn.send_task_action("send_chat", {"message": message})
            return event.plain_result("已发送")
        for conn in adapter._connections.values():
            await conn.send_task_action("send_chat", {"message": message})
        return event.plain_result("已广播")

    @filter.llm_tool(name="mc_players", desc="获取 Minecraft 服务器在线玩家列表")
    async def mc_players(self, event: AstrMessageEvent, server_id: str = ""):
        """查询在线玩家。"""
        adapter = self._get_adapter()
        if not adapter:
            return event.plain_result("适配器未运行")
        instances = [server_id] if server_id else list(adapter._connections.keys())
        result = {}
        for sid in instances:
            conn = adapter._connections.get(sid)
            if conn:
                result[sid] = {"account": conn.account, "online": True}
            else:
                result[sid] = {"online": False}
        return event.plain_result(json.dumps(result, ensure_ascii=False))

    # ==================== 辅助 ====================

    def _get_adapter(self):
        """获取运行中的 MinecraftPlatformAdapter 实例。"""
        manager = getattr(self.context, "platform_manager", None)
        if not manager:
            return None
        for inst in getattr(manager, "platform_insts", None) or []:
            meta = getattr(inst, "meta", None)
            if callable(meta) and getattr(meta(), "id", None) == "minecraft":
                return inst
        return None
