"""
Tests for Suyi Scheduler — Cron expression parsing, task scheduling, and trigger.

Covers:
    - CronExpression: parsing all wildcard syntax (*, /, -, ,)
    - CronExpression: boundary values, edge cases, invalid input
    - CronExpression: matches() and next_run() computation
    - CronExpression: serialization (to_dict / from_dict)
    - ScheduledTask: dataclass defaults, serialization round-trip
    - TaskScheduler: register, remove, list, enable/disable
    - TaskScheduler: get_pending_tasks, mark_executed
    - TaskScheduler: persistence with SQLiteBackend and in-memory
    - CronTrigger: trigger_once with MockLoop
    - CronTrigger: error handling, prompt extraction
    - CronTrigger: trigger_many batch execution
    - Integration: scheduler + trigger end-to-end
"""

import asyncio
import tempfile
import os
from datetime import datetime

import pytest

from suyi.scheduler import (
    CronExpression,
    ScheduledTask,
    TaskScheduler,
    CronTrigger,
    TriggerResult,
    MockLoop,
)
from suyi.persistence import SQLiteBackend


# ═══════════════════════════════════════════════════════════════
#  CronExpression — Parsing Tests
# ═══════════════════════════════════════════════════════════════


class TestCronExpressionParsing:
    """Test CronExpression field parsing for all supported syntax."""

    def test_wildcard_all(self):
        """'* * * * *' matches every minute of every day."""
        cron = CronExpression("* * * * *")
        assert cron.minutes == set(range(60))
        assert cron.hours == set(range(24))
        assert cron.days_of_month == set(range(1, 32))
        assert cron.months == set(range(1, 13))
        # day_of_week: * expands to 0-7, normalized to 0-6
        assert cron.days_of_week == {0, 1, 2, 3, 4, 5, 6}

    def test_step_every_5_minutes(self):
        """'*/5 * * * *' matches minutes 0,5,10,...,55."""
        cron = CronExpression("*/5 * * * *")
        assert cron.minutes == {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}

    def test_step_every_2_hours(self):
        """'0 */2 * * *' matches hours 0,2,4,...,22."""
        cron = CronExpression("0 */2 * * *")
        assert cron.hours == {0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22}

    def test_range_simple(self):
        """'0 9-17 * * *' matches hours 9 through 17."""
        cron = CronExpression("0 9-17 * * *")
        assert cron.hours == set(range(9, 18))

    def test_comma_list(self):
        """'0 9,12,18 * * *' matches hours 9, 12, 18."""
        cron = CronExpression("0 9,12,18 * * *")
        assert cron.hours == {9, 12, 18}

    def test_range_with_step(self):
        """'0-30/10 * * * *' matches minutes 0,10,20,30."""
        cron = CronExpression("0-30/10 * * * *")
        assert cron.minutes == {0, 10, 20, 30}

    def test_single_value(self):
        """'30 14 1 1 *' matches minute=30, hour=14, day=1, month=1."""
        cron = CronExpression("30 14 1 1 *")
        assert cron.minutes == {30}
        assert cron.hours == {14}
        assert cron.days_of_month == {1}
        assert cron.months == {1}

    def test_multiple_ranges_in_list(self):
        """'1-5,10-14 * * * *' matches minutes 1-5 and 10-14."""
        cron = CronExpression("1-5,10-14 * * * *")
        assert cron.minutes == {1, 2, 3, 4, 5, 10, 11, 12, 13, 14}

    def test_mixed_list_with_step(self):
        """'0,15,30-45/5 * * * *' matches 0,15,30,35,40,45."""
        cron = CronExpression("0,15,30-45/5 * * * *")
        assert cron.minutes == {0, 15, 30, 35, 40, 45}

    def test_value_with_step(self):
        """'5/15 * * * *' matches 5,20,35,50 (from 5 to max, step 15)."""
        cron = CronExpression("5/15 * * * *")
        assert cron.minutes == {5, 20, 35, 50}

    def test_sunday_as_0(self):
        """Day-of-week 0 represents Sunday."""
        cron = CronExpression("* * * * 0")
        assert cron.days_of_week == {0}

    def test_sunday_as_7(self):
        """Day-of-week 7 is normalized to 0 (Sunday)."""
        cron = CronExpression("* * * * 7")
        assert cron.days_of_week == {0}

    def test_weekday_range(self):
        """'1-5' in day-of-week matches Mon-Fri (1,2,3,4,5)."""
        cron = CronExpression("* * * * 1-5")
        assert cron.days_of_week == {1, 2, 3, 4, 5}


# ═══════════════════════════════════════════════════════════════
#  CronExpression — Invalid Input Tests
# ═══════════════════════════════════════════════════════════════


class TestCronExpressionInvalid:
    """Test CronExpression error handling for invalid input."""

    def test_too_few_fields(self):
        with pytest.raises(ValueError, match="5 fields"):
            CronExpression("* * * *")

    def test_too_many_fields(self):
        with pytest.raises(ValueError, match="5 fields"):
            CronExpression("* * * * * *")

    def test_empty_string(self):
        with pytest.raises(ValueError, match="5 fields"):
            CronExpression("")

    def test_minute_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            CronExpression("60 * * * *")

    def test_hour_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            CronExpression("* 24 * * *")

    def test_day_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            CronExpression("* * 0 * *")

    def test_month_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            CronExpression("* * * 13 *")

    def test_weekday_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            CronExpression("* * * * 8")

    def test_negative_value(self):
        with pytest.raises(ValueError, match="Invalid"):
            CronExpression("-1 * * * *")

    def test_invalid_step_zero(self):
        with pytest.raises(ValueError, match="positive"):
            CronExpression("*/0 * * * *")

    def test_invalid_step_negative(self):
        with pytest.raises(ValueError, match="positive"):
            CronExpression("*/-5 * * * *")

    def test_invalid_step_text(self):
        with pytest.raises(ValueError, match="Invalid step"):
            CronExpression("*/abc * * * *")

    def test_invalid_range_text(self):
        with pytest.raises(ValueError, match="Invalid range"):
            CronExpression("a-b * * * *")

    def test_empty_comma_element(self):
        with pytest.raises(ValueError, match="Empty list element"):
            CronExpression("1,,3 * * * *")

    def test_range_start_gt_end(self):
        with pytest.raises(ValueError):
            CronExpression("10-5 * * * *")


# ═══════════════════════════════════════════════════════════════
#  CronExpression — Matches Tests
# ═══════════════════════════════════════════════════════════════


class TestCronExpressionMatches:
    """Test CronExpression.matches() with various expressions and datetimes."""

    def test_every_minute_matches(self):
        cron = CronExpression("* * * * *")
        assert cron.matches(datetime(2025, 6, 15, 12, 30, 45))

    def test_specific_minute_matches(self):
        cron = CronExpression("30 * * * *")
        assert cron.matches(datetime(2025, 6, 15, 12, 30, 0))
        assert not cron.matches(datetime(2025, 6, 15, 12, 31, 0))

    def test_specific_hour_matches(self):
        cron = CronExpression("* 14 * * *")
        assert cron.matches(datetime(2025, 6, 15, 14, 0, 0))
        assert not cron.matches(datetime(2025, 6, 15, 15, 0, 0))

    def test_specific_day_matches(self):
        cron = CronExpression("* * 15 * *")
        assert cron.matches(datetime(2025, 6, 15, 0, 0, 0))
        assert not cron.matches(datetime(2025, 6, 16, 0, 0, 0))

    def test_specific_month_matches(self):
        cron = CronExpression("* * * 6 *")
        assert cron.matches(datetime(2025, 6, 15, 0, 0, 0))
        assert not cron.matches(datetime(2025, 7, 15, 0, 0, 0))

    def test_weekday_sunday(self):
        """2025-06-15 is a Sunday — should match day-of-week 0."""
        cron = CronExpression("* * * * 0")
        # June 15, 2025 is a Sunday
        assert cron.matches(datetime(2025, 6, 15, 12, 0, 0))

    def test_weekday_monday(self):
        """2025-06-16 is a Monday — should match day-of-week 1."""
        cron = CronExpression("* * * * 1")
        assert cron.matches(datetime(2025, 6, 16, 12, 0, 0))
        assert not cron.matches(datetime(2025, 6, 17, 12, 0, 0))

    def test_weekday_range_mon_fri(self):
        cron = CronExpression("0 9 * * 1-5")
        # Monday June 16, 2025
        assert cron.matches(datetime(2025, 6, 16, 9, 0, 0))
        # Saturday June 21, 2025
        assert not cron.matches(datetime(2025, 6, 21, 9, 0, 0))

    def test_dom_and_dow_or_logic(self):
        """When both dom and dow are restricted, OR logic applies."""
        cron = CronExpression("0 0 15 * 1")
        # 15th of June 2025 is a Sunday — matches via dom
        assert cron.matches(datetime(2025, 6, 15, 0, 0, 0))
        # Monday June 16 — matches via dow (1=Monday)
        assert cron.matches(datetime(2025, 6, 16, 0, 0, 0))
        # Tuesday June 17 — not 15th and not Monday
        assert not cron.matches(datetime(2025, 6, 17, 0, 0, 0))

    def test_dom_only_restricted(self):
        """When only dom is restricted (dow is *), dom must match."""
        cron = CronExpression("0 0 15 * *")
        assert cron.matches(datetime(2025, 6, 15, 0, 0, 0))
        assert not cron.matches(datetime(2025, 6, 16, 0, 0, 0))

    def test_step_matches(self):
        cron = CronExpression("*/15 * * * *")
        assert cron.matches(datetime(2025, 6, 15, 12, 0, 0))
        assert cron.matches(datetime(2025, 6, 15, 12, 15, 0))
        assert cron.matches(datetime(2025, 6, 15, 12, 30, 0))
        assert cron.matches(datetime(2025, 6, 15, 12, 45, 0))
        assert not cron.matches(datetime(2025, 6, 15, 12, 7, 0))

    def test_seconds_ignored(self):
        """Seconds and microseconds should not affect matching."""
        cron = CronExpression("30 14 * * *")
        assert cron.matches(datetime(2025, 6, 15, 14, 30, 0))
        assert cron.matches(datetime(2025, 6, 15, 14, 30, 59))
        assert cron.matches(datetime(2025, 6, 15, 14, 30, 0, 999999))


# ═══════════════════════════════════════════════════════════════
#  CronExpression — Next Run Tests
# ═══════════════════════════════════════════════════════════════


class TestCronExpressionNextRun:
    """Test CronExpression.next_run() computation."""

    def test_every_minute_next(self):
        cron = CronExpression("* * * * *")
        after = datetime(2025, 6, 15, 12, 0, 0)
        result = cron.next_run(after)
        assert result == datetime(2025, 6, 15, 12, 1, 0)

    def test_every_5_minutes_next(self):
        cron = CronExpression("*/5 * * * *")
        after = datetime(2025, 6, 15, 12, 3, 0)
        result = cron.next_run(after)
        assert result == datetime(2025, 6, 15, 12, 5, 0)

    def test_daily_at_9am(self):
        cron = CronExpression("0 9 * * *")
        after = datetime(2025, 6, 15, 10, 0, 0)
        result = cron.next_run(after)
        assert result == datetime(2025, 6, 16, 9, 0, 0)

    def test_daily_at_9am_same_day_before(self):
        cron = CronExpression("0 9 * * *")
        after = datetime(2025, 6, 15, 8, 0, 0)
        result = cron.next_run(after)
        assert result == datetime(2025, 6, 15, 9, 0, 0)

    def test_monthly_first_day(self):
        cron = CronExpression("0 0 1 * *")
        after = datetime(2025, 6, 15, 12, 0, 0)
        result = cron.next_run(after)
        assert result == datetime(2025, 7, 1, 0, 0, 0)

    def test_weekly_sunday(self):
        cron = CronExpression("0 0 * * 0")
        # June 15, 2025 is Sunday; June 16 is Monday
        after = datetime(2025, 6, 16, 12, 0, 0)
        result = cron.next_run(after)
        # Next Sunday is June 22
        assert result == datetime(2025, 6, 22, 0, 0, 0)

    def test_specific_time(self):
        cron = CronExpression("30 14 25 12 *")
        after = datetime(2025, 6, 15, 12, 0, 0)
        result = cron.next_run(after)
        assert result == datetime(2025, 12, 25, 14, 30, 0)

    def test_next_run_strictly_after(self):
        """next_run should return a time strictly after `after`."""
        cron = CronExpression("0 12 * * *")
        after = datetime(2025, 6, 15, 12, 0, 0)
        result = cron.next_run(after)
        # Should be the next day at 12:00, not the same day
        assert result == datetime(2025, 6, 16, 12, 0, 0)

    def test_next_run_with_seconds(self):
        """next_run should zero out seconds and find next match."""
        cron = CronExpression("*/5 * * * *")
        after = datetime(2025, 6, 15, 12, 0, 30)
        result = cron.next_run(after)
        assert result == datetime(2025, 6, 15, 12, 5, 0)

    def test_next_run_exact_minute_match(self):
        """If `after` is exactly a match time, next match is the next cycle."""
        cron = CronExpression("*/10 * * * *")
        after = datetime(2025, 6, 15, 12, 10, 0)
        result = cron.next_run(after)
        assert result == datetime(2025, 6, 15, 12, 20, 0)

    def test_year_rollover(self):
        """next_run should handle year boundary correctly."""
        cron = CronExpression("0 0 1 1 *")
        after = datetime(2025, 6, 15, 12, 0, 0)
        result = cron.next_run(after)
        assert result == datetime(2026, 1, 1, 0, 0, 0)

    def test_february_edge(self):
        """next_run should handle February (28/29 days)."""
        cron = CronExpression("0 0 1 3 *")
        after = datetime(2025, 2, 28, 12, 0, 0)
        result = cron.next_run(after)
        assert result == datetime(2025, 3, 1, 0, 0, 0)


# ═══════════════════════════════════════════════════════════════
#  CronExpression — Serialization Tests
# ═══════════════════════════════════════════════════════════════


class TestCronExpressionSerialization:
    """Test CronExpression to_dict / from_dict serialization."""

    def test_to_dict(self):
        cron = CronExpression("*/5 * * * *")
        d = cron.to_dict()
        assert d["expression"] == "*/5 * * * *"
        assert d["minutes"] == [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]
        assert d["hours"] == list(range(24))
        assert d["dom_restricted"] is False
        assert d["dow_restricted"] is False

    def test_from_dict(self):
        d = {"expression": "0 9 * * *"}
        cron = CronExpression.from_dict(d)
        assert cron.expression == "0 9 * * *"
        assert cron.hours == {9}

    def test_round_trip(self):
        cron = CronExpression("30 14 1 1 0")
        d = cron.to_dict()
        restored = CronExpression.from_dict(d)
        assert restored.expression == cron.expression
        assert restored.minutes == cron.minutes
        assert restored.hours == cron.hours
        assert restored.days_of_month == cron.days_of_month
        assert restored.months == cron.months
        assert restored.days_of_week == cron.days_of_week

    def test_repr(self):
        cron = CronExpression("*/5 * * * *")
        assert repr(cron) == "CronExpression('*/5 * * * *')"

    def test_equality(self):
        a = CronExpression("0 9 * * *")
        b = CronExpression("0 9 * * *")
        c = CronExpression("0 10 * * *")
        assert a == b
        assert a != c

    def test_hashable(self):
        cron = CronExpression("0 9 * * *")
        # Should be usable in a set
        s = {cron, CronExpression("0 9 * * *")}
        assert len(s) == 1


# ═══════════════════════════════════════════════════════════════
#  ScheduledTask Tests
# ═══════════════════════════════════════════════════════════════


class TestScheduledTask:
    """Test ScheduledTask dataclass and serialization."""

    def test_defaults(self):
        cron = CronExpression("0 9 * * *")
        task = ScheduledTask(name="test", cron_expr=cron)
        assert task.name == "test"
        assert task.task_config == {}
        assert task.enabled is True
        assert task.last_run is None
        assert task.next_run is None
        assert task.last_result is None
        assert task.run_count == 0

    def test_with_config(self):
        cron = CronExpression("0 9 * * *")
        task = ScheduledTask(
            name="report",
            cron_expr=cron,
            task_config={"prompt": "Generate report", "priority": "high"},
            enabled=False,
        )
        assert task.task_config["prompt"] == "Generate report"
        assert task.enabled is False

    def test_to_dict(self):
        cron = CronExpression("0 9 * * *")
        task = ScheduledTask(
            name="test",
            cron_expr=cron,
            task_config={"prompt": "hello"},
            last_run=datetime(2025, 6, 15, 9, 0, 0),
            next_run=datetime(2025, 6, 16, 9, 0, 0),
            run_count=5,
        )
        d = task.to_dict()
        assert d["name"] == "test"
        assert d["cron_expression"] == "0 9 * * *"
        assert d["task_config"] == {"prompt": "hello"}
        assert d["last_run"] == "2025-06-15T09:00:00"
        assert d["next_run"] == "2025-06-16T09:00:00"
        assert d["run_count"] == 5

    def test_from_dict(self):
        d = {
            "name": "test",
            "cron_expression": "0 9 * * *",
            "task_config": {"prompt": "hello"},
            "enabled": False,
            "last_run": "2025-06-15T09:00:00",
            "next_run": "2025-06-16T09:00:00",
            "last_result": {"success": True},
            "run_count": 3,
        }
        task = ScheduledTask.from_dict(d)
        assert task.name == "test"
        assert task.cron_expr.expression == "0 9 * * *"
        assert task.task_config == {"prompt": "hello"}
        assert task.enabled is False
        assert task.last_run == datetime(2025, 6, 15, 9, 0, 0)
        assert task.next_run == datetime(2025, 6, 16, 9, 0, 0)
        assert task.run_count == 3
        assert task.last_result == {"success": True}

    def test_round_trip(self):
        cron = CronExpression("*/15 * * * *")
        task = ScheduledTask(
            name="check",
            cron_expr=cron,
            task_config={"prompt": "Status check"},
            last_run=datetime(2025, 6, 15, 9, 0, 0),
            next_run=datetime(2025, 6, 15, 9, 15, 0),
            run_count=10,
        )
        d = task.to_dict()
        restored = ScheduledTask.from_dict(d)
        assert restored.name == task.name
        assert restored.cron_expr.expression == task.cron_expr.expression
        assert restored.task_config == task.task_config
        assert restored.last_run == task.last_run
        assert restored.next_run == task.next_run
        assert restored.run_count == task.run_count

    def test_from_dict_none_datetimes(self):
        d = {
            "name": "test",
            "cron_expression": "0 9 * * *",
            "last_run": None,
            "next_run": None,
        }
        task = ScheduledTask.from_dict(d)
        assert task.last_run is None
        assert task.next_run is None

    def test_repr(self):
        cron = CronExpression("0 9 * * *")
        task = ScheduledTask(name="test", cron_expr=cron)
        assert "ScheduledTask" in repr(task)
        assert "test" in repr(task)


# ═══════════════════════════════════════════════════════════════
#  TaskScheduler — In-Memory Tests
# ═══════════════════════════════════════════════════════════════


class TestTaskSchedulerInMemory:
    """Test TaskScheduler with in-memory backend (backend=None)."""

    def test_register_task(self):
        sched = TaskScheduler()
        task = sched.register_task("daily", "0 9 * * *", {"prompt": "Hi"})
        assert task.name == "daily"
        assert task.cron_expr.expression == "0 9 * * *"
        assert task.task_config == {"prompt": "Hi"}
        assert task.enabled is True
        assert task.next_run is not None
        assert sched.count() == 1

    def test_register_duplicate_overwrites(self):
        sched = TaskScheduler()
        sched.register_task("daily", "0 9 * * *")
        sched.register_task("daily", "0 10 * * *")
        assert sched.count() == 1
        task = sched.get_task("daily")
        assert task.cron_expr.expression == "0 10 * * *"

    def test_remove_task(self):
        sched = TaskScheduler()
        sched.register_task("daily", "0 9 * * *")
        assert sched.remove_task("daily") is True
        assert sched.count() == 0
        assert sched.get_task("daily") is None

    def test_remove_nonexistent(self):
        sched = TaskScheduler()
        assert sched.remove_task("nonexistent") is False

    def test_get_task(self):
        sched = TaskScheduler()
        sched.register_task("daily", "0 9 * * *", {"prompt": "test"})
        task = sched.get_task("daily")
        assert task is not None
        assert task.name == "daily"

    def test_get_nonexistent_task(self):
        sched = TaskScheduler()
        assert sched.get_task("nonexistent") is None

    def test_list_tasks(self):
        sched = TaskScheduler()
        sched.register_task("beta", "0 9 * * *")
        sched.register_task("alpha", "0 10 * * *")
        tasks = sched.list_tasks()
        assert len(tasks) == 2
        assert tasks[0].name == "alpha"  # sorted by name
        assert tasks[1].name == "beta"

    def test_list_tasks_enabled_only(self):
        sched = TaskScheduler()
        sched.register_task("active", "0 9 * * *", enabled=True)
        sched.register_task("inactive", "0 10 * * *", enabled=False)
        tasks = sched.list_tasks(enabled_only=True)
        assert len(tasks) == 1
        assert tasks[0].name == "active"

    def test_enable_task(self):
        sched = TaskScheduler()
        sched.register_task("test", "0 9 * * *", enabled=False)
        assert sched.enable_task("test") is True
        task = sched.get_task("test")
        assert task.enabled is True
        assert task.next_run is not None

    def test_disable_task(self):
        sched = TaskScheduler()
        sched.register_task("test", "0 9 * * *", enabled=True)
        assert sched.disable_task("test") is True
        task = sched.get_task("test")
        assert task.enabled is False

    def test_enable_nonexistent(self):
        sched = TaskScheduler()
        assert sched.enable_task("nonexistent") is False

    def test_disable_nonexistent(self):
        sched = TaskScheduler()
        assert sched.disable_task("nonexistent") is False

    def test_get_pending_tasks(self):
        sched = TaskScheduler()
        # Register a task with every-minute cron
        sched.register_task("frequent", "* * * * *", {"prompt": "Frequent"})
        # Manually set next_run to the past so it's due now
        task = sched.get_task("frequent")
        task.next_run = datetime(2020, 1, 1, 0, 0, 0)
        now = datetime.now()
        pending = sched.get_pending_tasks(now)
        # "frequent" should be pending (next_run is in the past)
        names = [t.name for t in pending]
        assert "frequent" in names

    def test_get_pending_tasks_excludes_disabled(self):
        sched = TaskScheduler()
        sched.register_task("disabled", "* * * * *", enabled=False)
        pending = sched.get_pending_tasks(datetime.now())
        assert len(pending) == 0

    def test_mark_executed(self):
        sched = TaskScheduler()
        sched.register_task("test", "* * * * *")
        now = datetime(2025, 6, 15, 12, 0, 0)
        result = sched.mark_executed("test", {"success": True, "output": "ok"}, now=now)
        assert result is not None
        assert result.last_run == now
        assert result.last_result == {"success": True, "output": "ok"}
        assert result.run_count == 1
        assert result.next_run is not None
        assert result.next_run > now

    def test_mark_executed_nonexistent(self):
        sched = TaskScheduler()
        result = sched.mark_executed("nonexistent", {"success": False})
        assert result is None

    def test_mark_executed_increments_count(self):
        sched = TaskScheduler()
        sched.register_task("test", "* * * * *")
        sched.mark_executed("test", {"success": True}, now=datetime(2025, 1, 1, 0, 0, 0))
        sched.mark_executed("test", {"success": True}, now=datetime(2025, 1, 1, 0, 1, 0))
        sched.mark_executed("test", {"success": True}, now=datetime(2025, 1, 1, 0, 2, 0))
        task = sched.get_task("test")
        assert task.run_count == 3

    def test_update_next_runs(self):
        sched = TaskScheduler()
        sched.register_task("test", "0 9 * * *")
        now = datetime(2025, 6, 15, 8, 0, 0)
        sched.update_next_runs(now)
        task = sched.get_task("test")
        assert task.next_run == datetime(2025, 6, 15, 9, 0, 0)

    def test_clear(self):
        sched = TaskScheduler()
        sched.register_task("a", "0 9 * * *")
        sched.register_task("b", "0 10 * * *")
        removed = sched.clear()
        assert removed == 2
        assert sched.count() == 0

    def test_count(self):
        sched = TaskScheduler()
        assert sched.count() == 0
        sched.register_task("a", "0 9 * * *")
        assert sched.count() == 1
        sched.register_task("b", "0 10 * * *")
        assert sched.count() == 2

    def test_invalid_cron_raises(self):
        sched = TaskScheduler()
        with pytest.raises(ValueError):
            sched.register_task("bad", "invalid cron")

    def test_repr(self):
        sched = TaskScheduler()
        assert "TaskScheduler" in repr(sched)


# ═══════════════════════════════════════════════════════════════
#  TaskScheduler — SQLite Persistence Tests
# ═══════════════════════════════════════════════════════════════


class TestTaskSchedulerPersistence:
    """Test TaskScheduler persistence with SQLiteBackend."""

    @pytest.fixture
    def backend(self, tmp_path):
        """Create a temporary SQLiteBackend."""
        db_path = str(tmp_path / "test_scheduler.db")
        return SQLiteBackend(db_path)

    def test_persist_on_register(self, backend):
        sched = TaskScheduler(backend=backend)
        sched.register_task("daily", "0 9 * * *", {"prompt": "Hi"})
        # Data should be in the backend
        data = backend.get("scheduler:daily")
        assert data is not None
        assert data["name"] == "daily"
        assert data["cron_expression"] == "0 9 * * *"

    def test_load_from_backend_on_init(self, backend):
        # Register with first scheduler
        sched1 = TaskScheduler(backend=backend)
        sched1.register_task("daily", "0 9 * * *", {"prompt": "Hi"})
        sched1.mark_executed("daily", {"success": True}, now=datetime(2025, 6, 15, 9, 0, 0))

        # Create a new scheduler with the same backend — should load tasks
        sched2 = TaskScheduler(backend=backend)
        assert sched2.count() == 1
        task = sched2.get_task("daily")
        assert task is not None
        assert task.name == "daily"
        assert task.run_count == 1
        assert task.last_result == {"success": True}

    def test_persist_on_remove(self, backend):
        sched = TaskScheduler(backend=backend)
        sched.register_task("daily", "0 9 * * *")
        assert backend.exists("scheduler:daily")
        sched.remove_task("daily")
        assert not backend.exists("scheduler:daily")

    def test_persist_on_mark_executed(self, backend):
        sched = TaskScheduler(backend=backend)
        sched.register_task("test", "* * * * *")
        sched.mark_executed("test", {"success": True}, now=datetime(2025, 6, 15, 12, 0, 0))
        # Reload from backend
        sched2 = TaskScheduler(backend=backend)
        task = sched2.get_task("test")
        assert task.run_count == 1
        assert task.last_run == datetime(2025, 6, 15, 12, 0, 0)

    def test_persist_on_enable_disable(self, backend):
        sched = TaskScheduler(backend=backend)
        sched.register_task("test", "0 9 * * *", enabled=True)
        sched.disable_task("test")
        sched2 = TaskScheduler(backend=backend)
        task = sched2.get_task("test")
        assert task.enabled is False

    def test_clear_removes_from_backend(self, backend):
        sched = TaskScheduler(backend=backend)
        sched.register_task("a", "0 9 * * *")
        sched.register_task("b", "0 10 * * *")
        sched.clear()
        assert not backend.exists("scheduler:a")
        assert not backend.exists("scheduler:b")
        sched2 = TaskScheduler(backend=backend)
        assert sched2.count() == 0

    def test_corrupted_entry_skipped(self, backend):
        """Corrupted backend entries should be skipped without crashing."""
        backend.set("scheduler:corrupt", {"invalid": "no name or cron"})
        sched = TaskScheduler(backend=backend)
        # Should not crash, and corrupt entry should be skipped
        assert sched.count() == 0

    def test_custom_namespace(self, backend):
        sched = TaskScheduler(backend=backend, namespace="custom_ns:")
        sched.register_task("daily", "0 9 * * *")
        assert backend.exists("custom_ns:daily")
        assert not backend.exists("scheduler:daily")


# ═══════════════════════════════════════════════════════════════
#  CronTrigger — MockLoop Tests
# ═══════════════════════════════════════════════════════════════


class TestCronTrigger:
    """Test CronTrigger with MockLoop."""

    @pytest.fixture
    def task(self):
        cron = CronExpression("* * * * *")
        return ScheduledTask(
            name="test_task",
            cron_expr=cron,
            task_config={"prompt": "Execute me"},
        )

    @pytest.fixture
    def mock_loop(self):
        return MockLoop(response="Task done successfully")

    @pytest.fixture
    def trigger(self):
        return CronTrigger()

    def test_trigger_once_success(self, trigger, task, mock_loop):
        result = asyncio.run(trigger.trigger_once(task, mock_loop))
        assert result.success is True
        assert result.content == "Task done successfully"
        assert result.task_name == "test_task"
        assert result.error is None
        assert mock_loop.call_count == 1

    def test_trigger_once_uses_prompt_from_config(self, trigger, task, mock_loop):
        asyncio.run(trigger.trigger_once(task, mock_loop))
        assert mock_loop.call_log[0]["user_message"] == "Execute me"

    def test_trigger_once_uses_message_key(self, trigger, mock_loop):
        cron = CronExpression("* * * * *")
        task = ScheduledTask(
            name="msg_task",
            cron_expr=cron,
            task_config={"message": "Run via message key"},
        )
        asyncio.run(trigger.trigger_once(task, mock_loop))
        assert mock_loop.call_log[0]["user_message"] == "Run via message key"

    def test_trigger_once_uses_user_message_key(self, trigger, mock_loop):
        cron = CronExpression("* * * * *")
        task = ScheduledTask(
            name="um_task",
            cron_expr=cron,
            task_config={"user_message": "Run via user_message key"},
        )
        asyncio.run(trigger.trigger_once(task, mock_loop))
        assert mock_loop.call_log[0]["user_message"] == "Run via user_message key"

    def test_trigger_once_default_prompt(self, trigger, mock_loop):
        cron = CronExpression("* * * * *")
        task = ScheduledTask(name="no_prompt", cron_expr=cron, task_config={})
        asyncio.run(trigger.trigger_once(task, mock_loop))
        # Should use default prompt
        assert mock_loop.call_log[0]["user_message"] == "Execute scheduled task."

    def test_trigger_once_custom_default_prompt(self, mock_loop):
        trigger = CronTrigger(default_prompt="Custom default")
        cron = CronExpression("* * * * *")
        task = ScheduledTask(name="no_prompt", cron_expr=cron, task_config={})
        asyncio.run(trigger.trigger_once(task, mock_loop))
        assert mock_loop.call_log[0]["user_message"] == "Custom default"

    def test_trigger_once_handles_exception(self, trigger, task, mock_loop):
        mock_loop.set_exception(RuntimeError("LLM service unavailable"))
        result = asyncio.run(trigger.trigger_once(task, mock_loop))
        assert result.success is False
        assert "RuntimeError" in result.error
        assert "LLM service unavailable" in result.error
        assert result.content == ""

    def test_trigger_once_handles_value_error(self, trigger, task, mock_loop):
        mock_loop.set_exception(ValueError("Bad input"))
        result = asyncio.run(trigger.trigger_once(task, mock_loop))
        assert result.success is False
        assert "ValueError" in result.error

    def test_trigger_once_records_timestamps(self, trigger, task, mock_loop):
        before = datetime.now()
        result = asyncio.run(trigger.trigger_once(task, mock_loop))
        after = datetime.now()
        assert result.started_at is not None
        assert result.finished_at is not None
        assert result.started_at >= before
        assert result.finished_at <= after
        assert result.finished_at >= result.started_at

    def test_trigger_many_sequential(self, trigger, mock_loop):
        cron = CronExpression("* * * * *")
        tasks = [
            ScheduledTask(name="t1", cron_expr=cron, task_config={"prompt": "First"}),
            ScheduledTask(name="t2", cron_expr=cron, task_config={"prompt": "Second"}),
            ScheduledTask(name="t3", cron_expr=cron, task_config={"prompt": "Third"}),
        ]
        results = asyncio.run(trigger.trigger_many(tasks, mock_loop))
        assert len(results) == 3
        assert all(r.success for r in results)
        assert mock_loop.call_count == 3
        assert mock_loop.call_log[0]["user_message"] == "First"
        assert mock_loop.call_log[1]["user_message"] == "Second"
        assert mock_loop.call_log[2]["user_message"] == "Third"

    def test_trigger_many_partial_failure(self, trigger):
        """trigger_many should continue even if one task fails."""
        mock_loop = MockLoop()
        cron = CronExpression("* * * * *")
        tasks = [
            ScheduledTask(name="ok1", cron_expr=cron, task_config={"prompt": "ok"}),
            ScheduledTask(name="fail", cron_expr=cron, task_config={"prompt": "fail"}),
            ScheduledTask(name="ok2", cron_expr=cron, task_config={"prompt": "ok"}),
        ]

        # Use a custom mock that fails on the second call
        class FlakyLoop:
            def __init__(self):
                self.calls = 0

            async def run(self, user_message: str):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("Flaky failure")
                return _SimpleResult(f"Result for {user_message}")

        class _SimpleResult:
            def __init__(self, content):
                self.content = content
                self.turns_used = 1
                self.stop_reason = "natural"

        flaky = FlakyLoop()
        results = asyncio.run(trigger.trigger_many(tasks, flaky))
        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True

    def test_trigger_result_to_dict(self, trigger, task, mock_loop):
        result = asyncio.run(trigger.trigger_once(task, mock_loop))
        d = result.to_dict()
        assert d["task_name"] == "test_task"
        assert d["success"] is True
        assert d["content"] == "Task done successfully"
        assert d["error"] is None
        assert "started_at" in d
        assert "finished_at" in d

    def test_trigger_result_repr(self, trigger, task, mock_loop):
        result = asyncio.run(trigger.trigger_once(task, mock_loop))
        assert "TriggerResult" in repr(result)
        assert "test_task" in repr(result)

    def test_mock_loop_reset(self, trigger, task, mock_loop):
        asyncio.run(trigger.trigger_once(task, mock_loop))
        assert mock_loop.call_count == 1
        mock_loop.reset()
        assert mock_loop.call_count == 0
        asyncio.run(trigger.trigger_once(task, mock_loop))
        assert mock_loop.call_count == 1

    def test_mock_loop_set_response(self, trigger, task, mock_loop):
        mock_loop.set_response("New response")
        result = asyncio.run(trigger.trigger_once(task, mock_loop))
        assert result.content == "New response"

    def test_mock_loop_set_exception_one_shot(self, trigger, task, mock_loop):
        """After raising once, the exception state persists until reset."""
        mock_loop.set_exception(ConnectionError("Network down"))
        result = asyncio.run(trigger.trigger_once(task, mock_loop))
        assert result.success is False
        # Second call should still raise (exception persists)
        result2 = asyncio.run(trigger.trigger_once(task, mock_loop))
        assert result2.success is False


# ═══════════════════════════════════════════════════════════════
#  Integration — Scheduler + Trigger
# ═══════════════════════════════════════════════════════════════


class TestSchedulerTriggerIntegration:
    """End-to-end integration of TaskScheduler + CronTrigger + MockLoop."""

    def test_full_cycle(self):
        """Register → check pending → trigger → mark executed → check advanced."""
        sched = TaskScheduler()
        trigger = CronTrigger()
        mock_loop = MockLoop(response="Done")

        # Register a task
        sched.register_task("health_check", "* * * * *", {"prompt": "Check health"})

        # Set next_run to the past so it's pending
        task = sched.get_task("health_check")
        task.next_run = datetime(2020, 1, 1, 0, 0, 0)

        # Get pending tasks (should include the task)
        now = datetime.now()
        pending = sched.get_pending_tasks(now)
        assert len(pending) >= 1

        task = pending[0]
        assert task.name == "health_check"

        # Execute via trigger
        result = asyncio.run(trigger.trigger_once(task, mock_loop))
        assert result.success is True
        assert result.content == "Done"

        # Mark executed
        sched.mark_executed(task.name, result.to_dict(), now=now)

        # Verify task state updated
        updated = sched.get_task("health_check")
        assert updated.run_count == 1
        assert updated.last_run == now
        assert updated.last_result is not None
        assert updated.last_result["success"] is True
        # next_run should be in the future
        assert updated.next_run > now

    def test_disabled_task_not_triggered(self):
        """Disabled tasks should not appear in pending and not be triggered."""
        sched = TaskScheduler()
        trigger = CronTrigger()
        mock_loop = MockLoop()

        sched.register_task("disabled_task", "* * * * *", enabled=False)
        pending = sched.get_pending_tasks(datetime.now())
        assert len(pending) == 0
        assert mock_loop.call_count == 0

    def test_multiple_tasks_with_persistence(self, tmp_path):
        """Test full cycle with SQLiteBackend persistence."""
        db_path = str(tmp_path / "integration.db")
        backend = SQLiteBackend(db_path)

        # First session: register and execute
        sched1 = TaskScheduler(backend=backend)
        sched1.register_task("task_a", "* * * * *", {"prompt": "A"})
        sched1.register_task("task_b", "0 9 * * *", {"prompt": "B"})

        # Set task_a's next_run to the past so it's pending
        task_a = sched1.get_task("task_a")
        task_a.next_run = datetime(2020, 1, 1, 0, 0, 0)

        now = datetime.now()
        pending = sched1.get_pending_tasks(now)
        # task_a (every minute, next_run in past) should be pending
        assert any(t.name == "task_a" for t in pending)

        # Execute task_a
        sched1.mark_executed("task_a", {"success": True}, now=now)

        # Second session: reload from backend
        sched2 = TaskScheduler(backend=backend)
        assert sched2.count() == 2

        task_a = sched2.get_task("task_a")
        assert task_a is not None
        assert task_a.run_count == 1
        assert task_a.last_result == {"success": True}

        task_b = sched2.get_task("task_b")
        assert task_b is not None
        assert task_b.run_count == 0
