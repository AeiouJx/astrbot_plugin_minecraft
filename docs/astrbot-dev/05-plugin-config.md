# 插件配置

本节介绍如何为 AstrBot 插件添加配置选项，包括配置 schema 定义、配置类型、特殊字段和配置使用。

## 配置 Schema

### 基本结构

在插件目录中创建 `_conf_schema.json` 文件：

```json
{
  "api_key": {
    "description": "API 密钥",
    "type": "string",
    "required": true,
    "secret": true
  },
  "max_retries": {
    "description": "最大重试次数",
    "type": "int",
    "default": 3,
    "minimum": 1,
    "maximum": 10
  },
  "enable_logging": {
    "description": "启用日志",
    "type": "bool",
    "default": true
  }
}
```

## 配置类型

### 字符串类型

```json
{
  "username": {
    "description": "用户名",
    "type": "string",
    "default": "default_user"
  }
}
```

### 文本类型（多行）

```json
{
  "prompt_template": {
    "description": "提示词模板",
    "type": "text",
    "default": "你是一个助手，请回答用户的问题。"
  }
}
```

### 整数类型

```json
{
  "timeout": {
    "description": "超时时间（秒）",
    "type": "int",
    "default": 30,
    "minimum": 1,
    "maximum": 300
  }
}
```

### 浮点数类型

```json
{
  "temperature": {
    "description": "温度参数",
    "type": "float",
    "default": 0.7,
    "minimum": 0.0,
    "maximum": 2.0
  }
}
```

### 布尔类型

```json
{
  "enable_feature": {
    "description": "启用功能",
    "type": "bool",
    "default": false
  }
}
```

### 对象类型

```json
{
  "api_config": {
    "description": "API 配置",
    "type": "object",
    "schema": {
      "base_url": {
        "description": "基础 URL",
        "type": "string",
        "default": "https://api.example.com"
      },
      "api_version": {
        "description": "API 版本",
        "type": "string",
        "default": "v1"
      }
    }
  }
}
```

### 列表类型

```json
{
  "allowed_users": {
    "description": "允许的用户列表",
    "type": "list",
    "item_type": "string",
    "default": ["user1", "user2"]
  }
}
```

### 字典类型

```json
{
  "custom_commands": {
    "description": "自定义命令",
    "type": "dict",
    "key_type": "string",
    "value_type": "string",
    "default": {
      "hello": "你好！",
      "help": "这是帮助信息"
    }
  }
}
```

### 模板列表类型

```json
{
  "response_templates": {
    "description": "回复模板列表",
    "type": "template_list",
    "default": [
      {
        "name": "默认回复",
        "template": "你好！有什么可以帮助你的吗？"
      },
      {
        "name": "技术支持",
        "template": "请描述你遇到的技术问题。"
      }
    ]
  }
}
```

### 文件类型

```json
{
  "custom_icon": {
    "description": "自定义图标",
    "type": "file",
    "accept": ".png,.jpg,.svg",
    "default": ""
  }
}
```

## Secret 字段

```json
{
  "api_secret": {
    "description": "API 密钥",
    "type": "string",
    "secret": true,
    "required": true
  }
}
```

- `secret: true`: 字段值在 UI 中会被隐藏
- 适用于密码、API 密钥等敏感信息

## 特殊字段

### required 字段

```json
{
  "mandatory_field": {
    "description": "必填字段",
    "type": "string",
    "required": true
  }
}
```

### default 字段

```json
{
  "optional_field": {
    "description": "可选字段",
    "type": "string",
    "default": "默认值"
  }
}
```

### description 字段

```json
{
  "field_with_desc": {
    "description": "这是一个带有详细描述的字段，用于说明该字段的用途和用法",
    "type": "string"
  }
}
```

## Options 和 Labels

### 使用 options

```json
{
  "mode": {
    "description": "运行模式",
    "type": "string",
    "options": ["fast", "balanced", "quality"],
    "default": "balanced"
  }
}
```

### 使用 labels

```json
{
  "log_level": {
    "description": "日志级别",
    "type": "string",
    "labels": {
      "debug": "调试",
      "info": "信息",
      "warning": "警告",
      "error": "错误"
    },
    "default": "info"
  }
}
```

## Editor Mode

### 代码编辑器

```json
{
  "code_template": {
    "description": "代码模板",
    "type": "text",
    "editor_mode": "code",
    "language": "python",
    "default": "def hello():\n    print('Hello, World!')"
  }
}
```

### JSON 编辑器

```json
{
  "json_config": {
    "description": "JSON 配置",
    "type": "text",
    "editor_mode": "json",
    "default": "{\"key\": \"value\"}"
  }
}
```

## Special Selectors

### 文件选择器

```json
{
  "input_file": {
    "description": "输入文件",
    "type": "file",
    "selector": "file",
    "accept": ".txt,.csv,.json"
  }
}
```

### 目录选择器

```json
{
  "output_dir": {
    "description": "输出目录",
    "type": "string",
    "selector": "directory"
  }
}
```

### 日期选择器

```json
{
  "start_date": {
    "description": "开始日期",
    "type": "string",
    "selector": "date"
  }
}
```

### 颜色选择器

```json
{
  "theme_color": {
    "description": "主题颜色",
    "type": "string",
    "selector": "color",
    "default": "#3498db"
  }
}
```

## 在插件中使用配置

### 获取配置值

```python
from astrbot.api.star import Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.star import Star

class ConfigurablePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 获取配置
        self.config = context.get_config()
        
    @filter.command("config")
    async def on_config(self, event: AstrMessageEvent):
        """显示当前配置"""
        api_key = self.config.get("api_key", "未设置")
        max_retries = self.config.get("max_retries", 3)
        enable_logging = self.config.get("enable_logging", True)
        
        config_text = f"""
        当前配置:
        - API 密钥: {api_key[:4]}**** (已隐藏)
        - 最大重试次数: {max_retries}
        - 启用日志: {enable_logging}
        """
        await event.plain_result(config_text)
```

### 动态修改配置

```python
@filter.command("set_config")
async def on_set_config(self, event: AstrMessageEvent):
    """动态修改配置"""
    args = event.message_str.split()[1:]
    if len(args) < 2:
        await event.plain_result("用法: /set_config <配置项> <值>")
        return
        
    key = args[0]
    value = args[1]
    
    # 更新配置
    self.config[key] = value
    await self.context.update_config(self.config)
    
    await event.plain_result(f"配置 {key} 已更新为 {value}")
```

### 配置验证

```python
from astrbot.api.validator import Validator

class ValidatedPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = context.get_config()
        self.validator = Validator()
        
    def validate_config(self):
        """验证配置"""
        errors = []
        
        # 验证 API 密钥
        api_key = self.config.get("api_key")
        if not api_key:
            errors.append("API 密钥不能为空")
            
        # 验证超时时间
        timeout = self.config.get("timeout")
        if timeout and (timeout < 1 or timeout > 300):
            errors.append("超时时间必须在 1-300 秒之间")
            
        return errors
```

## 配置变更监听

```python
class ConfigWatcherPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = context.get_config()
        
    @filter.on_config_changed()
    async def on_config_changed(self, old_config: dict, new_config: dict):
        """配置变更时触发"""
        # 检查特定配置项是否变更
        if old_config.get("api_key") != new_config.get("api_key"):
            self.context.logger.info("API 密钥已更改")
            # 重新初始化 API 客户端
            await self.reinitialize_api_client()
            
        if old_config.get("max_retries") != new_config.get("max_retries"):
            self.context.logger.info("重试次数已更改")
```

## 完整配置示例

```json
{
  "api_key": {
    "description": "API 密钥",
    "type": "string",
    "required": true,
    "secret": true
  },
  "api_url": {
    "description": "API 地址",
    "type": "string",
    "default": "https://api.example.com"
  },
  "model": {
    "description": "AI 模型",
    "type": "string",
    "options": ["gpt-3.5-turbo", "gpt-4", "claude-3"],
    "default": "gpt-3.5-turbo"
  },
  "temperature": {
    "description": "温度参数",
    "type": "float",
    "default": 0.7,
    "minimum": 0.0,
    "maximum": 2.0
  },
  "max_tokens": {
    "description": "最大 token 数",
    "type": "int",
    "default": 1000,
    "minimum": 100,
    "maximum": 4000
  },
  "enable_streaming": {
    "description": "启用流式响应",
    "type": "bool",
    "default": true
  },
  "custom_headers": {
    "description": "自定义请求头",
    "type": "dict",
    "key_type": "string",
    "value_type": "string",
    "default": {}
  },
  "allowed_models": {
    "description": "允许的模型列表",
    "type": "list",
    "item_type": "string",
    "default": ["gpt-3.5-turbo", "gpt-4"]
  }
}
```

## 下一步

配置完成后，你可以：
- [开发插件页面](06-plugin-pages.md)
- [实现插件国际化](07-plugin-i18n.md)
- [调用 AI 功能](08-ai.md)