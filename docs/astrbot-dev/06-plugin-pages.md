# 插件 Pages

本节介绍如何为 AstrBot 插件开发自定义页面，包括页面架构、后端 API、Bridge API 和页面国际化。

## 页面架构

### 目录结构

```
my_plugin/
├── main.py
├── metadata.yaml
├── _conf_schema.json
└── pages/
    ├── index.html          # 主页面
    ├── index.js            # 页面逻辑
    ├── index.css           # 页面样式
    └── i18n/               # 页面国际化
        ├── zh-CN.json
        └── en-US.json
```

### 基本页面文件

#### index.html

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>我的插件页面</title>
    <link rel="stylesheet" href="index.css">
</head>
<body>
    <div id="app">
        <h1>{{ title }}</h1>
        <div class="content">
            <p>{{ description }}</p>
            <button @click="fetchData">获取数据</button>
            <div v-if="loading">加载中...</div>
            <div v-else>
                <ul>
                    <li v-for="item in items" :key="item.id">
                        {{ item.name }}
                    </li>
                </ul>
            </div>
        </div>
    </div>
    <script src="index.js"></script>
</body>
</html>
```

#### index.js

```javascript
// 使用 Bridge API
const { ready, apiGet, apiPost, upload, download, subscribeSSE } = Bridge;

// 页面状态
const state = {
    title: '我的插件页面',
    description: '这是一个示例插件页面',
    items: [],
    loading: false
};

// 初始化页面
ready(() => {
    console.log('页面已就绪');
    fetchData();
});

// 获取数据
async function fetchData() {
    state.loading = true;
    try {
        const response = await apiGet('/api/data');
        state.items = response.data;
    } catch (error) {
        console.error('获取数据失败:', error);
    } finally {
        state.loading = false;
    }
}

// 提交数据
async function submitData(data) {
    try {
        const response = await apiPost('/api/submit', data);
        console.log('提交成功:', response);
        await fetchData(); // 刷新数据
    } catch (error) {
        console.error('提交失败:', error);
    }
}
```

#### index.css

```css
#app {
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
    font-family: Arial, sans-serif;
}

h1 {
    color: #333;
    text-align: center;
}

.content {
    margin-top: 20px;
}

button {
    background-color: #3498db;
    color: white;
    padding: 10px 20px;
    border: none;
    border-radius: 5px;
    cursor: pointer;
}

button:hover {
    background-color: #2980b9;
}

ul {
    list-style: none;
    padding: 0;
}

li {
    padding: 10px;
    border-bottom: 1px solid #eee;
}

.loading {
    text-align: center;
    color: #666;
}
```

## 开发流程

### 1. 创建页面目录

在插件目录中创建 `pages` 目录。

### 2. 创建页面文件

创建 `index.html`、`index.js` 和 `index.css` 文件。

### 3. 实现后端 API

在插件的 `main.py` 中注册 Web API。

### 4. 测试页面

在 AstrBot 管理界面中访问插件页面。

## 后端 Web API

### 注册 Web API

```python
from astrbot.api.star import Context
from astrbot.api.event import filter
from astrbot.core.star.star import Star

class PagesPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    @filter.register_web_api("/api/data")
    async def get_data(self, request):
        """获取数据 API"""
        # 实现数据获取逻辑
        data = [
            {"id": 1, "name": "项目 1"},
            {"id": 2, "name": "项目 2"},
            {"id": 3, "name": "项目 3"}
        ]
        return {"data": data}
        
    @filter.register_web_api("/api/submit", methods=["POST"])
    async def submit_data(self, request):
        """提交数据 API"""
        # 获取请求数据
        request_data = await request.json()
        
        # 处理数据
        result = {"success": True, "message": "数据已提交"}
        return result
```

### Request 对象

```python
@filter.register_web_api("/api/info")
async def get_info(self, request):
    """获取请求信息"""
    # 获取查询参数
    page = request.query.get("page", 1)
    limit = request.query.get("limit", 10)
    
    # 获取请求头
    user_agent = request.headers.get("User-Agent", "")
    
    # 获取请求体
    body = await request.json() if request.method == "POST" else None
    
    return {
        "page": page,
        "limit": limit,
        "user_agent": user_agent,
        "body": body
    }
```

### Response 辅助函数

```python
from astrbot.api.web_response import json_response, html_response, file_response

@filter.register_web_api("/api/json")
async def json_api(self, request):
    """返回 JSON 响应"""
    return json_response({"message": "成功"})
    
@filter.register_web_api("/api/html")
async def html_api(self, request):
    """返回 HTML 响应"""
    html_content = "<h1>这是 HTML 响应</h1>"
    return html_response(html_content)
    
@filter.register_web_api("/api/file")
async def file_api(self, request):
    """返回文件响应"""
    file_path = "/path/to/file.pdf"
    return file_response(file_path, filename="document.pdf")
```

## Bridge API

### ready

```javascript
// 页面加载完成后执行
ready(() => {
    console.log('页面已就绪');
    // 初始化页面
    initPage();
});
```

### apiGet

```javascript
// GET 请求
async function getData() {
    try {
        const response = await apiGet('/api/data');
        console.log('数据:', response.data);
        return response.data;
    } catch (error) {
        console.error('请求失败:', error);
    }
}
```

### apiPost

```javascript
// POST 请求
async function postData(data) {
    try {
        const response = await apiPost('/api/submit', data);
        console.log('响应:', response);
        return response;
    } catch (error) {
        console.error('请求失败:', error);
    }
}
```

### upload

```javascript
// 上传文件
async function uploadFile(file) {
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await upload('/api/upload', formData);
        console.log('上传成功:', response);
        return response;
    } catch (error) {
        console.error('上传失败:', error);
    }
}
```

### download

```javascript
// 下载文件
async function downloadFile(fileId) {
    try {
        const response = await download(`/api/download/${fileId}`);
        console.log('下载成功:', response);
        return response;
    } catch (error) {
        console.error('下载失败:', error);
    }
}
```

### subscribeSSE

```javascript
// 订阅 Server-Sent Events
const unsubscribe = subscribeSSE('/api/events', (event) => {
    console.log('收到事件:', event);
    
    // 处理不同类型的事件
    switch (event.type) {
        case 'update':
            updateUI(event.data);
            break;
        case 'notification':
            showNotification(event.message);
            break;
    }
});

// 取消订阅
// unsubscribe();
```

## 页面国际化

### 国际化文件结构

```
pages/
└── i18n/
    ├── zh-CN.json
    └── en-US.json
```

### 国际化文件内容

#### zh-CN.json

```json
{
    "title": "我的插件页面",
    "description": "这是一个示例插件页面",
    "buttons": {
        "fetch": "获取数据",
        "submit": "提交数据",
        "download": "下载文件"
    },
    "messages": {
        "loading": "加载中...",
        "success": "操作成功",
        "error": "操作失败"
    }
}
```

#### en-US.json

```json
{
    "title": "My Plugin Page",
    "description": "This is a sample plugin page",
    "buttons": {
        "fetch": "Fetch Data",
        "submit": "Submit Data",
        "download": "Download File"
    },
    "messages": {
        "loading": "Loading...",
        "success": "Operation successful",
        "error": "Operation failed"
    }
}
```

### 在页面中使用国际化

```javascript
// 获取当前语言
const currentLang = navigator.language || 'zh-CN';

// 加载国际化文件
async function loadI18n(lang) {
    const response = await apiGet(`/pages/i18n/${lang}.json`);
    return response;
}

// 使用国际化文本
const i18n = await loadI18n(currentLang);
document.title = i18n.title;
document.querySelector('h1').textContent = i18n.title;
```

## 主题支持

### 使用 AstrBot 主题

```css
/* 使用 AstrBot 主题变量 */
:root {
    --primary-color: var(--astrbot-primary-color, #3498db);
    --text-color: var(--astrbot-text-color, #333);
    --bg-color: var(--astrbot-bg-color, #fff);
}

body {
    background-color: var(--bg-color);
    color: var(--text-color);
}

button {
    background-color: var(--primary-color);
}
```

### 暗色主题适配

```css
/* 暗色主题 */
@media (prefers-color-scheme: dark) {
    :root {
        --primary-color: #3498db;
        --text-color: #ecf0f1;
        --bg-color: #2c3e50;
    }
}

/* AstrBot 暗色主题 */
[data-theme="dark"] {
    --primary-color: #3498db;
    --text-color: #ecf0f1;
    --bg-color: #2c3e50;
}
```

## 静态资源

### 添加静态资源

在 `pages` 目录中创建 `static` 目录：

```
pages/
├── index.html
├── index.js
├── index.css
└── static/
    ├── images/
    │   └── logo.png
    ├── fonts/
    │   └── custom-font.woff2
    └── js/
        └── utils.js
```

### 在页面中引用静态资源

```html
<!-- 引用图片 -->
<img src="static/images/logo.png" alt="Logo">

<!-- 引用字体 -->
<style>
@font-face {
    font-family: 'CustomFont';
    src: url('static/fonts/custom-font.woff2') format('woff2');
}
</style>

<!-- 引用脚本 -->
<script src="static/js/utils.js"></script>
```

## 安全约束

### 输入验证

```javascript
// 验证用户输入
function validateInput(input) {
    if (!input || typeof input !== 'string') {
        return false;
    }
    
    // 长度检查
    if (input.length > 1000) {
        return false;
    }
    
    // XSS 防护
    const regex = /[<>"'&]/;
    if (regex.test(input)) {
        return false;
    }
    
    return true;
}
```

### CSRF 防护

```javascript
// 在请求中添加 CSRF token
async function secureRequest(url, data) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    
    return apiPost(url, data, {
        headers: {
            'X-CSRF-Token': csrfToken
        }
    });
}
```

### 权限控制

```python
@filter.register_web_api("/api/admin")
async def admin_api(self, request):
    """需要管理员权限的 API"""
    # 检查用户权限
    user_id = request.headers.get("X-User-ID")
    if not await self.check_admin_permission(user_id):
        return {"error": "权限不足"}, 403
    
    # 处理请求
    return {"message": "管理员 API"}
```

## 完整示例

### 插件主文件

```python
from astrbot.api.star import Context
from astrbot.api.event import filter
from astrbot.core.star.star import Star

class DashboardPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    @filter.register_web_api("/api/stats")
    async def get_stats(self, request):
        """获取统计数据"""
        stats = {
            "total_users": 1000,
            "active_users": 500,
            "messages_today": 10000
        }
        return {"data": stats}
        
    @filter.register_web_api("/api/users", methods=["GET", "POST"])
    async def users_api(self, request):
        """用户管理 API"""
        if request.method == "GET":
            # 获取用户列表
            users = [{"id": 1, "name": "用户1"}, {"id": 2, "name": "用户2"}]
            return {"data": users}
        else:
            # 创建用户
            data = await request.json()
            # 实现创建用户逻辑
            return {"success": True, "message": "用户已创建"}
```

### 页面文件

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>管理面板</title>
    <link rel="stylesheet" href="index.css">
</head>
<body>
    <div id="app">
        <header>
            <h1>{{ title }}</h1>
        </header>
        
        <main>
            <section class="stats">
                <h2>统计数据</h2>
                <div class="stat-grid">
                    <div class="stat-card">
                        <h3>总用户数</h3>
                        <p class="stat-value">{{ stats.total_users }}</p>
                    </div>
                    <div class="stat-card">
                        <h3>活跃用户</h3>
                        <p class="stat-value">{{ stats.active_users }}</p>
                    </div>
                    <div class="stat-card">
                        <h3>今日消息</h3>
                        <p class="stat-value">{{ stats.messages_today }}</p>
                    </div>
                </div>
            </section>
            
            <section class="users">
                <h2>用户管理</h2>
                <button @click="showAddUser">添加用户</button>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>名称</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="user in users" :key="user.id">
                            <td>{{ user.id }}</td>
                            <td>{{ user.name }}</td>
                            <td>
                                <button @click="editUser(user)">编辑</button>
                                <button @click="deleteUser(user)">删除</button>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </section>
        </main>
    </div>
    
    <script src="index.js"></script>
</body>
</html>
```

## 下一步

掌握了插件页面开发后，你可以：
- [实现插件国际化](07-plugin-i18n.md)
- [调用 AI 功能](08-ai.md)
- [实现插件存储](09-storage.md)