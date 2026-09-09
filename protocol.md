# Minecraft ↔ AstrBot WebSocket 通讯协议

> 中立协议文档,供 ZenithProxy(游戏端)与 AstrBot(中枢端)两端共同遵守,用于两侧对接沟通。
> 配合文档:`minecraft_design.md`(ZenithProxy 端设计)、`astrbot_design.md`(AstrBot 端设计)。

## 1. 角色与连接

- **游戏端 (G)**:ZenithProxy + Java 插件,WebSocket **客户端**
- **中枢端 (S)**:AstrBot + Python 插件,WebSocket **服务端**
- G 主动连接 `ws://{ASTRBOT_IP}:8765/ws`,断线自动重连(间隔 5s)
- 鉴权:WS 握手请求头 `Authorization: Bearer {SHARED_TOKEN}`,两端一致;鉴权失败服务端返回 `401` 并断开

## 2. 帧格式

全部为 **JSON 文本帧**,用 `type` 字段区分方向与类别,必须包含 `type`。

## 3. 消息总表

| type | 方向 | 用途 |
|---|---|---|
| `hello` / `hello_ack` | G→S / S→G | 握手 |
| `heartbeat` / `heartbeat_ack` | G→S / S→G | 保活 |
| `update_info` / `update_info_ack` | G→S / S→G | 运行时更新注册信息 |
| `event` | G→S | 游戏事件上报 |
| `task` / `task_result` | S→G / G→S | 操作指令 / 执行结果 |
| `query` / `query_result` | S→G / G→S | 数据请求 / 查询结果 |

## 4. 握手

连接成功后 G 发送 `hello`(推荐):

```json
{
  "type": "hello",
  "server_id": "raspberrypi-b7e42d91",
  "account": "Pearl",
  "hwid": "dc:a6:32:1e:4f:9a",
  "server_name": "My Minecraft Server",
  "mod_version": "1.0.0",
  "capabilities": ["chat", "whisper", "query", "task"]
}
```

> `server_id` 为**稳定的实例 ID**,同一 ZenProxy 实例重启/换账号不变,用于多实例唯一区分(默认由插件自动生成 `设备名-随机8位`,如 `raspberrypi-b7e42d91`;可用 `/bridge serverId` 手动覆盖)。`account` 为当前登录的 MC 游戏账号名(可选,展示用;缺省回退 `server_id`)。`hwid` 为客户端**主网卡 MAC 地址**(可选,防盗防伪用,标识真实物理机器,不随配置/账号/重装变化)。

S 回复 `hello_ack`:

```json
{
  "type": "hello_ack",
  "server_id": "raspberrypi-b7e42d91",
  "capabilities": ["chat", "query", "task"],
  "timestamp": 1693123456
}
```

> **兼容方式**:若 G 以 `heartbeat` 作为首条消息,S 也接受并回复 `heartbeat_ack`,进入兼容模式。

## 5. 心跳

- G 每 `heartbeat_interval`(默认 5s)发送一次 `heartbeat`;S 对每条 `heartbeat` 回复一条 `heartbeat_ack`
- S 以收到任意消息的时间作为存活依据,超过 `heartbeat_timeout`(建议 3×interval,默认 15s)判定下线
- **G 端存活检测**:连续 `3×heartbeat_interval` 未收到 `heartbeat_ack`,判定连接死亡,强制重连

```json
{"type": "heartbeat", "server_id": "main", "timestamp": 1693123456}
```

## 6. 事件上报(G→S)

统一包装:

```json
{
  "type": "event",
  "server_id": "main",
  "event_type": "chat",
  "data": {"sender": "xxx", "message": "yyy"},
  "timestamp": 1693123456
}
```

### event_type 总表

| event_type | data 字段 | 说明 |
|---|---|---|
| `chat` | `sender`(str), `message`(str) | 玩家公共聊天 |
| `whisper` | `outgoing`(bool), `sender`(str), `receiver`(str), `message`(str) | 私聊 |
| `system` | `message`(str) | 服务器系统消息 |
| `player_join` | `player`(str), `message`(str) | 玩家加入游戏,`message` 为原生描述如 `k70pro joined the game` |
| `player_leave` | `player`(str), `message`(str) | 玩家离开游戏,`message` 为原生描述如 `k70pro left the game` |
| `bot_status` | `status`(str), `bot_name`(str), `health`(float), `food`(int), `position`{x,y,z} | Bot 状态,`bot_name` 为当前登录 BOT ID |
| `death` | `position`{x,y,z} | Bot 死亡(含死亡坐标) |
| `achievement` | `player`(str), `achievement`(str) | 玩家达成成就 |
| `player_death` | `victim`(str), `killer`(str, 可选), `weapon`(str, 可选) | 玩家(非 Bot)死亡 |
| `attack` | `player`(str), `x`(num), `y`(num), `z`(num) | 玩家攻击了 Bot |
| `totem_pop` | `totems_remaining`(int) | Bot/玩家 totem 被消耗,剩余数量 |
| `totem_empty` | - | Bot 已无备用 totem |
| `visual_enter` | `player`(str), `x`(int), `y`(int), `z`(int) | 玩家进入 Bot 视野 |
| `visual_leave` | `player`(str), `x`(int), `y`(int), `z`(int) | 玩家离开 Bot 视野 |
| `visual_logout` | `player`(str), `x`(int), `y`(int), `z`(int) | 视野内玩家退出游戏(最后下线坐标) |
| `connection_denied` | `player`(str), `ip`(str), `reason`(str) | 黑名单/非白名单玩家连接被拒,`reason` 取值 `blacklisted` / `not_whitelisted` |
| `queue_position` | `position`(int) | 进服队位更新(节流:≤1 次/30s) |
| `queue_complete` | `duration_seconds`(int) | 排队完成 |
| `queue_start` | `was_online`(bool), `online_duration_seconds`(int) | 开始排队,`was_online=true` 表示被踢到队列(服务器重启) |
| `queue_skip` | - | 排队被跳过 |
| `queue_warning` | `position`(int), `mention`(bool) | 队位接近(警告) |
| `health_warning` | `health`(float) | Bot 血量下降且低于 8 |
| `health_autodisconnect` | - | 低血自动断线触发 |
| `scan_found` | `target`(str), `name`(str), `x`(int), `y`(int), `z`(int), `distance`(int) | 扫描首次发现目标(方块/实体)及坐标 |
| `disconnect` | `reason`(str), `manual`(bool), `online_duration_seconds`(int), `was_in_queue`(bool), `queue_position`(int) | Bot 断开连接,`reason` 为断线原因(非手动),`manual` 标记手动断开 |
| `client_connecting` | - | Bot 客户端开始连接服务器 |
| `client_connected` | - | Bot 客户端已连上服务器 |
| `client_login_failed` | `error`(str) | Bot 登录失败,`error` 为异常信息 |
| `client_reconfiguring` | - | 客户端进入重配置阶段 |
| `session_time_limit_warning` | `duration_until_kick_minutes`(int), `session_time_limit_hours`(int) | 会话时长限制警告(距踢出剩余分钟数) |
| `auto_reconnect` | `delay_seconds`(int) | 自动重连已调度,`delay_seconds` 为倒计时 |
| `auto_eat_out_of_food` | - | 自动进食模块无食物可吃 |
| `bot_death_message` | `message`(str) | Bot 死亡的具体死亡文本(如 `You were slain by xxx`) |
| `server_restarting` | `message`(str) | 服务器重启公告 |
| `prio_status` | `prio`(bool) | 2b2t 优先队列状态变化 |
| `update_available` | `version`(str, 可选) | 检测到新版本 |
| `update_start` | `version`(str, 可选) | 开始更新/重启 |
| `replay_started` | - | 录像开始 |
| `replay_stopped` | `file`(str, 可选) | 录像结束(可能带文件名) |
| `active_hours_connect` | `will_wait`(bool) | 活跃时段自动连接触发 |
| `spawn_patrol_target` | `player`(str), `x`(int), `y`(int), `z`(int) | 出生点巡逻发现目标 |
| `spawn_patrol_target_killed` | `player`(str), `message`(str) | 出生点巡逻目标死亡 |
| `msa_device_code` | `url`(str), `code`(str) | 微软设备码登录(需浏览器访问 URL 并输入 code) |
| `tasks_command` | `command`(str) | 定时任务命令执行 |
| `plugin_load_failure` | `id`(str, 可选), `jar`(str), `message`(str) | 插件加载失败 |
| `plugin_loaded` | `id`(str), `description`(str), `version`(str), `url`(str), `authors`(str) | 插件加载成功 |
| `client_player_connected` | `player`(str), `mc_version`(str, 可选) | 控制玩家通过 clientConnection 连接代理 |
| `client_player_disconnected` | `player`(str, 可选), `reason`(str, 可选) | 控制玩家断开代理 |
| `spectator_connected` | `player`(str), `mc_version`(str, 可选) | 观察者连接代理 |
| `spectator_disconnected` | `player`(str) | 观察者断开代理 |

字段说明:
- `status` 取值:`online` / `offline` / `dead`
- `achievement` 仅在游戏端可解析成就公告文本时上报(如 `xxx has made the advancement: yyy`)
- `scan_found` 的 `target` 取值:`player` / `ender_pearl` / `item_frame` / `chest` / `ender_chest` / `shulker_box` / `soul_sand` / `bubble_column` / `sign` / `redstone`;`name` 为实际方块注册名(如 `minecraft:chest`)或实体显示名;`distance` 为到 Bot 的欧氏距离。扫描按**水平半径**在已加载区块全高度范围内查找(无垂直限制),仅对首见目标上报,目标消失后再出现会重新上报。

> **3c3u.org 服务器消息解析说明**:该服使用自定义聊天插件,所有聊天内容(公共聊天、私聊、系统消息)**统一走 `SystemChatEvent`**,`PublicChatEvent` / `WhisperChatEvent` 在本服不会触发。因此 **文本 → 结构化事件的解析全部由 G 端(插件)完成**:S 端收到的 `event_type` 已是归类结果(`chat`/`whisper`/`achievement`/`system` 等),S 端**只需按事件类型消费,无需也切勿自行解析原始文本**。
>
> G 端 `handleSystemChatEvent` 内按固定顺序解析(以下为 G 端内部实现,仅供理解,不属于 S 端职责):
> 1. **私聊** — 正则 `^📨\s*(?:\|\|)?(\S+?)\s*[➡→]\s*(.+)$` → `whisper`,输出 `{outgoing, sender, receiver, message}`;解析出的发送者 == Bot 账号名时 `outgoing=true`(Bot 自己发出的私聊),此时 `receiver` 置空
> 2. **公共聊天** — 正则 `^«([^»]+)» (.*)$` → `chat`,输出 `{sender, message}`
> 3. **成就** — `xxx has made the advancement: yyy` / `xxx has completed the challenge: yyy` / `xxx has reached the goal: yyy` → `achievement`,输出 `{player, achievement}`
> 4. **兜底** — 其余全部 → `system`,输出原始文本 `{message}`

### 6.1 G 端 system 兜底消息再解析(持续扩展,无需 S 端配合)

实机测试中若发现某些消息在 3c3u 上**无法触发对应专用事件**(专用事件只在原版/标准消息格式下触发),它们会暂时以 `system` 原文本上报。G 端将在后续迭代中为这些格式**追加文本解析,逐步归类为结构化事件**;一旦新增/改变 `event_type`,本文档第 6 节总表与第 12 节推送表会同步更新。

当前已知可能走 `system` 兜底的消息类别(理论上可触发的事件/输出):

| 消息类别 | 理想事件 | 兜底原因 |
|---|---|---|
| 服务器死亡广播/击杀文本 | `player_death` | 3c3u 死亡消息格式与 `DeathMessageChatEvent` 解析不兼容 |
| Bot 自身死亡文本 | `bot_death_message` | 同上,`ClientDeathMessageEvent` 可能不触发 |
| 玩家进服/出服提示 | `player_join` / `player_leave` | `ServerPlayerConnectedEvent`/`ServerPlayerDisconnectedEvent` 可能不触发 |
| 服务器重启公告 | `server_restarting` | `ServerRestartingEvent` 可能不触发 |
| 其他未识别系统提示 | - | 需测试后逐条归类 |

**协议约定**:S 端只需持续消费 `event_type`,无需因 G 端解析能力扩展而升级改版;对未识别的 `system` 消息按 §12 的 `system` 格式直接推送即可。

## 7. 更新信息(G→S)

连接后 G 可随时更新注册信息,无需断开重连:

```json
{
  "type": "update_info",
  "server_id": "raspberrypi-b7e42d91",
  "account": "Pearl",
  "hwid": "dc:a6:32:1e:4f:9a",
  "mod_version": "1.0.0",
  "capabilities": ["chat", "whisper", "query", "task"]
}
```

S 更新注册表后回复:

```json
{
  "type": "update_info_ack",
  "server_id": "raspberrypi-b7e42d91",
  "timestamp": 1693123456
}
```

> S 收到 `update_info` 后重新注册连接:旧 `server_id` 移除,新 `server_id` 加入注册表。
> `account` 为当前登录的 MC 游戏账号名(可选字段,用于 UI/QQ 推送展示;缺省时回退用 `server_id`)。`hwid` 为主网卡 MAC(可选,防盗防伪,跨 `server_id` 变化仍可识别同一机器)。

## 8. 任务(S→G)

```json
{
  "type": "task",
  "task_id": "unique_001",
  "action": "send_chat",
  "params": {"message": "大家好！"}
}
```

### 已约定 action

| action | params | 说明 |
|---|---|---|
| `send_chat` | `message`(str) | Bot 发送公共聊天 |
| `move_to` | `x`(int), `y`(int), `z`(int) | Baritone 寻路移动 |
| `attack_nearest` | `radius`(float, 可选, 默认16) | 攻击最近的非玩家攻击性实体 |

执行完成后 G 回复:

```json
{
  "type": "task_result",
  "task_id": "unique_001",
  "success": true,
  "error_message": null
}
```

## 9. 查询(S→G)

```json
{
  "type": "query",
  "query_id": "query_001",
  "resource": "online_players",
  "params": {}
}
```

### 已约定 resource 与返回 data

| resource | params | data 返回结构 |
|---|---|---|
| `online_players` | - | `{"players":[{"name","ping"}],"count":n}` |
| `bot_status` | - | `{"status","health","food","position":{"x","y","z"},"heldItemSlot"}` |
| `inventory` | - | `{"items":[{"slot","id","name","count"}],"count":n}` |
| `nearby_entities` | `radius`(float, 默认32) | `{"entities":[{"entity_id","type","player"?,"distance","x","y","z"}],"count":n}` |

G 回复:

```json
{
  "type": "query_result",
  "query_id": "query_001",
  "success": true,
  "data": {},
  "error_message": null
}
```

## 10. 请求-响应关联

- `task_id` / `query_id` 由 S 生成(UUID),响应原样带回
- S 维护 pending 队列,收到结果后按 id 立即解析,超时默认 10s(`rpc_timeout`)
- 超时未响应视为失败,由 S 处理补偿

## 11. 多实例

同一 AstrBot 可接入多个 Minecraft 服务端:以 `server_id` 区分。S 连接注册表 `dict[server_id -> BridgeConnection]`。

## 12. 事件 → QQ 群推送(AstrBot 侧行为)

AstrBot 将接收到的 `event` 按以下规则推送到 QQ 群(目标群号配置为 `minecraft_event_group`,内部转换为 `aiocqhttp:group:{group_id}`):

| 事件类型 | 触发开关 | QQ 群消息格式 |
|---|---|---|
| `chat` | `chat_push_enabled` | `[server_id] 玩家名: 消息内容` |
| `whisper` | `chat_push_enabled` | `[server_id] 玩家名 -> 目标: 消息内容` |
| `player_join` | `server_event_push_enabled` | `[server_id] {message}` |
| `player_leave` | `server_event_push_enabled` | `[server_id] {message}` |
| `death` | `server_event_push_enabled` | `[server_id] Bot 死亡了 [x,y,z]` |
| `achievement` | `server_event_push_enabled` | `[server_id] 玩家 玩家名 达成了成就: 成就名` |
| `player_death` | `server_event_push_enabled` | `[server_id] 玩家 玩家名 死亡了`(有击杀者/武器时附 `被 xxx 击杀 [武器]`) |
| `attack` | `server_event_push_enabled` | `[server_id] ⚠ 玩家 玩家名 攻击了 Bot [x,y,z]` |
| `totem_pop` | `server_event_push_enabled` | `[server_id] ⚠ 有人 totem 弹出,剩余 n 个` |
| `totem_empty` | `server_event_push_enabled` | `[server_id] ⚠ Bot 已无备用 totem,请补给` |
| `visual_enter` | `server_event_push_enabled` | `[server_id] 玩家 玩家名 进入视野 [x,y,z]` |
| `visual_leave` | `server_event_push_enabled` | `[server_id] 玩家 玩家名 离开视野 [x,y,z]` |
| `visual_logout` | `server_event_push_enabled` | `[server_id] 玩家 玩家名 退出游戏 [x,y,z]` |
| `connection_denied` | `server_event_push_enabled` | `[server_id] 拒绝玩家 玩家名 连接(原因/IP)` |
| `queue_position` | `server_event_push_enabled` | `[server_id] 排队中,当前位次: n` |
| `queue_complete` | `server_event_push_enabled` | `[server_id] 排队完成,已进入服务器` |
| `health_warning` | `server_event_push_enabled` | `[server_id] ⚠ Bot 血量过低: n 点` |
| `health_autodisconnect` | `server_event_push_enabled` | `[server_id] ⚠ Bot 因低血自动断开连接` |
| `scan_found` | `server_event_push_enabled` | `[server_id] 🔍 扫描发现 {target}: {name} [x,y,z](距离 n)` |
| `system` | `server_event_push_enabled` | `[server_id] 系统: 消息内容` |
| `bot_status` | 可选(未默认推送) | 自定 |
| `client_player_connected` | 可选(未默认推送) | `[server_id] 🖥 控制玩家 {player} 已连接代理 (MC {mc_version})` |
| `client_player_disconnected` | 可选(未默认推送) | `[server_id] 🔌 控制玩家 {player} 断开代理`(带 reason 时附 `: {reason}`) |
| `spectator_connected` | 可选(未默认推送) | `[server_id] 👁 观察者 {player} 已连接代理 (MC {mc_version})` |
| `spectator_disconnected` | 可选(未默认推送) | `[server_id] 👁 观察者 {player} 已断开代理` |

### 高价值事件 → QQ 群推送（参照 Discord 通知器结构）

以下事件对应 ZenithProxy 内置 Discord 通知器(`NotificationEventListener`)中的高价值通知,推送开关默认 `server_event_push_enabled`:

| 事件类型 | QQ 群消息格式 | 对应 Discord 通知标题 |
|---|---|---|
| `queue_start` | `[server_id] ⚠ 开始排队 (被踢到队列)`(was_online=true 时带 `在线 x s 后被踢`) | `Started Queuing` |
| `queue_skip` | `[server_id] 跳过排队,直接进服` | - |
| `queue_warning` | `[server_id] ⚠ 队位警告:当前第 n 位` | `Queue Warning` |
| `disconnect` | `[server_id] ⚠ Bot 断开: {reason} (在线 x s)`(manual=true 时为 `Bot 已手动断开`;原因缺省时显示连接类别) | `Disconnected` |
| `client_connecting` | `[server_id] 🔌 正在连接服务器...` | `Connecting...` |
| `client_connected` | `[server_id] ✅ 已连接服务器` | `Connected` |
| `client_login_failed` | `[server_id] ❌ 登录失败: {error}` | `Login Failed` |
| `client_reconfiguring` | `[server_id] 🔧 客户端重新配置中` | `Reconfiguring...` |
| `session_time_limit_warning` | `[server_id] ⏳ 会话时长限制:剩余 n 分钟将被踢出` | `Session Time Limit Warning` |
| `auto_reconnect` | `[server_id] 🔄 n 秒后自动重连` | `AutoReconnecting` |
| `auto_eat_out_of_food` | `[server_id] ⚠ 自动进食无食物可用` | `AutoEat Out Of Food` |
| `bot_death_message` | `[server_id] 💀 Bot 死亡: {message}` | `Death Message` |
| `server_restarting` | `[server_id] ⚠ 服务器重启: {message}` | `Server Restarting` |
| `prio_status` | `[server_id] ⭐ 优先队列: 已获得/已失去`(prio=true/false) | `Prio Queue Status Detected/Lost` |
| `update_available` | `[server_id] 📦 有新版本可用: {version}` | `Update Available!` |
| `update_start` | `[server_id] 📦 开始更新/重启...` | `Updating and restarting...` |
| `replay_started` | `[server_id] 🎥 录像开始` | `Replay Recording Started` |
| `replay_stopped` | `[server_id] 🎥 录像结束`(有文件名时附 `: {file}`) | `Replay Recording Stopped` |
| `active_hours_connect` | `[server_id] ⏰ 活跃时段连接触发`(will_wait=true 时附 `等待 1 分钟`) | `Active Hours Connect Triggered` |
| `spawn_patrol_target` | `[server_id] 🎯 巡逻发现目标: 玩家名 [x,y,z]` | `Target Acquired` |
| `spawn_patrol_target_killed` | `[server_id] 💀 巡逻击杀目标: 玩家名 ({message})` | `Target Killed` |
| `msa_device_code` | `[server_id] 🔑 微软登录: 打开 {url} 输入验证码 {code}` | `Microsoft Device Code Login` |
| `tasks_command` | `[server_id] ⚙ 定时任务执行: {command}` | `Scheduled Task Executed` |
| `plugin_load_failure` | `[server_id] ❌ 插件加载失败: {id} ({message})` | `Plugin Load Failure` |
| `plugin_loaded` | `[server_id] 📦 插件加载成功: {id} v{version}` | `Plugin Loaded` |

## 13. 两端配置项

| 配置项 | 默认值 | 描述 |
|---|---|---|
| `ws_host` | `0.0.0.0` | S 端 WS 监听地址 |
| `ws_port` | `8765` | S 端 WS 监听端口 |
| `ws_path` | `/ws` | S 端 WS 路径 |
| `shared_token` | `change-me` | 共享鉴权 Token(必须修改) |
| `default_server_id` | `default` | 默认服务器实例 ID |
| `heartbeat_interval` | `5` | 心跳间隔秒数(G 发 / S 可校验) |
| `heartbeat_timeout` | `15` | 心跳超时秒数(S 判定下线) |
| `rpc_timeout` | `10` | task/query 超时秒数 |

## 14. 安全

- Token 必须修改为唯一值
- 生产环境建议绑定内网或加 TLS(`wss://`),公网需放行防火墙/安全组
- 危险动作(如封禁、删除物品)两端均应拒绝

## 15. 变更记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-09-06 | v1.0 | 初稿:握手/心跳/事件/任务/查询 |
| 2026-09-07 | v1.1 | 新增 `update_info`;新增 `death`/`achievement` 事件;`bot_status` 增加 `bot_name`;事件→QQ 推送规则 |
| 2026-09-08 | v1.2 | `hello`/`update_info` 新增 `account`(MC 账号名,展示用)与 `hwid`(主网卡 MAC,防盗防伪);`server_id` 默认改为自动生成 `设备名-随机8位` |
| 2026-09-09 | v1.3 | 新增事件:`player_death`(改用 `DeathMessageChatEvent` 专用事件)、`attack`、`totem_pop`/`totem_empty`、`visual_enter`/`visual_leave`、`connection_denied`、`queue_position`/`queue_complete`、`health_warning`/`health_autodisconnect`;`queue_position` 节流 ≤1 次/30s |
| 2026-09-09 | v1.3.1 | `death`(Bot 死亡)新增 `position` 死亡坐标;新增 `visual_logout`(视野内玩家下线坐标);`visual_enter`/`visual_leave`/`visual_logout` 兜底玩家实体缺失 |
| 2026-09-09 | v1.3.2 | 新增扫描功能:周期性扫描 Bot 周围指定方块与实体,首次发现上报 `scan_found`{target,name,x,y,z,distance};可配 targets/radius/interval |
| 2026-09-09 | v1.3.3 | 扫描改用游戏刻(`ClientBotTick`)驱动,无独立线程;扫描按水平半径全高范围;`targets` 新增 `redstone`(红石系列);`player_join`/`player_leave` 新增 `message` 原生描述(`xx joined/left the game`) |
| 2026-09-09 | v1.4 | 新增高价值事件推送(参照 ZenithProxy Discord 通知器结构):`queue_start`/`queue_skip`/`queue_warning`、`disconnect`、`client_connecting`/`client_connected`/`client_login_failed`/`client_reconfiguring`、`session_time_limit_warning`、`auto_reconnect`、`auto_eat_out_of_food`、`bot_death_message`、`server_restarting`、`prio_status`、`update_available`/`update_start`、`replay_started`/`replay_stopped`、`active_hours_connect`、`spawn_patrol_target`/`spawn_patrol_target_killed`、`msa_device_code`、`tasks_command`、`plugin_load_failure`;新增 QQ 推送格式表 |
| 2026-09-10 | v1.5 | 新增 `plugin_loaded` 事件(对应 Discord `PluginLoadedEvent` 通知);补充 3c3u.org 服务器消息路由说明(所有聊天统一走 `SystemChatEvent` 及解析顺序/正则);`plugin_load_failure`/`plugin_loaded` 加入 QQ 推送格式表 |
| 2026-09-10 | v1.6 | 新增 4 个代理控制连接事件(对齐 Discord `PlayerConnectedEvent`/`PlayerDisconnectedEvent`/`SpectatorConnectedEvent`/`SpectatorDisconnectedEvent`):`client_player_connected`/`client_player_disconnected`/`spectator_connected`/`spectator_disconnected`;3c3u 说明改写为「解析全部由 G 端完成、S 端只消费」;新增 §6.1 G 端 system 兜底消息再解析规划 |