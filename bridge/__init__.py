"""bridge 包：WebSocket 桥接核心。

提供 BridgeManager 单例，持有 Registry（连接注册表 + RPC）。
平台适配器通过 BridgeManager 调用 send_query/send_task。
"""

from __future__ import annotations

import asyncio
from typing import Optional

from astrbot.api import logger

from .registry import Registry
from . import runtime_state


class BridgeManager:
    """桥接管理器单例。

    持有 Registry（连接注册表 + RPC）。
    工具层/适配器通过 BridgeManager 调用 send_query/send_task。
    """

    _instance: Optional["BridgeManager"] = None

    def __init__(self, config: Optional[dict] = None) -> None:
        self.config = config or {}
        self.registry = Registry()
        self.rpc_timeout = float(self.config.get("rpc_timeout", 10))
        self.started = False
        self.page_push_callback = None  # Dashboard 消息推送回调

    @classmethod
    def get_instance(cls) -> "BridgeManager":
        """获取单例。优先从运行时状态恢复（热重载存活）。"""
        inst = runtime_state.get_bridge_manager()
        if inst is not None:
            cls._instance = inst
            return inst
        if cls._instance is not None:
            return cls._instance
        inst = cls()
        cls._instance = inst
        runtime_state.set_bridge_manager(inst)
        return inst

    @classmethod
    def configure(cls, config: dict) -> "BridgeManager":
        """应用配置并返回单例。"""
        config = config or {}
        inst = cls.get_instance()
        inst.config = config
        inst.rpc_timeout = float(config.get("rpc_timeout", 10))
        cls._instance = inst
        runtime_state.set_bridge_manager(inst)
        return inst

    def start(self) -> None:
        """标记已启动。"""
        if self.started:
            return
        self.started = True
        logger.info("Minecraft Bridge 已启动")

    async def stop(self) -> None:
        """停止，清理连接。"""
        if not self.started:
            return
        for server_id in list(self.registry.server_ids):
            await self.registry.unregister(server_id, "plugin stop")
        self.started = False
        logger.info("Minecraft Bridge 已停止")

    # ---- 便捷 RPC ----

    async def send_query(self, server_id: str, resource: str, params: dict = None, timeout: float | None = None) -> dict:
        return await self.registry.send_query(server_id, resource, params, timeout or self.rpc_timeout)

    async def send_task(self, server_id: str, action: str, params: dict = None, timeout: float | None = None) -> dict:
        return await self.registry.send_task(server_id, action, params, timeout or self.rpc_timeout)

    async def send_chat(self, server_id: str, message: str) -> None:
        """bot 发送公共聊天（fire-and-forget），带频率限制和消息长度限制。"""
        max_len = int(self.config.get("outbound_max_message_length", 2000))
        if max_len > 0 and len(message) > max_len:
            message = message[:max_len] + "..."
        rate_limit = int(self.config.get("chat_rate_limit", 0))
        if rate_limit > 0:
            import time
            now = time.time()
            window = int(self.config.get("chat_rate_window", 60))
            if not hasattr(self, '_chat_timestamps'):
                self._chat_timestamps = []
            self._chat_timestamps = [t for t in self._chat_timestamps if now - t < window]
            if len(self._chat_timestamps) >= rate_limit:
                raise RuntimeError(f"发言频率限制: {window}秒内最多{rate_limit}条消息")
            self._chat_timestamps.append(now)
        await self.registry.send_task_fire(server_id, "send_chat", {"message": message})
