"""MinecraftEvent：Minecraft 平台事件。

携带 server_id，send() 时把 AstrBot 消息链转文本，经 BridgeManager.send_chat 下发。
"""

from __future__ import annotations

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.platform import AstrBotMessage, PlatformMetadata
from astrbot.api.message_components import Plain

from ..bridge import BridgeManager


class MinecraftEvent(AstrMessageEvent):
    """Minecraft 平台事件。

    一个虚拟会话即"游戏内聊天室"。send() 时 AstrBot 生成的
    回复文本将经桥接下发到对应游戏实例。
    """

    def __init__(
        self,
        message_str: str,
        message_obj: AstrBotMessage,
        platform_meta: PlatformMetadata,
        session_id: str,
        server_id: str,
    ) -> None:
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self.server_id = server_id
        self.bridge = BridgeManager.get_instance()

    async def send(self, message: MessageChain) -> None:
        """发送消息到 Minecraft 游戏内聊天。

        把消息链中的 Plain 文本拼接后，经桥接 send_chat 下发。
        """
        text = "".join(c.text if isinstance(c, Plain) else "" for c in message.chain)
        text = text.strip()
        if text and self.server_id:
            try:
                await self.bridge.send_chat(self.server_id, text)
            except Exception as e:
                logger.error(f"[{self.server_id}] 游戏内发送失败: {e}")
        await super().send(message)
