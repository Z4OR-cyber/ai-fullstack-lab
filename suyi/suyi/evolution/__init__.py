"""Suyi Phase 4 — Self-Evolution Engine.

The evolution engine enables the agent to learn from its own interactions,
automatically generate reusable skills, evaluate its performance, and
incorporate user feedback to continuously improve.

Modules:
    - **learner** — Extracts behavioral patterns from interaction records,
      updates policies, and consolidates high-frequency success patterns
      into experience rules.
    - **skill_generator** — Identifies repeated tool sequences and
      auto-generates SKILL.md files compatible with the Phase 2 SkillLoader.
    - **evaluator** — Multi-dimensional performance assessment with
      A/B version comparison and JSON report generation.
    - **feedback** — Collects explicit (thumbs up/down + text) and implicit
      (completion, retries, duration) feedback signals, passing them to
      the learner for policy updates.

Architecture::

    ┌─────────────┐     ┌──────────────┐     ┌────────────────┐
    │ Interaction │────▶│   Learner    │────▶│ SkillGenerator │
    │   Records   │     │ (patterns)   │     │  (new skills)  │
    └──────┬──────┘     └──────┬───────┘     └───────┬────────┘
           │                   │                     │
           ▼                   ▼                     ▼
    ┌─────────────┐     ┌──────────────┐     ┌────────────────┐
    │  Feedback   │────▶│  Evaluator   │     │  Validated     │
    │  Collector  │     │ (metrics)    │     │  Skills        │
    └─────────────┘     └──────────────┘     └────────────────┘

Quick start::

    from suyi.evolution import (
        LearningEngine, SkillGenerator, BehaviorEvaluator,
        FeedbackCollector, EvolutionOrchestrator,
    )

    engine = LearningEngine()
    engine.record_interaction(record)
    patterns = engine.extract_patterns()
    engine.update_policy()

    generator = SkillGenerator()
    generator.generate_from_patterns(patterns)

    evaluator = BehaviorEvaluator()
    report = evaluator.evaluate_batch(interactions)
"""

from .learner import (
    InteractionRecord,
    Pattern,
    BehaviorPolicy,
    LearningEngine,
)
from .skill_generator import (
    ToolSequence,
    GeneratedSkill,
    SkillGenerator,
)
from .evaluator import (
    EvaluationMetrics,
    EvaluationReport,
    BehaviorEvaluator,
)
from .feedback import (
    Feedback,
    FeedbackSignal,
    FeedbackCollector,
)
from .orchestrator import EvolutionOrchestrator

__all__ = [
    # Learner
    "InteractionRecord",
    "Pattern",
    "BehaviorPolicy",
    "LearningEngine",
    # Skill Generator
    "ToolSequence",
    "GeneratedSkill",
    "SkillGenerator",
    # Evaluator
    "EvaluationMetrics",
    "EvaluationReport",
    "BehaviorEvaluator",
    # Feedback
    "Feedback",
    "FeedbackSignal",
    "FeedbackCollector",
    # Orchestrator
    "EvolutionOrchestrator",
]
