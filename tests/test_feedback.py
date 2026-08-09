"""
Tests for Phase 12 — Feedback Loop Module.

Tests cover:
    - FeedbackEntry: creation, properties, serialization
    - FeedbackType / ImplicitSignalType: enum values
    - FeedbackSignalV2: computation, weights
    - FeedbackLoop: explicit collection, implicit collection, signal computation
    - Implicit signal recording: retry, edit, abandon, copy, regenerate
    - Trend analysis: window, direction
    - Evolution engine integration: feed_to_evolution
    - Statistics: get_stats
    - Persistence: save/load

All tests use no external API calls.
"""

import json
import os
import tempfile
import time
import pytest
from unittest.mock import MagicMock, patch

from suyi.feedback import (
    FeedbackType,
    ImplicitSignalType,
    FeedbackEntry,
    FeedbackSignalV2,
    FeedbackLoop,
)


# ═══════════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════════


class TestEnums:
    """枚举测试."""

    def test_feedback_type_values(self):
        assert FeedbackType.THUMBS_UP.value == "thumbs_up"
        assert FeedbackType.THUMBS_DOWN.value == "thumbs_down"
        assert FeedbackType.STAR_1.value == "star_1"
        assert FeedbackType.STAR_5.value == "star_5"

    def test_implicit_signal_type_values(self):
        assert ImplicitSignalType.RETRY.value == "retry"
        assert ImplicitSignalType.EDIT.value == "edit"
        assert ImplicitSignalType.ABANDON.value == "abandon"
        assert ImplicitSignalType.COPY.value == "copy"
        assert ImplicitSignalType.REGENERATE.value == "regenerate"


# ═══════════════════════════════════════════════════════════════
#  FeedbackEntry
# ═══════════════════════════════════════════════════════════════


class TestFeedbackEntry:
    """反馈条目测试."""

    def test_creation(self):
        entry = FeedbackEntry(interaction_id="int_001")
        assert entry.interaction_id == "int_001"
        assert entry.id.startswith("fb_")
        assert entry.timestamp > 0

    def test_has_explicit_false(self):
        entry = FeedbackEntry(interaction_id="int_001")
        assert entry.has_explicit is False

    def test_has_explicit_true(self):
        entry = FeedbackEntry(
            interaction_id="int_001",
            explicit_type=FeedbackType.THUMBS_UP.value,
        )
        assert entry.has_explicit is True

    def test_has_explicit_rating(self):
        entry = FeedbackEntry(interaction_id="int_001", explicit_rating=4)
        assert entry.has_explicit is True

    def test_has_implicit_false(self):
        entry = FeedbackEntry(interaction_id="int_001")
        assert entry.has_implicit is False

    def test_has_implicit_true(self):
        entry = FeedbackEntry(interaction_id="int_001", implicit_retries=1)
        assert entry.has_implicit is True

    def test_serialization(self):
        entry = FeedbackEntry(
            interaction_id="int_001",
            explicit_type="thumbs_up",
            implicit_retries=2,
            implicit_edited=True,
        )
        d = entry.to_dict()
        assert d["interaction_id"] == "int_001"
        assert d["explicit_type"] == "thumbs_up"
        restored = FeedbackEntry.from_dict(d)
        assert restored.interaction_id == "int_001"
        assert restored.implicit_retries == 2

    def test_from_dict_filters_unknown(self):
        d = {"interaction_id": "int_001", "unknown_field": "x"}
        entry = FeedbackEntry.from_dict(d)
        assert entry.interaction_id == "int_001"


# ═══════════════════════════════════════════════════════════════
#  FeedbackSignalV2
# ═══════════════════════════════════════════════════════════════


class TestFeedbackSignalV2:
    """反馈信号测试."""

    def test_compute_combined_both(self):
        signal = FeedbackSignalV2(
            interaction_id="int_001",
            explicit_signal=1.0,
            implicit_signal=0.5,
        )
        combined = signal.compute_combined()
        # 1.0 * 0.6 + 0.5 * 0.4 = 0.8
        assert combined == pytest.approx(0.8, abs=0.01)

    def test_compute_combined_explicit_only(self):
        signal = FeedbackSignalV2(
            interaction_id="int_001",
            explicit_signal=1.0,
            implicit_signal=0.0,
        )
        combined = signal.compute_combined()
        assert combined == 1.0

    def test_compute_combined_implicit_only(self):
        signal = FeedbackSignalV2(
            interaction_id="int_001",
            explicit_signal=0.0,
            implicit_signal=-0.5,
        )
        combined = signal.compute_combined()
        assert combined == pytest.approx(-0.5, abs=0.01)

    def test_compute_combined_both_zero(self):
        signal = FeedbackSignalV2(interaction_id="int_001")
        combined = signal.compute_combined()
        assert combined == 0.0

    def test_repr(self):
        signal = FeedbackSignalV2(combined=0.5, explicit_signal=0.8, implicit_signal=0.2)
        r = repr(signal)
        assert "FeedbackSignalV2" in r


# ═══════════════════════════════════════════════════════════════


class TestExplicitFeedback:
    """显式反馈收集测试."""

    def test_collect_thumbs_up(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        entry = loop.collect_explicit(
            interaction_id="int_001",
            feedback_type=FeedbackType.THUMBS_UP,
            comment="很好",
        )
        assert entry.explicit_type == "thumbs_up"
        assert entry.explicit_comment == "很好"

    def test_collect_thumbs_down(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        entry = loop.collect_explicit(
            interaction_id="int_001",
            feedback_type=FeedbackType.THUMBS_DOWN,
        )
        assert entry.explicit_type == "thumbs_down"

    def test_collect_star_rating(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        entry = loop.collect_explicit(
            interaction_id="int_001",
            rating=5,
        )
        assert entry.explicit_rating == 5
        # 5 星自动推导为 thumbs_up
        assert entry.explicit_type == "thumbs_up"

    def test_collect_star_rating_low(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        entry = loop.collect_explicit(
            interaction_id="int_001",
            rating=1,
        )
        assert entry.explicit_type == "thumbs_down"

    def test_collect_star_rating_mid(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        entry = loop.collect_explicit(
            interaction_id="int_001",
            rating=3,
        )
        assert entry.explicit_type == "neutral"

    def test_collect_rating_clamped(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        entry = loop.collect_explicit(
            interaction_id="int_001",
            rating=10,  # 超出范围
        )
        assert entry.explicit_rating == 5  # 被限制到 5

    def test_collect_explicit_signal_positive(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit(
            interaction_id="int_001",
            feedback_type=FeedbackType.THUMBS_UP,
        )
        signal = loop.get_signal("int_001")
        assert signal.explicit_signal == 1.0
        assert signal.combined > 0

    def test_collect_explicit_signal_negative(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit(
            interaction_id="int_001",
            feedback_type=FeedbackType.THUMBS_DOWN,
        )
        signal = loop.get_signal("int_001")
        assert signal.explicit_signal == -1.0
        assert signal.combined < 0

    def test_collect_star_signal(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit(
            interaction_id="int_001",
            feedback_type=FeedbackType.STAR_4,
        )
        signal = loop.get_signal("int_001")
        assert signal.explicit_signal == 0.5

    def test_collect_rating_signal(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit(
            interaction_id="int_001",
            rating=2,
        )
        signal = loop.get_signal("int_001")
        # rating=2 auto-derives to thumbs_down, which maps to -1.0
        assert signal.explicit_signal == -1.0

    def test_update_existing_entry(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit(
            interaction_id="int_001",
            feedback_type=FeedbackType.THUMBS_UP,
        )
        loop.collect_explicit(
            interaction_id="int_001",
            feedback_type=FeedbackType.THUMBS_DOWN,
            comment="不好",
        )
        entry = loop.get_entry("int_001")
        assert entry.explicit_type == "thumbs_down"
        assert entry.explicit_comment == "不好"

    def test_session_user_tracking(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        entry = loop.collect_explicit(
            interaction_id="int_001",
            feedback_type=FeedbackType.THUMBS_UP,
            session_id="s1",
            user_id="alice",
        )
        assert entry.session_id == "s1"
        assert entry.user_id == "alice"


# ═══════════════════════════════════════════════════════════════
#  Implicit Feedback
# ═══════════════════════════════════════════════════════════════


class TestImplicitFeedback:
    """隐式反馈收集测试."""

    def test_collect_implicit(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        entry = loop.collect_implicit(
            interaction_id="int_001",
            retries=1,
            edited=True,
            abandoned=False,
            dwell_time=10.0,
        )
        assert entry.implicit_retries == 1
        assert entry.implicit_edited is True
        assert entry.implicit_abandoned is False
        assert entry.implicit_dwell_time == 10.0

    def test_record_retry_signal(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        entry = loop.record_implicit_signal(
            "int_001", ImplicitSignalType.RETRY
        )
        assert entry.implicit_retries == 1
        entry = loop.record_implicit_signal(
            "int_001", ImplicitSignalType.RETRY
        )
        assert entry.implicit_retries == 2

    def test_record_edit_signal(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        entry = loop.record_implicit_signal(
            "int_001", ImplicitSignalType.EDIT
        )
        assert entry.implicit_edited is True

    def test_record_abandon_signal(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        entry = loop.record_implicit_signal(
            "int_001", ImplicitSignalType.ABANDON
        )
        assert entry.implicit_abandoned is True

    def test_record_copy_signal(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        entry = loop.record_implicit_signal(
            "int_001", ImplicitSignalType.COPY
        )
        assert entry.implicit_copied is True

    def test_record_regenerate_signal(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        entry = loop.record_implicit_signal(
            "int_001", ImplicitSignalType.REGENERATE
        )
        assert entry.implicit_regenerated is True

    def test_implicit_signal_abandon(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_implicit(
            interaction_id="int_001",
            abandoned=True,
        )
        signal = loop.get_signal("int_001")
        # 放弃是强烈负面信号
        assert signal.implicit_signal < 0
        assert signal.combined < 0

    def test_implicit_signal_copy_positive(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_implicit(
            interaction_id="int_001",
            copied=True,
            dwell_time=15.0,  # 适中停留
        )
        signal = loop.get_signal("int_001")
        assert signal.implicit_signal > 0

    def test_implicit_signal_retry_negative(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_implicit(
            interaction_id="int_001",
            retries=3,
        )
        signal = loop.get_signal("int_001")
        assert signal.implicit_signal < 0

    def test_implicit_signal_no_signals(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_implicit(
            interaction_id="int_001",
            retries=0,
            edited=False,
            abandoned=False,
            dwell_time=0,
        )
        signal = loop.get_signal("int_001")
        assert signal.implicit_signal == 0.0

    def test_implicit_signal_regenerate(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_implicit(
            interaction_id="int_001",
            regenerated=True,
        )
        signal = loop.get_signal("int_001")
        assert signal.implicit_signal < 0

    def test_implicit_signal_edited(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_implicit(
            interaction_id="int_001",
            edited=True,
        )
        signal = loop.get_signal("int_001")
        assert signal.implicit_signal < 0

    def test_dwell_signal_short(self):
        """过短停留 → 负面."""
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_implicit(interaction_id="int_001", dwell_time=0.5)
        signal = loop.get_signal("int_001")
        assert signal.components["dwell"] < 0

    def test_dwell_signal_optimal(self):
        """适中停留 → 正面."""
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_implicit(interaction_id="int_001", dwell_time=15.0)
        signal = loop.get_signal("int_001")
        assert signal.components["dwell"] > 0


# ═══════════════════════════════════════════════════════════════
#  Combined Signals
# ═══════════════════════════════════════════════════════════════


class TestCombinedSignals:
    """综合信号测试."""

    def test_explicit_and_implicit_positive(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)
        loop.collect_implicit("int_001", copied=True, dwell_time=15.0)
        signal = loop.get_signal("int_001")
        assert signal.combined > 0.5
        assert signal.weight == 1.0  # 有显式反馈

    def test_explicit_positive_implicit_negative(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)
        loop.collect_implicit("int_001", abandoned=True)
        signal = loop.get_signal("int_001")
        # 显式正面，隐式负面 → 综合应该在中间
        assert signal.combined > -1.0
        assert signal.combined < 1.0

    def test_implicit_only_lower_weight(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_implicit("int_001", retries=2)
        signal = loop.get_signal("int_001")
        assert signal.weight == 0.5  # 纯隐式反馈权重降低

    def test_get_all_signals(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)
        loop.collect_explicit("int_002", feedback_type=FeedbackType.THUMBS_DOWN)
        signals = loop.get_all_signals()
        assert len(signals) == 2

    def test_get_average_signal(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)
        loop.collect_explicit("int_002", feedback_type=FeedbackType.THUMBS_DOWN)
        avg = loop.get_average_signal()
        assert avg == 0.0  # (1.0 + -1.0) / 2

    def test_get_signal_nonexistent(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        assert loop.get_signal("nonexistent") is None

    def test_get_entry_nonexistent(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        assert loop.get_entry("nonexistent") is None

    def test_signal_components(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_implicit(
            "int_001",
            retries=1,
            edited=True,
            dwell_time=10.0,
        )
        signal = loop.get_signal("int_001")
        assert "explicit" in signal.components
        assert "implicit" in signal.components
        assert "retry" in signal.components
        assert "edit" in signal.components
        assert "dwell" in signal.components
        assert "abandon" in signal.components
        assert "copy" in signal.components
        assert "regenerate" in signal.components


# ═══════════════════════════════════════════════════════════════
#  Trend Analysis
# ═══════════════════════════════════════════════════════════════


class TestTrendAnalysis:
    """趋势分析测试."""

    def test_empty_trend(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        trend = loop.get_trend(window_seconds=3600)
        assert trend["count"] == 0
        assert trend["trend_direction"] == "stable"

    def test_positive_trend(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        # 前半段负面，后半段正面 → improving
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_DOWN)
        loop.collect_explicit("int_002", feedback_type=FeedbackType.THUMBS_DOWN)
        loop.collect_explicit("int_003", feedback_type=FeedbackType.THUMBS_UP)
        loop.collect_explicit("int_004", feedback_type=FeedbackType.THUMBS_UP)
        trend = loop.get_trend(window_seconds=3600)
        assert trend["count"] == 4
        assert trend["trend_direction"] == "improving"

    def test_declining_trend(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        # 前半段正面，后半段负面 → declining
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)
        loop.collect_explicit("int_002", feedback_type=FeedbackType.THUMBS_UP)
        loop.collect_explicit("int_003", feedback_type=FeedbackType.THUMBS_DOWN)
        loop.collect_explicit("int_004", feedback_type=FeedbackType.THUMBS_DOWN)
        trend = loop.get_trend(window_seconds=3600)
        assert trend["trend_direction"] == "declining"

    def test_stable_trend(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.NEUTRAL)
        loop.collect_explicit("int_002", feedback_type=FeedbackType.NEUTRAL)
        trend = loop.get_trend(window_seconds=3600)
        assert trend["trend_direction"] == "stable"

    def test_positive_ratio(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)
        loop.collect_explicit("int_002", feedback_type=FeedbackType.THUMBS_DOWN)
        trend = loop.get_trend(window_seconds=3600)
        assert trend["positive_ratio"] == 0.5
        assert trend["negative_ratio"] == 0.5


# ═══════════════════════════════════════════════════════════════
#  Statistics
# ═══════════════════════════════════════════════════════════════


class TestStatistics:
    """统计信息测试."""

    def test_empty_stats(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        stats = loop.get_stats()
        assert stats["total_entries"] == 0

    def test_stats_with_data(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)
        loop.collect_explicit("int_002", feedback_type=FeedbackType.THUMBS_DOWN)
        loop.collect_implicit("int_003", retries=1, edited=True)
        stats = loop.get_stats()
        assert stats["total_entries"] == 3
        assert stats["explicit_feedbacks"] == 2
        assert stats["implicit_feedbacks"] == 1
        assert stats["positive"] == 1
        # int_002 (thumbs_down) and int_003 (implicit negative) both count as negative
        assert stats["negative"] == 2

    def test_stats_implicit_signals(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_implicit("int_001", edited=True, abandoned=True, copied=True)
        loop.collect_implicit("int_002", regenerated=True)
        stats = loop.get_stats()
        assert stats["edited_count"] == 1
        assert stats["abandoned_count"] == 1
        assert stats["copied_count"] == 1
        assert stats["regenerated_count"] == 1

    def test_entry_count(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)
        assert loop.entry_count == 1

    def test_entries_property(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)
        entries = loop.entries
        assert len(entries) == 1


# ═══════════════════════════════════════════════════════════════
#  Evolution Engine Integration
# ═══════════════════════════════════════════════════════════════


class TestEvolutionIntegration:
    """Evolution 引擎集成测试."""

    def test_feed_to_learning_engine(self):
        """测试传递给 LearningEngine."""
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)
        loop.collect_implicit("int_001", retries=0)

        # Mock LearningEngine
        mock_engine = MagicMock()
        mock_record = MagicMock()
        mock_record.id = "int_001"
        mock_engine.get_interactions.return_value = [mock_record]

        result = loop.feed_to_evolution(engine=mock_engine)
        assert result["learning_engine"] == 1
        # 验证 feedback 被设置
        assert hasattr(mock_record, "feedback")

    def test_feed_to_feedback_collector(self):
        """测试传递给 evolution.FeedbackCollector."""
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)
        loop.collect_implicit("int_001", retries=1)

        mock_collector = MagicMock()
        result = loop.feed_to_evolution(collector=mock_collector)
        assert result["feedback_collector"] == 1
        # 验证 collect_explicit 被调用
        mock_collector.collect_explicit.assert_called_once()
        mock_collector.collect_implicit.assert_called_once()

    def test_feed_to_orchestrator(self):
        """测试传递给 EvolutionOrchestrator."""
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)

        mock_orch = MagicMock()
        mock_learner = MagicMock()
        mock_record = MagicMock()
        mock_record.id = "int_001"
        mock_learner.get_interactions.return_value = [mock_record]
        mock_orch.learner = mock_learner
        mock_orch.feedback_collector = MagicMock()

        result = loop.feed_to_evolution(orchestrator=mock_orch)
        assert "orchestrator" in result

    def test_feed_no_components(self):
        """没有传入任何组件时返回空字典."""
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        result = loop.feed_to_evolution()
        assert result == {}

    def test_feed_multiple_components(self):
        """同时传递多个组件."""
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)

        mock_engine = MagicMock()
        mock_record = MagicMock()
        mock_record.id = "int_001"
        mock_engine.get_interactions.return_value = [mock_record]

        mock_collector = MagicMock()

        result = loop.feed_to_evolution(
            engine=mock_engine,
            collector=mock_collector,
        )
        assert "learning_engine" in result
        assert "feedback_collector" in result

    def test_star_rating_to_thumbs_conversion(self):
        """测试星评分转 thumbs 的逻辑."""
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.STAR_5)

        mock_collector = MagicMock()
        loop.feed_to_evolution(collector=mock_collector)
        # STAR_5 → thumbs_up
        call_args = mock_collector.collect_explicit.call_args
        assert call_args.kwargs["rating"] == "thumbs_up"


# ═══════════════════════════════════════════════════════════════
#  Persistence
# ═══════════════════════════════════════════════════════════════


class TestPersistence:
    """持久化测试."""

    def test_save_load(self):
        storage = tempfile.mkdtemp()
        loop = FeedbackLoop(storage_dir=storage)
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)
        loop.collect_implicit("int_001", retries=1, edited=True)

        # 加载
        loop2 = FeedbackLoop(storage_dir=storage)
        assert loop2.entry_count == 1
        entry = loop2.get_entry("int_001")
        assert entry.explicit_type == "thumbs_up"
        assert entry.implicit_retries == 1
        assert entry.implicit_edited is True

    def test_clear(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)
        loop.clear()
        assert loop.entry_count == 0

    def test_load_nonexistent(self):
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        assert loop.entry_count == 0

    def test_update_persists(self):
        """更新操作自动持久化."""
        storage = tempfile.mkdtemp()
        loop = FeedbackLoop(storage_dir=storage)
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)

        loop2 = FeedbackLoop(storage_dir=storage)
        loop2.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_DOWN)

        loop3 = FeedbackLoop(storage_dir=storage)
        entry = loop3.get_entry("int_001")
        assert entry.explicit_type == "thumbs_down"


# ═══════════════════════════════════════════════════════════════
#  Complex Scenario
# ═══════════════════════════════════════════════════════════════


class TestComplexScenario:
    """复杂场景测试 — 模拟完整反馈闭环."""

    def test_full_feedback_cycle(self):
        """模拟完整反馈收集→信号计算→Evolution传递的闭环."""
        storage = tempfile.mkdtemp()
        loop = FeedbackLoop(storage_dir=storage)

        # 交互 1: 用户点赞 + 复制回答
        loop.collect_explicit("int_001", feedback_type=FeedbackType.THUMBS_UP)
        loop.collect_implicit("int_001", copied=True, dwell_time=20.0, retries=0)

        # 交互 2: 用户点踩 + 重试
        loop.collect_explicit("int_002", feedback_type=FeedbackType.THUMBS_DOWN)
        loop.collect_implicit("int_002", retries=2, dwell_time=2.0)

        # 交互 3: 用户放弃
        loop.collect_implicit("int_003", abandoned=True)

        # 获取信号
        sig1 = loop.get_signal("int_001")
        sig2 = loop.get_signal("int_002")
        sig3 = loop.get_signal("int_003")

        assert sig1.combined > 0  # 正面
        assert sig2.combined < 0  # 负面
        assert sig3.combined < 0  # 负面（放弃）

        # 统计
        stats = loop.get_stats()
        assert stats["total_entries"] == 3
        assert stats["positive"] == 1
        assert stats["negative"] == 2

        # 趋势
        trend = loop.get_trend(window_seconds=3600)
        assert trend["count"] == 3

        # 传递给 Evolution 引擎
        mock_engine = MagicMock()
        mock_records = []
        for iid in ["int_001", "int_002", "int_003"]:
            r = MagicMock()
            r.id = iid
            mock_records.append(r)
        mock_engine.get_interactions.return_value = mock_records

        result = loop.feed_to_evolution(engine=mock_engine)
        assert result["learning_engine"] == 3

    def test_feedback_with_all_signal_types(self):
        """测试包含所有隐式信号类型的场景."""
        loop = FeedbackLoop(storage_dir=tempfile.mkdtemp())
        loop.collect_implicit(
            "int_001",
            retries=2,
            edited=True,
            abandoned=False,
            dwell_time=45.0,  # 较长停留（可能困惑）
            copied=True,
            regenerated=True,
        )
        signal = loop.get_signal("int_001")
        # 所有分量都有值
        assert signal.components["retry"] < 0
        assert signal.components["edit"] < 0
        assert signal.components["abandon"] == 0.0  # 未放弃
        assert signal.components["dwell"] != 0.0
        assert signal.components["copy"] > 0
        assert signal.components["regenerate"] < 0
