# 处理消息事件

本节详细介绍 AstrBot 插件中如何处理各种消息事件，包括事件监听、命令定义、事件过滤和事件钩子。

## 事件监听基础

### 基本事件监听

```python
from astrbot.api.event import filter, AstrMessageEvent

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    @filter.on_event()
    async def on_any_message(self, event: AstrMessageEvent):
        """监听所有消息事件"""
        print(f"收到消息: {event.message_str}")
```

### 监听特定平台事件

```python
@filter.on_platform("qq")
async def on_qq_message(self, event: AstrMessageEvent):
    """只监听 QQ 平台的消息"""
    print(f"QQ 消息: {event.message_str}")
```

## 命令系统

### 单个命令

```python
@filter.command("help")
async def on_help(self, event: AstrMessageEvent):
    """显示帮助信息"""
    help_text = """
    可用命令:
    /help - 显示帮助
    /time - 显示时间
    /echo <消息> - 回显消息
    """
    await event.plain_result(help_text)
```

### 命令组

```python
@filter.command_group("admin")
class AdminGroup:
    @filter.command("ban")
    async def on_ban(self, event: AstrMessageEvent):
        """封禁用户"""
        # 实现封禁逻辑
        await event.plain_result("用户已封禁")
        
    @filter.command("unban")
    async def on_unban(self, event: AstrMessageEvent):
        """解封用户"""
        # 实现解封逻辑
        await event.plain_result("用户已解封")
```

## 事件类型过滤

### 文本消息

```python
@filter.text_message()
async def on_text_message(self, event: AstrMessageEvent):
    """只处理文本消息"""
    print(f"文本消息: {event.message_str}")
```

### 图片消息

```python
@filter.image_message()
async def on_image_message(self, event: AstrMessageEvent):
    """只处理图片消息"""
    # 获取图片 URL
    for comp in event.message:
        if hasattr(comp, 'url'):
            print(f"图片 URL: {comp.url}")
```

### 特定事件类型

```python
@filter.event_type("group_message")
async def on_group_message(self, event: AstrMessageEvent):
    """只处理群组消息"""
    print(f"群组消息: {event.message_str}")
```

## 平台过滤

### 指定平台

```python
@filter.platform("qq")
async def on_qq_only(self, event: AstrMessageEvent):
    """只在 QQ 平台触发"""
    await event.plain_result("这是 QQ 专属功能")
```

### 多平台支持

```python
@filter.platform("qq", "telegram")
async def on_multi_platform(self, event: AstrMessageEvent):
    """在 QQ 和 Telegram 平台触发"""
    await event.plain_result("支持多平台的功能")
```

## 权限过滤

### 管理员权限

```python
@filter.admin_permission()
async def on_admin_command(self, event: AstrMessageEvent):
    """需要管理员权限"""
    await event.plain_result("管理员专属命令")
```

### 群主权限

```python
@filter.owner_permission()
async def on_owner_command(self, event: AstrMessageEvent):
    """需要群主权限"""
    await event.plain_result("群主专属命令")
```

### 自定义权限

```python
@filter.permission("custom_permission")
async def on_custom_permission(self, event: AstrMessageEvent):
    """自定义权限检查"""
    # 实现自定义权限逻辑
    user_id = event.sender.id
    if self.check_permission(user_id):
        await event.plain_result("权限验证通过")
    else:
        await event.plain_result("权限不足")
```

## 事件钩子

### on_astrbot_loaded

```python
@filter.on_astrbot_loaded()
async def on_loaded(self):
    """AstrBot 加载完成时触发"""
    print("插件已加载")
    # 初始化资源
    await self.initialize_resources()
```

### on_llm_request

```python
@filter.on_llm_request()
async def on_llm_request(self, event: AstrMessageEvent):
    """LLM 请求前触发"""
    # 可以修改请求内容
    print(f"LLM 请求: {event.message_str}")
```

### on_llm_response

```python
@filter.on_llm_response()
async def on_llm_response(self, event: AstrMessageEvent):
    """LLM 响应后触发"""
    # 可以修改响应内容
    print(f"LLM 响应: {event.message_str}")
```

### on_agent_begin

```python
@filter.on_agent_begin()
async def on_agent_begin(self, event: AstrMessageEvent):
    """Agent 开始执行时触发"""
    print("Agent 开始执行")
```

### on_using_llm_tool

```python
@filter.on_using_llm_tool()
async def on_using_llm_tool(self, event: AstrMessageEvent):
    """使用 LLM 工具时触发"""
    print(f"使用工具: {event.tool_name}")
```

### on_llm_tool_respond

```python
@filter.on_llm_tool_respond()
async def on_llm_tool_respond(self, event: AstrMessageEvent):
    """LLM 工具响应后触发"""
    print(f"工具响应: {event.tool_result}")
```

### on_agent_done

```python
@filter.on_agent_done()
async def on_agent_done(self, event: AstrMessageEvent):
    """Agent 执行完成时触发"""
    print("Agent 执行完成")
```

### on_decorating_result

```python
@filter.on_decorating_result()
async def on_decorating_result(self, event: AstrMessageEvent):
    """装饰结果时触发"""
    # 可以修改最终结果
    print(f"装饰结果: {event.message_str}")
```

### after_message_sent

```python
@filter.after_message_sent()
async def after_message_sent(self, event: AstrMessageEvent):
    """消息发送后触发"""
    print("消息已发送")
    # 记录日志或其他后处理
```

## 优先级

### 设置优先级

```python
@filter.command("high_priority")
@filter.priority(10)
async def on_high_priority(self, event: AstrMessageEvent):
    """高优先级命令"""
    await event.plain_result("高优先级命令")

@filter.command("low_priority")
@filter.priority(1)
async def on_low_priority(self, event: AstrMessageEvent):
    """低优先级命令"""
    await event.plain_result("低优先级命令")
```

### 优先级说明

- 优先级范围: 1-100
- 数值越大，优先级越高
- 默认优先级: 50

## 事件传播控制

### 阻止事件传播

```python
@filter.command("stop_propagation")
async def on_stop_propagation(self, event: AstrMessageEvent):
    """阻止事件继续传播"""
    await event.plain_result("事件已处理")
    event.stop_propagation()  # 阻止后续处理器执行
```

### 检查事件是否已处理

```python
@filter.command("check_handled")
async def on_check_handled(self, event: AstrMessageEvent):
    """检查事件是否已被处理"""
    if event.is_handled:
        await event.plain_result("事件已被其他处理器处理")
    else:
        await event.plain_result("事件未被处理")
```

## 综合示例

```python
from astrbot.api.star import Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.star import Star

class MessageHandlerPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    @filter.on_astrbot_loaded()
    async def on_loaded(self):
        print("消息处理器插件已加载")
        
    @filter.command("menu")
    @filter.admin_permission()
    async def on_menu(self, event: AstrMessageEvent):
        """管理员菜单"""
        menu_text = """
        管理员菜单:
        1. /ban <user_id> - 封禁用户
        2. /unban <user_id> - 解封用户
        3. /stats - 查看统计
        """
        await event.plain_result(menu_text)
        
    @filter.text_message()
    async def on_text(self, event: AstrMessageEvent):
        """处理所有文本消息"""
        # 记录消息日志
        self.context.logger.info(f"收到文本: {event.message_str}")
        
    @filter.after_message_sent()
    async def after_send(self, event: AstrMessageEvent):
        """消息发送后记录日志"""
        self.context.logger.info(f"已发送回复")
```

## 下一步

掌握了消息事件处理后，你可以学习：
- [发送各种类型的消息](04-send-message.md)
- [配置插件选项](05-plugin-config.md)
- [开发插件页面](06-plugin-pages.md)