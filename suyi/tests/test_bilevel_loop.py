"""
Tests for the Bilevel Loop Integration (Phase 16).

Covers:
    - ExecutionLogEntry: creation, defaults, serialisation, repr.
    - ExecutionLog: add_entry, finalize, queries, serialisation.
    - TaskResult: creation, derived properties, serialisation, repr.
    - TriggerType: enum values and distinctness.
    - TriggerConfig: defaults, enabled_types, serialisation.
    - TriggerEvaluator: all four trigger types, state management.
    - TaskLoop: simulated execution, agent-driven execution, template
      selection, default fallback, execution log, quality assessment.
    - EvolutionLoop: process reflection, template stats, memory quality,
      anti-pattern registration, mutation, A/B experiments.
    - BilevelLoop: run, run_batch, trigger evaluation, properties.
    - AgentLoop template-driven mode: backward compatibility,
      run_with_template, phase execution, reflection points.
    - Integration: full bilevel pipeline, A/B test creation, failure
      handling, batch processing.
"""

import json
import math
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from suyi.core.loop import (
    AgentLoop,
    MockLLM,
    LLMResponse,
    LoopResult,
    ToolCall,
    ToolResult,
    Tool,
    FunctionTool,
    LoopState,
    Middleware,
)
from suyi.core.budget import BudgetTracker, BudgetConfig
from suyi.quality.grader import (
    QualityScore,
    QualityAssessor,
    ResultQuality,
    SourceQuality,
)
from suyi.quality.forgetting import (
    ForgettingAction,
    ForgettingEngine,
    MemoryRecord,
)
from suyi.quality.anti_pattern import (
    AntiPattern,
    AntiPatternStore,
    compute_signature,
)
from suyi.quality.loop_template import (
    LoopPhase,
    LoopTemplate,
    LoopTemplateStore,
    DefaultTemplates,
    compute_task_signature,
)
from suyi.quality.strategy_evolver import (
    ProcessReflection,
    ExecutionResult,
    MutationType,
    MutationProposal,
    StrategyEvolver,
    Experiment,
    ExperimentResult,
    ABTestFramework,
)
from suyi.quality.bilevel_loop import (
    ExecutionLogEntry,
    ExecutionLog,
    TaskResult,
    TriggerType,
    TriggerConfig,
    TriggerEvaluator,
    TaskLoop,
    EvolutionLoop,
    BilevelLoop,
)
from suyi.persistence.sqlite_backend import SQLiteBackend


# ═══════════════════════════════════════════════════════════════
#  Helper: run async function in tests
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
#  ExecutionLogEntry Tests
# ═══════════════════════════════════════════════════════════════


class TestExecutionLogEntry(unittest.TestCase):
    """Tests for ExecutionLogEntry dataclass."""

    def test_creation_with_defaults(self):
        entry = ExecutionLogEntry()
        self.assertEqual(entry.phase_name, "")
        self.assertEqual(entry.action, "")
        self.assertEqual(entry.tools_used, [])
        self.assertEqual(entry.duration, 0.0)
        self.assertEqual(entry.result, "")
        self.assertEqual(entry.errors, [])
        self.assertEqual(entry.iteration, 0)
        self.assertEqual(entry.step_index, 0)
        self.assertTrue(entry.timestamp)  # should have a timestamp

    def test_creation_with_values(self):
        entry = ExecutionLogEntry(
            phase_name="execute",
            action="Running search tool",
            tools_used=["search", "cache"],
            duration=0.123,
            result="Found 3 results",
            errors=["timeout"],
            iteration=2,
            step_index=1,
        )
        self.assertEqual(entry.phase_name, "execute")
        self.assertEqual(entry.action, "Running search tool")
        self.assertEqual(entry.tools_used, ["search", "cache"])
        self.assertEqual(entry.duration, 0.123)
        self.assertEqual(entry.result, "Found 3 results")
        self.assertEqual(entry.errors, ["timeout"])
        self.assertEqual(entry.iteration, 2)
        self.assertEqual(entry.step_index, 1)

    def test_to_dict(self):
        entry = ExecutionLogEntry(
            phase_name="plan",
            action="Deciding approach",
            tools_used=["reasoning"],
            duration=0.5,
            result="Plan A",
            errors=[],
            iteration=0,
            step_index=2,
        )
        d = entry.to_dict()
        self.assertEqual(d["phase_name"], "plan")
        self.assertEqual(d["action"], "Deciding approach")
        self.assertEqual(d["tools_used"], ["reasoning"])
        self.assertEqual(d["duration"], 0.5)
        self.assertEqual(d["result"], "Plan A")
        self.assertEqual(d["errors"], [])
        self.assertEqual(d["iteration"], 0)
        self.assertEqual(d["step_index"], 2)

    def test_from_dict(self):
        data = {
            "phase_name": "verify",
            "action": "Checking results",
            "tools_used": ["validator"],
            "duration": 0.01,
            "result": "All checks passed",
            "errors": [],
            "timestamp": "2025-01-01T00:00:00Z",
            "iteration": 1,
            "step_index": 3,
        }
        entry = ExecutionLogEntry.from_dict(data)
        self.assertEqual(entry.phase_name, "verify")
        self.assertEqual(entry.action, "Checking results")
        self.assertEqual(entry.tools_used, ["validator"])
        self.assertEqual(entry.duration, 0.01)
        self.assertEqual(entry.result, "All checks passed")
        self.assertEqual(entry.timestamp, "2025-01-01T00:00:00Z")
        self.assertEqual(entry.iteration, 1)
        self.assertEqual(entry.step_index, 3)

    def test_serialisation_roundtrip(self):
        entry = ExecutionLogEntry(
            phase_name="reflect",
            action="Reflecting on execution",
            tools_used=["memory"],
            duration=0.3,
            result="Need improvement",
            errors=["minor issue"],
            iteration=3,
            step_index=4,
        )
        d = entry.to_dict()
        restored = ExecutionLogEntry.from_dict(d)
        self.assertEqual(restored.phase_name, entry.phase_name)
        self.assertEqual(restored.action, entry.action)
        self.assertEqual(restored.tools_used, entry.tools_used)
        self.assertEqual(restored.duration, entry.duration)
        self.assertEqual(restored.result, entry.result)
        self.assertEqual(restored.errors, entry.errors)
        self.assertEqual(restored.iteration, entry.iteration)
        self.assertEqual(restored.step_index, entry.step_index)

    def test_repr(self):
        entry = ExecutionLogEntry(phase_name="execute", iteration=1, step_index=0)
        r = repr(entry)
        self.assertIn("execute", r)
        self.assertIn("iter=1", r)

    def test_empty_errors(self):
        entry = ExecutionLogEntry(errors=[])
        self.assertEqual(len(entry.errors), 0)

    def test_multiple_errors(self):
        entry = ExecutionLogEntry(errors=["err1", "err2", "err3"])
        self.assertEqual(len(entry.errors), 3)

    def test_duration_precision(self):
        entry = ExecutionLogEntry(duration=0.000001)
        d = entry.to_dict()
        self.assertEqual(d["duration"], 0.000001)


# ═══════════════════════════════════════════════════════════════
#  ExecutionLog Tests
# ═══════════════════════════════════════════════════════════════


class TestExecutionLog(unittest.TestCase):
    """Tests for ExecutionLog dataclass."""

    def test_creation_empty(self):
        log = ExecutionLog()
        self.assertEqual(log.entry_count, 0)
        self.assertFalse(log.has_errors)
        self.assertEqual(log.all_tools_used, [])
        self.assertEqual(log.phases_executed, [])
        self.assertEqual(log.total_errors, 0)
        self.assertEqual(log.iteration_count, 0)
        self.assertTrue(log.started_at)

    def test_add_entry(self):
        log = ExecutionLog()
        entry = ExecutionLogEntry(
            phase_name="execute",
            tools_used=["search"],
            duration=0.5,
        )
        log.add_entry(entry)
        self.assertEqual(log.entry_count, 1)
        self.assertEqual(log.total_duration, 0.5)

    def test_add_multiple_entries(self):
        log = ExecutionLog()
        for i in range(5):
            log.add_entry(ExecutionLogEntry(
                phase_name="execute",
                tools_used=[f"tool_{i}"],
                duration=0.1 * i,
                iteration=i,
            ))
        self.assertEqual(log.entry_count, 5)
        self.assertEqual(log.total_duration, 0.1 * (0 + 1 + 2 + 3 + 4))

    def test_finalize(self):
        log = ExecutionLog()
        log.add_entry(ExecutionLogEntry(duration=0.1))
        log.add_entry(ExecutionLogEntry(duration=0.2))
        log.finalize()
        self.assertTrue(log.completed_at)
        self.assertAlmostEqual(log.total_duration, 0.3)

    def test_has_errors(self):
        log = ExecutionLog()
        log.add_entry(ExecutionLogEntry(phase_name="execute", errors=[]))
        self.assertFalse(log.has_errors)
        log.add_entry(ExecutionLogEntry(phase_name="execute", errors=["err"]))
        self.assertTrue(log.has_errors)

    def test_all_tools_used(self):
        log = ExecutionLog()
        log.add_entry(ExecutionLogEntry(tools_used=["search", "cache"]))
        log.add_entry(ExecutionLogEntry(tools_used=["search", "writer"]))
        self.assertEqual(log.all_tools_used, ["search", "cache", "writer"])

    def test_phases_executed(self):
        log = ExecutionLog()
        log.add_entry(ExecutionLogEntry(phase_name="perceive"))
        log.add_entry(ExecutionLogEntry(phase_name="plan"))
        log.add_entry(ExecutionLogEntry(phase_name="plan"))  # duplicate
        log.add_entry(ExecutionLogEntry(phase_name="execute"))
        self.assertEqual(log.phases_executed, ["perceive", "plan", "execute"])

    def test_error_entries(self):
        log = ExecutionLog()
        log.add_entry(ExecutionLogEntry(phase_name="execute", errors=[]))
        log.add_entry(ExecutionLogEntry(phase_name="execute", errors=["e1"]))
        log.add_entry(ExecutionLogEntry(phase_name="execute", errors=["e2", "e3"]))
        self.assertEqual(len(log.error_entries), 2)
        self.assertEqual(log.total_errors, 3)

    def test_iteration_count(self):
        log = ExecutionLog()
        log.add_entry(ExecutionLogEntry(iteration=0))
        log.add_entry(ExecutionLogEntry(iteration=0))
        log.add_entry(ExecutionLogEntry(iteration=1))
        log.add_entry(ExecutionLogEntry(iteration=2))
        self.assertEqual(log.iteration_count, 3)

    def test_iteration_count_empty(self):
        log = ExecutionLog()
        self.assertEqual(log.iteration_count, 0)

    def test_to_dict(self):
        log = ExecutionLog()
        log.add_entry(ExecutionLogEntry(phase_name="execute", duration=0.1))
        d = log.to_dict()
        self.assertIn("entries", d)
        self.assertEqual(d["entry_count"], 1)
        self.assertFalse(d["has_errors"])
        self.assertTrue(d["completed_at"])

    def test_from_dict(self):
        log = ExecutionLog()
        log.add_entry(ExecutionLogEntry(phase_name="plan", duration=0.2))
        d = log.to_dict()
        restored = ExecutionLog.from_dict(d)
        self.assertEqual(restored.entry_count, 1)
        self.assertEqual(restored.entries[0].phase_name, "plan")

    def test_serialisation_roundtrip(self):
        log = ExecutionLog()
        for i in range(3):
            log.add_entry(ExecutionLogEntry(
                phase_name=["perceive", "plan", "execute"][i],
                tools_used=[f"tool_{i}"],
                duration=0.1 * (i + 1),
                errors=["err"] if i == 2 else [],
                iteration=i,
            ))
        d = log.to_dict()
        restored = ExecutionLog.from_dict(d)
        self.assertEqual(restored.entry_count, 3)
        self.assertEqual(restored.total_errors, 1)
        self.assertTrue(restored.has_errors)

    def test_repr(self):
        log = ExecutionLog()
        log.add_entry(ExecutionLogEntry(duration=0.5))
        r = repr(log)
        self.assertIn("entries=1", r)


# ═══════════════════════════════════════════════════════════════
#  TaskResult Tests
# ═══════════════════════════════════════════════════════════════


class TestTaskResult(unittest.TestCase):
    """Tests for TaskResult dataclass."""

    def test_creation_with_defaults(self):
        result = TaskResult()
        self.assertEqual(result.task, "")
        self.assertEqual(result.template_id, "")
        self.assertIsNone(result.template_used)
        self.assertFalse(result.success)
        self.assertEqual(result.content, "")
        self.assertEqual(result.iterations, 0)
        self.assertEqual(result.token_cost, 0.0)
        self.assertEqual(result.errors, [])
        self.assertIsNone(result.reflection)
        self.assertEqual(result.task_signature, "")
        self.assertEqual(result.related_memories, [])

    def test_creation_with_values(self):
        template = DefaultTemplates.standard_react()
        quality = QualityScore(
            source=SourceQuality.A,
            result=ResultQuality.TRUSTED,
            confidence=0.85,
        )
        result = TaskResult(
            task="search for cats",
            template_id=template.id,
            template_used=template,
            quality=quality,
            success=True,
            content="Found 5 cats",
            iterations=3,
            token_cost=150.0,
            errors=[],
            task_signature="search cat",
        )
        self.assertEqual(result.task, "search for cats")
        self.assertEqual(result.template_id, template.id)
        self.assertTrue(result.success)
        self.assertEqual(result.content, "Found 5 cats")
        self.assertEqual(result.iterations, 3)
        self.assertEqual(result.token_cost, 150.0)

    def test_is_successful(self):
        r1 = TaskResult(success=True)
        r2 = TaskResult(success=False)
        self.assertTrue(r1.is_successful)
        self.assertFalse(r2.is_successful)

    def test_has_errors(self):
        r1 = TaskResult(errors=["err"])
        r2 = TaskResult(errors=[])
        r3 = TaskResult(
            execution_log=ExecutionLog(
                entries=[ExecutionLogEntry(errors=["log_err"])]
            )
        )
        self.assertTrue(r1.has_errors)
        self.assertFalse(r2.has_errors)
        self.assertTrue(r3.has_errors)

    def test_all_errors(self):
        result = TaskResult(
            errors=["task_err"],
            execution_log=ExecutionLog(
                entries=[
                    ExecutionLogEntry(errors=["log_err1"]),
                    ExecutionLogEntry(errors=[]),
                    ExecutionLogEntry(errors=["log_err2"]),
                ]
            ),
        )
        all_errs = result.all_errors
        self.assertIn("task_err", all_errs)
        self.assertIn("log_err1", all_errs)
        self.assertIn("log_err2", all_errs)
        self.assertEqual(len(all_errs), 3)

    def test_tools_used(self):
        result = TaskResult(
            execution_log=ExecutionLog(
                entries=[
                    ExecutionLogEntry(tools_used=["search"]),
                    ExecutionLogEntry(tools_used=["cache", "search"]),
                ]
            ),
        )
        self.assertEqual(result.tools_used, ["search", "cache"])

    def test_duration(self):
        log = ExecutionLog()
        log.add_entry(ExecutionLogEntry(duration=0.3))
        log.add_entry(ExecutionLogEntry(duration=0.7))
        result = TaskResult(execution_log=log)
        self.assertAlmostEqual(result.duration, 1.0)

    def test_quality_grade(self):
        result = TaskResult(
            quality=QualityScore(source=SourceQuality.S)
        )
        self.assertEqual(result.quality_grade, "S")

    def test_to_dict(self):
        template = DefaultTemplates.standard_react()
        quality = QualityScore(
            source=SourceQuality.A,
            result=ResultQuality.TRUSTED,
            confidence=0.8,
            evidence_count=2,
        )
        result = TaskResult(
            task="test task",
            template_id=template.id,
            template_used=template,
            quality=quality,
            success=True,
            content="Done",
            iterations=2,
            token_cost=100.0,
            task_signature="test task",
        )
        d = result.to_dict()
        self.assertEqual(d["task"], "test task")
        self.assertEqual(d["template_id"], template.id)
        self.assertTrue(d["success"])
        self.assertEqual(d["iterations"], 2)
        self.assertEqual(d["quality"]["source"], "A")
        self.assertEqual(d["quality"]["result"], "TRUSTED")

    def test_from_dict(self):
        template = DefaultTemplates.standard_react()
        quality = QualityScore(
            source=SourceQuality.B,
            result=ResultQuality.TRUSTED,
            confidence=0.7,
        )
        result = TaskResult(
            task="from dict test",
            template_id=template.id,
            template_used=template,
            quality=quality,
            success=True,
            content="Result",
            iterations=5,
            token_cost=50.0,
            task_signature="from dict test",
        )
        d = result.to_dict()
        restored = TaskResult.from_dict(d)
        self.assertEqual(restored.task, "from dict test")
        self.assertEqual(restored.template_id, template.id)
        self.assertTrue(restored.success)
        self.assertEqual(restored.iterations, 5)
        self.assertEqual(restored.quality.source, SourceQuality.B)
        self.assertEqual(restored.quality.result, ResultQuality.TRUSTED)

    def test_repr(self):
        result = TaskResult(task="hello", success=True, iterations=3, token_cost=100)
        r = repr(result)
        self.assertIn("OK", r)
        self.assertIn("hello", r)


# ═══════════════════════════════════════════════════════════════
#  TriggerType Tests
# ═══════════════════════════════════════════════════════════════


class TestTriggerType(unittest.TestCase):
    """Tests for TriggerType enum."""

    def test_has_four_types(self):
        self.assertEqual(len(TriggerType), 4)

    def test_all_distinct(self):
        values = [t for t in TriggerType]
        self.assertEqual(len(values), 4)
        self.assertEqual(len(set(values)), 4)

    def test_member_names(self):
        self.assertTrue(hasattr(TriggerType, "EVERY_TASK"))
        self.assertTrue(hasattr(TriggerType, "ACCUMULATED_N"))
        self.assertTrue(hasattr(TriggerType, "PERFORMANCE_DROP"))
        self.assertTrue(hasattr(TriggerType, "SCHEDULED"))


# ═══════════════════════════════════════════════════════════════
#  TriggerConfig Tests
# ═══════════════════════════════════════════════════════════════


class TestTriggerConfig(unittest.TestCase):
    """Tests for TriggerConfig dataclass."""

    def test_defaults(self):
        config = TriggerConfig()
        self.assertTrue(config.every_task)
        self.assertEqual(config.accumulated_n, 5)
        self.assertAlmostEqual(config.performance_drop_threshold, 0.15)
        self.assertAlmostEqual(config.scheduled_interval_seconds, 3600.0)
        self.assertTrue(config.enable_every_task)
        self.assertTrue(config.enable_accumulated)
        self.assertTrue(config.enable_performance)
        self.assertTrue(config.enable_scheduled)

    def test_enabled_types_all(self):
        config = TriggerConfig()
        types = config.enabled_types
        self.assertEqual(len(types), 4)
        self.assertIn(TriggerType.EVERY_TASK, types)
        self.assertIn(TriggerType.ACCUMULATED_N, types)
        self.assertIn(TriggerType.PERFORMANCE_DROP, types)
        self.assertIn(TriggerType.SCHEDULED, types)

    def test_enabled_types_none(self):
        config = TriggerConfig(
            enable_every_task=False,
            enable_accumulated=False,
            enable_performance=False,
            enable_scheduled=False,
        )
        self.assertEqual(len(config.enabled_types), 0)

    def test_enabled_types_partial(self):
        config = TriggerConfig(
            enable_every_task=True,
            enable_accumulated=False,
            enable_performance=True,
            enable_scheduled=False,
        )
        types = config.enabled_types
        self.assertEqual(len(types), 2)
        self.assertIn(TriggerType.EVERY_TASK, types)
        self.assertIn(TriggerType.PERFORMANCE_DROP, types)

    def test_to_dict(self):
        config = TriggerConfig(accumulated_n=10, performance_drop_threshold=0.2)
        d = config.to_dict()
        self.assertEqual(d["accumulated_n"], 10)
        self.assertAlmostEqual(d["performance_drop_threshold"], 0.2)
        self.assertIn("enabled_types", d)

    def test_custom_values(self):
        config = TriggerConfig(
            every_task=False,
            accumulated_n=20,
            performance_drop_threshold=0.3,
            scheduled_interval_seconds=1800.0,
        )
        self.assertFalse(config.every_task)
        self.assertEqual(config.accumulated_n, 20)
        self.assertAlmostEqual(config.performance_drop_threshold, 0.3)
        self.assertAlmostEqual(config.scheduled_interval_seconds, 1800.0)

    def test_repr(self):
        config = TriggerConfig()
        r = repr(config)
        self.assertIn("TriggerConfig", r)
        self.assertIn("EVERY_TASK", r)

    def test_disabled_every_task_but_others_enabled(self):
        config = TriggerConfig(
            every_task=False,
            enable_every_task=False,
            enable_accumulated=True,
        )
        types = config.enabled_types
        self.assertNotIn(TriggerType.EVERY_TASK, types)
        self.assertIn(TriggerType.ACCUMULATED_N, types)


# ═══════════════════════════════════════════════════════════════
#  TriggerEvaluator Tests
# ═══════════════════════════════════════════════════════════════


class TestTriggerEvaluator(unittest.TestCase):
    """Tests for TriggerEvaluator."""

    def _make_result(self, success=True, task="test task", sig="test"):
        return TaskResult(
            task=task,
            success=success,
            task_signature=sig,
            execution_log=ExecutionLog(
                entries=[ExecutionLogEntry(phase_name="execute")]
            ),
        )

    def test_init_default(self):
        evaluator = TriggerEvaluator()
        self.assertEqual(evaluator.task_count, 0)
        self.assertAlmostEqual(evaluator.recent_success_rate, 0.0)
        self.assertIsNone(evaluator.triggered_by)

    def test_init_with_config(self):
        config = TriggerConfig(accumulated_n=3)
        evaluator = TriggerEvaluator(config)
        self.assertEqual(evaluator.config.accumulated_n, 3)

    def test_record_result(self):
        evaluator = TriggerEvaluator(TriggerConfig(every_task=False, enable_every_task=False))
        result = self._make_result(success=True)
        evaluator.record_result(result)
        self.assertEqual(evaluator.task_count, 1)
        self.assertAlmostEqual(evaluator.recent_success_rate, 1.0)

    def test_trigger_every_task(self):
        config = TriggerConfig(every_task=True, enable_every_task=True)
        evaluator = TriggerEvaluator(config)
        result = self._make_result()
        evaluator.record_result(result)
        self.assertTrue(evaluator.should_trigger(result))
        self.assertEqual(evaluator.triggered_by, TriggerType.EVERY_TASK)

    def test_trigger_every_task_disabled(self):
        config = TriggerConfig(
            every_task=False, enable_every_task=False,
            enable_scheduled=False,
        )
        evaluator = TriggerEvaluator(config)
        result = self._make_result()
        evaluator.record_result(result)
        self.assertFalse(evaluator.should_trigger(result))

    def test_trigger_accumulated_n(self):
        config = TriggerConfig(
            every_task=False, enable_every_task=False,
            accumulated_n=3, enable_accumulated=True,
            enable_performance=False, enable_scheduled=False,
        )
        evaluator = TriggerEvaluator(config)
        sig = "same_sig"
        for i in range(2):
            result = self._make_result(success=True, sig=sig)
            evaluator.record_result(result)
            self.assertFalse(evaluator.should_trigger(result))
        # Third task should trigger
        result = self._make_result(success=True, sig=sig)
        evaluator.record_result(result)
        self.assertTrue(evaluator.should_trigger(result))
        self.assertEqual(evaluator.triggered_by, TriggerType.ACCUMULATED_N)

    def test_trigger_accumulated_n_reset_after_mark(self):
        config = TriggerConfig(
            every_task=False, enable_every_task=False,
            accumulated_n=2, enable_accumulated=True,
            enable_performance=False, enable_scheduled=False,
        )
        evaluator = TriggerEvaluator(config)
        sig = "sig1"
        for i in range(2):
            result = self._make_result(success=True, sig=sig)
            evaluator.record_result(result)
        self.assertTrue(evaluator.should_trigger(result))
        evaluator.mark_evolved(sig)
        # Next task should not trigger immediately
        result = self._make_result(success=True, sig=sig)
        evaluator.record_result(result)
        self.assertFalse(evaluator.should_trigger(result))

    def test_trigger_performance_drop(self):
        config = TriggerConfig(
            every_task=False, enable_every_task=False,
            enable_accumulated=False,
            performance_drop_threshold=0.15, enable_performance=True,
            enable_scheduled=False,
        )
        evaluator = TriggerEvaluator(config)
        # Record 3 failures (0% success rate, well below 85%)
        for i in range(3):
            result = self._make_result(success=False)
            evaluator.record_result(result)
        self.assertTrue(evaluator.should_trigger(result))
        self.assertEqual(evaluator.triggered_by, TriggerType.PERFORMANCE_DROP)

    def test_trigger_performance_drop_not_triggered(self):
        config = TriggerConfig(
            every_task=False, enable_every_task=False,
            enable_accumulated=False,
            performance_drop_threshold=0.15, enable_performance=True,
            enable_scheduled=False,
        )
        evaluator = TriggerEvaluator(config)
        # Record 3 successes (100% success rate, above 85%)
        for i in range(3):
            result = self._make_result(success=True)
            evaluator.record_result(result)
        self.assertFalse(evaluator.should_trigger(result))

    def test_trigger_performance_drop_insufficient_data(self):
        config = TriggerConfig(
            every_task=False, enable_every_task=False,
            enable_accumulated=False,
            performance_drop_threshold=0.15, enable_performance=True,
            enable_scheduled=False,
        )
        evaluator = TriggerEvaluator(config)
        # Only 2 results (need >= 3)
        for i in range(2):
            result = self._make_result(success=False)
            evaluator.record_result(result)
        self.assertFalse(evaluator.should_trigger(result))

    def test_trigger_scheduled(self):
        config = TriggerConfig(
            every_task=False, enable_every_task=False,
            enable_accumulated=False,
            enable_performance=False,
            scheduled_interval_seconds=0.0, enable_scheduled=True,
        )
        evaluator = TriggerEvaluator(config)
        result = self._make_result()
        evaluator.record_result(result)
        # With interval 0, should always trigger
        self.assertTrue(evaluator.should_trigger(result))
        self.assertEqual(evaluator.triggered_by, TriggerType.SCHEDULED)

    def test_trigger_scheduled_not_triggered(self):
        config = TriggerConfig(
            every_task=False, enable_every_task=False,
            enable_accumulated=False,
            enable_performance=False,
            scheduled_interval_seconds=999999.0, enable_scheduled=True,
        )
        evaluator = TriggerEvaluator(config)
        # Mark evolved to set last_evolve_time
        evaluator._last_evolve_time = time.time()
        result = self._make_result()
        evaluator.record_result(result)
        self.assertFalse(evaluator.should_trigger(result))

    def test_mark_evolved(self):
        evaluator = TriggerEvaluator(
            TriggerConfig(every_task=False, enable_every_task=False)
        )
        sig = "test_sig"
        for i in range(5):
            evaluator.record_result(self._make_result(sig=sig))
        evaluator.mark_evolved(sig)
        self.assertGreater(evaluator._last_evolve_time, 0)

    def test_reset(self):
        evaluator = TriggerEvaluator()
        evaluator.record_result(self._make_result())
        evaluator.reset()
        self.assertEqual(evaluator.task_count, 0)
        self.assertAlmostEqual(evaluator.recent_success_rate, 0.0)
        self.assertIsNone(evaluator.triggered_by)

    def test_recent_success_rate(self):
        evaluator = TriggerEvaluator(
            TriggerConfig(every_task=False, enable_every_task=False)
        )
        evaluator.record_result(self._make_result(success=True))
        evaluator.record_result(self._make_result(success=False))
        evaluator.record_result(self._make_result(success=True))
        self.assertAlmostEqual(evaluator.recent_success_rate, 2.0 / 3.0)


# ═══════════════════════════════════════════════════════════════
#  TaskLoop Tests
# ═══════════════════════════════════════════════════════════════


class TestTaskLoop(unittest.TestCase):
    """Tests for TaskLoop."""

    def setUp(self):
        self.backend = SQLiteBackend(":memory:")
        self.store = LoopTemplateStore(self.backend)
        # Save default templates
        for t in DefaultTemplates.all_defaults():
            self.store.save_template(t)

    def test_init_default(self):
        loop = TaskLoop()
        self.assertIsNotNone(loop.template_store)
        self.assertIsNone(loop.agent_loop)

    def test_init_with_store(self):
        loop = TaskLoop(template_store=self.store)
        self.assertIs(loop.template_store, self.store)

    async def test_run_simulated(self):
        loop = TaskLoop(template_store=self.store)
        result = await loop.run("search for cats")
        self.assertIsInstance(result, TaskResult)
        self.assertEqual(result.task, "search for cats")
        self.assertTrue(result.success)
        self.assertTrue(result.content)
        self.assertGreater(result.iterations, 0)
        self.assertGreater(result.execution_log.entry_count, 0)

    async def test_run_produces_execution_log(self):
        loop = TaskLoop(template_store=self.store)
        result = await loop.run("analyze data")
        log = result.execution_log
        self.assertGreater(log.entry_count, 0)
        self.assertTrue(log.phases_executed)
        self.assertTrue(log.started_at)
        self.assertTrue(log.completed_at)

    async def test_run_uses_template(self):
        loop = TaskLoop(template_store=self.store)
        result = await loop.run("test task")
        self.assertIsNotNone(result.template_used)
        self.assertTrue(result.template_id)

    async def test_run_falls_back_to_default(self):
        empty_store = LoopTemplateStore(SQLiteBackend(":memory:"))
        loop = TaskLoop(template_store=empty_store)
        result = await loop.run("unknown task")
        self.assertIsNotNone(result.template_used)

    async def test_run_with_custom_default_template(self):
        empty_store = LoopTemplateStore(SQLiteBackend(":memory:"))
        custom = DefaultTemplates.reflective()
        loop = TaskLoop(
            template_store=empty_store,
            default_template=custom,
        )
        result = await loop.run("reflective task")
        self.assertEqual(result.template_id, custom.id)

    async def test_run_assesses_quality(self):
        loop = TaskLoop(template_store=self.store)
        result = await loop.run("quality test")
        self.assertIsNotNone(result.quality)
        self.assertIsInstance(result.quality, QualityScore)
        self.assertGreater(result.quality.confidence, 0)

    async def test_run_with_agent_loop(self):
        mock_llm = MockLLM([
            LLMResponse.text("Thinking about the task..."),
        ])
        agent = AgentLoop(llm=mock_llm)
        loop = TaskLoop(template_store=self.store, agent_loop=agent)
        result = await loop.run("agent test")
        self.assertIsInstance(result, TaskResult)
        self.assertTrue(result.success)

    async def test_run_with_agent_loop_template_mode(self):
        mock_llm = MockLLM([
            LLMResponse.text("Observing..."),
            LLMResponse.text("Planning..."),
            LLMResponse.text("Done!"),
        ])
        agent = AgentLoop(llm=mock_llm)
        loop = TaskLoop(template_store=self.store, agent_loop=agent)
        result = await loop.run("template test")
        self.assertIsInstance(result, TaskResult)
        self.assertGreater(result.execution_log.entry_count, 0)

    async def test_run_records_task_signature(self):
        loop = TaskLoop(template_store=self.store)
        result = await loop.run("signature test task")
        self.assertTrue(result.task_signature)

    async def test_run_related_memories(self):
        loop = TaskLoop(template_store=self.store, track_related_memories=True)
        result = await loop.run("memory test")
        self.assertIsInstance(result.related_memories, list)

    def test_repr(self):
        loop = TaskLoop(template_store=self.store)
        r = repr(loop)
        self.assertIn("TaskLoop", r)


# ═══════════════════════════════════════════════════════════════
#  EvolutionLoop Tests
# ═══════════════════════════════════════════════════════════════


class TestEvolutionLoop(unittest.TestCase):
    """Tests for EvolutionLoop."""

    def setUp(self):
        self.backend = SQLiteBackend(":memory:")
        self.store = LoopTemplateStore(self.backend)
        for t in DefaultTemplates.all_defaults():
            self.store.save_template(t)
        self.evolution = EvolutionLoop(template_store=self.store)

    def _make_task_result(self, success=True, template=None):
        if template is None:
            template = DefaultTemplates.standard_react()
        return TaskResult(
            task="test task",
            template_id=template.id,
            template_used=template,
            execution_log=ExecutionLog(
                entries=[ExecutionLogEntry(phase_name="execute", duration=0.1)]
            ),
            quality=QualityScore(
                source=SourceQuality.B,
                result=ResultQuality.TRUSTED if success else ResultQuality.FAILED,
                confidence=0.7,
            ),
            success=success,
            content="Done" if success else "",
            iterations=3,
            token_cost=100.0,
            errors=[] if success else ["some error"],
            task_signature="test task",
        )

    def test_init_default(self):
        loop = EvolutionLoop()
        self.assertIsNotNone(loop.template_store)
        self.assertIsNotNone(loop.strategy_evolver)
        self.assertIsNotNone(loop.ab_test_framework)
        self.assertIsNotNone(loop.forgetting_engine)
        self.assertEqual(loop.evolution_count, 0)

    def test_init_with_store(self):
        loop = EvolutionLoop(template_store=self.store)
        self.assertIs(loop.template_store, self.store)

    def test_evolve_success(self):
        result = self._make_task_result(success=True)
        variant = self.evolution.evolve(result)
        self.assertEqual(self.evolution.evolution_count, 1)
        self.assertIsNotNone(result.reflection)

    def test_evolve_sets_reflection(self):
        result = self._make_task_result(success=True)
        self.evolution.evolve(result)
        self.assertIsNotNone(result.reflection)
        self.assertIsInstance(result.reflection, ProcessReflection)

    def test_evolve_failure_triggers_mutation(self):
        result = self._make_task_result(success=False)
        variant = self.evolution.evolve(result)
        self.assertEqual(self.evolution.evolution_count, 1)

    def test_evolve_no_template_returns_none(self):
        result = TaskResult(task="no template", template_id="nonexistent")
        variant = self.evolution.evolve(result)
        self.assertIsNone(variant)

    def test_evolve_updates_template_stats(self):
        template = DefaultTemplates.standard_react()
        self.store.save_template(template)
        result = self._make_task_result(success=True, template=template)
        self.evolution.evolve(result)
        # Stats should be updated (no exception means success)
        updated = self.store.get_template(template.id)
        self.assertIsNotNone(updated)

    def test_evolve_registers_anti_pattern_on_failure(self):
        result = self._make_task_result(success=False)
        self.evolution.evolve(result)
        # Anti-pattern should be registered
        is_known = self.evolution.anti_pattern_store.check_task("test task")
        self.assertTrue(is_known)

    def test_evolve_updates_memory_quality(self):
        result = self._make_task_result(success=True)
        result.related_memories = ["mem1", "mem2"]
        self.evolution.evolve(result)
        # No exception means success

    def test_build_execution_result(self):
        template = DefaultTemplates.standard_react()
        result = self._make_task_result(success=True, template=template)
        exec_result = self.evolution._build_execution_result(result, template)
        self.assertIsInstance(exec_result, ExecutionResult)
        self.assertTrue(exec_result.success)
        self.assertEqual(exec_result.iterations, 3)

    def test_create_experiment(self):
        control = DefaultTemplates.standard_react()
        variant = DefaultTemplates.reflective()
        self.store.save_template(control)
        self.store.save_template(variant)
        exp = self.evolution.create_experiment(
            "test-exp", control, variant, min_samples=3
        )
        self.assertIsNotNone(exp)

    def test_record_experiment_result(self):
        control = DefaultTemplates.standard_react()
        variant = DefaultTemplates.reflective()
        self.store.save_template(control)
        self.store.save_template(variant)
        exp = self.evolution.create_experiment(
            "test-exp2", control, variant, min_samples=2
        )
        self.evolution.record_experiment_result(
            exp.id, control.id, True, 3, 50.0
        )
        # No exception means success

    def test_last_reflection_property(self):
        result = self._make_task_result(success=True)
        self.evolution.evolve(result)
        self.assertIsNotNone(self.evolution.last_reflection)

    def test_repr(self):
        r = repr(self.evolution)
        self.assertIn("EvolutionLoop", r)


# ═══════════════════════════════════════════════════════════════
#  BilevelLoop Tests
# ═══════════════════════════════════════════════════════════════


class TestBilevelLoop(unittest.TestCase):
    """Tests for BilevelLoop."""

    def setUp(self):
        self.backend = SQLiteBackend(":memory:")
        self.store = LoopTemplateStore(self.backend)
        for t in DefaultTemplates.all_defaults():
            self.store.save_template(t)

    def test_init_default(self):
        loop = BilevelLoop()
        self.assertIsNotNone(loop.task_loop)
        self.assertIsNotNone(loop.evolution_loop)
        self.assertEqual(loop.result_count, 0)
        self.assertEqual(loop.evolution_count, 0)

    def test_init_with_components(self):
        task_loop = TaskLoop(template_store=self.store)
        evolution_loop = EvolutionLoop(template_store=self.store)
        loop = BilevelLoop(
            task_loop=task_loop,
            evolution_loop=evolution_loop,
        )
        self.assertIs(loop.task_loop, task_loop)
        self.assertIs(loop.evolution_loop, evolution_loop)

    async def test_run_single_task(self):
        loop = BilevelLoop(
            task_loop=TaskLoop(template_store=self.store),
            evolution_loop=EvolutionLoop(template_store=self.store),
        )
        result = await loop.run("test task")
        self.assertIsInstance(result, TaskResult)
        self.assertEqual(loop.result_count, 1)
        self.assertGreater(loop.evolution_count, 0)

    async def test_run_with_every_task_trigger(self):
        config = TriggerConfig(every_task=True, enable_every_task=True)
        loop = BilevelLoop(
            task_loop=TaskLoop(template_store=self.store),
            evolution_loop=EvolutionLoop(template_store=self.store),
            trigger_config=config,
        )
        await loop.run("task 1")
        self.assertEqual(loop.evolution_count, 1)

    async def test_run_without_trigger(self):
        config = TriggerConfig(
            every_task=False, enable_every_task=False,
            enable_accumulated=False,
            enable_performance=False,
            enable_scheduled=False,
        )
        loop = BilevelLoop(
            task_loop=TaskLoop(template_store=self.store),
            evolution_loop=EvolutionLoop(template_store=self.store),
            trigger_config=config,
        )
        await loop.run("no trigger task")
        self.assertEqual(loop.evolution_count, 0)

    async def test_run_batch(self):
        loop = BilevelLoop(
            task_loop=TaskLoop(template_store=self.store),
            evolution_loop=EvolutionLoop(template_store=self.store),
        )
        results = await loop.run_batch(["task1", "task2", "task3"])
        self.assertEqual(len(results), 3)
        self.assertEqual(loop.result_count, 3)

    async def test_success_rate(self):
        loop = BilevelLoop(
            task_loop=TaskLoop(template_store=self.store),
            evolution_loop=EvolutionLoop(template_store=self.store),
        )
        await loop.run("task1")
        rate = loop.success_rate
        self.assertGreater(rate, 0.0)

    async def test_last_result(self):
        loop = BilevelLoop(
            task_loop=TaskLoop(template_store=self.store),
            evolution_loop=EvolutionLoop(template_store=self.store),
        )
        self.assertIsNone(loop.last_result)
        await loop.run("last task")
        self.assertIsNotNone(loop.last_result)
        self.assertEqual(loop.last_result.task, "last task")

    async def test_reset(self):
        loop = BilevelLoop(
            task_loop=TaskLoop(template_store=self.store),
            evolution_loop=EvolutionLoop(template_store=self.store),
        )
        await loop.run("task1")
        loop.reset()
        self.assertEqual(loop.result_count, 0)
        self.assertEqual(loop.evolution_count, 0)

    def test_repr(self):
        loop = BilevelLoop()
        r = repr(loop)
        self.assertIn("BilevelLoop", r)


# ═══════════════════════════════════════════════════════════════
#  AgentLoop Template-Driven Mode Tests
# ═══════════════════════════════════════════════════════════════


class TestAgentLoopTemplateMode(unittest.TestCase):
    """Tests for AgentLoop's template-driven mode (Phase 16)."""

    async def test_backward_compatible_no_template(self):
        """AgentLoop without template works exactly as before."""
        mock = MockLLM([LLMResponse.text("Hello!")])
        loop = AgentLoop(llm=mock)
        self.assertIsNone(loop.template)
        result = await loop.run("Hi")
        self.assertEqual(result.content, "Hello!")
        self.assertEqual(result.stop_reason, "natural")

    async def test_backward_compatible_with_tools(self):
        """AgentLoop with tools but no template works as before."""
        def search_func(query=""):
            return f"Results for: {query}"

        tool = FunctionTool("search", "Search", search_func)
        mock = MockLLM([
            LLMResponse.action("search", {"query": "cats"}),
            LLMResponse.text("Found cats!"),
        ])
        loop = AgentLoop(llm=mock, tools=[tool])
        result = await loop.run("Search for cats")
        self.assertEqual(result.content, "Found cats!")
        self.assertTrue(result.is_complete)

    async def test_template_in_init(self):
        """Template set in __init__ is used by run()."""
        mock = MockLLM([
            LLMResponse.text("Observing..."),
            LLMResponse.text("Planning..."),
            LLMResponse.text("Done!"),
        ])
        template = DefaultTemplates.standard_react()
        loop = AgentLoop(llm=mock, template=template)
        self.assertIsNotNone(loop.template)
        result = await loop.run("Test")
        self.assertTrue(result.is_complete)

    async def test_template_in_run(self):
        """Template passed to run() overrides __init__ template."""
        mock = MockLLM([
            LLMResponse.text("Plan..."),
            LLMResponse.text("Execute..."),
            LLMResponse.text("Verify..."),
        ])
        loop = AgentLoop(llm=mock)
        template = DefaultTemplates.plan_execute()
        result = await loop.run("Test", template=template)
        self.assertTrue(result.is_complete)

    async def test_run_with_template_method(self):
        """run_with_template convenience method works."""
        mock = MockLLM([
            LLMResponse.text("Perceiving..."),
            LLMResponse.text("Planning..."),
            LLMResponse.text("Done!"),
        ])
        loop = AgentLoop(llm=mock)
        template = DefaultTemplates.standard_react()
        result = await loop.run_with_template("Test", template)
        self.assertIsInstance(result, LoopResult)
        self.assertTrue(result.is_complete)

    async def test_template_driven_executes_phases(self):
        """Template-driven mode calls LLM for each phase."""
        mock = MockLLM([
            LLMResponse.text("Phase 1 done"),
            LLMResponse.text("Phase 2 done"),
            LLMResponse.text("Phase 3 done"),
        ])
        template = DefaultTemplates.standard_react()
        loop = AgentLoop(llm=mock)
        result = await loop.run_with_template("test", template)
        self.assertTrue(result.is_complete)
        self.assertGreaterEqual(mock.calls_made, 1)

    async def test_template_driven_budget_exhaustion(self):
        """Template-driven mode respects budget."""
        mock = MockLLM([
            LLMResponse.text("response 1", tokens=10000),
        ] * 100)
        budget = BudgetTracker(BudgetConfig(max_turns=1))
        template = DefaultTemplates.standard_react()
        loop = AgentLoop(llm=mock, budget_tracker=budget)
        result = await loop.run_with_template("test", template)
        # Budget exhausted after first phase records a turn;
        # inter-phase budget check catches it before the next phase.
        self.assertTrue(result.partial or result.stop_reason == "budget_exhausted")

    async def test_template_driven_interrupt(self):
        """Template-driven mode respects interrupt via middleware."""
        class InterruptMiddleware(Middleware):
            def __init__(self):
                self._call_count = 0

            async def before_llm_call(self, state):
                self._call_count += 1
                if self._call_count >= 1:
                    state.should_stop = True
                    state.stop_reason = "Interrupted by middleware"
                return state

        mock = MockLLM([
            LLMResponse.text("response 1"),
        ] * 100)
        template = DefaultTemplates.standard_react()
        loop = AgentLoop(
            llm=mock,
            middleware_chain=[InterruptMiddleware()],
        )
        result = await loop.run_with_template("test", template)
        self.assertTrue(result.partial or result.stop_reason == "middleware")

    async def test_template_with_empty_phases_falls_back(self):
        """Template with no phases falls back to standard loop."""
        mock = MockLLM([LLMResponse.text("Done!")])
        empty_template = LoopTemplate(
            id="empty-template",
            phases=[],
            max_iterations=1,
        )
        loop = AgentLoop(llm=mock)
        result = await loop.run_with_template("test", empty_template)
        self.assertTrue(result.is_complete)

    def test_build_phase_prompt(self):
        """Phase prompt builder produces correct content."""
        prompt = AgentLoop._build_phase_prompt(
            "execute", "Run search", "Base system prompt"
        )
        self.assertIn("EXECUTE", prompt)
        self.assertIn("Base system prompt", prompt)
        self.assertIn("Run search", prompt)

    def test_build_phase_prompt_unknown_phase(self):
        """Unknown phase name uses generic description."""
        prompt = AgentLoop._build_phase_prompt(
            "custom", "Do something", "base"
        )
        self.assertIn("CUSTOM", prompt)


# ═══════════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestBilevelIntegration(unittest.TestCase):
    """End-to-end integration tests for the bilevel loop."""

    def setUp(self):
        self.backend = SQLiteBackend(":memory:")
        self.store = LoopTemplateStore(self.backend)
        for t in DefaultTemplates.all_defaults():
            self.store.save_template(t)

    async def test_full_pipeline_success(self):
        """Full pipeline: task → execute → reflect → evolve → return."""
        task_loop = TaskLoop(template_store=self.store)
        evolution_loop = EvolutionLoop(template_store=self.store)
        loop = BilevelLoop(
            task_loop=task_loop,
            evolution_loop=evolution_loop,
        )
        result = await loop.run("analyze data and report")
        self.assertTrue(result.success)
        self.assertIsNotNone(result.template_used)
        self.assertGreater(result.execution_log.entry_count, 0)
        self.assertIsNotNone(result.reflection)
        self.assertGreater(loop.evolution_count, 0)

    def test_full_pipeline_failure(self):
        """Full pipeline handles task failure gracefully."""
        task_loop = TaskLoop(template_store=self.store)
        evolution_loop = EvolutionLoop(template_store=self.store)
        loop = BilevelLoop(
            task_loop=task_loop,
            evolution_loop=evolution_loop,
        )
        # Create a failing task result manually
        template = DefaultTemplates.standard_react()
        failing_result = TaskResult(
            task="failing task",
            template_id=template.id,
            template_used=template,
            execution_log=ExecutionLog(
                entries=[ExecutionLogEntry(
                    phase_name="execute",
                    errors=["execution failed"],
                )]
            ),
            quality=QualityScore(
                source=SourceQuality.C,
                result=ResultQuality.FAILED,
                confidence=0.2,
            ),
            success=False,
            content="",
            iterations=5,
            token_cost=200.0,
            errors=["task failed"],
            task_signature="failing task",
        )
        # Evolve the failing result
        variant = evolution_loop.evolve(failing_result)
        self.assertEqual(evolution_loop.evolution_count, 1)
        # Anti-pattern should be registered
        self.assertTrue(
            evolution_loop.anti_pattern_store.check_task("failing task")
        )

    async def test_batch_with_mixed_results(self):
        """Batch processing with mixed success/failure."""
        loop = BilevelLoop(
            task_loop=TaskLoop(template_store=self.store),
            evolution_loop=EvolutionLoop(template_store=self.store),
        )
        results = await loop.run_batch([
            "task 1",
            "task 2",
            "task 3",
        ])
        self.assertEqual(len(results), 3)
        self.assertGreater(loop.success_rate, 0.0)

    async def test_accumulated_trigger_evolution(self):
        """ACCUMULATED_N trigger fires after N same-signature tasks."""
        config = TriggerConfig(
            every_task=False, enable_every_task=False,
            accumulated_n=2, enable_accumulated=True,
            enable_performance=False, enable_scheduled=False,
        )
        loop = BilevelLoop(
            task_loop=TaskLoop(template_store=self.store),
            evolution_loop=EvolutionLoop(template_store=self.store),
            trigger_config=config,
        )
        # Use the same task description so signatures match
        await loop.run("same task")
        self.assertEqual(loop.evolution_count, 0)
        await loop.run("same task")
        self.assertGreater(loop.evolution_count, 0)

    def test_serialisation_roundtrip(self):
        """TaskResult serialisation roundtrip preserves data."""
        template = DefaultTemplates.standard_react()
        log = ExecutionLog()
        log.add_entry(ExecutionLogEntry(
            phase_name="execute",
            action="test action",
            tools_used=["tool1"],
            duration=0.5,
            result="test result",
            errors=[],
            iteration=0,
            step_index=0,
        ))
        log.finalize()
        quality = QualityScore(
            source=SourceQuality.A,
            result=ResultQuality.TRUSTED,
            confidence=0.85,
            evidence_count=3,
        )
        original = TaskResult(
            task="serialisation test",
            template_id=template.id,
            template_used=template,
            execution_log=log,
            quality=quality,
            related_memories=["mem1", "mem2"],
            success=True,
            content="Test output",
            iterations=3,
            token_cost=150.0,
            errors=[],
            task_signature="serialisation test",
        )
        d = original.to_dict()
        json_str = json.dumps(d)  # Must be JSON-serialisable
        restored = TaskResult.from_dict(json.loads(json_str))
        self.assertEqual(restored.task, original.task)
        self.assertEqual(restored.template_id, original.template_id)
        self.assertTrue(restored.success)
        self.assertEqual(restored.iterations, original.iterations)
        self.assertEqual(restored.execution_log.entry_count, 1)
        self.assertEqual(restored.quality.source, SourceQuality.A)
        self.assertEqual(restored.quality.result, ResultQuality.TRUSTED)


if __name__ == "__main__":
    unittest.main()
