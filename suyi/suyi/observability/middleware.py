"""可观测性中间件 — 集成 logger / metrics / tracer 到中间件链.

在 AgentLoop 的四个钩子点自动记录:
    - before_llm_call:  开始 llm_call span，记录请求
    - after_llm_call:   结束 llm_call span，记录 token 使用和延迟
    - before_tool_call: 开始 tool_exec span，记录工具名
    - after_tool_call:  结束 tool_exec span，记录耗时和结果

排序优先级: 5（最先执行，在所有其他中间件之前）.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from ..core.loop import LLMResponse, LoopState
from ..middleware.base import MiddlewareBase
from .logger import StructuredLogger
from .metrics import MetricsCollector
from .tracer import Span, Tracer, SpanStatus

__all__ = ["ObservabilityMiddleware"]


class ObservabilityMiddleware(MiddlewareBase):
    """可观测性中间件 — 自动记录每个阶段的耗时、token 和错误.

    集成三大可观测性组件:
        - StructuredLogger:  记录结构化日志
        - MetricsCollector:  收集指标
        - Tracer:            创建追踪 span

    Args:
        logger:  可选的 StructuredLogger 实例.
        metrics: 可选的 MetricsCollector 实例.
        tracer:  可选的 Tracer 实例.

    如果未提供任何组件，中间件仍然可以正常运行（空操作）.
    """

    def __init__(
        self,
        logger: Optional[StructuredLogger] = None,
        metrics: Optional[MetricsCollector] = None,
        tracer: Optional[Tracer] = None,
    ) -> None:
        self.logger: Optional[StructuredLogger] = logger
        self.metrics: Optional[MetricsCollector] = metrics
        self.tracer: Optional[Tracer] = tracer

        # 存储 span 引用以便在 after_* 钩子中结束
        self._llm_span: Optional[Span] = None
        self._tool_spans: dict[str, Span] = {}  # tool_name -> span
        self._turn_start: float = 0.0

    @property
    def priority(self) -> int:
        """可观测性中间件最先执行（5）."""
        return 5

    # ── before_llm_call ────────────────────────────────────────

    async def before_llm_call(self, state: LoopState) -> LoopState:
        """在 LLM 调用前记录请求信息并创建追踪 span.

        Args:
            state: 当前循环状态.

        Returns:
            未修改的 state.
        """
        self._turn_start = time.time()

        # 记录日志
        if self.logger:
            self.logger.info(
                "LLM call starting",
                extra={
                    "turn": state.turn,
                    "history_length": len(state.history),
                },
            )

        # 记录指标
        if self.metrics:
            self.metrics.inc_counter("requests_total")
            self.metrics.set_gauge(
                "active_sessions",
                state.metadata.get("active_sessions", 1),
            )

        # 创建追踪 span
        if self.tracer:
            self._llm_span = self.tracer.start_span(
                f"llm_call_turn_{state.turn}",
            )
            self._llm_span.set_tag("turn", state.turn)
            self._llm_span.set_tag("history_length", len(state.history))

        return state

    # ── after_llm_call ─────────────────────────────────────────

    async def after_llm_call(
        self, response: LLMResponse, state: LoopState
    ) -> LLMResponse:
        """在 LLM 调用后记录响应信息和 token 使用.

        Args:
            response: LLM 响应.
            state: 当前循环状态.

        Returns:
            未修改的 response.
        """
        elapsed: float = time.time() - self._turn_start

        # 记录日志
        if self.logger:
            self.logger.info(
                "LLM call completed",
                extra={
                    "turn": state.turn,
                    "duration_sec": round(elapsed, 4),
                    "total_tokens": response.total_tokens,
                    "tool_calls": len(response.tool_calls),
                },
            )

        # 记录指标
        if self.metrics:
            self.metrics.observe_histogram("request_duration", elapsed)
            self.metrics.observe_histogram(
                "token_usage", response.total_tokens
            )

        # 结束追踪 span
        if self.tracer and self._llm_span:
            self._llm_span.set_tag("total_tokens", response.total_tokens)
            self._llm_span.set_tag("tool_call_count", len(response.tool_calls))
            self._llm_span.finish()
            self._llm_span = None

        return response

    # ── before_tool_call ───────────────────────────────────────

    async def before_tool_call(
        self, tool_name: str, arguments: dict, state: LoopState
    ) -> tuple[str, dict]:
        """在工具执行前记录工具名并创建追踪 span.

        Args:
            tool_name: 工具名称.
            arguments: 工具参数.
            state: 当前循环状态.

        Returns:
            未修改的工具名称和参数.
        """
        # 记录日志
        if self.logger:
            self.logger.debug(
                f"Tool '{tool_name}' executing",
                extra={
                    "tool": tool_name,
                    "args_keys": list(arguments.keys()),
                },
            )

        # 记录指标
        if self.metrics:
            self.metrics.inc_counter("tool_calls_total")

        # 创建追踪 span
        if self.tracer:
            span: Span = self.tracer.start_span(
                f"tool_exec_{tool_name}",
            )
            span.set_tag("tool_name", tool_name)
            self._tool_spans[tool_name] = span

        return tool_name, arguments

    # ── after_tool_call ────────────────────────────────────────

    async def after_tool_call(
        self,
        tool_name: str,
        arguments: dict,
        output: str,
        state: LoopState,
    ) -> str:
        """在工具执行后记录耗时和结果.

        Args:
            tool_name: 工具名称.
            arguments: 工具参数.
            output: 工具输出.
            state: 当前循环状态.

        Returns:
            未修改的输出.
        """
        # 记录日志
        if self.logger:
            self.logger.debug(
                f"Tool '{tool_name}' completed",
                extra={
                    "tool": tool_name,
                    "output_length": len(output),
                },
            )

        # 结束追踪 span
        if self.tracer and tool_name in self._tool_spans:
            span: Span = self._tool_spans.pop(tool_name)
            span.set_tag("output_length", len(output))
            span.finish()

        return output

    # ── 错误处理辅助 ──────────────────────────────────────────

    def record_error(
        self,
        error: Exception,
        context: Optional[dict] = None,
    ) -> None:
        """记录错误（可从外部调用）.

        Args:
            error: 异常对象.
            context: 额外上下文.
        """
        if self.logger:
            self.logger.error(
                f"Error: {error}",
                extra=context or {},
            )
        if self.metrics:
            self.metrics.inc_counter("errors_total")
        if self.tracer and self._llm_span:
            self._llm_span.set_tag("error", str(error))
            self._llm_span.finish(SpanStatus.ERROR)
            self._llm_span = None
