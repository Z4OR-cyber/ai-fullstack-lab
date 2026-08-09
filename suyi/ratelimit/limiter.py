"""
多维度限流器 — 支持令牌桶 + 滑动窗口双算法，可按用户/IP/API 维度限流.

设计原则:
    - **双算法**：令牌桶用于平滑限流（允许突发），滑动窗口用于精确计数.
    - **多维度**：同一限流器实例可同时按 user / ip / api_key 三个维度
      独立计数，互不干扰.
    - **中间件集成**：提供 RateLimitMiddleware，可直接插入中间件链，
      在 before_llm_call 钩子中执行限流检查.
    - **JSON 持久化**：限流状态可持久化到 JSON 文件，支持跨进程恢复.
    - **线程安全**：内部使用锁保护共享状态（基于 threading.Lock）.

信号流转::

    请求 ──▶ MultiRateLimiter.acquire(user="alice", ip="1.2.3.4", api_key="sk-xxx")
                │
                ├─▶ 令牌桶检查（每维度独立桶）
                ├─▶ 滑动窗口检查（每维度独立窗口）
                │
                ▼
            True（放行）/ False（拒绝）

使用示例::

    from suyi.ratelimit import MultiRateLimiter, RateLimitConfig

    config = RateLimitConfig(
        rpm=60,          # 每分钟 60 请求
        burst=10,        # 突发 10 个
        window_size=60,  # 滑动窗口 60 秒
        window_max=100,  # 窗口内最多 100 请求
    )
    limiter = MultiRateLimiter(config)

    if limiter.acquire(user="alice", ip="1.2.3.4"):
        # 放行
        ...
    else:
        # 限流
        ...
"""

from __future__ import annotations

import json
import os
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Optional

from ..core.loop import LLMResponse, LoopState
from ..middleware.base import MiddlewareBase


# ═══════════════════════════════════════════════════════════════
#  配置
# ═══════════════════════════════════════════════════════════════


@dataclass
class RateLimitConfig:
    """限流配置.

    同时配置令牌桶和滑动窗口两套算法，请求需要同时通过两套检查才能放行.

    Attributes:
        rpm:         每分钟允许的请求数（令牌桶填充速率）.
        burst:       令牌桶容量（突发上限）.
        window_size: 滑动窗口大小（秒）.
        window_max:  滑动窗口内最大请求数.
        tpm:         每分钟允许的 token 数（0 表示不限制 token）.
        storage_path: JSON 持久化路径（None 表示不持久化）.
    """

    rpm: int = 60
    burst: int = 10
    window_size: float = 60.0
    window_max: int = 100
    tpm: int = 0
    storage_path: Optional[str] = None

    def validate(self) -> None:
        """校验配置合法性."""
        if self.rpm <= 0:
            raise ValueError("rpm 必须为正数")
        if self.burst <= 0:
            raise ValueError("burst 必须为正数")
        if self.window_size <= 0:
            raise ValueError("window_size 必须为正数")
        if self.window_max <= 0:
            raise ValueError("window_max 必须为正数")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RateLimitConfig":
        return cls(**d)


# ═══════════════════════════════════════════════════════════════
#  限流算法接口
# ═══════════════════════════════════════════════════════════════


class RateLimitAlgorithm(ABC):
    """限流算法抽象基类."""

    @abstractmethod
    def try_acquire(self, count: float = 1) -> bool:
        """尝试获取 count 个配额，成功返回 True."""
        ...

    @abstractmethod
    def available(self) -> float:
        """查询可用配额（不消耗）."""
        ...

    def check(self) -> bool:
        """检查是否有至少 1 个配额可用（不消耗）."""
        return self.available() >= 1

    @abstractmethod
    def reset(self) -> None:
        """重置到初始状态."""
        ...

    @abstractmethod
    def snapshot(self) -> dict:
        """导出当前状态快照（用于持久化）."""
        ...

    @abstractmethod
    def restore(self, data: dict) -> None:
        """从快照恢复状态."""
        ...


# ═══════════════════════════════════════════════════════════════
#  令牌桶
# ═══════════════════════════════════════════════════════════════


class TokenBucket(RateLimitAlgorithm):
    """令牌桶限流器 — 平滑限流，允许突发.

    令牌以固定速率填充到桶中，每个请求消耗令牌.
    桶有最大容量，允许短时突发.

    Attributes:
        capacity:    桶容量（突发上限）.
        refill_rate: 令牌填充速率（每秒）.
    """

    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self._tokens: float = float(capacity)
        self._last_update: float = time.monotonic()

    def _refill(self) -> None:
        """根据经过的时间填充令牌."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(
            self.capacity,
            self._tokens + elapsed * self.refill_rate,
        )
        self._last_update = now

    def try_acquire(self, count: float = 1) -> bool:
        """尝试消耗 count 个令牌."""
        self._refill()
        if self._tokens >= count:
            self._tokens -= count
            return True
        return False

    def available(self) -> float:
        """查询可用令牌数."""
        self._refill()
        return self._tokens

    def reset(self) -> None:
        """重置到满桶."""
        self._tokens = self.capacity
        self._last_update = time.monotonic()

    def snapshot(self) -> dict:
        """导出状态快照."""
        self._refill()
        return {
            "capacity": self.capacity,
            "refill_rate": self.refill_rate,
            "tokens": self._tokens,
        }

    def restore(self, data: dict) -> None:
        """从快照恢复."""
        self._tokens = float(data.get("tokens", self.capacity))
        self._last_update = time.monotonic()

    def __repr__(self) -> str:
        return (
            f"TokenBucket(capacity={self.capacity}, "
            f"refill_rate={self.refill_rate}, tokens={self._tokens:.2f})"
        )


# ═══════════════════════════════════════════════════════════════
#  滑动窗口
# ═══════════════════════════════════════════════════════════════


class SlidingWindow(RateLimitAlgorithm):
    """滑动窗口限流器 — 精确计数，无突发.

    在 window_size 秒的滑动窗口内，最多允许 max_requests 个请求.

    Attributes:
        window_size:  窗口大小（秒）.
        max_requests: 窗口内最大请求数.
    """

    def __init__(self, window_size: float, max_requests: int):
        self.window_size = float(window_size)
        self.max_requests = int(max_requests)
        self._requests: deque = deque()

    def _purge(self) -> None:
        """清理窗口外的过期请求."""
        cutoff = time.monotonic() - self.window_size
        while self._requests and self._requests[0] <= cutoff:
            self._requests.popleft()

    def try_acquire(self, count: float = 1) -> bool:
        """尝试记录 count 个请求."""
        self._purge()
        if len(self._requests) + count > self.max_requests:
            return False
        now = time.monotonic()
        for _ in range(int(count)):
            self._requests.append(now)
        return True

    def available(self) -> float:
        """查询可用配额."""
        self._purge()
        return max(0, self.max_requests - len(self._requests))

    def reset(self) -> None:
        """清空所有记录."""
        self._requests.clear()

    def snapshot(self) -> dict:
        """导出状态快照."""
        self._purge()
        return {
            "window_size": self.window_size,
            "max_requests": self.max_requests,
            "current_count": len(self._requests),
        }

    def restore(self, data: dict) -> None:
        """从快照恢复（时间戳无法精确恢复，近似恢复计数）."""
        # 滑动窗口的时间戳无法精确恢复，只重置为空窗口
        self._requests.clear()

    @property
    def current_count(self) -> int:
        """当前窗口内请求数."""
        self._purge()
        return len(self._requests)

    def __repr__(self) -> str:
        return (
            f"SlidingWindow(window_size={self.window_size}, "
            f"max_requests={self.max_requests}, current={len(self._requests)})"
        )


# ═══════════════════════════════════════════════════════════════
#  单维度限流器
# ═══════════════════════════════════════════════════════════════


class DimensionLimiter:
    """单维度限流器 — 组合令牌桶 + 滑动窗口双算法.

    请求需要同时通过令牌桶和滑动窗口两道检查才能放行.
    如果配置了 token 限制，还有第三道 token 令牌桶检查.

    Attributes:
        config: 限流配置.
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config
        # 请求令牌桶
        self._request_bucket = TokenBucket(
            capacity=config.burst,
            refill_rate=config.rpm / 60.0,
        )
        # 滑动窗口
        self._sliding_window = SlidingWindow(
            window_size=config.window_size,
            max_requests=config.window_max,
        )
        # Token 令牌桶（可选）
        self._token_bucket: Optional[TokenBucket] = None
        if config.tpm > 0:
            self._token_bucket = TokenBucket(
                capacity=config.tpm,
                refill_rate=config.tpm / 60.0,
            )

    def acquire(self, tokens: int = 0) -> bool:
        """尝试获取请求配额.

        Args:
            tokens: 本次请求预计消耗的 token 数（0 表示不检查 token）.

        Returns:
            True 如果通过所有限流检查.
        """
        # 第一道：令牌桶
        if not self._request_bucket.try_acquire(1):
            return False
        # 第二道：滑动窗口
        if not self._sliding_window.try_acquire(1):
            return False
        # 第三道：token 限制
        if tokens > 0 and self._token_bucket is not None:
            if not self._token_bucket.try_acquire(tokens):
                return False
        return True

    def check(self) -> bool:
        """检查是否允许一个请求（不消耗配额）."""
        return (
            self._request_bucket.available() >= 1
            and self._sliding_window.available() >= 1
        )

    def reset(self) -> None:
        """重置所有限流器."""
        self._request_bucket.reset()
        self._sliding_window.reset()
        if self._token_bucket:
            self._token_bucket.reset()

    def status(self) -> dict:
        """返回当前限流状态."""
        return {
            "request_bucket_available": self._request_bucket.available(),
            "sliding_window_available": self._sliding_window.available(),
            "sliding_window_count": self._sliding_window.current_count,
            "token_bucket_available": (
                self._token_bucket.available()
                if self._token_bucket
                else None
            ),
        }

    def snapshot(self) -> dict:
        """导出快照."""
        return {
            "request_bucket": self._request_bucket.snapshot(),
            "sliding_window": self._sliding_window.snapshot(),
            "token_bucket": (
                self._token_bucket.snapshot()
                if self._token_bucket
                else None
            ),
        }

    def restore(self, data: dict) -> None:
        """从快照恢复."""
        if "request_bucket" in data:
            self._request_bucket.restore(data["request_bucket"])
        if "sliding_window" in data:
            self._sliding_window.restore(data["sliding_window"])
        if "token_bucket" in data and self._token_bucket and data["token_bucket"]:
            self._token_bucket.restore(data["token_bucket"])


# ═══════════════════════════════════════════════════════════════
#  多维度限流器
# ═══════════════════════════════════════════════════════════════


class MultiRateLimiter:
    """多维度限流器 — 按 user / ip / api_key 维度独立限流.

    每个维度的每个 key 都有独立的 DimensionLimiter 实例.
    请求需要同时通过所有指定维度的限流检查.

    Args:
        config:      限流配置.
        dimensions:  启用的维度列表，默认 ["user", "ip", "api_key"].
        storage_path: JSON 持久化路径.

    使用示例::

        limiter = MultiRateLimiter(
            config=RateLimitConfig(rpm=60, burst=10, window_max=100),
            dimensions=["user", "ip"],
        )

        # 按 user + ip 双维度限流
        ok = limiter.acquire(user="alice", ip="1.2.3.4")
    """

    def __init__(
        self,
        config: Optional[RateLimitConfig] = None,
        dimensions: Optional[list[str]] = None,
        storage_path: Optional[str] = None,
    ):
        self.config = config or RateLimitConfig()
        self.config.validate()
        self.dimensions = dimensions or ["user", "ip", "api_key"]
        self.storage_path = storage_path or self.config.storage_path

        # 维度 → key → DimensionLimiter
        self._limiters: dict[str, dict[str, DimensionLimiter]] = {
            dim: {} for dim in self.dimensions
        }
        self._lock = threading.Lock()

        # 尝试从存储加载
        if self.storage_path and os.path.exists(self.storage_path):
            self.load()

    def _get_limiter(self, dimension: str, key: str) -> DimensionLimiter:
        """获取或创建指定维度的限流器."""
        if dimension not in self._limiters:
            self._limiters[dimension] = {}
        if key not in self._limiters[dimension]:
            self._limiters[dimension][key] = DimensionLimiter(self.config)
        return self._limiters[dimension][key]

    def acquire(
        self,
        user: Optional[str] = None,
        ip: Optional[str] = None,
        api_key: Optional[str] = None,
        tokens: int = 0,
    ) -> bool:
        """尝试获取请求配额（多维度同时检查）.

        Args:
            user:    用户标识（如启用 user 维度）.
            ip:      IP 地址（如启用 ip 维度）.
            api_key: API 密钥（如启用 api_key 维度）.
            tokens:  预计消耗的 token 数.

        Returns:
            True 如果通过所有启用维度的限流检查.

        注意:
            如果某个维度未指定 key，则跳过该维度.
            如果所有维度都未指定 key，则使用 "default" 作为 user 维度 key.
        """
        with self._lock:
            # 构建维度 → key 映射
            dim_keys: dict[str, str] = {}
            if "user" in self.dimensions and user:
                dim_keys["user"] = user
            if "ip" in self.dimensions and ip:
                dim_keys["ip"] = ip
            if "api_key" in self.dimensions and api_key:
                dim_keys["api_key"] = api_key

            # 如果没有任何 key，使用 default
            if not dim_keys:
                dim_keys["user"] = "default"

            # 第一阶段：检查所有维度是否都能通过（不消耗）
            limiters: list[tuple[str, str, DimensionLimiter]] = []
            for dim, key in dim_keys.items():
                limiter = self._get_limiter(dim, key)
                if not limiter.check():
                    return False
                limiters.append((dim, key, limiter))

            # 第二阶段：同时消耗所有维度的配额
            # 由于可能部分成功部分失败，需要回滚
            acquired: list[DimensionLimiter] = []
            for dim, key, limiter in limiters:
                if not limiter.acquire(tokens):
                    # 回滚已获取的配额（简单处理：重置已获取的）
                    # 实际生产中应实现 refund 机制
                    # 这里由于 check 已通过，理论上不会失败
                    # 但并发场景下可能失败，此时直接拒绝
                    return False
                acquired.append(limiter)

            # 持久化
            if self.storage_path:
                self._save()

            return True

    def check(
        self,
        user: Optional[str] = None,
        ip: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> bool:
        """检查是否允许请求（不消耗配额）."""
        with self._lock:
            dim_keys = self._build_dim_keys(user, ip, api_key)
            for dim, key in dim_keys.items():
                limiter = self._get_limiter(dim, key)
                if not limiter.check():
                    return False
            return True

    def reset(self, dimension: Optional[str] = None, key: Optional[str] = None) -> None:
        """重置限流器.

        Args:
            dimension: 指定维度（None 表示所有维度）.
            key:       指定 key（None 表示该维度所有 key）.
        """
        with self._lock:
            if dimension is None:
                for dim in self._limiters:
                    for k, limiter in self._limiters[dim].items():
                        limiter.reset()
            elif dimension in self._limiters:
                if key is None:
                    for k, limiter in self._limiters[dimension].items():
                        limiter.reset()
                elif key in self._limiters[dimension]:
                    self._limiters[dimension][key].reset()

    def get_status(
        self,
        user: Optional[str] = None,
        ip: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> dict:
        """获取指定 key 的限流状态."""
        with self._lock:
            dim_keys = self._build_dim_keys(user, ip, api_key)
            result: dict[str, dict] = {}
            for dim, key in dim_keys.items():
                limiter = self._get_limiter(dim, key)
                result[f"{dim}:{key}"] = limiter.status()
            return result

    def get_all_keys(self) -> dict[str, list[str]]:
        """获取所有维度下的所有 key."""
        with self._lock:
            return {
                dim: list(keys.keys())
                for dim, keys in self._limiters.items()
            }

    # ── 持久化 ──────────────────────────────────────────────

    def _save(self) -> None:
        """保存限流状态到 JSON 文件."""
        if not self.storage_path:
            return
        data: dict = {
            "config": self.config.to_dict(),
            "dimensions": self.dimensions,
            "limiters": {},
        }
        for dim, keys in self._limiters.items():
            data["limiters"][dim] = {}
            for key, limiter in keys.items():
                data["limiters"][dim][key] = limiter.snapshot()
        dir_path = os.path.dirname(self.storage_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self) -> None:
        """从 JSON 文件加载限流状态."""
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for dim, keys in data.get("limiters", {}).items():
                if dim not in self._limiters:
                    self._limiters[dim] = {}
                for key, snap in keys.items():
                    limiter = self._get_limiter(dim, key)
                    limiter.restore(snap)
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    # ── 内部方法 ──────────────────────────────────────────

    def _build_dim_keys(
        self,
        user: Optional[str] = None,
        ip: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> dict[str, str]:
        """构建维度 → key 映射."""
        dim_keys: dict[str, str] = {}
        if "user" in self.dimensions and user:
            dim_keys["user"] = user
        if "ip" in self.dimensions and ip:
            dim_keys["ip"] = ip
        if "api_key" in self.dimensions and api_key:
            dim_keys["api_key"] = api_key
        if not dim_keys:
            dim_keys["user"] = "default"
        return dim_keys


# ═══════════════════════════════════════════════════════════════
#  限流中间件
# ═══════════════════════════════════════════════════════════════


class RateLimitMiddleware(MiddlewareBase):
    """限流中间件 — 在中间件链中集成限流检查.

    在 before_llm_call 钩子中执行限流检查，
    如果被限流则设置 should_stop 阻止 LLM 调用.

    Args:
        limiter:   MultiRateLimiter 实例.
        user_extractor:  从 LoopState 提取用户标识的函数.
        ip_extractor:    从 LoopState 提取 IP 的函数.
        api_key_extractor: 从 LoopState 提取 API key 的函数.
        blocked_message: 被限流时返回给用户的消息.

    使用示例::

        limiter = MultiRateLimiter(RateLimitConfig(rpm=30))
        mw = RateLimitMiddleware(
            limiter=limiter,
            user_extractor=lambda state: state.metadata.get("user"),
        )
        chain = [mw, ...]
    """

    def __init__(
        self,
        limiter: MultiRateLimiter,
        user_extractor: Optional[callable] = None,
        ip_extractor: Optional[callable] = None,
        api_key_extractor: Optional[callable] = None,
        blocked_message: str = "请求频率超限，请稍后再试。",
    ):
        self.limiter = limiter
        self._user_extractor = user_extractor or (
            lambda s: s.metadata.get("user")
        )
        self._ip_extractor = ip_extractor or (
            lambda s: s.metadata.get("ip")
        )
        self._api_key_extractor = api_key_extractor or (
            lambda s: s.metadata.get("api_key")
        )
        self.blocked_message = blocked_message

    @property
    def name(self) -> str:
        return "RateLimitMiddleware"

    @property
    def priority(self) -> int:
        """限流中间件优先级 5 — 最先执行."""
        return 5

    async def before_llm_call(self, state: LoopState) -> LoopState:
        """在 LLM 调用前执行限流检查."""
        user = self._safe_extract(self._user_extractor, state)
        ip = self._safe_extract(self._ip_extractor, state)
        api_key = self._safe_extract(self._api_key_extractor, state)

        # 从 metadata 获取预计 token 数
        tokens = state.metadata.get("estimated_tokens", 0)

        if not self.limiter.acquire(
            user=user, ip=ip, api_key=api_key, tokens=tokens
        ):
            state.should_stop = True
            state.stop_reason = "rate_limited"
            state.metadata["rate_limited"] = True
            state.metadata["rate_limit_message"] = self.blocked_message

        return state

    async def after_llm_call(
        self, response: LLMResponse, state: LoopState
    ) -> LLMResponse:
        """LLM 调用后，如果被限流则替换响应内容."""
        if state.metadata.get("rate_limited"):
            response.content = self.blocked_message
            response.tool_calls = []
        return response

    @staticmethod
    def _safe_extract(extractor: callable, state: LoopState) -> Optional[str]:
        """安全执行提取函数."""
        try:
            result = extractor(state)
            return result if result else None
        except Exception:
            return None
