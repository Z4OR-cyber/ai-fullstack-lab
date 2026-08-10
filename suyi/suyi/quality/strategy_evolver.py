"""
Strategy Evolver — automated loop-template mutation and A/B testing.

This module implements Phase 15 of the ALA (Adaptive Loop Architecture)
self-evolution system.  While Phase 14 stored reusable Loop execution
templates, Phase 15 lets the agent **improve** them automatically:

1.  **ProcessReflection** — five-dimensional self-assessment of a
    single loop execution (efficiency, accuracy, cost, robustness,
    adaptability).  Each dimension is scored 0–1 and combined into a
    weighted composite score with a human-readable summary.

2.  **StrategyEvolver** — analyses an execution result, proposes a
    mutation to improve the weakest dimension, applies it to produce a
    new template variant, and registers the variant via
    :meth:`LoopTemplateStore.create_variant`.

    Six mutation operations are supported::

        ADD_PHASE          — insert a new phase (e.g. a verify step)
        REMOVE_PHASE       — drop a redundant phase
        REORDER_PHASES     — rearrange phase ordering
        ADD_TOOL           — add a tool to a phase / template
        REMOVE_TOOL        — remove an unnecessary tool
        ADJUST_REFLECTION  — modify reflection points

3.  **ABTestFramework** — A/B testing framework that compares a
    control template against a variant.  Uses a two-proportion z-test
    (normal approximation) and Wilson score intervals to judge
    statistical significance.  Winners are auto-promoted (quality
    score raised); losers are auto-demoted.

Statistical methods
--------------------

The module implements two independent significance tests using **only
the Python standard library** (no scipy / numpy required):

- **Two-proportion z-test** — compares the success rates of two
  groups.  Uses the pooled-proportion standard error and the normal
  CDF (via ``math.erf``).

- **Wilson score interval overlap** — constructs a Wilson interval
  for each group's success rate; if the intervals do not overlap the
  difference is significant at the chosen confidence level (default
  95 %, z = 1.96).

A result is considered significant when *either* test confirms it.
"""

from __future__ import annotations

import copy
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .grader import QualityScore, QualityAssessor, ResultQuality, SourceQuality
from .loop_template import (
    LoopPhase,
    LoopTemplate,
    LoopTemplateStore,
    VALID_PHASE_NAMES,
    compute_task_signature,
)


# ═══════════════════════════════════════════════════════════════
#  Statistical helpers (pure stdlib)
# ═══════════════════════════════════════════════════════════════


def _normal_cdf(x: float) -> float:
    """Standard normal cumulative distribution function.

    Uses ``math.erf`` — available since Python 3.2.
    """
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _wilson_interval(
    successes: int,
    n: int,
    z: float = 1.96,
) -> Tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Args:
        successes: Number of successes.
        n:         Total trials.
        z:         Z-score for the desired confidence (1.96 → 95 %).

    Returns:
        ``(lower, upper)`` — the Wilson score interval bounds.
    """
    if n <= 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    spread = z * math.sqrt(
        p * (1.0 - p) / n + z * z / (4.0 * n * n)
    ) / denom
    lower = max(0.0, center - spread)
    upper = min(1.0, center + spread)
    return (round(lower, 6), round(upper, 6))


def _two_proportion_z_test(
    successes1: int,
    n1: int,
    successes2: int,
    n2: int,
) -> Tuple[float, bool]:
    """Two-proportion z-test (two-tailed, α = 0.05).

    Compares the success rates of two independent groups.  Uses the
    pooled-proportion standard error and the normal CDF.

    Args:
        successes1: Successes in group 1 (control).
        n1:         Trials in group 1.
        successes2: Successes in group 2 (variant).
        n2:         Trials in group 2.

    Returns:
        ``(p_value, is_significant)`` — the two-tailed p-value and
        whether it is below 0.05.
    """
    if n1 < 2 or n2 < 2:
        return (1.0, False)

    p1 = successes1 / n1
    p2 = successes2 / n2

    # Edge case: both rates identical → not significant
    if p1 == p2:
        return (1.0, False)

    # Pooled proportion
    p_pool = (successes1 + successes2) / (n1 + n2)

    # If pooled proportion is 0 or 1, variance is 0 → can't test
    if p_pool == 0.0 or p_pool == 1.0:
        # Fall back to unpooled test
        var1 = p1 * (1.0 - p1) / max(n1, 1)
        var2 = p2 * (1.0 - p2) / max(n2, 1)
        se = math.sqrt(var1 + var2)
        if se == 0:
            return (1.0, False)
        z = abs(p1 - p2) / se
    else:
        se = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n2))
        if se == 0:
            return (1.0, False)
        z = abs(p1 - p2) / se

    p_value = 2.0 * (1.0 - _normal_cdf(z))
    return (round(p_value, 6), p_value < 0.05)


def _wilson_overlap_test(
    successes1: int,
    n1: int,
    successes2: int,
    n2: int,
    z: float = 1.96,
) -> bool:
    """Wilson interval overlap test.

    Returns ``True`` if the Wilson intervals **do not** overlap,
    indicating a significant difference.

    Args:
        successes1, n1: Group 1 stats.
        successes2, n2: Group 2 stats.
        z:              Z-score (1.96 → 95 %).

    Returns:
        ``True`` if intervals do not overlap (significant).
    """
    lo1, hi1 = _wilson_interval(successes1, n1, z)
    lo2, hi2 = _wilson_interval(successes2, n2, z)
    # No overlap → significant
    return hi1 < lo2 or hi2 < lo1


# ═══════════════════════════════════════════════════════════════
#  ExecutionResult dataclass
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExecutionResult:
    """Result of executing a Loop template on a real task.

    Captures everything :class:`StrategyEvolver` needs to produce a
    :class:`ProcessReflection`.

    Attributes:
        success:            Whether the task succeeded.
        iterations:         Number of loop iterations actually used.
        expected_iterations: Expected iterations (defaults to
                             ``template.max_iterations`` if not set).
        token_cost:         Total token cost incurred.
        token_budget:       Token budget for the task.
        errors:             List of error messages encountered.
        tools_used:         Tools actually called during execution.
        tools_available:    Tools that were available.
        result_correct:     Whether the final result was correct
                             (defaults to ``success`` if not set).
    """

    success: bool = True
    iterations: int = 1
    expected_iterations: Optional[int] = None
    token_cost: float = 0.0
    token_budget: float = 1000.0
    errors: List[str] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    tools_available: List[str] = field(default_factory=list)
    result_correct: Optional[bool] = None

    @property
    def is_correct(self) -> bool:
        """Whether the result was correct (falls back to ``success``)."""
        return self.result_correct if self.result_correct is not None else self.success

    @property
    def error_count(self) -> int:
        """Number of errors encountered."""
        return len(self.errors)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "iterations": self.iterations,
            "expected_iterations": self.expected_iterations,
            "token_cost": self.token_cost,
            "token_budget": self.token_budget,
            "errors": list(self.errors),
            "tools_used": list(self.tools_used),
            "tools_available": list(self.tools_available),
            "result_correct": self.result_correct,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionResult":
        return cls(
            success=data.get("success", True),
            iterations=int(data.get("iterations", 1)),
            expected_iterations=data.get("expected_iterations"),
            token_cost=float(data.get("token_cost", 0.0)),
            token_budget=float(data.get("token_budget", 1000.0)),
            errors=list(data.get("errors", [])),
            tools_used=list(data.get("tools_used", [])),
            tools_available=list(data.get("tools_available", [])),
            result_correct=data.get("result_correct"),
        )


# ═══════════════════════════════════════════════════════════════
#  ProcessReflection dataclass
# ═══════════════════════════════════════════════════════════════


@dataclass
class ProcessReflection:
    """Five-dimensional process reflection of a loop execution.

    Each dimension is scored in [0, 1]:

    - **efficiency**   — how well iterations matched expectations.
    - **accuracy**     — whether the result was correct.
    - **cost**         — token consumption vs budget.
    - **robustness**   — exception / error handling performance.
    - **adaptability** — tool selection appropriateness.

    The **composite_score** is a weighted average.  Weights default to::

        accuracy     0.30
        efficiency   0.20
        robustness   0.20
        cost         0.15
        adaptability 0.15

    Attributes:
        efficiency:           Efficiency score [0, 1].
        accuracy:             Accuracy score [0, 1].
        cost:                 Cost score [0, 1].
        robustness:           Robustness score [0, 1].
        adaptability:         Adaptability score [0, 1].
        weights:              Custom weight overrides.
        raw_metrics:          The raw execution metrics used.
        notes:                Additional textual notes.
    """

    efficiency: float = 0.5
    accuracy: float = 0.5
    cost: float = 0.5
    robustness: float = 0.5
    adaptability: float = 0.5
    weights: Dict[str, float] = field(default_factory=lambda: {
        "efficiency": 0.20,
        "accuracy": 0.30,
        "cost": 0.15,
        "robustness": 0.20,
        "adaptability": 0.15,
    })
    raw_metrics: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    # ------------------------------------------------------------------
    #  Composite score
    # ------------------------------------------------------------------
    @property
    def composite_score(self) -> float:
        """Weighted average of all five dimensions."""
        total = 0.0
        for dim, weight in self.weights.items():
            total += getattr(self, dim, 0.0) * weight
        return round(max(0.0, min(1.0, total)), 4)

    @property
    def weakest_dimension(self) -> str:
        """Name of the lowest-scoring dimension."""
        dims = ["efficiency", "accuracy", "cost", "robustness", "adaptability"]
        return min(dims, key=lambda d: getattr(self, d, 1.0))

    @property
    def strongest_dimension(self) -> str:
        """Name of the highest-scoring dimension."""
        dims = ["efficiency", "accuracy", "cost", "robustness", "adaptability"]
        return max(dims, key=lambda d: getattr(self, d, 0.0))

    # ------------------------------------------------------------------
    #  Summary
    # ------------------------------------------------------------------
    @property
    def summary(self) -> str:
        """Human-readable reflection summary."""
        lines: List[str] = []
        lines.append(
            f"Process Reflection — Composite: {self.composite_score:.2f}"
        )
        lines.append(
            f"  efficiency={self.efficiency:.2f}  "
            f"accuracy={self.accuracy:.2f}  "
            f"cost={self.cost:.2f}  "
            f"robustness={self.robustness:.2f}  "
            f"adaptability={self.adaptability:.2f}"
        )

        if self.accuracy < 0.5:
            lines.append("  ⚠ Accuracy below threshold — result may be incorrect.")
        if self.efficiency < 0.5:
            lines.append("  ⚠ Efficiency below threshold — too many iterations.")
        if self.cost < 0.5:
            lines.append("  ⚠ Cost above budget — token consumption too high.")
        if self.robustness < 0.5:
            lines.append("  ⚠ Robustness below threshold — errors encountered.")
        if self.adaptability < 0.5:
            lines.append("  ⚠ Adaptability below threshold — poor tool selection.")

        lines.append(f"  Weakest dimension: {self.weakest_dimension}")
        if self.notes:
            lines.append(f"  Notes: {self.notes}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    #  Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "efficiency": round(self.efficiency, 4),
            "accuracy": round(self.accuracy, 4),
            "cost": round(self.cost, 4),
            "robustness": round(self.robustness, 4),
            "adaptability": round(self.adaptability, 4),
            "composite_score": self.composite_score,
            "weakest_dimension": self.weakest_dimension,
            "strongest_dimension": self.strongest_dimension,
            "weights": dict(self.weights),
            "raw_metrics": dict(self.raw_metrics),
            "notes": self.notes,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessReflection":
        return cls(
            efficiency=float(data.get("efficiency", 0.5)),
            accuracy=float(data.get("accuracy", 0.5)),
            cost=float(data.get("cost", 0.5)),
            robustness=float(data.get("robustness", 0.5)),
            adaptability=float(data.get("adaptability", 0.5)),
            weights=data.get("weights", {}),
            raw_metrics=data.get("raw_metrics", {}),
            notes=data.get("notes", ""),
        )

    def __repr__(self) -> str:
        return (
            f"ProcessReflection(composite={self.composite_score:.2f}, "
            f"eff={self.efficiency:.2f}, acc={self.accuracy:.2f}, "
            f"cost={self.cost:.2f}, rob={self.robustness:.2f}, "
            f"adapt={self.adaptability:.2f})"
        )


# ═══════════════════════════════════════════════════════════════
#  MutationType enum
# ═══════════════════════════════════════════════════════════════


class MutationType(Enum):
    """Types of mutation operations applicable to a Loop template."""

    ADD_PHASE = "ADD_PHASE"
    REMOVE_PHASE = "REMOVE_PHASE"
    REORDER_PHASES = "REORDER_PHASES"
    ADD_TOOL = "ADD_TOOL"
    REMOVE_TOOL = "REMOVE_TOOL"
    ADJUST_REFLECTION = "ADJUST_REFLECTION"


# ═══════════════════════════════════════════════════════════════
#  MutationProposal dataclass
# ═══════════════════════════════════════════════════════════════


@dataclass
class MutationProposal:
    """A proposed mutation to a Loop template.

    Attributes:
        mutation_type:          One of :class:`MutationType`.
        description:            Human-readable description.
        target_phase_index:     Index of the phase to modify (for
                                ADD_PHASE this is the insertion point;
                                for REMOVE_PHASE the index to remove).
        new_phase:              New :class:`LoopPhase` to insert
                                (for ADD_PHASE).
        tool_name:              Tool name for ADD_TOOL / REMOVE_TOOL.
        target_phase_for_tool:  Index of the phase to add/remove the
                                tool in (None = all phases).
        new_order:              New ordering of phase indices
                                (for REORDER_PHASES).
        new_reflection_points:  New reflection points
                                (for ADJUST_REFLECTION).
        rationale:              Why this mutation is proposed.
        expected_improvement:   Expected improvement to the composite
                                score (0–1).
        target_dimension:       Which reflection dimension this
                                mutation aims to improve.
    """

    mutation_type: MutationType = MutationType.ADD_PHASE
    description: str = ""
    target_phase_index: Optional[int] = None
    new_phase: Optional[LoopPhase] = None
    tool_name: Optional[str] = None
    target_phase_for_tool: Optional[int] = None
    new_order: Optional[List[int]] = None
    new_reflection_points: Optional[List[int]] = None
    rationale: str = ""
    expected_improvement: float = 0.05
    target_dimension: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutation_type": self.mutation_type.value,
            "description": self.description,
            "target_phase_index": self.target_phase_index,
            "new_phase": self.new_phase.to_dict() if self.new_phase else None,
            "tool_name": self.tool_name,
            "target_phase_for_tool": self.target_phase_for_tool,
            "new_order": list(self.new_order) if self.new_order else None,
            "new_reflection_points": (
                list(self.new_reflection_points)
                if self.new_reflection_points is not None
                else None
            ),
            "rationale": self.rationale,
            "expected_improvement": round(self.expected_improvement, 4),
            "target_dimension": self.target_dimension,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MutationProposal":
        new_phase = None
        if data.get("new_phase"):
            new_phase = LoopPhase.from_dict(data["new_phase"])
        mt_val = data.get("mutation_type", "ADD_PHASE")
        if isinstance(mt_val, str):
            mt = MutationType(mt_val)
        else:
            mt = mt_val
        return cls(
            mutation_type=mt,
            description=data.get("description", ""),
            target_phase_index=data.get("target_phase_index"),
            new_phase=new_phase,
            tool_name=data.get("tool_name"),
            target_phase_for_tool=data.get("target_phase_for_tool"),
            new_order=data.get("new_order"),
            new_reflection_points=data.get("new_reflection_points"),
            rationale=data.get("rationale", ""),
            expected_improvement=float(data.get("expected_improvement", 0.05)),
            target_dimension=data.get("target_dimension", ""),
        )

    def __repr__(self) -> str:
        return (
            f"MutationProposal(type={self.mutation_type.value}, "
            f"desc={self.description[:50]!r}, "
            f"dim={self.target_dimension!r}, "
            f"exp_imp={self.expected_improvement:.2f})"
        )


# ═══════════════════════════════════════════════════════════════
#  StrategyEvolver
# ═══════════════════════════════════════════════════════════════


class StrategyEvolver:
    """Automated strategy evolution for Loop templates.

    The evolver:

    1.  **Analyses** an execution result to produce a
        :class:`ProcessReflection`.
    2.  **Proposes** a mutation targeting the weakest dimension.
    3.  **Applies** the mutation to create a new template variant
        (without modifying the original).
    4.  **Registers** the variant via
        :meth:`LoopTemplateStore.create_variant`.

    The evolver is stateless between calls — all state is passed
    per invocation, making it trivially mockable for testing.

    Args:
        store:    A :class:`LoopTemplateStore` for variant registration.
                  If ``None``, a new in-memory store is created.
        backend:  Optional :class:`SQLiteBackend` for mutation history.
                  If ``None``, uses the store's backend.
    """

    def __init__(
        self,
        store: Optional[LoopTemplateStore] = None,
        backend: Optional[Any] = None,
    ) -> None:
        if store is not None:
            self._store = store
        else:
            self._store = LoopTemplateStore()
        if backend is not None:
            self._backend = backend
        else:
            self._backend = self._store._backend

    # ------------------------------------------------------------------
    #  1. Analyse
    # ------------------------------------------------------------------
    def analyze_run(
        self,
        template: LoopTemplate,
        execution_result: ExecutionResult,
    ) -> ProcessReflection:
        """Analyse a single execution and produce a process reflection.

        Scores each of the five dimensions:

        - **efficiency** — based on ``iterations`` vs
          ``expected_iterations`` (or ``template.max_iterations``).
        - **accuracy** — based on whether the result was correct.
        - **cost** — based on ``token_cost`` vs ``token_budget``.
        - **robustness** — based on the number of errors.
        - **adaptability** — based on tool selection appropriateness.

        Args:
            template:         The :class:`LoopTemplate` that was executed.
            execution_result: The :class:`ExecutionResult` of the run.

        Returns:
            A :class:`ProcessReflection` with scores and summary.
        """
        result = execution_result

        # --- Efficiency ---
        expected = (
            result.expected_iterations
            if result.expected_iterations is not None
            else template.max_iterations
        )
        if expected <= 0:
            efficiency = 1.0
        else:
            ratio = result.iterations / expected
            # ratio <= 0.5 → 1.0, ratio >= 1.0 → linear decay to 0,
            # ratio >= 2.0 → 0.0
            if ratio <= 0.5:
                efficiency = 1.0
            elif ratio >= 1.0:
                # Decay 1.5× faster past the expected count
                efficiency = max(0.0, 1.0 - (ratio - 1.0) * 1.5)
            else:
                efficiency = 1.0 - (ratio - 0.5) / 0.5
            efficiency = max(0.0, min(1.0, efficiency))

        # --- Accuracy ---
        accuracy = 1.0 if result.is_correct else 0.0

        # --- Cost ---
        budget = result.token_budget
        if budget <= 0:
            cost = 0.0
        else:
            ratio = result.token_cost / budget
            if ratio <= 0.5:
                cost = 1.0
            elif ratio >= 1.0:
                cost = 0.0
            else:
                cost = 1.0 - (ratio - 0.5) / 0.5
            cost = max(0.0, min(1.0, cost))

        # --- Robustness ---
        error_count = result.error_count
        # 0 errors → 1.0, each error reduces by 0.3 (min 0.0)
        robustness = max(0.0, 1.0 - 0.3 * error_count)

        # --- Adaptability ---
        tools_used = set(result.tools_used)
        tools_available = set(result.tools_available)
        template_tools = set(template.tools)

        if not tools_used and not template_tools:
            # No tools to evaluate
            adaptability = 0.5
        elif not tools_available:
            # No available info — check if used tools match template
            if template_tools and tools_used.issubset(template_tools):
                adaptability = 1.0
            else:
                # Used tools not in template — lower score
                unknown = tools_used - template_tools
                adaptability = max(0.0, 1.0 - 0.2 * len(unknown))
        else:
            # Check: are used tools a subset of available?
            unknown_tools = tools_used - tools_available
            # Are used tools relevant (in template)?
            relevant_tools = tools_used & template_tools
            irrelevant = tools_used - template_tools

            base = 1.0
            base -= 0.2 * len(unknown_tools)   # penalty for unknown tools
            base -= 0.1 * len(irrelevant)      # penalty for irrelevant tools
            if template_tools and not relevant_tools:
                base -= 0.3  # didn't use any template tools
            adaptability = max(0.0, min(1.0, base))

        # Build notes
        notes_parts: List[str] = []
        if efficiency < 0.5:
            notes_parts.append(
                f"Used {result.iterations}/{expected} iterations"
            )
        if cost < 0.5:
            notes_parts.append(
                f"Cost {result.token_cost}/{budget} tokens"
            )
        if error_count > 0:
            notes_parts.append(f"{error_count} error(s)")
        if not tools_used:
            notes_parts.append("No tools used")

        return ProcessReflection(
            efficiency=round(efficiency, 4),
            accuracy=round(accuracy, 4),
            cost=round(cost, 4),
            robustness=round(robustness, 4),
            adaptability=round(adaptability, 4),
            raw_metrics=result.to_dict(),
            notes="; ".join(notes_parts) if notes_parts else "",
        )

    # ------------------------------------------------------------------
    #  2. Propose mutation
    # ------------------------------------------------------------------
    def propose_mutation(
        self,
        template: LoopTemplate,
        reflection: ProcessReflection,
    ) -> MutationProposal:
        """Propose a mutation targeting the weakest reflection dimension.

        The proposal logic maps weak dimensions to appropriate mutations:

        - **accuracy** < 0.5 → ``ADD_PHASE`` (insert a verify phase
          after the last execute phase).
        - **efficiency** < 0.5 → ``ADJUST_REFLECTION`` (add a
          reflection point to catch issues early) or ``REMOVE_PHASE``
          (if there are too many phases).
        - **cost** < 0.5 → ``REMOVE_PHASE`` or ``REMOVE_TOOL`` to
          reduce overhead.
        - **robustness** < 0.5 → ``ADD_PHASE`` (insert a verify /
          reflect phase for error handling) or ``ADJUST_REFLECTION``.
        - **adaptability** < 0.5 → ``ADD_TOOL`` (add a missing tool)
          or ``REMOVE_TOOL`` (remove an inappropriate tool).

        If all dimensions are ≥ 0.5, the weakest is still targeted
        for incremental improvement.

        Args:
            template:   The :class:`LoopTemplate` to improve.
            reflection: The :class:`ProcessReflection` from analysis.

        Returns:
            A :class:`MutationProposal`.
        """
        weakest = reflection.weakest_dimension
        score = getattr(reflection, weakest)

        # --- Accuracy is low → add a verify phase ---
        if weakest == "accuracy" and score < 0.6:
            # Find the index after the last execute phase
            insert_at = self._find_insert_after_execute(template)
            new_phase = LoopPhase(
                name="verify",
                action="Verify the execution result before proceeding.",
                tools=[],
                condition="verification_passed",
            )
            return MutationProposal(
                mutation_type=MutationType.ADD_PHASE,
                description=f"Add verify phase after execute (accuracy={score:.2f})",
                target_phase_index=insert_at,
                new_phase=new_phase,
                rationale=(
                    "Low accuracy suggests results are not being verified. "
                    "Adding a verify phase should catch incorrect outputs."
                ),
                expected_improvement=0.15,
                target_dimension="accuracy",
            )

        # --- Efficiency is low → add reflection or remove phase ---
        if weakest == "efficiency" and score < 0.6:
            if len(template.phases) > 4:
                # Too many phases — suggest removing a redundant one
                remove_idx = self._find_redundant_phase(template)
                if remove_idx is not None:
                    return MutationProposal(
                        mutation_type=MutationType.REMOVE_PHASE,
                        description=(
                            f"Remove redundant phase at index {remove_idx} "
                            f"(efficiency={score:.2f})"
                        ),
                        target_phase_index=remove_idx,
                        rationale=(
                            "Low efficiency with many phases suggests "
                            "redundant steps. Removing one should reduce "
                            "iteration count."
                        ),
                        expected_improvement=0.10,
                        target_dimension="efficiency",
                    )
            # Otherwise — add a reflection point
            reflect_idx = self._find_reflection_insert_point(template)
            new_points = list(template.reflection_points) + [reflect_idx]
            return MutationProposal(
                mutation_type=MutationType.ADJUST_REFLECTION,
                description=(
                    f"Add reflection point at index {reflect_idx} "
                    f"(efficiency={score:.2f})"
                ),
                new_reflection_points=new_points,
                rationale=(
                    "Adding a reflection point allows early detection of "
                    "issues, potentially reducing wasted iterations."
                ),
                expected_improvement=0.08,
                target_dimension="efficiency",
            )

        # --- Cost is high → remove phase or tool ---
        if weakest == "cost" and score < 0.6:
            if len(template.phases) > 3:
                remove_idx = self._find_redundant_phase(template)
                if remove_idx is not None:
                    return MutationProposal(
                        mutation_type=MutationType.REMOVE_PHASE,
                        description=(
                            f"Remove phase at index {remove_idx} to reduce "
                            f"token cost (cost={score:.2f})"
                        ),
                        target_phase_index=remove_idx,
                        rationale=(
                            "High cost with many phases — removing a "
                            "redundant phase reduces token consumption."
                        ),
                        expected_improvement=0.10,
                        target_dimension="cost",
                    )
            if len(template.tools) > 2:
                # Remove the last tool (least likely to be critical)
                tool_to_remove = template.tools[-1]
                return MutationProposal(
                    mutation_type=MutationType.REMOVE_TOOL,
                    description=(
                        f"Remove tool '{tool_to_remove}' to reduce cost "
                        f"(cost={score:.2f})"
                    ),
                    tool_name=tool_to_remove,
                    rationale=(
                        "High cost with many tools — removing an "
                        "unnecessary tool reduces token usage."
                    ),
                    expected_improvement=0.07,
                    target_dimension="cost",
                )

        # --- Robustness is low → add verify/reflect phase ---
        if weakest == "robustness" and score < 0.6:
            insert_at = self._find_insert_after_execute(template)
            new_phase = LoopPhase(
                name="reflect",
                action="Reflect on potential errors and adjust strategy.",
                tools=[],
                condition="always",
            )
            return MutationProposal(
                mutation_type=MutationType.ADD_PHASE,
                description=(
                    f"Add reflect phase for error handling "
                    f"(robustness={score:.2f})"
                ),
                target_phase_index=insert_at,
                new_phase=new_phase,
                rationale=(
                    "Low robustness indicates poor error handling. "
                    "Adding a reflect phase allows error recovery."
                ),
                expected_improvement=0.12,
                target_dimension="robustness",
            )

        # --- Adaptability is low → add or remove tool ---
        if weakest == "adaptability" and score < 0.6:
            # If template has no tools but there are tools in phases
            # that could be elevated — add a tool
            if not template.tools:
                # Try to find a tool from phases
                candidate_tools = set()
                for p in template.phases:
                    candidate_tools.update(p.tools)
                if candidate_tools:
                    tool = sorted(candidate_tools)[0]
                    return MutationProposal(
                        mutation_type=MutationType.ADD_TOOL,
                        description=f"Add tool '{tool}' to template (adaptability={score:.2f})",
                        tool_name=tool,
                        rationale=(
                            "Low adaptability — the template has no tools "
                            "registered. Adding one from phases improves "
                            "tool selection tracking."
                        ),
                        expected_improvement=0.10,
                        target_dimension="adaptability",
                    )
            # If there are tools but adaptability is still low,
            # try reordering phases for better tool flow
            if len(template.phases) >= 2:
                new_order = self._suggest_reorder(template)
                if new_order is not None and new_order != list(range(len(template.phases))):
                    return MutationProposal(
                        mutation_type=MutationType.REORDER_PHASES,
                        description=(
                            f"Reorder phases to {new_order} "
                            f"(adaptability={score:.2f})"
                        ),
                        new_order=new_order,
                        rationale=(
                            "Low adaptability — reordering phases may "
                            "improve tool selection flow."
                        ),
                        expected_improvement=0.08,
                        target_dimension="adaptability",
                    )

        # --- Fallback: target weakest dimension generally ---
        return self._fallback_proposal(template, reflection, weakest, score)

    # ------------------------------------------------------------------
    #  3. Apply mutation
    # ------------------------------------------------------------------
    def apply_mutation(
        self,
        template: LoopTemplate,
        proposal: MutationProposal,
    ) -> LoopTemplate:
        """Apply a mutation to produce a new template variant.

        The original template is **not** modified — a deep copy is
        made and the mutation is applied to the copy.

        Args:
            template: The original :class:`LoopTemplate`.
            proposal: The :class:`MutationProposal` to apply.

        Returns:
            A new :class:`LoopTemplate` with the mutation applied.
        """
        # Deep-copy phases and lists
        new_phases = [LoopPhase.from_dict(p.to_dict()) for p in template.phases]
        new_tools = list(template.tools)
        new_tool_order = list(template.tool_order)
        new_reflection_points = list(template.reflection_points)
        new_max_iterations = template.max_iterations
        new_mutations = list(template.mutations)

        mt = proposal.mutation_type

        if mt == MutationType.ADD_PHASE:
            new_phase = proposal.new_phase or LoopPhase(
                name="execute",
                action="Additional execution step.",
            )
            insert_at = proposal.target_phase_index
            if insert_at is None or insert_at > len(new_phases):
                insert_at = len(new_phases)
            elif insert_at < 0:
                insert_at = 0
            new_phases.insert(insert_at, new_phase)
            # Shift reflection points that are at or after the insert point
            new_reflection_points = [
                (rp + 1 if rp >= insert_at else rp)
                for rp in new_reflection_points
            ]
            mutation_desc = f"ADD_PHASE: {new_phase.name} at index {insert_at}"

        elif mt == MutationType.REMOVE_PHASE:
            idx = proposal.target_phase_index
            if idx is not None and 0 <= idx < len(new_phases):
                removed = new_phases.pop(idx)
                # Remove reflection points at the deleted index;
                # shift those after it down by 1
                new_reflection_points = [
                    (rp - 1 if rp > idx else rp)
                    for rp in new_reflection_points
                    if rp != idx
                ]
                mutation_desc = f"REMOVE_PHASE: {removed.name} at index {idx}"
            else:
                mutation_desc = "REMOVE_PHASE: no-op (invalid index)"

        elif mt == MutationType.REORDER_PHASES:
            new_order = proposal.new_order
            if new_order and len(new_order) == len(new_phases):
                # Validate all indices are present
                if sorted(new_order) == list(range(len(new_phases))):
                    new_phases = [new_phases[i] for i in new_order]
                    # Re-map reflection points
                    old_to_new = {old: new for new, old in enumerate(new_order)}
                    new_reflection_points = sorted({
                        old_to_new.get(rp, rp)
                        for rp in new_reflection_points
                    })
                    mutation_desc = f"REORDER_PHASES: {new_order}"
                else:
                    mutation_desc = "REORDER_PHASES: no-op (invalid permutation)"
            else:
                mutation_desc = "REORDER_PHASES: no-op (mismatched length)"

        elif mt == MutationType.ADD_TOOL:
            tool = proposal.tool_name
            if tool:
                if tool not in new_tools:
                    new_tools.append(tool)
                if tool not in new_tool_order:
                    new_tool_order.append(tool)
                # Optionally add to a specific phase
                phase_idx = proposal.target_phase_for_tool
                if phase_idx is not None and 0 <= phase_idx < len(new_phases):
                    if tool not in new_phases[phase_idx].tools:
                        new_phases[phase_idx].tools.append(tool)
                mutation_desc = f"ADD_TOOL: {tool}"
            else:
                mutation_desc = "ADD_TOOL: no-op (no tool name)"

        elif mt == MutationType.REMOVE_TOOL:
            tool = proposal.tool_name
            if tool:
                if tool in new_tools:
                    new_tools.remove(tool)
                if tool in new_tool_order:
                    new_tool_order.remove(tool)
                # Remove from all phases
                for phase in new_phases:
                    if tool in phase.tools:
                        phase.tools.remove(tool)
                mutation_desc = f"REMOVE_TOOL: {tool}"
            else:
                mutation_desc = "REMOVE_TOOL: no-op (no tool name)"

        elif mt == MutationType.ADJUST_REFLECTION:
            if proposal.new_reflection_points is not None:
                new_reflection_points = list(proposal.new_reflection_points)
                # Clamp to valid range
                new_reflection_points = [
                    rp for rp in new_reflection_points
                    if 0 <= rp < len(new_phases)
                ]
                mutation_desc = (
                    f"ADJUST_REFLECTION: {new_reflection_points}"
                )
            else:
                mutation_desc = "ADJUST_REFLECTION: no-op (no points)"

        else:
            mutation_desc = f"UNKNOWN: {mt}"

        new_mutations.append(mutation_desc)

        # Create the new variant
        variant = LoopTemplate(
            id=str(uuid.uuid4()),
            task_signature=template.task_signature,
            task_description=template.task_description,
            phases=new_phases,
            tools=new_tools,
            tool_order=new_tool_order,
            reflection_points=new_reflection_points,
            max_iterations=new_max_iterations,
            termination_conditions=list(template.termination_conditions),
            quality=QualityScore(
                source=template.quality.source,
                result=template.quality.result,
                confidence=template.quality.confidence,
                evidence_count=template.quality.evidence_count,
                contradiction_count=template.quality.contradiction_count,
            ),
            parent_id=template.id,
            mutations=new_mutations,
            variants=[],
            is_active=True,
        )
        return variant

    # ------------------------------------------------------------------
    #  4. Full evolution pipeline
    # ------------------------------------------------------------------
    def evolve(
        self,
        template: LoopTemplate,
        execution_result: ExecutionResult,
        register: bool = True,
    ) -> Optional[LoopTemplate]:
        """Full evolution pipeline: analyse → propose → apply → register.

        Args:
            template:         The template that was executed.
        execution_result: The result of the execution.
            register:         If ``True``, register the variant via
                              :meth:`LoopTemplateStore.create_variant`.

        Returns:
            The new variant :class:`LoopTemplate`, or ``None`` if no
            beneficial mutation could be proposed.
        """
        reflection = self.analyze_run(template, execution_result)
        proposal = self.propose_mutation(template, reflection)
        variant = self.apply_mutation(template, proposal)

        if register:
            # Register via store
            registered = self._store.create_variant(
                parent_id=template.id,
                mutations=variant.mutations,
                modified_phases=variant.phases,
                modified_tools=variant.tools,
                modified_tool_order=variant.tool_order,
                modified_max_iterations=variant.max_iterations,
                modified_reflection_points=variant.reflection_points,
            )
            if registered is not None:
                # Preserve the mutations list on the registered variant
                registered.mutations = variant.mutations
                self._store.save_template(registered)
                # Record mutation history with the registered variant's ID
                self._record_mutation(template, registered, proposal, reflection)
                return registered

        # Non-register path: record history with the local variant ID
        self._record_mutation(template, variant, proposal, reflection)
        return variant

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_insert_after_execute(template: LoopTemplate) -> int:
        """Find the index after the last 'execute' phase."""
        last_execute = -1
        for i, phase in enumerate(template.phases):
            if phase.name == "execute":
                last_execute = i
        if last_execute >= 0:
            return last_execute + 1
        return len(template.phases)

    @staticmethod
    def _find_redundant_phase(template: LoopTemplate) -> Optional[int]:
        """Find a redundant phase to remove (first non-perceive/plan phase)."""
        for i, phase in enumerate(template.phases):
            if phase.name in ("verify", "reflect") and i > 0:
                # Don't remove if it's the only phase of its kind
                count = sum(1 for p in template.phases if p.name == phase.name)
                if count > 1:
                    return i
        # If no redundant verify/reflect, look for duplicate execute phases
        execute_indices = [
            i for i, p in enumerate(template.phases) if p.name == "execute"
        ]
        if len(execute_indices) > 1:
            return execute_indices[-1]  # remove the last execute
        return None

    @staticmethod
    def _find_reflection_insert_point(template: LoopTemplate) -> int:
        """Find a good point to add a reflection point."""
        # Prefer after the execute phase
        for i, phase in enumerate(template.phases):
            if phase.name == "execute" and i not in template.reflection_points:
                return i
        # Fallback: after the last phase
        return max(0, len(template.phases) - 1)

    @staticmethod
    def _suggest_reorder(template: LoopTemplate) -> Optional[List[int]]:
        """Suggest a reordering of phases.

        Moves reflect phases earlier and verify phases after execute.
        """
        if len(template.phases) < 2:
            return None

        order = list(range(len(template.phases)))

        # Try: perceive, plan, execute, verify, reflect
        priority = {"perceive": 0, "plan": 1, "execute": 2, "verify": 3, "reflect": 4}
        sorted_order = sorted(
            order,
            key=lambda i: priority.get(template.phases[i].name, 5),
        )
        if sorted_order != order:
            return sorted_order
        # If already sorted, suggest a simple swap
        if len(order) >= 2:
            swapped = list(order)
            swapped[0], swapped[1] = swapped[1], swapped[0]
            return swapped
        return None

    @staticmethod
    def _fallback_proposal(
        template: LoopTemplate,
        reflection: ProcessReflection,
        weakest: str,
        score: float,
    ) -> MutationProposal:
        """Generate a fallback proposal for incremental improvement."""
        # If reflection points can be added, suggest ADJUST_REFLECTION
        if len(template.phases) > 0:
            reflect_idx = StrategyEvolver._find_reflection_insert_point(template)
            if reflect_idx not in template.reflection_points:
                new_points = list(template.reflection_points) + [reflect_idx]
                return MutationProposal(
                    mutation_type=MutationType.ADJUST_REFLECTION,
                    description=(
                        f"Add reflection point at {reflect_idx} "
                        f"to improve {weakest} (score={score:.2f})"
                    ),
                    new_reflection_points=new_points,
                    rationale=(
                        f"Incremental improvement: adding a reflection "
                        f"point to address the weakest dimension ({weakest})."
                    ),
                    expected_improvement=0.05,
                    target_dimension=weakest,
                )

        # Ultimate fallback: add a verify phase
        insert_at = len(template.phases)
        return MutationProposal(
            mutation_type=MutationType.ADD_PHASE,
            description=f"Add verify phase for {weakest} improvement",
            target_phase_index=insert_at,
            new_phase=LoopPhase(
                name="verify",
                action="Verify the current state and results.",
            ),
            rationale=(
                f"No specific mutation matched — adding a verify phase "
                f"as a general improvement for {weakest}."
            ),
            expected_improvement=0.03,
            target_dimension=weakest,
        )

    def _record_mutation(
        self,
        parent: LoopTemplate,
        variant: LoopTemplate,
        proposal: MutationProposal,
        reflection: ProcessReflection,
    ) -> None:
        """Record a mutation in the mutation_history table."""
        mutation_data = {
            "template_id": variant.id,
            "parent_id": parent.id,
            "mutation_type": proposal.mutation_type.value,
            "description": proposal.description,
            "rationale": proposal.rationale,
            "expected_improvement": proposal.expected_improvement,
            "reflection_composite": reflection.composite_score,
            "target_dimension": proposal.target_dimension,
            "reflection_details": json.dumps(reflection.to_dict(), ensure_ascii=False),
            "proposal_details": json.dumps(proposal.to_dict(), ensure_ascii=False),
        }
        try:
            self._backend.save_mutation_history(mutation_data)
        except AttributeError:
            # Backend may not have the method yet (e.g., mock backend)
            pass

    def __repr__(self) -> str:
        return f"StrategyEvolver(store={self._store!r})"


# ═══════════════════════════════════════════════════════════════
#  Experiment dataclasses
# ═══════════════════════════════════════════════════════════════


@dataclass
class Experiment:
    """An A/B test experiment comparing two templates.

    Attributes:
        id:                   Unique experiment ID.
        name:                 Human-readable experiment name.
        control_template_id:  Control (baseline) template ID.
        variant_template_id:  Variant (experimental) template ID.
        min_samples:           Minimum samples per group before
                               evaluation is meaningful.
        status:               ``"running"``, ``"completed"``, or
                               ``"cancelled"``.
        winner:               ``"control"``, ``"variant"``, ``"tie"``,
                               or ``None`` (not yet evaluated).
        created_at:           ISO timestamp.
        completed_at:         ISO timestamp (when completed).
    """

    id: str = ""
    name: str = ""
    control_template_id: str = ""
    variant_template_id: str = ""
    min_samples: int = 10
    status: str = "running"
    winner: Optional[str] = None
    created_at: str = ""
    completed_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "control_template_id": self.control_template_id,
            "variant_template_id": self.variant_template_id,
            "min_samples": self.min_samples,
            "status": self.status,
            "winner": self.winner,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Experiment":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            control_template_id=data.get("control_template_id", ""),
            variant_template_id=data.get("variant_template_id", ""),
            min_samples=int(data.get("min_samples", 10)),
            status=data.get("status", "running"),
            winner=data.get("winner"),
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at"),
        )

    def __repr__(self) -> str:
        return (
            f"Experiment(id={self.id[:8]}, name={self.name!r}, "
            f"status={self.status}, winner={self.winner})"
        )


@dataclass
class ExperimentResult:
    """Result of evaluating an A/B test experiment.

    Attributes:
        experiment_id:        The experiment ID.
        control_samples:      Number of control trials.
        variant_samples:      Number of variant trials.
        control_success_rate: Control success rate [0, 1].
        variant_success_rate: Variant success rate [0, 1].
        control_avg_cost:    Average cost per control trial.
        variant_avg_cost:    Average cost per variant trial.
        control_avg_iterations: Average iterations per control trial.
        variant_avg_iterations: Average iterations per variant trial.
        is_significant:       Whether the difference is statistically
                               significant.
        p_value:              Z-test p-value (two-tailed).
        wilson_significant:   Whether Wilson intervals confirm
                               significance.
        winner:               ``"control"``, ``"variant"``, or ``"tie"``.
        message:              Human-readable summary.
    """

    experiment_id: str = ""
    control_samples: int = 0
    variant_samples: int = 0
    control_success_rate: float = 0.0
    variant_success_rate: float = 0.0
    control_avg_cost: float = 0.0
    variant_avg_cost: float = 0.0
    control_avg_iterations: float = 0.0
    variant_avg_iterations: float = 0.0
    is_significant: bool = False
    p_value: float = 1.0
    wilson_significant: bool = False
    winner: str = "tie"
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "control_samples": self.control_samples,
            "variant_samples": self.variant_samples,
            "control_success_rate": round(self.control_success_rate, 4),
            "variant_success_rate": round(self.variant_success_rate, 4),
            "control_avg_cost": round(self.control_avg_cost, 4),
            "variant_avg_cost": round(self.variant_avg_cost, 4),
            "control_avg_iterations": round(self.control_avg_iterations, 4),
            "variant_avg_iterations": round(self.variant_avg_iterations, 4),
            "is_significant": self.is_significant,
            "p_value": self.p_value,
            "wilson_significant": self.wilson_significant,
            "winner": self.winner,
            "message": self.message,
        }

    def __repr__(self) -> str:
        return (
            f"ExperimentResult(exp={self.experiment_id[:8]}, "
            f"ctrl={self.control_success_rate:.2f}({self.control_samples}), "
            f"var={self.variant_success_rate:.2f}({self.variant_samples}), "
            f"sig={self.is_significant}, winner={self.winner})"
        )


# ═══════════════════════════════════════════════════════════════
#  ABTestFramework
# ═══════════════════════════════════════════════════════════════


class ABTestFramework:
    """A/B testing framework for Loop template variants.

    Compares a control template against a variant by collecting
    execution results from both and applying statistical tests to
    determine if the variant is significantly better or worse.

    Statistical methods (pure stdlib):

    - **Two-proportion z-test** — pooled-proportion SE + normal CDF.
    - **Wilson score interval overlap** — non-overlapping intervals
      indicate significance at the chosen confidence level.

    A result is significant when *either* test confirms it.

    When a variant wins, its quality score is auto-promoted
    (confidence increased, result upgraded).  When it loses, it is
    auto-demoted (confidence decreased, result potentially downgraded).

    Args:
        store:    A :class:`LoopTemplateStore` for template access.
        backend:  Optional :class:`SQLiteBackend` for experiment
                  persistence.  If ``None``, uses the store's backend.
    """

    #: Significance level (α).
    ALPHA: float = 0.05

    #: Z-score for 95 % confidence.
    Z_SCORE: float = 1.96

    #: Amount to adjust confidence on win/loss.
    CONFIDENCE_DELTA: float = 0.1

    def __init__(
        self,
        store: Optional[LoopTemplateStore] = None,
        backend: Optional[Any] = None,
    ) -> None:
        if store is not None:
            self._store = store
        else:
            self._store = LoopTemplateStore()
        if backend is not None:
            self._backend = backend
        else:
            self._backend = self._store._backend

    # ------------------------------------------------------------------
    #  Create experiment
    # ------------------------------------------------------------------
    def create_experiment(
        self,
        name: str,
        control_template: LoopTemplate,
        variant_template: LoopTemplate,
        min_samples: int = 10,
    ) -> Experiment:
        """Create a new A/B test experiment.

        Both templates are saved to the store (if not already saved).

        Args:
            name:              Experiment name.
            control_template:  The control (baseline) template.
            variant_template:  The variant (experimental) template.
            min_samples:        Minimum samples per group.

        Returns:
            The created :class:`Experiment`.
        """
        # Ensure both templates are saved
        self._store.save_template(control_template)
        self._store.save_template(variant_template)

        experiment = Experiment(
            name=name,
            control_template_id=control_template.id,
            variant_template_id=variant_template.id,
            min_samples=min_samples,
        )

        # Persist to backend
        try:
            self._backend.save_strategy_experiment(experiment.to_dict())
        except AttributeError:
            pass  # mock backend without the method

        return experiment

    # ------------------------------------------------------------------
    #  Record result
    # ------------------------------------------------------------------
    def record_result(
        self,
        experiment_id: str,
        template_id: str,
        success: bool,
        iterations: int,
        cost: float,
    ) -> None:
        """Record a single trial result for an experiment.

        Args:
            experiment_id: The experiment's ID.
            template_id:    The template that was used (control or variant).
            success:        Whether the trial succeeded.
            iterations:     Number of iterations used.
            cost:           Token cost of the trial.
        """
        result_data = {
            "experiment_id": experiment_id,
            "template_id": template_id,
            "success": int(success),
            "iterations": iterations,
            "cost": cost,
        }
        try:
            self._backend.save_experiment_result(result_data)
        except AttributeError:
            pass  # mock backend

        # Also update template stats
        self._store.update_stats(template_id, success, iterations, cost)

    # ------------------------------------------------------------------
    #  Evaluate
    # ------------------------------------------------------------------
    def evaluate(self, experiment_id: str) -> ExperimentResult:
        """Evaluate an experiment and determine the winner.

        Collects all recorded results for both the control and variant
        templates, computes success rates and statistics, and determines
        if there is a statistically significant difference.

        If the result is significant:

        - **Variant wins** → variant's quality is promoted (confidence
          raised, result upgraded).
        - **Control wins** → variant's quality is demoted (confidence
          lowered).

        The experiment status is set to ``"completed"``.

        Args:
            experiment_id: The experiment's ID.

        Returns:
            An :class:`ExperimentResult` with statistics and verdict.
        """
        # Get experiment
        exp = self._get_experiment(experiment_id)
        if exp is None:
            return ExperimentResult(
                experiment_id=experiment_id,
                message="Experiment not found.",
            )

        # Get results for each group
        control_results = self._get_results(experiment_id, exp.control_template_id)
        variant_results = self._get_results(experiment_id, exp.variant_template_id)

        control_n = len(control_results)
        variant_n = len(variant_results)

        # Compute success rates
        control_successes = sum(1 for r in control_results if r.get("success"))
        variant_successes = sum(1 for r in variant_results if r.get("success"))

        control_rate = control_successes / control_n if control_n > 0 else 0.0
        variant_rate = variant_successes / variant_n if variant_n > 0 else 0.0

        # Compute averages
        control_avg_cost = (
            sum(r.get("cost", 0.0) for r in control_results) / control_n
            if control_n > 0 else 0.0
        )
        variant_avg_cost = (
            sum(r.get("cost", 0.0) for r in variant_results) / variant_n
            if variant_n > 0 else 0.0
        )
        control_avg_iter = (
            sum(r.get("iterations", 0) for r in control_results) / control_n
            if control_n > 0 else 0.0
        )
        variant_avg_iter = (
            sum(r.get("iterations", 0) for r in variant_results) / variant_n
            if variant_n > 0 else 0.0
        )

        # Check minimum samples
        min_samples = exp.min_samples
        if control_n < min_samples or variant_n < min_samples:
            return ExperimentResult(
                experiment_id=experiment_id,
                control_samples=control_n,
                variant_samples=variant_n,
                control_success_rate=control_rate,
                variant_success_rate=variant_rate,
                control_avg_cost=control_avg_cost,
                variant_avg_cost=variant_avg_cost,
                control_avg_iterations=control_avg_iter,
                variant_avg_iterations=variant_avg_iter,
                is_significant=False,
                p_value=1.0,
                wilson_significant=False,
                winner="tie",
                message=(
                    f"Insufficient samples: control={control_n}, "
                    f"variant={variant_n} (need {min_samples} each)."
                ),
            )

        # Statistical tests
        p_value, z_significant = _two_proportion_z_test(
            control_successes, control_n,
            variant_successes, variant_n,
        )
        wilson_sig = _wilson_overlap_test(
            control_successes, control_n,
            variant_successes, variant_n,
            self.Z_SCORE,
        )

        is_significant = z_significant or wilson_sig

        # Determine winner
        if is_significant:
            if variant_rate > control_rate:
                winner = "variant"
                self._promote_variant(exp.variant_template_id)
            elif control_rate > variant_rate:
                winner = "control"
                self._demote_variant(exp.variant_template_id)
            else:
                winner = "tie"
        else:
            winner = "tie"

        # Build message
        if is_significant:
            if winner == "variant":
                msg = (
                    f"Variant wins: {variant_rate:.1%} vs {control_rate:.1%} "
                    f"(p={p_value:.4f}, Wilson={wilson_sig}). "
                    f"Variant promoted."
                )
            elif winner == "control":
                msg = (
                    f"Control wins: {control_rate:.1%} vs {variant_rate:.1%} "
                    f"(p={p_value:.4f}, Wilson={wilson_sig}). "
                    f"Variant demoted."
                )
            else:
                msg = (
                    f"Tie: both at {control_rate:.1%} "
                    f"(p={p_value:.4f}, Wilson={wilson_sig})."
                )
        else:
            msg = (
                f"No significant difference: control={control_rate:.1%} "
                f"({control_n} samples), variant={variant_rate:.1%} "
                f"({variant_n} samples). p={p_value:.4f}."
            )

        result = ExperimentResult(
            experiment_id=experiment_id,
            control_samples=control_n,
            variant_samples=variant_n,
            control_success_rate=control_rate,
            variant_success_rate=variant_rate,
            control_avg_cost=control_avg_cost,
            variant_avg_cost=variant_avg_cost,
            control_avg_iterations=control_avg_iter,
            variant_avg_iterations=variant_avg_iter,
            is_significant=is_significant,
            p_value=p_value,
            wilson_significant=wilson_sig,
            winner=winner,
            message=msg,
        )

        # Update experiment status
        exp.status = "completed"
        exp.winner = winner
        exp.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            self._backend.save_strategy_experiment(exp.to_dict())
        except AttributeError:
            pass

        return result

    # ------------------------------------------------------------------
    #  List / get experiments
    # ------------------------------------------------------------------
    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Retrieve an experiment by ID."""
        return self._get_experiment(experiment_id)

    def list_experiments(
        self,
        status: Optional[str] = None,
    ) -> List[Experiment]:
        """List experiments, optionally filtered by status.

        Args:
            status: Filter by status (``"running"``, ``"completed"``,
                    ``"cancelled"``).

        Returns:
            List of :class:`Experiment` objects.
        """
        try:
            rows = self._backend.list_strategy_experiments(status)
            return [Experiment.from_dict(r) for r in rows]
        except AttributeError:
            return []

    def cancel_experiment(self, experiment_id: str) -> bool:
        """Cancel an experiment (set status to ``"cancelled"``).

        Returns:
            ``True`` if the experiment was found and cancelled.
        """
        exp = self._get_experiment(experiment_id)
        if exp is None:
            return False
        exp.status = "cancelled"
        try:
            self._backend.save_strategy_experiment(exp.to_dict())
        except AttributeError:
            pass
        return True

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    def _get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Retrieve an experiment from the backend."""
        try:
            row = self._backend.get_strategy_experiment(experiment_id)
            if row is None:
                return None
            return Experiment.from_dict(row)
        except AttributeError:
            return None

    def _get_results(
        self,
        experiment_id: str,
        template_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all trial results for a specific template in an experiment."""
        try:
            return self._backend.list_experiment_results(
                experiment_id, template_id
            )
        except AttributeError:
            return []

    def _promote_variant(self, template_id: str) -> None:
        """Promote the variant's quality score (winner)."""
        template = self._store.get_template(template_id)
        if template is None:
            return

        assessor = QualityAssessor()
        new_quality = assessor.update_after_task(
            template.quality,
            success=True,
            new_evidence=1,
        )
        # Boost confidence
        boosted_confidence = min(1.0, new_quality.confidence + self.CONFIDENCE_DELTA)
        template.quality = QualityScore(
            source=new_quality.source,
            result=new_quality.result,
            confidence=boosted_confidence,
            evidence_count=new_quality.evidence_count,
            contradiction_count=new_quality.contradiction_count,
        )
        self._store.save_template(template)

    def _demote_variant(self, template_id: str) -> None:
        """Demote the variant's quality score (loser)."""
        template = self._store.get_template(template_id)
        if template is None:
            return

        assessor = QualityAssessor()
        new_quality = assessor.update_after_task(
            template.quality,
            success=False,
            new_contradictions=1,
        )
        # Reduce confidence
        reduced_confidence = max(0.0, new_quality.confidence - self.CONFIDENCE_DELTA)
        template.quality = QualityScore(
            source=new_quality.source,
            result=new_quality.result,
            confidence=reduced_confidence,
            evidence_count=new_quality.evidence_count,
            contradiction_count=new_quality.contradiction_count,
        )
        self._store.save_template(template)

    def __repr__(self) -> str:
        return f"ABTestFramework(store={self._store!r})"
