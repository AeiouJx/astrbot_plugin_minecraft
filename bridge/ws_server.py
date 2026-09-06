"""ws_server.py：aiohttp WebSocket 服务端。

监听 0.0.0.0:8765 /ws
├─ 握手鉴权：比对 Authorization: Bearer 与 config.shared_token，失败 401 断开
├─ 注册：从首条 heartbeat 的 server_id 建立 BridgeConnection，加入 registry
├─ 循环读帧：
│   ├─ heartbeat        -> 更新 last_seen，回 heartbeat_ack
│   ├─ event            -> 交给路由：chat/whisper -> 平台适配器；其余 -> 状态通知
│   ├─ task_result      -> 解析 pending[task_id] Future
│   └─ query_result     -> 解析 pending[query_id] Future
├─ 异步监控：每 1s 扫描，last_seen 超时 -> 标记离线、广播 bot_status offline、移除注册表
└─ 连接断开/异常     -> 清理 Future（置为失败）、清理注册表
"""

from __future__ import annotations

import asyncio
from typing import Optional

from aiohttp import web, WSMsgType
from astrbot.api import logger

from . import protocol
from .connection import BridgeConnection
from .registry import Registry


class WSServer:
    """aiohttp WebSocket 服务端封装。"""

    def __init__(self, registry: Registry, config: dict) -> None:
        self.registry = registry
        self._runner: Optional[web.AppRunner] = None
        self._task: Optional[asyncio.Task] = None
        self.apply_config(config or {})

    def apply_config(self, config: dict) -> None:
        """应用配置到服务端字段（运行中修改需重启服务生效）。"""
        self.host = config.get("ws_host", "0.0.0.0")
        self.port = int(config.get("ws_port", 8765))
        self.path = config.get("ws_path", "/ws")
        self.shared_token = config.get("shared_token", "change-me")
        self.heartbeat_timeout = float(config.get("heartbeat_timeout", 15))

    # ---- 生命周期 ----

    def start(self) -> None:
        """在事件循环中启动 WS 服务（非阻塞启动后台任务）。"""
        if self._runner is not None:
            logger.warning("WS 服务已在运行")
            return
        self._task = asyncio.create_task(self._run())
        # 同时启动心跳监控
        asyncio.create_task(self.registry.monitor())
        logger.info(f"WS 服务正在启动: ws://{self.host}:{self.port}{self.path}")

    async def stop(self) -> None:
        """停止 WS 服务。"""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("WS 服务已停止")

    async def _run(self) -> None:
        """后台运行 aiohttp 应用（独立事件循环内需 await，这里以任务运行）。"""
        app = web.Application()
        app.router.add_get(self.path, self._handle_ws)
        self._runner = web.AppRunner(app)
        try:
            await self._runner.setup()
            site = web.TCPSite(self._runner, self.host, self.port)
            await site.start()
            logger.info(f"WS 服务已监听: ws://{self.host}:{self.port}{self.path}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"WS 服务启动失败: {e}")
            self._runner = None

    # ---- 握手处理 ----

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30, max_msg_size=1024 * 1024)
        await ws.prepare(request)

        auth = request.headers.get("Authorization", "")
        if not self._check_auth(auth):
            logger.warning(f"鉴权失败: {request.remote} (missing/invalid Bearer)")
            await ws.close()
            return ws

        logger.info(f"收到来自 {request.remote} 的 WS 握手，鉴权通过，等待 heartbeat")

        conn: Optional[BridgeConnection] = None
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    data = protocol.parse_message(msg.data)
                    if not data:
                        logger.debug("收到非法 JSON 帧")
                        continue
                    # 首条必须是 heartbeat，用于确定 server_id 并注册
                    msg_type = data.get("type")
                    if conn is None:
                        if msg_type == protocol.MSG_HEARTBEAT:
                            server_id = data.get("server_id") or "default"
                            conn = BridgeConnection(server_id, ws, self.registry.pending, self.heartbeat_timeout)
                            await self.registry.register(conn)
                            conn.touch()
                            await conn.send_heartbeat_ack()
                            logger.info(f"[{server_id}] 连接注册完成")
                        else:
                            logger.warning("连接未初始化（无 heartbeat）即发送数据")
                            break
                    else:
                        conn.touch()
                        self.registry.handle_data_message(conn.server_id, data)
                        if msg_type == protocol.MSG_HEARTBEAT:
                            await conn.send_heartbeat_ack()
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WS 连接错误: {ws.exception()}")
                    break
        except Exception as e:  # noqa: BLE001
            logger.error(f"WS 处理异常: {e}")
        finally:
            if conn is not None:
                conn.closed = True
                self.registry.pending.cancel_for(conn.server_id)
                await self.registry.unregister(conn.server_id, "connection closed")
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass
        return ws

    # ---- 鉴权 ----

    def _check_auth(self, auth_header: str) -> bool:
        """校验 Authorization: Bearer {token}。"""
        if not auth_header.startswith("Bearer "):
            return False
        token = auth_header[len("Bearer "):].strip()
        return token == self.shared_token
