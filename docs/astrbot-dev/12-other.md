# 杂项

本节介绍 AstrBot 插件开发中的一些其他功能，包括获取平台实例、调用 QQ 协议 API、获取已加载插件和平台。

## 获取平台实例

### 获取所有平台

```python
from astrbot.api.star import Context

class PlatformPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    async def get_all_platforms(self):
        """获取所有已加载的平台"""
        platforms = await self.context.get_platforms()
        return platforms
        
    async def get_platform_info(self):
        """获取平台信息"""
        platforms = await self.context.get_platforms()
        platform_info = []
        
        for platform in platforms:
            info = {
                "id": platform.platform_id,
                "type": platform.platform_type,
                "name": platform.platform_name,
                "status": platform.status
            }
            platform_info.append(info)
            
        return platform_info
```

### 获取指定平台

```python
async def get_platform_by_id(self, platform_id: str):
    """根据 ID 获取平台"""
    platforms = await self.context.get_platforms()
    
    for platform in platforms:
        if platform.platform_id == platform_id:
            return platform
            
    return None
    
async def get_platform_by_type(self, platform_type: str):
    """根据类型获取平台"""
    platforms = await self.context.get_platforms()
    
    for platform in platforms:
        if platform.platform_type == platform_type:
            return platform
            
    return None
```

### 平台操作

```python
@filter.command("platform_list")
async def on_platform_list(self, event: AstrMessageEvent):
    """列出所有平台"""
    platforms = await self.context.get_platforms()
    
    if not platforms:
        await event.plain_result("没有已加载的平台")
        return
        
    platform_text = "已加载的平台:\n"
    for platform in platforms:
        status = "在线" if platform.status == "online" else "离线"
        platform_text += f"- {platform.platform_name} ({platform.platform_type}) - {status}\n"
        
    await event.plain_result(platform_text)
    
@filter.command("platform_info")
async def on_platform_info(self, event: AstrMessageEvent):
    """获取平台详细信息"""
    args = event.message_str.split()[1:]
    if not args:
        await event.plain_result("用法: /platform_info <平台ID>")
        return
        
    platform_id = args[0]
    platform = await self.get_platform_by_id(platform_id)
    
    if platform:
        info = f"""
        平台信息:
        - ID: {platform.platform_id}
        - 类型: {platform.platform_type}
        - 名称: {platform.platform_name}
        - 状态: {platform.status}
        - 连接时间: {platform.connected_at}
        """
        await event.plain_result(info)
    else:
        await event.plain_result(f"未找到平台: {platform_id}")
```

## 调用 QQ 协议 API

### 基本 API 调用

```python
class QQAPIPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    async def call_qq_api(self, api_name: str, params: dict):
        """调用 QQ 协议 API"""
        # 获取 QQ 平台实例
        qq_platform = await self.context.get_platform_by_type("qq")
        
        if not qq_platform:
            return {"error": "QQ 平台未加载"}
            
        # 调用 API
        try:
            result = await qq_platform.call_api(api_name, params)
            return result
        except Exception as e:
            return {"error": str(e)}
```

### 获取群信息

```python
async def get_group_info(self, group_id: str):
    """获取群信息"""
    params = {"group_id": group_id}
    result = await self.call_qq_api("get_group_info", params)
    return result
    
async def get_group_member_list(self, group_id: str):
    """获取群成员列表"""
    params = {"group_id": group_id}
    result = await self.call_qq_api("get_group_member_list", params)
    return result
```

### 获取用户信息

```python
async def get_user_info(self, user_id: str):
    """获取用户信息"""
    params = {"user_id": user_id}
    result = await self.call_qq_api("get_user_info", params)
    return result
    
async def get_friend_list(self):
    """获取好友列表"""
    result = await self.call_qq_api("get_friend_list", {})
    return result
```

### 发送消息

```python
async def send_group_message(self, group_id: str, message: str):
    """发送群消息"""
    params = {
        "group_id": group_id,
        "message": message
    }
    result = await self.call_qq_api("send_group_msg", params)
    return result
    
async def send_private_message(self, user_id: str, message: str):
    """发送私聊消息"""
    params = {
        "user_id": user_id,
        "message": message
    }
    result = await self.call_qq_api("send_private_msg", params)
    return result
```

### 使用示例

```python
@filter.command("qq_group_info")
async def on_qq_group_info(self, event: AstrMessageEvent):
    """获取 QQ 群信息"""
    args = event.message_str.split()[1:]
    if not args:
        await event.plain_result("用法: /qq_group_info <群号>")
        return
        
    group_id = args[0]
    
    try:
        group_info = await self.get_group_info(group_id)
        if "error" in group_info:
            await event.plain_result(f"获取失败: {group_info['error']}")
        else:
            info = f"""
            群信息:
            - 群号: {group_info.get('group_id')}
            - 群名: {group_info.get('group_name')}
            - 成员数: {group_info.get('member_count')}
            """
            await event.plain_result(info)
    except Exception as e:
        await event.plain_result(f"获取群信息失败: {str(e)}")
        
@filter.command("qq_send")
async def on_qq_send(self, event: AstrMessageEvent):
    """发送 QQ 消息"""
    args = event.message_str.split()[1:]
    if len(args) < 2:
        await event.plain_result("用法: /qq_send <目标ID> <消息>")
        return
        
    target_id = args[0]
    message = " ".join(args[1:])
    
    try:
        # 判断是群号还是用户号
        if len(target_id) > 10:  # 简单的判断逻辑
            result = await self.send_group_message(target_id, message)
        else:
            result = await self.send_private_message(target_id, message)
            
        if "error" in result:
            await event.plain_result(f"发送失败: {result['error']}")
        else:
            await event.plain_result("消息已发送")
    except Exception as e:
        await event.plain_result(f"发送消息失败: {str(e)}")
```

## 获取已加载插件

### 基本获取

```python
class PluginManagerPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    async def get_loaded_plugins(self):
        """获取已加载的插件"""
        plugins = await self.context.get_plugins()
        return plugins
        
    async def get_plugin_info(self):
        """获取插件信息"""
        plugins = await self.context.get_plugins()
        plugin_info = []
        
        for plugin in plugins:
            info = {
                "name": plugin.name,
                "version": plugin.version,
                "author": plugin.author,
                "description": plugin.description,
                "status": plugin.status
            }
            plugin_info.append(info)
            
        return plugin_info
```

### 插件操作

```python
@filter.command("plugin_list")
async def on_plugin_list(self, event: AstrMessageEvent):
    """列出所有插件"""
    plugins = await self.context.get_plugins()
    
    if not plugins:
        await event.plain_result("没有已加载的插件")
        return
        
    plugin_text = "已加载的插件:\n"
    for plugin in plugins:
        status = "启用" if plugin.status == "enabled" else "禁用"
        plugin_text += f"- {plugin.name} v{plugin.version} - {status}\n"
        
    await event.plain_result(plugin_text)
    
@filter.command("plugin_info")
async def on_plugin_info(self, event: AstrMessageEvent):
    """获取插件详细信息"""
    args = event.message_str.split()[1:]
    if not args:
        await event.plain_result("用法: /plugin_info <插件名>")
        return
        
    plugin_name = args[0]
    plugins = await self.context.get_plugins()
    
    for plugin in plugins:
        if plugin.name == plugin_name:
            info = f"""
            插件信息:
            - 名称: {plugin.name}
            - 版本: {plugin.version}
            - 作者: {plugin.author}
            - 描述: {plugin.description}
            - 状态: {plugin.status}
            - 加载时间: {plugin.loaded_at}
            """
            await event.plain_result(info)
            return
            
    await event.plain_result(f"未找到插件: {plugin_name}")
```

## 获取已加载平台

### 平台管理

```python
@filter.command("platform_status")
async def on_platform_status(self, event: AstrMessageEvent):
    """获取平台状态"""
    platforms = await self.context.get_platforms()
    
    if not platforms:
        await event.plain_result("没有已加载的平台")
        return
        
    status_text = "平台状态:\n"
    for platform in platforms:
        status_emoji = "🟢" if platform.status == "online" else "🔴"
        status_text += f"{status_emoji} {platform.platform_name} ({platform.platform_type})\n"
        
    await event.plain_result(status_text)
    
@filter.command("platform_detail")
async def on_platform_detail(self, event: AstrMessageEvent):
    """获取平台详细信息"""
    platforms = await self.context.get_platforms()
    
    if not platforms:
        await event.plain_result("没有已加载的平台")
        return
        
    detail_text = "平台详细信息:\n\n"
    for platform in platforms:
        detail_text += f"平台: {platform.platform_name}\n"
        detail_text += f"- ID: {platform.platform_id}\n"
        detail_text += f"- 类型: {platform.platform_type}\n"
        detail_text += f"- 状态: {platform.status}\n"
        detail_text += f"- 连接时间: {platform.connected_at}\n"
        detail_text += "\n"
        
    await event.plain_result(detail_text)
```

## 其他实用功能

### 获取系统信息

```python
@filter.command("sysinfo")
async def on_sysinfo(self, event: AstrMessageEvent):
    """获取系统信息"""
    import platform
    import psutil
    
    info = f"""
    系统信息:
    - 操作系统: {platform.system()} {platform.release()}
    - Python 版本: {platform.python_version()}
    - CPU 使用率: {psutil.cpu_percent()}%
    - 内存使用率: {psutil.virtual_memory().percent}%
    - 磁盘使用率: {psutil.disk_usage('/').percent}%
    """
    await event.plain_result(info)
```

### 获取 AstrBot 版本

```python
@filter.command("version")
async def on_version(self, event: AstrMessageEvent):
    """获取 AstrBot 版本"""
    version = await self.context.get_version()
    await event.plain_result(f"AstrBot 版本: {version}")
```

### 获取配置信息

```python
@filter.command("config_info")
async def on_config_info(self, event: AstrMessageEvent):
    """获取配置信息"""
    config = await self.context.get_config()
    
    # 过滤敏感信息
    safe_config = {}
    for key, value in config.items():
        if "secret" in key.lower() or "key" in key.lower() or "password" in key.lower():
            safe_config[key] = "******"
        else:
            safe_config[key] = value
            
    import json
    config_text = json.dumps(safe_config, indent=2, ensure_ascii=False)
    await event.plain_result(f"配置信息:\n{config_text}")
```

### 日志操作

```python
@filter.command("log")
async def on_log(self, event: AstrMessageEvent):
    """记录日志"""
    args = event.message_str.split()[1:]
    if not args:
        await event.plain_result("用法: /log <消息>")
        return
        
    message = " ".join(args)
    
    # 记录不同级别的日志
    self.context.logger.debug(f"调试日志: {message}")
    self.context.logger.info(f"信息日志: {message}")
    self.context.logger.warning(f"警告日志: {message}")
    self.context.logger.error(f"错误日志: {message}")
    
    await event.plain_result("日志已记录")
```

## 完整杂项示例

```python
from astrbot.api.star import Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.star import Star
import platform
import psutil
import json

class MiscellaneousPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    @filter.command("help_misc")
    async def on_help_misc(self, event: AstrMessageEvent):
        """显示杂项功能帮助"""
        help_text = """
        杂项功能命令:
        
        /platform_list - 列出所有平台
        /platform_info <平台ID> - 获取平台信息
        /plugin_list - 列出所有插件
        /plugin_info <插件名> - 获取插件信息
        /sysinfo - 获取系统信息
        /version - 获取 AstrBot 版本
        /config_info - 获取配置信息
        /log <消息> - 记录日志
        """
        await event.plain_result(help_text)
        
    @filter.command("platform_list")
    async def on_platform_list(self, event: AstrMessageEvent):
        """列出所有平台"""
        platforms = await self.context.get_platforms()
        
        if not platforms:
            await event.plain_result("没有已加载的平台")
            return
            
        platform_text = "已加载的平台:\n"
        for platform in platforms:
            status = "在线" if platform.status == "online" else "离线"
            platform_text += f"- {platform.platform_name} ({platform.platform_type}) - {status}\n"
            
        await event.plain_result(platform_text)
        
    @filter.command("plugin_list")
    async def on_plugin_list(self, event: AstrMessageEvent):
        """列出所有插件"""
        plugins = await self.context.get_plugins()
        
        if not plugins:
            await event.plain_result("没有已加载的插件")
            return
            
        plugin_text = "已加载的插件:\n"
        for plugin in plugins:
            status = "启用" if plugin.status == "enabled" else "禁用"
            plugin_text += f"- {plugin.name} v{plugin.version} - {status}\n"
            
        await event.plain_result(plugin_text)
        
    @filter.command("sysinfo")
    async def on_sysinfo(self, event: AstrMessageEvent):
        """获取系统信息"""
        info = f"""
        系统信息:
        - 操作系统: {platform.system()} {platform.release()}
        - Python 版本: {platform.python_version()}
        - CPU 使用率: {psutil.cpu_percent()}%
        - 内存使用率: {psutil.virtual_memory().percent}%
        - 磁盘使用率: {psutil.disk_usage('/').percent}%
        """
        await event.plain_result(info)
        
    @filter.command("version")
    async def on_version(self, event: AstrMessageEvent):
        """获取 AstrBot 版本"""
        version = await self.context.get_version()
        await event.plain_result(f"AstrBot 版本: {version}")
        
    @filter.command("config_info")
    async def on_config_info(self, event: AstrMessageEvent):
        """获取配置信息"""
        config = await self.context.get_config()
        
        # 过滤敏感信息
        safe_config = {}
        for key, value in config.items():
            if "secret" in key.lower() or "key" in key.lower() or "password" in key.lower():
                safe_config[key] = "******"
            else:
                safe_config[key] = value
                
        config_text = json.dumps(safe_config, indent=2, ensure_ascii=False)
        await event.plain_result(f"配置信息:\n{config_text}")
        
    @filter.command("log")
    async def on_log(self, event: AstrMessageEvent):
        """记录日志"""
        args = event.message_str.split()[1:]
        if not args:
            await event.plain_result("用法: /log <消息>")
            return
            
        message = " ".join(args)
        
        # 记录不同级别的日志
        self.context.logger.debug(f"调试日志: {message}")
        self.context.logger.info(f"信息日志: {message}")
        self.context.logger.warning(f"警告日志: {message}")
        self.context.logger.error(f"错误日志: {message}")
        
        await event.plain_result("日志已记录")
```

## 下一步

掌握了这些杂项功能后，你可以：
- [发布插件到市场](13-plugin-publish.md)
- [接入平台适配器](14-platform-adapter.md)
- [查看完整开发指南](01-plugin-new.md)