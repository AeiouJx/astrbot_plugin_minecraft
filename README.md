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
