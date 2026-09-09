# 插件国际化

本节介绍如何为 AstrBot 插件添加国际化支持，包括元数据翻译、配置翻译、页面翻译和嵌套配置翻译。

## 国际化结构

### 目录结构

```
my_plugin/
├── main.py
├── metadata.yaml
├── _conf_schema.json
└── .astrbot-plugin/
    └── i18n/
        ├── zh-CN.json
        ├── en-US.json
        └── ja-JP.json
```

### 国际化文件结构

```
.astrbot-plugin/
└── i18n/
    ├── zh-CN.json      # 中文（简体）
    ├── en-US.json      # 英语（美国）
    ├── ja-JP.json      # 日语
    └── ko-KR.json      # 韩语
```

## 国际化文件内容

### 基本结构

```json
{
    "metadata": {
        "name": "插件名称",
        "description": "插件描述"
    },
    "config": {
        "api_key": {
            "description": "API 密钥描述"
        },
        "max_retries": {
            "description": "最大重试次数描述"
        }
    },
    "pages": {
        "title": "页面标题",
        "buttons": {
            "save": "保存",
            "cancel": "取消"
        }
    }
}
```

## 元数据翻译

### metadata.yaml 翻译

在 `metadata.yaml` 中添加翻译：

```yaml
name: my_plugin
author: developer
version: 1.0.0
description: 这是一个示例插件
description_en: This is a sample plugin
description_ja: これはサンプルプラグインです
astrbot_version: ">=1.0.0"
repository: https://github.com/developer/my_plugin
```

### 使用国际化文件翻译元数据

在 `.astrbot-plugin/i18n/zh-CN.json` 中：

```json
{
    "metadata": {
        "name": "我的插件",
        "description": "这是一个示例插件，提供了丰富的功能。"
    }
}
```

在 `.astrbot-plugin/i18n/en-US.json` 中：

```json
{
    "metadata": {
        "name": "My Plugin",
        "description": "This is a sample plugin with rich features."
    }
}
```

## 配置翻译

### 配置项翻译

在 `.astrbot-plugin/i18n/zh-CN.json` 中：

```json
{
    "config": {
        "api_key": {
            "description": "请输入您的 API 密钥，用于访问外部服务。"
        },
        "max_retries": {
            "description": "设置最大重试次数，范围 1-10。"
        },
        "timeout": {
            "description": "请求超时时间，单位为秒。"
        },
        "enable_logging": {
            "description": "启用详细日志记录，便于调试。"
        }
    }
}
```

在 `.astrbot-plugin/i18n/en-US.json` 中：

```json
{
    "config": {
        "api_key": {
            "description": "Please enter your API key to access external services."
        },
        "max_retries": {
            "description": "Set maximum retry attempts, range 1-10."
        },
        "timeout": {
            "description": "Request timeout in seconds."
        },
        "enable_logging": {
            "description": "Enable detailed logging for debugging."
        }
    }
}
```

### 配置选项翻译

对于带有选项的配置：

```json
{
    "config": {
        "mode": {
            "description": "选择运行模式",
            "options": {
                "fast": "快速模式",
                "balanced": "平衡模式",
                "quality": "高质量模式"
            }
        },
        "log_level": {
            "description": "设置日志级别",
            "labels": {
                "debug": "调试",
                "info": "信息",
                "warning": "警告",
                "error": "错误"
            }
        }
    }
}
```

## 页面翻译

### 页面内容翻译

在 `.astrbot-plugin/i18n/zh-CN.json` 中：

```json
{
    "pages": {
        "title": "管理面板",
        "description": "欢迎使用管理面板",
        "buttons": {
            "save": "保存",
            "cancel": "取消",
            "delete": "删除",
            "edit": "编辑",
            "add": "添加"
        },
        "messages": {
            "loading": "加载中...",
            "success": "操作成功",
            "error": "操作失败",
            "confirm_delete": "确定要删除吗？"
        },
        "table": {
            "headers": {
                "id": "ID",
                "name": "名称",
                "status": "状态",
                "actions": "操作"
            },
            "empty": "暂无数据"
        }
    }
}
```

在 `.astrbot-plugin/i18n/en-US.json` 中：

```json
{
    "pages": {
        "title": "Management Panel",
        "description": "Welcome to the management panel",
        "buttons": {
            "save": "Save",
            "cancel": "Cancel",
            "delete": "Delete",
            "edit": "Edit",
            "add": "Add"
        },
        "messages": {
            "loading": "Loading...",
            "success": "Operation successful",
            "error": "Operation failed",
            "confirm_delete": "Are you sure you want to delete?"
        },
        "table": {
            "headers": {
                "id": "ID",
                "name": "Name",
                "status": "Status",
                "actions": "Actions"
            },
            "empty": "No data available"
        }
    }
}
```

### 在页面中使用翻译

```javascript
// 获取当前语言
const currentLang = navigator.language || 'zh-CN';

// 加载翻译文件
async function loadTranslations(lang) {
    const response = await apiGet(`/pages/i18n/${lang}.json`);
    return response;
}

// 使用翻译
const translations = await loadTranslations(currentLang);

// 更新页面内容
document.title = translations.pages.title;
document.querySelector('h1').textContent = translations.pages.title;
document.querySelector('.description').textContent = translations.pages.description;

// 更新按钮文本
document.querySelector('#save-btn').textContent = translations.pages.buttons.save;
document.querySelector('#cancel-btn').textContent = translations.pages.buttons.cancel;
```

## 嵌套配置翻译

### 复杂配置结构

对于对象类型的配置：

```json
{
    "config": {
        "api_config": {
            "description": "API 配置",
            "schema": {
                "base_url": {
                    "description": "API 基础地址"
                },
                "api_version": {
                    "description": "API 版本"
                },
                "timeout": {
                    "description": "请求超时时间"
                }
            }
        }
    }
}
```

### 翻译嵌套配置

在 `.astrbot-plugin/i18n/zh-CN.json` 中：

```json
{
    "config": {
        "api_config": {
            "description": "配置 API 连接参数",
            "schema": {
                "base_url": {
                    "description": "API 服务器的基础地址，例如：https://api.example.com"
                },
                "api_version": {
                    "description": "API 版本号，例如：v1、v2"
                },
                "timeout": {
                    "description": "请求超时时间，单位为秒，建议设置 30-60 秒"
                }
            }
        }
    }
}
```

在 `.astrbot-plugin/i18n/en-US.json` 中：

```json
{
    "config": {
        "api_config": {
            "description": "Configure API connection parameters",
            "schema": {
                "base_url": {
                    "description": "Base URL of the API server, e.g., https://api.example.com"
                },
                "api_version": {
                    "description": "API version number, e.g., v1, v2"
                },
                "timeout": {
                    "description": "Request timeout in seconds, recommended 30-60 seconds"
                }
            }
        }
    }
}
```

## 模板列表翻译

### 模板列表配置

```json
{
    "config": {
        "response_templates": {
            "description": "回复模板列表",
            "type": "template_list",
            "default": [
                {
                    "name": "默认回复",
                    "template": "你好！有什么可以帮助你的吗？"
                }
            ]
        }
    }
}
```

### 翻译模板列表

在 `.astrbot-plugin/i18n/zh-CN.json` 中：

```json
{
    "config": {
        "response_templates": {
            "description": "配置不同的回复模板",
            "templates": {
                "默认回复": "你好！有什么可以帮助你的吗？",
                "技术支持": "请描述你遇到的技术问题，我会尽力帮助你。",
                "投诉建议": "感谢你的反馈，我们会认真处理你的投诉和建议。"
            }
        }
    }
}
```

在 `.astrbot-plugin/i18n/en-US.json` 中：

```json
{
    "config": {
        "response_templates": {
            "description": "Configure different response templates",
            "templates": {
                "默认回复": "Hello! How can I help you?",
                "技术支持": "Please describe your technical issue, I'll do my best to help.",
                "投诉建议": "Thank you for your feedback, we will carefully handle your complaints and suggestions."
            }
        }
    }
}
```

## 动态语言切换

### 实现语言切换

```python
from astrbot.api.star import Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.star import Star

class I18nPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.current_lang = "zh-CN"
        
    @filter.command("lang")
    async def on_lang(self, event: AstrMessageEvent):
        """切换语言"""
        args = event.message_str.split()[1:]
        if not args:
            await event.plain_result(f"当前语言: {self.current_lang}\n可用语言: zh-CN, en-US, ja-JP")
            return
            
        new_lang = args[0]
        if new_lang in ["zh-CN", "en-US", "ja-JP"]:
            self.current_lang = new_lang
            await event.plain_result(f"语言已切换为: {new_lang}")
        else:
            await event.plain_result("不支持的语言")
            
    def get_translation(self, key: str):
        """获取翻译文本"""
        # 这里简化实现，实际应该从 i18n 文件加载
        translations = {
            "zh-CN": {"welcome": "欢迎使用"},
            "en-US": {"welcome": "Welcome to"},
            "ja-JP": {"welcome": "ようこそ"}
        }
        return translations.get(self.current_lang, {}).get(key, key)
```

## 自动检测语言

### 基于用户设置

```python
class AutoI18nPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.user_languages = {}  # 用户语言设置
        
    @filter.command("set_lang")
    async def on_set_lang(self, event: AstrMessageEvent):
        """设置用户语言"""
        args = event.message_str.split()[1:]
        if not args:
            await event.plain_result("用法: /set_lang <语言代码>")
            return
            
        lang = args[0]
        user_id = event.sender.id
        self.user_languages[user_id] = lang
        await event.plain_result(f"语言已设置为: {lang}")
        
    def get_user_language(self, user_id: str):
        """获取用户语言"""
        return self.user_languages.get(user_id, "zh-CN")
```

### 基于平台语言

```python
class PlatformI18nPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    def detect_language(self, event: AstrMessageEvent):
        """检测平台语言"""
        platform = event.platform
        
        # 根据平台设置默认语言
        platform_languages = {
            "qq": "zh-CN",
            "telegram": "en-US",
            "discord": "en-US",
            "wechat": "zh-CN"
        }
        
        return platform_languages.get(platform, "zh-CN")
```

## 完整国际化示例

### 国际化文件

#### zh-CN.json

```json
{
    "metadata": {
        "name": "国际化插件",
        "description": "支持多语言的示例插件"
    },
    "config": {
        "greeting": {
            "description": "问候语模板"
        },
        "language": {
            "description": "默认语言",
            "options": {
                "zh-CN": "中文",
                "en-US": "English",
                "ja-JP": "日本語"
            }
        }
    },
    "pages": {
        "title": "国际化设置",
        "welcome": "欢迎使用国际化插件",
        "buttons": {
            "save": "保存设置",
            "reset": "重置默认"
        }
    },
    "commands": {
        "greet": "问候",
        "help": "帮助",
        "lang": "切换语言"
    }
}
```

#### en-US.json

```json
{
    "metadata": {
        "name": "Internationalization Plugin",
        "description": "A sample plugin supporting multiple languages"
    },
    "config": {
        "greeting": {
            "description": "Greeting message template"
        },
        "language": {
            "description": "Default language",
            "options": {
                "zh-CN": "中文",
                "en-US": "English",
                "ja-JP": "日本語"
            }
        }
    },
    "pages": {
        "title": "Internationalization Settings",
        "welcome": "Welcome to the Internationalization Plugin",
        "buttons": {
            "save": "Save Settings",
            "reset": "Reset to Default"
        }
    },
    "commands": {
        "greet": "Greet",
        "help": "Help",
        "lang": "Switch Language"
    }
}
```

### 插件主文件

```python
from astrbot.api.star import Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.star import Star

class InternationalizationPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.translations = {}
        self.load_translations()
        
    def load_translations(self):
        """加载翻译文件"""
        import json
        import os
        
        i18n_dir = os.path.join(os.path.dirname(__file__), ".astrbot-plugin", "i18n")
        if os.path.exists(i18n_dir):
            for filename in os.listdir(i18n_dir):
                if filename.endswith(".json"):
                    lang = filename[:-5]  # 移除 .json
                    filepath = os.path.join(i18n_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self.translations[lang] = json.load(f)
                        
    def get_translation(self, lang: str, key: str, default: str = ""):
        """获取翻译文本"""
        if lang not in self.translations:
            return default
            
        # 支持嵌套键
        keys = key.split(".")
        value = self.translations[lang]
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
                
        return value if isinstance(value, str) else default
        
    @filter.command("greet")
    async def on_greet(self, event: AstrMessageEvent):
        """问候命令"""
        lang = self.detect_language(event)
        greeting = self.get_translation(lang, "commands.greet", "你好")
        await event.plain_result(f"{greeting}！")
        
    @filter.command("help")
    async def on_help(self, event: AstrMessageEvent):
        """帮助命令"""
        lang = self.detect_language(event)
        help_title = self.get_translation(lang, "pages.title", "帮助")
        save_btn = self.get_translation(lang, "pages.buttons.save", "保存")
        
        help_text = f"""
        {help_title}
        
        可用命令:
        /greet - 问候
        /help - 显示帮助
        /lang <语言代码> - 切换语言
        
        按钮示例: {save_btn}
        """
        await event.plain_result(help_text)
        
    @filter.command("lang")
    async def on_lang(self, event: AstrMessageEvent):
        """切换语言"""
        args = event.message_str.split()[1:]
        if not args:
            current_lang = self.detect_language(event)
            current_lang_name = self.get_translation(
                current_lang, 
                f"config.language.options.{current_lang}", 
                current_lang
            )
            await event.plain_result(f"当前语言: {current_lang_name}")
            return
            
        new_lang = args[0]
        if new_lang in self.translations:
            # 保存用户语言设置
            self.save_user_language(event.sender.id, new_lang)
            lang_name = self.get_translation(
                new_lang, 
                f"config.language.options.{new_lang}", 
                new_lang
            )
            await event.plain_result(f"语言已切换为: {lang_name}")
        else:
            await event.plain_result("不支持的语言")
            
    def detect_language(self, event: AstrMessageEvent):
        """检测用户语言"""
        # 这里可以实现更复杂的语言检测逻辑
        return "zh-CN"  # 默认中文
```

## 下一步

完成了国际化设置后，你可以：
- [调用 AI 功能](08-ai.md)
- [实现插件存储](09-storage.md)
- [实现文本转图片](10-html-to-pic.md)