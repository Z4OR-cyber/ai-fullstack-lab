"""
Suyi Phase 12 — 多维度限流模块.

支持令牌桶 + 滑动窗口双算法，可按用户/IP/API 维度独立限流，
并提供中间件集成.

Exports:
    Config:
        RateLimitConfig
    Algorithms:
        RateLimitAlgorithm, TokenBucket, SlidingWindow
    Limiter:
        DimensionLimiter, MultiRateLimiter
    Middleware:
        RateLimitMiddleware

Usage::

    from suyi.ratelimit import (
        MultiRateLimiter, RateLimitConfig, RateLimitMiddleware,
    )

    # 创建多维度限流器
    limiter = MultiRateLimiter(
        config=RateLimitConfig(rpm=60, burst=10, window_max=100),
        dimensions=["user", "ip"],
    )

    # 限流检查
    if limiter.acquire(user="alice", ip="1.2.3.4"):
        # 放行
        ...

    # 中间件集成
    mw = RateLimitMiddleware(limiter=limiter)
"""

from .limiter import (
    RateLimitConfig,
    RateLimitAlgorithm,
    TokenBucket,
    SlidingWindow,
    DimensionLimiter,
    MultiRateLimiter,
    RateLimitMiddleware,
)

__all__ = [
    "RateLimitConfig",
    "RateLimitAlgorithm",
    "TokenBucket",
    "SlidingWindow",
    "DimensionLimiter",
    "MultiRateLimiter",
    "RateLimitMiddleware",
]
