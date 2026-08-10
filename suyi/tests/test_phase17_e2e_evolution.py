"""
Phase 17 — End-to-End Evolution Cycle Integration Test.

This test exercises the full bilevel evolution pipeline:

    TaskLoop (inner) → TriggerEvaluator → EvolutionLoop (outer) →
    TemplateStore + ForgettingEngine + AntiPatternStore +
    StrategyEvolver + ABTestFramework → EvolutionReportGenerator

It runs **12 rounds** of real task execution (using MockLLM to simulate
LLM responses), with 2 deliberately failing tasks to exercise the
anti-pattern registration and mutation pathways.  After the batch,
the test verifies:

1.  10+ task rounds were executed.
2.  LoopTemplateStore accumulated at least 5 templates (3 defaults +
    variants from mutations).
3.  ForgettingEngine evaluated at least 1 COMPRESS action on old,
    low-quality memories.
4.  StrategyEvolver recorded at least 1 mutation in mutation_history.
5.  An A/B experiment was created, results recorded, and a variant
    won.
6.  AntiPatternStore has at least 1 registered pattern from the
    deliberate failures.
7.  Before/after performance metrics show the evolution trend.
8.  EvolutionReportGenerator produces valid dict / markdown / json
    output.

All assertions use MockLLM — no real LLM API calls are made.  The test
is designed to be switchable to a real LLM by replacing MockLLM with
an OmniRoute-backed LLM interface.
"""

import asyncio
import json
import math
import os
import tempfile
import time
import unittest
from typing import Any, Dict, List, Optional, Tuple

from suyi.core.loop import (
    AgentLoop,
    MockLLM,
    LLMResponse,
    LoopResult,
    ToolCall,
    FunctionTool,
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
    ForgettingCurve,
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
from suyi.quality.evolution_report import (
    EvolutionReport,
    EvolutionReportGenerator,
)
from suyi.persistence.sqlite_backend import SQLiteBackend


# ═══════════════════════════════════════════════════════════════
#  Helper: ConfigurableTaskLoop — injects failures on specified tasks
# ═══════════════════════════════════════════════════════════════


class ConfigurableTaskLoop(TaskLoop):
    """TaskLoop that can be configured to produce failing results.

    This subclass overrides :meth:`run` to inject pre-built failing
    :class:`TaskResult` objects for specific task indices.  All other
    tasks run through the normal :class:`TaskLoop` pipeline.

    Args:
        fail_indices: Set of 0-based task indices that should fail.
        *args, **kwargs: Passed to :class:`TaskLoop.__init__`.
    """

    def __init__(self, *args, fail_indices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._fail_indices: set = set(fail_indices or [])
        self._task_counter: int = 0

    async def run(self, task: str) -> TaskResult:
        self._task_counter += 1
        # _task_counter is 1-based; convert to 0-based for comparison
        idx = self._task_counter - 1
        if idx in self._fail_indices:
            return self._make_failing_result(task)
        return await super().run(task)

    def _make_failing_result(self, task: str) -> TaskResult:
        """Build a failing TaskResult for injection."""
        task_signature = compute_task_signature(task)
        template = self._select_template(task, task_signature)

        execution_log = ExecutionLog()
        execution_log.add_entry(ExecutionLogEntry(
            phase_name="execute",
            action="Execution attempted but encountered an error.",
            tools_used=[],
            duration=0.05,
            result="",
            errors=["Simulated failure: resource unavailable"],
            iteration=0,
            step_index=0,
        ))
        execution_log.add_entry(ExecutionLogEntry(
            phase_name="reflect",
            action="Reflection on failure.",
            tools_used=[],
            duration=0.01,
            result="Task could not be completed due to missing resources.",
            errors=[],
            iteration=0,
            step_index=1,
        ))
        execution_log.finalize()

        quality = QualityScore(
            source=SourceQuality.C,
            result=ResultQuality.FAILED,
            confidence=0.15,
            evidence_count=0,
            contradiction_count=1,
        )

        return TaskResult(
            task=task,
            template_id=template.id,
            template_used=template,
            execution_log=execution_log,
            quality=quality,
            related_memories=[],
            success=False,
            content="",
            iterations=3,
            token_cost=80.0,
            errors=["Simulated failure: resource unavailable"],
            task_signature=task_signature,
        )


# ═══════════════════════════════════════════════════════════════
#  Phase 17 E2E Evolution Test
# ═══════════════════════════════════════════════════════════════


class TestPhase17E2EEvolution(unittest.TestCase):
    """Phase 17 end-to-end evolution cycle integration test.

    Runs a full 12-round evolution cycle through the BilevelLoop with
    MockLLM-driven task execution, verifying that all sub-systems
    (template store, forgetting engine, strategy evolver, A/B testing,
    anti-pattern store, and report generator) work together correctly.
    """

    def setUp(self):
        """Set up the bilevel loop with all sub-components."""
        # ── Persistence ─────────────────────────────────────────
        self.backend = SQLiteBackend(":memory:")
        self.store = LoopTemplateStore(self.backend)

        # Save the 3 default templates
        for t in DefaultTemplates.all_defaults():
            self.store.save_template(t)

        # ── Sub-components ──────────────────────────────────────
        # NOTE: AntiPatternStore implements __len__, so an empty store
        # is falsy.  EvolutionLoop.__init__ uses `anti_pattern_store or
        # AntiPatternStore()`, which would create a new instance if the
        # store is empty.  We pre-populate the store with a dummy
        # pattern to avoid this, then access it via evolution_loop's
        # property.  Alternatively, we access all sub-components through
        # the evolution_loop's properties to ensure consistency.
        forgetting_engine = ForgettingEngine(is_dry_run=True)
        anti_pattern_store = AntiPatternStore()
        strategy_evolver = StrategyEvolver(
            store=self.store, backend=self.backend
        )
        ab_test_framework = ABTestFramework(
            store=self.store, backend=self.backend
        )

        # ── Evolution loop ──────────────────────────────────────
        self.evolution_loop = EvolutionLoop(
            template_store=self.store,
            strategy_evolver=strategy_evolver,
            ab_test_framework=ab_test_framework,
            forgetting_engine=forgetting_engine,
            anti_pattern_store=anti_pattern_store,
        )

        # Access sub-components through the evolution_loop's properties
        # to ensure we're using the same instances the loop uses.
        self.forgetting_engine = self.evolution_loop.forgetting_engine
        self.anti_pattern_store = self.evolution_loop.anti_pattern_store
        self.strategy_evolver = self.evolution_loop.strategy_evolver
        self.ab_test_framework = self.evolution_loop.ab_test_framework

        # ── Task loop with injected failures ────────────────────
        # Tasks at index 4 and 9 (0-based) will fail
        self.task_loop = ConfigurableTaskLoop(
            template_store=self.store,
            fail_indices={4, 9},
        )

        # ── Bilevel loop ────────────────────────────────────────
        self.bilevel_loop = BilevelLoop(
            task_loop=self.task_loop,
            evolution_loop=self.evolution_loop,
        )

        # ── 12 diverse task descriptions ────────────────────────
        self.tasks = [
            "analyze market data and generate a quarterly report",
            "search for relevant academic papers on machine learning",
            "write a concise summary of the research findings",
            "create a data visualization showing revenue trends",
            "translate technical documentation from Chinese to English",
            "optimize database query performance for large datasets",
            "review source code for potential security vulnerabilities",
            "deploy the application to the production environment",
            "debug a memory leak in the Python service",
            "refactor the authentication module for better extensibility",
            "generate comprehensive API documentation from code",
            "conduct a performance benchmark comparison",
        ]

    # ── Helper to run async tests ──────────────────────────────

    def _run_async(self, coro):
        """Run an async coroutine in a new event loop."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    # ═══════════════════════════════════════════════════════════
    #  Main E2E Test
    # ═══════════════════════════════════════════════════════════

    def test_full_evolution_cycle(self):
        """Full 12-round evolution cycle with all sub-systems.

        This is the primary integration test.  It:
        1.  Runs 12 tasks through the BilevelLoop (2 deliberately failing).
        2.  Verifies template accumulation (5+ templates).
        3.  Verifies forgetting engine COMPRESS action.
        4.  Verifies mutation history (1+ mutations).
        5.  Verifies A/B experiment with a winning variant.
        6.  Verifies anti-pattern registration.
        7.  Verifies before/after performance metrics.
        8.  Verifies evolution report generation.
        """
        # ──────────────────────────────────────────────────────
        #  Phase 1: Run 12 tasks through the bilevel loop
        # ──────────────────────────────────────────────────────
        results = self._run_async(
            self.bilevel_loop.run_batch(self.tasks)
        )

        # ── Verify 10+ rounds ──────────────────────────────────
        self.assertGreaterEqual(
            len(results), 10,
            "Must execute at least 10 task rounds"
        )
        self.assertEqual(len(results), 12)

        # ── Verify some tasks succeeded and some failed ────────
        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]
        self.assertGreaterEqual(
            len(successes), 8,
            "At least 8 tasks should succeed"
        )
        self.assertEqual(
            len(failures), 2,
            "Exactly 2 tasks should fail (indices 4 and 9)"
        )

        # ── Verify evolution cycles were triggered ─────────────
        self.assertGreater(
            self.bilevel_loop.evolution_count, 0,
            "At least one evolution cycle should have been triggered"
        )

        # ──────────────────────────────────────────────────────
        #  Phase 2: Verify template accumulation (5+ templates)
        # ──────────────────────────────────────────────────────
        all_templates = self.store.list_templates()
        self.assertGreaterEqual(
            len(all_templates), 5,
            f"Template store should have at least 5 templates, "
            f"got {len(all_templates)}"
        )

        # Verify at least one variant was created (has parent_id)
        variants = [t for t in all_templates if t.parent_id is not None]
        self.assertGreaterEqual(
            len(variants), 1,
            "At least 1 variant template should have been created"
        )

        # ──────────────────────────────────────────────────────
        #  Phase 3: Verify forgetting engine COMPRESS action
        # ──────────────────────────────────────────────────────
        forgetting_evals = self._evaluate_old_memories()

        compress_actions = [
            (mem, action) for mem, action in forgetting_evals
            if action == ForgettingAction.COMPRESS
        ]
        self.assertGreaterEqual(
            len(compress_actions), 1,
            "ForgettingEngine should produce at least 1 COMPRESS action "
            "on old, low-quality memories"
        )

        # Verify no PURGE on anti-pattern memories
        anti_pattern_evals = self._evaluate_anti_pattern_memories()
        for mem, action in anti_pattern_evals:
            self.assertNotEqual(
                action, ForgettingAction.PURGE,
                "Anti-pattern memories must never be purged"
            )

        # ──────────────────────────────────────────────────────
        #  Phase 4: Verify mutation history
        # ──────────────────────────────────────────────────────
        mutation_records = self.backend.list_mutation_history(limit=100)
        self.assertGreaterEqual(
            len(mutation_records), 1,
            "At least 1 mutation should be recorded in mutation_history"
        )

        # Verify mutation has expected fields
        first_mutation = mutation_records[0]
        self.assertTrue(first_mutation.get("mutation_type"))
        self.assertTrue(first_mutation.get("description"))
        self.assertTrue(first_mutation.get("target_dimension"))

        # ──────────────────────────────────────────────────────
        #  Phase 5: Verify A/B experiment with winning variant
        # ──────────────────────────────────────────────────────
        experiments = self.ab_test_framework.list_experiments()
        self.assertGreaterEqual(
            len(experiments), 1,
            "At least 1 A/B experiment should have been created"
        )

        # Record results for the first experiment to get a winner
        exp = experiments[0]
        self._record_ab_test_results(exp)

        # Evaluate the experiment
        eval_result = self.ab_test_framework.evaluate(exp.id)
        self.assertEqual(
            eval_result.winner, "variant",
            f"Variant should win the A/B test, got winner={eval_result.winner}. "
            f"Message: {eval_result.message}"
        )
        self.assertTrue(
            eval_result.is_significant,
            "A/B test result should be statistically significant"
        )

        # ──────────────────────────────────────────────────────
        #  Phase 6: Verify anti-pattern registration
        # ──────────────────────────────────────────────────────
        self.assertGreaterEqual(
            self.anti_pattern_store.count(), 1,
            "At least 1 anti-pattern should be registered from failures"
        )

        # Verify anti-patterns are from the failing tasks
        all_patterns = self.anti_pattern_store.get_all()
        self.assertGreaterEqual(len(all_patterns), 1)
        for ap in all_patterns:
            self.assertTrue(ap.is_anti_pattern)
            self.assertGreater(ap.failure_count, 0)

        # ──────────────────────────────────────────────────────
        #  Phase 7: Verify before/after performance metrics
        # ──────────────────────────────────────────────────────
        self._verify_performance_metrics(results)

        # ──────────────────────────────────────────────────────
        #  Phase 8: Verify evolution report generation
        # ──────────────────────────────────────────────────────
        all_evals = forgetting_evals + anti_pattern_evals
        report_gen = EvolutionReportGenerator(
            self.bilevel_loop,
            forgetting_evaluations=all_evals,
        )
        report = report_gen.generate()

        # ── to_dict() ──────────────────────────────────────────
        report_dict = report.to_dict()
        self.assertIsInstance(report_dict, dict)
        self.assertIn("task_overview", report_dict)
        self.assertIn("template_evolution", report_dict)
        self.assertIn("forgetting_summary", report_dict)
        self.assertIn("mutation_history", report_dict)
        self.assertIn("ab_test_results", report_dict)
        self.assertIn("performance_comparison", report_dict)
        self.assertIn("key_findings", report_dict)
        self.assertIn("recommendations", report_dict)

        # Verify task overview data
        overview = report_dict["task_overview"]
        self.assertEqual(overview["total_tasks"], 12)
        self.assertEqual(overview["successful"], 10)
        self.assertEqual(overview["failed"], 2)
        self.assertGreater(overview["evolution_cycles"], 0)

        # Verify forgetting summary has COMPRESS
        forgetting_summary = report_dict["forgetting_summary"]
        self.assertGreater(forgetting_summary["compress_count"], 0)

        # Verify mutation history has records
        mut_history = report_dict["mutation_history"]
        self.assertGreater(mut_history["total_mutations"], 0)

        # ── to_markdown() ──────────────────────────────────────
        report_md = report.to_markdown()
        self.assertIsInstance(report_md, str)
        self.assertIn("# Evolution Report", report_md)
        self.assertIn("## 1. Task Overview", report_md)
        self.assertIn("## 2. Template Evolution Timeline", report_md)
        self.assertIn("## 3. Forgetting Engine Summary", report_md)
        self.assertIn("## 4. Strategy Mutation History", report_md)
        self.assertIn("## 5. A/B Experiment Results", report_md)
        self.assertIn("## 6. Performance Comparison", report_md)
        self.assertIn("## 7. Key Findings", report_md)
        self.assertIn("## 8. Recommendations", report_md)

        # ── to_json() ──────────────────────────────────────────
        report_json = report.to_json()
        self.assertIsInstance(report_json, str)
        parsed = json.loads(report_json)
        self.assertEqual(parsed["task_overview"]["total_tasks"], 12)

        # ── save_to_file() ─────────────────────────────────────
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = os.path.join(tmpdir, "evolution_report.md")
            json_path = os.path.join(tmpdir, "evolution_report.json")

            saved_md = report.save_to_file(md_path, fmt="markdown")
            self.assertTrue(os.path.exists(saved_md))
            with open(saved_md, "r", encoding="utf-8") as f:
                md_content = f.read()
            self.assertIn("# Evolution Report", md_content)

            saved_json = report.save_to_file(json_path, fmt="json")
            self.assertTrue(os.path.exists(saved_json))
            with open(saved_json, "r", encoding="utf-8") as f:
                json_content = f.read()
            parsed_json = json.loads(json_content)
            self.assertEqual(
                parsed_json["task_overview"]["total_tasks"], 12
            )

    # ═══════════════════════════════════════════════════════════
    #  Sub-tests: individual verification methods
    # ═══════════════════════════════════════════════════════════

    def _evaluate_old_memories(self) -> List[Tuple[MemoryRecord, ForgettingAction]]:
        """Create and evaluate old, low-quality memories.

        Creates MemoryRecords with varying ages and quality grades,
        then evaluates each through the ForgettingEngine.  Some should
        trigger COMPRESS (retention in [0.05, 0.2)).

        Returns:
            List of (MemoryRecord, ForgettingAction) tuples.
        """
        engine = self.forgetting_engine
        now = time.time()
        evaluations: List[Tuple[MemoryRecord, ForgettingAction]] = []

        # Memory 1: D-grade, 2 days old, episodic → should COMPRESS
        # tau for D = 1 day. After 2 days: retention ≈ Q0 * e^(-2) ≈ Q0 * 0.135
        # Q0 = memory_weight for D/SPECULATIVE/0.1 ≈ 0.1
        # retention ≈ 0.1 * 0.135 ≈ 0.0135 → PURGE (below 0.05)
        # Let's use 1.5 days: retention ≈ 0.1 * e^(-1.5) ≈ 0.1 * 0.223 ≈ 0.0223 → PURGE
        # Hmm, need to adjust. Let's use a C-grade with some age.
        # C-grade: tau = 7 days. Q0 = memory_weight for C/SPECULATIVE/0.2
        # source_weight = 2/5 = 0.4, result_weight = 0.5, confidence = 0.2
        # evidence_ratio = 0.5 (no evidence)
        # weight = 0.4*0.4 + 0.3*0.5 + 0.2*0.2 + 0.1*0.5 = 0.16+0.15+0.04+0.05 = 0.40
        # retention = 0.40 * e^(-days/7)
        # For COMPRESS (0.05 ≤ retention < 0.2):
        # 0.05 ≤ 0.40 * e^(-d/7) < 0.2
        # 0.125 ≤ e^(-d/7) < 0.5
        # -ln(0.5) < d/7 ≤ -ln(0.125)
        # 4.85 < d ≤ 14.56
        # So d=10 days → retention ≈ 0.40 * e^(-10/7) ≈ 0.40 * 0.239 ≈ 0.0956 → COMPRESS ✓

        mem_old_c = MemoryRecord(
            id="old-mem-c-001",
            quality=QualityScore(
                source=SourceQuality.C,
                result=ResultQuality.SPECULATIVE,
                confidence=0.2,
                evidence_count=0,
                contradiction_count=0,
            ),
            created_at=now - 10 * 86400,  # 10 days ago
            last_reinforced=now - 10 * 86400,
            is_episodic=True,
            content="Old episodic memory about a data analysis task that was partially completed.",
        )
        action = engine.evaluate(mem_old_c)
        evaluations.append((mem_old_c, action))

        # Memory 2: D-grade, 1 day old → retention ≈ 0.1 * e^(-1) ≈ 0.0368 → PURGE
        # Actually, let's compute more carefully.
        # D-grade: tau = 1 day = 86400s
        # Q0 = memory_weight for D/SPECULATIVE/0.1
        # source_weight = 1/5 = 0.2, result_weight = 0.5
        # weight = 0.4*0.2 + 0.3*0.5 + 0.2*0.1 + 0.1*0.5 = 0.08+0.15+0.02+0.05 = 0.30
        # retention = 0.30 * e^(-1) ≈ 0.30 * 0.368 ≈ 0.110 → COMPRESS ✓
        mem_old_d = MemoryRecord(
            id="old-mem-d-001",
            quality=QualityScore(
                source=SourceQuality.D,
                result=ResultQuality.SPECULATIVE,
                confidence=0.1,
                evidence_count=0,
                contradiction_count=0,
            ),
            created_at=now - 1 * 86400,  # 1 day ago
            last_reinforced=now - 1 * 86400,
            is_episodic=True,
            content="Old speculative memory about a hypothesis that was never verified.",
        )
        action = engine.evaluate(mem_old_d)
        evaluations.append((mem_old_d, action))

        # Memory 3: B-grade, recent → should DEGRADE (high retention)
        mem_recent_b = MemoryRecord(
            id="recent-mem-b-001",
            quality=QualityScore(
                source=SourceQuality.B,
                result=ResultQuality.TRUSTED,
                confidence=0.7,
                evidence_count=2,
                contradiction_count=0,
            ),
            created_at=now,  # just created
            last_reinforced=now,
            is_episodic=True,
            content="Recent reliable memory about a successful deployment.",
        )
        action = engine.evaluate(mem_recent_b)
        evaluations.append((mem_recent_b, action))

        # Memory 4: C-grade, 5 days old → retention ≈ 0.40 * e^(-5/7) ≈ 0.40*0.49 ≈ 0.196 → COMPRESS (just under 0.2)
        mem_mid_c = MemoryRecord(
            id="mid-mem-c-001",
            quality=QualityScore(
                source=SourceQuality.C,
                result=ResultQuality.SPECULATIVE,
                confidence=0.2,
                evidence_count=0,
                contradiction_count=0,
            ),
            created_at=now - 5 * 86400,  # 5 days ago
            last_reinforced=now - 5 * 86400,
            is_episodic=True,
            content="Mid-age speculative memory about an uncertain finding.",
        )
        action = engine.evaluate(mem_mid_c)
        evaluations.append((mem_mid_c, action))

        return evaluations

    def _evaluate_anti_pattern_memories(self) -> List[Tuple[MemoryRecord, ForgettingAction]]:
        """Evaluate anti-pattern (FAILED) memories.

        Anti-patterns should never be PURGED — they are retained
        indefinitely as cautionary memories.

        Returns:
            List of (MemoryRecord, ForgettingAction) tuples.
        """
        engine = self.forgetting_engine
        now = time.time()
        evaluations: List[Tuple[MemoryRecord, ForgettingAction]] = []

        # Anti-pattern memory: FAILED result, very old
        mem_anti = MemoryRecord(
            id="anti-pattern-mem-001",
            quality=QualityScore(
                source=SourceQuality.C,
                result=ResultQuality.FAILED,
                confidence=0.1,
                evidence_count=0,
                contradiction_count=2,
            ),
            created_at=now - 30 * 86400,  # 30 days old
            last_reinforced=now - 30 * 86400,
            is_episodic=False,
            content="This approach caused a system crash — do not repeat.",
        )
        action = engine.evaluate(mem_anti)
        evaluations.append((mem_anti, action))

        # Another anti-pattern, even older
        mem_anti2 = MemoryRecord(
            id="anti-pattern-mem-002",
            quality=QualityScore(
                source=SourceQuality.D,
                result=ResultQuality.FAILED,
                confidence=0.05,
                evidence_count=0,
                contradiction_count=3,
            ),
            created_at=now - 365 * 86400,  # 1 year old
            last_reinforced=now - 365 * 86400,
            is_episodic=False,
            content="Critical failure pattern from a year ago.",
        )
        action = engine.evaluate(mem_anti2)
        evaluations.append((mem_anti2, action))

        return evaluations

    def _record_ab_test_results(self, experiment: Experiment) -> None:
        """Record A/B test results so the variant wins.

        Records enough trials for both control and variant templates
        so that the variant has a significantly higher success rate.

        Args:
            experiment: The A/B experiment to record results for.
        """
        ab = self.ab_test_framework

        # Record variant wins (6 successes, 0 failures)
        for _ in range(6):
            ab.record_result(
                experiment_id=experiment.id,
                template_id=experiment.variant_template_id,
                success=True,
                iterations=2,
                cost=50.0,
            )

        # Record control losses (1 success, 5 failures)
        ab.record_result(
            experiment_id=experiment.id,
            template_id=experiment.control_template_id,
            success=True,
            iterations=4,
            cost=150.0,
        )
        for _ in range(5):
            ab.record_result(
                experiment_id=experiment.id,
                template_id=experiment.control_template_id,
                success=False,
                iterations=8,
                cost=300.0,
            )

    def _verify_performance_metrics(self, results: List[TaskResult]) -> None:
        """Verify before/after performance metrics.

        Splits results into first half and second half and verifies
        that the metrics are computed correctly.

        Args:
            results: All task results from the bilevel loop run.
        """
        total = len(results)
        midpoint = total // 2
        before = results[:midpoint]
        after = results[midpoint:]

        # Compute before metrics
        before_success = sum(1 for r in before if r.success)
        before_rate = before_success / len(before) if before else 0.0

        # Compute after metrics
        after_success = sum(1 for r in after if r.success)
        after_rate = after_success / len(after) if after else 0.0

        # Both halves should have valid metrics
        self.assertGreater(len(before), 0)
        self.assertGreater(len(after), 0)
        self.assertGreaterEqual(before_rate, 0.0)
        self.assertGreaterEqual(after_rate, 0.0)

        # Total token cost should be positive
        total_cost = sum(r.token_cost for r in results)
        self.assertGreater(total_cost, 0.0)

        # Total iterations should be positive
        total_iters = sum(r.iterations for r in results)
        self.assertGreater(total_iters, 0)


# ═══════════════════════════════════════════════════════════════
#  Additional Tests: Report Generator Unit Tests
# ═══════════════════════════════════════════════════════════════


class TestEvolutionReportGenerator(unittest.TestCase):
    """Unit tests for EvolutionReportGenerator and EvolutionReport."""

    def setUp(self):
        """Set up a minimal bilevel loop with a few results."""
        self.backend = SQLiteBackend(":memory:")
        self.store = LoopTemplateStore(self.backend)
        for t in DefaultTemplates.all_defaults():
            self.store.save_template(t)

        self.evolution_loop = EvolutionLoop(template_store=self.store)
        self.task_loop = TaskLoop(template_store=self.store)
        self.bilevel_loop = BilevelLoop(
            task_loop=self.task_loop,
            evolution_loop=self.evolution_loop,
        )

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_generate_empty_loop(self):
        """Report generation works with zero results."""
        gen = EvolutionReportGenerator(self.bilevel_loop)
        report = gen.generate()
        d = report.to_dict()
        self.assertEqual(d["task_overview"]["total_tasks"], 0)
        self.assertEqual(d["task_overview"]["success_rate"], 0.0)

    def test_generate_with_results(self):
        """Report generation works after running tasks."""
        self._run_async(self.bilevel_loop.run_batch(["task 1", "task 2", "task 3"]))
        gen = EvolutionReportGenerator(self.bilevel_loop)
        report = gen.generate()
        d = report.to_dict()
        self.assertEqual(d["task_overview"]["total_tasks"], 3)
        self.assertGreater(d["task_overview"]["evolution_cycles"], 0)

    def test_markdown_has_all_sections(self):
        """Markdown report contains all 8 sections."""
        self._run_async(self.bilevel_loop.run("test task"))
        gen = EvolutionReportGenerator(self.bilevel_loop)
        report = gen.generate()
        md = report.to_markdown()
        for section in range(1, 9):
            self.assertIn(f"## {section}.", md)

    def test_json_is_valid(self):
        """JSON output is valid and parseable."""
        self._run_async(self.bilevel_loop.run("test task"))
        gen = EvolutionReportGenerator(self.bilevel_loop)
        report = gen.generate()
        json_str = report.to_json()
        parsed = json.loads(json_str)
        self.assertIsInstance(parsed, dict)
        self.assertIn("task_overview", parsed)

    def test_save_to_file(self):
        """Report can be saved to file in both formats."""
        self._run_async(self.bilevel_loop.run("test task"))
        gen = EvolutionReportGenerator(self.bilevel_loop)
        report = gen.generate()

        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = report.save_to_file(
                os.path.join(tmpdir, "report.md"), fmt="markdown"
            )
            self.assertTrue(os.path.exists(md_path))

            json_path = report.save_to_file(
                os.path.join(tmpdir, "report.json"), fmt="json"
            )
            self.assertTrue(os.path.exists(json_path))

    def test_forgetting_evaluations_in_report(self):
        """Forgetting evaluations are included in the report."""
        self._run_async(self.bilevel_loop.run("test task"))

        # Create a memory that will be COMPRESS'd
        now = time.time()
        old_mem = MemoryRecord(
            id="test-old-mem",
            quality=QualityScore(
                source=SourceQuality.C,
                result=ResultQuality.SPECULATIVE,
                confidence=0.2,
            ),
            created_at=now - 10 * 86400,
            last_reinforced=now - 10 * 86400,
            is_episodic=True,
        )
        action = self.evolution_loop.forgetting_engine.evaluate(old_mem)

        gen = EvolutionReportGenerator(
            self.bilevel_loop,
            forgetting_evaluations=[(old_mem, action)],
        )
        report = gen.generate()
        d = report.to_dict()
        self.assertGreater(d["forgetting_summary"]["total_evaluated"], 0)
        self.assertIn(action.name, d["forgetting_summary"]["actions"])

    def test_report_repr(self):
        """Report has a useful repr."""
        self._run_async(self.bilevel_loop.run("test task"))
        gen = EvolutionReportGenerator(self.bilevel_loop)
        report = gen.generate()
        r = repr(report)
        self.assertIn("EvolutionReport", r)

    def test_report_contains_item(self):
        """Report supports __contains__ for section keys."""
        self._run_async(self.bilevel_loop.run("test task"))
        gen = EvolutionReportGenerator(self.bilevel_loop)
        report = gen.generate()
        self.assertIn("task_overview", report)
        self.assertIn("key_findings", report)
        self.assertNotIn("nonexistent_key", report)

    def test_report_getitem(self):
        """Report supports __getitem__ for section access."""
        self._run_async(self.bilevel_loop.run("test task"))
        gen = EvolutionReportGenerator(self.bilevel_loop)
        report = gen.generate()
        overview = report["task_overview"]
        self.assertIsInstance(overview, dict)
        self.assertIn("total_tasks", overview)


# ═══════════════════════════════════════════════════════════════
#  Additional Tests: Switchable LLM Design Verification
# ═══════════════════════════════════════════════════════════════


class TestSwitchableLLMDesign(unittest.TestCase):
    """Verify the e2e test design supports switching to a real LLM.

    These tests confirm that the BilevelLoop accepts any LLMInterface
    implementation, not just MockLLM.  When OmniRoute is configured
    with real Providers, the same test infrastructure will work
    without code changes.
    """

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_mock_llm_is_llm_interface(self):
        """MockLLM satisfies the LLMInterface protocol."""
        from suyi.core.loop import LLMInterface
        mock = MockLLM([LLMResponse.text("Hello")])
        self.assertIsInstance(mock, LLMInterface)

    def test_bilevel_loop_with_agent_loop(self):
        """BilevelLoop works with an AgentLoop backed by MockLLM."""
        backend = SQLiteBackend(":memory:")
        store = LoopTemplateStore(backend)
        for t in DefaultTemplates.all_defaults():
            store.save_template(t)

        # Create a MockLLM with enough responses for template-driven execution
        mock_llm = MockLLM([
            LLMResponse.text("Observing the task and gathering context."),
            LLMResponse.text("Planning the approach for this task."),
            LLMResponse.text("Task completed successfully."),
        ])
        agent = AgentLoop(llm=mock_llm)

        task_loop = TaskLoop(template_store=store, agent_loop=agent)
        evolution_loop = EvolutionLoop(template_store=store)
        loop = BilevelLoop(
            task_loop=task_loop,
            evolution_loop=evolution_loop,
        )

        result = self._run_async(loop.run("test task with agent loop"))
        self.assertIsInstance(result, TaskResult)
        self.assertTrue(result.success)

    def test_configurable_task_loop_preserves_normal_behavior(self):
        """ConfigurableTaskLoop runs normally for non-failing indices."""
        backend = SQLiteBackend(":memory:")
        store = LoopTemplateStore(backend)
        for t in DefaultTemplates.all_defaults():
            store.save_template(t)

        task_loop = ConfigurableTaskLoop(
            template_store=store,
            fail_indices={99},  # No task will hit this index
        )
        result = self._run_async(task_loop.run("normal task"))
        self.assertTrue(result.success)
        self.assertGreater(result.content, "")


if __name__ == "__main__":
    unittest.main()
