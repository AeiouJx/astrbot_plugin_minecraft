"""MinecraftPlatformEvent：Minecraft 平台事件。

send() 时把 AstrBot 消息链转文本，经 WebSocket 下发到游戏内。
"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.platform import AstrBotMessage, PlatformMetadata
from astrbot.api.message_components import Plain


class MinecraftPlatformEvent(AstrMessageEvent):
    def __init__(
        self,
        message_str: str,
        message_obj: AstrBotMessage,
        platform_meta: PlatformMetadata,
        session_id: str,
        adapter,
        server_id: str,
    ) -> None:
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self.adapter = adapter
        self.server_id = server_id

    async def send(self, message: MessageChain) -> None:
        text = "".join(
            c.text if isinstance(c, Plain) else "" for c in message.chain
        ).strip()
        if text and self.server_id:
            conn = self.adapter._connections.get(self.server_id)
            if conn:
                await conn.send_task_action("send_chat", {"message": text})
        await super().send(message)
