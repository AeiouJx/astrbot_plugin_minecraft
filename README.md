# astrbot_plugin_minecraft_bridge

通过 WebSocket 将 **ZenithProxy (Minecraft)** 与 **AstrBot** 深度集成：游戏事件上报、QQ 群聊下发指令、AI 工具调用控制游戏 Bot。

> 本项目为 [ZenithProxy 插件方案](plane.md) 的 AstrBot (Python) 侧实现。Java 端 (ZenithProxy 插件) 负责作为 WebSocket 客户端主动连接本插件提供的服务端。

## 功能特性

- **WebSocket 全双工通信**：AstrBot 侧作为 WS 服务端（监听 `0.0.0.0:8765 /ws`），Bearer Token 鉴权，支持断线自动重连
- **双向消息桥接**：Minecraft 游戏聊天/私聊事件推送到 AstrBot（作为虚拟 `minecraft` 平台），AstrBot 回复/指令下发给游戏 Bot 发言
- **AI 工具控制**：注册 8 个 LLM 工具，AI 可查询/控制游戏 Bot（见下表）
- **多实例支持**：以 `server_id` 区分多个 Minecraft 服务端
- **心跳监控**：超时自动判定离线并广播状态

## AI 工具清单

| 工具名 | 类型 | 说明 |
|---|---|---|
| `get_server_status` | query | 服务器连接状态 |
| `get_online_players` | query | 在线玩家列表 |
| `get_bot_state` | query | Bot 详细状态（血/饥饿/坐标） |
| `get_inventory` | query | 背包物品列表 |
| `get_nearby_entities` | query | 附近实体（可指定半径） |
| `move_bot` | task | baritone 寻路移动 |
| `attack_nearest` | task | 攻击最近攻击性实体 |
| `send_chat` | task | 发送公共聊天 |

## 配置项

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `ws_host` | `0.0.0.0` | WS 监听地址 |
| `ws_port` | `8765` | WS 监听端口 |
| `ws_path` | `/ws` | WS 路径 |
| `shared_token` | `change-me` | 共享鉴权 Token（**必须修改**，与 Java 端一致） |
| `default_server_id` | `default` | 工具未指定 server 时的默认实例 |
| `heartbeat_timeout` | `15` | 心跳超时秒数 |
| `rpc_timeout` | `10` | task/query 等待超时秒数 |
| `group_id_prefix` | `minecraft` | 虚拟群 ID 前缀 |
| `bridge_on` | `false` | 插件启动时是否自动启动 WS 服务 |

## 使用方法

1. 安装插件并填写配置（`shared_token` 必须与 Java 端 `bridge.sharedToken` 一致）
2. 用 `/mcbridge on` 启动 WS 服务，或配置 `bridge_on=true` 开机自启
3. ZenithProxy 插件连接后即可：

| 命令 | 说明 |
|---|---|
| `/mcbridge status` | 查看桥接状态 |
| `/mcbridge list` | 查看已连接实例 |
| `/mc <消息>` | 让 Bot 在游戏内发言 |
| 直接对话 | 游戏内玩家发言会作为 `minecraft` 平台消息进入 AstrBot，AI 可自动回复 |

## 开发

### 目录结构

```
astrbot_plugin_minecraft_bridge/
├── metadata.yaml              # 插件元数据
├── main.py                   # 插件入口 (Star 类)
├── _conf_schema.json         # 配置 Schema
├── bridge/                   # WebSocket 桥接核心
│   ├── ws_server.py          # aiohttp WS 服务端
│   ├── protocol.py           # 消息协议 + RPC 关联
│   ├── connection.py         # 单连接封装 + 心跳监控
│   └── registry.py           # server_id 路由注册表
├── adapter/                  # minecraft 虚拟平台适配器
├── tools/                    # AI 工具
└── requirements.txt          # 依赖
```

### 协议

通信协议与平面文档 [plane.md](plane.md) 第 3 章保持一致：`heartbeat/heartbeat_ack`、`event`、`task/task_result`、`query/query_result`，JSON 文本帧。

## 风险 & 安全

- **Token 必改**：默认 `change-me`，请配置唯一值，勿提交仓库
- **网络隔离**：`ws_port` 建议仅绑内网，公网需放防火墙/TLS
- **最小权限**：Java 端仅实现了 `send_chat/move_to/attack_nearest`，注入了 `run_command` 等危险动作拒绝策略

## License

MIT