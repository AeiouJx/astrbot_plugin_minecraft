# AstrBot 插件开发文档索引

来源: https://docs.astrbot.app/dev/star/plugin-new.html

## 文档列表

| 文件 | 原始 URL | 说明 |
|------|----------|------|
| [01-plugin-new.md](01-plugin-new.md) | /dev/star/plugin-new.html | 插件开发指南 - 从这里开始 |
| [02-simple.md](02-simple.md) | /dev/star/guides/simple.html | 最小实例 |
| [03-listen-message-event.md](03-listen-message-event.md) | /dev/star/guides/listen-message-event.html | 处理消息事件 |
| [04-send-message.md](04-send-message.md) | /dev/star/guides/send-message.html | 消息的发送 |
| [05-plugin-config.md](05-plugin-config.md) | /dev/star/guides/plugin-config.html | 插件配置 |
| [06-plugin-pages.md](06-plugin-pages.md) | /dev/star/guides/plugin-pages.html | 插件 Pages |
| [07-plugin-i18n.md](07-plugin-i18n.md) | /dev/star/guides/plugin-i18n.html | 插件国际化 |
| [08-ai.md](08-ai.md) | /dev/star/guides/ai.html | 调用 AI |
| [09-storage.md](09-storage.md) | /dev/star/guides/storage.html | 插件存储 |
| [10-html-to-pic.md](10-html-to-pic.md) | /dev/star/guides/html-to-pic.html | 文转图 |
| [11-session-control.md](11-session-control.md) | /dev/star/guides/session-control.html | 会话控制 |
| [12-other.md](12-other.md) | /dev/star/guides/other.html | 杂项 |
| [13-plugin-publish.md](13-plugin-publish.md) | /dev/star/plugin-publish.html | 发布插件到插件市场 |
| [14-platform-adapter.md](14-platform-adapter.md) | /dev/plugin-platform-adapter.html | 接入平台适配器 |

## 关键要点

### 适配器模式
- 适配器文件命名: `minecraft_platform_adapter.py` + `minecraft_platform_event.py`
- 注册方式: `@register_platform_adapter("minecraft", "描述", default_config_tmpl={...})`
- 核心方法: `meta()`, `run()`, `send_by_session()`
- 事件提交: `self.commit_event(event)`

### 配置系统
- `_conf_schema.json` 定义配置 schema
- `metadata.yaml` 定义插件元数据
- 配置自动保存到 `data/config/<plugin_name>_config.json`

### AI 工具
- 装饰器: `@filter.llm_tool(name="tool_name", desc="描述")`
- 参数通过 docstring 的 `Args:` 段定义
- 支持类型: string, number, object, boolean, array

### 消息发送
- 被动: `yield event.plain_result("text")`
- 主动: `self.context.send_message(unified_msg_origin, chain)`
- 富媒体: `MessageChain().message("text").file_image("path")`
