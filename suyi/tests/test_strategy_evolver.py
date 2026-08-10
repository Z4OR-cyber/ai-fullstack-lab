"""
Tests for the Strategy Evolver system (Phase 15).

Covers:
    - ProcessReflection: five-dimensional scoring, composite score,
      weakest/strongest dimension, summary generation, serialisation.
    - ExecutionResult: creation, is_correct, error_count, serialisation.
    - MutationType: all six types.
    - MutationProposal: creation, serialisation round-trip.
    - StrategyEvolver: analyse_run (all 5 dimensions, edge cases),
      propose_mutation (per-dimension proposals), apply_mutation
      (all 6 mutation types), evolve (full pipeline with/without
      registration), mutation history recording.
    - ABTestFramework: create_experiment, record_result, evaluate
      (insufficient samples, variant wins, control wins, tie),
      promotion/demotion, list_experiments, cancel_experiment.
    - SQLiteBackend Phase 15 methods: save/get/list
      strategy_experiments, save/list/count experiment_results,
      save/list mutation_history.
    - Statistical functions: _normal_cdf, _wilson_interval,
      _two_proportion_z_test, _wilson_overlap_test.
    - Edge cases: empty templates, invalid indices, mock backends,
      identical success rates, all-success / all-failure.
"""

import json
import math
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from suyi.quality.grader import (
    QualityScore,
    QualityAssessor,
    ResultQuality,
    SourceQuality,
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
    _normal_cdf,
    _wilson_interval,
    _two_proportion_z_test,
    _wilson_overlap_test,
)
from suyi.persistence.sqlite_backend import SQLiteBackend


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════


def _make_backend():
    """Create a temporary SQLiteBackend for testing."""
    tmpdir = tempfile.mkdtemp()
    return SQLiteBackend(db_path=os.path.join(tmpdir, "test_strat.db"))


def _make_store(backend=None):
    """Create a LoopTemplateStore backed by a temp DB."""
    if backend is None:
        backend = _make_backend()
    return LoopTemplateStore(backend=backend)


def _make_template(
    task_desc="deploy application to production",
    phases=None,
    tools=None,
    max_iterations=10,
):
    """Create a simple template for testing."""
    if phases is None:
        phases = [
            LoopPhase(name="perceive", action="Check state", tools=["read"]),
            LoopPhase(name="plan", action="Plan deploy", tools=[]),
            LoopPhase(name="execute", action="Run deploy", tools=["deploy"]),
        ]
    if tools is None:
        tools = ["read", "deploy"]
    return LoopTemplate(
        task_signature=compute_task_signature(task_desc),
        task_description=task_desc,
        phases=phases,
        tools=tools,
        tool_order=list(tools),
        reflection_points=[1],
        max_iterations=max_iterations,
        termination_conditions=["done", "error"],
        success_count=5,
        failure_count=1,
        avg_iterations=4.5,
        avg_cost=0.12,
        quality=QualityScore(
            source=SourceQuality.B,
            result=ResultQuality.TRUSTED,
            confidence=0.7,
            evidence_count=3,
        ),
    )


def _make_result(
    success=True,
    iterations=5,
    token_cost=100.0,
    token_budget=1000.0,
    errors=None,
    tools_used=None,
    tools_available=None,
    result_correct=None,
    expected_iterations=None,
):
    """Create a simple ExecutionResult for testing."""
    if errors is None:
        errors = []
    if tools_used is None:
        tools_used = ["read", "deploy"]
    if tools_available is None:
        tools_available = ["read", "deploy", "search"]
    return ExecutionResult(
        success=success,
        iterations=iterations,
        expected_iterations=expected_iterations,
        token_cost=token_cost,
        token_budget=token_budget,
        errors=errors,
        tools_used=tools_used,
        tools_available=tools_available,
        result_correct=result_correct,
    )


# ═══════════════════════════════════════════════════════════════
#  TestProcessReflection
# ═══════════════════════════════════════════════════════════════


class TestProcessReflection(unittest.TestCase):
    """ProcessReflection dataclass tests."""

    def test_default_values(self):
        """All dimensions default to 0.5."""
        r = ProcessReflection()
        self.assertAlmostEqual(r.efficiency, 0.5)
        self.assertAlmostEqual(r.accuracy, 0.5)
        self.assertAlmostEqual(r.cost, 0.5)
        self.assertAlmostEqual(r.robustness, 0.5)
        self.assertAlmostEqual(r.adaptability, 0.5)

    def test_composite_score_defaults(self):
        """Composite score of all-0.5 defaults is 0.5."""
        r = ProcessReflection()
        self.assertAlmostEqual(r.composite_score, 0.5)

    def test_composite_score_perfect(self):
        """All dimensions at 1.0 → composite 1.0."""
        r = ProcessReflection(
            efficiency=1.0, accuracy=1.0, cost=1.0,
            robustness=1.0, adaptability=1.0,
        )
        self.assertAlmostEqual(r.composite_score, 1.0)

    def test_composite_score_zero(self):
        """All dimensions at 0.0 → composite 0.0."""
        r = ProcessReflection(
            efficiency=0.0, accuracy=0.0, cost=0.0,
            robustness=0.0, adaptability=0.0,
        )
        self.assertAlmostEqual(r.composite_score, 0.0)

    def test_weakest_dimension(self):
        """weakest_dimension identifies the lowest score."""
        r = ProcessReflection(
            efficiency=0.8, accuracy=0.9, cost=0.1,
            robustness=0.7, adaptability=0.6,
        )
        self.assertEqual(r.weakest_dimension, "cost")

    def test_strongest_dimension(self):
        """strongest_dimension identifies the highest score."""
        r = ProcessReflection(
            efficiency=0.8, accuracy=0.9, cost=0.1,
            robustness=0.7, adaptability=0.6,
        )
        self.assertEqual(r.strongest_dimension, "accuracy")

    def test_summary_contains_composite(self):
        """summary includes the composite score."""
        r = ProcessReflection()
        s = r.summary
        self.assertIn("Composite", s)
        self.assertIn("0.50", s)

    def test_summary_warns_low_dimensions(self):
        """summary contains warning for dimensions below 0.5."""
        r = ProcessReflection(accuracy=0.3)
        s = r.summary
        self.assertIn("Accuracy", s)

    def test_custom_weights(self):
        """Custom weights affect the composite score."""
        r = ProcessReflection(
            efficiency=1.0, accuracy=0.0, cost=1.0,
            robustness=1.0, adaptability=1.0,
            weights={
                "efficiency": 0.0, "accuracy": 1.0, "cost": 0.0,
                "robustness": 0.0, "adaptability": 0.0,
            },
        )
        self.assertAlmostEqual(r.composite_score, 0.0)

    def test_serialisation_roundtrip(self):
        """to_dict / from_dict round-trip preserves values."""
        r = ProcessReflection(
            efficiency=0.7, accuracy=0.8, cost=0.6,
            robustness=0.9, adaptability=0.5,
            notes="test notes",
        )
        d = r.to_dict()
        r2 = ProcessReflection.from_dict(d)
        self.assertAlmostEqual(r2.efficiency, 0.7)
        self.assertAlmostEqual(r2.accuracy, 0.8)
        self.assertAlmostEqual(r2.cost, 0.6)
        self.assertAlmostEqual(r2.robustness, 0.9)
        self.assertAlmostEqual(r2.adaptability, 0.5)
        self.assertEqual(r2.notes, "test notes")


# ═══════════════════════════════════════════════════════════════
#  TestExecutionResult
# ═══════════════════════════════════════════════════════════════


class TestExecutionResult(unittest.TestCase):
    """ExecutionResult dataclass tests."""

    def test_default_values(self):
        r = ExecutionResult()
        self.assertTrue(r.success)
        self.assertEqual(r.iterations, 1)
        self.assertEqual(r.token_cost, 0.0)
        self.assertEqual(r.token_budget, 1000.0)
        self.assertEqual(r.errors, [])

    def test_is_correct_falls_back_to_success(self):
        """is_correct returns success when result_correct is None."""
        r = ExecutionResult(success=True, result_correct=None)
        self.assertTrue(r.is_correct)
        r = ExecutionResult(success=False, result_correct=None)
        self.assertFalse(r.is_correct)

    def test_is_correct_uses_result_correct(self):
        """is_correct uses result_correct when set."""
        r = ExecutionResult(success=True, result_correct=False)
        self.assertFalse(r.is_correct)

    def test_error_count(self):
        r = ExecutionResult(errors=["e1", "e2", "e3"])
        self.assertEqual(r.error_count, 3)

    def test_serialisation_roundtrip(self):
        r = ExecutionResult(
            success=False, iterations=7, token_cost=500.0,
            errors=["timeout"], tools_used=["search"],
        )
        d = r.to_dict()
        r2 = ExecutionResult.from_dict(d)
        self.assertEqual(r2.success, r.success)
        self.assertEqual(r2.iterations, r.iterations)
        self.assertEqual(r2.token_cost, r.token_cost)
        self.assertEqual(r2.errors, r.errors)
        self.assertEqual(r2.tools_used, r.tools_used)


# ═══════════════════════════════════════════════════════════════
#  TestMutationType
# ═══════════════════════════════════════════════════════════════


class TestMutationType(unittest.TestCase):
    """MutationType enum tests."""

    def test_all_six_types_exist(self):
        types = {MutationType.ADD_PHASE, MutationType.REMOVE_PHASE,
                 MutationType.REORDER_PHASES, MutationType.ADD_TOOL,
                 MutationType.REMOVE_TOOL, MutationType.ADJUST_REFLECTION}
        self.assertEqual(len(types), 6)

    def test_value_strings(self):
        self.assertEqual(MutationType.ADD_PHASE.value, "ADD_PHASE")
        self.assertEqual(MutationType.REMOVE_PHASE.value, "REMOVE_PHASE")
        self.assertEqual(MutationType.REORDER_PHASES.value, "REORDER_PHASES")
        self.assertEqual(MutationType.ADD_TOOL.value, "ADD_TOOL")
        self.assertEqual(MutationType.REMOVE_TOOL.value, "REMOVE_TOOL")
        self.assertEqual(MutationType.ADJUST_REFLECTION.value, "ADJUST_REFLECTION")


# ═══════════════════════════════════════════════════════════════
#  TestMutationProposal
# ═══════════════════════════════════════════════════════════════


class TestMutationProposal(unittest.TestCase):
    """MutationProposal dataclass tests."""

    def test_default_values(self):
        p = MutationProposal()
        self.assertEqual(p.mutation_type, MutationType.ADD_PHASE)
        self.assertEqual(p.description, "")
        self.assertEqual(p.expected_improvement, 0.05)

    def test_serialisation_roundtrip(self):
        p = MutationProposal(
            mutation_type=MutationType.ADD_PHASE,
            description="Add verify phase",
            target_phase_index=2,
            new_phase=LoopPhase(name="verify", action="Check result"),
            rationale="Improve accuracy",
            expected_improvement=0.15,
            target_dimension="accuracy",
        )
        d = p.to_dict()
        p2 = MutationProposal.from_dict(d)
        self.assertEqual(p2.mutation_type, MutationType.ADD_PHASE)
        self.assertEqual(p2.description, "Add verify phase")
        self.assertEqual(p2.target_phase_index, 2)
        self.assertIsNotNone(p2.new_phase)
        self.assertEqual(p2.new_phase.name, "verify")
        self.assertEqual(p2.target_dimension, "accuracy")


# ═══════════════════════════════════════════════════════════════
#  TestStatisticalFunctions
# ═══════════════════════════════════════════════════════════════


class TestStatisticalFunctions(unittest.TestCase):
    """Tests for the pure-stdlib statistical helpers."""

    def test_normal_cdf_at_zero(self):
        """CDF(0) = 0.5."""
        self.assertAlmostEqual(_normal_cdf(0), 0.5)

    def test_normal_cdf_at_large_positive(self):
        """CDF(5) ≈ 1.0."""
        self.assertGreater(_normal_cdf(5), 0.999)

    def test_normal_cdf_at_large_negative(self):
        """CDF(-5) ≈ 0.0."""
        self.assertLess(_normal_cdf(-5), 0.001)

    def test_wilson_interval_basic(self):
        """Wilson interval for 5/10 successes."""
        lo, hi = _wilson_interval(5, 10)
        self.assertGreater(lo, 0.0)
        self.assertLess(hi, 1.0)
        self.assertGreater(hi, lo)

    def test_wilson_interval_zero_successes(self):
        """Wilson interval for 0/n is [0, something]."""
        lo, hi = _wilson_interval(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertGreater(hi, 0.0)

    def test_wilson_interval_all_successes(self):
        """Wilson interval for n/n is [something, 1]."""
        lo, hi = _wilson_interval(10, 10)
        self.assertEqual(hi, 1.0)
        self.assertLess(lo, 1.0)

    def test_wilson_interval_zero_n(self):
        """Wilson interval for 0/0 returns [0, 1]."""
        lo, hi = _wilson_interval(0, 0)
        self.assertEqual(lo, 0.0)
        self.assertEqual(hi, 1.0)

    def test_two_proportion_z_test_identical_rates(self):
        """Identical success rates → not significant."""
        p, sig = _two_proportion_z_test(8, 10, 8, 10)
        self.assertFalse(sig)
        self.assertAlmostEqual(p, 1.0)

    def test_two_proportion_z_test_significant_difference(self):
        """9/10 vs 1/10 → significant."""
        p, sig = _two_proportion_z_test(9, 10, 1, 10)
        self.assertTrue(sig)
        self.assertLess(p, 0.05)

    def test_two_proportion_z_test_insufficient_samples(self):
        """n < 2 → not significant."""
        p, sig = _two_proportion_z_test(1, 1, 0, 1)
        self.assertFalse(sig)

    def test_two_proportion_z_test_all_success(self):
        """Both 10/10 → p_pool = 1.0 → not significant."""
        p, sig = _two_proportion_z_test(10, 10, 10, 10)
        self.assertFalse(sig)

    def test_wilson_overlap_no_overlap(self):
        """Disjoint rates → no overlap → significant."""
        sig = _wilson_overlap_test(9, 10, 1, 10)
        self.assertTrue(sig)

    def test_wilson_overlap_overlapping(self):
        """Similar rates → overlap → not significant."""
        sig = _wilson_overlap_test(5, 10, 6, 10)
        self.assertFalse(sig)


# ═══════════════════════════════════════════════════════════════
#  TestStrategyEvolverAnalyse
# ═══════════════════════════════════════════════════════════════


class TestStrategyEvolverAnalyse(unittest.TestCase):
    """StrategyEvolver.analyze_run tests."""

    def setUp(self):
        self.store = _make_store()
        self.evolver = StrategyEvolver(store=self.store)

    def test_analyze_perfect_run(self):
        """Perfect execution → all dimensions high."""
        tpl = _make_template(max_iterations=10)
        result = _make_result(
            success=True, iterations=3, token_cost=50.0,
            token_budget=1000.0, errors=[],
            tools_used=["read", "deploy"], tools_available=["read", "deploy"],
            result_correct=True,
        )
        r = self.evolver.analyze_run(tpl, result)
        self.assertGreater(r.efficiency, 0.8)
        self.assertEqual(r.accuracy, 1.0)
        self.assertGreater(r.cost, 0.8)
        self.assertEqual(r.robustness, 1.0)
        self.assertGreater(r.composite_score, 0.8)

    def test_analyze_accuracy_zero_on_failure(self):
        """Failed result → accuracy 0."""
        tpl = _make_template()
        result = _make_result(success=False, result_correct=False)
        r = self.evolver.analyze_run(tpl, result)
        self.assertEqual(r.accuracy, 0.0)

    def test_analyze_efficiency_too_many_iterations(self):
        """Iterations > max → low efficiency."""
        tpl = _make_template(max_iterations=10)
        result = _make_result(iterations=15)
        r = self.evolver.analyze_run(tpl, result)
        self.assertLess(r.efficiency, 0.5)

    def test_analyze_efficiency_few_iterations(self):
        """Iterations well below max → high efficiency."""
        tpl = _make_template(max_iterations=10)
        result = _make_result(iterations=3)
        r = self.evolver.analyze_run(tpl, result)
        self.assertGreater(r.efficiency, 0.9)

    def test_analyze_cost_over_budget(self):
        """Cost > budget → cost score 0."""
        tpl = _make_template()
        result = _make_result(token_cost=1500.0, token_budget=1000.0)
        r = self.evolver.analyze_run(tpl, result)
        self.assertEqual(r.cost, 0.0)

    def test_analyze_cost_within_budget(self):
        """Cost well below budget → high cost score."""
        tpl = _make_template()
        result = _make_result(token_cost=100.0, token_budget=1000.0)
        r = self.evolver.analyze_run(tpl, result)
        self.assertEqual(r.cost, 1.0)

    def test_analyze_robustness_with_errors(self):
        """Errors reduce robustness."""
        tpl = _make_template()
        result = _make_result(errors=["e1", "e2"])
        r = self.evolver.analyze_run(tpl, result)
        self.assertAlmostEqual(r.robustness, 0.4)

    def test_analyze_robustness_no_errors(self):
        """No errors → robustness 1.0."""
        tpl = _make_template()
        result = _make_result(errors=[])
        r = self.evolver.analyze_run(tpl, result)
        self.assertEqual(r.robustness, 1.0)

    def test_analyze_adaptability_good_tools(self):
        """Used tools are subset of available → high adaptability."""
        tpl = _make_template(tools=["read", "deploy"])
        result = _make_result(
            tools_used=["read", "deploy"],
            tools_available=["read", "deploy", "search"],
        )
        r = self.evolver.analyze_run(tpl, result)
        self.assertEqual(r.adaptability, 1.0)

    def test_analyze_adaptability_unknown_tools(self):
        """Unknown tools → lower adaptability."""
        tpl = _make_template(tools=["read", "deploy"])
        result = _make_result(
            tools_used=["read", "unknown_tool"],
            tools_available=["read", "deploy"],
        )
        r = self.evolver.analyze_run(tpl, result)
        self.assertLess(r.adaptability, 1.0)

    def test_analyze_uses_expected_iterations(self):
        """expected_iterations overrides template.max_iterations."""
        tpl = _make_template(max_iterations=10)
        result = _make_result(iterations=3, expected_iterations=5)
        r = self.evolver.analyze_run(tpl, result)
        # 3/5 = 0.6 ratio → efficiency should be ~0.8
        self.assertGreater(r.efficiency, 0.7)

    def test_analyze_raw_metrics_stored(self):
        """Raw execution metrics are stored in reflection."""
        tpl = _make_template()
        result = _make_result(iterations=5, token_cost=200.0)
        r = self.evolver.analyze_run(tpl, result)
        self.assertEqual(r.raw_metrics["iterations"], 5)
        self.assertEqual(r.raw_metrics["token_cost"], 200.0)

    def test_analyze_zero_budget(self):
        """Zero budget → cost score 0."""
        tpl = _make_template()
        result = _make_result(token_cost=0.0, token_budget=0.0)
        r = self.evolver.analyze_run(tpl, result)
        self.assertEqual(r.cost, 0.0)

    def test_analyze_no_tools(self):
        """Template with no tools and no tools used → adaptability 0.5."""
        tpl = _make_template(tools=[])
        result = _make_result(tools_used=[], tools_available=[])
        r = self.evolver.analyze_run(tpl, result)
        self.assertAlmostEqual(r.adaptability, 0.5)


# ═══════════════════════════════════════════════════════════════
#  TestStrategyEvolverPropose
# ═══════════════════════════════════════════════════════════════


class TestStrategyEvolverPropose(unittest.TestCase):
    """StrategyEvolver.propose_mutation tests."""

    def setUp(self):
        self.store = _make_store()
        self.evolver = StrategyEvolver(store=self.store)

    def test_propose_for_low_accuracy(self):
        """Low accuracy → ADD_PHASE with verify."""
        tpl = _make_template()
        reflection = ProcessReflection(
            efficiency=0.9, accuracy=0.2, cost=0.9,
            robustness=0.9, adaptability=0.9,
        )
        proposal = self.evolver.propose_mutation(tpl, reflection)
        self.assertEqual(proposal.mutation_type, MutationType.ADD_PHASE)
        self.assertEqual(proposal.target_dimension, "accuracy")
        self.assertIsNotNone(proposal.new_phase)
        self.assertEqual(proposal.new_phase.name, "verify")

    def test_propose_for_low_efficiency_many_phases(self):
        """Low efficiency with many phases → REMOVE_PHASE."""
        tpl = _make_template(phases=[
            LoopPhase(name="perceive", action="a"),
            LoopPhase(name="plan", action="b"),
            LoopPhase(name="execute", action="c"),
            LoopPhase(name="execute", action="d"),
            LoopPhase(name="verify", action="e"),
        ])
        reflection = ProcessReflection(
            efficiency=0.2, accuracy=0.9, cost=0.9,
            robustness=0.9, adaptability=0.9,
        )
        proposal = self.evolver.propose_mutation(tpl, reflection)
        self.assertEqual(proposal.mutation_type, MutationType.REMOVE_PHASE)
        self.assertEqual(proposal.target_dimension, "efficiency")

    def test_propose_for_low_efficiency_few_phases(self):
        """Low efficiency with few phases → ADJUST_REFLECTION."""
        tpl = _make_template()
        reflection = ProcessReflection(
            efficiency=0.2, accuracy=0.9, cost=0.9,
            robustness=0.9, adaptability=0.9,
        )
        proposal = self.evolver.propose_mutation(tpl, reflection)
        self.assertEqual(proposal.mutation_type, MutationType.ADJUST_REFLECTION)
        self.assertIsNotNone(proposal.new_reflection_points)

    def test_propose_for_low_cost_many_phases(self):
        """Low cost score with many phases → REMOVE_PHASE."""
        tpl = _make_template(phases=[
            LoopPhase(name="perceive", action="a"),
            LoopPhase(name="plan", action="b"),
            LoopPhase(name="execute", action="c"),
            LoopPhase(name="execute", action="d"),
            LoopPhase(name="verify", action="e"),
        ])
        reflection = ProcessReflection(
            efficiency=0.9, accuracy=0.9, cost=0.2,
            robustness=0.9, adaptability=0.9,
        )
        proposal = self.evolver.propose_mutation(tpl, reflection)
        self.assertEqual(proposal.mutation_type, MutationType.REMOVE_PHASE)
        self.assertEqual(proposal.target_dimension, "cost")

    def test_propose_for_low_cost_many_tools(self):
        """Low cost with many tools → REMOVE_TOOL."""
        tpl = _make_template(tools=["a", "b", "c", "d"])
        reflection = ProcessReflection(
            efficiency=0.9, accuracy=0.9, cost=0.2,
            robustness=0.9, adaptability=0.9,
        )
        proposal = self.evolver.propose_mutation(tpl, reflection)
        self.assertEqual(proposal.mutation_type, MutationType.REMOVE_TOOL)
        self.assertIsNotNone(proposal.tool_name)

    def test_propose_for_low_robustness(self):
        """Low robustness → ADD_PHASE with reflect."""
        tpl = _make_template()
        reflection = ProcessReflection(
            efficiency=0.9, accuracy=0.9, cost=0.9,
            robustness=0.2, adaptability=0.9,
        )
        proposal = self.evolver.propose_mutation(tpl, reflection)
        self.assertEqual(proposal.mutation_type, MutationType.ADD_PHASE)
        self.assertEqual(proposal.new_phase.name, "reflect")

    def test_propose_for_low_adaptability_no_tools(self):
        """Low adaptability with no template tools → ADD_TOOL."""
        tpl = _make_template(
            tools=[],
            phases=[
                LoopPhase(name="perceive", action="a", tools=["search"]),
                LoopPhase(name="execute", action="b"),
            ],
        )
        reflection = ProcessReflection(
            efficiency=0.9, accuracy=0.9, cost=0.9,
            robustness=0.9, adaptability=0.2,
        )
        proposal = self.evolver.propose_mutation(tpl, reflection)
        self.assertEqual(proposal.mutation_type, MutationType.ADD_TOOL)
        self.assertIsNotNone(proposal.tool_name)

    def test_propose_all_high_scores(self):
        """All dimensions high → fallback proposal still returned."""
        tpl = _make_template()
        reflection = ProcessReflection(
            efficiency=0.9, accuracy=0.9, cost=0.9,
            robustness=0.9, adaptability=0.9,
        )
        proposal = self.evolver.propose_mutation(tpl, reflection)
        self.assertIsNotNone(proposal)
        self.assertIn(proposal.mutation_type, list(MutationType))

    def test_proposal_has_rationale(self):
        """Every proposal has a non-empty rationale."""
        tpl = _make_template()
        reflection = ProcessReflection(
            efficiency=0.2, accuracy=0.2, cost=0.2,
            robustness=0.2, adaptability=0.2,
        )
        proposal = self.evolver.propose_mutation(tpl, reflection)
        self.assertTrue(proposal.rationale)


# ═══════════════════════════════════════════════════════════════
#  TestStrategyEvolverApply
# ═══════════════════════════════════════════════════════════════


class TestStrategyEvolverApply(unittest.TestCase):
    """StrategyEvolver.apply_mutation tests."""

    def setUp(self):
        self.store = _make_store()
        self.evolver = StrategyEvolver(store=self.store)

    def test_apply_add_phase(self):
        """ADD_PHASE inserts a new phase."""
        tpl = _make_template()
        proposal = MutationProposal(
            mutation_type=MutationType.ADD_PHASE,
            target_phase_index=1,
            new_phase=LoopPhase(name="verify", action="Check result"),
        )
        variant = self.evolver.apply_mutation(tpl, proposal)
        self.assertEqual(len(variant.phases), len(tpl.phases) + 1)
        self.assertEqual(variant.phases[1].name, "verify")

    def test_apply_remove_phase(self):
        """REMOVE_PHASE deletes a phase."""
        tpl = _make_template()
        original_len = len(tpl.phases)
        proposal = MutationProposal(
            mutation_type=MutationType.REMOVE_PHASE,
            target_phase_index=1,
        )
        variant = self.evolver.apply_mutation(tpl, proposal)
        self.assertEqual(len(variant.phases), original_len - 1)

    def test_apply_reorder_phases(self):
        """REORDER_PHASES rearranges phases."""
        tpl = _make_template(phases=[
            LoopPhase(name="perceive", action="a"),
            LoopPhase(name="plan", action="b"),
            LoopPhase(name="execute", action="c"),
        ])
        proposal = MutationProposal(
            mutation_type=MutationType.REORDER_PHASES,
            new_order=[2, 0, 1],
        )
        variant = self.evolver.apply_mutation(tpl, proposal)
        self.assertEqual(variant.phases[0].action, "c")
        self.assertEqual(variant.phases[1].action, "a")
        self.assertEqual(variant.phases[2].action, "b")

    def test_apply_add_tool(self):
        """ADD_TOOL adds a tool to the template."""
        tpl = _make_template(tools=["read"])
        proposal = MutationProposal(
            mutation_type=MutationType.ADD_TOOL,
            tool_name="search",
        )
        variant = self.evolver.apply_mutation(tpl, proposal)
        self.assertIn("search", variant.tools)
        self.assertIn("search", variant.tool_order)

    def test_apply_remove_tool(self):
        """REMOVE_TOOL removes a tool from the template."""
        tpl = _make_template(tools=["read", "deploy"])
        proposal = MutationProposal(
            mutation_type=MutationType.REMOVE_TOOL,
            tool_name="deploy",
        )
        variant = self.evolver.apply_mutation(tpl, proposal)
        self.assertNotIn("deploy", variant.tools)
        self.assertNotIn("deploy", variant.tool_order)

    def test_apply_adjust_reflection(self):
        """ADJUST_REFLECTION modifies reflection points."""
        tpl = _make_template()
        tpl.reflection_points = [0]
        proposal = MutationProposal(
            mutation_type=MutationType.ADJUST_REFLECTION,
            new_reflection_points=[0, 2],
        )
        variant = self.evolver.apply_mutation(tpl, proposal)
        self.assertEqual(variant.reflection_points, [0, 2])

    def test_apply_does_not_modify_original(self):
        """Original template is not modified by apply_mutation."""
        tpl = _make_template()
        original_phase_count = len(tpl.phases)
        proposal = MutationProposal(
            mutation_type=MutationType.ADD_PHASE,
            new_phase=LoopPhase(name="verify", action="check"),
        )
        self.evolver.apply_mutation(tpl, proposal)
        self.assertEqual(len(tpl.phases), original_phase_count)

    def test_apply_add_phase_shifts_reflection_points(self):
        """ADD_PHASE at index 0 shifts existing reflection points."""
        tpl = _make_template()
        tpl.reflection_points = [1]
        proposal = MutationProposal(
            mutation_type=MutationType.ADD_PHASE,
            target_phase_index=0,
            new_phase=LoopPhase(name="perceive", action="init"),
        )
        variant = self.evolver.apply_mutation(tpl, proposal)
        # Original reflection point was at 1, now should be at 2
        self.assertIn(2, variant.reflection_points)
        self.assertNotIn(1, variant.reflection_points)

    def test_apply_remove_phase_invalid_index(self):
        """REMOVE_PHASE with invalid index is a no-op."""
        tpl = _make_template()
        proposal = MutationProposal(
            mutation_type=MutationType.REMOVE_PHASE,
            target_phase_index=99,
        )
        variant = self.evolver.apply_mutation(tpl, proposal)
        self.assertEqual(len(variant.phases), len(tpl.phases))

    def test_apply_reorder_invalid_permutation(self):
        """REORDER_PHASES with invalid permutation is a no-op."""
        tpl = _make_template(phases=[
            LoopPhase(name="perceive"),
            LoopPhase(name="plan"),
            LoopPhase(name="execute"),
        ])
        proposal = MutationProposal(
            mutation_type=MutationType.REORDER_PHASES,
            new_order=[0, 1],  # wrong length
        )
        variant = self.evolver.apply_mutation(tpl, proposal)
        self.assertEqual(
            [p.name for p in variant.phases],
            [p.name for p in tpl.phases],
        )

    def test_apply_add_tool_to_specific_phase(self):
        """ADD_TOOL with target_phase_for_tool adds to that phase."""
        tpl = _make_template()
        proposal = MutationProposal(
            mutation_type=MutationType.ADD_TOOL,
            tool_name="verify_tool",
            target_phase_for_tool=1,
        )
        variant = self.evolver.apply_mutation(tpl, proposal)
        self.assertIn("verify_tool", variant.phases[1].tools)

    def test_apply_add_duplicate_tool(self):
        """ADD_TOOL with existing tool doesn't duplicate."""
        tpl = _make_template(tools=["read"])
        proposal = MutationProposal(
            mutation_type=MutationType.ADD_TOOL,
            tool_name="read",
        )
        variant = self.evolver.apply_mutation(tpl, proposal)
        self.assertEqual(variant.tools.count("read"), 1)

    def test_apply_add_phase_append_at_end(self):
        """ADD_PHASE with None index appends to end."""
        tpl = _make_template()
        proposal = MutationProposal(
            mutation_type=MutationType.ADD_PHASE,
            target_phase_index=None,
            new_phase=LoopPhase(name="verify", action="final check"),
        )
        variant = self.evolver.apply_mutation(tpl, proposal)
        self.assertEqual(variant.phases[-1].name, "verify")

    def test_variant_has_parent_id(self):
        """Applied mutation variant has parent_id set."""
        tpl = _make_template()
        proposal = MutationProposal(
            mutation_type=MutationType.ADD_TOOL,
            tool_name="new_tool",
        )
        variant = self.evolver.apply_mutation(tpl, proposal)
        self.assertEqual(variant.parent_id, tpl.id)

    def test_variant_has_mutation_description(self):
        """Applied mutation variant records the mutation description."""
        tpl = _make_template()
        proposal = MutationProposal(
            mutation_type=MutationType.ADD_TOOL,
            tool_name="new_tool",
        )
        variant = self.evolver.apply_mutation(tpl, proposal)
        self.assertTrue(any("ADD_TOOL" in m for m in variant.mutations))


# ═══════════════════════════════════════════════════════════════
#  TestStrategyEvolverEvolve
# ═══════════════════════════════════════════════════════════════


class TestStrategyEvolverEvolve(unittest.TestCase):
    """StrategyEvolver.evolve full-pipeline tests."""

    def test_evolve_without_register(self):
        """evolve with register=False returns a variant."""
        store = _make_store()
        evolver = StrategyEvolver(store=store)
        tpl = _make_template()
        result = _make_result(success=False, iterations=15, result_correct=False)
        variant = evolver.evolve(tpl, result, register=False)
        self.assertIsNotNone(variant)
        self.assertEqual(variant.parent_id, tpl.id)
        self.assertTrue(len(variant.mutations) > 0)

    def test_evolve_with_register(self):
        """evolve with register=True saves variant to store."""
        store = _make_store()
        evolver = StrategyEvolver(store=store)
        tpl = _make_template()
        store.save_template(tpl)
        result = _make_result(success=False, iterations=15, result_correct=False)
        variant = evolver.evolve(tpl, result, register=True)
        self.assertIsNotNone(variant)
        # Variant should be in the store
        retrieved = store.get_template(variant.id)
        self.assertIsNotNone(retrieved)

    def test_evolve_records_mutation_history(self):
        """evolve records mutation in history table."""
        backend = _make_backend()
        store = LoopTemplateStore(backend=backend)
        evolver = StrategyEvolver(store=store, backend=backend)
        tpl = _make_template()
        store.save_template(tpl)
        result = _make_result(success=False, iterations=15, result_correct=False)
        variant = evolver.evolve(tpl, result, register=True)
        history = backend.list_mutation_history(template_id=variant.id)
        self.assertEqual(len(history), 1)
        self.assertIn("mutation_type", history[0])


# ═══════════════════════════════════════════════════════════════
#  TestABTestFramework
# ═══════════════════════════════════════════════════════════════


class TestABTestFramework(unittest.TestCase):
    """ABTestFramework tests."""

    def setUp(self):
        self.backend = _make_backend()
        self.store = LoopTemplateStore(backend=self.backend)
        self.framework = ABTestFramework(store=self.store, backend=self.backend)

    def test_create_experiment(self):
        """create_experiment returns an Experiment with IDs."""
        ctrl = _make_template()
        var = _make_template()
        exp = self.framework.create_experiment(
            "test-exp", ctrl, var, min_samples=5,
        )
        self.assertTrue(exp.id)
        self.assertEqual(exp.name, "test-exp")
        self.assertEqual(exp.min_samples, 5)
        self.assertEqual(exp.status, "running")
        self.assertEqual(exp.control_template_id, ctrl.id)
        self.assertEqual(exp.variant_template_id, var.id)

    def test_create_experiment_saves_templates(self):
        """create_experiment saves both templates to the store."""
        ctrl = _make_template()
        var = _make_template()
        exp = self.framework.create_experiment(
            "test", ctrl, var,
        )
        # Templates should be in the store
        self.assertIsNotNone(self.store.get_template(ctrl.id))
        self.assertIsNotNone(self.store.get_template(var.id))

    def test_record_result(self):
        """record_result stores a trial result."""
        ctrl = _make_template()
        var = _make_template()
        exp = self.framework.create_experiment("t", ctrl, var)
        self.framework.record_result(exp.id, ctrl.id, True, 5, 100.0)
        results = self.backend.list_experiment_results(exp.id, ctrl.id)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["success"])
        self.assertEqual(results[0]["iterations"], 5)

    def test_evaluate_insufficient_samples(self):
        """Evaluate with too few samples returns not significant."""
        ctrl = _make_template()
        var = _make_template()
        exp = self.framework.create_experiment("t", ctrl, var, min_samples=10)
        # Record only 3 samples each
        for _ in range(3):
            self.framework.record_result(exp.id, ctrl.id, True, 5, 100.0)
            self.framework.record_result(exp.id, var.id, True, 4, 90.0)
        result = self.framework.evaluate(exp.id)
        self.assertFalse(result.is_significant)
        self.assertIn("Insufficient", result.message)

    def test_evaluate_variant_wins(self):
        """Variant with significantly higher success rate wins."""
        ctrl = _make_template()
        var = _make_template()
        exp = self.framework.create_experiment("t", ctrl, var, min_samples=10)
        # Control: 3/10 success, Variant: 9/10 success
        for i in range(10):
            self.framework.record_result(
                exp.id, ctrl.id, success=(i < 3), iterations=5, cost=100.0
            )
            self.framework.record_result(
                exp.id, var.id, success=(i < 9), iterations=4, cost=80.0
            )
        result = self.framework.evaluate(exp.id)
        self.assertTrue(result.is_significant)
        self.assertEqual(result.winner, "variant")

    def test_evaluate_control_wins(self):
        """Control with significantly higher success rate wins."""
        ctrl = _make_template()
        var = _make_template()
        exp = self.framework.create_experiment("t", ctrl, var, min_samples=10)
        for i in range(10):
            self.framework.record_result(
                exp.id, ctrl.id, success=(i < 9), iterations=4, cost=80.0
            )
            self.framework.record_result(
                exp.id, var.id, success=(i < 3), iterations=6, cost=120.0
            )
        result = self.framework.evaluate(exp.id)
        self.assertTrue(result.is_significant)
        self.assertEqual(result.winner, "control")

    def test_evaluate_tie(self):
        """Identical success rates → tie."""
        ctrl = _make_template()
        var = _make_template()
        exp = self.framework.create_experiment("t", ctrl, var, min_samples=10)
        for _ in range(10):
            self.framework.record_result(exp.id, ctrl.id, True, 5, 100.0)
            self.framework.record_result(exp.id, var.id, True, 5, 100.0)
        result = self.framework.evaluate(exp.id)
        self.assertFalse(result.is_significant)
        self.assertEqual(result.winner, "tie")

    def test_evaluate_promotes_variant_on_win(self):
        """Winning variant gets promoted (higher confidence)."""
        ctrl = _make_template()
        var = _make_template()
        original_confidence = var.quality.confidence
        exp = self.framework.create_experiment("t", ctrl, var, min_samples=10)
        for i in range(10):
            self.framework.record_result(
                exp.id, ctrl.id, success=(i < 3), iterations=5, cost=100.0
            )
            self.framework.record_result(
                exp.id, var.id, success=(i < 9), iterations=4, cost=80.0
            )
        self.framework.evaluate(exp.id)
        promoted = self.store.get_template(var.id)
        self.assertGreater(promoted.quality.confidence, original_confidence)

    def test_evaluate_demotes_variant_on_loss(self):
        """Losing variant gets demoted (lower confidence)."""
        ctrl = _make_template()
        var = _make_template()
        original_confidence = var.quality.confidence
        exp = self.framework.create_experiment("t", ctrl, var, min_samples=10)
        for i in range(10):
            self.framework.record_result(
                exp.id, ctrl.id, success=(i < 9), iterations=4, cost=80.0
            )
            self.framework.record_result(
                exp.id, var.id, success=(i < 3), iterations=6, cost=120.0
            )
        self.framework.evaluate(exp.id)
        demoted = self.store.get_template(var.id)
        self.assertLess(demoted.quality.confidence, original_confidence)

    def test_evaluate_updates_experiment_status(self):
        """Evaluate sets experiment status to completed."""
        ctrl = _make_template()
        var = _make_template()
        exp = self.framework.create_experiment("t", ctrl, var, min_samples=5)
        for _ in range(5):
            self.framework.record_result(exp.id, ctrl.id, True, 5, 100.0)
            self.framework.record_result(exp.id, var.id, True, 5, 100.0)
        self.framework.evaluate(exp.id)
        updated = self.framework.get_experiment(exp.id)
        self.assertEqual(updated.status, "completed")

    def test_evaluate_nonexistent_experiment(self):
        """Evaluate non-existent experiment returns message."""
        result = self.framework.evaluate("nonexistent-id")
        self.assertIn("not found", result.message.lower())

    def test_list_experiments(self):
        """list_experiments returns created experiments."""
        ctrl = _make_template()
        var = _make_template()
        self.framework.create_experiment("exp1", ctrl, var)
        self.framework.create_experiment("exp2", ctrl, var)
        exps = self.framework.list_experiments()
        self.assertEqual(len(exps), 2)

    def test_list_experiments_by_status(self):
        """list_experiments filters by status."""
        ctrl = _make_template()
        var = _make_template()
        exp = self.framework.create_experiment("exp1", ctrl, var, min_samples=5)
        for _ in range(5):
            self.framework.record_result(exp.id, ctrl.id, True, 5, 100.0)
            self.framework.record_result(exp.id, var.id, True, 5, 100.0)
        self.framework.evaluate(exp.id)
        running = self.framework.list_experiments(status="running")
        completed = self.framework.list_experiments(status="completed")
        self.assertEqual(len(running), 0)
        self.assertEqual(len(completed), 1)

    def test_cancel_experiment(self):
        """cancel_experiment sets status to cancelled."""
        ctrl = _make_template()
        var = _make_template()
        exp = self.framework.create_experiment("t", ctrl, var)
        self.assertTrue(self.framework.cancel_experiment(exp.id))
        cancelled = self.framework.get_experiment(exp.id)
        self.assertEqual(cancelled.status, "cancelled")

    def test_cancel_nonexistent_experiment(self):
        """cancel_experiment returns False for non-existent ID."""
        self.assertFalse(self.framework.cancel_experiment("nonexistent"))

    def test_record_result_updates_template_stats(self):
        """record_result also updates template usage stats."""
        ctrl = _make_template()
        var = _make_template()
        exp = self.framework.create_experiment("t", ctrl, var)
        self.framework.record_result(exp.id, ctrl.id, True, 5, 100.0)
        updated = self.store.get_template(ctrl.id)
        self.assertGreater(updated.use_count, 0)

    def test_evaluate_result_has_averages(self):
        """ExperimentResult includes average cost and iterations."""
        ctrl = _make_template()
        var = _make_template()
        exp = self.framework.create_experiment("t", ctrl, var, min_samples=5)
        for _ in range(5):
            self.framework.record_result(exp.id, ctrl.id, True, 5, 100.0)
            self.framework.record_result(exp.id, var.id, True, 4, 80.0)
        result = self.framework.evaluate(exp.id)
        self.assertAlmostEqual(result.control_avg_cost, 100.0)
        self.assertAlmostEqual(result.variant_avg_cost, 80.0)
        self.assertAlmostEqual(result.control_avg_iterations, 5.0)
        self.assertAlmostEqual(result.variant_avg_iterations, 4.0)


# ═══════════════════════════════════════════════════════════════
#  TestSQLiteBackendPhase15
# ═══════════════════════════════════════════════════════════════


class TestSQLiteBackendPhase15(unittest.TestCase):
    """Tests for SQLiteBackend Phase 15 table methods."""

    def setUp(self):
        self.backend = _make_backend()

    def test_save_and_get_strategy_experiment(self):
        """save_strategy_experiment / get_strategy_experiment round-trip."""
        data = {
            "id": "exp-001",
            "name": "test-experiment",
            "control_template_id": "ctrl-001",
            "variant_template_id": "var-001",
            "min_samples": 10,
            "status": "running",
            "winner": None,
            "created_at": "2026-01-01T00:00:00Z",
            "completed_at": None,
        }
        self.backend.save_strategy_experiment(data)
        retrieved = self.backend.get_strategy_experiment("exp-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["name"], "test-experiment")
        self.assertEqual(retrieved["status"], "running")

    def test_get_nonexistent_experiment(self):
        """get_strategy_experiment returns None for unknown ID."""
        self.assertIsNone(self.backend.get_strategy_experiment("nonexistent"))

    def test_list_strategy_experiments_all(self):
        """list_strategy_experiments returns all experiments."""
        for i in range(3):
            self.backend.save_strategy_experiment({
                "id": f"exp-{i}",
                "name": f"exp{i}",
                "control_template_id": "c",
                "variant_template_id": "v",
                "min_samples": 10,
                "status": "running",
            })
        exps = self.backend.list_strategy_experiments()
        self.assertEqual(len(exps), 3)

    def test_list_strategy_experiments_by_status(self):
        """list_strategy_experiments filters by status."""
        self.backend.save_strategy_experiment({
            "id": "exp-1", "name": "a", "control_template_id": "c",
            "variant_template_id": "v", "min_samples": 5, "status": "running",
        })
        self.backend.save_strategy_experiment({
            "id": "exp-2", "name": "b", "control_template_id": "c",
            "variant_template_id": "v", "min_samples": 5, "status": "completed",
        })
        running = self.backend.list_strategy_experiments(status="running")
        completed = self.backend.list_strategy_experiments(status="completed")
        self.assertEqual(len(running), 1)
        self.assertEqual(len(completed), 1)

    def test_save_experiment_result(self):
        """save_experiment_result inserts a record."""
        self.backend.save_experiment_result({
            "experiment_id": "exp-1",
            "template_id": "tpl-1",
            "success": 1,
            "iterations": 5,
            "cost": 100.0,
        })
        results = self.backend.list_experiment_results("exp-1")
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["success"])
        self.assertEqual(results[0]["iterations"], 5)

    def test_list_experiment_results_by_template(self):
        """list_experiment_results filters by template_id."""
        for i in range(3):
            self.backend.save_experiment_result({
                "experiment_id": "exp-1",
                "template_id": "tpl-A" if i < 2 else "tpl-B",
                "success": 1,
                "iterations": 5,
                "cost": 100.0,
            })
        results_a = self.backend.list_experiment_results("exp-1", "tpl-A")
        results_b = self.backend.list_experiment_results("exp-1", "tpl-B")
        self.assertEqual(len(results_a), 2)
        self.assertEqual(len(results_b), 1)

    def test_count_experiment_results(self):
        """count_experiment_results returns the correct count."""
        for _ in range(5):
            self.backend.save_experiment_result({
                "experiment_id": "exp-1",
                "template_id": "tpl-1",
                "success": 1,
                "iterations": 5,
                "cost": 100.0,
            })
        count = self.backend.count_experiment_results("exp-1")
        self.assertEqual(count, 5)

    def test_count_experiment_results_by_template(self):
        """count_experiment_results filters by template."""
        for _ in range(3):
            self.backend.save_experiment_result({
                "experiment_id": "exp-1", "template_id": "tpl-A",
                "success": 1, "iterations": 5, "cost": 100.0,
            })
        for _ in range(2):
            self.backend.save_experiment_result({
                "experiment_id": "exp-1", "template_id": "tpl-B",
                "success": 0, "iterations": 5, "cost": 100.0,
            })
        self.assertEqual(self.backend.count_experiment_results("exp-1", "tpl-A"), 3)
        self.assertEqual(self.backend.count_experiment_results("exp-1", "tpl-B"), 2)

    def test_save_mutation_history(self):
        """save_mutation_history inserts a record."""
        row_id = self.backend.save_mutation_history({
            "template_id": "tpl-001",
            "parent_id": "parent-001",
            "mutation_type": "ADD_PHASE",
            "description": "Added verify phase",
            "rationale": "Low accuracy",
            "expected_improvement": 0.15,
            "reflection_composite": 0.45,
            "target_dimension": "accuracy",
        })
        self.assertGreater(row_id, 0)

    def test_list_mutation_history_by_template(self):
        """list_mutation_history filters by template_id."""
        for i in range(3):
            self.backend.save_mutation_history({
                "template_id": "tpl-1" if i < 2 else "tpl-2",
                "parent_id": "parent",
                "mutation_type": "ADD_PHASE",
                "description": f"Mutation {i}",
            })
        history = self.backend.list_mutation_history(template_id="tpl-1")
        self.assertEqual(len(history), 2)

    def test_list_mutation_history_by_parent(self):
        """list_mutation_history filters by parent_id."""
        self.backend.save_mutation_history({
            "template_id": "tpl-1", "parent_id": "p1",
            "mutation_type": "ADD_PHASE", "description": "m1",
        })
        self.backend.save_mutation_history({
            "template_id": "tpl-2", "parent_id": "p2",
            "mutation_type": "REMOVE_PHASE", "description": "m2",
        })
        by_p1 = self.backend.list_mutation_history(parent_id="p1")
        self.assertEqual(len(by_p1), 1)
        self.assertEqual(by_p1[0]["template_id"], "tpl-1")


# ═══════════════════════════════════════════════════════════════
#  TestExperimentDataclass
# ═══════════════════════════════════════════════════════════════


class TestExperimentDataclass(unittest.TestCase):
    """Experiment and ExperimentResult dataclass tests."""

    def test_experiment_auto_id(self):
        """Experiment generates an ID if not provided."""
        exp = Experiment(name="test")
        self.assertTrue(exp.id)

    def test_experiment_auto_created_at(self):
        """Experiment generates created_at if not provided."""
        exp = Experiment(name="test")
        self.assertTrue(exp.created_at)

    def test_experiment_serialisation(self):
        """Experiment to_dict / from_dict round-trip."""
        exp = Experiment(
            id="exp-1", name="test",
            control_template_id="c1", variant_template_id="v1",
            min_samples=5, status="completed", winner="variant",
        )
        d = exp.to_dict()
        exp2 = Experiment.from_dict(d)
        self.assertEqual(exp2.id, "exp-1")
        self.assertEqual(exp2.name, "test")
        self.assertEqual(exp2.min_samples, 5)
        self.assertEqual(exp2.winner, "variant")

    def test_experiment_result_serialisation(self):
        """ExperimentResult to_dict preserves fields."""
        er = ExperimentResult(
            experiment_id="exp-1",
            control_samples=10, variant_samples=10,
            control_success_rate=0.3, variant_success_rate=0.9,
            is_significant=True, p_value=0.01,
            winner="variant",
        )
        d = er.to_dict()
        self.assertEqual(d["experiment_id"], "exp-1")
        self.assertTrue(d["is_significant"])
        self.assertEqual(d["winner"], "variant")


# ═══════════════════════════════════════════════════════════════
#  TestMockBackend
# ═══════════════════════════════════════════════════════════════


class TestMockBackend(unittest.TestCase):
    """Test that the framework works with mock backends."""

    def test_evolver_with_mock_backend(self):
        """StrategyEvolver works with a mock backend (no save_mutation_history)."""
        mock_backend = MagicMock()
        mock_backend.save_mutation_history = MagicMock(
            side_effect=AttributeError("no such method")
        )
        store = _make_store()
        evolver = StrategyEvolver(store=store, backend=mock_backend)
        tpl = _make_template()
        store.save_template(tpl)
        result = _make_result(success=False, iterations=15, result_correct=False)
        # Should not raise even though mock backend lacks the method
        variant = evolver.evolve(tpl, result, register=True)
        self.assertIsNotNone(variant)

    def test_abtest_with_mock_backend(self):
        """ABTestFramework gracefully handles missing backend methods."""
        mock_store = MagicMock()
        mock_store._backend = MagicMock()
        mock_store.save_template = MagicMock()
        mock_store.get_template = MagicMock(return_value=None)
        mock_store.update_stats = MagicMock()
        # Backend without Phase 15 methods
        mock_backend = MagicMock()
        mock_backend.save_strategy_experiment = MagicMock(
            side_effect=AttributeError()
        )
        mock_backend.get_strategy_experiment = MagicMock(
            side_effect=AttributeError()
        )
        mock_backend.save_experiment_result = MagicMock(
            side_effect=AttributeError()
        )
        mock_backend.list_experiment_results = MagicMock(
            side_effect=AttributeError()
        )
        mock_backend.list_strategy_experiments = MagicMock(
            side_effect=AttributeError()
        )
        framework = ABTestFramework(store=mock_store, backend=mock_backend)
        # Should not crash even with missing methods
        experiments = framework.list_experiments()
        self.assertEqual(experiments, [])


# ═══════════════════════════════════════════════════════════════
#  TestIntegration
# ═══════════════════════════════════════════════════════════════


class TestIntegration(unittest.TestCase):
    """End-to-end integration tests."""

    def test_full_evolution_and_ab_test(self):
        """Full pipeline: evolve a template, then A/B test it."""
        backend = _make_backend()
        store = LoopTemplateStore(backend=backend)
        evolver = StrategyEvolver(store=store, backend=backend)
        framework = ABTestFramework(store=store, backend=backend)

        # Start with a default template
        tpl = DefaultTemplates.standard_react()
        store.save_template(tpl)

        # Evolve based on a poor execution
        result = _make_result(
            success=False, iterations=15, token_cost=800.0,
            token_budget=1000.0, errors=["timeout"],
            result_correct=False,
        )
        variant = evolver.evolve(tpl, result, register=True)
        self.assertIsNotNone(variant)
        self.assertNotEqual(variant.id, tpl.id)

        # A/B test
        exp = framework.create_experiment(
            "evolution-test", tpl, variant, min_samples=5,
        )
        # Record results: variant is better
        for i in range(5):
            framework.record_result(
                exp.id, tpl.id, success=(i < 2), iterations=8, cost=600.0
            )
            framework.record_result(
                exp.id, variant.id, success=(i < 4), iterations=5, cost=300.0
            )
        result_eval = framework.evaluate(exp.id)
        # With 2/5 vs 4/5, this may or may not be significant with only 5 samples
        # Just verify it runs without error
        self.assertIsNotNone(result_eval)
        self.assertIn(result_eval.winner, ["control", "variant", "tie"])

    def test_mutation_history_persists(self):
        """Mutation history is retrievable after evolve."""
        backend = _make_backend()
        store = LoopTemplateStore(backend=backend)
        evolver = StrategyEvolver(store=store, backend=backend)
        tpl = _make_template()
        store.save_template(tpl)
        result = _make_result(success=False, iterations=15, result_correct=False)
        variant = evolver.evolve(tpl, result, register=True)
        history = backend.list_mutation_history(template_id=variant.id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["parent_id"], tpl.id)
        self.assertIn("mutation_type", history[0])


if __name__ == "__main__":
    unittest.main()
