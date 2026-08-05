"""
轨道A·阶段十：工程进阶 — 设计模式练习（Q1-Q5）
Q1: 创建型模式 | Q2: 结构型模式 | Q3: 行为型模式 | Q4: SOLID原则 | Q5: Agent开发实战
"""
from __future__ import annotations

import threading
import time
import copy
import hashlib
import json
from abc import ABC, abstractmethod
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable, Optional
from dataclasses import dataclass, field

# ============================================================
# Q1: 创建型模式
# ============================================================

class Q1CreationalPatterns:
    """创建型模式：单例、工厂方法、抽象工厂、建造者、原型"""

    # ---------- 1. 单例模式（线程安全）—— 数据库连接池 ----------
    class _DBConnectionPool:
        _instance = None
        _lock = threading.Lock()

        def __new__(cls):
            if cls._instance is None:
                with cls._lock:
                    if cls._instance is None:
                        cls._instance = super().__new__(cls)
                        cls._instance._pool = []
                        cls._instance._max_size = 5
            return cls._instance

        def get_connection(self):
            if self._pool:
                return self._pool.pop()
            return f"DBConn-{id(self)}-{len(self._pool)}"

        def release_connection(self, conn):
            if len(self._pool) < self._max_size:
                self._pool.append(conn)

    def test_singleton(self):
        p1 = self._DBConnectionPool()
        p2 = self._DBConnectionPool()
        assert p1 is p2, "单例失败：两个实例不同"
        # 线程安全测试
        results = []

        def create_pool():
            results.append(self._DBConnectionPool())

        threads = [threading.Thread(target=create_pool) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert all(r is p1 for r in results), "多线程下单例失败"
        print("  ✅ 单例模式（线程安全）—— 数据库连接池")

    # ---------- 2. 工厂方法 —— 不同LLM Provider创建 ----------
    class LLMProvider(ABC):
        @abstractmethod
        def chat(self, messages: list[dict]) -> str: ...

    class OpenAIProvider(LLMProvider):
        def chat(self, messages): return f"[OpenAI] 回复: {messages[-1]['content']}"

    class ClaudeProvider(LLMProvider):
        def chat(self, messages): return f"[Claude] 回复: {messages[-1]['content']}"

    class LLMProviderFactory(ABC):
        @abstractmethod
        def create_provider(self) -> "Q1CreationalPatterns.LLMProvider": ...

    class OpenAIFactory(LLMProviderFactory):
        def create_provider(self): return self.__class__.__mro__[-2].OpenAIProvider()  # noqa

    @staticmethod
    def _make_factory(provider_name: str) -> LLMProviderFactory:
        if provider_name == "openai":
            class F(Q1CreationalPatterns.LLMProviderFactory):
                def create_provider(self): return Q1CreationalPatterns.OpenAIProvider()
            return F()
        elif provider_name == "claude":
            class F(Q1CreationalPatterns.LLMProviderFactory):
                def create_provider(self): return Q1CreationalPatterns.ClaudeProvider()
            return F()
        raise ValueError(f"Unknown provider: {provider_name}")

    def test_factory_method(self):
        factory = self._make_factory("openai")
        provider = factory.create_provider()
        result = provider.chat([{"role": "user", "content": "Hello"}])
        assert "OpenAI" in result
        factory2 = self._make_factory("claude")
        provider2 = factory2.create_provider()
        result2 = provider2.chat([{"role": "user", "content": "Hi"}])
        assert "Claude" in result2
        print("  ✅ 工厂方法 —— 不同LLM Provider创建")

    # ---------- 3. 抽象工厂 —— UI组件跨平台 ----------
    class Button(ABC):
        @abstractmethod
        def render(self) -> str: ...

    class Input(ABC):
        @abstractmethod
        def render(self) -> str: ...

    class WebButton(Button):
        def render(self): return "<button>Web Button</button>"

    class WebInput(Input):
        def render(self): return "<input type='text' />"

    class MobileButton(Button):
        def render(self): return "[Mobile Button]"

    class MobileInput(Input):
        def render(self): return "[Mobile Input Field]"

    class UIComponentFactory(ABC):
        @abstractmethod
        def create_button(self) -> Button: ...
        @abstractmethod
        def create_input(self) -> Input: ...

    class WebUIFactory(UIComponentFactory):
        def create_button(self): return Q1CreationalPatterns.WebButton()
        def create_input(self): return Q1CreationalPatterns.WebInput()

    class MobileUIFactory(UIComponentFactory):
        def create_button(self): return Q1CreationalPatterns.MobileButton()
        def create_input(self): return Q1CreationalPatterns.MobileInput()

    def test_abstract_factory(self):
        web_factory = self.WebUIFactory()
        assert "<button>" in web_factory.create_button().render()
        assert "<input" in web_factory.create_input().render()
        mobile_factory = self.MobileUIFactory()
        assert "[Mobile Button]" == mobile_factory.create_button().render()
        assert "[Mobile Input Field]" == mobile_factory.create_input().render()
        print("  ✅ 抽象工厂 —— UI组件跨平台")

    # ---------- 4. 建造者模式 —— LLM请求构建 ----------
    class LLMRequest:
        def __init__(self):
            self.model = ""
            self.messages: list[dict] = []
            self.temperature = 0.7
            self.max_tokens = 1024
            self.stream = False
            self.tools: list[dict] = []

        def __str__(self):
            return (f"LLMRequest(model={self.model}, messages={len(self.messages)}条, "
                    f"temperature={self.temperature}, max_tokens={self.max_tokens}, "
                    f"stream={self.stream}, tools={len(self.tools)}个)")

    class LLMRequestBuilder:
        def __init__(self):
            self._request = Q1CreationalPatterns.LLMRequest()

        def set_model(self, model: str):
            self._request.model = model
            return self

        def add_message(self, role: str, content: str):
            self._request.messages.append({"role": role, "content": content})
            return self

        def set_temperature(self, temp: float):
            self._request.temperature = temp
            return self

        def set_max_tokens(self, tokens: int):
            self._request.max_tokens = tokens
            return self

        def enable_stream(self):
            self._request.stream = True
            return self

        def add_tool(self, tool: dict):
            self._request.tools.append(tool)
            return self

        def build(self):
            if not self._request.model:
                raise ValueError("model is required")
            return self._request

    def test_builder(self):
        req = (self.LLMRequestBuilder()
               .set_model("gpt-4")
               .add_message("system", "You are a helpful assistant")
               .add_message("user", "Write a haiku")
               .set_temperature(0.3)
               .set_max_tokens(256)
               .enable_stream()
               .add_tool({"name": "search", "type": "function"})
               .build())
        assert req.model == "gpt-4"
        assert len(req.messages) == 2
        assert req.temperature == 0.3
        assert req.stream is True
        assert len(req.tools) == 1
        print("  ✅ 建造者模式 —— LLM请求构建")

    # ---------- 5. 原型模式 —— 配置模板克隆 ----------
    class PromptTemplate:
        def __init__(self, name: str, system_prompt: str, params: dict):
            self.name = name
            self.system_prompt = system_prompt
            self.params = params

        def clone(self) -> "Q1CreationalPatterns.PromptTemplate":
            return copy.deepcopy(self)

        def __str__(self):
            return f"PromptTemplate(name={self.name}, params={self.params})"

    def test_prototype(self):
        base = self.PromptTemplate("coder", "You are a code expert", {"lang": "python", "level": "senior"})
        clone1 = base.clone()
        clone1.name = "coder-junior"
        clone1.params["level"] = "junior"
        # 原始对象不受影响（深拷贝）
        assert base.name == "coder"
        assert base.params["level"] == "senior"
        assert clone1.params["level"] == "junior"
        assert clone1.params["lang"] == "python"
        print("  ✅ 原型模式 —— 配置模板克隆")

    def run(self):
        print("=" * 60)
        print("Q1: 创建型模式（单例 / 工厂方法 / 抽象工厂 / 建造者 / 原型）")
        print("=" * 60)
        self.test_singleton()
        self.test_factory_method()
        self.test_abstract_factory()
        self.test_builder()
        self.test_prototype()
        print()


# ============================================================
# Q2: 结构型模式
# ============================================================

class Q2StructuralPatterns:
    """结构型模式：适配器、装饰器、代理、外观、组合"""

    # ---------- 1. 适配器模式 —— 统一不同AI API接口 ----------
    class AIProvider(ABC):
        @abstractmethod
        def generate(self, prompt: str) -> str: ...

    class _OpenAISDK:
        """第三方SDK，接口不同"""
        def completions_create(self, prompt: str, model: str = "gpt-4") -> str:
            return f"OpenAI says: {prompt}"

    class _GeminiSDK:
        def generate_content(self, prompt: str) -> str:
            return f"Gemini says: {prompt}"

    class OpenAIAdapter(AIProvider):
        def __init__(self):
            self._sdk = Q2StructuralPatterns._OpenAISDK()

        def generate(self, prompt: str) -> str:
            return self._sdk.completions_create(prompt)

    class GeminiAdapter(AIProvider):
        def __init__(self):
            self._sdk = Q2StructuralPatterns._GeminiSDK()

        def generate(self, prompt: str) -> str:
            return self._sdk.generate_content(prompt)

    def test_adapter(self):
        providers: list[Q2StructuralPatterns.AIProvider] = [
            self.OpenAIAdapter(),
            self.GeminiAdapter(),
        ]
        results = [p.generate("Hello") for p in providers]
        assert "OpenAI" in results[0]
        assert "Gemini" in results[1]
        # 统一接口调用
        for p in providers:
            assert isinstance(p.generate("test"), str)
        print("  ✅ 适配器模式 —— 统一不同AI API接口")

    # ---------- 2. 装饰器模式 —— 为LLM调用添加功能 ----------
    class LLMService(ABC):
        @abstractmethod
        def call(self, prompt: str) -> str: ...

    class BaseLLMService(LLMService):
        def call(self, prompt: str) -> str:
            return f"LLM response for: {prompt}"

    class LLMServiceDecorator(LLMService):
        def __init__(self, wrapped: Q2StructuralPatterns.LLMService):
            self._wrapped = wrapped

        def call(self, prompt: str) -> str:
            return self._wrapped.call(prompt)

    class LoggingDecorator(LLMServiceDecorator):
        def call(self, prompt: str) -> str:
            result = self._wrapped.call(prompt)
            return f"[LOGGED] {result}"

    class CachingDecorator(LLMServiceDecorator):
        def __init__(self, wrapped):
            super().__init__(wrapped)
            self._cache: dict[str, str] = {}

        def call(self, prompt: str) -> str:
            if prompt in self._cache:
                return f"[CACHED] {self._cache[prompt]}"
            result = self._wrapped.call(prompt)
            self._cache[prompt] = result
            return result

    class RateLimitDecorator(LLMServiceDecorator):
        def __init__(self, wrapped, max_calls: int = 3):
            super().__init__(wrapped)
            self._max_calls = max_calls
            self._call_count = 0

        def call(self, prompt: str) -> str:
            self._call_count += 1
            if self._call_count > self._max_calls:
                return "[RATE LIMITED] Too many calls"
            return self._wrapped.call(prompt)

    def test_decorator(self):
        # 链式装饰：缓存 -> 日志 -> 限流 -> 基础服务
        service = self.CachingDecorator(
            self.LoggingDecorator(
                self.RateLimitDecorator(self.BaseLLMService(), max_calls=5)
            )
        )
        r1 = service.call("Hello")
        r2 = service.call("Hello")  # 应命中缓存
        assert "LLM response" in r1
        assert "CACHED" in r2
        print("  ✅ 装饰器模式 —— LLM调用添加日志/缓存/限流")

    # ---------- 3. 代理模式 —— 懒加载/缓存/权限控制 ----------
    class ExpensiveModel:
        def __init__(self, name: str):
            self.name = name
            self.loaded = False
            time.sleep(0.01)  # 模拟加载耗时
            self.loaded = True

        def infer(self, text: str) -> str:
            return f"[{self.name}] inference: {text}"

    class ModelProxy:
        """代理：懒加载 + 缓存 + 权限"""
        def __init__(self, name: str, allowed_users: set[str]):
            self._name = name
            self._model: Optional[Q2StructuralPatterns.ExpensiveModel] = None
            self._cache: dict[str, str] = {}
            self._allowed = allowed_users

        def infer(self, text: str, user: str = "admin") -> str:
            if user not in self._allowed:
                return f"[DENIED] {user} has no access to {self._name}"
            if text in self._cache:
                return f"[CACHED] {self._cache[text]}"
            if self._model is None:
                self._model = Q2StructuralPatterns.ExpensiveModel(self._name)
            result = self._model.infer(text)
            self._cache[text] = result
            return result

    def test_proxy(self):
        proxy = self.ModelProxy("llama-70b", allowed_users={"alice", "bob"})
        # 权限控制
        denied = proxy.infer("test", user="eve")
        assert "DENIED" in denied
        # 懒加载 + 正常调用
        r1 = proxy.infer("hello", user="alice")
        assert "llama-70b" in r1
        # 缓存
        r2 = proxy.infer("hello", user="alice")
        assert "CACHED" in r2
        print("  ✅ 代理模式 —— 懒加载/缓存/权限控制")

    # ---------- 4. 外观模式 —— 简化复杂子系统 ----------
    class _CPU:
        def freeze(self): return "CPU frozen"
        def jump(self, addr): return f"CPU jump to {addr}"

    class _Memory:
        def load(self, addr, data): return f"Memory loaded {data} at {addr}"

    class _Disk:
        def read(self, sector): return f"Disk read sector {sector}"

    class ComputerFacade:
        """外观：一键启动电脑"""
        def __init__(self):
            self.cpu = Q2StructuralPatterns._CPU()
            self.memory = Q2StructuralPatterns._Memory()
            self.disk = Q2StructuralPatterns._Disk()

        def start(self) -> str:
            steps = [
                self.cpu.freeze(),
                self.memory.load(0, "bootloader"),
                self.disk.read("boot"),
                self.cpu.jump("bootloader"),
            ]
            return " → ".join(steps)

    def test_facade(self):
        computer = self.ComputerFacade()
        result = computer.start()
        assert "CPU frozen" in result
        assert "Memory loaded" in result
        assert "Disk read" in result
        assert "bootloader" in result
        print("  ✅ 外观模式 —— 简化电脑启动子系统")

    # ---------- 5. 组合模式 —— 文件系统树 ----------
    class FileSystemNode(ABC):
        @abstractmethod
        def get_size(self) -> int: ...
        @abstractmethod
        def display(self, indent: int = 0) -> str: ...

    class FileNode(FileSystemNode):
        def __init__(self, name: str, size: int):
            self.name = name
            self.size = size

        def get_size(self): return self.size

        def display(self, indent: int = 0):
            return "  " * indent + f"📄 {self.name} ({self.size}KB)"

    class FolderNode(FileSystemNode):
        def __init__(self, name: str):
            self.name = name
            self.children: list[Q2StructuralPatterns.FileSystemNode] = []

        def add(self, node: Q2StructuralPatterns.FileSystemNode):
            self.children.append(node)
            return self

        def get_size(self):
            return sum(c.get_size() for c in self.children)

        def display(self, indent: int = 0):
            lines = ["  " * indent + f"📁 {self.name}/"]
            for c in self.children:
                lines.append(c.display(indent + 1))
            return "\n".join(lines)

    def test_composite(self):
        root = self.FolderNode("project")
        src = self.FolderNode("src").add(self.FileNode("main.py", 10)).add(self.FileNode("utils.py", 5))
        root.add(src).add(self.FileNode("README.md", 2))
        assert root.get_size() == 17
        assert "📁 project/" in root.display()
        assert "📄 main.py (10KB)" in root.display()
        print("  ✅ 组合模式 —— 文件系统树")

    def run(self):
        print("=" * 60)
        print("Q2: 结构型模式（适配器 / 装饰器 / 代理 / 外观 / 组合）")
        print("=" * 60)
        self.test_adapter()
        self.test_decorator()
        self.test_proxy()
        self.test_facade()
        self.test_composite()
        print()


# ============================================================
# Q3: 行为型模式
# ============================================================

class Q3BehavioralPatterns:
    """行为型模式：策略、观察者、责任链、命令、状态"""

    # ---------- 1. 策略模式 —— 不同推荐算法切换 ----------
    class RecommendationStrategy(ABC):
        @abstractmethod
        def recommend(self, items: list[str], user_history: list[str]) -> list[str]: ...

    class PopularityStrategy(RecommendationStrategy):
        def recommend(self, items, user_history):
            return sorted(items, reverse=True)[:3]

    class ContentBasedStrategy(RecommendationStrategy):
        def recommend(self, items, user_history):
            # 基于历史中关键词匹配
            keywords = set("".join(user_history))
            return sorted(items, key=lambda x: len(set(x) & keywords), reverse=True)[:3]

    class CollaborativeStrategy(RecommendationStrategy):
        def recommend(self, items, user_history):
            # 简化：推荐未看过的
            return [i for i in items if i not in user_history][:3]

    class Recommender:
        def __init__(self, strategy: Q3BehavioralPatterns.RecommendationStrategy):
            self._strategy = strategy

        def set_strategy(self, strategy: Q3BehavioralPatterns.RecommendationStrategy):
            self._strategy = strategy

        def recommend(self, items, user_history):
            return self._strategy.recommend(items, user_history)

    def test_strategy(self):
        items = ["AI课程", "Python教程", "Web开发", "数据科学", "机器学习"]
        history = ["Python教程", "数据科学"]
        rec = self.Recommender(self.PopularityStrategy())
        r1 = rec.recommend(items, history)
        assert len(r1) == 3
        rec.set_strategy(self.CollaborativeStrategy())
        r2 = rec.recommend(items, history)
        assert "Python教程" not in r2  # 已看过的不推荐
        rec.set_strategy(self.ContentBasedStrategy())
        r3 = rec.recommend(items, history)
        assert len(r3) == 3
        print("  ✅ 策略模式 —— 不同推荐算法切换")

    # ---------- 2. 观察者模式 —— 事件总线 ----------
    class EventBus:
        def __init__(self):
            self._subscribers: dict[str, list[Callable]] = {}

        def subscribe(self, event_type: str, handler: Callable):
            self._subscribers.setdefault(event_type, []).append(handler)

        def publish(self, event_type: str, data: Any):
            for handler in self._subscribers.get(event_type, []):
                handler(data)

    def test_observer(self):
        bus = self.EventBus()
        log: list[str] = []
        bus.subscribe("user.created", lambda d: log.append(f"Email sent to {d['email']}"))
        bus.subscribe("user.created", lambda d: log.append(f"Analytics tracked: {d['user_id']}"))
        bus.subscribe("user.deleted", lambda d: log.append(f"Cleanup for {d['user_id']}"))
        bus.publish("user.created", {"user_id": 1, "email": "test@test.com"})
        bus.publish("user.deleted", {"user_id": 1})
        assert len(log) == 3
        assert "Email sent" in log[0]
        assert "Analytics tracked" in log[1]
        assert "Cleanup" in log[2]
        print("  ✅ 观察者模式 —— 事件总线")

    # ---------- 3. 责任链模式 —— 请求处理链 ----------
    class Handler(ABC):
        def __init__(self):
            self._next: Optional[Q3BehavioralPatterns.Handler] = None

        def set_next(self, handler: "Q3BehavioralPatterns.Handler"):
            self._next = handler
            return handler

        @abstractmethod
        def handle(self, request: dict) -> str: ...

    class AuthHandler(Handler):
        def handle(self, request):
            if not request.get("token"):
                return "❌ Auth failed: no token"
            if self._next:
                return self._next.handle(request)
            return "✅ Auth passed"

    class RateLimitHandler(Handler):
        def __init__(self):
            super().__init__()
            self._count = 0

        def handle(self, request):
            self._count += 1
            if self._count > 3:
                return "❌ Rate limit exceeded"
            if self._next:
                return self._next.handle(request)
            return "✅ Rate limit passed"

    class LoggingHandler(Handler):
        def handle(self, request):
            result = "✅ Request passed"
            if self._next:
                result = self._next.handle(request)
            return f"[LOG] {request.get('path', '/')} → {result}"

    def test_chain_of_responsibility(self):
        auth = self.AuthHandler()
        rate = self.RateLimitHandler()
        logging = self.LoggingHandler()
        auth.set_next(rate).set_next(logging)

        # 无token
        r1 = auth.handle({"path": "/api/data"})
        assert "Auth failed" in r1

        # 有token，正常
        r2 = auth.handle({"path": "/api/data", "token": "abc"})
        assert "LOG" in r2
        assert "passed" in r2

        # 超过限流
        auth.handle({"path": "/api/data", "token": "abc"})
        auth.handle({"path": "/api/data", "token": "abc"})
        r5 = auth.handle({"path": "/api/data", "token": "abc"})
        assert "Rate limit" in r5
        print("  ✅ 责任链模式 —— 请求处理链（认证→限流→日志）")

    # ---------- 4. 命令模式 —— 撤销/重做操作 ----------
    class Command(ABC):
        @abstractmethod
        def execute(self) -> str: ...
        @abstractmethod
        def undo(self) -> str: ...

    class TextEditor:
        def __init__(self):
            self.text = ""

        def insert(self, text: str): self.text += text
        def delete(self, n: int):
            deleted = self.text[-n:]
            self.text = self.text[:-n]
            return deleted

    class InsertCommand(Command):
        def __init__(self, editor: Q3BehavioralPatterns.TextEditor, text: str):
            self._editor = editor
            self._text = text

        def execute(self):
            self._editor.insert(self._text)
            return f"Inserted '{self._text}'"

        def undo(self):
            self._editor.delete(len(self._text))
            return f"Undid insert '{self._text}'"

    class CommandHistory:
        def __init__(self):
            self._undo_stack: list[Q3BehavioralPatterns.Command] = []
            self._redo_stack: list[Q3BehavioralPatterns.Command] = []

        def execute(self, cmd: Q3BehavioralPatterns.Command):
            result = cmd.execute()
            self._undo_stack.append(cmd)
            self._redo_stack.clear()
            return result

        def undo(self):
            if not self._undo_stack:
                return "Nothing to undo"
            cmd = self._undo_stack.pop()
            result = cmd.undo()
            self._redo_stack.append(cmd)
            return result

    def test_command(self):
        editor = self.TextEditor()
        history = self.CommandHistory()
        history.execute(self.InsertCommand(editor, "Hello "))
        history.execute(self.InsertCommand(editor, "World"))
        assert editor.text == "Hello World"
        history.undo()
        assert editor.text == "Hello "
        history.undo()
        assert editor.text == ""
        print("  ✅ 命令模式 —— 撤销/重做文本编辑")

    # ---------- 5. 状态模式 —— 订单状态机 ----------
    class OrderState(ABC):
        @abstractmethod
        def next(self, order: "Q3BehavioralPatterns.Order") -> str: ...
        @abstractmethod
        def cancel(self, order: "Q3BehavioralPatterns.Order") -> str: ...

    class PendingState(OrderState):
        def next(self, order):
            order.state = Q3BehavioralPatterns.PaidState()
            return "Order paid"
        def cancel(self, order):
            order.state = Q3BehavioralPatterns.CancelledState()
            return "Order cancelled from pending"

    class PaidState(OrderState):
        def next(self, order):
            order.state = Q3BehavioralPatterns.ShippedState()
            return "Order shipped"
        def cancel(self, order):
            order.state = Q3BehavioralPatterns.CancelledState()
            return "Order refunded and cancelled"

    class ShippedState(OrderState):
        def next(self, order):
            order.state = Q3BehavioralPatterns.DeliveredState()
            return "Order delivered"
        def cancel(self, order):
            return "Cannot cancel shipped order"

    class DeliveredState(OrderState):
        def next(self, order):
            return "Order already delivered"
        def cancel(self, order):
            return "Cannot cancel delivered order"

    class CancelledState(OrderState):
        def next(self, order):
            return "Order is cancelled"
        def cancel(self, order):
            return "Order already cancelled"

    class Order:
        def __init__(self, order_id: str):
            self.id = order_id
            self.state: Q3BehavioralPatterns.OrderState = Q3BehavioralPatterns.PendingState()

        def pay(self): return self.state.next(self)
        def ship(self): return self.state.next(self)
        def deliver(self): return self.state.next(self)
        def cancel(self): return self.state.cancel(self)

    def test_state(self):
        order = self.Order("ORD-001")
        assert "paid" in order.pay()
        assert "shipped" in order.ship()
        assert "delivered" in order.deliver()
        assert "already delivered" in order.deliver()

        order2 = self.Order("ORD-002")
        assert "cancelled" in order2.cancel()
        assert "already cancelled" in order2.cancel()
        print("  ✅ 状态模式 —— 订单状态机（待付→已付→已发→已送达）")

    def run(self):
        print("=" * 60)
        print("Q3: 行为型模式（策略 / 观察者 / 责任链 / 命令 / 状态）")
        print("=" * 60)
        self.test_strategy()
        self.test_observer()
        self.test_chain_of_responsibility()
        self.test_command()
        self.test_state()
        print()


# ============================================================
# Q4: SOLID原则与模式选择
# ============================================================

class Q4SOLIDPrinciples:
    """SOLID原则：每个原则写违反→修正对比，展示模式选择"""

    # ---------- 1. SRP 单一职责 ----------
    def test_srp(self):
        # ❌ 违反：一个类既处理用户数据又发邮件
        class BadUserService:
            def __init__(self):
                self.users = {}
            def create_user(self, name, email):
                self.users[email] = name
                # 直接发邮件 —— 职责混乱
                return f"User {name} created, email sent to {email}"

        # ✅ 修正：分离用户管理和通知
        class UserRepository:
            def __init__(self):
                self.users = {}
            def save(self, name, email):
                self.users[email] = name
                return email

        class EmailService:
            def send(self, to, subject, body):
                return f"Email sent to {to}: {subject}"

        class GoodUserService:
            def __init__(self, repo: UserRepository, emailer: EmailService):
                self.repo = repo
                self.emailer = emailer
            def create_user(self, name, email):
                self.repo.save(name, email)
                self.emailer.send(email, "Welcome", f"Hello {name}")
                return f"User {name} created"

        bad = BadUserService()
        assert "email sent" in bad.create_user("Alice", "a@b.com")
        good = GoodUserService(UserRepository(), EmailService())
        assert "created" in good.create_user("Bob", "b@c.com")
        print("  ✅ SRP 单一职责 —— 用户管理 vs 邮件通知分离")

    # ---------- 2. OCP 开闭原则 ----------
    def test_ocp(self):
        # ❌ 违反：每加一种折扣就要改calculate_price
        class BadPriceCalculator:
            def calculate(self, price: float, discount_type: str) -> float:
                if discount_type == "none":
                    return price
                elif discount_type == "vip":
                    return price * 0.8
                # 新增折扣类型需要修改此类

        # ✅ 修正：用策略模式，新增折扣不需修改原有代码
        class DiscountStrategy(ABC):
            @abstractmethod
            def apply(self, price: float) -> float: ...

        class NoDiscount(DiscountStrategy):
            def apply(self, price): return price

        class VIPDiscount(DiscountStrategy):
            def apply(self, price): return price * 0.8

        class SuperVIPDiscount(DiscountStrategy):
            def apply(self, price): return price * 0.6  # 新增，无需修改其他类

        class GoodPriceCalculator:
            def __init__(self, strategy: DiscountStrategy):
                self._strategy = strategy
            def calculate(self, price: float) -> float:
                return self._strategy.apply(price)

        calc = GoodPriceCalculator(SuperVIPDiscount())
        assert calc.calculate(100) == 60.0
        calc2 = GoodPriceCalculator(NoDiscount())
        assert calc2.calculate(100) == 100.0
        print("  ✅ OCP 开闭原则 —— 策略模式实现折扣扩展")

    # ---------- 3. LSP 里氏替换 ----------
    def test_lsp(self):
        # ❌ 违反：子类改变了父类行为契约
        class Bird:
            def fly(self) -> str: return "flying"

        class Penguin(Bird):
            def fly(self) -> str: raise Exception("Penguins can't fly!")

        # ✅ 修正：用接口隔离飞行能力
        class BirdFixed:
            def eat(self) -> str: return "eating"

        class FlyingBird(BirdFixed):
            def fly(self) -> str: return "flying"

        class Sparrow(FlyingBird):
            pass

        class PenguinFixed(BirdFixed):
            def swim(self) -> str: return "swimming"

        sparrow = Sparrow()
        assert sparrow.fly() == "flying"
        assert sparrow.eat() == "eating"
        penguin = PenguinFixed()
        assert penguin.eat() == "eating"
        assert penguin.swim() == "swimming"
        # PenguinFixed 不能替换 FlyingBird，但它也不应该能替换
        print("  ✅ LSP 里氏替换 —— 飞行能力接口隔离")

    # ---------- 4. ISP 接口隔离 ----------
    def test_isp(self):
        # ❌ 违反：胖接口强迫实现不需要的方法
        class BadWorkerInterface(ABC):
            @abstractmethod
            def work(self) -> str: ...
            @abstractmethod
            def eat(self) -> str: ...
            @abstractmethod
            def sleep(self) -> str: ...

        # 机器人worker被迫实现eat和sleep
        class BadRobotWorker(BadWorkerInterface):
            def work(self): return "working"
            def eat(self): return "robots don't eat"  # 无意义
            def sleep(self): return "robots don't sleep"  # 无意义

        # ✅ 修正：接口拆分
        class Workable(ABC):
            @abstractmethod
            def work(self) -> str: ...

        class Eatable(ABC):
            @abstractmethod
            def eat(self) -> str: ...

        class HumanWorker(Workable, Eatable):
            def work(self): return "human working"
            def eat(self): return "human eating"

        class RobotWorker(Workable):
            def work(self): return "robot working"
            # 不需要实现eat

        human = HumanWorker()
        robot = RobotWorker()
        assert human.work() == "human working"
        assert human.eat() == "human eating"
        assert robot.work() == "robot working"
        print("  ✅ ISP 接口隔离 —— Workable/Eatable分离")

    # ---------- 5. DIP 依赖倒置 ----------
    def test_dip(self):
        # ❌ 违反：高层直接依赖低层具体实现
        class BadMySQLDB:
            def query(self, sql): return f"MySQL: {sql}"

        class BadUserService:
            def __init__(self):
                self.db = BadMySQLDB()  # 直接依赖具体类
            def get_user(self, uid):
                return self.db.query(f"SELECT * FROM users WHERE id={uid}")

        # ✅ 修正：高层依赖抽象接口
        class DatabaseInterface(ABC):
            @abstractmethod
            def query(self, sql: str) -> str: ...

        class MySQLDB(DatabaseInterface):
            def query(self, sql): return f"MySQL: {sql}"

        class PostgreSQLDB(DatabaseInterface):
            def query(self, sql): return f"PostgreSQL: {sql}"

        class GoodUserService:
            def __init__(self, db: DatabaseInterface):  # 依赖抽象
                self.db = db
            def get_user(self, uid):
                return self.db.query(f"SELECT * FROM users WHERE id={uid}")

        svc = GoodUserService(MySQLDB())
        assert "MySQL" in svc.get_user(1)
        svc2 = GoodUserService(PostgreSQLDB())  # 切换数据库不改业务代码
        assert "PostgreSQL" in svc2.get_user(1)
        print("  ✅ DIP 依赖倒置 —— 依赖抽象接口而非具体实现")

    # ---------- 模式选择指南 ----------
    def test_pattern_selection(self):
        """展示如何根据场景选择合适的设计模式"""
        scenarios = {
            "需要唯一实例": "单例模式",
            "需要创建不同类型对象": "工厂方法/抽象工厂",
            "需要逐步构建复杂对象": "建造者模式",
            "需要统一不同接口": "适配器模式",
            "需要动态添加功能": "装饰器模式",
            "需要控制访问": "代理模式",
            "需要简化复杂子系统": "外观模式",
            "需要树形结构": "组合模式",
            "需要算法切换": "策略模式",
            "需要事件通知": "观察者模式",
            "需要多步处理": "责任链模式",
            "需要撤销操作": "命令模式",
            "需要状态机": "状态模式",
        }
        assert len(scenarios) == 13
        assert scenarios["需要唯一实例"] == "单例模式"
        assert scenarios["需要算法切换"] == "策略模式"
        print("  ✅ 模式选择指南 —— 13种场景→模式映射")

    def run(self):
        print("=" * 60)
        print("Q4: SOLID原则与模式选择（SRP/OCP/LSP/ISP/DIP）")
        print("=" * 60)
        self.test_srp()
        self.test_ocp()
        self.test_lsp()
        self.test_isp()
        self.test_dip()
        self.test_pattern_selection()
        print()


# ============================================================
# Q5: Agent开发中的设计模式实战
# ============================================================

class Q5AgentPatterns:
    """Agent开发实战模式：工具注册器、ReAct循环、记忆管理、多Agent协作、工具链编排"""

    # ---------- 1. 工具注册器模式 ----------
    class ToolRegistry:
        """类似Function Calling的工具注册系统"""
        def __init__(self):
            self._tools: dict[str, dict] = {}

        def register(self, name: str, description: str, parameters: dict, func: Callable):
            self._tools[name] = {
                "name": name,
                "description": description,
                "parameters": parameters,
                "func": func,
            }
            return self

        def get_tool_schemas(self) -> list[dict]:
            """生成Function Calling格式的schema"""
            return [
                {"type": "function", "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                }}
                for t in self._tools.values()
            ]

        def execute(self, name: str, **kwargs) -> Any:
            if name not in self._tools:
                raise ValueError(f"Unknown tool: {name}")
            return self._tools[name]["func"](**kwargs)

        def list_tools(self) -> list[str]:
            return list(self._tools.keys())

    def test_tool_registry(self):
        registry = self.ToolRegistry()
        registry.register(
            name="search_web",
            description="Search the web for information",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}},
            func=lambda query: f"Search results for: {query}"
        )
        registry.register(
            name="calculate",
            description="Perform a calculation",
            parameters={"type": "object", "properties": {"expression": {"type": "string"}}},
            func=lambda expression: str(eval(expression))  # demo only
        )
        schemas = registry.get_tool_schemas()
        assert len(schemas) == 2
        assert schemas[0]["function"]["name"] == "search_web"
        result = registry.execute("search_web", query="Python design patterns")
        assert "Python design patterns" in result
        calc_result = registry.execute("calculate", expression="2+3")
        assert calc_result == "5"
        assert "search_web" in registry.list_tools()
        print("  ✅ 工具注册器模式 —— Function Calling工具注册与执行")

    # ---------- 2. ReAct循环模式 ----------
    class ReActAgent:
        """ReAct: Thought → Action → Observation 循环"""
        def __init__(self, max_steps: int = 5):
            self.max_steps = max_steps
            self.history: list[dict] = []

        def think(self, thought: str) -> dict:
            step = {"type": "thought", "content": thought}
            self.history.append(step)
            return step

        def act(self, tool: str, args: dict) -> dict:
            step = {"type": "action", "tool": tool, "args": args}
            self.history.append(step)
            return step

        def observe(self, result: str) -> dict:
            step = {"type": "observation", "content": result}
            self.history.append(step)
            return step

        def answer(self, answer: str) -> dict:
            step = {"type": "answer", "content": answer}
            self.history.append(step)
            return step

        def run(self, query: str, tool_executor: Callable) -> str:
            """执行ReAct循环"""
            for i in range(self.max_steps):
                if i == 0:
                    self.think(f"I need to answer: {query}")
                    self.act("search", {"query": query})
                    obs = tool_executor("search", {"query": query})
                    self.observe(obs)
                    if "found" in obs.lower() or "result" in obs.lower():
                        self.think("I have enough information to answer")
                        self.answer(f"Based on search: {obs}")
                        break
                else:
                    self.answer(f"After {i+1} steps, here's my answer")
                    break
            return self.history[-1]["content"]

    def test_react(self):
        agent = self.ReActAgent(max_steps=3)
        def mock_executor(tool, args):
            return f"Found results for {args.get('query', '')}"

        result = agent.run("What is Python?", mock_executor)
        assert "Based on search" in result
        # 验证Thought → Action → Observation → Answer序列
        types = [s["type"] for s in agent.history]
        assert "thought" in types
        assert "action" in types
        assert "observation" in types
        assert "answer" in types
        print("  ✅ ReAct循环模式 —— Thought→Action→Observation→Answer")

    # ---------- 3. 记忆管理模式 ----------
    class MemoryManager:
        """短期/长期记忆管理"""
        def __init__(self, short_term_limit: int = 5, long_term_limit: int = 50):
            self._short_term: OrderedDict = OrderedDict()
            self._long_term: list[dict] = []
            self._short_term_limit = short_term_limit
            self._long_term_limit = long_term_limit

        def add_short_term(self, key: str, value: str):
            if key in self._short_term:
                self._short_term.move_to_end(key)
            self._short_term[key] = value
            while len(self._short_term) > self._short_term_limit:
                # LRU淘汰，转移到长期记忆
                old_key, old_val = self._short_term.popitem(last=False)
                self._long_term.append({"key": old_key, "value": old_val})
                while len(self._long_term) > self._long_term_limit:
                    self._long_term.pop(0)

        def get_short_term(self, key: str) -> Optional[str]:
            if key in self._short_term:
                self._short_term.move_to_end(key)
                return self._short_term[key]
            return None

        def get_context(self) -> str:
            """获取上下文：短期记忆 + 相关长期记忆"""
            st = "\n".join(f"[ST] {v}" for v in self._short_term.values())
            lt = "\n".join(f"[LT] {m['value']}" for m in self._long_term[-3:])
            return f"{st}\n{lt}" if lt else st

        def consolidate(self):
            """将短期记忆整合到长期记忆"""
            for k, v in self._short_term.items():
                self._long_term.append({"key": k, "value": v})
            self._short_term.clear()
            while len(self._long_term) > self._long_term_limit:
                self._long_term.pop(0)

    def test_memory_manager(self):
        mem = self.MemoryManager(short_term_limit=3, long_term_limit=10)
        mem.add_short_term("msg1", "Hello")
        mem.add_short_term("msg2", "World")
        mem.add_short_term("msg3", "!")
        # 添加第4条，msg1应被淘汰到长期记忆
        mem.add_short_term("msg4", "New message")
        assert mem.get_short_term("msg4") == "New message"
        assert mem.get_short_term("msg1") is None  # 已转移到长期
        context = mem.get_context()
        assert "New message" in context
        assert "LT" in context  # 长期记忆
        mem.consolidate()
        assert len(mem._short_term) == 0
        print("  ✅ 记忆管理模式 —— 短期LRU淘汰 + 长期记忆整合")

    # ---------- 4. 多Agent协作模式 ----------
    class Agent(ABC):
        def __init__(self, name: str, role: str):
            self.name = name
            self.role = role

        @abstractmethod
        def process(self, task: str) -> str: ...

    class ResearcherAgent(Agent):
        def process(self, task): return f"[{self.name}] Research on: {task}"

    class WriterAgent(Agent):
        def process(self, task): return f"[{self.name}] Article about: {task}"

    class ReviewerAgent(Agent):
        def process(self, task): return f"[{self.name}] Approved: {task}"

    class HubSpokeOrchestrator:
        """Hub-Spoke模式：中心调度多个Agent"""
        def __init__(self):
            self.agents: list[Q5AgentPatterns.Agent] = []

        def register(self, agent: Q5AgentPatterns.Agent):
            self.agents.append(agent)
            return self

        def run(self, task: str) -> list[str]:
            return [a.process(task) for a in self.agents]

    class PipelineOrchestrator:
        """Pipeline模式：顺序执行"""
        def __init__(self):
            self.stages: list[Q5AgentPatterns.Agent] = []

        def add_stage(self, agent: Q5AgentPatterns.Agent):
            self.stages.append(agent)
            return self

        def run(self, task: str) -> str:
            current = task
            results = []
            for stage in self.stages:
                current = stage.process(current)
                results.append(current)
            return " → ".join(results)

    class DebateOrchestrator:
        """Debate模式：多Agent辩论达成共识"""
        def __init__(self, max_rounds: int = 3):
            self.max_rounds = max_rounds
            self.participants: list[Q5AgentPatterns.Agent] = []

        def add(self, agent: Q5AgentPatterns.Agent):
            self.participants.append(agent)
            return self

        def run(self, topic: str) -> str:
            opinions = []
            for r in range(self.max_rounds):
                round_opinions = [p.process(f"Round {r+1}: {topic}") for p in self.participants]
                opinions.extend(round_opinions)
            return f"Consensus reached after {self.max_rounds} rounds: {len(opinions)} opinions"

    def test_multi_agent(self):
        # Hub-Spoke
        hub = self.HubSpokeOrchestrator()
        hub.register(self.ResearcherAgent("R1", "researcher"))
        hub.register(self.WriterAgent("W1", "writer"))
        results = hub.run("AI Design Patterns")
        assert len(results) == 2
        assert "Research" in results[0]

        # Pipeline
        pipeline = self.PipelineOrchestrator()
        pipeline.add_stage(self.ResearcherAgent("R1", "researcher"))
        pipeline.add_stage(self.WriterAgent("W1", "writer"))
        pipeline.add_stage(self.ReviewerAgent("V1", "reviewer"))
        result = pipeline.run("AI Topics")
        assert "Research" in result
        assert "Article" in result
        assert "Approved" in result

        # Debate
        debate = self.DebateOrchestrator(max_rounds=2)
        debate.add(self.ResearcherAgent("R1", "researcher"))
        debate.add(self.WriterAgent("W1", "writer"))
        debate_result = debate.run("Best AI framework")
        assert "Consensus" in debate_result
        assert "2 rounds" in debate_result
        print("  ✅ 多Agent协作模式 —— Hub-Spoke / Pipeline / Debate")

    # ---------- 5. 工具链编排模式 ----------
    class ToolChain:
        """工具链编排：按顺序执行多个工具，传递中间结果"""
        def __init__(self):
            self._steps: list[tuple[str, Callable]] = []

        def add_step(self, name: str, handler: Callable):
            self._steps.append((name, handler))
            return self

        def execute(self, initial_input: Any) -> dict:
            results = {}
            current = initial_input
            for name, handler in self._steps:
                current = handler(current)
                results[name] = current
            return results

    class ParallelToolExecutor:
        """并行执行多个工具，聚合结果"""
        def __init__(self):
            self._tools: list[tuple[str, Callable]] = []

        def add(self, name: str, func: Callable):
            self._tools.append((name, func))
            return self

        def execute(self, input_data: Any) -> dict:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            results = {}
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(f, input_data): name for name, f in self._tools}
                for future in as_completed(futures):
                    name = futures[future]
                    results[name] = future.result()
            return results

    def test_tool_chain(self):
        # 串行工具链
        chain = self.ToolChain()
        chain.add_step("fetch", lambda x: f"fetched:{x}")
        chain.add_step("parse", lambda x: x.replace("fetched:", "parsed:"))
        chain.add_step("transform", lambda x: x.upper())
        results = chain.execute("data")
        assert results["fetch"] == "fetched:data"
        assert results["parse"] == "parsed:data"
        assert results["transform"] == "PARSED:DATA"

        # 并行执行
        parallel = self.ParallelToolExecutor()
        parallel.add("search", lambda x: f"search:{x}")
        parallel.add("analyze", lambda x: f"analyze:{x}")
        parallel.add("translate", lambda x: f"translate:{x}")
        p_results = parallel.execute("input")
        assert len(p_results) == 3
        assert "search:input" in p_results["search"]
        assert "analyze:input" in p_results["analyze"]
        print("  ✅ 工具链编排模式 —— 串行Pipeline + 并行聚合")

    def run(self):
        print("=" * 60)
        print("Q5: Agent开发中的设计模式实战")
        print("=" * 60)
        self.test_tool_registry()
        self.test_react()
        self.test_memory_manager()
        self.test_multi_agent()
        self.test_tool_chain()
        print()


# ============================================================
# 主函数
# ============================================================

def main():
    print("\n" + "🔥" * 30)
    print("  阶段十·工程进阶 — 设计模式练习（Q1-Q5）")
    print("🔥" * 30 + "\n")

    Q1CreationalPatterns().run()
    Q2StructuralPatterns().run()
    Q3BehavioralPatterns().run()
    Q4SOLIDPrinciples().run()
    Q5AgentPatterns().run()

    print("=" * 60)
    print("  🎉 Q1-Q5 全部通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()
