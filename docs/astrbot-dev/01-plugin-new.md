# AstrBot 插件开发指南

AstrBot 插件是扩展 AstrBot 功能的模块化组件。本指南将帮助你从零开始开发一个 AstrBot 插件。

## 环境准备

### 安装 AstrBot

首先，确保你已经安装了 AstrBot。如果尚未安装，可以通过以下方式获取：

```bash
# 克隆 AstrBot 仓库
git clone https://github.com/Soulter/AstrBot.git
cd AstrBot

# 安装依赖
pip install -r requirements.txt
```

### 开发工具

推荐使用以下工具进行开发：
- **IDE**: VS Code / PyCharm
- **Python**: 3.10 或更高版本
- **包管理**: pip

## 插件模板

AstrBot 提供了插件模板，你可以快速创建插件项目：

```bash
# 使用模板创建插件
astrbot new-plugin
```

或者手动创建以下目录结构：

```
my_plugin/
├── main.py           # 插件主文件
├── metadata.yaml     # 插件元数据
└── _conf_schema.json # 配置 schema（可选）
```

## metadata.yaml

`metadata.yaml` 是插件的元数据文件，包含了插件的基本信息：

```yaml
name: my_plugin
author: your_name
version: 1.0.0
description: 这是一个示例插件
astrbot_version: ">=1.0.0"
repository: https://github.com/your_name/my_plugin
```

### 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| name | string | 是 | 插件名称 |
| author | string | 是 | 插件作者 |
| version | string | 是 | 插件版本 |
| description | string | 是 | 插件描述 |
| astrbot_version | string | 否 | AstrBot 版本要求 |
| repository | string | 否 | 仓库地址 |

## 调试

### 启用调试模式

在 AstrBot 配置中启用插件热重载：

```yaml
plugin:
  hot_reload: true
```

### 日志输出

使用 AstrBot 内置的日志系统：

```python
from astrbot.api.star import Context

# 在插件中使用
context = Context()
context.logger.info("这是一条日志")
context.logger.error("这是一条错误日志")
```

### 调试技巧

1. **断点调试**: 使用 IDE 的断点功能
2. **日志追踪**: 在关键位置添加日志
3. **异常捕获**: 使用 try-except 捕获异常
4. **热重载**: 修改代码后自动加载

## 开发原则

### 1. 模块化设计

每个插件应该专注于一个功能，保持单一职责。

### 2. 错误处理

始终处理可能的异常，提供友好的错误信息。

```python
try:
    result = await some_operation()
except Exception as e:
    await event.send(f"操作失败: {str(e)}")
```

### 3. 资源管理

及时释放资源，避免内存泄漏。

### 4. 兼容性

确保插件兼容多个 AstrBot 版本。

### 5. 文档

为你的插件编写清晰的文档，包括使用说明和配置说明。

## 下一步

现在你已经了解了插件开发的基础知识，可以开始：
- [编写第一个简单插件](02-simple.md)
- [学习消息处理](03-listen-message-event.md)
- [掌握消息发送](04-send-message.md)
- [配置插件选项](05-plugin-config.md)