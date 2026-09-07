# AstrBot 插件 Pages 开发文档

来源: https://docs.astrbot.app/dev/star/guides/plugin-pages.html

## 核心概念

插件 Pages 允许插件在 AstrBot WebUI 中提供自己的页面。
页面文件放在插件目录的 `pages/` 下，由 Dashboard 以受限 iframe 方式加载。

## 目录结构

```
astrbot_plugin_xxx/
├─ main.py
└─ pages/
   └─ dashboard/
       ├─ index.html
       ├─ app.js
       └─ style.css
```

AstrBot 只扫描 `pages/<page_name>/index.html`。

## Bridge 使用

页面脚本通过 `window.AstrBotPluginPage` bridge 和 Dashboard 通信。

```js
const bridge = window.AstrBotPluginPage;
const context = await bridge.ready();
```

不需要手动引入 bridge SDK。AstrBot 返回 HTML 时会自动插入 `/api/plugin/page/bridge-sdk.js`。
如果内联脚本必须同步访问 `window.AstrBotPluginPage`，请显式引入：
```html
<script src="/api/plugin/page/bridge-sdk.js"></script>
```

## 后端 API 注册

```python
context.register_web_api(
    f"/{PLUGIN_NAME}/status",
    self.page_status,
    ["GET"],
    "Get status",
)
```

路由需要包含插件名作为前缀。Page 端的 bridge endpoint 不需要包含插件名：

```js
await bridge.apiGet("status");
```

Dashboard 会把它转发到：
```
/api/v1/plugins/extensions/<plugin_name>/status
```

## Bridge 返回值解包规则

- 如果后端返回 `{ "status": "ok", "data": value }`，Promise resolve 为 `value`。
- 如果后端返回普通 JSON，例如 `{ "message": "pong" }`，Promise resolve 为完整 JSON。
- 如果后端返回 `{ "status": "error", "message": "..." }`，或 HTTP 请求失败，Promise reject 为 Error。

## API 方法

### apiGet(endpoint, params)
```js
const stats = await bridge.apiGet("stats", { limit: 20, tag: "today" });
```

### apiPost(endpoint, body)
```js
const result = await bridge.apiPost("settings/save", { enabled: true });
```

### subscribeSSE(endpoint, handlers, params)
```js
const subscriptionId = await bridge.subscribeSSE("events", {
  onOpen() { console.log("SSE opened"); },
  onMessage(event) { console.log(event.raw, event.parsed); },
  onError() { console.warn("SSE error"); },
}, { topic: "logs" });
```

## 请求对象 (后端)

```python
from astrbot.api.web import request

async def handler(self):
    limit = request.query.get("limit", 20, type=int)
    payload = await request.json(default={})
    return json_response({"saved": True})
```

## 响应对象 (后端)

```python
from astrbot.api.web import json_response, error_response, file_response, stream_response

return json_response({"message": "pong"})
return error_response("invalid", status_code=400)
return file_response(path, filename="export.json", content_type="application/json")
return stream_response(events())
```

## 亮暗主题

bridge SDK 会维护 `<html>` 的 `data-theme` 属性。

```css
:root { --bg: #ffffff; --text: #1a1a1a; }
[data-theme="dark"] { --bg: #1a1a1a; --text: #e0e0e0; }
```

## 调试建议

- Page 没出现：检查 `pages/<page_name>/index.html` 是否存在。
- bridge 不存在：确认脚本在 bridge SDK 注入之后运行；推荐使用外部 `type="module"` 脚本。
- API 未匹配：确认注册路由包含插件名前缀。
