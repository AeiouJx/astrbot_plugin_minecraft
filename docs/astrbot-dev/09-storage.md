# 插件存储

本节介绍 AstrBot 插件的存储机制，包括简单的 KV 存储和大文件存储。

## 简单 KV 存储

### 基本操作

#### 存储数据

```python
from astrbot.api.star import Context

class StoragePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    async def save_data(self, key: str, value: str):
        """存储数据"""
        await self.context.put_kv_data(key, value)
        
    async def save_user_setting(self, user_id: str, setting: dict):
        """存储用户设置"""
        import json
        key = f"user_{user_id}_settings"
        value = json.dumps(setting)
        await self.context.put_kv_data(key, value)
```

#### 获取数据

```python
async def get_data(self, key: str, default: str = "") -> str:
    """获取数据"""
    value = await self.context.get_kv_data(key)
    return value if value else default
    
async def get_user_setting(self, user_id: str) -> dict:
    """获取用户设置"""
    import json
    key = f"user_{user_id}_settings"
    value = await self.context.get_kv_data(key)
    return json.loads(value) if value else {}
```

#### 删除数据

```python
async def delete_data(self, key: str):
    """删除数据"""
    await self.context.delete_kv_data(key)
    
async def delete_user_setting(self, user_id: str):
    """删除用户设置"""
    key = f"user_{user_id}_settings"
    await self.context.delete_kv_data(key)
```

### 使用示例

```python
@filter.command("set_name")
async def on_set_name(self, event: AstrMessageEvent):
    """设置用户名"""
    args = event.message_str.split()[1:]
    if not args:
        await event.plain_result("用法: /set_name <名称>")
        return
        
    name = " ".join(args)
    user_id = event.sender.id
    
    # 存储用户名
    await self.save_user_setting(user_id, {"name": name})
    await event.plain_result(f"用户名已设置为: {name}")
    
@filter.command("get_name")
async def on_get_name(self, event: AstrMessageEvent):
    """获取用户名"""
    user_id = event.sender.id
    
    # 获取用户名
    settings = await self.get_user_setting(user_id)
    name = settings.get("name", "未设置")
    await event.plain_result(f"你的用户名: {name}")
    
@filter.command("clear_name")
async def on_clear_name(self, event: AstrMessageEvent):
    """清除用户名"""
    user_id = event.sender.id
    
    # 删除用户名
    await self.delete_user_setting(user_id)
    await event.plain_result("用户名已清除")
```

### 批量操作

```python
async def batch_save(self, data: dict):
    """批量存储数据"""
    for key, value in data.items():
        await self.context.put_kv_data(key, value)
        
async def batch_get(self, keys: list) -> dict:
    """批量获取数据"""
    result = {}
    for key in keys:
        value = await self.context.get_kv_data(key)
        result[key] = value
    return result
    
async def batch_delete(self, keys: list):
    """批量删除数据"""
    for key in keys:
        await self.context.delete_kv_data(key)
```

### 数据过期

```python
import time

async def save_with_expiry(self, key: str, value: str, expiry_seconds: int):
    """存储带过期时间的数据"""
    data = {
        "value": value,
        "expiry": time.time() + expiry_seconds
    }
    import json
    await self.context.put_kv_data(key, json.dumps(data))
    
async def get_with_expiry(self, key: str):
    """获取带过期时间的数据"""
    import json
    data = await self.context.get_kv_data(key)
    if not data:
        return None
        
    data = json.loads(data)
    if time.time() > data["expiry"]:
        # 数据已过期，删除它
        await self.context.delete_kv_data(key)
        return None
        
    return data["value"]
```

## 大文件存储

### 存储目录结构

```
data/
└── plugin_data/
    └── my_plugin/
        ├── files/
        ├── images/
        └── cache/
```

### 保存文件

```python
import os
import aiofiles

class FileStoragePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_dir = os.path.join(context.data_dir, "plugin_data", "my_plugin")
        os.makedirs(self.data_dir, exist_ok=True)
        
    async def save_file(self, filename: str, content: bytes):
        """保存文件"""
        file_path = os.path.join(self.data_dir, filename)
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        return file_path
        
    async def save_text_file(self, filename: str, content: str):
        """保存文本文件"""
        file_path = os.path.join(self.data_dir, filename)
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(content)
        return file_path
```

### 读取文件

```python
async def read_file(self, filename: str) -> bytes:
    """读取文件"""
    file_path = os.path.join(self.data_dir, filename)
    if not os.path.exists(file_path):
        return None
        
    async with aiofiles.open(file_path, 'rb') as f:
        return await f.read()
        
async def read_text_file(self, filename: str) -> str:
    """读取文本文件"""
    file_path = os.path.join(self.data_dir, filename)
    if not os.path.exists(file_path):
        return None
        
    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
        return await f.read()
```

### 删除文件

```python
async def delete_file(self, filename: str):
    """删除文件"""
    file_path = os.path.join(self.data_dir, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        
async def delete_directory(self, dir_path: str):
    """删除目录"""
    full_path = os.path.join(self.data_dir, dir_path)
    if os.path.exists(full_path):
        import shutil
        shutil.rmtree(full_path)
```

### 文件操作示例

```python
@filter.command("upload_file")
async def on_upload_file(self, event: AstrMessageEvent):
    """上传文件示例"""
    # 这里假设用户上传了文件
    # 实际实现需要根据平台适配器处理
    await event.plain_result("文件上传功能需要平台支持")
    
@filter.command("save_note")
async def on_save_note(self, event: AstrMessageEvent):
    """保存笔记"""
    args = event.message_str.split()[1:]
    if len(args) < 2:
        await event.plain_result("用法: /save_note <文件名> <内容>")
        return
        
    filename = args[0]
    content = " ".join(args[1:])
    
    # 保存笔记
    file_path = await self.save_text_file(f"notes/{filename}.txt", content)
    await event.plain_result(f"笔记已保存: {filename}")
    
@filter.command("read_note")
async def on_read_note(self, event: AstrMessageEvent):
    """读取笔记"""
    args = event.message_str.split()[1:]
    if not args:
        await event.plain_result("用法: /read_note <文件名>")
        return
        
    filename = args[0]
    
    # 读取笔记
    content = await self.read_text_file(f"notes/{filename}.txt")
    if content:
        await event.plain_result(f"笔记内容:\n{content}")
    else:
        await event.plain_result(f"未找到笔记: {filename}")
        
@filter.command("list_notes")
async def on_list_notes(self, event: AstrMessageEvent):
    """列出所有笔记"""
    notes_dir = os.path.join(self.data_dir, "notes")
    if not os.path.exists(notes_dir):
        await event.plain_result("暂无笔记")
        return
        
    notes = []
    for filename in os.listdir(notes_dir):
        if filename.endswith(".txt"):
            notes.append(filename[:-4])  # 移除 .txt 后缀
            
    if notes:
        notes_text = "\n".join(f"- {note}" for note in notes)
        await event.plain_result(f"笔记列表:\n{notes_text}")
    else:
        await event.plain_result("暂无笔记")
```

## 缓存实现

### 内存缓存

```python
import time
from collections import OrderedDict

class MemoryCache:
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl
        
    def get(self, key: str):
        """获取缓存"""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                # 移动到末尾（最近使用）
                self.cache.move_to_end(key)
                return value
            else:
                # 已过期，删除
                del self.cache[key]
        return None
        
    def set(self, key: str, value):
        """设置缓存"""
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = (value, time.time())
        
        # 检查大小限制
        while len(self.cache) > self.max_size:
            self.cache.popitem(last=False)
            
    def delete(self, key: str):
        """删除缓存"""
        if key in self.cache:
            del self.cache[key]
            
    def clear(self):
        """清空缓存"""
        self.cache.clear()
```

### 使用缓存

```python
class CachedPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.cache = MemoryCache(max_size=500, ttl=600)
        
    async def get_cached_data(self, key: str):
        """获取缓存数据"""
        # 先从缓存获取
        cached = self.cache.get(key)
        if cached:
            return cached
            
        # 缓存未命中，从存储获取
        data = await self.context.get_kv_data(key)
        if data:
            # 存入缓存
            self.cache.set(key, data)
            
        return data
        
    async def set_cached_data(self, key: str, value: str):
        """设置缓存数据"""
        # 存入存储
        await self.context.put_kv_data(key, value)
        # 存入缓存
        self.cache.set(key, value)
```

## 完整存储示例

```python
from astrbot.api.star import Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.star import Star
import os
import json
import time

class DataStoragePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data_dir = os.path.join(context.data_dir, "plugin_data", "data_storage")
        os.makedirs(self.data_dir, exist_ok=True)
        
    @filter.command("save_data")
    async def on_save_data(self, event: AstrMessageEvent):
        """保存数据"""
        args = event.message_str.split()[1:]
        if len(args) < 2:
            await event.plain_result("用法: /save_data <键> <值>")
            return
            
        key = args[0]
        value = " ".join(args[1:])
        
        # 存储数据
        await self.context.put_kv_data(key, value)
        await event.plain_result(f"数据已保存: {key} = {value}")
        
    @filter.command("get_data")
    async def on_get_data(self, event: AstrMessageEvent):
        """获取数据"""
        args = event.message_str.split()[1:]
        if not args:
            await event.plain_result("用法: /get_data <键>")
            return
            
        key = args[0]
        
        # 获取数据
        value = await self.context.get_kv_data(key)
        if value:
            await event.plain_result(f"{key} = {value}")
        else:
            await event.plain_result(f"未找到数据: {key}")
            
    @filter.command("delete_data")
    async def on_delete_data(self, event: AstrMessageEvent):
        """删除数据"""
        args = event.message_str.split()[1:]
        if not args:
            await event.plain_result("用法: /delete_data <键>")
            return
            
        key = args[0]
        
        # 删除数据
        await self.context.delete_kv_data(key)
        await event.plain_result(f"数据已删除: {key}")
        
    @filter.command("save_file")
    async def on_save_file(self, event: AstrMessageEvent):
        """保存文件"""
        args = event.message_str.split()[1:]
        if len(args) < 2:
            await event.plain_result("用法: /save_file <文件名> <内容>")
            return
            
        filename = args[0]
        content = " ".join(args[1:])
        
        # 保存文件
        file_path = os.path.join(self.data_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        await event.plain_result(f"文件已保存: {filename}")
        
    @filter.command("read_file")
    async def on_read_file(self, event: AstrMessageEvent):
        """读取文件"""
        args = event.message_str.split()[1:]
        if not args:
            await event.plain_result("用法: /read_file <文件名>")
            return
            
        filename = args[0]
        
        # 读取文件
        file_path = os.path.join(self.data_dir, filename)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            await event.plain_result(f"文件内容:\n{content}")
        else:
            await event.plain_result(f"未找到文件: {filename}")
            
    @filter.command("list_files")
    async def on_list_files(self, event: AstrMessageEvent):
        """列出文件"""
        if os.path.exists(self.data_dir):
            files = os.listdir(self.data_dir)
            if files:
                files_text = "\n".join(f"- {file}" for file in files)
                await event.plain_result(f"文件列表:\n{files_text}")
            else:
                await event.plain_result("暂无文件")
        else:
            await event.plain_result("数据目录不存在")
```

## 下一步

掌握了存储机制后，你可以：
- [实现文本转图片](10-html-to-pic.md)
- [实现实验控制](11-session-control.md)
- [实现其他功能](12-other.md)