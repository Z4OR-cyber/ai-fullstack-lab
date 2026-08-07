"""指标收集 — 计数器、直方图、仪表盘，支持时间窗口聚合.

提供三类指标:
    - Counter（计数器）:   单调递增，如请求总数、错误次数
    - Histogram（直方图）: 分布统计，如延迟分布、token 使用量
    - Gauge（仪表盘）:     当前值，如活跃会话数、内存使用

时间窗口聚合:
    支持 1m / 5m / 1h / 24h 四档时间窗口，
    过期数据自动清理.

导出:
    JSON 格式，便于外部系统消费.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional


# ── 时间窗口常量 ──────────────────────────────────────────────

WINDOW_1M: int = 60            # 1 分钟
WINDOW_5M: int = 300           # 5 分钟
WINDOW_1H: int = 3600          # 1 小时
WINDOW_24H: int = 86400        # 24 小时

ALL_WINDOWS: List[int] = [WINDOW_1M, WINDOW_5M, WINDOW_1H, WINDOW_24H]

WINDOW_LABELS: Dict[int, str] = {
    WINDOW_1M: "1m",
    WINDOW_5M: "5m",
    WINDOW_1H: "1h",
    WINDOW_24H: "24h",
}


# ── Counter ────────────────────────────────────────────────────


class Counter:
    """计数器指标 — 单调递增（可 reset）.

    记录带时间戳的增量事件，支持时间窗口查询.

    Args:
        name: 指标名称.
        description: 指标描述.
    """

    def __init__(self, name: str, description: str = "") -> None:
        self.name: str = name
        self.description: str = description
        self._total: float = 0.0
        # 每个时间窗口一个 deque，存储 (timestamp, delta)
        self._events: Dict[int, Deque[tuple[float, float]]] = {
            w: deque() for w in ALL_WINDOWS
        }
        self._lock: threading.Lock = threading.Lock()

    def inc(self, amount: float = 1.0) -> None:
        """增加计数.

        Args:
            amount: 增量值（默认 1.0）.
        """
        now: float = time.time()
        with self._lock:
            self._total += amount
            for window in ALL_WINDOWS:
                self._events[window].append((now, amount))

    def value(self) -> float:
        """返回总累计值."""
        return self._total

    def window_value(self, window: int = WINDOW_5M) -> float:
        """返回指定时间窗口内的增量总和.

        Args:
            window: 时间窗口秒数.

        Returns:
            窗口内的增量总和.
        """
        now: float = time.time()
        cutoff: float = now - window
        events: Deque[tuple[float, float]] = self._events.get(
            window, deque()
        )
        # 清理过期事件
        while events and events[0][0] < cutoff:
            events.popleft()
        return sum(delta for _, delta in events)

    def reset(self) -> None:
        """重置计数器（清零并清除所有事件）."""
        with self._lock:
            self._total = 0.0
            for window in ALL_WINDOWS:
                self._events[window].clear()

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典."""
        return {
            "type": "counter",
            "name": self.name,
            "description": self.description,
            "total": self._total,
            "windows": {
                WINDOW_LABELS[w]: self.window_value(w) for w in ALL_WINDOWS
            },
        }


# ── Gauge ──────────────────────────────────────────────────────


class Gauge:
    """仪表盘指标 — 当前值（可增可减）.

    Args:
        name: 指标名称.
        description: 指标描述.
    """

    def __init__(self, name: str, description: str = "") -> None:
        self.name: str = name
        self.description: str = description
        self._value: float = 0.0
        self._lock: threading.Lock = threading.Lock()

    def set(self, value: float) -> None:
        """设置当前值.

        Args:
            value: 当前值.
        """
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0) -> None:
        """增加值.

        Args:
            amount: 增量.
        """
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        """减少值.

        Args:
            amount: 减量.
        """
        with self._lock:
            self._value -= amount

    def value(self) -> float:
        """返回当前值."""
        return self._value

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典."""
        return {
            "type": "gauge",
            "name": self.name,
            "description": self.description,
            "value": self._value,
        }


# ── Histogram ──────────────────────────────────────────────────


class Histogram:
    """直方图指标 — 分布统计.

    记录观测值并计算分位数（percentiles）.

    默认桶边界: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
    默认分位数: [0.5, 0.9, 0.99]

    Args:
        name: 指标名称.
        description: 指标描述.
        buckets: 桶边界列表.
    """

    DEFAULT_BUCKETS: List[float] = [
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10,
    ]
    DEFAULT_PERCENTILES: List[float] = [0.5, 0.9, 0.99]

    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: Optional[List[float]] = None,
    ) -> None:
        self.name: str = name
        self.description: str = description
        self.buckets: List[float] = sorted(buckets or self.DEFAULT_BUCKETS)
        self._observations: List[float] = []
        self._bucket_counts: List[int] = [0] * len(self.buckets)
        self._sum: float = 0.0
        self._count: int = 0
        self._lock: threading.Lock = threading.Lock()

    def observe(self, value: float) -> None:
        """记录一个观测值.

        Args:
            value: 观测值.
        """
        with self._lock:
            self._observations.append(value)
            self._sum += value
            self._count += 1
            for i, bound in enumerate(self.buckets):
                if value <= bound:
                    self._bucket_counts[i] += 1

    def percentile(self, p: float) -> float:
        """计算分位数.

        Args:
            p: 分位数（0.0–1.0）.

        Returns:
            分位数值，无数据时返回 0.0.
        """
        with self._lock:
            if not self._observations:
                return 0.0
            sorted_vals: List[float] = sorted(self._observations)
            index: int = int(len(sorted_vals) * p)
            index = min(index, len(sorted_vals) - 1)
            return sorted_vals[index]

    def count(self) -> int:
        """返回观测总数."""
        return self._count

    def sum(self) -> float:
        """返回观测值总和."""
        return self._sum

    def mean(self) -> float:
        """返回观测值均值."""
        return self._sum / self._count if self._count > 0 else 0.0

    def reset(self) -> None:
        """重置直方图."""
        with self._lock:
            self._observations.clear()
            self._bucket_counts = [0] * len(self.buckets)
            self._sum = 0.0
            self._count = 0

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典."""
        return {
            "type": "histogram",
            "name": self.name,
            "description": self.description,
            "count": self._count,
            "sum": round(self._sum, 6),
            "mean": round(self.mean(), 6),
            "percentiles": {
                f"p{int(p * 100)}": round(self.percentile(p), 6)
                for p in self.DEFAULT_PERCENTILES
            },
            "buckets": {
                f"<={bound}": count
                for bound, count in zip(self.buckets, self._bucket_counts)
            },
        }


# ── MetricsCollector ───────────────────────────────────────────


class MetricsCollector:
    """指标收集器 — 管理所有计数器、直方图和仪表盘.

    预置常用指标:
        - requests_total (Counter): 请求总数
        - request_duration (Histogram): 请求延迟分布
        - token_usage (Histogram): token 使用量分布
        - tool_calls_total (Counter): 工具调用次数
        - errors_total (Counter): 错误总数

    使用示例::

        metrics = MetricsCollector()
        metrics.inc_counter("requests_total")
        metrics.observe_histogram("request_duration", 0.42)
        metrics.set_gauge("active_sessions", 5)
        metrics.export_json()  # 导出全部指标
    """

    def __init__(self) -> None:
        self._counters: Dict[str, Counter] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._lock: threading.Lock = threading.Lock()

        # 初始化预置指标
        self._init_default_metrics()

    def _init_default_metrics(self) -> None:
        """初始化预置指标."""
        self._counters["requests_total"] = Counter(
            "requests_total", "Total number of requests"
        )
        self._histograms["request_duration"] = Histogram(
            "request_duration", "Request duration in seconds"
        )
        self._histograms["token_usage"] = Histogram(
            "token_usage", "Token usage per request"
        )
        self._counters["tool_calls_total"] = Counter(
            "tool_calls_total", "Total number of tool calls"
        )
        self._counters["errors_total"] = Counter(
            "errors_total", "Total number of errors"
        )
        self._gauges["active_sessions"] = Gauge(
            "active_sessions", "Number of active sessions"
        )

    # ── Counter 操作 ──────────────────────────────────────────

    def counter(self, name: str, description: str = "") -> Counter:
        """获取或创建计数器.

        Args:
            name: 指标名称.
            description: 描述（仅创建时生效）.

        Returns:
            Counter 实例.
        """
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name, description)
            return self._counters[name]

    def inc_counter(self, name: str, amount: float = 1.0) -> None:
        """增加计数器值.

        Args:
            name: 指标名称.
            amount: 增量.
        """
        self.counter(name).inc(amount)

    # ── Histogram 操作 ────────────────────────────────────────

    def histogram(self, name: str, description: str = "") -> Histogram:
        """获取或创建直方图."""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(name, description)
            return self._histograms[name]

    def observe_histogram(self, name: str, value: float) -> None:
        """记录直方图观测值.

        Args:
            name: 指标名称.
            value: 观测值.
        """
        self.histogram(name).observe(value)

    # ── Gauge 操作 ────────────────────────────────────────────

    def gauge(self, name: str, description: str = "") -> Gauge:
        """获取或创建仪表盘."""
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name, description)
            return self._gauges[name]

    def set_gauge(self, name: str, value: float) -> None:
        """设置仪表盘值.

        Args:
            name: 指标名称.
            value: 当前值.
        """
        self.gauge(name).set(value)

    # ── 导出 ──────────────────────────────────────────────────

    def export_json(self) -> Dict[str, Any]:
        """导出所有指标为字典（JSON 兼容）.

        Returns:
            包含所有指标的字典.
        """
        result: Dict[str, Any] = {
            "counters": {},
            "histograms": {},
            "gauges": {},
        }
        for name, counter in self._counters.items():
            result["counters"][name] = counter.to_dict()
        for name, hist in self._histograms.items():
            result["histograms"][name] = hist.to_dict()
        for name, gauge in self._gauges.items():
            result["gauges"][name] = gauge.to_dict()
        return result

    def reset(self) -> None:
        """重置所有指标."""
        with self._lock:
            for counter in self._counters.values():
                counter.reset()
            for hist in self._histograms.values():
                hist.reset()
            for gauge in self._gauges.values():
                gauge.set(0.0)

    # ── 便捷查询 ──────────────────────────────────────────────

    def error_rate(self, window: int = WINDOW_5M) -> float:
        """计算错误率.

        Args:
            window: 时间窗口.

        Returns:
            错误率（0.0–1.0）.
        """
        requests: float = self._counters.get(
            "requests_total", Counter("")
        ).window_value(window)
        errors: float = self._counters.get(
            "errors_total", Counter("")
        ).window_value(window)
        return errors / requests if requests > 0 else 0.0
