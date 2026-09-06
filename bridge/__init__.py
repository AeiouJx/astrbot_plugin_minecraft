"""bridge 包：WebSocket 桥接核心。

提供 BridgeManager 单例，供平台适配器/AI 工具共享 WS 服务、注册表与 RPC 能力。
"""

from __future__ import annotations

import asyncio
from typing import Optional

from astrbot.api import logger

from .registry import Registry
from .ws_server import WSServer


class BridgeManager:
    """桥接管理器单例。

    持有 Registry（连接注册表 + RPC）与 WSServer（WS 服务端）。
    工具层/适配器通过 BridgeManager 调用 send_query/send_task。
    """

    _instance: Optional["BridgeManager"] = None

    def __init__(self, config: Optional[dict] = None) -> None:
        self.config = config or {}
        self.registry = Registry()
        self.ws_server = WSServer(self.registry, self.config)
        self.rpc_timeout = float(self.config.get("rpc_timeout", 10))
        self.started = False

    @classmethod
    def get_instance(cls) -> "BridgeManager":
        """获取单例。未初始化则新建（config 为空，启动前应调用 configure）。"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def configure(cls, config: dict) -> "BridgeManager":
        """应用配置并返回单例。"""
        config = config or {}
        if cls._instance is not None:
            inst = cls._instance
            inst.config = config
            inst.rpc_timeout = float(config.get("rpc_timeout", 10))
            inst.ws_server.apply_config(config)
            return inst
        inst = cls(config)
        cls._instance = inst
        return inst

    def start(self) -> None:
        """启动 WS 服务 + 心跳监控。"""
        if self.started:
            return
        self.ws_server.start()
        self.started = True
        logger.info("Minecraft Bridge 已启动")

    async def stop(self) -> None:
        """停止 WS 服务，清理连接。"""
        if not self.started:
            return
        for server_id in list(self.registry.server_ids):
            await self.registry.unregister(server_id, "plugin stop")
        await self.ws_server.stop()
        self.started = False
        logger.info("Minecraft Bridge 已停止")

    # ---- 便捷 RPC ----

    async def send_query(self, server_id: str, resource: str, params: dict = None, timeout: float | None = None) -> dict:
        return await self.registry.send_query(server_id, resource, params, timeout or self.rpc_timeout)

    async def send_task(self, server_id: str, action: str, params: dict = None, timeout: float | None = None) -> dict:
        return await self.registry.send_task(server_id, action, params, timeout or self.rpc_timeout)

    async def send_chat(self, server_id: str, message: str) -> None:
        """bot 发送公共聊天（fire-and-forget）。"""
        await self.registry.send_task_fire(server_id, "send_chat", {"message": message})

    @property
    def event_queue(self) -> asyncio.Queue:
        return self.registry.event_queue

    @property
    def status_queue(self) -> asyncio.Queue:
        return self.registry.status_queue