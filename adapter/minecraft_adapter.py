"""MinecraftPlatformAdapter：minecraft 虚拟平台适配器。

将 BridgeManager 事件队列中的 chat/whisper 事件转换为
AstrBotMessage，包装成 MinecraftEvent 提交到 AstrBot 事件总线。
"""

from __future__ import annotations

import asyncio
import uuid

from astrbot.api import logger
from astrbot.api.platform import (
    Platform,
    AstrBotMessage,
    MessageMember,
    MessageType,
    PlatformMetadata,
    register_platform_adapter,
)
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain
from astrbot.core.platform.message_session import MessageSesion

from ..bridge import BridgeManager
from ..bridge.protocol import EVENT_CHAT, EVENT_WHISPER
from .minecraft_event import MinecraftEvent


_registered = False

CONFIG_METADATA = {
    "ws_host": {
        "description": "WebSocket 监听地址",
        "hint": "建议绑定内网地址，如 0.0.0.0 或局域网 IP",
        "type": "string",
    },
    "ws_port": {
        "description": "WebSocket 监听端口",
        "hint": "与 ZenithProxy 插件 bridge.wsPort 一致",
        "type": "int",
    },
    "ws_path": {
        "description": "WebSocket 路径",
        "hint": "默认 /ws，两端需一致",
        "type": "string",
    },
    "shared_token": {
        "description": "连接认证 Token",
        "hint": "两端必须完全一致，建议改为随机字符串，勿使用默认值",
        "type": "string",
        "secret": True,
    },
    "default_server_id": {
        "description": "默认服务器实例 ID",
        "hint": "AI 工具未指定 server 时使用的默认实例",
        "type": "string",
    },
    "heartbeat_timeout": {
        "description": "心跳超时秒数",
        "hint": "超过该时间未收到心跳则判定客户端离线",
        "type": "int",
    },
    "rpc_timeout": {
        "description": "RPC 超时秒数",
        "hint": "task/query 等待结果的最大秒数",
        "type": "int",
    },
    "group_id_prefix": {
        "description": "虚拟群 ID 前缀",
        "hint": "生成格式: {prefix}:{server_id}，一般不需要修改",
        "type": "string",
    },
    "bridge_on": {
        "description": "开机自启 WS 服务",
        "hint": "插件加载时自动启动 WebSocket 服务（运行中可用 Dashboard 按钮临时启停）",
        "type": "bool",
    },
    "allowed_groups": {
        "description": "允许使用的群号列表",
        "hint": "留空表示所有群都可用；填写后仅这些群可使用 Minecraft Bridge 命令",
        "type": "list",
    },
    "blocked_groups": {
        "description": "禁止使用的群号列表",
        "hint": "这些群无法使用 Minecraft Bridge 命令（优先级高于白名单）",
        "type": "list",
    },
    "server_event_push_enabled": {
        "description": "启用 Minecraft 事件推送",
        "hint": "接收并投递 Mod 发来的玩家上下线、死亡和公开成就事件",
        "type": "bool",
    },
    "minecraft_event_group": {
        "description": "Minecraft 事件推送群号",
        "hint": "留空不推送；填写后游戏事件会推送到该群",
        "type": "string",
    },
    "inbound_max_message_length": {
        "description": "入站消息最大长度",
        "hint": "单条 Minecraft 消息转发到 AstrBot 前允许的最大长度，超出部分会被截断",
        "type": "int",
    },
    "outbound_max_message_length": {
        "description": "出站消息最大长度",
        "hint": "AstrBot 回复广播到 Minecraft 前允许的最大长度，超出部分会被截断",
        "type": "int",
    },
    "llm_reply_enabled": {
        "description": "启用 LLM 自动回复",
        "hint": "开启后，游戏内玩家聊天会触发 AI 自动回复",
        "type": "bool",
    },
    "llm_reply_weight": {
        "description": "LLM 回复触发权重",
        "hint": "触发概率 = 权重 / 10。权重越高越容易触发 LLM 回复",
        "type": "int",
    },
    "llm_prompt_template": {
        "description": "LLM 回复提示模板",
        "hint": "支持变量: {player_name} = 发言玩家名, {message} = 消息内容",
        "type": "text",
    },
    "chat_rate_limit": {
        "description": "发言频率限制",
        "hint": "每个时间窗口内最多发送的消息数量（0=不限制）",
        "type": "int",
    },
    "chat_rate_window": {
        "description": "发言频率窗口（秒）",
        "hint": "频率限制的时间窗口大小（秒）",
        "type": "int",
    },
    "ai_companion_enabled": {
        "description": "启用 AI 陪伴模式",
        "hint": "AI 可围绕高层目标持续行动和搭话（Mod 端也必须同时启用）",
        "type": "bool",
    },
    "blocked_users": {
        "description": "用户黑名单",
        "hint": "黑名单中的用户发送的消息不会被处理",
        "type": "list",
    },
}


def _register_adapter():
    global _registered
    if _registered:
        return
    _registered = True

    @register_platform_adapter(
        "minecraft_bridge",
        "Minecraft Bridge（ZenithProxy WebSocket 桥接）",
        default_config_tmpl={},
        config_metadata=CONFIG_METADATA,
    )
    class MinecraftPlatformAdapter(Platform):
        """把游戏内聊天室映射为 AstrBot 的一个虚拟群会话。"""

        def __init__(
            self,
            platform_config: dict,
            platform_settings: dict,
            event_queue: asyncio.Queue,
        ) -> None:
            super().__init__(platform_config, event_queue)
            self.settings = platform_settings
            self.bridge = BridgeManager.get_instance()
            self._dedup_cache: dict[str, float] = {}
            self._dedup_window = 2.0

        def meta(self) -> PlatformMetadata:
            return PlatformMetadata(
                name="minecraft_bridge",
                description="Minecraft Bridge（ZenithProxy WebSocket 桥接）",
                id="minecraft_bridge",
            )

        async def run(self) -> None:
            """阻塞消费 BridgeManager 的 chat 事件队列。"""
            import random
            logger.info("Minecraft Platform Adapter 已启动")
            while True:
                try:
                    item = await self.bridge.event_queue.get()
                    event_type = item.get("event_type")
                    if event_type in (EVENT_CHAT, EVENT_WHISPER):
                        abm = await self.convert_message(item)
                        if abm is not None and not self._is_duplicate(item):
                            await self.handle_msg(abm)
                            # LLM 自动回复
                            if event_type == EVENT_CHAT and self._should_llm_reply():
                                await self._try_llm_reply(item)
                    else:
                        # 非聊天事件也需要去重
                        if self._is_duplicate(item):
                            continue
                    # 所有事件都尝试推送到群（包括聊天）
                    await self._push_event_to_group(item)
                    if event_type not in (EVENT_CHAT, EVENT_WHISPER):
                        logger.debug(f"收到事件: {event_type}")
                except asyncio.CancelledError:
                    break
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Minecraft Adapter 事件处理异常: {e}")

        async def _push_event_to_group(self, item: dict) -> None:
            """推送游戏事件到配置的群聊。"""
            event_type = item.get("event_type")
            server_id = item.get("server_id", "default")
            
            logger.debug(f"[{server_id}] _push_event_to_group: event_type={event_type}")
            
            # 检查是否启用推送
            if event_type in ("chat", "whisper"):
                if not self.bridge.config.get("chat_push_enabled", False):
                    logger.debug(f"[{server_id}] chat_push_enabled=False, 跳过")
                    return
            else:
                if not self.bridge.config.get("server_event_push_enabled", False):
                    logger.debug(f"[{server_id}] server_event_push_enabled=False, 跳过")
                    return

            event_group = self.bridge.config.get("minecraft_event_group", "")
            if not event_group:
                logger.debug(f"[{server_id}] minecraft_event_group 为空, 跳过")
                return

            # 检查目标群是否在白名单中
            if not self._is_event_group_allowed():
                logger.debug(f"[{server_id}] 事件推送目标群 {event_group} 不在白名单中，跳过推送")
                return

            event_type = item.get("event_type")
            server_id = item.get("server_id", "default")
            payload = item.get("data", {})

            # 格式化事件消息
            msg = None
            if event_type == "chat":
                sender = payload.get("sender", "unknown")
                message = payload.get("message", "")
                if message:
                    msg = f"[{server_id}] {sender}: {message}"
            elif event_type == "whisper":
                sender = payload.get("sender", "unknown")
                message = payload.get("message", "")
                receiver = payload.get("receiver", "")
                if message and not payload.get("outgoing"):
                    msg = f"[{server_id}] {sender} -> {receiver}: {message}"
            elif event_type == "player_join":
                player = payload.get("player", "unknown")
                msg = f"[{server_id}] 玩家 {player} 加入了游戏"
            elif event_type == "player_leave":
                player = payload.get("player", "unknown")
                msg = f"[{server_id}] 玩家 {player} 离开了游戏"
            elif event_type == "death":
                msg = f"[{server_id}] Bot 死亡了"
            elif event_type == "achievement":
                player = payload.get("player", "unknown")
                achievement = payload.get("achievement", "未知成就")
                msg = f"[{server_id}] 玩家 {player} 达成了成就: {achievement}"
            elif event_type == "system":
                system_msg = payload.get("message", "")
                if system_msg:
                    msg = f"[{server_id}] 系统: {system_msg}"

            if msg:
                try:
                    context = getattr(self.bridge, 'context', None)
                    if context:
                        # 使用 AstrBot 的消息发送能力推送到群聊
                        from astrbot.api.message_components import Plain
                        from astrbot.core.platform.astr_message_event import MessageChain
                        # 构造消息链
                        chain = MessageChain([Plain(text=msg)])
                        # 构造 unified_msg_origin 格式
                        # 尝试多种格式
                        umo_formats = [
                            f"aiocqhttp:group:{event_group}",
                            f"qqoffical:group:{event_group}",
                            f"onebot:group:{event_group}",
                        ]
                        sent = False
                        for umo in umo_formats:
                            try:
                                await context.send_message(umo, chain)
                                logger.info(f"[{server_id}] 事件推送到群 {event_group} (UMOP: {umo}): {msg}")
                                sent = True
                                break
                            except Exception as e:
                                logger.debug(f"[{server_id}] UMOP {umo} 失败: {e}")
                        if not sent:
                            logger.error(f"[{server_id}] 所有 UMOP 格式都失败，无法推送消息")
                    else:
                        logger.warning(f"[{server_id}] context 为空，无法推送事件")
                except Exception as e:
                    logger.error(f"[{server_id}] 事件推送失败: {e}")
            else:
                logger.debug(f"[{server_id}] event_type={event_type} 没有生成消息内容")

        def _should_llm_reply(self) -> bool:
            """根据权重判断是否触发 LLM 回复。"""
            config = self.bridge.config
            if not config.get("llm_reply_enabled", False):
                return False
            weight = int(config.get("llm_reply_weight", 0))
            if weight <= 0:
                return False
            # 简单概率触发：权重越高越容易触发
            # 权重 1 = 10% 概率，权重 5 = 50% 概率，权重 10 = 100% 概率
            return random.random() < (weight / 10.0)

        async def _try_llm_reply(self, item: dict) -> None:
            """尝试调用 LLM 生成回复。"""
            try:
                payload = item.get("data", {})
                player_name = payload.get("sender", "unknown")
                message = payload.get("message", "")
                server_id = item.get("server_id", "default")

                # 格式化提示模板
                template = self.bridge.config.get("llm_prompt_template", "")
                if not template:
                    return
                prompt = template.replace("{player_name}", player_name).replace("{message}", message)

                # 通过 AstrBot context 调用 LLM
                context = getattr(self.bridge, 'context', None)
                if context is None:
                    logger.warning("LLM 回复失败: 无法获取 AstrBot context")
                    return

                # 获取默认 chat provider
                provider_id = context.provider_manager.default_chat_provider_id
                if not provider_id:
                    logger.warning("LLM 回复失败: 未配置聊天模型")
                    return

                logger.info(f"[{server_id}] LLM 回复触发: player={player_name}, msg={message[:50]}...")

                # 调用 LLM
                from astrbot.core.agent.message import UserMessageSegment, TextPart
                user_msg = UserMessageSegment(content=[TextPart(text=prompt)])
                llm_resp = await context.llm_generate(
                    chat_provider_id=provider_id,
                    contexts=[user_msg],
                )

                # 发送回复到游戏
                reply_text = llm_resp.completion_text if hasattr(llm_resp, 'completion_text') else str(llm_resp)
                if reply_text:
                    await self.bridge.send_chat(server_id, reply_text)
                    logger.info(f"[{server_id}] LLM 回复已发送: {reply_text[:50]}...")

            except Exception as e:
                logger.error(f"LLM 回复失败: {e}")

        async def convert_message(self, data: dict) -> AstrBotMessage | None:
            """将桥接事件字典转换为 AstrBotMessage。

            data = {"server_id","event_type","data": {...},"timestamp"}
            其中 data.data = {"sender","message","outgoing","receiver",...}
            """
            server_id = data.get("server_id", "default")
            payload = data.get("data", {})
            event_type = data.get("event_type")

            if event_type == EVENT_WHISPER:
                if payload.get("outgoing"):
                    # bot 发出的私聊，忽略避免回路
                    return None
                sender = payload.get("sender", "unknown")
                message = payload.get("message", "")
            else:  # EVENT_CHAT
                sender = payload.get("sender", "unknown")
                message = payload.get("message", "")

            if not message:
                return None

            # 检查用户黑名单
            if self._is_blocked_user(sender):
                logger.debug(f"忽略黑名单用户 {sender} 的消息")
                return None

            # 入站消息长度限制
            max_len = int(self.bridge.config.get("inbound_max_message_length", 1000))
            if max_len > 0 and len(message) > max_len:
                message = message[:max_len] + "..."

            abm = AstrBotMessage()
            abm.type = MessageType.GROUP_MESSAGE
            group_id = self._group_id(server_id)
            abm.group_id = group_id
            abm.message_str = message
            abm.sender = MessageMember(user_id=sender, nickname=sender)
            abm.message = [Plain(text=message)]
            abm.self_id = f"minecraft:{server_id}"
            abm.session_id = group_id
            abm.message_id = str(uuid.uuid4())
            abm.raw_message = data
            return abm

        async def handle_msg(self, message: AstrBotMessage) -> None:
            """包装为 MinecraftEvent 并提交到事件队列。"""
            server_id = message.self_id.split(":", 1)[1] if ":" in message.self_id else "default"
            message_event = MinecraftEvent(
                message_str=message.message_str,
                message_obj=message,
                platform_meta=self.meta(),
                session_id=message.session_id,
                server_id=server_id,
            )
            self.commit_event(message_event)

        async def send_by_session(self, session: MessageSesion, message_chain: MessageChain) -> None:
            """通过会话 ID 主动推送消息到游戏内。"""
            text = "".join(c.text if isinstance(c, Plain) else "" for c in message_chain.chain)
            text = text.strip()
            if text:
                # session_id 格式为 minecraft:{server_id}
                parts = session.session_id.split(":", 1)
                server_id = parts[1] if len(parts) > 1 else self.bridge.config.get("default_server_id", "default")
                try:
                    await self.bridge.send_chat(server_id, text)
                except Exception as e:  # noqa: BLE001
                    logger.error(f"[{server_id}] 推送失败: {e}")
            await super().send_by_session(session, message_chain)

        # ---- 工具方法 ----

        def _group_id(self, server_id: str) -> str:
            prefix = self.bridge.config.get("group_id_prefix", "minecraft")
            return f"{prefix}:{server_id}"

        def _is_blocked_user(self, user_id: str) -> bool:
            """检查用户是否在黑名单中。"""
            blocked_users = self.bridge.config.get("blocked_users", [])
            if not blocked_users:
                return False
            return str(user_id) in [str(u) for u in blocked_users]

        def _is_group_blocked(self, group_id: str) -> bool:
            """检查群是否在禁止列表中。"""
            blocked_groups = self.bridge.config.get("blocked_groups", [])
            if blocked_groups and group_id in blocked_groups:
                return True
            allowed_groups = self.bridge.config.get("allowed_groups", [])
            if allowed_groups and group_id not in allowed_groups:
                return True
            return False

        def _is_event_group_allowed(self) -> bool:
            """检查事件推送目标群是否在白名单中。"""
            event_group = self.bridge.config.get("minecraft_event_group", "")
            if not event_group:
                return False  # 未配置则不推送
            return not self._is_group_blocked(event_group)

        def _guard(self, user_id: str, group_id: str = None) -> bool:
            """权限守卫：检查用户和群是否被允许。返回 True 表示允许。"""
            if self._is_blocked_user(user_id):
                logger.debug(f"用户 {user_id} 在黑名单中，忽略")
                return False
            if group_id and self._is_group_blocked(group_id):
                logger.debug(f"群 {group_id} 不在白名单或在黑名单中，忽略")
                return False
            return True

        def _is_duplicate(self, item: dict) -> bool:
            """消息去重：同一事件类型 + 关键内容 + 时间窗内丢弃。"""
            if not self._dedup_window:
                return False
            
            event_type = item.get("event_type")
            server_id = item.get("server_id")
            payload = item.get("data", {})
            now = asyncio.get_running_loop().time()
            
            # 根据事件类型生成去重 key
            if event_type == "chat":
                # 聊天: server_id + sender + message
                key = f"chat|{server_id}|{payload.get('sender')}|{payload.get('message')}"
            elif event_type == "whisper":
                # 私聊: server_id + sender + receiver + message
                key = f"whisper|{server_id}|{payload.get('sender')}|{payload.get('receiver')}|{payload.get('message')}"
            elif event_type == "player_join":
                # 加入: server_id + player
                key = f"player_join|{server_id}|{payload.get('player')}"
            elif event_type == "player_leave":
                # 离开: server_id + player
                key = f"player_leave|{server_id}|{payload.get('player')}"
            elif event_type == "death":
                # 死亡: server_id + death (固定 key，同一服务器短时间内只记录一次)
                key = f"death|{server_id}"
            elif event_type == "achievement":
                # 成就: server_id + player + achievement
                key = f"achievement|{server_id}|{payload.get('player')}|{payload.get('achievement')}"
            elif event_type == "system":
                # 系统消息: server_id + message
                key = f"system|{server_id}|{payload.get('message')}"
            else:
                # 其他事件不去重
                return False
            
            last = self._dedup_cache.get(key)
            if last and (now - last) < self._dedup_window:
                logger.debug(f"[{server_id}] 重复事件已过滤: {event_type}")
                return True
            self._dedup_cache[key] = now
            
            # 简单清理：超过 500 条清一次
            if len(self._dedup_cache) > 500:
                self._dedup_cache.clear()
            return False


def _ensure_registered():
    """确保适配器已注册（由 main.py 调用）。"""
    # 检查运行时状态中是否已有实例（热重载存活）
    from ..bridge.runtime_state import get_adapter_instance
    existing = get_adapter_instance("minecraft_bridge")
    if existing is not None:
        logger.debug("从运行时状态恢复适配器实例")
    _register_adapter()
