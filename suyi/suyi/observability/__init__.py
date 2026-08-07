"""Suyi 可观测性模块 — 结构化日志、指标收集、分布式追踪.

提供三大可观测性支柱 + 中间件集成:

    StructuredLogger          — JSON 格式结构化日志，支持上下文追踪和轮转
    MetricsCollector          — 计数器/直方图/仪表盘，时间窗口聚合
    Tracer / Span            — 分布式追踪，span 创建/嵌套/关联
    ObservabilityMiddleware  — 中间件集成（priority=5，最先执行）

使用示例::

    from suyi.observability import (
        StructuredLogger,
        MetricsCollector,
        Tracer,
        ObservabilityMiddleware,
    )

    logger = StructuredLogger(session_id="s1")
    metrics = MetricsCollector()
    tracer = Tracer()

    # 中间件自动集成
    mw = ObservabilityMiddleware(
        logger=logger, metrics=metrics, tracer=tracer,
    )
"""

from .logger import StructuredLogger, LogLevel
from .metrics import MetricsCollector, Histogram, Counter, Gauge
from .tracer import Tracer, Span, SpanStatus
from .middleware import ObservabilityMiddleware

__all__ = [
    "StructuredLogger",
    "LogLevel",
    "MetricsCollector",
    "Histogram",
    "Counter",
    "Gauge",
    "Tracer",
    "Span",
    "SpanStatus",
    "ObservabilityMiddleware",
]
