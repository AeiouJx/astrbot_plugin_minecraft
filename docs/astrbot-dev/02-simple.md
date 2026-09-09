# 最小实例

本节将展示一个最小的 AstrBot 插件示例，帮助你快速上手插件开发。

## 基本结构

一个最小的 AstrBot 插件包含以下核心组件：

1. **Star 类**: 继承自 `Star`，作为插件的主类
2. **命令装饰器**: 使用 `@filter.command` 定义命令
3. **事件处理**: 处理 `AstrMessageEvent` 事件

## 完整示例

```python
from astrbot.api.star import Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.star import Star

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    @filter.command("hello")
    async def on_hello(self, event: AstrMessageEvent):
        """
        处理 /hello 命令
        """
        await event.plain_result("你好！这是一个示例插件。")
```

## 代码解析

### 1. 导入必要的模块

```python
from astrbot.api.star import Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.star import Star
```

- `Context`: 提供插件与 AstrBot 核心的交互接口
- `filter`: 包含各种装饰器，用于定义命令和过滤器
- `AstrMessageEvent`: 表示收到的消息事件
- `Star`: 插件基类

### 2. 定义插件类

```python
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
```

- 继承 `Star` 基类
- 在构造函数中调用 `super().__init__(context)`
- `context` 对象提供了与 AstrBot 核心交互的能力

### 3. 定义命令

```python
@filter.command("hello")
async def on_hello(self, event: AstrMessageEvent):
    """
    处理 /hello 命令
    """
    await event.plain_result("你好！这是一个示例插件。")
```

- `@filter.command("hello")`: 定义一个名为 `hello` 的命令
- `async def on_hello`: 异步处理函数
- `event: AstrMessageEvent`: 接收消息事件参数
- `event.plain_result()`: 发送纯文本回复

## 运行插件

1. 将插件文件放入 AstrBot 的插件目录
2. 重启 AstrBot 或启用热重载
3. 在聊天中发送 `/hello` 命令
4. 插件会回复 "你好！这是一个示例插件。"

## 扩展功能

### 带参数的命令

```python
@filter.command("greet")
async def on_greet(self, event: AstrMessageEvent):
    """
    处理 /greet 命令，支持参数
    """
    # 获取命令参数
    args = event.message_str.split()[1:] if len(event.message_str.split()) > 1 else []
    
    if args:
        name = " ".join(args)
        await event.plain_result(f"你好，{name}！")
    else:
        await event.plain_result("你好！请告诉我你的名字。")
```

### 使用命令组

```python
@filter.command_group("utils")
class UtilsGroup:
    @filter.command("time")
    async def on_time(self, event: AstrMessageEvent):
        """获取当前时间"""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await event.plain_result(f"当前时间: {now}")
        
    @filter.command("date")
    async def on_date(self, event: AstrMessageEvent):
        """获取当前日期"""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        await event.plain_result(f"当前日期: {today}")
```

### 响应不同消息类型

```python
@filter.command("echo")
async def on_echo(self, event: AstrMessageEvent):
    """回显用户输入"""
    # 获取用户输入的消息
    user_input = event.message_str.replace("/echo", "").strip()
    
    if user_input:
        await event.plain_result(f"你输入了: {user_input}")
    else:
        await event.plain_result("请输入要回显的内容，格式: /echo <内容>")
```

## 下一步

学习了基本的插件结构后，你可以：
- [深入理解消息处理](03-listen-message-event.md)
- [学习发送各种类型的消息](04-send-message.md)
- [为插件添加配置选项](05-plugin-config.md)