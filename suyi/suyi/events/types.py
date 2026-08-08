"""事件类型定义 — 标准事件类型和事件数据结构。

定义框架中使用的标准事件:
    - before_llm_call / after_llm_call
    - before_tool_call / after_tool_call
    - memory_updated
    - skill_loaded
    - agent_spawned
    - error
    - workflow_started / workflow_completed
    - cache_hit / cache_miss
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class EventType(str, Enum):
    """标准事件类型。"""

    # LLM 相关
    BEFORE_LLM_CALL = "before_llm_call"
    AFTER_LLM_CALL = "after_llm_call"

    # 工具相关
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"

    # 记忆相关
    MEMORY_UPDATED = "memory_updated"

    # 技能相关
    SKILL_LOADED = "skill_loaded"

    # Agent 相关
    AGENT_SPAWNED = "agent_spawned"
    AGENT_COMPLETED = "agent_completed"

    # 工作流相关
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_NODE_STARTED = "workflow_node_started"
    WORKFLOW_NODE_COMPLETED = "workflow_node_completed"

    # 缓存相关
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"

    # 错误
    ERROR = "error"

    # 自定义
    CUSTOM = "custom"


@dataclass
class Event:
    """事件数据结构。

    Attributes:
        type: 事件类型。
        data: 事件负载数据。
        timestamp: 事件时间戳。
        id: 事件唯一 ID。
        source: 事件来源（如模块名）。
    """

    type: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
        }

    @classmethod
    def create(
        cls,
        event_type: str | EventType,
        data: Optional[Dict[str, Any]] = None,
        source: str = "",
    ) -> "Event":
        """便捷创建方法。"""
        if isinstance(event_type, EventType):
            event_type = event_type.value
        return cls(
            type=event_type,
            data=data or {},
            source=source,
        )

    def __repr__(self) -> str:
        return f"Event(type={self.type!r}, source={self.source!r}, id={self.id[:8]})"


# ── 事件工厂函数 ──────────────────────────────────────────────

def before_llm_call(messages: list, system_prompt: str = "", source: str = "") -> Event:
    """创建 before_llm_call 事件。"""
    return Event.create(
        EventType.BEFORE_LLM_CALL,
        {"messages_count": len(messages), "system_prompt": system_prompt},
        source,
    )


def after_llm_call(content: str, tokens: int = 0, source: str = "") -> Event:
    """创建 after_llm_call 事件。"""
    return Event.create(
        EventType.AFTER_LLM_CALL,
        {"content": content, "total_tokens": tokens},
        source,
    )


def before_tool_call(tool_name: str, arguments: dict, source: str = "") -> Event:
    """创建 before_tool_call 事件。"""
    return Event.create(
        EventType.BEFORE_TOOL_CALL,
        {"tool_name": tool_name, "arguments": arguments},
        source,
    )


def after_tool_call(tool_name: str, result: str, success: bool = True, source: str = "") -> Event:
    """创建 after_tool_call 事件。"""
    return Event.create(
        EventType.AFTER_TOOL_CALL,
        {"tool_name": tool_name, "result": result, "success": success},
        source,
    )


def memory_updated(operation: str, key: str = "", source: str = "") -> Event:
    """创建 memory_updated 事件。"""
    return Event.create(
        EventType.MEMORY_UPDATED,
        {"operation": operation, "key": key},
        source,
    )


def skill_loaded(skill_name: str, source: str = "") -> Event:
    """创建 skill_loaded 事件。"""
    return Event.create(
        EventType.SKILL_LOADED,
        {"skill_name": skill_name},
        source,
    )


def agent_spawned(agent_name: str, task: str = "", source: str = "") -> Event:
    """创建 agent_spawned 事件。"""
    return Event.create(
        EventType.AGENT_SPAWNED,
        {"agent_name": agent_name, "task": task},
        source,
    )


def error_event(error: str, context: Optional[dict] = None, source: str = "") -> Event:
    """创建 error 事件。"""
    return Event.create(
        EventType.ERROR,
        {"error": error, "context": context or {}},
        source,
    )


__all__ = [
    "EventType",
    "Event",
    "before_llm_call",
    "after_llm_call",
    "before_tool_call",
    "after_tool_call",
    "memory_updated",
    "skill_loaded",
    "agent_spawned",
    "error_event",
]
