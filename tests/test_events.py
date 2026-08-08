"""Tests for Event System — 事件总线、事件类型、发布/订阅。"""

import asyncio
import pytest

from suyi.events.types import (
    EventType,
    Event,
    before_llm_call,
    after_llm_call,
    before_tool_call,
    after_tool_call,
    memory_updated,
    skill_loaded,
    agent_spawned,
    error_event,
)
from suyi.events.bus import EventBus, Subscription, get_event_bus, reset_event_bus


# ═════════════════════════════════════════════════════════════
#  EventType
# ═════════════════════════════════════════════════════════════

class TestEventType:
    """事件类型枚举测试。"""

    def test_standard_types_exist(self):
        assert EventType.BEFORE_LLM_CALL.value == "before_llm_call"
        assert EventType.AFTER_LLM_CALL.value == "after_llm_call"
        assert EventType.BEFORE_TOOL_CALL.value == "before_tool_call"
        assert EventType.AFTER_TOOL_CALL.value == "after_tool_call"
        assert EventType.MEMORY_UPDATED.value == "memory_updated"
        assert EventType.SKILL_LOADED.value == "skill_loaded"
        assert EventType.AGENT_SPAWNED.value == "agent_spawned"
        assert EventType.ERROR.value == "error"

    def test_is_string_enum(self):
        assert isinstance(EventType.BEFORE_LLM_CALL, str)
        assert EventType.BEFORE_LLM_CALL == "before_llm_call"


# ═════════════════════════════════════════════════════════════
#  Event
# ═════════════════════════════════════════════════════════════

class TestEvent:
    """事件数据结构测试。"""

    def test_creation(self):
        event = Event(type="test_event", data={"key": "value"})
        assert event.type == "test_event"
        assert event.data["key"] == "value"
        assert event.id  # 自动生成
        assert event.timestamp > 0

    def test_create_from_enum(self):
        event = Event.create(EventType.BEFORE_LLM_CALL, {"count": 3})
        assert event.type == "before_llm_call"
        assert event.data["count"] == 3

    def test_create_from_string(self):
        event = Event.create("custom_event", {"x": 1}, source="test")
        assert event.type == "custom_event"
        assert event.source == "test"

    def test_to_dict(self):
        event = Event(type="test", data={"k": "v"}, source="mod")
        d = event.to_dict()
        assert d["type"] == "test"
        assert d["data"] == {"k": "v"}
        assert d["source"] == "mod"
        assert "id" in d
        assert "timestamp" in d

    def test_repr(self):
        event = Event(type="test_event", source="module")
        r = repr(event)
        assert "Event" in r
        assert "test_event" in r


# ═════════════════════════════════════════════════════════════
#  Event Factory Functions
# ═════════════════════════════════════════════════════════════

class TestEventFactories:
    """事件工厂函数测试。"""

    def test_before_llm_call(self):
        event = before_llm_call(messages=[{"role": "user"}], system_prompt="You are AI")
        assert event.type == "before_llm_call"
        assert event.data["messages_count"] == 1

    def test_after_llm_call(self):
        event = after_llm_call(content="Hello", tokens=42)
        assert event.type == "after_llm_call"
        assert event.data["content"] == "Hello"
        assert event.data["total_tokens"] == 42

    def test_before_tool_call(self):
        event = before_tool_call("search", {"query": "test"})
        assert event.type == "before_tool_call"
        assert event.data["tool_name"] == "search"

    def test_after_tool_call(self):
        event = after_tool_call("search", "results", success=True)
        assert event.type == "after_tool_call"
        assert event.data["success"] is True

    def test_memory_updated(self):
        event = memory_updated("add", key="fact1")
        assert event.type == "memory_updated"
        assert event.data["operation"] == "add"

    def test_skill_loaded(self):
        event = skill_loaded("my_skill")
        assert event.type == "skill_loaded"
        assert event.data["skill_name"] == "my_skill"

    def test_agent_spawned(self):
        event = agent_spawned("worker", task="process data")
        assert event.type == "agent_spawned"
        assert event.data["agent_name"] == "worker"

    def test_error_event(self):
        event = error_event("ValueError: bad input", context={"step": 3})
        assert event.type == "error"
        assert event.data["error"] == "ValueError: bad input"
        assert event.data["context"]["step"] == 3


# ═════════════════════════════════════════════════════════════
#  EventBus — Sync
# ═════════════════════════════════════════════════════════════

class TestEventBusSync:
    """事件总线同步测试。"""

    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe("test_event", lambda e: received.append(e))
        event = Event.create("test_event", {"data": "hello"})
        bus.publish(event)
        assert len(received) == 1
        assert received[0].data["data"] == "hello"

    def test_multiple_subscribers(self):
        bus = EventBus()
        results1 = []
        results2 = []
        bus.subscribe("test", lambda e: results1.append(1))
        bus.subscribe("test", lambda e: results2.append(2))
        bus.publish(Event.create("test"))
        assert len(results1) == 1
        assert len(results2) == 1

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        sub_id = bus.subscribe("test", lambda e: received.append(e))
        assert bus.unsubscribe(sub_id) is True
        bus.publish(Event.create("test"))
        assert len(received) == 0

    def test_unsubscribe_invalid(self):
        bus = EventBus()
        assert bus.unsubscribe(999) is False

    def test_wildcard_subscribe(self):
        bus = EventBus()
        received = []
        bus.subscribe("before_*", lambda e: received.append(e.type))
        bus.publish(Event.create("before_llm_call"))
        bus.publish(Event.create("before_tool_call"))
        bus.publish(Event.create("after_llm_call"))
        assert len(received) == 2
        assert "before_llm_call" in received
        assert "before_tool_call" in received

    def test_wildcard_all(self):
        bus = EventBus()
        received = []
        bus.subscribe("*", lambda e: received.append(e.type))
        bus.publish(Event.create("any_event"))
        bus.publish(Event.create("other_event"))
        assert len(received) == 2

    def test_once_subscription(self):
        bus = EventBus()
        received = []
        bus.subscribe("test", lambda e: received.append(e), once=True)
        bus.publish(Event.create("test"))
        bus.publish(Event.create("test"))
        assert len(received) == 1

    def test_unsubscribe_all(self):
        bus = EventBus()
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        bus.unsubscribe_all()
        assert bus.subscription_count == 0

    def test_handler_exception_isolated(self):
        bus = EventBus()
        results = []
        bus.subscribe("test", lambda e: 1 / 0)  # 会抛异常
        bus.subscribe("test", lambda e: results.append("ok"))
        results_list = bus.publish(Event.create("test"))
        # 异常应该被捕获，不影响其他处理器
        assert len(results) == 1
        assert any(isinstance(r, ZeroDivisionError) for r in results_list)

    def test_event_history(self):
        bus = EventBus(max_history=100)
        bus.publish(Event.create("event1"))
        bus.publish(Event.create("event2"))
        history = bus.get_history()
        assert len(history) == 2
        assert history[0].type == "event1"

    def test_history_with_filter(self):
        bus = EventBus(max_history=100)
        bus.publish(Event.create("type_a"))
        bus.publish(Event.create("type_b"))
        bus.publish(Event.create("type_a"))
        filtered = bus.get_history(event_type="type_a")
        assert len(filtered) == 2

    def test_clear_history(self):
        bus = EventBus()
        bus.publish(Event.create("test"))
        bus.clear_history()
        assert bus.history_size == 0

    def test_publish_count(self):
        bus = EventBus()
        bus.publish(Event.create("a"))
        bus.publish(Event.create("b"))
        assert bus.publish_count == 2

    def test_stats(self):
        bus = EventBus()
        bus.subscribe("test", lambda e: None)
        bus.subscribe("before_*", lambda e: None)
        bus.subscribe_async("after_*", lambda e: None)
        bus.publish(Event.create("test"))
        stats = bus.get_stats()
        assert stats["total_subscriptions"] == 3
        assert stats["sync_subscriptions"] == 2
        assert stats["async_subscriptions"] == 1
        assert stats["publish_count"] == 1


# ═════════════════════════════════════════════════════════════
#  EventBus — Async
# ═════════════════════════════════════════════════════════════

class TestEventBusAsync:
    """事件总线异步测试。"""

    @pytest.mark.asyncio
    async def test_async_subscribe_and_publish(self):
        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event.type)

        bus.subscribe_async("test_event", handler)
        await bus.publish_async(Event.create("test_event"))
        assert len(received) == 1
        assert received[0] == "test_event"

    @pytest.mark.asyncio
    async def test_mixed_sync_async(self):
        bus = EventBus()
        sync_results = []
        async_results = []

        bus.subscribe("test", lambda e: sync_results.append("sync"))
        
        async def async_handler(e):
            async_results.append("async")

        bus.subscribe_async("test", async_handler)
        await bus.publish_async(Event.create("test"))
        assert len(sync_results) == 1
        assert len(async_results) == 1

    @pytest.mark.asyncio
    async def test_async_wildcard(self):
        bus = EventBus()
        received = []

        async def handler(e):
            received.append(e.type)

        bus.subscribe_async("after_*", handler)
        await bus.publish_async(Event.create("after_llm_call"))
        await bus.publish_async(Event.create("after_tool_call"))
        assert len(received) == 2

    @pytest.mark.asyncio
    async def test_async_once(self):
        bus = EventBus()
        received = []

        async def handler(e):
            received.append(e.type)

        bus.subscribe_async("test", handler, once=True)
        await bus.publish_async(Event.create("test"))
        await bus.publish_async(Event.create("test"))
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_async_parallel_execution(self):
        bus = EventBus()
        order = []

        async def slow_handler(e):
            await asyncio.sleep(0.05)
            order.append(e.data.get("name", ""))

        bus.subscribe_async("task", slow_handler)
        bus.subscribe_async("task", slow_handler)
        await bus.publish_async(Event.create("task", {"name": "parallel"}))
        assert len(order) == 2


# ═════════════════════════════════════════════════════════════
#  Global Event Bus
# ═════════════════════════════════════════════════════════════

class TestGlobalEventBus:
    """全局事件总线测试。"""

    def test_get_event_bus_singleton(self):
        reset_event_bus()
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_reset_event_bus(self):
        bus1 = get_event_bus()
        reset_event_bus()
        bus2 = get_event_bus()
        assert bus1 is not bus2

    def test_global_bus_functional(self):
        reset_event_bus()
        bus = get_event_bus()
        received = []
        bus.subscribe("global_test", lambda e: received.append(e))
        bus.publish(Event.create("global_test"))
        assert len(received) == 1


# ═════════════════════════════════════════════════════════════
#  History Limits
# ═════════════════════════════════════════════════════════════

class TestEventBusHistory:
    """事件历史限制测试。"""

    def test_history_limit(self):
        bus = EventBus(max_history=3)
        for i in range(5):
            bus.publish(Event.create(f"event_{i}"))
        history = bus.get_history()
        assert len(history) == 3
        # 应该保留最后 3 个
        assert history[-1].type == "event_4"

    def test_no_history(self):
        bus = EventBus(max_history=0)
        bus.publish(Event.create("test"))
        assert bus.history_size == 0

    def test_history_limit_with_limit_param(self):
        bus = EventBus(max_history=100)
        for i in range(10):
            bus.publish(Event.create(f"event_{i}"))
        history = bus.get_history(limit=3)
        assert len(history) == 3
