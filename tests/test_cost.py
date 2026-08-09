"""
Tests for Phase 12 — Cost Tracker Module.

Tests cover:
    - CostConfig: creation, serialization
    - CostRecord: creation, serialization
    - CostTrackerV2: calculate_cost, record, total_cost, total_tokens
    - Budget management: check_budget, budget_remaining, budget_percentage
    - Alerts: warning, critical, exhausted, session-level alerts
    - Reports: by provider, model, session, user, time
    - BudgetTracker integration: token sync, status
    - Persistence: save/load
    - Pricing: get_pricing, set_pricing, custom pricing

All tests use no external API calls.
"""

import json
import os
import tempfile
import time
import pytest

from suyi.cost import (
    CostConfig,
    CostRecord,
    CostAlert,
    CostReport,
    AlertLevel,
    DEFAULT_MODEL_PRICING,
    CostTrackerV2,
)
from suyi.core.budget import BudgetTracker, BudgetConfig


# ═══════════════════════════════════════════════════════════════
#  CostConfig
# ═══════════════════════════════════════════════════════════════


class TestCostConfig:
    """成本配置测试."""

    def test_default_config(self):
        config = CostConfig()
        assert config.budget is None
        assert config.warning_threshold == 0.8
        assert config.critical_threshold == 0.95
        assert config.exhausted_threshold == 1.0

    def test_custom_config(self):
        config = CostConfig(budget=10.0, warning_threshold=0.7, session_budget=2.0)
        assert config.budget == 10.0
        assert config.session_budget == 2.0

    def test_serialization(self):
        config = CostConfig(budget=5.0, storage_path="/tmp/test.json")
        d = config.to_dict()
        assert d["budget"] == 5.0
        assert d["storage_path"] == "/tmp/test.json"


# ═══════════════════════════════════════════════════════════════
#  CostRecord
# ═══════════════════════════════════════════════════════════════


class TestCostRecord:
    """成本记录测试."""

    def test_creation(self):
        record = CostRecord(
            timestamp=time.time(),
            provider="openai",
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.003,
            session_id="s1",
        )
        assert record.provider == "openai"
        assert record.total_tokens == 150

    def test_serialization(self):
        record = CostRecord(
            timestamp=1000.0,
            provider="openai",
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.003,
        )
        d = record.to_dict()
        assert d["provider"] == "openai"
        restored = CostRecord.from_dict(d)
        assert restored.prompt_tokens == 100


# ═══════════════════════════════════════════════════════════════


class TestCostTrackerBasics:
    """成本追踪器基础测试."""

    def test_initial_state(self):
        tracker = CostTrackerV2()
        assert tracker.record_count == 0
        assert tracker.total_cost() == 0.0

    def test_calculate_cost(self):
        tracker = CostTrackerV2()
        # gpt-4o: prompt $0.0025/1K, completion $0.01/1K
        cost = tracker.calculate_cost("openai", "gpt-4o", 1000, 500)
        expected = (1000 / 1000) * 0.0025 + (500 / 1000) * 0.01
        assert cost == pytest.approx(expected, rel=1e-4)

    def test_calculate_cost_unknown_model(self):
        tracker = CostTrackerV2()
        cost = tracker.calculate_cost("unknown", "unknown-model", 1000, 500)
        assert cost == 0.0

    def test_record(self):
        tracker = CostTrackerV2()
        record = tracker.record(
            provider="openai",
            model="gpt-4o",
            prompt_tokens=1000,
            completion_tokens=500,
            session_id="s1",
        )
        assert record.provider == "openai"
        assert record.total_tokens == 1500
        assert record.session_id == "s1"
        assert tracker.record_count == 1

    def test_total_cost(self):
        tracker = CostTrackerV2()
        tracker.record("openai", "gpt-4o", 1000, 500)
        tracker.record("openai", "gpt-4o", 2000, 1000)
        # 两次记录的总费用
        cost1 = tracker.calculate_cost("openai", "gpt-4o", 1000, 500)
        cost2 = tracker.calculate_cost("openai", "gpt-4o", 2000, 1000)
        assert tracker.total_cost() == pytest.approx(cost1 + cost2, rel=1e-4)

    def test_total_tokens(self):
        tracker = CostTrackerV2()
        tracker.record("openai", "gpt-4o", 1000, 500)
        tracker.record("openai", "gpt-4o", 2000, 1000)
        tokens = tracker.total_tokens()
        assert tokens["prompt_tokens"] == 3000
        assert tokens["completion_tokens"] == 1500
        assert tokens["total_tokens"] == 4500

    def test_multiple_providers(self):
        tracker = CostTrackerV2()
        tracker.record("openai", "gpt-4o", 1000, 500)
        tracker.record("anthropic", "claude-3-opus-20240229", 1000, 500)
        assert tracker.record_count == 2

    def test_record_with_metadata(self):
        tracker = CostTrackerV2()
        record = tracker.record(
            provider="openai",
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
            metadata={"request_id": "req_123"},
        )
        assert record.metadata["request_id"] == "req_123"


# ═══════════════════════════════════════════════════════════════
#  Session Tracking
# ═══════════════════════════════════════════════════════════════


class TestSessionTracking:
    """会话维度追踪测试."""

    def test_session_cost(self):
        tracker = CostTrackerV2()
        tracker.record("openai", "gpt-4o", 1000, 500, session_id="s1")
        tracker.record("openai", "gpt-4o", 2000, 1000, session_id="s2")
        tracker.record("openai", "gpt-4o", 500, 250, session_id="s1")

        cost_s1 = tracker.session_cost("s1")
        cost_s2 = tracker.session_cost("s2")
        # s2 has more tokens (2000+1000) than s1 (1000+500 + 500+250)
        assert cost_s2 > cost_s1

    def test_session_tokens(self):
        tracker = CostTrackerV2()
        tracker.record("openai", "gpt-4o", 1000, 500, session_id="s1")
        tracker.record("openai", "gpt-4o", 500, 250, session_id="s1")

        tokens = tracker.session_tokens("s1")
        assert tokens["prompt_tokens"] == 1500
        assert tokens["total_tokens"] == 2250

    def test_sessions_list(self):
        tracker = CostTrackerV2()
        tracker.record("openai", "gpt-4o", 100, 50, session_id="s1")
        tracker.record("openai", "gpt-4o", 100, 50, session_id="s2")
        tracker.record("openai", "gpt-4o", 100, 50, session_id="s1")
        assert set(tracker.sessions) == {"s1", "s2"}

    def test_session_budget_remaining(self):
        config = CostConfig(session_budget=1.0)
        tracker = CostTrackerV2(config)
        tracker.record("openai", "gpt-4o", 1000, 500, session_id="s1")
        remaining = tracker.session_budget_remaining("s1")
        assert remaining is not None
        assert remaining < 1.0


# ═══════════════════════════════════════════════════════════════
#  Budget Management
# ═══════════════════════════════════════════════════════════════


class TestBudgetManagement:
    """预算管理测试."""

    def test_check_budget_no_limit(self):
        tracker = CostTrackerV2()
        assert tracker.check_budget() is True

    def test_check_budget_within(self):
        config = CostConfig(budget=10.0)
        tracker = CostTrackerV2(config)
        tracker.record("openai", "gpt-4o", 1000, 500)
        assert tracker.check_budget() is True

    def test_check_budget_exceeded(self):
        config = CostConfig(budget=0.001)  # 极小预算
        tracker = CostTrackerV2(config)
        tracker.record("openai", "gpt-4o", 1000, 500)  # 费用 ~$0.0075
        assert tracker.check_budget() is False

    def test_budget_remaining(self):
        config = CostConfig(budget=10.0)
        tracker = CostTrackerV2(config)
        tracker.record("openai", "gpt-4o", 1000, 500)
        remaining = tracker.budget_remaining()
        assert remaining is not None
        assert 0 < remaining < 10.0

    def test_budget_remaining_no_budget(self):
        tracker = CostTrackerV2()
        assert tracker.budget_remaining() is None

    def test_budget_percentage(self):
        config = CostConfig(budget=10.0)
        tracker = CostTrackerV2(config)
        tracker.record("openai", "gpt-4o", 1000, 500)
        pct = tracker.budget_percentage()
        assert pct is not None
        assert 0 < pct < 100


# ═══════════════════════════════════════════════════════════════
#  Alerts
# ═══════════════════════════════════════════════════════════════


class TestAlerts:
    """告警测试."""

    def test_no_alerts_without_budget(self):
        tracker = CostTrackerV2()
        tracker.record("openai", "gpt-4o", 1000, 500)
        assert len(tracker.alerts) == 0

    def test_warning_alert(self):
        # gpt-4o: prompt $0.0025/1K, completion $0.01/1K
        # 1000 prompt + 500 completion = $0.0025 + $0.005 = $0.0075
        # 预算 $0.0075 * (1/0.8) = $0.009375 → 使用 80% 触发 warning
        config = CostConfig(
            budget=0.009375,
            warning_threshold=0.8,
            critical_threshold=0.95,
        )
        tracker = CostTrackerV2(config)
        tracker.record("openai", "gpt-4o", 1000, 500)
        warning_alerts = [a for a in tracker.alerts if a.level == AlertLevel.WARNING]
        assert len(warning_alerts) == 1

    def test_critical_alert(self):
        config = CostConfig(
            budget=0.0075,  # 恰好等于一次调用费用
            warning_threshold=0.5,
            critical_threshold=0.9,
            exhausted_threshold=1.0,
        )
        tracker = CostTrackerV2(config)
        tracker.record("openai", "gpt-4o", 1000, 500)
        # 100% 使用 → 触发 exhausted（也自动触发 warning 和 critical）
        levels = {a.level for a in tracker.alerts}
        assert AlertLevel.EXHAUSTED in levels

    def test_progressive_alerts(self):
        """验证告警逐步触发."""
        config = CostConfig(
            budget=0.03,  # 约 4 次调用
            warning_threshold=0.5,
            critical_threshold=0.8,
            exhausted_threshold=1.0,
        )
        tracker = CostTrackerV2(config)
        # 每次费用 ~$0.0075
        tracker.record("openai", "gpt-4o", 1000, 500)  # ~25%
        assert len(tracker.alerts) == 0

        tracker.record("openai", "gpt-4o", 1000, 500)  # ~50%
        assert any(a.level == AlertLevel.WARNING for a in tracker.alerts)

        tracker.record("openai", "gpt-4o", 1000, 500)  # ~75%
        tracker.record("openai", "gpt-4o", 1000, 500)  # ~100%
        levels = {a.level for a in tracker.alerts}
        assert AlertLevel.CRITICAL in levels
        assert AlertLevel.EXHAUSTED in levels

    def test_alert_not_duplicated(self):
        """同一级别告警不重复."""
        config = CostConfig(budget=0.01, warning_threshold=0.1)
        tracker = CostTrackerV2(config)
        tracker.record("openai", "gpt-4o", 1000, 500)
        tracker.record("openai", "gpt-4o", 1000, 500)
        warnings = [a for a in tracker.alerts if a.level == AlertLevel.WARNING]
        assert len(warnings) == 1

    def test_clear_alerts(self):
        config = CostConfig(budget=0.01, warning_threshold=0.1)
        tracker = CostTrackerV2(config)
        tracker.record("openai", "gpt-4o", 1000, 500)
        assert len(tracker.alerts) > 0
        tracker.clear_alerts()
        assert len(tracker.alerts) == 0

    def test_session_alert(self):
        config = CostConfig(session_budget=0.005)
        tracker = CostTrackerV2(config)
        tracker.record("openai", "gpt-4o", 1000, 500, session_id="s1")
        session_alerts = [a for a in tracker.alerts if a.session_id == "s1"]
        assert len(session_alerts) > 0

    def test_alert_properties(self):
        config = CostConfig(budget=0.01, warning_threshold=0.1)
        tracker = CostTrackerV2(config)
        tracker.record("openai", "gpt-4o", 1000, 500)
        alert = tracker.alerts[0]
        assert alert.level == AlertLevel.WARNING
        assert alert.spent > 0
        assert alert.budget == 0.01
        assert alert.percentage > 0
        assert alert.timestamp > 0

    def test_alert_serialization(self):
        alert = CostAlert(
            level=AlertLevel.WARNING,
            message="test",
            spent=5.0,
            budget=10.0,
            percentage=50.0,
        )
        d = alert.to_dict()
        assert d["level"] == "warning"
        assert d["spent"] == 5.0


# ═══════════════════════════════════════════════════════════════
#  Reports
# ═══════════════════════════════════════════════════════════════


class TestReports:
    """报告测试."""

    def test_report_by_provider(self):
        tracker = CostTrackerV2()
        tracker.record("openai", "gpt-4o", 1000, 500)
        tracker.record("anthropic", "claude-3-opus-20240229", 1000, 500)
        report = tracker.get_report(by="provider")
        assert "openai" in report.entries
        assert "anthropic" in report.entries
        assert report.dimension == "provider"

    def test_report_by_model(self):
        tracker = CostTrackerV2()
        tracker.record("openai", "gpt-4o", 1000, 500)
        tracker.record("openai", "gpt-4o-mini", 1000, 500)
        report = tracker.get_report(by="model")
        assert "openai/gpt-4o" in report.entries
        assert "openai/gpt-4o-mini" in report.entries

    def test_report_by_session(self):
        tracker = CostTrackerV2()
        tracker.record("openai", "gpt-4o", 1000, 500, session_id="s1")
        tracker.record("openai", "gpt-4o", 1000, 500, session_id="s2")
        report = tracker.get_report(by="session")
        assert "s1" in report.entries
        assert "s2" in report.entries

    def test_report_by_user(self):
        tracker = CostTrackerV2()
        tracker.record("openai", "gpt-4o", 1000, 500, user="alice")
        tracker.record("openai", "gpt-4o", 1000, 500, user="bob")
        report = tracker.get_report(by="user")
        assert "alice" in report.entries
        assert "bob" in report.entries

    def test_report_by_time(self):
        tracker = CostTrackerV2()
        tracker.record("openai", "gpt-4o", 1000, 500)
        report = tracker.get_report(by="time")
        assert len(report.entries) >= 1

    def test_report_invalid_dimension(self):
        tracker = CostTrackerV2()
        with pytest.raises(ValueError):
            tracker.get_report(by="invalid")

    def test_report_totals(self):
        tracker = CostTrackerV2()
        tracker.record("openai", "gpt-4o", 1000, 500)
        tracker.record("openai", "gpt-4o", 2000, 1000)
        report = tracker.get_report(by="provider")
        assert report.total_requests == 2
        assert report.total_tokens == 4500


# ═══════════════════════════════════════════════════════════════
#  BudgetTracker Integration
# ═══════════════════════════════════════════════════════════════


class TestBudgetTrackerIntegration:
    """BudgetTracker 集成测试."""

    def test_token_sync(self):
        budget_tracker = BudgetTracker(BudgetConfig(max_tokens=10000))
        budget_tracker.start()

        tracker = CostTrackerV2(budget_tracker=budget_tracker)
        tracker.record("openai", "gpt-4o", 1000, 500)
        tracker.record("openai", "gpt-4o", 2000, 1000)

        # BudgetTracker 应该记录了 4500 tokens
        assert budget_tracker.tokens_used == 4500

    def test_get_budget_status(self):
        budget_tracker = BudgetTracker(BudgetConfig(max_tokens=5000))
        budget_tracker.start()

        tracker = CostTrackerV2(budget_tracker=budget_tracker)
        tracker.record("openai", "gpt-4o", 1000, 500)

        status = tracker.get_budget_status()
        assert status is not None
        assert status["tokens_used"] == 1500
        assert status["tokens_max"] == 5000

    def test_no_budget_tracker(self):
        tracker = CostTrackerV2()
        assert tracker.get_budget_status() is None


# ═══════════════════════════════════════════════════════════════
#  Pricing
# ═══════════════════════════════════════════════════════════════


class TestPricing:
    """定价表测试."""

    def test_get_pricing(self):
        tracker = CostTrackerV2()
        pricing = tracker.get_pricing("openai", "gpt-4o")
        assert pricing is not None
        assert "prompt" in pricing
        assert "completion" in pricing

    def test_get_pricing_unknown(self):
        tracker = CostTrackerV2()
        assert tracker.get_pricing("unknown", "unknown") is None

    def test_set_pricing(self):
        tracker = CostTrackerV2()
        tracker.set_pricing("custom", "my-model", 0.001, 0.002)
        pricing = tracker.get_pricing("custom", "my-model")
        assert pricing["prompt"] == 0.001
        assert pricing["completion"] == 0.002

    def test_custom_pricing_config(self):
        custom = {"custom": {"model-x": {"prompt": 0.001, "completion": 0.002}}}
        config = CostConfig(pricing=custom)
        tracker = CostTrackerV2(config)
        pricing = tracker.get_pricing("custom", "model-x")
        assert pricing["prompt"] == 0.001

    def test_default_pricing_table(self):
        assert "openai" in DEFAULT_MODEL_PRICING
        assert "anthropic" in DEFAULT_MODEL_PRICING
        assert "deepseek" in DEFAULT_MODEL_PRICING


# ═══════════════════════════════════════════════════════════════
#  Persistence
# ═══════════════════════════════════════════════════════════════


class TestPersistence:
    """持久化测试."""

    def test_save_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cost.json")
            config = CostConfig(budget=10.0, storage_path=path)
            tracker = CostTrackerV2(config)
            tracker.record("openai", "gpt-4o", 1000, 500, session_id="s1")
            original_cost = tracker.total_cost()

            # 加载
            config2 = CostConfig(budget=10.0, storage_path=path)
            tracker2 = CostTrackerV2(config2)
            assert tracker2.record_count == 1
            assert tracker2.total_cost() == pytest.approx(original_cost)

    def test_load_nonexistent(self):
        config = CostConfig(storage_path="/nonexistent/cost.json")
        tracker = CostTrackerV2(config)
        assert tracker.record_count == 0

    def test_clear(self):
        tracker = CostTrackerV2()
        tracker.record("openai", "gpt-4o", 100, 50)
        tracker.clear()
        assert tracker.record_count == 0
        assert len(tracker.alerts) == 0

    def test_repr(self):
        tracker = CostTrackerV2()
        r = repr(tracker)
        assert "CostTrackerV2" in r


# ═══════════════════════════════════════════════════════════════
#  Complex Scenario
# ═══════════════════════════════════════════════════════════════


class TestComplexScenario:
    """复杂场景测试 — 多会话多模型成本追踪."""

    def test_multi_session_multi_model(self):
        config = CostConfig(budget=1.0, session_budget=0.5)
        tracker = CostTrackerV2(config)

        # 会话 1: 使用 gpt-4o
        tracker.record("openai", "gpt-4o", 2000, 1000, session_id="s1")
        tracker.record("openai", "gpt-4o", 1000, 500, session_id="s1")

        # 会话 2: 使用 gpt-4o-mini (便宜)
        tracker.record("openai", "gpt-4o-mini", 2000, 1000, session_id="s2")

        # 会话 3: 使用 claude
        tracker.record("anthropic", "claude-3-haiku-20240307", 1000, 500, session_id="s3")

        # 按会话报告
        session_report = tracker.get_report(by="session")
        assert len(session_report.entries) == 3

        # 按模型报告
        model_report = tracker.get_report(by="model")
        assert "openai/gpt-4o" in model_report.entries
        assert "openai/gpt-4o-mini" in model_report.entries

        # 总费用
        assert tracker.total_cost() > 0

        # 各会话费用不同
        s1_cost = tracker.session_cost("s1")
        s2_cost = tracker.session_cost("s2")
        assert s1_cost > s2_cost  # gpt-4o 比 mini 贵
