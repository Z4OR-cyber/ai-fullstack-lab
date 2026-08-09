"""
Tests for Phase 12 — Rate Limiter Module.

Tests cover:
    - TokenBucket: consume, refill, capacity, reset, snapshot, restore
    - SlidingWindow: allow, window expiry, count, reset, snapshot, restore
    - DimensionLimiter: dual algorithm check, token tracking, status
    - MultiRateLimiter: multi-dimension acquire, check, reset, status, persistence
    - RateLimitMiddleware: before_llm_call integration, blocked message
    - RateLimitConfig: validation, serialization

All tests use no external API calls.
"""

import asyncio
import json
import os
import tempfile
import time
import pytest

from suyi.ratelimit import (
    RateLimitConfig,
    RateLimitAlgorithm,
    TokenBucket,
    SlidingWindow,
    DimensionLimiter,
    MultiRateLimiter,
    RateLimitMiddleware,
)
from suyi.core.loop import LoopState, LLMResponse


# ═══════════════════════════════════════════════════════════════
#  RateLimitConfig
# ═══════════════════════════════════════════════════════════════


class TestRateLimitConfig:
    """限流配置测试."""

    def test_default_config(self):
        config = RateLimitConfig()
        assert config.rpm == 60
        assert config.burst == 10
        assert config.window_size == 60.0
        assert config.window_max == 100

    def test_custom_config(self):
        config = RateLimitConfig(rpm=120, burst=20, window_size=30, window_max=50)
        assert config.rpm == 120
        assert config.burst == 20
        assert config.window_size == 30
        assert config.window_max == 50

    def test_validate_valid(self):
        config = RateLimitConfig()
        config.validate()  # 不应抛出异常

    def test_validate_invalid_rpm(self):
        config = RateLimitConfig(rpm=0)
        with pytest.raises(ValueError, match="rpm"):
            config.validate()

    def test_validate_invalid_burst(self):
        config = RateLimitConfig(burst=-1)
        with pytest.raises(ValueError, match="burst"):
            config.validate()

    def test_validate_invalid_window_size(self):
        config = RateLimitConfig(window_size=0)
        with pytest.raises(ValueError, match="window_size"):
            config.validate()

    def test_validate_invalid_window_max(self):
        config = RateLimitConfig(window_max=0)
        with pytest.raises(ValueError, match="window_max"):
            config.validate()

    def test_serialization(self):
        config = RateLimitConfig(rpm=100, burst=15)
        d = config.to_dict()
        assert d["rpm"] == 100
        restored = RateLimitConfig.from_dict(d)
        assert restored.rpm == 100
        assert restored.burst == 15


# ═══════════════════════════════════════════════════════════════
#  TokenBucket
# ═══════════════════════════════════════════════════════════════


class TestTokenBucket:
    """令牌桶测试."""

    def test_initial_full(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.available() == pytest.approx(10, abs=0.1)

    def test_consume(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.try_acquire(3) is True
        assert bucket.available() == pytest.approx(7, abs=0.1)

    def test_consume_exact(self):
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        assert bucket.try_acquire(5) is True
        assert bucket.available() < 0.1

    def test_consume_more_than_available(self):
        bucket = TokenBucket(capacity=3, refill_rate=1.0)
        assert bucket.try_acquire(5) is False

    def test_refill(self):
        bucket = TokenBucket(capacity=10, refill_rate=10.0)  # 10 tokens/sec
        bucket.try_acquire(10)  # 清空
        assert bucket.available() < 0.1
        time.sleep(0.15)  # 等待填充
        assert bucket.available() > 0.5

    def test_refill_max_capacity(self):
        bucket = TokenBucket(capacity=5, refill_rate=100.0)
        bucket.try_acquire(2)
        time.sleep(0.05)
        assert bucket.available() <= 5.0  # 不超过容量

    def test_reset(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        bucket.try_acquire(5)
        bucket.reset()
        assert bucket.available() == pytest.approx(10, abs=0.1)

    def test_check(self):
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        assert bucket.check() is True
        bucket.try_acquire(5)
        assert bucket.check() is False

    def test_snapshot_restore(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        bucket.try_acquire(4)
        snap = bucket.snapshot()
        assert snap["capacity"] == 10
        assert snap["tokens"] == pytest.approx(6, abs=0.5)

        bucket2 = TokenBucket(capacity=10, refill_rate=1.0)
        bucket2.restore(snap)
        assert bucket2.available() == pytest.approx(6, abs=0.5)

    def test_repr(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        r = repr(bucket)
        assert "TokenBucket" in r


# ═══════════════════════════════════════════════════════════════
#  SlidingWindow
# ═══════════════════════════════════════════════════════════════


class TestSlidingWindow:
    """滑动窗口测试."""

    def test_initial_empty(self):
        window = SlidingWindow(window_size=60, max_requests=10)
        assert window.available() == 10
        assert window.current_count == 0

    def test_acquire(self):
        window = SlidingWindow(window_size=60, max_requests=5)
        assert window.try_acquire(1) is True
        assert window.current_count == 1
        assert window.available() == 4

    def test_acquire_multiple(self):
        window = SlidingWindow(window_size=60, max_requests=10)
        assert window.try_acquire(3) is True
        assert window.current_count == 3

    def test_acquire_exceed_max(self):
        window = SlidingWindow(window_size=60, max_requests=3)
        window.try_acquire(3)
        assert window.try_acquire(1) is False

    def test_window_expiry(self):
        window = SlidingWindow(window_size=0.1, max_requests=2)
        window.try_acquire(2)
        assert window.try_acquire(1) is False
        time.sleep(0.15)  # 等待窗口过期
        assert window.try_acquire(1) is True

    def test_reset(self):
        window = SlidingWindow(window_size=60, max_requests=5)
        window.try_acquire(3)
        window.reset()
        assert window.current_count == 0
        assert window.available() == 5

    def test_check(self):
        window = SlidingWindow(window_size=60, max_requests=2)
        assert window.check() is True
        window.try_acquire(2)
        assert window.check() is False

    def test_snapshot(self):
        window = SlidingWindow(window_size=60, max_requests=10)
        window.try_acquire(3)
        snap = window.snapshot()
        assert snap["max_requests"] == 10
        assert snap["current_count"] == 3

    def test_restore(self):
        window = SlidingWindow(window_size=60, max_requests=10)
        window.try_acquire(3)
        snap = window.snapshot()

        window2 = SlidingWindow(window_size=60, max_requests=10)
        window2.restore(snap)
        # 滑动窗口恢复后是空的（时间戳无法精确恢复）
        assert window2.current_count == 0

    def test_repr(self):
        window = SlidingWindow(window_size=60, max_requests=10)
        assert "SlidingWindow" in repr(window)


# ═══════════════════════════════════════════════════════════════
#  DimensionLimiter
# ═══════════════════════════════════════════════════════════════


class TestDimensionLimiter:
    """单维度限流器测试."""

    def test_basic_acquire(self):
        config = RateLimitConfig(rpm=60, burst=5, window_max=10)
        limiter = DimensionLimiter(config)
        assert limiter.acquire() is True

    def test_burst_limit(self):
        config = RateLimitConfig(rpm=6, burst=3, window_size=60, window_max=100)
        limiter = DimensionLimiter(config)
        # 令牌桶容量 3，突发 3 个
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        # 第 4 个应该被令牌桶拒绝（填充速率 0.1 tokens/sec，来不及填充）
        assert limiter.acquire() is False

    def test_sliding_window_limit(self):
        config = RateLimitConfig(rpm=1000, burst=1000, window_size=60, window_max=3)
        limiter = DimensionLimiter(config)
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        # 滑动窗口满了
        assert limiter.acquire() is False

    def test_token_tracking(self):
        config = RateLimitConfig(rpm=60, burst=10, window_max=100, tpm=100)
        limiter = DimensionLimiter(config)
        # tpm=100, burst=10 → 桶容量 100
        assert limiter.acquire(tokens=50) is True
        assert limiter.acquire(tokens=60) is False  # 50+60 > 100

    def test_check(self):
        config = RateLimitConfig(rpm=6, burst=2, window_max=10)
        limiter = DimensionLimiter(config)
        assert limiter.check() is True
        limiter.acquire()
        limiter.acquire()
        assert limiter.check() is False

    def test_reset(self):
        config = RateLimitConfig(rpm=6, burst=2, window_max=5)
        limiter = DimensionLimiter(config)
        limiter.acquire()
        limiter.acquire()
        limiter.reset()
        assert limiter.check() is True

    def test_status(self):
        config = RateLimitConfig(rpm=60, burst=10, window_max=20, tpm=1000)
        limiter = DimensionLimiter(config)
        limiter.acquire()
        status = limiter.status()
        assert "request_bucket_available" in status
        assert "sliding_window_available" in status
        assert "sliding_window_count" in status
        assert "token_bucket_available" in status

    def test_no_token_limit(self):
        config = RateLimitConfig(rpm=60, burst=10, window_max=100, tpm=0)
        limiter = DimensionLimiter(config)
        status = limiter.status()
        assert status["token_bucket_available"] is None

    def test_snapshot_restore(self):
        config = RateLimitConfig(rpm=60, burst=10, window_max=20)
        limiter = DimensionLimiter(config)
        limiter.acquire()
        snap = limiter.snapshot()

        limiter2 = DimensionLimiter(config)
        limiter2.restore(snap)
        # 验证恢复后状态正确（令牌桶）
        assert limiter2.status()["request_bucket_available"] < 10


# ═══════════════════════════════════════════════════════════════
#  MultiRateLimiter
# ═══════════════════════════════════════════════════════════════


class TestMultiRateLimiter:
    """多维度限流器测试."""

    def test_basic_acquire(self):
        config = RateLimitConfig(rpm=60, burst=10, window_max=100)
        limiter = MultiRateLimiter(config)
        assert limiter.acquire(user="alice") is True

    def test_multi_dimension(self):
        config = RateLimitConfig(rpm=60, burst=10, window_max=100)
        limiter = MultiRateLimiter(
            config, dimensions=["user", "ip"]
        )
        assert limiter.acquire(user="alice", ip="1.2.3.4") is True

    def test_independent_keys(self):
        config = RateLimitConfig(rpm=6, burst=2, window_size=60, window_max=100)
        limiter = MultiRateLimiter(config, dimensions=["user"])
        # alice 的额度
        assert limiter.acquire(user="alice") is True
        assert limiter.acquire(user="alice") is True
        assert limiter.acquire(user="alice") is False  # alice 额度用完
        # bob 有独立额度
        assert limiter.acquire(user="bob") is True

    def test_check(self):
        config = RateLimitConfig(rpm=6, burst=2, window_max=10)
        limiter = MultiRateLimiter(config, dimensions=["user"])
        assert limiter.check(user="alice") is True
        limiter.acquire(user="alice")
        limiter.acquire(user="alice")
        assert limiter.check(user="alice") is False

    def test_default_key(self):
        config = RateLimitConfig(rpm=60, burst=10, window_max=100)
        limiter = MultiRateLimiter(config)
        # 没有指定 key，使用 default
        assert limiter.acquire() is True
        keys = limiter.get_all_keys()
        assert "default" in keys["user"]

    def test_reset_all(self):
        config = RateLimitConfig(rpm=6, burst=2, window_max=10)
        limiter = MultiRateLimiter(config, dimensions=["user"])
        limiter.acquire(user="alice")
        limiter.acquire(user="alice")
        limiter.reset()
        assert limiter.check(user="alice") is True

    def test_reset_dimension_key(self):
        config = RateLimitConfig(rpm=6, burst=2, window_max=10)
        limiter = MultiRateLimiter(config, dimensions=["user"])
        limiter.acquire(user="alice")
        limiter.acquire(user="alice")
        limiter.reset(dimension="user", key="alice")
        assert limiter.check(user="alice") is True

    def test_get_status(self):
        config = RateLimitConfig(rpm=60, burst=10, window_max=20)
        limiter = MultiRateLimiter(config, dimensions=["user", "ip"])
        limiter.acquire(user="alice", ip="1.2.3.4")
        status = limiter.get_status(user="alice", ip="1.2.3.4")
        assert "user:alice" in status
        assert "ip:1.2.3.4" in status

    def test_get_all_keys(self):
        config = RateLimitConfig(rpm=60, burst=10, window_max=100)
        limiter = MultiRateLimiter(config, dimensions=["user", "ip"])
        limiter.acquire(user="alice", ip="1.1.1.1")
        limiter.acquire(user="bob", ip="2.2.2.2")
        keys = limiter.get_all_keys()
        assert "alice" in keys["user"]
        assert "bob" in keys["user"]
        assert "1.1.1.1" in keys["ip"]
        assert "2.2.2.2" in keys["ip"]

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "ratelimit.json")
            config = RateLimitConfig(
                rpm=60, burst=10, window_max=100, storage_path=path
            )
            limiter = MultiRateLimiter(config, dimensions=["user"])
            limiter.acquire(user="alice")

            # 创建新实例加载
            config2 = RateLimitConfig(
                rpm=60, burst=10, window_max=100, storage_path=path
            )
            limiter2 = MultiRateLimiter(config2, dimensions=["user"])
            keys = limiter2.get_all_keys()
            assert "alice" in keys["user"]

    def test_api_key_dimension(self):
        config = RateLimitConfig(rpm=6, burst=2, window_max=10)
        limiter = MultiRateLimiter(config, dimensions=["api_key"])
        assert limiter.acquire(api_key="sk-xxx") is True
        assert limiter.acquire(api_key="sk-xxx") is True
        assert limiter.acquire(api_key="sk-xxx") is False

    def test_config_validation(self):
        config = RateLimitConfig(rpm=0)
        with pytest.raises(ValueError):
            MultiRateLimiter(config)

    def test_all_three_dimensions(self):
        config = RateLimitConfig(rpm=6, burst=3, window_size=60, window_max=100)
        limiter = MultiRateLimiter(config, dimensions=["user", "ip", "api_key"])
        # 同一请求消耗三个维度的配额
        assert limiter.acquire(user="alice", ip="1.1.1.1", api_key="sk-1") is True
        assert limiter.acquire(user="alice", ip="1.1.1.1", api_key="sk-1") is True
        assert limiter.acquire(user="alice", ip="1.1.1.1", api_key="sk-1") is True
        # 令牌桶用完
        assert limiter.acquire(user="alice", ip="1.1.1.1", api_key="sk-1") is False
        # 但新 user 有独立额度（使用不同的 ip 和 api_key 避免共享维度限流）
        assert limiter.acquire(user="bob", ip="2.2.2.2", api_key="sk-2") is True


# ═══════════════════════════════════════════════════════════════
#  RateLimitMiddleware
# ═══════════════════════════════════════════════════════════════


class TestRateLimitMiddleware:
    """限流中间件测试."""

    async def test_middleware_allows(self):
        config = RateLimitConfig(rpm=60, burst=10, window_max=100)
        limiter = MultiRateLimiter(config, dimensions=["user"])
        mw = RateLimitMiddleware(limiter=limiter)

        state = LoopState(history=[], turn=0, metadata={"user": "alice"})
        result_state = await mw.before_llm_call(state)
        assert result_state.should_stop is False
        assert result_state.metadata.get("rate_limited") is not True

    async def test_middleware_blocks(self):
        config = RateLimitConfig(rpm=6, burst=2, window_size=60, window_max=100)
        limiter = MultiRateLimiter(config, dimensions=["user"])
        mw = RateLimitMiddleware(limiter=limiter)

        # 消耗完额度
        limiter.acquire(user="alice")
        limiter.acquire(user="alice")

        state = LoopState(history=[], turn=0, metadata={"user": "alice"})
        result_state = await mw.before_llm_call(state)
        assert result_state.should_stop is True
        assert result_state.stop_reason == "rate_limited"
        assert result_state.metadata.get("rate_limited") is True

    async def test_middleware_after_llm_blocked(self):
        config = RateLimitConfig(rpm=6, burst=1, window_size=60, window_max=100)
        limiter = MultiRateLimiter(config, dimensions=["user"])
        mw = RateLimitMiddleware(limiter=limiter)

        limiter.acquire(user="alice")

        state = LoopState(history=[], turn=0, metadata={"user": "alice"})
        await mw.before_llm_call(state)

        response = LLMResponse.text("原始回答")
        result = await mw.after_llm_call(response, state)
        assert result.content == mw.blocked_message
        assert len(result.tool_calls) == 0

    async def test_middleware_custom_extractors(self):
        config = RateLimitConfig(rpm=6, burst=1, window_size=60, window_max=100)
        limiter = MultiRateLimiter(config, dimensions=["user"])

        def extract_user(state):
            return state.metadata.get("current_user")

        mw = RateLimitMiddleware(
            limiter=limiter,
            user_extractor=extract_user,
        )
        limiter.acquire(user="charlie")

        state = LoopState(history=[], turn=0, metadata={"current_user": "charlie"})
        result_state = await mw.before_llm_call(state)
        assert result_state.should_stop is True

    def test_middleware_priority(self):
        config = RateLimitConfig(rpm=60, burst=10, window_max=100)
        limiter = MultiRateLimiter(config)
        mw = RateLimitMiddleware(limiter=limiter)
        assert mw.priority == 5  # 最先执行

    def test_middleware_name(self):
        config = RateLimitConfig(rpm=60, burst=10, window_max=100)
        limiter = MultiRateLimiter(config)
        mw = RateLimitMiddleware(limiter=limiter)
        assert mw.name == "RateLimitMiddleware"

    async def test_middleware_custom_message(self):
        config = RateLimitConfig(rpm=6, burst=1, window_size=60, window_max=100)
        limiter = MultiRateLimiter(config, dimensions=["user"])
        mw = RateLimitMiddleware(
            limiter=limiter,
            blocked_message="自定义限流消息",
        )
        limiter.acquire(user="alice")

        state = LoopState(history=[], turn=0, metadata={"user": "alice"})
        await mw.before_llm_call(state)

        response = LLMResponse.text("回答")
        result = await mw.after_llm_call(response, state)
        assert result.content == "自定义限流消息"

    async def test_middleware_no_user(self):
        """没有 user 信息时使用 default key."""
        config = RateLimitConfig(rpm=60, burst=10, window_max=100)
        limiter = MultiRateLimiter(config, dimensions=["user"])
        mw = RateLimitMiddleware(limiter=limiter)

        state = LoopState(history=[], turn=0, metadata={})
        result_state = await mw.before_llm_call(state)
        assert result_state.should_stop is False

    async def test_middleware_with_tokens(self):
        """测试带 token 估计的限流."""
        config = RateLimitConfig(rpm=60, burst=10, window_max=100, tpm=50)
        limiter = MultiRateLimiter(config, dimensions=["user"])
        mw = RateLimitMiddleware(limiter=limiter)

        # 第一次请求消耗 30 token
        state = LoopState(
            history=[], turn=0,
            metadata={"user": "alice", "estimated_tokens": 30},
        )
        await mw.before_llm_call(state)
        assert state.should_stop is False

        # 第二次请求消耗 30 token（总共 60 > 50）
        state2 = LoopState(
            history=[], turn=0,
            metadata={"user": "alice", "estimated_tokens": 30},
        )
        await mw.before_llm_call(state2)
        assert state2.should_stop is True
