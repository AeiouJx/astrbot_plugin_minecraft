# 接入平台适配器

本节介绍如何为 AstrBot 开发平台适配器，包括适配器实现、事件处理和媒体处理。

## 适配器架构

### 基本结构

```
platform_adapter/
├── main.py              # 适配器主文件
├── metadata.yaml        # 适配器元数据
├── platform.py          # 平台实现
├── event.py             # 事件实现
└── utils.py             # 工具函数
```

### 核心组件

1. **Platform 类**: 平台适配器的核心类
2. **AstrMessageEvent 子类**: 事件处理类
3. **消息转换**: 平台消息与 AstrBot 消息的转换
4. **媒体处理**: 图片、语音、视频等媒体的处理

## FakePlatform 示例

### 平台实现

```python
from astrbot.api.platform import Platform, AstrBotEvent
from astrbot.api.messagecomponent import MessageChain, PlainText, Image
import asyncio
import json

class FakePlatform(Platform):
    """虚拟平台适配器示例"""
    
    def __init__(self, context):
        super().__init__(context)
        self.platform_id = "fake"
        self.platform_name = "虚拟平台"
        self.platform_type = "fake"
        self.status = "offline"
        self.message_queue = asyncio.Queue()
        
    async def run(self):
        """运行平台"""
        self.status = "online"
        self.context.logger.info("虚拟平台已启动")
        
        # 模拟接收消息
        while True:
            try:
                # 从队列获取消息
                message_data = await self.message_queue.get()
                
                # 处理消息
                await self.handle_msg(message_data)
                
            except Exception as e:
                self.context.logger.error(f"处理消息失败: {e}")
                
    async def stop(self):
        """停止平台"""
        self.status = "offline"
        self.context.logger.info("虚拟平台已停止")
        
    async def send_by_session(self, session_id: str, message: MessageChain):
        """发送消息"""
        # 转换为平台格式
        platform_message = await self.convert_to_platform_message(message)
        
        # 模拟发送
        self.context.logger.info(f"发送消息到 {session_id}: {platform_message}")
        
        # 这里可以实现实际的发送逻辑
        # 例如: await self.send_to_websocket(session_id, platform_message)
        
    async def convert_message(self, message: dict) -> AstrBotEvent:
        """转换平台消息为 AstrBot 事件"""
        # 解析消息数据
        user_id = message.get("user_id", "")
        group_id = message.get("group_id", "")
        content = message.get("content", "")
        message_type = message.get("message_type", "private")
        
        # 创建事件
        event = FakeMessageEvent(
            platform=self,
            message_id=message.get("message_id", ""),
            user_id=user_id,
            group_id=group_id,
            content=content,
            message_type=message_type,
            raw_message=message
        )
        
        return event
        
    async def handle_msg(self, message_data: dict):
        """处理接收到的消息"""
        # 转换消息
        event = await self.convert_message(message_data)
        
        # 提交事件到 AstrBot
        await self.commit_event(event)
        
    async def convert_to_platform_message(self, message: MessageChain):
        """将 AstrBot 消息转换为平台格式"""
        platform_message = []
        
        for component in message:
            if isinstance(component, PlainText):
                platform_message.append({
                    "type": "text",
                    "data": {"text": component.text}
                })
            elif isinstance(component, Image):
                if component.url:
                    platform_message.append({
                        "type": "image",
                        "data": {"url": component.url}
                    })
                elif component.file_path:
                    platform_message.append({
                        "type": "image",
                        "data": {"file": component.file_path}
                    })
                    
        return platform_message
        
    def get_meta(self):
        """获取平台元数据"""
        return {
            "platform_id": self.platform_id,
            "platform_name": self.platform_name,
            "platform_type": self.platform_type,
            "version": "1.0.0",
            "author": "developer",
            "description": "虚拟平台适配器示例"
        }
```

### 事件实现

```python
from astrbot.api.event import AstrMessageEvent
from astrbot.api.messagecomponent import MessageChain, PlainText, Image

class FakeMessageEvent(AstrMessageEvent):
    """虚拟平台消息事件"""
    
    def __init__(self, platform, message_id: str, user_id: str, 
                 group_id: str, content: str, message_type: str, 
                 raw_message: dict):
        super().__init__()
        self.platform = platform
        self.message_id = message_id
        self.user_id = user_id
        self.group_id = group_id
        self.content = content
        self.message_type = message_type
        self.raw_message = raw_message
        
        # 设置会话 ID
        if message_type == "group" and group_id:
            self.session_id = f"fake_group_{group_id}"
        else:
            self.session_id = f"fake_user_{user_id}"
        
        # 解析消息内容
        self.message = self.parse_message(content)
        self.message_str = content
        
    def parse_message(self, content: str) -> MessageChain:
        """解析消息内容"""
        chain = MessageChain()
        
        # 简单解析，实际应该根据平台格式解析
        if content.startswith("http"):
            # 可能是图片链接
            chain.add(Image.fromURL(content))
        else:
            chain.add(PlainText(content))
            
        return chain
        
    async def send(self, message: MessageChain):
        """发送消息"""
        await self.platform.send_by_session(self.session_id, message)
        
    async def plain_result(self, text: str):
        """发送纯文本结果"""
        message = MessageChain()
        message.add(PlainText(text))
        await self.send(message)
        
    async def image_result(self, image_url: str):
        """发送图片结果"""
        message = MessageChain()
        message.add(Image.fromURL(image_url))
        await self.send(message)
```

## 适配器实现

### register_platform_adapter

```python
from astrbot.api.platform import register_platform_adapter

@register_platform_adapter
def register():
    """注册平台适配器"""
    return {
        "platform_class": FakePlatform,
        "platform_id": "fake",
        "platform_name": "虚拟平台",
        "platform_type": "fake",
        "version": "1.0.0",
        "author": "developer",
        "description": "虚拟平台适配器示例"
    }
```

### Platform 类

```python
class CustomPlatform(Platform):
    """自定义平台适配器"""
    
    def __init__(self, context):
        super().__init__(context)
        self.platform_id = "custom"
        self.platform_name = "自定义平台"
        self.platform_type = "custom"
        
    async def run(self):
        """运行平台"""
        # 初始化平台连接
        await self.initialize_connection()
        
        # 启动消息接收循环
        await self.start_message_loop()
        
    async def initialize_connection(self):
        """初始化平台连接"""
        # 实现连接初始化逻辑
        pass
        
    async def start_message_loop(self):
        """启动消息接收循环"""
        # 实现消息接收逻辑
        pass
        
    async def send_by_session(self, session_id: str, message: MessageChain):
        """发送消息"""
        # 实现消息发送逻辑
        pass
        
    async def convert_message(self, message: dict) -> AstrBotEvent:
        """转换消息"""
        # 实现消息转换逻辑
        pass
        
    async def handle_msg(self, message_data: dict):
        """处理消息"""
        # 实现消息处理逻辑
        pass
```

### meta 方法

```python
def get_meta(self):
    """获取平台元数据"""
    return {
        "platform_id": self.platform_id,
        "platform_name": self.platform_name,
        "platform_type": self.platform_type,
        "version": self.version,
        "author": self.author,
        "description": self.description,
        "capabilities": [
            "text_message",
            "image_message",
            "voice_message",
            "video_message"
        ]
    }
```

### run 方法

```python
async def run(self):
    """运行平台"""
    try:
        # 初始化
        await self.initialize()
        
        # 设置状态
        self.status = "online"
        
        # 启动主循环
        await self.main_loop()
        
    except Exception as e:
        self.context.logger.error(f"平台运行失败: {e}")
        self.status = "error"
        
async def initialize(self):
    """初始化平台"""
    # 实现初始化逻辑
    pass
    
async def main_loop(self):
    """主循环"""
    while self.status == "online":
        try:
            # 处理消息
            await self.process_messages()
            
            # 等待一段时间
            await asyncio.sleep(0.1)
            
        except Exception as e:
            self.context.logger.error(f"处理消息失败: {e}")
```

### send_by_session 方法

```python
async def send_by_session(self, session_id: str, message: MessageChain):
    """发送消息"""
    try:
        # 转换消息格式
        platform_message = await self.convert_to_platform_message(message)
        
        # 发送消息
        await self.send_message(session_id, platform_message)
        
    except Exception as e:
        self.context.logger.error(f"发送消息失败: {e}")
        
async def send_message(self, session_id: str, message: dict):
    """发送消息到平台"""
    # 实现实际发送逻辑
    pass
```

### convert_message 方法

```python
async def convert_message(self, message: dict) -> AstrBotEvent:
    """转换平台消息为 AstrBot 事件"""
    # 提取消息信息
    user_id = message.get("user_id", "")
    group_id = message.get("group_id", "")
    content = message.get("content", "")
    message_type = message.get("message_type", "private")
    
    # 创建事件对象
    event = CustomMessageEvent(
        platform=self,
        message_id=message.get("message_id", ""),
        user_id=user_id,
        group_id=group_id,
        content=content,
        message_type=message_type,
        raw_message=message
    )
    
    return event
```

### handle_msg 方法

```python
async def handle_msg(self, message_data: dict):
    """处理接收到的消息"""
    # 转换消息
    event = await self.convert_message(message_data)
    
    # 提交事件
    await self.commit_event(event)
    
async def commit_event(self, event: AstrBotEvent):
    """提交事件到 AstrBot"""
    # 这里应该调用 AstrBot 的事件处理机制
    # 实际实现可能需要通过回调函数
    pass
```

## 事件实现

### AstrMessageEvent 子类

```python
class CustomMessageEvent(AstrMessageEvent):
    """自定义消息事件"""
    
    def __init__(self, platform, message_id: str, user_id: str,
                 group_id: str, content: str, message_type: str,
                 raw_message: dict):
        super().__init__()
        self.platform = platform
        self.message_id = message_id
        self.user_id = user_id
        self.group_id = group_id
        self.content = content
        self.message_type = message_type
        self.raw_message = raw_message
        
        # 设置会话 ID
        if message_type == "group" and group_id:
            self.session_id = f"custom_group_{group_id}"
        else:
            self.session_id = f"custom_user_{user_id}"
        
        # 解析消息
        self.message = self.parse_message(content)
        self.message_str = content
        
    def parse_message(self, content: str) -> MessageChain:
        """解析消息内容"""
        chain = MessageChain()
        
        # 根据平台格式解析消息
        # 这里只是简单示例
        chain.add(PlainText(content))
        
        return chain
```

### send 方法

```python
async def send(self, message: MessageChain):
    """发送消息"""
    await self.platform.send_by_session(self.session_id, message)
    
async def plain_result(self, text: str):
    """发送纯文本结果"""
    message = MessageChain()
    message.add(PlainText(text))
    await self.send(message)
    
async def image_result(self, image_url: str):
    """发送图片结果"""
    message = MessageChain()
    message.add(Image.fromURL(image_url))
    await self.send(message)
    
async def voice_result(self, voice_url: str):
    """发送语音结果"""
    message = MessageChain()
    message.add(Record.fromURL(voice_url))
    await self.send(message)
```

## 媒体处理

### component file/url 引用

```python
class MediaHandler:
    """媒体处理器"""
    
    def __init__(self, context):
        self.context = context
        
    async def handle_image(self, image_data: dict):
        """处理图片"""
        if "url" in image_data:
            # URL 引用
            return Image.fromURL(image_data["url"])
        elif "file" in image_data:
            # 本地文件引用
            return Image.fromFile(image_data["file"])
        elif "base64" in image_data:
            # Base64 数据
            return Image.fromBase64(image_data["base64"])
        else:
            raise ValueError("无效的图片数据")
            
    async def handle_voice(self, voice_data: dict):
        """处理语音"""
        if "url" in voice_data:
            return Record.fromURL(voice_data["url"])
        elif "file" in voice_data:
            return Record.fromFile(voice_data["file"])
        else:
            raise ValueError("无效的语音数据")
            
    async def handle_video(self, video_data: dict):
        """处理视频"""
        if "url" in video_data:
            return Video.fromURL(video_data["url"])
        elif "file" in video_data:
            return Video.fromFile(video_data["file"])
        else:
            raise ValueError("无效的视频数据")
```

### convert_to_file_path

```python
async def convert_to_file_path(self, url: str, filename: str = None):
    """将 URL 转换为本地文件路径"""
    import aiohttp
    import os
    import tempfile
    
    # 生成文件名
    if not filename:
        filename = os.path.basename(url)
        
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, filename)
    
    # 下载文件
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                with open(file_path, 'wb') as f:
                    f.write(await response.read())
            else:
                raise Exception(f"下载文件失败: {response.status}")
                
    return file_path
    
async def cleanup_temp_files(self):
    """清理临时文件"""
    import shutil
    import tempfile
    
    # 清理临时目录
    temp_dir = tempfile.gettempdir()
    for item in os.listdir(temp_dir):
        if item.startswith("astrbot_"):
            item_path = os.path.join(temp_dir, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
```

## 完整平台适配器示例

```python
from astrbot.api.platform import Platform, AstrBotEvent, register_platform_adapter
from astrbot.api.event import AstrMessageEvent
from astrbot.api.messagecomponent import MessageChain, PlainText, Image, Record
import asyncio
import aiohttp
import json

@register_platform_adapter
def register():
    """注册平台适配器"""
    return {
        "platform_class": WebSocketPlatform,
        "platform_id": "websocket",
        "platform_name": "WebSocket 平台",
        "platform_type": "websocket",
        "version": "1.0.0",
        "author": "developer",
        "description": "WebSocket 平台适配器示例"
    }

class WebSocketPlatform(Platform):
    """WebSocket 平台适配器"""
    
    def __init__(self, context):
        super().__init__(context)
        self.platform_id = "websocket"
        self.platform_name = "WebSocket 平台"
        self.platform_type = "websocket"
        self.websocket = None
        self.connected = False
        
    async def run(self):
        """运行平台"""
        try:
            # 连接 WebSocket 服务器
            await self.connect()
            
            # 启动消息接收循环
            await self.receive_messages()
            
        except Exception as e:
            self.context.logger.error(f"WebSocket 平台运行失败: {e}")
            
    async def connect(self):
        """连接 WebSocket 服务器"""
        # 获取配置
        config = self.context.get_config()
        server_url = config.get("server_url", "ws://localhost:8765")
        
        # 连接
        self.websocket = await aiohttp.ClientSession().ws_connect(server_url)
        self.connected = True
        
        self.context.logger.info(f"已连接到 WebSocket 服务器: {server_url}")
        
    async def receive_messages(self):
        """接收消息"""
        while self.connected:
            try:
                # 接收消息
                msg = await self.websocket.receive()
                
                if msg.type == aiohttp.WSMsgType.TEXT:
                    # 解析消息
                    message_data = json.loads(msg.data)
                    
                    # 处理消息
                    await self.handle_msg(message_data)
                    
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self.context.logger.error(f"WebSocket 错误: {self.websocket.exception()}")
                    break
                    
            except Exception as e:
                self.context.logger.error(f"接收消息失败: {e}")
                
    async def send_by_session(self, session_id: str, message: MessageChain):
        """发送消息"""
        try:
            # 转换消息
            platform_message = await self.convert_to_platform_message(message)
            
            # 发送
            await self.websocket.send_json(platform_message)
            
        except Exception as e:
            self.context.logger.error(f"发送消息失败: {e}")
            
    async def convert_to_platform_message(self, message: MessageChain):
        """转换消息格式"""
        platform_message = {
            "type": "message",
            "data": []
        }
        
        for component in message:
            if isinstance(component, PlainText):
                platform_message["data"].append({
                    "type": "text",
                    "data": {"text": component.text}
                })
            elif isinstance(component, Image):
                if component.url:
                    platform_message["data"].append({
                        "type": "image",
                        "data": {"url": component.url}
                    })
                    
        return platform_message
        
    async def convert_message(self, message: dict) -> AstrBotEvent:
        """转换消息"""
        return WebSocketMessageEvent(
            platform=self,
            message_id=message.get("id", ""),
            user_id=message.get("user_id", ""),
            group_id=message.get("group_id", ""),
            content=message.get("content", ""),
            message_type=message.get("type", "private"),
            raw_message=message
        )
        
    async def handle_msg(self, message_data: dict):
        """处理消息"""
        event = await self.convert_message(message_data)
        await self.commit_event(event)
        
    def get_meta(self):
        """获取元数据"""
        return {
            "platform_id": self.platform_id,
            "platform_name": self.platform_name,
            "platform_type": self.platform_type,
            "version": "1.0.0",
            "author": "developer",
            "description": "WebSocket 平台适配器"
        }

class WebSocketMessageEvent(AstrMessageEvent):
    """WebSocket 消息事件"""
    
    def __init__(self, platform, message_id: str, user_id: str,
                 group_id: str, content: str, message_type: str,
                 raw_message: dict):
        super().__init__()
        self.platform = platform
        self.message_id = message_id
        self.user_id = user_id
        self.group_id = group_id
        self.content = content
        self.message_type = message_type
        self.raw_message = raw_message
        
        # 设置会话 ID
        if message_type == "group" and group_id:
            self.session_id = f"websocket_group_{group_id}"
        else:
            self.session_id = f"websocket_user_{user_id}"
        
        # 解析消息
        self.message = self.parse_message(content)
        self.message_str = content
        
    def parse_message(self, content: str) -> MessageChain:
        """解析消息"""
        chain = MessageChain()
        chain.add(PlainText(content))
        return chain
        
    async def send(self, message: MessageChain):
        """发送消息"""
        await self.platform.send_by_session(self.session_id, message)
        
    async def plain_result(self, text: str):
        """发送纯文本"""
        message = MessageChain()
        message.add(PlainText(text))
        await self.send(message)
```

## 下一步

掌握了平台适配器开发后，你可以：
- [查看完整开发指南](01-plugin-new.md)
- [发布插件到市场](13-plugin-publish.md)
- [参与社区讨论](https://github.com/Soulter/AstrBot/discussions)