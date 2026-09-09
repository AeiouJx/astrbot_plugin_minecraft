# 消息的发送

本节介绍 AstrBot 插件中如何发送各种类型的消息，包括被动消息、主动消息和富媒体消息。

## 被动消息

被动消息是对用户消息的直接响应，使用 `event.plain_result()` 方法。

### 发送纯文本

```python
@filter.command("hello")
async def on_hello(self, event: AstrMessageEvent):
    """发送纯文本消息"""
    await event.plain_result("你好！这是一条纯文本消息。")
```

### 发送多行文本

```python
@filter.command("info")
async def on_info(self, event: AstrMessageEvent):
    """发送多行文本"""
    info_text = """
    插件信息:
    - 名称: 示例插件
    - 版本: 1.0.0
    - 作者: 开发者
    """
    await event.plain_result(info_text)
```

### 使用消息链

```python
from astrbot.api.messagecomponent import MessageChain, PlainText

@filter.command("chain")
async def on_chain(self, event: AstrMessageEvent):
    """使用消息链发送消息"""
    chain = MessageChain()
    chain.add(PlainText("这是第一部分"))
    chain.add(PlainText("\n这是第二部分"))
    await event.plain_result(chain)
```

## 主动消息

主动消息是插件主动发送的消息，使用 `context.send_message()` 方法。

### 基本主动消息

```python
@filter.command("broadcast")
async def on_broadcast(self, event: AstrMessageEvent):
    """主动发送广播消息"""
    # 获取当前会话信息
    session_id = event.session_id
    
    # 主动发送消息
    await self.context.send_message(
        session_id=session_id,
        message="这是一条主动发送的广播消息"
    )
```

### 向指定会话发送消息

```python
async def send_to_specific_session(self, session_id: str, message: str):
    """向指定会话发送消息"""
    await self.context.send_message(
        session_id=session_id,
        message=message
    )
```

### 定时发送消息

```python
import asyncio
from datetime import datetime

class ScheduledMessagePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.scheduled_tasks = {}
        
    @filter.command("schedule")
    async def on_schedule(self, event: AstrMessageEvent):
        """设置定时消息"""
        # 解析时间参数
        args = event.message_str.split()[1:]
        if len(args) < 2:
            await event.plain_result("用法: /schedule <分钟数> <消息>")
            return
            
        try:
            minutes = int(args[0])
            message = " ".join(args[1:])
            
            # 创建定时任务
            task = asyncio.create_task(
                self.send_scheduled_message(event.session_id, message, minutes)
            )
            self.scheduled_tasks[event.session_id] = task
            
            await event.plain_result(f"已设置 {minutes} 分钟后发送消息")
        except ValueError:
            await event.plain_result("无效的时间参数")
            
    async def send_scheduled_message(self, session_id: str, message: str, minutes: int):
        """发送定时消息"""
        await asyncio.sleep(minutes * 60)
        await self.context.send_message(session_id=session_id, message=message)
```

## 富媒体消息

### 图片消息

```python
from astrbot.api.messagecomponent import Image

@filter.command("send_image")
async def on_send_image(self, event: AstrMessageEvent):
    """发送图片消息"""
    # 方式1: 使用 URL
    image = Image.fromURL("https://example.com/image.jpg")
    await event.plain_result(image)
    
    # 方式2: 使用本地文件
    image = Image.fromFile("/path/to/local/image.jpg")
    await event.plain_result(image)
    
    # 方式3: 使用 base64
    image = Image.fromBase64("data:image/jpeg;base64,/9j/4AAQ...")
    await event.plain_result(image)
```

### 语音消息

```python
from astrbot.api.messagecomponent import Record

@filter.command("send_voice")
async def on_send_voice(self, event: AstrMessageEvent):
    """发送语音消息"""
    # 使用 URL
    voice = Record.fromURL("https://example.com/voice.mp3")
    await event.plain_result(voice)
    
    # 使用本地文件
    voice = Record.fromFile("/path/to/local/voice.mp3")
    await event.plain_result(voice)
```

### 视频消息

```python
from astrbot.api.messagecomponent import Video

@filter.command("send_video")
async def on_send_video(self, event: AstrMessageEvent):
    """发送视频消息"""
    # 使用 URL
    video = Video.fromURL("https://example.com/video.mp4")
    await event.plain_result(video)
    
    # 使用本地文件
    video = Video.fromFile("/path/to/local/video.mp4")
    await event.plain_result(video)
```

### 文件消息

```python
from astrbot.api.messagecomponent import File

@filter.command("send_file")
async def on_send_file(self, event: AstrMessageEvent):
    """发送文件消息"""
    # 使用 URL
    file = File.fromURL("https://example.com/document.pdf", name="文档.pdf")
    await event.plain_result(file)
    
    # 使用本地文件
    file = File.fromFile("/path/to/local/document.pdf", name="文档.pdf")
    await event.plain_result(file)
```

### 节点消息（合并转发）

```python
from astrbot.api.messagecomponent import Node, PlainText

@filter.command("send_node")
async def on_send_node(self, event: AstrMessageEvent):
    """发送节点消息（合并转发）"""
    node = Node(
        name="机器人",
        uid="bot_123",
        content=MessageChain([PlainText("这是节点消息内容")])
    )
    await event.plain_result(node)
```

## 组合消息

### 混合文本和图片

```python
from astrbot.api.messagecomponent import MessageChain, PlainText, Image

@filter.command("mixed")
async def on_mixed(self, event: AstrMessageEvent):
    """发送混合消息"""
    chain = MessageChain()
    chain.add(PlainText("这是文本部分\n"))
    chain.add(Image.fromURL("https://example.com/image.jpg"))
    chain.add(PlainText("\n这是另一段文本"))
    await event.plain_result(chain)
```

### 多图消息

```python
@filter.command("multi_image")
async def on_multi_image(self, event: AstrMessageEvent):
    """发送多图消息"""
    chain = MessageChain()
    chain.add(Image.fromURL("https://example.com/image1.jpg"))
    chain.add(PlainText("\n"))
    chain.add(Image.fromURL("https://example.com/image2.jpg"))
    chain.add(PlainText("\n"))
    chain.add(Image.fromURL("https://example.com/image3.jpg"))
    await event.plain_result(chain)
```

## 错误处理

### 发送失败处理

```python
@filter.command("safe_send")
async def on_safe_send(self, event: AstrMessageEvent):
    """安全发送消息"""
    try:
        await event.plain_result("发送的消息内容")
    except Exception as e:
        # 发送失败时的处理
        print(f"发送失败: {e}")
        # 尝试发送错误提示
        try:
            await event.plain_result("消息发送失败，请稍后重试")
        except:
            pass
```

### 带重试机制

```python
import asyncio

async def send_with_retry(self, session_id: str, message: str, max_retries: int = 3):
    """带重试机制的消息发送"""
    for attempt in range(max_retries):
        try:
            await self.context.send_message(session_id=session_id, message=message)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # 等待 1 秒后重试
            else:
                print(f"消息发送失败，已重试 {max_retries} 次: {e}")
                return False
```

## 性能优化

### 批量发送

```python
async def batch_send(self, session_ids: list, message: str):
    """批量发送消息"""
    tasks = []
    for session_id in session_ids:
        task = self.context.send_message(session_id=session_id, message=message)
        tasks.append(task)
    
    # 并发发送
    await asyncio.gather(*tasks, return_exceptions=True)
```

### 消息缓存

```python
from functools import lru_cache

class CachedMessagePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.message_cache = {}
        
    @lru_cache(maxsize=100)
    def get_cached_message(self, key: str):
        """获取缓存的消息"""
        return self.message_cache.get(key)
        
    def cache_message(self, key: str, message: str):
        """缓存消息"""
        self.message_cache[key] = message
```

## 完整示例

```python
from astrbot.api.star import Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.messagecomponent import MessageChain, PlainText, Image, Record
from astrbot.core.star.star import Star

class MessageSenderPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    @filter.command("hello")
    async def on_hello(self, event: AstrMessageEvent):
        """发送欢迎消息"""
        chain = MessageChain()
        chain.add(PlainText("欢迎使用消息发送示例！\n\n"))
        chain.add(PlainText("可用命令:\n"))
        chain.add(PlainText("/hello - 显示欢迎消息\n"))
        chain.add(PlainText("/image - 发送示例图片\n"))
        chain.add(PlainText("/voice - 发送示例语音\n"))
        chain.add(PlainText("/mixed - 发送混合消息"))
        await event.plain_result(chain)
        
    @filter.command("image")
    async def on_image(self, event: AstrMessageEvent):
        """发送示例图片"""
        image = Image.fromURL("https://picsum.photos/800/600")
        chain = MessageChain()
        chain.add(PlainText("这是一张示例图片:\n"))
        chain.add(image)
        await event.plain_result(chain)
        
    @filter.command("voice")
    async def on_voice(self, event: AstrMessageEvent):
        """发送示例语音"""
        voice = Record.fromURL("https://example.com/sample.mp3")
        await event.plain_result(voice)
        
    @filter.command("mixed")
    async def on_mixed(self, event: AstrMessageEvent):
        """发送混合消息"""
        chain = MessageChain()
        chain.add(PlainText("混合消息示例:\n"))
        chain.add(Image.fromURL("https://picsum.photos/400/300"))
        chain.add(PlainText("\n这是一段文本\n"))
        chain.add(Image.fromURL("https://picsum.photos/400/300"))
        await event.plain_result(chain)
```

## 下一步

掌握了消息发送技巧后，你可以：
- [配置插件选项](05-plugin-config.md)
- [开发插件页面](06-plugin-pages.md)
- [实现插件国际化](07-plugin-i18n.md)