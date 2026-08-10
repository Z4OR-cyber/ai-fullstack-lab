"""
Suyi Quality Module — quality grading, forgetting engine, anti-pattern
memory, and loop template memory.

This package implements Phases 13–14 of the ALA (Adaptive Loop
Architecture) self-evolution system:

- :mod:`grader`        — Source/result quality grading (S–D scale).
- :mod:`forgetting`    — Exponential forgetting curve and engine.
- :mod:`anti_pattern`  — Failure pattern storage (反面记忆).
- :mod:`loop_template` — Reusable Loop execution templates (Phase 14).

Usage::

    from suyi.quality import (
        SourceQuality, ResultQuality, QualityScore, QualityAssessor,
        ForgettingCurve, ForgettingAction, ForgettingEngine, MemoryRecord,
        AntiPattern, AntiPatternStore, compute_signature,
        LoopPhase, LoopTemplate, LoopTemplateStore, DefaultTemplates,
    )

    # Grade a memory
    assessor = QualityAssessor()
    score = assessor.assess(
        source_description="official documentation",
        confirmed=True,
        evidence_count=3,
    )

    # Evaluate forgetting
    engine = ForgettingEngine(is_dry_run=True)
    record = MemoryRecord(id="m1", quality=score, content="...")
    action = engine.evaluate(record)

    # Check anti-patterns
    store = AntiPatternStore()
    store.register_from_failure("deploy to prod", error_message="OOM")
    is_known_failure = store.check_task("deploy to prod")
"""

from .grader import (
    SourceQuality,
    ResultQuality,
    QualityScore,
    QualityAssessor,
)
from .forgetting import (
    ForgettingCurve,
    ForgettingAction,
    ForgettingEngine,
    MemoryRecord,
    THRESHOLD_KEEP,
    THRESHOLD_DEGRADE,
    THRESHOLD_COMPRESS,
    THRESHOLD_PURGE,
)
from .anti_pattern import (
    AntiPattern,
    AntiPatternStore,
    compute_signature,
)
from .loop_template import (
    LoopPhase,
    LoopTemplate,
    LoopTemplateStore,
    DefaultTemplates,
    compute_task_signature,
)
from .strategy_evolver import (
    ProcessReflection,
    ExecutionResult,
    MutationType,
    MutationProposal,
    StrategyEvolver,
    Experiment,
    ExperimentResult,
    ABTestFramework,
)

__all__ = [
    # Grader
    "SourceQuality",
    "ResultQuality",
    "QualityScore",
    "QualityAssessor",
    # Forgetting
    "ForgettingCurve",
    "ForgettingAction",
    "ForgettingEngine",
    "MemoryRecord",
    "THRESHOLD_KEEP",
    "THRESHOLD_DEGRADE",
    "THRESHOLD_COMPRESS",
    "THRESHOLD_PURGE",
    # Anti-pattern
    "AntiPattern",
    "AntiPatternStore",
    "compute_signature",
    # Loop template (Phase 14)
    "LoopPhase",
    "LoopTemplate",
    "LoopTemplateStore",
    "DefaultTemplates",
    "compute_task_signature",
    # Strategy evolution (Phase 15)
    "ProcessReflection",
    "ExecutionResult",
    "MutationType",
    "MutationProposal",
    "StrategyEvolver",
    "Experiment",
    "ExperimentResult",
    "ABTestFramework",
]
