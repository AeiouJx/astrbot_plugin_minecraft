# astrbot_plugin_minecraft_bridge

Deep integration between **ZenithProxy (Minecraft)** and **AstrBot** via WebSocket: game event reporting, QQ group chat command dispatch, and AI tool-based control of game bots.

> This project is the AstrBot (Python) side of the [ZenithProxy bridge solution](plane.md). The Java side (ZenithProxy plugin) acts as a WebSocket client that connects to the server provided by this plugin.

## Requirements

This plugin requires the **ZenithProxy plugin** on the Minecraft server side to function. Please install and configure it from:

**https://github.com/AeiouJx/ZenithProxyRaspiPlugin**

## Features

- **WebSocket Full-Duplex Communication**: AstrBot acts as the WS server (listening on `0.0.0.0:8765 /ws`) with Bearer Token authentication and automatic reconnection on disconnect
- **Bidirectional Message Bridging**: Minecraft game chat/private message events are pushed to AstrBot (as a virtual `minecraft` platform), and AstrBot replies/instructions are sent back to the game bot
- **AI Tool Control**: 8 LLM tools registered for AI to query/control the game bot (see table below)
- **Multi-Instance Support**: Multiple Minecraft server instances distinguished by `server_id`
- **Heartbeat Monitoring**: Automatic offline detection and status broadcast on timeout

## AI Tools

| Tool Name | Type | Description |
|---|---|---|
| `get_server_status` | query | Server connection status |
| `get_online_players` | query | List of online players |
| `get_bot_state` | query | Bot detailed state (health/hunger/coordinates) |
| `get_inventory` | query | Inventory item list |
| `get_nearby_entities` | query | Nearby entities (configurable radius) |
| `move_bot` | task | Baritone pathfinding movement |
| `attack_nearest` | task | Attack nearest hostile entity |
| `send_chat` | task | Send public chat message |

## Configuration

| Key | Default | Description |
|---|---|---|
| `ws_host` | `0.0.0.0` | WS listen address |
| `ws_port` | `8765` | WS listen port |
| `ws_path` | `/ws` | WS path |
| `shared_token` | `change-me` | Shared auth token (**must change**, must match Java side) |
| `default_server_id` | `default` | Default instance when tool does not specify a server |
| `heartbeat_timeout` | `15` | Heartbeat timeout in seconds |
| `rpc_timeout` | `10` | task/query wait timeout in seconds |
| `group_id_prefix` | `minecraft` | Virtual group ID prefix |
| `bridge_on` | `false` | Auto-start WS service on plugin startup |

## Usage

1. Install the plugin and configure it (`shared_token` must match the Java side's `bridge.sharedToken`)
2. Start the WS service with `/mcbridge on`, or set `bridge_on=true` for auto-start on boot
3. Once the ZenithProxy plugin connects, you can:

| Command | Description |
|---|---|
| `/mcbridge status` | View bridge status |
| `/mcbridge list` | List connected instances |
| `/mc <message>` | Send a chat message in-game |
| Direct chat | Player messages in-game are injected into AstrBot as `minecraft` platform messages, and AI can respond automatically |

## Development

### Directory Structure

```
astrbot_plugin_minecraft_bridge/
├── metadata.yaml              # Plugin metadata
├── main.py                   # Plugin entry (Star class)
├── _conf_schema.json         # Configuration schema
├── bridge/                   # WebSocket bridge core
│   ├── ws_server.py          # aiohttp WS server
│   ├── protocol.py           # Message protocol + RPC correlation
│   ├── connection.py         # Single connection wrapper + heartbeat
│   └── registry.py           # server_id routing registry
├── adapter/                  # minecraft virtual platform adapter
├── tools/                    # AI tools
└── requirements.txt          # Dependencies
```

### Protocol

The communication protocol follows [plane.md](plane.md) Chapter 3: `heartbeat/heartbeat_ack`, `event`, `task/task_result`, `query/query_result` as JSON text frames.

## Security

- **Token must be changed**: Default is `change-me`, set a unique value and never commit it to the repository
- **Network isolation**: `ws_port` should bind to internal network only; public network requires firewall/TLS
- **Least privilege**: Java side only implements `send_chat/move_to/attack_nearest`; dangerous actions like `run_command` are rejected

## License

MIT

## Changelog

### 2026-09-07

- **QQ 群推送修复**: 使用 AstrBot `MessageSesion` 格式 (`{platform_id}:GroupMessage:{group_id}`) 调用 `context.send_message()`，正确找到 QQ 平台适配器并推送消息
- **Dashboard 实例消息分离**: 选择哪个 BOT 实例就显示哪个实例的消息，默认选中第一个实例
- **Dashboard 配置面板修复**: `_api_get_config` 返回 QQ 推送相关配置项；加载时自动填充表单；保存按钮真正调用 API 保存配置
- **保存配置不再断开连接**: 只有 WS 相关配置变更时才重启 bridge
- **平台自动注册**: 插件启动时自动注册 `minecraft_bridge` 平台
- **后台事件消费**: `_consume_events()` 直接从 `event_queue` 读取事件推送到 Dashboard 和 QQ

### 2026-09-06

- **LLM 自动回复**: 游戏内玩家聊天触发 AI 自动回复，支持权重触发、速率限制、提示模板
- **QQ 群推送**: 玩家聊天和游戏事件（加入/离开/死亡/成就）推送到指定 QQ 群，支持实例前缀 `[server_id]`
- **Dashboard SSE 实时推送**: 使用 `bridge.subscribeSSE()` 接收实时事件，`bridge.apiPost('send')` 发送消息
- **Web Dashboard 重建**: 按 AstrBot Plugin Pages 规范文档重建，修复 bridge SDK 变量名、SSE 认证、模块作用域等问题
- **事件去重**: `maxlen=2048` 去重环，防止重复事件
- **黑白名单**: 群号白名单、用户黑名单
- **消息长度限制**: `inbound_max_message_length` / `outbound_max_message_length`
- **WS 重启修复**: 修复重复启动时旧线程未清理导致重复响应的问题
