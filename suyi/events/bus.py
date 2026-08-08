"""事件总线 — 同步和异步发布/订阅，支持通配符订阅和事件历史。

EventBus 提供:
    - 同步发布/订阅（publish / subscribe）
    - 异步发布/订阅（publish_async / subscribe_async）
    - 通配符订阅（如 "before_*" 匹配 "before_llm_call"）
    - 事件历史记录
    - 取消订阅
    - 一次性订阅（once）

Usage::

    bus = EventBus()

    # 同步订阅
    def on_llm_call(event):
        print(f"LLM call: {event.data}")

    bus.subscribe("before_llm_call", on_llm_call)
    bus.publish(Event.create("before_llm_call", {"messages_count": 3}))

    # 通配符订阅
    bus.subscribe("before_*", lambda e: print(f"Before: {e.type}"))

    # 异步订阅
    async def async_handler(event):
        await asyncio.sleep(0.1)
        print(f"Async: {event.type}")

    bus.subscribe_async("after_*", async_handler)
    await bus.publish_async(Event.create("after_llm_call", {"content": "Hello"}))
"""

from __future__ import annotations

import asyncio
import fnmatch
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from .types import Event, EventType


# ── 订阅者记录 ────────────────────────────────────────────────

@dataclass
class Subscription:
    """订阅记录。

    Attributes:
        pattern: 订阅模式（支持通配符）。
        handler: 回调函数。
        is_async: 是否异步回调。
        once: 是否一次性订阅。
        id: 订阅 ID。
    """

    pattern: str
    handler: Callable
    is_async: bool = False
    once: bool = False
    id: int = 0


# ── 事件总线 ──────────────────────────────────────────────────

class EventBus:
    """事件总线 — 同步/异步发布订阅，通配符支持，事件历史。

    Args:
        max_history: 最大历史记录数（0 表示不限制）。
    """

    def __init__(self, max_history: int = 1000) -> None:
        self.max_history = max_history
        self._subscriptions: List[Subscription] = []
        self._next_id: int = 1
        self._history: List[Event] = []
        self._publish_count: int = 0

    # ── 订阅 ──────────────────────────────────────────────────

    def subscribe(
        self,
        pattern: str,
        handler: Callable[[Event], Any],
        once: bool = False,
    ) -> int:
        """同步订阅。

        Args:
            pattern: 事件类型模式（支持 * 通配符）。
            handler: 同步回调函数。
            once: 是否只触发一次。

        Returns:
            订阅 ID（用于取消订阅）。
        """
        sub = Subscription(
            pattern=pattern,
            handler=handler,
            is_async=False,
            once=once,
            id=self._next_id,
        )
        self._next_id += 1
        self._subscriptions.append(sub)
        return sub.id

    def subscribe_async(
        self,
        pattern: str,
        handler: Callable[[Event], Any],
        once: bool = False,
    ) -> int:
        """异步订阅。

        Args:
            pattern: 事件类型模式。
            handler: 异步回调函数。
            once: 是否只触发一次。

        Returns:
            订阅 ID。
        """
        sub = Subscription(
            pattern=pattern,
            handler=handler,
            is_async=True,
            once=once,
            id=self._next_id,
        )
        self._next_id += 1
        self._subscriptions.append(sub)
        return sub.id

    def unsubscribe(self, sub_id: int) -> bool:
        """取消订阅。

        Args:
            sub_id: 订阅 ID。

        Returns:
            是否成功取消。
        """
        original_len = len(self._subscriptions)
        self._subscriptions = [s for s in self._subscriptions if s.id != sub_id]
        return len(self._subscriptions) < original_len

    def unsubscribe_all(self) -> None:
        """取消所有订阅。"""
        self._subscriptions.clear()

    # ── 发布 ──────────────────────────────────────────────────

    def publish(self, event: Event) -> List[Any]:
        """同步发布事件。

        Args:
            event: 要发布的事件。

        Returns:
            所有同步处理器的返回值列表（异步处理器被忽略）。
        """
        self._publish_count += 1
        self._record_history(event)

        results: List[Any] = []
        to_remove: List[int] = []

        for sub in self._subscriptions:
            if self._matches(sub.pattern, event.type):
                if sub.is_async:
                    # 异步处理器在同步发布中跳过
                    continue
                try:
                    result = sub.handler(event)
                    results.append(result)
                except Exception as e:
                    results.append(e)

                if sub.once:
                    to_remove.append(sub.id)

        # 清理一次性订阅
        if to_remove:
            self._subscriptions = [
                s for s in self._subscriptions if s.id not in to_remove
            ]

        return results

    async def publish_async(self, event: Event) -> List[Any]:
        """异步发布事件。

        同时触发同步和异步处理器。异步处理器使用 asyncio.gather 并行执行。

        Args:
            event: 要发布的事件。

        Returns:
            所有处理器的返回值列表。
        """
        self._publish_count += 1
        self._record_history(event)

        sync_results: List[Any] = []
        async_tasks: List[asyncio.Task] = []
        async_subs: List[Subscription] = []
        to_remove: List[int] = []

        for sub in self._subscriptions:
            if not self._matches(sub.pattern, event.type):
                continue

            if sub.is_async:
                task = asyncio.ensure_future(sub.handler(event))
                async_tasks.append(task)
                async_subs.append(sub)
            else:
                try:
                    result = sub.handler(event)
                    sync_results.append(result)
                except Exception as e:
                    sync_results.append(e)

            if sub.once:
                to_remove.append(sub.id)

        # 并行执行异步处理器
        async_results: List[Any] = []
        if async_tasks:
            outcomes = await asyncio.gather(*async_tasks, return_exceptions=True)
            async_results = list(outcomes)

        # 清理一次性订阅
        if to_remove:
            self._subscriptions = [
                s for s in self._subscriptions if s.id not in to_remove
            ]

        return sync_results + async_results

    # ── 通配符匹配 ────────────────────────────────────────────

    @staticmethod
    def _matches(pattern: str, event_type: str) -> bool:
        """检查事件类型是否匹配通配符模式。

        支持的通配符:
            *     — 匹配任意字符序列
            ?     — 匹配单个字符

        Examples:
            "before_*" matches "before_llm_call"
            "*_call"  matches "before_llm_call"
            "*"       matches everything
        """
        return fnmatch.fnmatch(event_type, pattern)

    # ── 事件历史 ──────────────────────────────────────────────

    def _record_history(self, event: Event) -> None:
        """记录事件到历史。"""
        if self.max_history <= 0:
            return
        self._history.append(event)
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]

    def get_history(
        self,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Event]:
        """获取事件历史。

        Args:
            event_type: 可选的事件类型过滤。
            limit: 最大返回数。

        Returns:
            事件列表。
        """
        if event_type:
            filtered = [e for e in self._history if e.type == event_type]
        else:
            filtered = list(self._history)
        return filtered[-limit:]

    def clear_history(self) -> None:
        """清空事件历史。"""
        self._history.clear()

    # ── 统计 ──────────────────────────────────────────────────

    @property
    def subscription_count(self) -> int:
        return len(self._subscriptions)

    @property
    def publish_count(self) -> int:
        return self._publish_count

    @property
    def history_size(self) -> int:
        return len(self._history)

    def get_stats(self) -> Dict[str, Any]:
        """获取总线统计信息。"""
        # 按模式统计订阅数
        pattern_counts: Dict[str, int] = defaultdict(int)
        sync_count = 0
        async_count = 0
        once_count = 0
        for sub in self._subscriptions:
            pattern_counts[sub.pattern] += 1
            if sub.is_async:
                async_count += 1
            else:
                sync_count += 1
            if sub.once:
                once_count += 1

        return {
            "total_subscriptions": len(self._subscriptions),
            "sync_subscriptions": sync_count,
            "async_subscriptions": async_count,
            "once_subscriptions": once_count,
            "publish_count": self._publish_count,
            "history_size": len(self._history),
            "patterns": dict(pattern_counts),
        }


# ── 全局事件总线 ──────────────────────────────────────────────

_global_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取全局事件总线实例。"""
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus


def reset_event_bus() -> None:
    """重置全局事件总线。"""
    global _global_bus
    _global_bus = None


__all__ = [
    "EventBus",
    "Subscription",
    "Event",
    "EventType",
    "get_event_bus",
    "reset_event_bus",
]
