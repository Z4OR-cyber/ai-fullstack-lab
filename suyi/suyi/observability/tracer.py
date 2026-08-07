"""分布式追踪 — Span 创建、嵌套、关联，导出 JSON trace.

追踪模型:
    - Tracer: 追踪器，管理一次 AgentLoop 执行的完整追踪
    - Span: 单个操作追踪单元，支持嵌套
    - SpanStatus: span 状态（OK / ERROR）

一次 AgentLoop 执行包含多个 span:
    - llm_call:    LLM 调用
    - tool_exec:   工具执行
    - memory_ops:  记忆操作

Span 结构:
    - operation_name: 操作名称
    - start_time / end_time: 开始和结束时间
    - tags: 自定义标签
    - logs: 日志事件
    - parent: 父 span 引用
    - children: 子 span 列表
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class SpanStatus:
    """Span 状态常量."""

    OK: str = "OK"
    ERROR: str = "ERROR"


@dataclass
class SpanLog:
    """Span 日志事件.

    Attributes:
        timestamp: 时间戳（Unix epoch 秒）.
        level: 日志级别.
        message: 日志消息.
        fields: 额外字段.
    """

    timestamp: float
    level: str = "info"
    message: str = ""
    fields: Dict[str, Any] = field(default_factory=dict)


class Span:
    """追踪 Span — 单个操作的追踪单元.

    Span 可以嵌套形成树结构（parent → children）.

    使用示例::

        with tracer.start_span("llm_call") as span:
            span.set_tag("model", "gpt-4")
            span.set_tag("tokens", 1500)
            # ... 执行 LLM 调用 ...
            span.log("response received", level="info")
    """

    def __init__(
        self,
        operation_name: str,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        parent: Optional["Span"] = None,
    ) -> None:
        self.operation_name: str = operation_name
        self.trace_id: str = trace_id or str(uuid.uuid4())
        self.span_id: str = span_id or str(uuid.uuid4())
        self.parent_id: Optional[str] = parent_id
        self.parent: Optional["Span"] = parent
        self.children: List[Span] = []

        self.start_time: float = 0.0
        self.end_time: Optional[float] = None
        self.status: str = SpanStatus.OK
        self.tags: Dict[str, Any] = {}
        self.logs: List[SpanLog] = []
        self._finished: bool = False

    # ── 时间控制 ──────────────────────────────────────────────

    def start(self) -> "Span":
        """开始 span 计时."""
        self.start_time = time.time()
        return self

    def finish(self, status: str = SpanStatus.OK) -> None:
        """结束 span 计时.

        Args:
            status: span 状态（OK / ERROR）.
        """
        if self._finished:
            return
        self.end_time = time.time()
        self.status = status
        self._finished = True

    @property
    def duration(self) -> float:
        """返回 span 持续时间（秒）.

        未结束时返回从 start 到当前时间的差值.
        """
        end: float = self.end_time or time.time()
        return end - self.start_time

    @property
    def is_finished(self) -> bool:
        """是否已结束."""
        return self._finished

    # ── 标签 ──────────────────────────────────────────────────

    def set_tag(self, key: str, value: Any) -> "Span":
        """设置标签.

        Args:
            key: 标签键.
            value: 标签值.

        Returns:
            self（支持链式调用）.
        """
        self.tags[key] = value
        return self

    # ── 日志 ──────────────────────────────────────────────────

    def log(
        self,
        message: str,
        level: str = "info",
        **fields: Any,
    ) -> "Span":
        """记录日志事件.

        Args:
            message: 日志消息.
            level: 日志级别.
            **fields: 额外字段.

        Returns:
            self（支持链式调用）.
        """
        self.logs.append(SpanLog(
            timestamp=time.time(),
            level=level,
            message=message,
            fields=fields,
        ))
        return self

    # ── 子 span ──────────────────────────────────────────────

    def add_child(self, child: "Span") -> None:
        """添加子 span."""
        self.children.append(child)

    # ── 导出 ──────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "operation_name": self.operation_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": round(self.duration, 6),
            "status": self.status,
            "tags": self.tags,
            "logs": [
                {
                    "timestamp": log.timestamp,
                    "level": log.level,
                    "message": log.message,
                    "fields": log.fields,
                }
                for log in self.logs
            ],
            "children": [child.to_dict() for child in self.children],
        }

    # ── 上下文管理器 ──────────────────────────────────────────

    def __enter__(self) -> "Span":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.status = SpanStatus.ERROR
            self.log(
                f"Exception: {exc_val}",
                level="error",
                exc_type=str(exc_type),
            )
        self.finish(self.status)


class Tracer:
    """分布式追踪器 — 管理 trace 和 span 的创建.

    一次 Tracer 实例对应一次 AgentLoop 执行，
    产生的所有 span 共享同一个 trace_id.

    使用示例::

        tracer = Tracer()

        with tracer.start_span("agent_loop") as root:
            with tracer.start_span("llm_call", parent=root) as llm_span:
                llm_span.set_tag("model", "gpt-4")
            with tracer.start_span("tool_exec", parent=root) as tool_span:
                tool_span.set_tag("tool", "bash")

        trace = tracer.export()
    """

    def __init__(self, trace_id: Optional[str] = None) -> None:
        self.trace_id: str = trace_id or str(uuid.uuid4())
        self._spans: List[Span] = []
        self._root: Optional[Span] = None
        self._lock: threading.Lock = threading.Lock()
        self._current_span: Optional[Span] = None

    def start_span(
        self,
        operation_name: str,
        parent: Optional[Span] = None,
    ) -> Span:
        """创建并开始一个新 span.

        Args:
            operation_name: 操作名称.
            parent: 父 span（None 则创建根 span）.

        Returns:
            已开始的 Span 实例（可作为上下文管理器使用）.
        """
        parent_span: Optional[Span] = parent or self._current_span
        span: Span = Span(
            operation_name=operation_name,
            trace_id=self.trace_id,
            parent_id=parent_span.span_id if parent_span else None,
            parent=parent_span,
        )
        span.start()

        with self._lock:
            self._spans.append(span)
            if parent_span is not None:
                parent_span.add_child(span)
            elif self._root is None:
                self._root = span

        return span

    def set_current_span(self, span: Optional[Span]) -> None:
        """设置当前活跃的 span（用于自动父子关联）.

        Args:
            span: 当前 span，None 表示清除.
        """
        self._current_span = span

    @property
    def root(self) -> Optional[Span]:
        """返回根 span."""
        return self._root

    @property
    def spans(self) -> List[Span]:
        """返回所有 span 列表."""
        return list(self._spans)

    @property
    def span_count(self) -> int:
        """返回 span 总数."""
        return len(self._spans)

    def export(self) -> Dict[str, Any]:
        """导出完整 trace 为字典.

        Returns:
            包含 trace_id 和根 span 树的字典.
        """
        return {
            "trace_id": self.trace_id,
            "span_count": len(self._spans),
            "root": self._root.to_dict() if self._root else None,
            "spans": [
                span.to_dict() for span in self._spans
            ],
        }

    def reset(self) -> None:
        """重置追踪器，清除所有 span."""
        with self._lock:
            self._spans.clear()
            self._root = None
            self._current_span = None
            self.trace_id = str(uuid.uuid4())
