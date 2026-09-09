# 文转图

本节介绍如何在 AstrBot 插件中将文本转换为图片，包括简单的文本转图片和使用 HTML 渲染。

## 文本转图片

### 基本文本转图片

```python
from astrbot.api.star import Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.messagecomponent import Image

class TextToImagePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    @filter.command("text2img")
    async def on_text2img(self, event: AstrMessageEvent):
        """将文本转换为图片"""
        text = event.message_str.replace("/text2img", "").strip()
        if not text:
            await event.plain_result("请输入要转换的文本，格式: /text2img <文本>")
            return
            
        try:
            # 使用 text_to_image 方法
            image = await self.context.text_to_image(text)
            await event.plain_result(image)
        except Exception as e:
            await event.plain_result(f"转换失败: {str(e)}")
```

### 自定义样式

```python
async def text_to_styled_image(self, text: str, style: dict = None):
    """自定义样式的文本转图片"""
    if style is None:
        style = {
            "font_size": 16,
            "font_color": "#333333",
            "background_color": "#ffffff",
            "padding": 20,
            "max_width": 800
        }
    
    # 构建 HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-size: {style['font_size']}px;
                color: {style['font_color']};
                background-color: {style['background_color']};
                padding: {style['padding']}px;
                max-width: {style['max_width']}px;
                margin: 0 auto;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                line-height: 1.6;
            }}
            .content {{
                white-space: pre-wrap;
                word-wrap: break-word;
            }}
        </style>
    </head>
    <body>
        <div class="content">{text}</div>
    </body>
    </html>
    """
    
    # 使用 html_render 渲染
    return await self.html_render(html)
```

## HTML 渲染

### 基本 HTML 渲染

```python
@filter.command("html2img")
async def on_html2img(self, event: AstrMessageEvent):
    """将 HTML 转换为图片"""
    html = event.message_str.replace("/html2img", "").strip()
    if not html:
        await event.plain_result("请输入 HTML 内容，格式: /html2img <HTML>")
        return
        
    try:
        # 使用 html_render 方法
        image = await self.context.html_render(html)
        await event.plain_result(image)
    except Exception as e:
        await event.plain_result(f"渲染失败: {str(e)}")
```

### 使用 Jinja2 模板

```python
from jinja2 import Template

class TemplatePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    async def render_template(self, template_str: str, data: dict):
        """渲染 Jinja2 模板"""
        template = Template(template_str)
        return template.render(**data)
        
    @filter.command("render")
    async def on_render(self, event: AstrMessageEvent):
        """渲染模板为图片"""
        # 定义模板
        template_str = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }
                .card {
                    background: rgba(255, 255, 255, 0.2);
                    border-radius: 10px;
                    padding: 20px;
                    margin: 10px 0;
                    backdrop-filter: blur(10px);
                }
                .title {
                    font-size: 24px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }
                .content {
                    font-size: 16px;
                    line-height: 1.5;
                }
                .footer {
                    margin-top: 20px;
                    font-size: 12px;
                    opacity: 0.8;
                }
            </style>
        </head>
        <body>
            <div class="card">
                <div class="title">{{ title }}</div>
                <div class="content">{{ content }}</div>
                <div class="footer">生成时间: {{ timestamp }}</div>
            </div>
        </body>
        </html>
        """
        
        # 准备数据
        from datetime import datetime
        data = {
            "title": "示例卡片",
            "content": "这是一个使用 Jinja2 模板渲染的示例。",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 渲染模板
        html = await self.render_template(template_str, data)
        
        # 转换为图片
        image = await self.context.html_render(html)
        await event.plain_result(image)
```

### 复杂模板示例

```python
async def create_user_card(self, user_data: dict):
    """创建用户卡片"""
    template_str = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #f5f7fa;
                padding: 20px;
            }
            .user-card {
                background: white;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                overflow: hidden;
                max-width: 400px;
                margin: 0 auto;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                height: 120px;
                position: relative;
            }
            .avatar {
                width: 80px;
                height: 80px;
                border-radius: 50%;
                border: 4px solid white;
                position: absolute;
                bottom: -40px;
                left: 50%;
                transform: translateX(-50%);
                background: #ddd;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 32px;
                color: white;
            }
            .info {
                padding: 50px 20px 20px;
                text-align: center;
            }
            .name {
                font-size: 24px;
                font-weight: bold;
                color: #333;
                margin-bottom: 5px;
            }
            .title {
                color: #666;
                margin-bottom: 15px;
            }
            .stats {
                display: flex;
                justify-content: space-around;
                margin-top: 20px;
                padding-top: 20px;
                border-top: 1px solid #eee;
            }
            .stat {
                text-align: center;
            }
            .stat-value {
                font-size: 20px;
                font-weight: bold;
                color: #667eea;
            }
            .stat-label {
                font-size: 12px;
                color: #999;
                margin-top: 5px;
            }
        </style>
    </head>
    <body>
        <div class="user-card">
            <div class="header">
                <div class="avatar">{{ avatar_letter }}</div>
            </div>
            <div class="info">
                <div class="name">{{ name }}</div>
                <div class="title">{{ title }}</div>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value">{{ posts }}</div>
                        <div class="stat-label">帖子</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{{ followers }}</div>
                        <div class="stat-label">关注者</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{{ following }}</div>
                        <div class="stat-label">关注</div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    # 准备数据
    data = {
        "name": user_data.get("name", "未知用户"),
        "title": user_data.get("title", "普通用户"),
        "avatar_letter": user_data.get("name", "U")[0].upper(),
        "posts": user_data.get("posts", 0),
        "followers": user_data.get("followers", 0),
        "following": user_data.get("following", 0)
    }
    
    # 渲染模板
    template = Template(template_str)
    html = template.render(**data)
    
    # 转换为图片
    return await self.context.html_render(html)
```

## Playwright 截图选项

### 基本截图配置

```python
async def html_render_with_options(self, html: str, options: dict = None):
    """带选项的 HTML 渲染"""
    if options is None:
        options = {}
    
    # 默认配置
    default_options = {
        "viewport": {"width": 800, "height": 600},
        "full_page": True,
        "type": "png",
        "quality": 100
    }
    
    # 合并配置
    final_options = {**default_options, **options}
    
    # 使用 html_render
    return await self.context.html_render(html, **final_options)
```

### 视口配置

```python
async def render_with_viewport(self, html: str, width: int = 800, height: int = 600):
    """自定义视口大小"""
    options = {
        "viewport": {"width": width, "height": height}
    }
    return await self.html_render_with_options(html, options)
```

### 全页面截图

```python
async def render_full_page(self, html: str):
    """全页面截图"""
    options = {
        "full_page": True
    }
    return await self.html_render_with_options(html, options)
```

### 指定区域截图

```python
async def render_element(self, html: str, selector: str):
    """截取指定元素"""
    # 先渲染页面，然后截取指定元素
    # 这需要更复杂的实现
    pass
```

### 图片格式和质量

```python
async def render_as_jpeg(self, html: str, quality: int = 80):
    """渲染为 JPEG 格式"""
    options = {
        "type": "jpeg",
        "quality": quality
    }
    return await self.html_render_with_options(html, options)
    
async def render_as_png(self, html: str):
    """渲染为 PNG 格式"""
    options = {
        "type": "png"
    }
    return await self.html_render_with_options(html, options)
```

## 实用示例

### 天气卡片

```python
async def create_weather_card(self, weather_data: dict):
    """创建天气卡片"""
    template_str = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {
                font-family: 'Segoe UI', sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
            }
            .weather-card {
                background: rgba(255, 255, 255, 0.2);
                border-radius: 20px;
                padding: 30px;
                color: white;
                max-width: 300px;
                margin: 0 auto;
                backdrop-filter: blur(10px);
            }
            .city {
                font-size: 28px;
                font-weight: bold;
                margin-bottom: 10px;
            }
            .temperature {
                font-size: 48px;
                font-weight: bold;
                margin: 20px 0;
            }
            .condition {
                font-size: 18px;
                opacity: 0.9;
                margin-bottom: 20px;
            }
            .details {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
                margin-top: 20px;
            }
            .detail-item {
                text-align: center;
            }
            .detail-value {
                font-size: 16px;
                font-weight: bold;
            }
            .detail-label {
                font-size: 12px;
                opacity: 0.8;
                margin-top: 5px;
            }
        </style>
    </head>
    <body>
        <div class="weather-card">
            <div class="city">{{ city }}</div>
            <div class="temperature">{{ temperature }}°C</div>
            <div class="condition">{{ condition }}</div>
            <div class="details">
                <div class="detail-item">
                    <div class="detail-value">{{ humidity }}%</div>
                    <div class="detail-label">湿度</div>
                </div>
                <div class="detail-item">
                    <div class="detail-value">{{ wind_speed }} km/h</div>
                    <div class="detail-label">风速</div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    template = Template(template_str)
    html = template.render(**weather_data)
    return await self.context.html_render(html)
```

### 数据图表

```python
async def create_chart(self, chart_data: dict):
    """创建数据图表"""
    template_str = """
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {
                font-family: 'Segoe UI', sans-serif;
                margin: 0;
                padding: 20px;
                background: #f5f5f5;
            }
            .chart-container {
                background: white;
                border-radius: 10px;
                padding: 20px;
                max-width: 600px;
                margin: 0 auto;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }
            .title {
                font-size: 20px;
                font-weight: bold;
                margin-bottom: 20px;
                color: #333;
            }
            canvas {
                max-height: 300px;
            }
        </style>
    </head>
    <body>
        <div class="chart-container">
            <div class="title">{{ title }}</div>
            <canvas id="chart"></canvas>
        </div>
        <script>
            const ctx = document.getElementById('chart').getContext('2d');
            new Chart(ctx, {
                type: '{{ chart_type }}',
                data: {
                    labels: {{ labels | tojson }},
                    datasets: [{
                        label: '{{ dataset_label }}',
                        data: {{ data | tojson }},
                        backgroundColor: {{ colors | tojson }},
                        borderColor: {{ border_colors | tojson }},
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        </script>
    </body>
    </html>
    """
    
    template = Template(template_str)
    html = template.render(**chart_data)
    return await self.context.html_render(html)
```

## 完整示例

```python
from astrbot.api.star import Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.messagecomponent import Image
from astrbot.core.star.star import Star
from jinja2 import Template

class HtmlToImagePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    @filter.command("card")
    async def on_card(self, event: AstrMessageEvent):
        """生成卡片图片"""
        args = event.message_str.split()[1:]
        if len(args) < 2:
            await event.plain_result("用法: /card <标题> <内容>")
            return
            
        title = args[0]
        content = " ".join(args[1:])
        
        template_str = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: 'Segoe UI', sans-serif;
                    margin: 0;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }
                .card {
                    background: white;
                    border-radius: 15px;
                    padding: 30px;
                    max-width: 400px;
                    margin: 0 auto;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
                }
                .title {
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 15px;
                    padding-bottom: 15px;
                    border-bottom: 2px solid #eee;
                }
                .content {
                    font-size: 16px;
                    color: #666;
                    line-height: 1.6;
                }
                .footer {
                    margin-top: 20px;
                    padding-top: 15px;
                    border-top: 1px solid #eee;
                    font-size: 12px;
                    color: #999;
                    text-align: right;
                }
            </style>
        </head>
        <body>
            <div class="card">
                <div class="title">{{ title }}</div>
                <div class="content">{{ content }}</div>
                <div class="footer">生成时间: {{ timestamp }}</div>
            </div>
        </body>
        </html>
        """
        
        from datetime import datetime
        data = {
            "title": title,
            "content": content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        template = Template(template_str)
        html = template.render(**data)
        
        try:
            image = await self.context.html_render(html)
            await event.plain_result(image)
        except Exception as e:
            await event.plain_result(f"生成失败: {str(e)}")
            
    @filter.command("list")
    async def on_list(self, event: AstrMessageEvent):
        """生成列表图片"""
        items = ["项目 1", "项目 2", "项目 3", "项目 4", "项目 5"]
        
        template_str = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: 'Segoe UI', sans-serif;
                    margin: 0;
                    padding: 20px;
                    background: #f5f7fa;
                }
                .list-container {
                    background: white;
                    border-radius: 10px;
                    padding: 20px;
                    max-width: 300px;
                    margin: 0 auto;
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                }
                .list-title {
                    font-size: 20px;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 15px;
                }
                .list-item {
                    padding: 10px;
                    border-bottom: 1px solid #eee;
                    display: flex;
                    align-items: center;
                }
                .list-item:last-child {
                    border-bottom: none;
                }
                .item-number {
                    width: 24px;
                    height: 24px;
                    background: #667eea;
                    color: white;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 12px;
                    font-weight: bold;
                    margin-right: 10px;
                }
                .item-text {
                    color: #666;
                    font-size: 14px;
                }
            </style>
        </head>
        <body>
            <div class="list-container">
                <div class="list-title">项目列表</div>
                {% for item in items %}
                <div class="list-item">
                    <div class="item-number">{{ loop.index }}</div>
                    <div class="item-text">{{ item }}</div>
                </div>
                {% endfor %}
            </div>
        </body>
        </html>
        """
        
        template = Template(template_str)
        html = template.render(items=items)
        
        try:
            image = await self.context.html_render(html)
            await event.plain_result(image)
        except Exception as e:
            await event.plain_result(f"生成失败: {str(e)}")
```

## 下一步

掌握了文本转图片后，你可以：
- [实现实验控制](11-session-control.md)
- [实现其他功能](12-other.md)
- [发布插件到市场](13-plugin-publish.md)