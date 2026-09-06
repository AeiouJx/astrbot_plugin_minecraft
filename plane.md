# ZenithProxy + AstrBot WebSocket + AI 集成开发方案

## 1. 项目愿景

构建 **AstrBot 插件**（WebSocket 服务端）与 **ZenithProxy 插件**（WebSocket 客户端，本仓库 Java 端，已完成主体），通过 WebSocket 全双工通信，将 Minecraft 游戏事件与 QQ 群聊深度整合，并开放 AI 工具调用能力，实现对游戏 Bot 的监控、查询与控制。

Java 端（本项目，已完成阶段 1~3）：连接管理、事件上报、任务执行、查询处理。
本文档后续部分为 **AstrBot 插件（Python）开发计划与对接方案**，供新建的 AstrBot 插件项目直接使用。

## 2. 核心架构

```
graph TD
    subgraph 游戏服务端 (ZenithProxy + Java 插件)
        ZPPlugin[ZenithProxy 插件<br>WebSocket 客户端<br>事件上报 / 任务执行 / 查询处理]
    end
    subgraph 中枢服务 (AstrBot + Python 插件)
        WSS[Bridge WebSocket 服务端<br>9527 端口 /ws]
        BA[Bridge 可选: 平台适配器<br>minecraft 虚拟平台]
        TOOLS[AI 工具注册<br>@filter.llm_tool]
        AB[AstrBot 核心]
    end
    subgraph 交互层
        QQ[QQ 群聊 · NapCatQQ]
        WEBUI[WebUI 仪表盘]
    end

    ZPPlugin --主动连接 ws://y:N/ws, Bearer Token--> WSS
    WSS -- 游戏 chat 事件 --> BA --> AB --> NapCat --> QQ
    QQ -- 会话/指令 --> AB --> TOOLS --> WSS -- task/query --> ZPPlugin
```

- **Minecraft 为源**：ZenithProxy 是执行器（负责采事件、执行任务、应答查询）。
- **AstrBot 为中心**：负责消息路由、会话、AI 编排；WebSocket 服务端由 AstrBot 插件承担。
- **全双工持久连接**：客户端（游戏端）主动连接服务端（AstrBot），握手一次，双向收发。

### 2.1 职责划分

| 侧 | 职责 | 状态 |
|---|---|---|
| Java 插件（ZenithProxy） | 心跳、事件上报、任务执行、查询应答 | ✅ 已完成（本仓库 dev 分支） |
| Python 插件（AstrBot） | WS 服务端、连接池、平台适配器、AI 工具 | 🚧 本文档方案 |
| NapCatQQ | QQ 协议端 | 外部依赖 |

## 3. 通信协议规范（以此为准，Java 端已按此实现）

### 3.1 连接与鉴权

- 服务端：AstrBot 插件监听 `0.0.0.0:8765`，路径 `/ws`。
- 客户端：游戏端插件启动/启用时主动连接 `ws://{ASTRBOT_IP}:8765/ws`，断线自动重连（间隔默认 5s，指数退避可选）。
- 鉴权：WS 握手请求头 `Authorization: Bearer {SHARED_TOKEN}`，两端需一致；服务端鉴权失败返回 `401` 并断开。
- 心跳：客户端每 `heartbeat_interval`（默认 5s）发送一次心跳；服务端回 `heartbeat_ack`。服务端以收到任意消息/心跳的时间作为存活依据，超过 `heartbeat_timeout`（建议 3×间隔）判定下线。

### 3.2 消息总表

全部为 JSON 文本帧，`type` 字段区分方向与类别。

| type | 方向 | 用途 |
|---|---|---|
| `heartbeat` / `heartbeat_ack` | G→S / S→G | 保活 |
| `event` | G→S | 游戏事件上报（聊天/加入/离开/状态/死亡） |
| `task` | S→G | 下发操作指令（发消息/移动/攻击） |
| `query` | S→G | 请求实时数据（玩家/状态/背包/实体） |
| `task_result` | G→S | 任务执行结果 |
| `query_result` | G→S | 查询结果 |

### 3.3 客户端 → 服务端（游戏 → AstrBot）

**heartbeat**
```json
{"type":"heartbeat","server_id":"main","timestamp":1693123456}
```
服务端回复：
```json
{"type":"heartbeat_ack","server_id":"main","timestamp":1693123456}
```

**event**（统一包装）
```json
{"type":"event","server_id":"main","event_type":"chat","data":{...},"timestamp":1693123456}
```
`data` 按 `event_type`：

| event_type | data 字段 | 说明 |
|---|---|---|
| `chat` | `sender`(str), `message`(str) | 玩家公共聊天；**bot 自己的消息已在 Java 端过滤** |
| `whisper` | `outgoing`(bool), `sender`(str), `receiver`(str), `message`(str) | 私聊 |
| `system` | `message`(str) | 服务器系统消息 |
| `player_join` | `player`(str) | 玩家加入 |
| `player_leave` | `player`(str) | 玩家离开 |
| `bot_status` | `status`(str: online/offline/dead), `health`(float), `food`(int), `position`{x,y,z} | bot 状态；离线时 health/food 可能缺失 |
| `death` | （暂无） | bot 死亡 |

**task_result**
```json
{"type":"task_result","task_id":"unique_001","success":true,"error_message":null}
```

**query_result**
```json
{"type":"query_result","query_id":"query_001","success":true,"data":{...},"error_message":null}
```

### 3.4 服务端 → 客户端（AstrBot → 游戏）

**task**
```json
{"type":"task","task_id":"unique_001","action":"send_chat","params":{"message":"大家好！"}}
```
已实现 action 与 params：

| action | params | 说明 |
|---|---|---|
| `send_chat` | `message`(str) | bot 发送公共聊天 |
| `move_to` | `x`,`y`,`z`(int) | baritone 寻路移动 |
| `attack_nearest` | `radius`(float, 可选, 默认16) | 攻击最近的非玩家攻击性实体 |

预留（后续）：`eat_food`、`use_item`。

**query**
```json
{"type":"query","query_id":"query_001","resource":"online_players","params":{}}
```
已实现 resource → `data` 返回结构：

| resource | params | data |
|---|---|---|
| `online_players` | - | `{"players":[{"name","ping"}],"count":n}` |
| `bot_status` | - | `{"status","health","food","position":{"x","y","z"},"heldItemSlot"}` |
| `inventory` | - | `{"items":[{"slot","id","name","count"}],"count":n}` |
| `nearby_entities` | `radius`(float,默认32) | `{"entities":[{"entity_id","type","player"?,"distance","x","y","z"}],"count":n}`（按距离升序，最多64） |

`region` 暂不支持（核心无该 API）。

### 3.5 请求-响应关联

`task_id` / `query_id` 由服务端生成（`uuid4`），响应原样带回。服务端维护 `pending: dict[id -> asyncio.Future]`，收到结果后按 id 立刻解析，附超时（建议 10s）。

### 3.6 多实例

同一 AstrBot 可接多个 Minecraft 服务端：以 `server_id` 区分客户端。服务端连接注册表 `dict[server_id -> BridgeConnection]`。事件/结果按 `server_id` 路由（见 4.2）。

## 4. AstrBot 插件对接方案（新建项目）

### 4.1 项目文件结构

```
astrbot-minecraft-bridge/
├── metadata.yaml              # AstrBot 插件元数据（module_name / author / version / desc）
├── main.py                    # Star 插件入口：启动 WS 服务、导入平台适配器、注册工具
├── bridge/
│   ├── __init__.py            # BridgeManager 单例（供适配器/工具共享）
│   ├── ws_server.py           # aiohttp / websockets 的 WS 服务端（见 4.2）
│   ├── protocol.py            # 消息构造/解析、RPC 关联（见 3.5）
│   ├── connection.py          # BridgeConnection：单连接封装 + heartbeat 监控
│   └── registry.py            # server_id -> connection 注册表 + 路由
├── adapter/
│   ├── __init__.py
│   ├── minecraft_platform_event.py   # MineCraftPlatformEvent(AstrMessageEvent)（见 4.4）
│   └── minecraft_platform_adapter.py # 平台适配器（见 4.3）
└── tools/
    ├── __init__.py
    ├── rpc_tools.py           # @filter.llm_tool 全部工具（见 5）
    └── queries.py / tasks.py  # 对 protocol.py 的薄封装
```

### 4.2 WebSocket 服务端（ws_server.py）

```
监听 0.0.0.0:8765 /ws
├─ 握手鉴权：比对 Authorization: Bearer 与 config.shared_token，失败 401 断开
├─ 注册：从首条 heartbeat 的 server_id 建立 BridgeConnection，加入 registry
├─ 循环读帧：
│   ├─ heartbeat        -> 更新 last_seen，回 heartbeat_ack
│   ├─ event            -> 交给路由：chat/whisper -> 平台适配器；其余 -> 日志/通知
│   ├─ task_result      -> 解析 pending[task_id] Future
│   └─ query_result     -> 解析 pending[query_id] Future
├─ 异步监控：每 1s 扫描，last_seen 超时 -> 标记离线、广播 bot_status offline、移除注册表
└─ 连接断开/异常     -> 清理 Future（置为失败）、清理注册表
```

依赖建议：`aiohttp`（含 WS 服务端，与 AstrBot 生态兼容）或 `websockets`。

### 4.3 平台适配器（mac 虚拟平台）

基于 AstrBot 平台适配器机制（`@register_platform_adapter`）。**平台名建议 `minecraft`**，一个虚拟会话即“游戏内聊天室”。

```python
@register_platform_adapter("minecraft", "Minecraft (via ZenithProxy Bridge)", default_config_tmpl={})
class MinecraftPlatformAdapter(Platform):
    # __init__(platform_config, platform_settings, event_queue): 存 BridgeManager 引用
    async def run(self):
        # 阻塞等待 BridgeManager 的 chat 事件（内部 asyncio.Queue）
        while True:
            abm = await self.bridge.event_queue.get()
            await self.handle_msg(abm)

    async def convert_message(self, data: dict) -> AstrBotMessage:
        # data = {"server_id","sender","message","raw_event"}
        abm = AstrBotMessage()
        abm.type = MessageType.GROUP_MESSAGE
        abm.group_id = f"minecraft:{data['server_id']}"   # 虚拟群
        abm.message_str = data["message"]
        abm.sender = MessageMember(user_id=data["sender"], nickname=data["sender"])
        abm.message = [Plain(text=data["message"])]
        abm.self_id = data.get("server_id", "minecraft")
        abm.session_id = f"minecraft:{data['server_id']}"
        abm.message_id = str(uuid4())
        abm.raw_message = data["raw_event"]
        return abm
```

事件路由补充：
- 只把 `event_type ∈ {chat, whisper}` 推入 chat 事件队列；`system / player_join / player_leave / bot_status / death` 作为可选“系统消息”通知（v1 可仅记日志 + 发一条静默状态）。
- **防循环**：Java 端已过滤 bot 自身发言；AstrBot 端再做一层去重（同一 `server_id + sender + message + 时间窗` 丢弃），防止某些服务器回显导致环路。

### 4.4 平台事件（minecraft_platform_event.py）

```python
class MineCraftPlatformEvent(AstrMessageEvent):
    # 携带 server_id，send() 时把 AstrBot 消息链转文本，经 BridgeManager.send_chat 下发
    async def send(self, message: MessageChain):
        text = "".join(c.text if isinstance(c, Plain) else "" for c in message.chain)
        if text and self.server_id:
            await self.bridge.send_chat(self.server_id, text, session_id=self.session_id)
        await super().send(message)   # 必须调用父类
```

`main.py` 只需导入适配器模块即完成注册：
```python
class MineCraftBridgePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        from adapter.minecraft_platform_adapter import MinecraftPlatformAdapter  # noqa
        self.bridge = BridgeManager.get_instance()
        self.bridge.start()          # 启动 WS 服务端
        self.context.add_llm_tools(*rpc_tools.ALL_TOOLS)  # 注册 AI 工具
```

### 4.5 RPC 封装（协议层）

```python
async def send_query(server_id, resource, params=None, timeout=10) -> dict | None:
    qid = str(uuid4())
    fut = registry.expect(qid)
    await registry.route(server_id).send_task({
        "type": "query", "query_id": qid, "resource": resource, "params": params or {},
    })
    return await asyncio.wait_for(fut, timeout)   # 成功解析 data / 失败抛错

# send_task 同理，task_id 关联 task_result
```
所有工具基于这两个函数（或 `send_task(..., fire_and_forget=True)`，用于聊天回复等无需等待的场景）。

## 5. AI 工具清单（@filter.llm_tool）

工具统一签名 `(self, event, server, ...)`；`server` 可选，默认取配置 `default_server_id`。docstring 必须写 `Args:` 块，AstrBot 解析为工具 schema。

| 工具名 | resource/action | 参数 | 返回 |
|---|---|---|---|
| `get_server_status` | query `bot_status` | - | 在线状态/血/饥饿/坐标 |
| `get_online_players` | query `online_players` | - | 玩家列表 + 人数 |
| `get_bot_state` | query `bot_status` | - | 详细状态 |
| `get_inventory` | query `inventory` | - | 背包物品列表 |
| `get_nearby_entities` | query `nearby_entities` | `radius`(number) | 附近实体 |
| `move_bot` | task `move_to` | `x`,`y`,`z`(number) | 是否已开始寻路 |
| `attack_nearest` | task `attack_nearest` | `radius`(number?) | 目标实体 |
| `send_chat` | task `send_chat` | `message`(string) | 是否已发送 |

示例：
```python
@filter.llm_tool(name="get_online_players")
async def get_online_players(self, event: AstrMessageEvent, server: str = None) -> MessageEventResult:
    '''获取指定 Minecraft 服务器在线玩家列表。

    Args:
        server(string): 服务器实例 ID，默认为 default_server_id
    '''
    server = server or self.bridge.config.default_server_id
    data = await self.bridge.send_query(server, "online_players")
    players = [p["name"] for p in data["players"]]
    yield event.plain_result(f"在线玩家({data['count']}): " + ", ".join(players))
```

## 6. 配置项（AstrBot 插件 config）

| 配置项 | 默认值 | 描述 |
|---|---|---|
| `ws_host` | `0.0.0.0` | WS 监听地址 |
| `ws_port` | `8765` | WS 监听端口 |
| `ws_path` | `/ws` | WS 路径 |
| `shared_token` | `change-me` | 与 Java 端 `bridge.sharedToken` 一致 |
| `default_server_id` | `default` | 工具未指定 server 时的默认实例 |
| `heartbeat_timeout` | `15` | 心跳超时秒数，超时判定离线 |
| `rpc_timeout` | `10` | task/query 等待结果超时秒数 |
| `group_id` | `minecraft` | 虚拟群前缀 |

## 7. 开发里程碑（AstrBot 插件）

**M1 通信底座**：WS 服务端 + Bearer 鉴权 + 连接注册表 + 心跳监控/`heartbeat_ack`。对照本仓库 Java 端（已能连接+心跳）联调：起 AstrBot 插件 → `/bridge on` → 服务端看到连接与心跳。

**M2 平台适配器**：`minecraft` 平台适配器 + 事件路由。聊天事件出现在 WebUI/QQ；`/mc send <text>` 或群会话回复能下发给 bot（`send_chat`）。完成 QQ↔游戏双向文本通路。

**M3 AI 工具**：注册全部 8 个工具；在 QQ 群用自然语言触发（“看一下 bot 血量”“让 bot 去 100 210 -300”），验证 query/task 全链路 + 超时/失败提示。

**M4 加固**：多实例路由与群绑定、RPC 超时与重试、心跳抖动容错、操作日志/审计、命令白名单（Java 端限制 `run_command` 类危险动作）、端口仅绑定内网 + 防火墙。

## 8. 安全注意事项

- **Token 必改**：两端一致，不落代码/不提交仓库。
- **网络隔离**：8765 只绑内网，公网需放防火墙/TLS。
- **最小权限动作**：Java 端仅实现 `send_chat/move_to/attack_nearest`，`run_command/eat_food/use_item` 默认拒绝，防止危险操作。
- **审计**：AstrBot 记录每个来自 QQ 的调用与游戏内执行结果；Java 端日志已含 task_id。
- **异常兜底**：所有异步回调 try/except，RPC 超时必须给用户可读错误，不能悬挂。

## 9. Java 端参考（已实现，勿重复开发）

本仓库 `src/main/java/org/example/module/BridgeModule.java`：
- `registerEvents()`：再上报 chat/whisper/system/join/leave/bot_status/death
- `handleIncomingMessage()` → `handleTask`（send_chat/move_to/attack_nearest）+ `handleQuery`（online_players/bot_status/inventory/nearby_entities）
- 心跳/重连/`connect()`/`disconnect()`/`sendMessage()`
- 命令 `/bridge`（别名 `/ws`）：on/off/status/reconnect/wsUrl/sharedToken/serverId

Java 端发往 AstrBot 的消息以 3.3 为准；AstrBot 侧实现必须与 3.2/3.4 逐字段对齐，联调时先用测试客户端（以下脚本可复用）验证服务端行为。