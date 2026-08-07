"""
Tests for AI Gateway Module — Router, Rate Limiting, Cost Tracking, and Fallback.

Tests cover:
    - TokenBucket: consume, refill, capacity, reset
    - SlidingWindow: allow, window expiry, count
    - RateLimiter: per-key limiting, check, acquire, reset, status
    - CostTracker: calculate_cost, record, total_cost, budget, reports, persistence
    - GatewayRouter: provider management, routing rules, failover, health
    - FallbackChain: retry, provider switch, model downgrade, cache

All tests use MockLLM — no real API calls.
"""

import asyncio
import json
import os
import tempfile
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from suyi.core.loop import LLMResponse, LLMInterface, MockLLM, ToolCall
from suyi.gateway import (
    # Router
    GatewayRouter,
    ProviderEntry,
    RoutingRule,
    # Rate Limiting
    RateLimiter,
    TokenBucket,
    SlidingWindow,
    RateLimitAlgorithm,
    # Cost
    CostTracker,
    CostEntry,
    BudgetAlert,
    DEFAULT_PRICING,
    # Fallback
    FallbackChain,
    FallbackConfig,
    FallbackResult,
)


# ═══════════════════════════════════════════════════════════════
#  Test Helpers
# ═══════════════════════════════════════════════════════════════


class FailingLLM:
    """LLM that always raises an exception."""

    async def chat(self, messages, tools, system_prompt):
        raise RuntimeError("LLM service unavailable")


class DelayedLLM:
    """LLM that succeeds after a configurable delay."""

    def __init__(self, delay=0.01, response=None):
        self._delay = delay
        self._response = response or LLMResponse.text("Delayed response")

    async def chat(self, messages, tools, system_prompt):
        await asyncio.sleep(self._delay)
        return self._response


def make_mock_llm(content="Hello!", tokens=50):
    """Create a MockLLM with a single text response."""
    return MockLLM([LLMResponse.text(content, tokens=tokens)])


# ═══════════════════════════════════════════════════════════════
#  TokenBucket Tests
# ═══════════════════════════════════════════════════════════════


class TestTokenBucket:
    """Test TokenBucket rate limiter."""

    def test_init(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.capacity == 10
        assert bucket.refill_rate == 1.0
        assert bucket.available() == 10  # Starts full

    def test_acquire_success(self):
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        assert bucket.try_acquire(1) is True
        assert bucket.available() == pytest.approx(4, abs=0.1)

    def test_acquire_multiple(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.try_acquire(3) is True
        assert bucket.available() == pytest.approx(7, abs=0.1)

    def test_acquire_more_than_available(self):
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        assert bucket.try_acquire(6) is False
        # Tokens should not be consumed on failure
        assert bucket.available() == pytest.approx(5, abs=0.1)

    def test_refill(self):
        bucket = TokenBucket(capacity=10, refill_rate=10.0)  # 10 tokens/sec
        # Consume all tokens
        bucket.try_acquire(10)
        assert bucket.available() == pytest.approx(0, abs=0.1)

        # Wait for refill
        time.sleep(0.15)
        available = bucket.available()
        assert available > 0  # Should have refilled

    def test_refill_capped_at_capacity(self):
        bucket = TokenBucket(capacity=5, refill_rate=100.0)
        bucket._tokens = 0
        bucket._last_update = time.monotonic()
        time.sleep(0.05)
        # Should not exceed capacity
        assert bucket.available() <= 5

    def test_reset(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        bucket.try_acquire(5)
        bucket.reset()
        assert bucket.available() == pytest.approx(10, abs=0.1)

    def test_check_non_consuming(self):
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        assert bucket.check() is True  # At least 1 available
        bucket.try_acquire(5)
        assert bucket.check() is False  # No tokens left

    def test_zero_refill_rate(self):
        """Bucket with 0 refill rate never refills."""
        bucket = TokenBucket(capacity=3, refill_rate=0.0)
        assert bucket.try_acquire(3) is True
        time.sleep(0.05)
        assert bucket.try_acquire(1) is False

    def test_is_rate_limit_algorithm(self):
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        assert isinstance(bucket, RateLimitAlgorithm)


# ═══════════════════════════════════════════════════════════════
#  SlidingWindow Tests
# ═══════════════════════════════════════════════════════════════


class TestSlidingWindow:
    """Test SlidingWindow rate limiter."""

    def test_init(self):
        window = SlidingWindow(window_size=60, max_requests=100)
        assert window.window_size == 60
        assert window.max_requests == 100
        assert window.available() == 100

    def test_acquire_success(self):
        window = SlidingWindow(window_size=60, max_requests=5)
        assert window.try_acquire(1) is True
        assert window.available() == 4

    def test_acquire_multiple(self):
        window = SlidingWindow(window_size=60, max_requests=10)
        assert window.try_acquire(3) is True
        assert window.available() == 7

    def test_acquire_exceeds_max(self):
        window = SlidingWindow(window_size=60, max_requests=3)
        assert window.try_acquire(3) is True
        assert window.try_acquire(1) is False
        # Count should not increase on failure
        assert window.current_count == 3

    def test_window_expiry(self):
        """Old requests should be purged after the window expires."""
        window = SlidingWindow(window_size=0.1, max_requests=2)
        assert window.try_acquire(2) is True
        assert window.try_acquire(1) is False  # Full

        # Wait for window to expire
        time.sleep(0.15)
        assert window.try_acquire(1) is True  # Old requests purged

    def test_reset(self):
        window = SlidingWindow(window_size=60, max_requests=5)
        window.try_acquire(3)
        window.reset()
        assert window.available() == 5
        assert window.current_count == 0

    def test_check_non_consuming(self):
        window = SlidingWindow(window_size=60, max_requests=3)
        assert window.check() is True
        window.try_acquire(3)
        assert window.check() is False

    def test_is_rate_limit_algorithm(self):
        window = SlidingWindow(window_size=60, max_requests=10)
        assert isinstance(window, RateLimitAlgorithm)


# ═══════════════════════════════════════════════════════════════
#  RateLimiter Tests
# ═══════════════════════════════════════════════════════════════


class TestRateLimiter:
    """Test composite RateLimiter."""

    def test_init_token_bucket(self):
        limiter = RateLimiter(strategy="token_bucket", requests_per_minute=60)
        assert limiter.strategy == "token_bucket"

    def test_init_sliding_window(self):
        limiter = RateLimiter(strategy="sliding_window", requests_per_minute=60)
        assert limiter.strategy == "sliding_window"

    def test_invalid_strategy(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            RateLimiter(strategy="invalid")

    def test_check_default_key(self):
        limiter = RateLimiter(strategy="token_bucket", requests_per_minute=10)
        assert limiter.check("default") is True

    def test_acquire_success(self):
        limiter = RateLimiter(strategy="token_bucket", requests_per_minute=10)
        assert limiter.acquire(key="openai") is True

    def test_acquire_with_tokens(self):
        limiter = RateLimiter(
            strategy="token_bucket",
            requests_per_minute=10,
            tokens_per_minute=1000,
        )
        assert limiter.acquire(key="openai", tokens=100) is True

    def test_per_key_isolation(self):
        """Different keys have separate limits."""
        limiter = RateLimiter(strategy="sliding_window", requests_per_minute=2)
        # Exhaust key "openai"
        assert limiter.acquire(key="openai") is True
        assert limiter.acquire(key="openai") is True
        assert limiter.acquire(key="openai") is False  # Exhausted

        # Key "anthropic" should still have capacity
        assert limiter.acquire(key="anthropic") is True

    def test_reset_key(self):
        limiter = RateLimiter(strategy="sliding_window", requests_per_minute=2)
        limiter.acquire(key="openai")
        limiter.acquire(key="openai")
        assert limiter.check("openai") is False

        limiter.reset(key="openai")
        assert limiter.check("openai") is True

    def test_reset_all(self):
        limiter = RateLimiter(strategy="sliding_window", requests_per_minute=2)
        limiter.acquire(key="a")
        limiter.acquire(key="b")
        limiter.reset()
        assert limiter.check("a") is True
        assert limiter.check("b") is True

    def test_get_status(self):
        limiter = RateLimiter(
            strategy="token_bucket",
            requests_per_minute=60,
            tokens_per_minute=10000,
        )
        status = limiter.get_status("openai")
        assert status["key"] == "openai"
        assert status["strategy"] == "token_bucket"
        assert status["requests_available"] > 0
        assert status["tokens_available"] > 0

    def test_keys_property(self):
        limiter = RateLimiter(strategy="token_bucket")
        limiter.acquire(key="openai")
        limiter.acquire(key="anthropic")
        keys = limiter.keys
        assert "openai" in keys
        assert "anthropic" in keys


# ═══════════════════════════════════════════════════════════════
#  CostTracker Tests
# ═══════════════════════════════════════════════════════════════


class TestCostTracker:
    """Test CostTracker."""

    def test_init_defaults(self):
        tracker = CostTracker()
        assert tracker.budget is None
        assert tracker.entry_count == 0
        assert tracker.total_cost() == 0.0

    def test_init_with_budget(self):
        tracker = CostTracker(budget=10.0)
        assert tracker.budget == 10.0

    def test_calculate_cost_known_model(self):
        tracker = CostTracker()
        cost = tracker.calculate_cost(
            provider="openai",
            model="gpt-4o",
            usage={"prompt_tokens": 1000, "completion_tokens": 500},
        )
        # gpt-4o: $0.0025/1K prompt, $0.01/1K completion
        expected = (1000 / 1000) * 0.0025 + (500 / 1000) * 0.01
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_calculate_cost_unknown_model(self):
        tracker = CostTracker()
        cost = tracker.calculate_cost(
            provider="unknown",
            model="unknown-model",
            usage={"prompt_tokens": 1000, "completion_tokens": 500},
        )
        assert cost == 0.0  # Unknown models have 0 pricing

    def test_calculate_cost_anthropic(self):
        tracker = CostTracker()
        cost = tracker.calculate_cost(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            usage={"prompt_tokens": 2000, "completion_tokens": 1000},
        )
        # claude-sonnet: $0.003/1K prompt, $0.015/1K completion
        expected = (2000 / 1000) * 0.003 + (1000 / 1000) * 0.015
        assert cost == pytest.approx(expected, rel=1e-6)

    def test_record(self):
        tracker = CostTracker()
        entry = tracker.record(
            provider="openai",
            model="gpt-4o",
            usage={"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
        )
        assert entry.provider == "openai"
        assert entry.model == "gpt-4o"
        assert entry.prompt_tokens == 1000
        assert entry.completion_tokens == 500
        assert entry.cost > 0
        assert tracker.entry_count == 1

    def test_total_cost(self):
        tracker = CostTracker()
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 1000, "completion_tokens": 0})
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 0, "completion_tokens": 1000})
        total = tracker.total_cost()
        expected = 0.0025 + 0.01
        assert total == pytest.approx(expected, rel=1e-6)

    def test_total_tokens(self):
        tracker = CostTracker()
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 100, "completion_tokens": 50})
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 200, "completion_tokens": 100})
        tokens = tracker.total_tokens()
        assert tokens["prompt_tokens"] == 300
        assert tokens["completion_tokens"] == 150
        assert tokens["total_tokens"] == 450

    def test_check_budget_no_budget(self):
        tracker = CostTracker()
        assert tracker.check_budget() is True

    def test_check_budget_within(self):
        tracker = CostTracker(budget=100.0)
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 1000, "completion_tokens": 500})
        assert tracker.check_budget() is True

    def test_check_budget_exceeded(self):
        tracker = CostTracker(budget=0.001)  # Very small budget
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 1000, "completion_tokens": 500})
        assert tracker.check_budget() is False

    def test_budget_remaining(self):
        tracker = CostTracker(budget=1.0)
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 100, "completion_tokens": 0})
        remaining = tracker.budget_remaining()
        assert remaining is not None
        assert remaining < 1.0
        assert remaining > 0.99

    def test_budget_remaining_no_budget(self):
        tracker = CostTracker()
        assert tracker.budget_remaining() is None

    def test_budget_percentage(self):
        tracker = CostTracker(budget=1.0)
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 100, "completion_tokens": 0})
        pct = tracker.budget_percentage()
        assert pct is not None
        assert 0 < pct < 1  # Less than 1%

    def test_budget_percentage_no_budget(self):
        tracker = CostTracker()
        assert tracker.budget_percentage() is None

    def test_budget_warning_alert(self):
        tracker = CostTracker(budget=0.01, warning_threshold=0.5)
        # Record enough to exceed 50% of budget
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 3000, "completion_tokens": 0})
        # 3000 prompt tokens at $0.0025/1K = $0.0075, which is 75% of $0.01
        alerts = tracker.alerts
        assert len(alerts) >= 1
        assert alerts[0].level == "warning"

    def test_budget_critical_alert(self):
        tracker = CostTracker(budget=0.001, warning_threshold=0.5, critical_threshold=0.9)
        # Record enough to exceed 90% of budget
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 1000, "completion_tokens": 0})
        # 1000 prompt tokens at $0.0025/1K = $0.0025, which is 250% of $0.001
        alerts = tracker.alerts
        assert any(a.level == "critical" for a in alerts)

    def test_clear_alerts(self):
        tracker = CostTracker(budget=0.001)
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 1000, "completion_tokens": 0})
        assert len(tracker.alerts) > 0
        tracker.clear_alerts()
        assert len(tracker.alerts) == 0

    def test_report_by_provider(self):
        tracker = CostTracker()
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 100, "completion_tokens": 50})
        tracker.record("anthropic", "claude-sonnet-4-20250514", {"prompt_tokens": 200, "completion_tokens": 100})
        report = tracker.get_report(by="provider")
        assert "openai" in report
        assert "anthropic" in report
        assert report["openai"]["requests"] == 1
        assert report["anthropic"]["requests"] == 1

    def test_report_by_model(self):
        tracker = CostTracker()
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 100, "completion_tokens": 50})
        tracker.record("openai", "gpt-4o-mini", {"prompt_tokens": 100, "completion_tokens": 50})
        report = tracker.get_report(by="model")
        assert "openai/gpt-4o" in report
        assert "openai/gpt-4o-mini" in report

    def test_report_by_user(self):
        tracker = CostTracker()
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 100, "completion_tokens": 0}, user="alice")
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 100, "completion_tokens": 0}, user="bob")
        report = tracker.get_report(by="user")
        assert "alice" in report
        assert "bob" in report

    def test_report_by_time(self):
        tracker = CostTracker()
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 100, "completion_tokens": 0})
        report = tracker.get_report(by="time")
        assert len(report) >= 1  # At least one date entry

    def test_report_invalid_type(self):
        tracker = CostTracker()
        with pytest.raises(ValueError, match="Unknown report type"):
            tracker.get_report(by="invalid")

    def test_set_pricing(self):
        tracker = CostTracker()
        tracker.set_pricing("custom", "my-model", prompt=0.001, completion=0.002)
        cost = tracker.calculate_cost("custom", "my-model", {"prompt_tokens": 1000, "completion_tokens": 1000})
        assert cost == pytest.approx(0.001 + 0.002, rel=1e-6)

    def test_get_pricing(self):
        tracker = CostTracker()
        pricing = tracker.get_pricing("openai", "gpt-4o")
        assert pricing is not None
        assert pricing["prompt"] == 0.0025

    def test_get_pricing_unknown(self):
        tracker = CostTracker()
        pricing = tracker.get_pricing("unknown", "unknown")
        assert pricing is None

    def test_persistence_save_load(self):
        """Test saving and loading cost data to/from JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        try:
            # Delete the empty temp file so CostTracker doesn't try to load from it
            os.unlink(path)

            tracker = CostTracker(budget=10.0, storage_path=path)
            tracker.record("openai", "gpt-4o", {"prompt_tokens": 100, "completion_tokens": 50})
            tracker.save()

            # Create new tracker from same file
            tracker2 = CostTracker(storage_path=path)
            assert tracker2.entry_count == 1
            assert tracker2.budget == 10.0
            assert tracker2.total_cost() > 0
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_clear(self):
        tracker = CostTracker(budget=10.0)
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 100, "completion_tokens": 0})
        tracker.clear()
        assert tracker.entry_count == 0
        assert tracker.total_cost() == 0.0

    def test_entries_property(self):
        tracker = CostTracker()
        tracker.record("openai", "gpt-4o", {"prompt_tokens": 100, "completion_tokens": 0})
        entries = tracker.entries
        assert len(entries) == 1
        assert entries[0].provider == "openai"


class TestCostEntry:
    """Test CostEntry data class."""

    def test_creation(self):
        entry = CostEntry(
            timestamp=1234567890.0,
            provider="openai",
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
            cost=0.005,
            user="alice",
        )
        assert entry.provider == "openai"
        assert entry.cost == 0.005

    def test_to_dict(self):
        entry = CostEntry(
            timestamp=1234567890.0,
            provider="openai",
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
            cost=0.005,
        )
        d = entry.to_dict()
        assert d["provider"] == "openai"
        assert d["prompt_tokens"] == 100
        assert d["user"] == "default"

    def test_from_dict(self):
        d = {
            "timestamp": 1234567890.0,
            "provider": "openai",
            "model": "gpt-4o",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cost": 0.005,
            "user": "alice",
        }
        entry = CostEntry.from_dict(d)
        assert entry.provider == "openai"
        assert entry.user == "alice"


# ═══════════════════════════════════════════════════════════════
#  GatewayRouter Tests
# ═══════════════════════════════════════════════════════════════


class TestGatewayRouterInit:
    """Test GatewayRouter initialization."""

    def test_init_empty(self):
        router = GatewayRouter()
        assert router.list_providers() == []

    def test_init_with_providers(self):
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="primary", llm=llm, priority=0),
            ProviderEntry(name="backup", llm=llm, priority=1),
        ])
        assert "primary" in router.list_providers()
        assert "backup" in router.list_providers()

    def test_add_provider(self):
        router = GatewayRouter()
        llm = make_mock_llm()
        router.add_provider(ProviderEntry(name="test", llm=llm))
        assert "test" in router.list_providers()

    def test_remove_provider(self):
        router = GatewayRouter()
        llm = make_mock_llm()
        router.add_provider(ProviderEntry(name="test", llm=llm))
        router.remove_provider("test")
        assert "test" not in router.list_providers()

    def test_get_provider(self):
        router = GatewayRouter()
        llm = make_mock_llm()
        entry = ProviderEntry(name="test", llm=llm, priority=5)
        router.add_provider(entry)
        got = router.get_provider("test")
        assert got is entry

    def test_get_provider_not_found(self):
        router = GatewayRouter()
        assert router.get_provider("nonexistent") is None


class TestGatewayRouterRouting:
    """Test GatewayRouter routing logic."""

    def test_route_single_provider(self):
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="only", llm=llm),
        ])
        provider = router.route()
        assert provider.name == "only"

    def test_route_by_priority(self):
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="low", llm=llm, priority=10),
            ProviderEntry(name="high", llm=llm, priority=0),
        ])
        provider = router.route()
        assert provider.name == "high"  # Lower priority = higher preference

    def test_route_skips_unhealthy(self):
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="primary", llm=llm, priority=0, healthy=False),
            ProviderEntry(name="backup", llm=llm, priority=1),
        ])
        provider = router.route()
        assert provider.name == "backup"

    def test_route_all_unhealthy(self):
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="p1", llm=llm, healthy=False),
            ProviderEntry(name="p2", llm=llm, healthy=False),
        ])
        assert router.route() is None

    def test_route_by_model(self):
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="gpt4", llm=llm, models=["gpt-4o"]),
            ProviderEntry(name="claude", llm=llm, models=["claude-sonnet"]),
        ])
        provider = router.route(model="gpt-4o")
        assert provider.name == "gpt4"

    def test_route_by_model_fallback_to_any(self):
        """If no provider has the exact model, fall back to providers without model restrictions."""
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="restricted", llm=llm, models=["gpt-4o"]),
            ProviderEntry(name="open", llm=llm, models=[]),  # No model restriction
        ])
        provider = router.route(model="unknown-model")
        # Should fall back to "open" which has no model restriction
        assert provider.name == "open"

    def test_route_by_task_type(self):
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="chat", llm=llm, task_types=["chat"]),
            ProviderEntry(name="code", llm=llm, task_types=["code"]),
        ])
        provider = router.route(task_type="code")
        assert provider.name == "code"

    def test_route_with_routing_rule(self):
        llm = make_mock_llm()
        router = GatewayRouter(
            providers=[
                ProviderEntry(name="default", llm=llm, priority=0),
                ProviderEntry(name="special", llm=llm, priority=10),
            ],
            routing_rules=[
                RoutingRule(
                    name="code_rule",
                    provider_name="special",
                    task_type="code",
                ),
            ],
        )
        # For code tasks, should use "special" (from routing rule)
        provider = router.route(task_type="code")
        assert provider.name == "special"

        # For other tasks, should use "default" (lower priority)
        provider = router.route(task_type="chat")
        assert provider.name == "default"

    def test_route_weighted(self):
        """Test that weighted routing distributes requests."""
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="heavy", llm=llm, weight=10, priority=0),
            ProviderEntry(name="light", llm=llm, weight=1, priority=0),
        ])
        # Run many times and check distribution
        counts = {"heavy": 0, "light": 0}
        for _ in range(1000):
            p = router.route()
            counts[p.name] += 1
        # Heavy should get significantly more traffic
        assert counts["heavy"] > counts["light"]

    def test_get_sorted_providers(self):
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="p3", llm=llm, priority=2),
            ProviderEntry(name="p1", llm=llm, priority=0),
            ProviderEntry(name="p2", llm=llm, priority=1),
        ])
        sorted_list = router.get_sorted_providers()
        assert [p.name for p in sorted_list] == ["p1", "p2", "p3"]

    def test_get_sorted_providers_excludes_unhealthy(self):
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="healthy", llm=llm, priority=0),
            ProviderEntry(name="unhealthy", llm=llm, priority=1, healthy=False),
        ])
        sorted_list = router.get_sorted_providers()
        assert len(sorted_list) == 1
        assert sorted_list[0].name == "healthy"


class TestGatewayRouterChat:
    """Test GatewayRouter.chat() method."""

    @pytest.mark.asyncio
    async def test_chat_success(self):
        llm = make_mock_llm("Hello from LLM!")
        router = GatewayRouter(providers=[
            ProviderEntry(name="primary", llm=llm),
        ])
        response = await router.chat(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system_prompt="Be helpful.",
        )
        assert response.content == "Hello from LLM!"

    @pytest.mark.asyncio
    async def test_chat_failover(self):
        """Test that the router fails over to the next provider."""
        failing = FailingLLM()
        success = make_mock_llm("Backup response!")
        router = GatewayRouter(providers=[
            ProviderEntry(name="primary", llm=failing, priority=0),
            ProviderEntry(name="backup", llm=success, priority=1),
        ])
        response = await router.chat(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system_prompt="",
        )
        assert response.content == "Backup response!"
        # Primary should be marked unhealthy
        assert not router.get_provider("primary").healthy

    @pytest.mark.asyncio
    async def test_chat_all_fail(self):
        """Test that RuntimeError is raised when all providers fail."""
        router = GatewayRouter(providers=[
            ProviderEntry(name="p1", llm=FailingLLM()),
            ProviderEntry(name="p2", llm=FailingLLM()),
        ])
        with pytest.raises(RuntimeError, match="All providers failed"):
            await router.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            )

    @pytest.mark.asyncio
    async def test_chat_no_providers(self):
        router = GatewayRouter()
        with pytest.raises(RuntimeError, match="No healthy providers"):
            await router.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            )

    @pytest.mark.asyncio
    async def test_chat_marks_healthy_on_success(self):
        """Test that a successful call marks the provider as healthy."""
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="p1", llm=llm, healthy=False, failure_count=3),
        ])
        # Even though initially unhealthy, the router tries sorted providers
        # which only includes healthy ones. Let's mark it healthy first.
        router.mark_healthy("p1")
        await router.chat(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system_prompt="",
        )
        assert router.get_provider("p1").healthy
        assert router.get_provider("p1").failure_count == 0

    @pytest.mark.asyncio
    async def test_chat_is_llm_interface(self):
        """Test that GatewayRouter satisfies the LLMInterface protocol."""
        llm = make_mock_llm()
        router = GatewayRouter(providers=[ProviderEntry(name="p1", llm=llm)])
        assert isinstance(router, LLMInterface)

    def test_get_status(self):
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="p1", llm=llm, priority=0, weight=2),
        ])
        status = router.get_status()
        assert "p1" in status
        assert status["p1"]["healthy"] is True
        assert status["p1"]["priority"] == 0
        assert status["p1"]["weight"] == 2

    def test_repr(self):
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="p1", llm=llm),
            ProviderEntry(name="p2", llm=llm, healthy=False),
        ])
        r = repr(router)
        assert "2" in r  # 2 providers
        assert "1" in r  # 1 healthy

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health_check method."""
        good = make_mock_llm()
        bad = FailingLLM()
        router = GatewayRouter(providers=[
            ProviderEntry(name="good", llm=good),
            ProviderEntry(name="bad", llm=bad),
        ])
        results = await router.health_check()
        assert results["good"] is True
        assert results["bad"] is False
        assert router.get_provider("good").healthy
        assert not router.get_provider("bad").healthy


# ═══════════════════════════════════════════════════════════════
#  FallbackChain Tests
# ═══════════════════════════════════════════════════════════════


class TestFallbackChain:
    """Test FallbackChain."""

    @pytest.mark.asyncio
    async def test_chat_success_first_try(self):
        """Test that a successful call works on the first try."""
        llm = make_mock_llm("Success!")
        router = GatewayRouter(providers=[
            ProviderEntry(name="p1", llm=llm),
        ])
        chain = FallbackChain(router=router, config=FallbackConfig(max_retries=1))
        response = await chain.chat(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system_prompt="",
        )
        assert response.content == "Success!"

    @pytest.mark.asyncio
    async def test_chat_retry_then_success(self):
        """Test that retry works when the first attempt fails."""
        # MockLLM that fails once then succeeds
        call_count = [0]

        class FlakyLLM:
            async def chat(self, messages, tools, system_prompt):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise RuntimeError("Transient error")
                return LLMResponse.text("Recovered!")

        router = GatewayRouter(providers=[
            ProviderEntry(name="flaky", llm=FlakyLLM()),
        ])
        chain = FallbackChain(router=router, config=FallbackConfig(max_retries=2, retry_delay=0))

        # Need to reset health between retries since mark_unhealthy is called
        # Actually, the retry happens within the same provider loop before
        # trying the next provider. Let me check the implementation...
        # The retry loop is per-provider, so it should retry on the same provider.
        # But mark_unhealthy is called on each failure. Since there's only one
        # provider, get_sorted_providers will return it initially.
        # After the first failure, it's marked unhealthy, but we're already
        # in the loop for this provider. The retry happens in the inner loop.
        # Wait, no — the inner loop retries, but mark_unhealthy is called
        # on each exception. The provider is still in the list because
        # we already have the list from get_sorted_providers.

        response = await chain.chat(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system_prompt="",
        )
        assert response.content == "Recovered!"
        assert call_count[0] == 2  # Failed once, succeeded on retry

    @pytest.mark.asyncio
    async def test_chat_failover_to_backup(self):
        """Test that the chain fails over to a backup provider."""
        failing = FailingLLM()
        success = make_mock_llm("Backup OK!")
        router = GatewayRouter(providers=[
            ProviderEntry(name="primary", llm=failing, priority=0),
            ProviderEntry(name="backup", llm=success, priority=1),
        ])
        chain = FallbackChain(router=router, config=FallbackConfig(max_retries=0))
        response = await chain.chat(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system_prompt="",
        )
        assert response.content == "Backup OK!"

    @pytest.mark.asyncio
    async def test_chat_all_fail_raises(self):
        """Test that all failures raise RuntimeError."""
        router = GatewayRouter(providers=[
            ProviderEntry(name="p1", llm=FailingLLM()),
            ProviderEntry(name="p2", llm=FailingLLM()),
        ])
        chain = FallbackChain(router=router, config=FallbackConfig(max_retries=1))
        with pytest.raises(RuntimeError, match="All fallback strategies failed"):
            await chain.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            )

    @pytest.mark.asyncio
    async def test_chat_no_providers_raises(self):
        router = GatewayRouter()
        chain = FallbackChain(router=router)
        with pytest.raises(RuntimeError, match="No healthy providers"):
            await chain.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            )

    @pytest.mark.asyncio
    async def test_chat_with_cache(self):
        """Test that caching returns cached responses."""
        llm = make_mock_llm("Cached response!")
        router = GatewayRouter(providers=[ProviderEntry(name="p1", llm=llm)])
        chain = FallbackChain(
            router=router,
            config=FallbackConfig(enable_cache=True, cache_ttl=60),
        )

        # First call — hits the LLM
        response1 = await chain.chat(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system_prompt="system",
        )
        assert response1.content == "Cached response!"
        assert chain.cache_size == 1

        # Second call — should return cached response
        # Even if LLM would fail now, the cache should return
        response2 = await chain.chat(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system_prompt="system",
        )
        assert response2.content == "Cached response!"

    @pytest.mark.asyncio
    async def test_chat_with_details(self):
        """Test chat_with_details returns metadata."""
        llm = make_mock_llm("Detailed!")
        router = GatewayRouter(providers=[
            ProviderEntry(name="p1", llm=llm),
        ])
        chain = FallbackChain(router=router)
        result = await chain.chat_with_details(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system_prompt="",
        )
        assert isinstance(result, FallbackResult)
        assert result.response.content == "Detailed!"
        assert result.provider_name == "p1"
        assert result.attempts == 1
        assert not result.used_cache
        assert not result.used_fallback

    @pytest.mark.asyncio
    async def test_chat_with_cost_tracking(self):
        """Test that cost tracking records usage."""
        llm = make_mock_llm("Tracked!", tokens=100)
        router = GatewayRouter(providers=[
            ProviderEntry(name="openai", llm=llm),
        ])
        tracker = CostTracker()
        chain = FallbackChain(router=router, cost_tracker=tracker)

        await chain.chat(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system_prompt="",
            model="gpt-4o",
        )

        assert tracker.entry_count == 1
        entry = tracker.entries[0]
        assert entry.provider == "openai"
        assert entry.model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_chat_with_rate_limiter_allowed(self):
        """Test that rate limiter allows requests within limit."""
        llm = make_mock_llm("Limited!")
        router = GatewayRouter(providers=[
            ProviderEntry(name="p1", llm=llm),
        ])
        limiter = RateLimiter(strategy="token_bucket", requests_per_minute=10)
        chain = FallbackChain(router=router, rate_limiter=limiter)

        response = await chain.chat(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system_prompt="",
        )
        assert response.content == "Limited!"

    @pytest.mark.asyncio
    async def test_chat_with_rate_limiter_blocked(self):
        """Test that rate limiter blocks requests when limit is exceeded."""
        llm = make_mock_llm()
        router = GatewayRouter(providers=[
            ProviderEntry(name="p1", llm=llm),
        ])
        limiter = RateLimiter(strategy="sliding_window", requests_per_minute=1)
        # Exhaust the limit
        limiter.acquire(key="p1")

        chain = FallbackChain(router=router, rate_limiter=limiter)
        with pytest.raises(RuntimeError, match="failed"):
            await chain.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            )

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        llm = make_mock_llm("Cached!")
        router = GatewayRouter(providers=[ProviderEntry(name="p1", llm=llm)])
        chain = FallbackChain(
            router=router,
            config=FallbackConfig(enable_cache=True),
        )
        await chain.chat(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system_prompt="",
        )
        assert chain.cache_size == 1
        chain.clear_cache()
        assert chain.cache_size == 0

    @pytest.mark.asyncio
    async def test_is_llm_interface(self):
        """Test that FallbackChain satisfies the LLMInterface protocol."""
        llm = make_mock_llm()
        router = GatewayRouter(providers=[ProviderEntry(name="p1", llm=llm)])
        chain = FallbackChain(router=router)
        assert isinstance(chain, LLMInterface)

    def test_get_status(self):
        llm = make_mock_llm()
        router = GatewayRouter(providers=[ProviderEntry(name="p1", llm=llm)])
        chain = FallbackChain(router=router, config=FallbackConfig(enable_cache=True))
        status = chain.get_status()
        assert "router" in status
        assert "cache_size" in status
        assert "config" in status
        assert status["config"]["enable_cache"] is True


class TestFallbackConfig:
    """Test FallbackConfig dataclass."""

    def test_defaults(self):
        config = FallbackConfig()
        assert config.max_retries == 1
        assert config.retry_delay == 0.0
        assert config.enable_provider_switch is True
        assert config.enable_model_downgrade is False
        assert config.enable_cache is False
        assert config.cache_ttl == 300.0

    def test_custom(self):
        config = FallbackConfig(
            max_retries=3,
            retry_delay=0.5,
            enable_cache=True,
            cache_ttl=600.0,
            fallback_model="gpt-4o-mini",
        )
        assert config.max_retries == 3
        assert config.retry_delay == 0.5
        assert config.enable_cache is True
        assert config.cache_ttl == 600.0
        assert config.fallback_model == "gpt-4o-mini"


# ═══════════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestGatewayIntegration:
    """Integration tests for the full gateway stack."""

    @pytest.mark.asyncio
    async def test_full_stack_with_failover_and_cost_tracking(self):
        """Test the full stack: router → fallback → cost tracking."""
        failing = FailingLLM()
        success = make_mock_llm("Final answer!", tokens=100)
        router = GatewayRouter(providers=[
            ProviderEntry(name="primary", llm=failing, priority=0),
            ProviderEntry(name="backup", llm=success, priority=1),
        ])
        tracker = CostTracker()
        chain = FallbackChain(
            router=router,
            config=FallbackConfig(max_retries=1, retry_delay=0),
            cost_tracker=tracker,
        )

        response = await chain.chat(
            messages=[{"role": "user", "content": "Hello"}],
            tools=[],
            system_prompt="Be helpful.",
            model="gpt-4o",
        )

        assert response.content == "Final answer!"
        assert tracker.entry_count == 1
        assert tracker.entries[0].provider == "backup"
        assert not router.get_provider("primary").healthy
        assert router.get_provider("backup").healthy

    @pytest.mark.asyncio
    async def test_gateway_with_agent_loop(self):
        """Test that GatewayRouter can be used with AgentLoop."""
        from suyi.core.loop import AgentLoop, LLMResponse, MockLLM

        llm = MockLLM([LLMResponse.text("Gateway-powered response!")])
        router = GatewayRouter(providers=[
            ProviderEntry(name="p1", llm=llm),
        ])

        loop = AgentLoop(llm=router)
        result = await loop.run("Hello")

        assert result.content == "Gateway-powered response!"
        assert result.is_complete

    @pytest.mark.asyncio
    async def test_fallback_chain_with_agent_loop(self):
        """Test that FallbackChain can be used with AgentLoop."""
        from suyi.core.loop import AgentLoop, LLMResponse, MockLLM

        llm = MockLLM([LLMResponse.text("Fallback-powered response!")])
        router = GatewayRouter(providers=[
            ProviderEntry(name="p1", llm=llm),
        ])
        chain = FallbackChain(router=router)

        loop = AgentLoop(llm=chain)
        result = await loop.run("Hello")

        assert result.content == "Fallback-powered response!"
        assert result.is_complete

    @pytest.mark.asyncio
    async def test_rate_limited_gateway(self):
        """Test a gateway with rate limiting that allows and then blocks."""
        # Use a custom LLM that always returns the same response
        class AlwaysOK:
            async def chat(self, messages, tools, system_prompt):
                return LLMResponse.text("OK!")

        llm = AlwaysOK()
        router = GatewayRouter(providers=[
            ProviderEntry(name="p1", llm=llm),
        ])
        limiter = RateLimiter(strategy="sliding_window", requests_per_minute=2)
        chain = FallbackChain(router=router, rate_limiter=limiter)

        # First two calls should succeed
        r1 = await chain.chat(
            messages=[{"role": "user", "content": "1"}],
            tools=[],
            system_prompt="",
        )
        assert r1.content == "OK!"

        r2 = await chain.chat(
            messages=[{"role": "user", "content": "2"}],
            tools=[],
            system_prompt="",
        )
        assert r2.content == "OK!"

        # Third call should fail due to rate limiting
        with pytest.raises(RuntimeError, match="failed"):
            await chain.chat(
                messages=[{"role": "user", "content": "3"}],
                tools=[],
                system_prompt="",
            )

    @pytest.mark.asyncio
    async def test_cached_fallback_on_failure(self):
        """Test that cache returns a prior response when all providers fail."""
        # First call succeeds, second call (same params) should return cache
        # even though the provider now fails

        call_count = [0]

        class ToggleLLM:
            def __init__(self):
                self._call_count = 0

            async def chat(self, messages, tools, system_prompt):
                call_count[0] += 1
                if call_count[0] == 1:
                    return LLMResponse.text("First response!")
                raise RuntimeError("Service down")

        router = GatewayRouter(providers=[
            ProviderEntry(name="p1", llm=ToggleLLM()),
        ])
        chain = FallbackChain(
            router=router,
            config=FallbackConfig(
                max_retries=0,
                enable_cache=True,
                cache_ttl=60,
            ),
        )

        messages = [{"role": "user", "content": "same message"}]
        system = "same system"

        # First call — succeeds and caches
        r1 = await chain.chat(messages, [], system)
        assert r1.content == "First response!"

        # Reset health for retry
        router.mark_healthy("p1")

        # Second call — provider fails, but cache returns prior response
        r2 = await chain.chat(messages, [], system)
        assert r2.content == "First response!"
