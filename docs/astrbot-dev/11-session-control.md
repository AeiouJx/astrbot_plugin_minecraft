# 会话控制

本节介绍 AstrBot 插件中的会话控制机制，包括等待用户输入、会话管理和自定义会话 ID。

## session_waiter 装饰器

### 基本用法

```python
from astrbot.api.star import Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.star import Star

class SessionControlPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
    @filter.command("confirm")
    async def on_confirm(self, event: AstrMessageEvent):
        """确认操作"""
        # 发送确认提示
        await event.plain_result("确定要执行此操作吗？(yes/no)")
        
        # 等待用户输入
        @self.session_waiter(event.session_id)
        async def wait_for_confirm(response: AstrMessageEvent):
            """等待用户确认"""
            answer = response.message_str.strip().lower()
            
            if answer in ["yes", "y", "是"]:
                await response.plain_result("操作已执行")
                # 执行操作
                await self.execute_operation()
            elif answer in ["no", "n", "否"]:
                await response.plain_result("操作已取消")
            else:
                await response.plain_result("请输入 yes 或 no")
                
        # 启动等待
        await wait_for_confirm()
```

### 带超时的等待

```python
@filter.command("timeout_example")
async def on_timeout_example(self, event: AstrMessageEvent):
    """带超时的等待示例"""
    await event.plain_result("请输入你的名字（10秒内有效）：")
    
    @self.session_waiter(event.session_id, timeout=10)
    async def wait_for_name(response: AstrMessageEvent):
        """等待用户输入名字"""
        name = response.message_str.strip()
        if name:
            await response.plain_result(f"你好，{name}！")
        else:
            await response.plain_result("输入超时或无效")
            
    # 启动等待
    await wait_for_name()
```

### 多轮对话

```python
@filter.command("survey")
async def on_survey(self, event: AstrMessageEvent):
    """多轮对话示例"""
    await event.plain_result("开始问卷调查，请依次回答以下问题。")
    
    # 第一轮
    @self.session_waiter(event.session_id)
    async def wait_for_question1(response: AstrMessageEvent):
        """等待第一个问题的回答"""
        answer1 = response.message_str.strip()
        await response.plain_result("感谢回答！第二个问题：你的年龄是？")
        
        # 第二轮
        @self.session_waiter(event.session_id)
        async def wait_for_question2(response: AstrMessageEvent):
            """等待第二个问题的回答"""
            answer2 = response.message_str.strip()
            await response.plain_result("感谢参与问卷调查！")
            
            # 处理问卷结果
            await self.process_survey(answer1, answer2)
            
        await wait_for_question2()
        
    await wait_for_question1()
```

## SessionController

### 基本用法

```python
@filter.command("session_info")
async def on_session_info(self, event: AstrMessageEvent):
    """获取会话信息"""
    # 获取 SessionController
    controller = self.context.get_session_controller(event.session_id)
    
    # 获取会话历史
    history = await controller.get_history_chains()
    
    # 显示历史消息
    history_text = "\n".join([f"{msg.role}: {msg.content}" for msg in history])
    await event.plain_result(f"会话历史:\n{history_text}")
```

### 保持会话

```python
@filter.command("keep_session")
async def on_keep_session(self, event: AstrMessageEvent):
    """保持会话"""
    controller = self.context.get_session_controller(event.session_id)
    
    # 保持会话，防止超时
    await controller.keep()
    
    await event.plain_result("会话已保持")
```

### 停止会话

```python
@filter.command("stop_session")
async def on_stop_session(self, event: AstrMessageEvent):
    """停止会话"""
    controller = self.context.get_session_controller(event.session_id)
    
    # 停止会话
    await controller.stop()
    
    await event.plain_result("会话已停止")
```

### 获取历史消息

```python
@filter.command("history")
async def on_history(self, event: AstrMessageEvent):
    """获取历史消息"""
    controller = self.context.get_session_controller(event.session_id)
    
    # 获取历史消息链
    history = await controller.get_history_chains()
    
    # 显示历史消息
    if history:
        history_text = ""
        for i, msg in enumerate(history[-10:], 1):  # 显示最近10条
            history_text += f"{i}. {msg.role}: {msg.content[:50]}...\n"
        await event.plain_result(f"最近历史消息:\n{history_text}")
    else:
        await event.plain_result("暂无历史消息")
```

## 超时处理

### 基本超时

```python
@filter.command("timeout")
async def on_timeout(self, event: AstrMessageEvent):
    """超时处理示例"""
    await event.plain_result("请输入内容（5秒后超时）：")
    
    try:
        @self.session_waiter(event.session_id, timeout=5)
        async def wait_with_timeout(response: AstrMessageEvent):
            """等待用户输入"""
            return response.message_str.strip()
            
        result = await wait_with_timeout()
        await event.plain_result(f"你输入了: {result}")
        
    except TimeoutError:
        await event.plain_result("输入超时")
```

### 自定义超时消息

```python
@filter.command("custom_timeout")
async def on_custom_timeout(self, event: AstrMessageEvent):
    """自定义超时消息"""
    await event.plain_result("请输入内容：")
    
    @self.session_waiter(
        event.session_id, 
        timeout=10,
        timeout_message="输入超时，请重新尝试"
    )
    async def wait_with_custom_timeout(response: AstrMessageEvent):
        """等待用户输入"""
        return response.message_str.strip()
        
    result = await wait_with_custom_timeout()
    if result:
        await event.plain_result(f"你输入了: {result}")
```

### 超时重试

```python
@filter.command("retry_timeout")
async def on_retry_timeout(self, event: AstrMessageEvent):
    """超时重试示例"""
    max_retries = 3
    current_retry = 0
    
    while current_retry < max_retries:
        await event.plain_result(f"请输入内容（第 {current_retry + 1} 次尝试）：")
        
        try:
            @self.session_waiter(event.session_id, timeout=5)
            async def wait_with_retry(response: AstrMessageEvent):
                """等待用户输入"""
                return response.message_str.strip()
                
            result = await wait_with_retry()
            if result:
                await event.plain_result(f"你输入了: {result}")
                return
                
        except TimeoutError:
            current_retry += 1
            if current_retry < max_retries:
                await event.plain_result("输入超时，请重试")
            else:
                await event.plain_result("已达到最大重试次数")
```

## 自定义会话 ID

### 基本自定义会话 ID

```python
@filter.command("custom_session")
async def on_custom_session(self, event: AstrMessageEvent):
    """使用自定义会话 ID"""
    # 创建自定义会话 ID
    custom_session_id = f"custom_{event.sender.id}_{event.session_id}"
    
    # 使用自定义会话 ID 等待输入
    @self.session_waiter(custom_session_id)
    async def wait_with_custom_id(response: AstrMessageEvent):
        """等待用户输入"""
        return response.message_str.strip()
        
    result = await wait_with_custom_id()
    await event.plain_result(f"你输入了: {result}")
```

### 多会话管理

```python
class MultiSessionPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.user_sessions = {}  # 用户会话状态
        
    @filter.command("start_session")
    async def on_start_session(self, event: AstrMessageEvent):
        """开始新会话"""
        user_id = event.sender.id
        
        # 创建新会话
        session_id = f"session_{user_id}_{int(time.time())}"
        self.user_sessions[user_id] = {
            "session_id": session_id,
            "status": "active",
            "created_at": time.time()
        }
        
        await event.plain_result(f"会话已创建: {session_id}")
        
    @filter.command("join_session")
    async def on_join_session(self, event: AstrMessageEvent):
        """加入现有会话"""
        args = event.message_str.split()[1:]
        if not args:
            await event.plain_result("用法: /join_session <会话ID>")
            return
            
        session_id = args[0]
        user_id = event.sender.id
        
        # 检查会话是否存在
        for uid, session in self.user_sessions.items():
            if session["session_id"] == session_id:
                # 加入会话
                await event.plain_result(f"已加入会话: {session_id}")
                
                # 等待会话消息
                @self.session_waiter(session_id)
                async def wait_for_session_message(response: AstrMessageEvent):
                    """等待会话消息"""
                    message = response.message_str.strip()
                    await response.plain_result(f"收到消息: {message}")
                    
                await wait_for_session_message()
                return
                
        await event.plain_result("未找到指定的会话")
```

### 会话持久化

```python
class PersistentSessionPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.session_storage = {}  # 会话存储
        
    async def save_session(self, session_id: str, session_data: dict):
        """保存会话数据"""
        # 使用 KV 存储保存会话
        import json
        key = f"session_{session_id}"
        value = json.dumps(session_data)
        await self.context.put_kv_data(key, value)
        
    async def load_session(self, session_id: str):
        """加载会话数据"""
        import json
        key = f"session_{session_id}"
        value = await self.context.get_kv_data(key)
        return json.loads(value) if value else None
        
    async def delete_session(self, session_id: str):
        """删除会话"""
        key = f"session_{session_id}"
        await self.context.delete_kv_data(key)
        
    @filter.command("save_current_session")
    async def on_save_current_session(self, event: AstrMessageEvent):
        """保存当前会话"""
        controller = self.context.get_session_controller(event.session_id)
        history = await controller.get_history_chains()
        
        session_data = {
            "session_id": event.session_id,
            "history": [msg.to_dict() for msg in history],
            "saved_at": time.time()
        }
        
        await self.save_session(event.session_id, session_data)
        await event.plain_result("会话已保存")
```

## 完整会话控制示例

```python
from astrbot.api.star import Context
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.star import Star
import time

class SessionControlExamplePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.user_states = {}
        
    @filter.command("interactive")
    async def on_interactive(self, event: AstrMessageEvent):
        """交互式对话示例"""
        user_id = event.sender.id
        
        # 初始化用户状态
        self.user_states[user_id] = {
            "step": 0,
            "data": {}
        }
        
        await event.plain_result("欢迎使用交互式对话！请输入你的名字：")
        
        # 第一步：获取名字
        @self.session_waiter(event.session_id, timeout=30)
        async def wait_for_name(response: AstrMessageEvent):
            """等待用户输入名字"""
            name = response.message_str.strip()
            if not name:
                await response.plain_result("名字不能为空，请重新输入：")
                await wait_for_name()
                return
                
            self.user_states[user_id]["data"]["name"] = name
            self.user_states[user_id]["step"] = 1
            
            await response.plain_result(f"你好，{name}！请输入你的年龄：")
            
            # 第二步：获取年龄
            @self.session_waiter(event.session_id, timeout=30)
            async def wait_for_age(response: AstrMessageEvent):
                """等待用户输入年龄"""
                age_str = response.message_str.strip()
                try:
                    age = int(age_str)
                    if age < 0 or age > 150:
                        raise ValueError("年龄无效")
                        
                    self.user_states[user_id]["data"]["age"] = age
                    self.user_states[user_id]["step"] = 2
                    
                    await response.plain_result(f"年龄 {age} 岁，收到！请输入你的职业：")
                    
                    # 第三步：获取职业
                    @self.session_waiter(event.session_id, timeout=30)
                    async def wait_for_job(response: AstrMessageEvent):
                        """等待用户输入职业"""
                        job = response.message_str.strip()
                        if not job:
                            await response.plain_result("职业不能为空，请重新输入：")
                            await wait_for_job()
                            return
                            
                        self.user_states[user_id]["data"]["job"] = job
                        self.user_states[user_id]["step"] = 3
                        
                        # 显示收集的信息
                        data = self.user_states[user_id]["data"]
                        summary = f"""
                        信息收集完成！
                        
                        姓名: {data['name']}
                        年龄: {data['age']}
                        职业: {data['job']}
                        
                        感谢参与！
                        """
                        
                        await response.plain_result(summary)
                        
                        # 清理状态
                        del self.user_states[user_id]
                        
                    await wait_for_job()
                    
                except ValueError:
                    await response.plain_result("请输入有效的年龄数字：")
                    await wait_for_age()
                    
            await wait_for_age()
            
        await wait_for_name()
        
    @filter.command("cancel")
    async def on_cancel(self, event: AstrMessageEvent):
        """取消当前操作"""
        user_id = event.sender.id
        
        if user_id in self.user_states:
            del self.user_states[user_id]
            await event.plain_result("操作已取消")
        else:
            await event.plain_result("没有进行中的操作")
```

## 下一步

掌握了会话控制后，你可以：
- [实现其他功能](12-other.md)
- [发布插件到市场](13-plugin-publish.md)
- [接入平台适配器](14-platform-adapter.md)