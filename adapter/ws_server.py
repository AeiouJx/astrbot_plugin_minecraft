"""MinecraftWSServer：aiohttp WebSocket 服务端 + 连接管理。"""

from __future__ import annotations

import asyncio
from typing import Optional

from aiohttp import web, WSMsgType

from astrbot import logger
from .connection import BridgeConnection
from . import protocol


class MinecraftWSServer:
    def __init__(self, adapter) -> None:
        self.adapter = adapter
        self.config = adapter.config
        self._runner: Optional[web.AppRunner] = None
        self._pending = protocol.PendingFuture()
        self._monitor_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        app = web.Application()
        path = self.config.get("path", "/ws")
        app.router.add_get(path, self._handle)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.config["host"], self.config["port"])
        await site.start()
        logger.info(
            f"MC Bridge WS 已监听: "
            f"ws://{self.config['host']}:{self.config['port']}{path}"
        )
        self._monitor_task = asyncio.create_task(self._monitor())
        await asyncio.Event().wait()

    async def stop(self) -> None:
        """关闭 WS 服务端，释放端口。"""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        for sid, conn in list(self.adapter._connections.items()):
            conn.closed = True
            try:
                await conn.ws.close()
            except Exception:
                pass
        self.adapter._connections.clear()
        logger.info("MC Bridge WS 已关闭")

    async def _handle(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30, max_msg_size=1024 * 1024)
        await ws.prepare(request)

        # 鉴权
        auth = request.headers.get("Authorization", "")
        token = self.config.get("token", "")
        if token and auth != f"Bearer {token}":
            logger.warning(f"WS 鉴权失败: {request.remote}")
            await ws.close()
            return ws

        logger.info(f"MC Bridge 收到连接: {request.remote}")

        conn: Optional[BridgeConnection] = None
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    data = protocol.parse_message(msg.data)
                    if not data:
                        continue
                    msg_type = data.get("type")

                    if conn is None:
                        if msg_type == protocol.MSG_HELLO:
                            server_id = data.get("server_id") or "default"
                            conn = BridgeConnection(server_id, ws, self._pending)
                            conn.apply_hello(data)
                            self.adapter._connections[server_id] = conn
                            conn.touch()
                            await conn.send_hello_ack()
                            logger.info(
                                f"[{server_id}] hello 完成 "
                                f"(account={conn.account})"
                            )
                        elif msg_type == protocol.MSG_HEARTBEAT:
                            server_id = data.get("server_id") or "default"
                            conn = BridgeConnection(server_id, ws, self._pending)
                            self.adapter._connections[server_id] = conn
                            conn.touch()
                            await conn.send_heartbeat_ack()
                            logger.info(f"[{server_id}] heartbeat 兼容模式")
                        else:
                            break
                    else:
                        conn.touch()
                        if msg_type == protocol.MSG_UPDATE_INFO:
                            new_id = data.get("server_id")
                            if new_id and new_id != conn.server_id:
                                old = conn.server_id
                                self.adapter._connections.pop(old, None)
                                conn.server_id = new_id
                                conn.apply_hello(data)
                                self.adapter._connections[new_id] = conn
                                logger.info(f"[{old}] 更新为: {new_id}")
                            continue

                        if msg_type == protocol.MSG_EVENT:
                            event_type = data.get("event_type", "")
                            payload = data.get("data", {})
                            payload["_timestamp"] = data.get("timestamp")
                            self.adapter.on_ws_event(
                                conn.server_id, event_type, payload
                            )
                        elif msg_type == protocol.MSG_HEARTBEAT:
                            await conn.send_heartbeat_ack()
                        elif msg_type == protocol.MSG_TASK_RESULT:
                            self._pending.resolve(
                                data.get("task_id", ""),
                                bool(data.get("success")),
                                error_message=data.get("error_message"),
                            )
                        elif msg_type == protocol.MSG_QUERY_RESULT:
                            self._pending.resolve(
                                data.get("query_id", ""),
                                bool(data.get("success")),
                                data=data.get("data"),
                                error_message=data.get("error_message"),
                            )
                elif msg.type == WSMsgType.ERROR:
                    break
        except Exception as e:
            logger.error(f"MC Bridge WS 异常: {e}")
        finally:
            if conn:
                conn.closed = True
                self._pending.cancel_for(conn.server_id)
                self.adapter._connections.pop(conn.server_id, None)
            try:
                await ws.close()
            except Exception:
                pass
        return ws

    async def _monitor(self) -> None:
        """后台心跳监控：每 5s 扫描，超时则移除连接。"""
        while True:
            await asyncio.sleep(5)
            for sid, c in list(self.adapter._connections.items()):
                if not c.alive:
                    logger.warning(f"[{sid}] 心跳超时，判定离线")
                    self.adapter._connections.pop(sid, None)
