# 发布插件到插件市场

本节介绍如何将开发的 AstrBot 插件发布到插件市场，包括发布流程、metadata.yaml 格式、大小限制和 AstrBot Cloud。

## 发布流程

### 准备工作

1. **完善插件功能**: 确保插件功能完整、稳定
2. **编写文档**: 包括 README、使用说明
3. **测试插件**: 在不同环境下测试插件
4. **准备元数据**: 完善 metadata.yaml 文件

### 发布步骤

1. **注册账号**: 在 AstrBot Cloud 注册账号
2. **上传插件**: 将插件打包并上传
3. **填写信息**: 填写插件详细信息
4. **提交审核**: 提交插件进行审核
5. **发布上线**: 审核通过后发布到市场

## metadata.yaml 格式

### 基本格式

```yaml
name: my_plugin
author: your_name
version: 1.0.0
description: 这是一个示例插件
description_en: This is a sample plugin
astrbot_version: ">=1.0.0"
repository: https://github.com/your_name/my_plugin
license: MIT
tags:
  - utility
  - assistant
  - tool
category: utility
icon: icon.png
homepage: https://github.com/your_name/my_plugin
readme: README.md
```

### 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| name | string | 是 | 插件名称（唯一标识） |
| author | string | 是 | 插件作者 |
| version | string | 是 | 语义化版本号 |
| description | string | 是 | 插件描述（中文） |
| description_en | string | 否 | 插件描述（英文） |
| astrbot_version | string | 是 | AstrBot 版本要求 |
| repository | string | 否 | 代码仓库地址 |
| license | string | 否 | 开源许可证 |
| tags | list | 否 | 标签列表 |
| category | string | 是 | 插件分类 |
| icon | string | 否 | 插件图标 |
| homepage | string | 否 | 插件主页 |
| readme | string | 否 | README 文件路径 |

### 版本号规范

使用语义化版本号（Semantic Versioning）：

- **MAJOR**: 主版本号，不兼容的 API 修改
- **MINOR**: 次版本号，向下兼容的功能性新增
- **PATCH**: 修订号，向下兼容的问题修正

示例：
```yaml
version: 1.2.3
```

### 依赖声明

```yaml
dependencies:
  astrbot_plugin_core: ">=1.0.0"
  astrbot_plugin_ai: ">=2.0.0"
```

### 配置 schema 引用

```yaml
config_schema: _conf_schema.json
```

## 大小限制

### 文件大小限制

| 文件类型 | 最大大小 |
|----------|----------|
| 插件包总大小 | 10 MB |
| 单个文件 | 5 MB |
| 图片文件 | 2 MB |
| 文档文件 | 1 MB |

### 优化建议

1. **压缩图片**: 使用适当的图片压缩工具
2. **清理无用文件**: 移除开发过程中的临时文件
3. **使用外部资源**: 将大型资源放在外部 CDN
4. **代码压缩**: 压缩 JavaScript 和 CSS 文件

### 检查文件大小

```bash
# 检查插件包大小
du -sh my_plugin/

# 检查单个文件大小
find my_plugin/ -type f -size +1M
```

## AstrBot Cloud

### 注册账号

1. 访问 AstrBot Cloud 官网
2. 点击注册按钮
3. 填写注册信息
4. 验证邮箱
5. 完成注册

### 上传插件

1. 登录 AstrBot Cloud
2. 进入插件管理页面
3. 点击"上传插件"按钮
4. 选择插件包文件
5. 填写插件信息
6. 提交上传

### 插件信息填写

#### 基本信息

- **插件名称**: 与 metadata.yaml 中的 name 一致
- **版本号**: 与 metadata.yaml 中的 version 一致
- **描述**: 详细描述插件功能
- **分类**: 选择合适的分类

#### 文档信息

- **README**: 上传或粘贴 README 内容
- **使用说明**: 详细说明插件使用方法
- **配置说明**: 说明插件配置项

#### 图标和截图

- **插件图标**: 上传插件图标（推荐 128x128 像素）
- **功能截图**: 上传插件运行截图

### 审核流程

1. **自动检查**: 系统自动检查插件格式和大小
2. **安全检查**: 检查插件是否包含恶意代码
3. **功能测试**: 测试插件基本功能
4. **人工审核**: 审核插件描述和文档

### 发布和更新

#### 首次发布

1. 通过审核后，插件会发布到市场
2. 插件状态变为"已发布"
3. 用户可以在市场中搜索和安装

#### 版本更新

1. 上传新版本插件包
2. 更新版本号和更新日志
3. 提交审核
4. 审核通过后自动更新

### 插件管理

#### 查看统计

- **安装量**: 查看插件安装次数
- **评分**: 查看用户评分和评价
- **下载量**: 查看插件下载次数

#### 回复评价

- 查看用户评价
- 回复用户问题
- 改进插件功能

## 发布检查清单

### 代码质量

- [ ] 代码符合 PEP 8 规范
- [ ] 没有语法错误
- [ ] 没有运行时错误
- [ ] 异常处理完善

### 功能完整性

- [ ] 所有功能正常工作
- [ ] 命令和参数正确
- [ ] 错误提示友好
- [ ] 文档与实际功能一致

### 配置和元数据

- [ ] metadata.yaml 格式正确
- [ ] 版本号符合规范
- [ ] 描述准确完整
- [ ] 配置 schema 正确

### 文档

- [ ] README 完整清晰
- [ ] 使用说明详细
- [ ] 配置说明完整
- [ ] 示例代码可用

### 测试

- [ ] 在不同平台测试通过
- [ ] 在不同 Python 版本测试通过
- [ ] 性能测试通过
- [ ] 安全测试通过

## 发布示例

### 示例 metadata.yaml

```yaml
name: astrbot_plugin_weather
author: developer
version: 1.2.0
description: 天气查询插件，支持全球城市天气查询
description_en: Weather query plugin, supports global city weather queries
astrbot_version: ">=1.0.0"
repository: https://github.com/developer/astrbot_plugin_weather
license: MIT
tags:
  - weather
  - utility
  - information
category: utility
icon: icon.png
homepage: https://github.com/developer/astrbot_plugin_weather
readme: README.md
dependencies:
  astrbot_plugin_core: ">=1.0.0"
config_schema: _conf_schema.json
```

### 示例 README

```markdown
# 天气查询插件

AstrBot 天气查询插件，支持全球城市天气查询。

## 功能特性

- 支持全球城市天气查询
- 支持多种天气数据源
- 支持自定义查询格式
- 支持天气预报

## 安装方法

1. 在 AstrBot 管理界面搜索"天气查询"
2. 点击安装按钮
3. 配置 API 密钥

## 使用方法

### 查询天气

```
/weather 北京
/weather Shanghai
```

### 查询天气预报

```
/weather forecast 北京
```

## 配置说明

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| api_key | string | - | API 密钥（必填） |
| default_city | string | Beijing | 默认城市 |
| temperature_unit | string | celsius | 温度单位 |

## 更新日志

### v1.2.0 (2024-01-15)

- 新增天气预报功能
- 优化查询速度
- 修复已知问题

### v1.1.0 (2024-01-01)

- 新增多语言支持
- 优化错误提示

### v1.0.0 (2023-12-01)

- 初始版本发布
```

## 常见问题

### 审核失败常见原因

1. **metadata.yaml 格式错误**: 检查 YAML 语法
2. **文件过大**: 压缩或删除大文件
3. **描述不清晰**: 完善插件描述
4. **缺少文档**: 添加完整的 README
5. **功能不完整**: 确保所有功能正常

### 更新插件

1. 修改代码和版本号
2. 重新打包
3. 上传新版本
4. 更新更新日志
5. 提交审核

### 处理用户反馈

1. 定期查看用户评价
2. 及时回复用户问题
3. 根据反馈改进插件
4. 发布修复版本

## 下一步

发布插件后，你可以：
- [接入平台适配器](14-platform-adapter.md)
- [查看完整开发指南](01-plugin-new.md)
- [参与社区讨论](https://github.com/Soulter/AstrBot/discussions)