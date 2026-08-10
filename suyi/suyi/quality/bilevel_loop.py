"""
Bilevel Loop Integration — TaskLoop (inner) + EvolutionLoop (outer).

This module implements Phase 16 of the ALA (Adaptive Loop Architecture)
self-evolution system.  It combines the Phase 13–15 quality, forgetting,
template, and strategy-evolution modules into a single coherent
**bilevel control loop**:

- **Inner loop** (:class:`TaskLoop`) — executes a task by selecting the
  best matching :class:`LoopTemplate`, following its phases, reflecting
  at designated points, and producing an :class:`ExecutionLog` +
  :class:`TaskResult`.

- **Outer loop** (:class:`EvolutionLoop`) — after each task (or
  according to a configurable trigger), it performs process reflection,
  updates template statistics, runs the forgetting engine on related
  memories, proposes and applies template mutations, and evaluates any
  outstanding A/B experiments.

- **Top-level coordinator** (:class:`BilevelLoop`) — wires the two
  loops together, manages trigger evaluation, and exposes a single
  ``run(task)`` entry point.

Four trigger mechanisms
-----------------------

1.  **EVERY_TASK** — evolve after every task completion.
2.  **ACCUMULATED_N** — evolve after *N* tasks of the same signature
    have been completed since the last evolution.
3.  **PERFORMANCE_DROP** — evolve when performance drops below a
    threshold relative to the recent moving average.
4.  **SCHEDULED** — evolve at fixed time intervals.

All triggers can be combined; the :class:`TriggerEvaluator` checks each
enabled trigger and returns ``True`` if any fires.

Design principles
-----------------

- **Pure Python + stdlib** (no new external dependencies).
- **Injectable** — every component (template store, evolver, AB test
  framework, forgetting engine, anti-pattern store) can be replaced
  with a mock for testing.
- **Async-aware** — :meth:`TaskLoop.run` is ``async`` because it
  delegates to :class:`AgentLoop`; :meth:`EvolutionLoop.evolve` is
  synchronous because Phase 13–15 operations are all synchronous.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

from .grader import (
    QualityScore,
    QualityAssessor,
    ResultQuality,
    SourceQuality,
)
from .forgetting import (
    ForgettingAction,
    ForgettingEngine,
    ForgettingCurve,
    MemoryRecord,
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


# ═══════════════════════════════════════════════════════════════
#  Execution Log
# ═══════════════════════════════════════════════════════════════


def _now_iso() -> str:
    """Return an ISO-8601 UTC timestamp string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class ExecutionLogEntry:
    """A single step recorded during template-driven execution.

    Attributes:
        phase_name:   Name of the LoopPhase that produced this entry
                      (perceive / plan / execute / verify / reflect).
        action:       Human-readable description of the action taken.
        tools_used:   Tool names actually invoked in this step.
        duration:     Wall-clock duration in seconds.
        result:       Result content (truncated for logging).
        errors:       Error messages encountered (if any).
        timestamp:    ISO-8601 UTC timestamp of the entry.
        iteration:    Outer-loop iteration index (0-based).
        step_index:   Step index within the iteration (0-based).
    """

    phase_name: str = ""
    action: str = ""
    tools_used: List[str] = field(default_factory=list)
    duration: float = 0.0
    result: str = ""
    errors: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=_now_iso)
    iteration: int = 0
    step_index: int = 0

    # ------------------------------------------------------------------
    #  Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase_name": self.phase_name,
            "action": self.action,
            "tools_used": list(self.tools_used),
            "duration": round(self.duration, 6),
            "result": self.result,
            "errors": list(self.errors),
            "timestamp": self.timestamp,
            "iteration": self.iteration,
            "step_index": self.step_index,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionLogEntry":
        return cls(
            phase_name=data.get("phase_name", ""),
            action=data.get("action", ""),
            tools_used=list(data.get("tools_used", [])),
            duration=float(data.get("duration", 0.0)),
            result=data.get("result", ""),
            errors=list(data.get("errors", [])),
            timestamp=data.get("timestamp", _now_iso()),
            iteration=int(data.get("iteration", 0)),
            step_index=int(data.get("step_index", 0)),
        )

    def __repr__(self) -> str:
        return (
            f"ExecutionLogEntry(phase={self.phase_name!r}, "
            f"iter={self.iteration}, step={self.step_index}, "
            f"dur={self.duration:.3f}s, tools={self.tools_used})"
        )


@dataclass
class ExecutionLog:
    """Full execution log for a single task run.

    Attributes:
        entries:        Ordered list of :class:`ExecutionLogEntry`.
        started_at:     ISO-8601 timestamp of task start.
        completed_at:   ISO-8601 timestamp of task completion.
        total_duration:  Total wall-clock duration in seconds.
    """

    entries: List[ExecutionLogEntry] = field(default_factory=list)
    started_at: str = field(default_factory=_now_iso)
    completed_at: str = ""
    total_duration: float = 0.0

    # ------------------------------------------------------------------
    #  Mutators
    # ------------------------------------------------------------------
    def add_entry(self, entry: ExecutionLogEntry) -> None:
        """Append an entry and update ``total_duration``."""
        self.entries.append(entry)
        self.total_duration += entry.duration

    def finalize(self) -> None:
        """Set ``completed_at`` and recompute ``total_duration``."""
        self.completed_at = _now_iso()
        self.total_duration = sum(e.duration for e in self.entries)

    # ------------------------------------------------------------------
    #  Queries
    # ------------------------------------------------------------------
    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def has_errors(self) -> bool:
        return any(e.errors for e in self.entries)

    @property
    def all_tools_used(self) -> List[str]:
        """Unique tool names across all entries (preserving order)."""
        seen: set = set()
        result: List[str] = []
        for entry in self.entries:
            for t in entry.tools_used:
                if t not in seen:
                    seen.add(t)
                    result.append(t)
        return result

    @property
    def phases_executed(self) -> List[str]:
        """Unique phase names across all entries (preserving order)."""
        seen: set = set()
        result: List[str] = []
        for entry in self.entries:
            if entry.phase_name not in seen:
                seen.add(entry.phase_name)
                result.append(entry.phase_name)
        return result

    @property
    def error_entries(self) -> List[ExecutionLogEntry]:
        """Entries that recorded at least one error."""
        return [e for e in self.entries if e.errors]

    @property
    def total_errors(self) -> int:
        return sum(len(e.errors) for e in self.entries)

    @property
    def iteration_count(self) -> int:
        """Number of distinct iteration indices."""
        if not self.entries:
            return 0
        return max(e.iteration for e in self.entries) + 1

    # ------------------------------------------------------------------
    #  Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        self.finalize()
        return {
            "entries": [e.to_dict() for e in self.entries],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration": round(self.total_duration, 6),
            "entry_count": self.entry_count,
            "has_errors": self.has_errors,
            "all_tools_used": self.all_tools_used,
            "phases_executed": self.phases_executed,
            "total_errors": self.total_errors,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionLog":
        log = cls(
            entries=[
                ExecutionLogEntry.from_dict(e)
                for e in data.get("entries", [])
            ],
            started_at=data.get("started_at", _now_iso()),
            completed_at=data.get("completed_at", ""),
            total_duration=float(data.get("total_duration", 0.0)),
        )
        return log

    def __repr__(self) -> str:
        return (
            f"ExecutionLog(entries={self.entry_count}, "
            f"errors={self.total_errors}, "
            f"duration={self.total_duration:.3f}s)"
        )


# ═══════════════════════════════════════════════════════════════
#  Task Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class TaskResult:
    """Result of executing a single task through the bilevel loop.

    Attributes:
        task:             The original task string.
        template_id:      ID of the LoopTemplate used.
        template_used:    The LoopTemplate object (or ``None``).
        execution_log:    Detailed :class:`ExecutionLog`.
        quality:          :class:`QualityScore` for this result.
        related_memories: IDs of memories involved.
        success:          Whether the task succeeded.
        content:          Final answer content.
        iterations:       Number of loop iterations executed.
        token_cost:       Token cost incurred.
        errors:           List of error messages.
        reflection:       ProcessReflection (if evolution ran).
        task_signature:   Canonical task signature for matching.
    """

    task: str = ""
    template_id: str = ""
    template_used: Optional[LoopTemplate] = None
    execution_log: ExecutionLog = field(default_factory=ExecutionLog)
    quality: QualityScore = field(default_factory=QualityScore)
    related_memories: List[str] = field(default_factory=list)
    success: bool = False
    content: str = ""
    iterations: int = 0
    token_cost: float = 0.0
    errors: List[str] = field(default_factory=list)
    reflection: Optional[ProcessReflection] = None
    task_signature: str = ""

    # ------------------------------------------------------------------
    #  Derived properties
    # ------------------------------------------------------------------
    @property
    def is_successful(self) -> bool:
        """Alias for ``success``."""
        return self.success

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0 or self.execution_log.has_errors

    @property
    def all_errors(self) -> List[str]:
        """Merge task-level errors and execution-log errors."""
        combined = list(self.errors)
        for entry in self.execution_log.entries:
            combined.extend(entry.errors)
        return combined

    @property
    def tools_used(self) -> List[str]:
        """All tools used during execution."""
        return self.execution_log.all_tools_used

    @property
    def duration(self) -> float:
        """Total execution duration."""
        return self.execution_log.total_duration

    @property
    def quality_grade(self) -> str:
        """Shortcut to the quality source grade letter."""
        return self.quality.source.grade_letter

    # ------------------------------------------------------------------
    #  Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "template_id": self.template_id,
            "template_used": (
                self.template_used.to_dict()
                if self.template_used is not None
                else None
            ),
            "execution_log": self.execution_log.to_dict(),
            "quality": {
                "source": self.quality.source.name,
                "result": self.quality.result.name,
                "confidence": self.quality.confidence,
                "evidence_count": self.quality.evidence_count,
                "contradiction_count": self.quality.contradiction_count,
            },
            "related_memories": list(self.related_memories),
            "success": self.success,
            "content": self.content,
            "iterations": self.iterations,
            "token_cost": self.token_cost,
            "errors": list(self.errors),
            "reflection": (
                self.reflection.to_dict()
                if self.reflection is not None
                else None
            ),
            "task_signature": self.task_signature,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskResult":
        quality_data = data.get("quality", {})
        quality = QualityScore(
            source=(
                SourceQuality[quality_data["source"]]
                if isinstance(quality_data.get("source"), str)
                and quality_data["source"] in SourceQuality.__members__
                else SourceQuality.C
            ),
            result=(
                ResultQuality[quality_data["result"]]
                if isinstance(quality_data.get("result"), str)
                and quality_data["result"] in ResultQuality.__members__
                else ResultQuality.SPECULATIVE
            ),
            confidence=float(quality_data.get("confidence", 0.5)),
            evidence_count=int(quality_data.get("evidence_count", 0)),
            contradiction_count=int(quality_data.get("contradiction_count", 0)),
        )
        template_data = data.get("template_used")
        template_used = (
            LoopTemplate.from_dict(template_data)
            if template_data
            else None
        )
        reflection_data = data.get("reflection")
        reflection = (
            ProcessReflection.from_dict(reflection_data)
            if reflection_data
            else None
        )
        return cls(
            task=data.get("task", ""),
            template_id=data.get("template_id", ""),
            template_used=template_used,
            execution_log=ExecutionLog.from_dict(
                data.get("execution_log", {})
            ),
            quality=quality,
            related_memories=list(data.get("related_memories", [])),
            success=data.get("success", False),
            content=data.get("content", ""),
            iterations=int(data.get("iterations", 0)),
            token_cost=float(data.get("token_cost", 0.0)),
            errors=list(data.get("errors", [])),
            reflection=reflection,
            task_signature=data.get("task_signature", ""),
        )

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAIL"
        return (
            f"TaskResult({status}, task={self.task[:30]!r}, "
            f"template={self.template_id!r}, "
            f"iters={self.iterations}, cost={self.token_cost:.0f})"
        )


# ═══════════════════════════════════════════════════════════════
#  Trigger Mechanism
# ═══════════════════════════════════════════════════════════════


class TriggerType(Enum):
    """Evolution trigger types for :class:`EvolutionLoop`.

    Members:
        EVERY_TASK:      Trigger after every task completion.
        ACCUMULATED_N:   Trigger after N tasks of the same signature.
        PERFORMANCE_DROP: Trigger when performance drops below threshold.
        SCHEDULED:       Trigger at fixed time intervals.
    """

    EVERY_TASK = auto()
    ACCUMULATED_N = auto()
    PERFORMANCE_DROP = auto()
    SCHEDULED = auto()


@dataclass
class TriggerConfig:
    """Configuration for when evolution should be triggered.

    Multiple trigger types can be enabled simultaneously.  The
    :class:`TriggerEvaluator` fires evolution if *any* enabled trigger
    is satisfied.

    Attributes:
        every_task:         Whether to trigger on every task.
        accumulated_n:      Trigger after this many same-signature tasks.
        performance_drop_threshold: Relative drop (0-1) that triggers
                            evolution.  E.g. 0.15 = 15% drop.
        scheduled_interval_seconds: Minimum seconds between triggers.
        enable_every_task: Enable the EVERY_TASK trigger.
        enable_accumulated: Enable the ACCUMULATED_N trigger.
        enable_performance: Enable the PERFORMANCE_DROP trigger.
        enable_scheduled:   Enable the SCHEDULED trigger.
    """

    every_task: bool = True
    accumulated_n: int = 5
    performance_drop_threshold: float = 0.15
    scheduled_interval_seconds: float = 3600.0
    enable_every_task: bool = True
    enable_accumulated: bool = True
    enable_performance: bool = True
    enable_scheduled: bool = True

    @property
    def enabled_types(self) -> List[TriggerType]:
        """List of currently enabled trigger types."""
        types: List[TriggerType] = []
        if self.enable_every_task:
            types.append(TriggerType.EVERY_TASK)
        if self.enable_accumulated:
            types.append(TriggerType.ACCUMULATED_N)
        if self.enable_performance:
            types.append(TriggerType.PERFORMANCE_DROP)
        if self.enable_scheduled:
            types.append(TriggerType.SCHEDULED)
        return types

    def to_dict(self) -> Dict[str, Any]:
        return {
            "every_task": self.every_task,
            "accumulated_n": self.accumulated_n,
            "performance_drop_threshold": self.performance_drop_threshold,
            "scheduled_interval_seconds": self.scheduled_interval_seconds,
            "enable_every_task": self.enable_every_task,
            "enable_accumulated": self.enable_accumulated,
            "enable_performance": self.enable_performance,
            "enable_scheduled": self.enable_scheduled,
            "enabled_types": [t.name for t in self.enabled_types],
        }

    def __repr__(self) -> str:
        types = ", ".join(t.name for t in self.enabled_types)
        return f"TriggerConfig(enabled=[{types}])"


class TriggerEvaluator:
    """Evaluate whether evolution should be triggered.

    Tracks task completion history and uses :class:`TriggerConfig` to
    decide when to fire the outer evolution loop.

    The evaluator is **stateful** -- it accumulates results, signatures,
    and timestamps between calls.  Use :meth:`reset` to clear state.

    Attributes:
        config: The :class:`TriggerConfig` controlling triggers.
    """

    #: Window size for the moving-average performance baseline.
    PERF_WINDOW: int = 10

    def __init__(self, config: Optional[TriggerConfig] = None) -> None:
        self.config = config or TriggerConfig()
        self._task_count: int = 0
        self._signature_counts: Dict[str, int] = defaultdict(int)
        self._last_evolve_per_sig: Dict[str, float] = {}
        self._last_evolve_time: float = 0.0
        self._recent_success: deque = deque(maxlen=self.PERF_WINDOW)
        self._triggered_by: Optional[TriggerType] = None

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------
    def record_result(self, task_result: TaskResult) -> None:
        """Record a task result for trigger evaluation.

        Call this *before* :meth:`should_trigger`.

        Args:
            task_result: The completed :class:`TaskResult`.
        """
        self._task_count += 1
        sig = task_result.task_signature or compute_task_signature(
            task_result.task
        )
        self._signature_counts[sig] += 1
        self._recent_success.append(1.0 if task_result.success else 0.0)

    def should_trigger(self, task_result: TaskResult) -> bool:
        """Check if any enabled trigger is satisfied.

        Args:
            task_result: The just-completed task result.

        Returns:
            ``True`` if evolution should run now.
        """
        self._triggered_by = None
        sig = task_result.task_signature or compute_task_signature(
            task_result.task
        )
        now = time.time()

        # --- 1. EVERY_TASK ---
        if self.config.enable_every_task and self.config.every_task:
            self._triggered_by = TriggerType.EVERY_TASK
            return True

        # --- 2. ACCUMULATED_N ---
        if self.config.enable_accumulated:
            sig_count = self._signature_counts.get(sig, 0)
            last_evolve = self._last_evolve_per_sig.get(sig, 0)
            unevolved = sig_count - last_evolve
            if unevolved >= self.config.accumulated_n:
                self._triggered_by = TriggerType.ACCUMULATED_N
                return True

        # --- 3. PERFORMANCE_DROP ---
        if self.config.enable_performance:
            if len(self._recent_success) >= 3:
                avg = sum(self._recent_success) / len(self._recent_success)
                if avg < (1.0 - self.config.performance_drop_threshold):
                    self._triggered_by = TriggerType.PERFORMANCE_DROP
                    return True

        # --- 4. SCHEDULED ---
        if self.config.enable_scheduled:
            if now - self._last_evolve_time >= self.config.scheduled_interval_seconds:
                self._triggered_by = TriggerType.SCHEDULED
                return True

        return False

    def mark_evolved(self, task_signature: str = "") -> None:
        """Mark that an evolution cycle has completed.

        Resets the accumulated counters for the given signature and
        updates the last-evolve timestamps.

        Args:
            task_signature: The signature that was evolved.  If empty,
                            resets all signature counters.
        """
        now = time.time()
        self._last_evolve_time = now
        if task_signature:
            self._last_evolve_per_sig[task_signature] = self._signature_counts.get(
                task_signature, 0
            )
        else:
            self._last_evolve_per_sig.clear()

    @property
    def triggered_by(self) -> Optional[TriggerType]:
        """The trigger type that fired in the last :meth:`should_trigger`."""
        return self._triggered_by

    @property
    def task_count(self) -> int:
        return self._task_count

    @property
    def recent_success_rate(self) -> float:
        """Moving-average success rate over the recent window."""
        if not self._recent_success:
            return 0.0
        return sum(self._recent_success) / len(self._recent_success)

    def reset(self) -> None:
        """Clear all accumulated state."""
        self._task_count = 0
        self._signature_counts.clear()
        self._last_evolve_per_sig.clear()
        self._last_evolve_time = 0.0
        self._recent_success.clear()
        self._triggered_by = None

    def __repr__(self) -> str:
        return (
            f"TriggerEvaluator(tasks={self._task_count}, "
            f"rate={self.recent_success_rate:.2f}, "
            f"triggered_by={self._triggered_by})"
        )


# ═══════════════════════════════════════════════════════════════
#  TaskLoop -- Inner Business Loop
# ═══════════════════════════════════════════════════════════════


class TaskLoop:
    """Inner loop: execute a task using a LoopTemplate.

    Workflow::

        task -> find_best_template -> execute phases -> reflect -> TaskResult

    The TaskLoop wraps an :class:`AgentLoop` for actual LLM execution.
    When the AgentLoop supports template-driven mode (Phase 16
    modification), the template is passed through; otherwise, the
    TaskLoop falls back to standard execution and logs phases manually.

    Args:
        template_store: :class:`LoopTemplateStore` for template retrieval.
        agent_loop:     Optional :class:`AgentLoop` for execution.
                        If ``None``, simulated execution is used.
        quality_assessor: Optional :class:`QualityAssessor`.
        default_template: Optional default :class:`LoopTemplate` to use
                          when no matching template is found.
        track_related_memories: Whether to track related memory IDs.
    """

    def __init__(
        self,
        template_store: Optional[LoopTemplateStore] = None,
        agent_loop: Any = None,
        quality_assessor: Optional[QualityAssessor] = None,
        default_template: Optional[LoopTemplate] = None,
        track_related_memories: bool = True,
    ) -> None:
        self._store = template_store or LoopTemplateStore()
        self._agent_loop = agent_loop
        self._quality_assessor = quality_assessor or QualityAssessor()
        self._default_template = default_template
        self._track_related = track_related_memories
        self._related_memories: List[str] = []

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------
    async def run(self, task: str) -> TaskResult:
        """Execute a task through the template-driven inner loop.

        Steps:
            1.  Select the best matching LoopTemplate.
            2.  If no match, fall back to a default template.
            3.  Execute the task following the template phases.
            4.  Reflect at designated reflection points.
            5.  Record the execution log.
            6.  Return a :class:`TaskResult`.

        Args:
            task: The task description string.

        Returns:
            A :class:`TaskResult` with full execution metadata.
        """
        self._related_memories = []
        task_signature = compute_task_signature(task)

        # 1. Select template
        template = self._select_template(task, task_signature)

        # 2. Create execution log
        execution_log = ExecutionLog(started_at=_now_iso())

        # 3. Execute
        content, iterations, token_cost, errors = await self._execute(
            task, template, execution_log
        )

        # 4. Finalize log
        execution_log.finalize()

        # 5. Assess quality
        success = len(errors) == 0 and bool(content)
        quality = self._quality_assessor.assess(
            source_description="agent loop execution",
            success=success,
            error=len(errors) > 0,
            evidence_count=1,
        )

        # 6. Build result
        result = TaskResult(
            task=task,
            template_id=template.id,
            template_used=template,
            execution_log=execution_log,
            quality=quality,
            related_memories=list(self._related_memories) if self._track_related else [],
            success=success,
            content=content,
            iterations=iterations,
            token_cost=token_cost,
            errors=errors,
            task_signature=task_signature,
        )
        return result

    # ------------------------------------------------------------------
    #  Template Selection
    # ------------------------------------------------------------------
    def _select_template(
        self,
        task: str,
        task_signature: str,
    ) -> LoopTemplate:
        """Find the best matching template, or use a default.

        Args:
            task:            Task description.
            task_signature:  Pre-computed task signature.

        Returns:
            A :class:`LoopTemplate` (never ``None``).
        """
        # Try the store
        try:
            best = self._store.find_best_template(task, task_signature)
            if best is not None:
                return best
        except Exception:
            pass

        # Fall back to configured default
        if self._default_template is not None:
            return self._default_template

        # Ultimate fallback: standard ReAct
        return DefaultTemplates.standard_react()

    # ------------------------------------------------------------------
    #  Execution
    # ------------------------------------------------------------------
    async def _execute(
        self,
        task: str,
        template: LoopTemplate,
        log: ExecutionLog,
    ) -> Tuple[str, int, float, List[str]]:
        """Execute the task following the template phases.

        If an AgentLoop is available, delegate to it (with template if
        supported).  Otherwise, simulate execution by walking through
        the phases and producing a minimal result.

        Returns:
            ``(content, iterations, token_cost, errors)``
        """
        content = ""
        iterations = 0
        token_cost = 0.0
        errors: List[str] = []
        max_iters = template.max_iterations

        # --- Try AgentLoop with template support ---
        if self._agent_loop is not None:
            content, iterations, token_cost, errors = await self._execute_with_agent(
                task, template, log, max_iters
            )
        else:
            # --- Simulated execution (no AgentLoop) ---
            content, iterations, token_cost, errors = await self._execute_simulated(
                task, template, log, max_iters
            )

        return content, iterations, token_cost, errors

    async def _execute_with_agent(
        self,
        task: str,
        template: LoopTemplate,
        log: ExecutionLog,
        max_iters: int,
    ) -> Tuple[str, int, float, List[str]]:
        """Execute using an AgentLoop (with template if supported)."""
        loop = self._agent_loop
        content = ""
        iterations = 0
        token_cost = 0.0
        errors: List[str] = []

        # Try template-driven run
        run_with_template = getattr(loop, "run_with_template", None)
        if callable(run_with_template):
            try:
                result = await run_with_template(task, template)
                content = getattr(result, "content", "")
                iterations = getattr(result, "turns_used", 0)
                token_cost = getattr(result, "total_tokens", 0) or 0.0
                if getattr(result, "partial", False):
                    errors.append("Loop ended with partial result.")
                stop = getattr(result, "stop_reason", "natural")
                if stop == "budget_exhausted":
                    errors.append("Budget exhausted during execution.")

                # Record phases from the template
                for i, phase in enumerate(template.phases):
                    log.add_entry(ExecutionLogEntry(
                        phase_name=phase.name,
                        action=phase.action,
                        tools_used=phase.tools,
                        duration=0.0,
                        result=content[:200] if i == len(template.phases) - 1 else "",
                        errors=[],
                        iteration=0,
                        step_index=i,
                    ))
                return content, max(1, iterations), token_cost, errors
            except Exception as e:
                errors.append(f"Template-driven execution failed: {e}")

        # Fall back to standard run
        try:
            result = await loop.run(task)
            content = getattr(result, "content", "")
            iterations = getattr(result, "turns_used", 0)
            token_cost = getattr(result, "total_tokens", 0) or 0.0

            # Record a single execution entry
            log.add_entry(ExecutionLogEntry(
                phase_name="execute",
                action="Standard ReAct execution.",
                tools_used=[],
                duration=0.0,
                result=content[:200],
                errors=[],
                iteration=0,
                step_index=0,
            ))

            # Record remaining phases
            for i, phase in enumerate(template.phases):
                if phase.name == "execute":
                    continue
                log.add_entry(ExecutionLogEntry(
                    phase_name=phase.name,
                    action=phase.action,
                    tools_used=phase.tools,
                    duration=0.0,
                    result="",
                    errors=[],
                    iteration=0,
                    step_index=i,
                ))

        except Exception as e:
            errors.append(f"AgentLoop execution failed: {e}")
            content = ""

        return content, max(1, iterations), token_cost, errors

    async def _execute_simulated(
        self,
        task: str,
        template: LoopTemplate,
        log: ExecutionLog,
        max_iters: int,
    ) -> Tuple[str, int, float, List[str]]:
        """Simulate execution by walking through template phases.

        Used when no AgentLoop is available.  Each phase is recorded
        in the execution log.  At reflection points, a reflection
        entry is added.
        """
        content_parts: List[str] = []
        token_cost = 0.0
        errors: List[str] = []
        iterations = 0

        for iteration in range(max_iters):
            iterations = iteration + 1

            for step_idx, phase in enumerate(template.phases):
                t_start = time.time()

                # Simulate phase execution
                phase_result, phase_cost, phase_errors = await self._run_phase(
                    phase, task, content_parts, iteration
                )
                token_cost += phase_cost
                errors.extend(phase_errors)

                if phase_result:
                    content_parts.append(phase_result)

                # Record log entry
                t_end = time.time()
                log.add_entry(ExecutionLogEntry(
                    phase_name=phase.name,
                    action=phase.action,
                    tools_used=phase.tools,
                    duration=t_end - t_start,
                    result=phase_result[:200] if phase_result else "",
                    errors=phase_errors,
                    iteration=iteration,
                    step_index=step_idx,
                ))

            # Check reflection points
            for rp in template.reflection_points:
                if rp < len(template.phases):
                    reflection_text = await self._reflect(
                        task, content_parts, iteration
                    )
                    log.add_entry(ExecutionLogEntry(
                        phase_name="reflect",
                        action="Reflection at designated point.",
                        tools_used=[],
                        duration=0.001,
                        result=reflection_text[:200],
                        errors=[],
                        iteration=iteration,
                        step_index=rp + 1,
                    ))

            # Termination: simulated execution completes after one
            # full pass through the phases (or when content is produced)
            if content_parts:
                break

        content = "\n".join(content_parts) if content_parts else "Task completed."
        return content, iterations, token_cost, errors

    async def _run_phase(
        self,
        phase: LoopPhase,
        task: str,
        prior_content: List[str],
        iteration: int,
    ) -> Tuple[str, float, List[str]]:
        """Simulate a single phase execution.

        Returns:
            ``(result_text, token_cost, errors)``
        """
        cost = 10.0  # simulated cost per phase
        errors: List[str] = []

        if phase.name == "perceive":
            return f"Observed task: {task[:50]}", cost, errors
        elif phase.name == "plan":
            return f"Planned approach for: {task[:50]}", cost, errors
        elif phase.name == "execute":
            return f"Executed: {task[:50]}", cost, errors
        elif phase.name == "verify":
            verified = "Verification passed." if prior_content else "Nothing to verify."
            return verified, cost, errors
        elif phase.name == "reflect":
            return "Reflected on execution.", cost, errors
        else:
            return phase.action, cost, errors

    async def _reflect(
        self,
        task: str,
        content_parts: List[str],
        iteration: int,
    ) -> str:
        """Produce a reflection summary."""
        summary = " | ".join(content_parts[-3:]) if content_parts else "no prior content"
        return f"Reflection (iter {iteration}): {summary[:100]}"

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------
    @property
    def template_store(self) -> LoopTemplateStore:
        return self._store

    @property
    def agent_loop(self) -> Any:
        return self._agent_loop

    def __repr__(self) -> str:
        return (
            f"TaskLoop(store={self._store!r}, "
            f"has_agent={self._agent_loop is not None})"
        )


# ═══════════════════════════════════════════════════════════════
#  EvolutionLoop -- Outer Evolution Loop
# ═══════════════════════════════════════════════════════════════


class EvolutionLoop:
    """Outer loop: evolve templates and memories after task completion.

    The evolution loop orchestrates four sub-systems:

    1.  **Process Reflection** -- via :class:`StrategyEvolver.analyze_run`.
    2.  **Template Statistics** -- via
        :meth:`LoopTemplateStore.update_stats`.
    3.  **Memory Quality** -- via :class:`ForgettingEngine` on related
        memories.
    4.  **Mutation & A/B Testing** -- via :class:`StrategyEvolver.evolve`
        and :class:`ABTestFramework`.

    Args:
        template_store:    :class:`LoopTemplateStore`.
        strategy_evolver:  :class:`StrategyEvolver` (or ``None`` for auto).
        ab_test_framework: :class:`ABTestFramework` (or ``None`` for auto).
        forgetting_engine: :class:`ForgettingEngine` (or ``None`` for auto).
        anti_pattern_store: :class:`AntiPatternStore` (or ``None``).
        trigger_config:    :class:`TriggerConfig` for trigger rules.
        quality_assessor:  :class:`QualityAssessor`.
    """

    def __init__(
        self,
        template_store: Optional[LoopTemplateStore] = None,
        strategy_evolver: Optional[StrategyEvolver] = None,
        ab_test_framework: Optional[ABTestFramework] = None,
        forgetting_engine: Optional[ForgettingEngine] = None,
        anti_pattern_store: Optional[AntiPatternStore] = None,
        trigger_config: Optional[TriggerConfig] = None,
        quality_assessor: Optional[QualityAssessor] = None,
    ) -> None:
        self._store = template_store or LoopTemplateStore()
        self._evolver = strategy_evolver or StrategyEvolver(
            store=self._store, backend=self._store._backend
        )
        self._ab_test = ab_test_framework or ABTestFramework(
            store=self._store, backend=self._store._backend
        )
        self._forgetting = forgetting_engine or ForgettingEngine(is_dry_run=True)
        self._anti_patterns = anti_pattern_store or AntiPatternStore()
        self._trigger_config = trigger_config or TriggerConfig()
        self._quality_assessor = quality_assessor or QualityAssessor()

        # Track evolution history
        self._evolution_count: int = 0
        self._last_reflection: Optional[ProcessReflection] = None
        self._last_variant: Optional[LoopTemplate] = None
        self._experiment_results: List[ExperimentResult] = []

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------
    def evolve(self, task_result: TaskResult) -> Optional[LoopTemplate]:
        """Run one evolution cycle on a completed task.

        Steps:
            1.  Build an :class:`ExecutionResult` from the task result.
            2.  Run process reflection via the strategy evolver.
            3.  Update the template's usage statistics.
            4.  Update memory quality via the forgetting engine.
            5.  If the task failed, register an anti-pattern.
            6.  If a beneficial mutation is proposed, apply it.
            7.  Evaluate any outstanding A/B experiments.

        Args:
            task_result: The completed :class:`TaskResult`.

        Returns:
            The new variant :class:`LoopTemplate` if one was created,
            or ``None``.
        """
        self._evolution_count += 1

        template = task_result.template_used
        if template is None:
            template = self._store.get_template(task_result.template_id)
        if template is None:
            # Cannot evolve without a template
            return None

        # 1. Build ExecutionResult
        exec_result = self._build_execution_result(task_result, template)

        # 2. Process reflection
        reflection = self._process_reflection(template, exec_result)
        task_result.reflection = reflection
        self._last_reflection = reflection

        # 3. Update template stats
        self._update_template_stats(task_result, template)

        # 4. Update memory quality
        self._update_memory_quality(task_result)

        # 5. Anti-pattern registration on failure
        if not task_result.success:
            self._register_anti_pattern(task_result)

        # 6. Mutation
        variant = self._try_mutation(template, exec_result, task_result)
        self._last_variant = variant

        # 7. A/B experiment evaluation
        self._evaluate_experiments()

        return variant

    # ------------------------------------------------------------------
    #  Sub-steps
    # ------------------------------------------------------------------
    def _build_execution_result(
        self,
        task_result: TaskResult,
        template: LoopTemplate,
    ) -> ExecutionResult:
        """Build an :class:`ExecutionResult` from a :class:`TaskResult`."""
        errors = list(task_result.errors)
        for entry in task_result.execution_log.entries:
            errors.extend(entry.errors)

        tools_used = task_result.tools_used
        tools_available = list(template.tools) if template.tools else tools_used

        return ExecutionResult(
            success=task_result.success,
            iterations=task_result.iterations,
            expected_iterations=template.max_iterations,
            token_cost=task_result.token_cost,
            token_budget=1000.0,  # default budget
            errors=errors,
            tools_used=tools_used,
            tools_available=tools_available,
            result_correct=task_result.success,
        )

    def _process_reflection(
        self,
        template: LoopTemplate,
        exec_result: ExecutionResult,
    ) -> ProcessReflection:
        """Run the strategy evolver's analysis."""
        try:
            return self._evolver.analyze_run(template, exec_result)
        except Exception:
            # Fallback: neutral reflection
            return ProcessReflection(
                efficiency=0.5,
                accuracy=0.5,
                cost=0.5,
                robustness=0.5,
                adaptability=0.5,
                notes="Reflection failed; using neutral defaults.",
            )

    def _update_template_stats(
        self,
        task_result: TaskResult,
        template: LoopTemplate,
    ) -> None:
        """Update the template's usage statistics in the store."""
        try:
            self._store.update_stats(
                template.id,
                success=task_result.success,
                iterations=task_result.iterations,
                cost=task_result.token_cost,
            )
        except Exception:
            pass  # store may be in-memory or mock

    def _update_memory_quality(self, task_result: TaskResult) -> None:
        """Run the forgetting engine on related memories.

        For each related memory, evaluates the forgetting action and
        updates quality based on the task outcome.
        """
        for memory_id in task_result.related_memories:
            try:
                # Build a MemoryRecord from the task result
                record = MemoryRecord(
                    id=memory_id,
                    quality=task_result.quality,
                    reinforcement_count=1 if task_result.success else 0,
                    contradiction_count=0 if task_result.success else 1,
                )
                action = self._forgetting.evaluate(record)
                # The action is logged but actual memory updates
                # would be handled by the persistence layer.
            except Exception:
                pass

    def _register_anti_pattern(self, task_result: TaskResult) -> None:
        """Register a failure as an anti-pattern."""
        try:
            error_desc = "; ".join(task_result.errors[:3]) or "Unknown failure"
            self._anti_patterns.register_from_failure(
                task_result.task,
                error_message=error_desc,
            )
        except Exception:
            pass

    def _try_mutation(
        self,
        template: LoopTemplate,
        exec_result: ExecutionResult,
        task_result: TaskResult,
    ) -> Optional[LoopTemplate]:
        """Attempt to evolve the template via mutation.

        Only triggers mutation if:
        - The reflection composite score is below a threshold (0.6).
        - OR the task failed.
        """
        reflection = self._last_reflection
        if reflection is None:
            return None

        # Decide whether to mutate
        should_mutate = (
            task_result.success is False
            or reflection.composite_score < 0.6
        )

        if not should_mutate:
            return None

        try:
            variant = self._evolver.evolve(
                template, exec_result, register=True
            )
            return variant
        except Exception:
            return None

    def _evaluate_experiments(self) -> None:
        """Evaluate any outstanding (running) A/B experiments."""
        try:
            experiments = self._ab_test.list_experiments(status="running")
            for exp in experiments:
                try:
                    result = self._ab_test.evaluate(exp.id)
                    self._experiment_results.append(result)
                except Exception:
                    pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    #  A/B Test Management
    # ------------------------------------------------------------------
    def create_experiment(
        self,
        name: str,
        control_template: LoopTemplate,
        variant_template: LoopTemplate,
        min_samples: int = 10,
    ) -> Optional[Experiment]:
        """Create a new A/B test experiment."""
        try:
            return self._ab_test.create_experiment(
                name=name,
                control_template=control_template,
                variant_template=variant_template,
                min_samples=min_samples,
            )
        except Exception:
            return None

    def record_experiment_result(
        self,
        experiment_id: str,
        template_id: str,
        success: bool,
        iterations: int,
        cost: float,
    ) -> None:
        """Record a trial result for an A/B experiment."""
        try:
            self._ab_test.record_result(
                experiment_id=experiment_id,
                template_id=template_id,
                success=success,
                iterations=iterations,
                cost=cost,
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------
    @property
    def evolution_count(self) -> int:
        return self._evolution_count

    @property
    def last_reflection(self) -> Optional[ProcessReflection]:
        return self._last_reflection

    @property
    def last_variant(self) -> Optional[LoopTemplate]:
        return self._last_variant

    @property
    def experiment_results(self) -> List[ExperimentResult]:
        return list(self._experiment_results)

    @property
    def template_store(self) -> LoopTemplateStore:
        return self._store

    @property
    def strategy_evolver(self) -> StrategyEvolver:
        return self._evolver

    @property
    def ab_test_framework(self) -> ABTestFramework:
        return self._ab_test

    @property
    def forgetting_engine(self) -> ForgettingEngine:
        return self._forgetting

    @property
    def anti_pattern_store(self) -> AntiPatternStore:
        return self._anti_patterns

    @property
    def trigger_config(self) -> TriggerConfig:
        return self._trigger_config

    def __repr__(self) -> str:
        if self._last_reflection:
            return (
                f"EvolutionLoop(evolved={self._evolution_count}, "
                f"last_score={self._last_reflection.composite_score:.2f})"
            )
        return f"EvolutionLoop(evolved={self._evolution_count})"


# ═══════════════════════════════════════════════════════════════
#  BilevelLoop -- Top-Level Coordinator
# ═══════════════════════════════════════════════════════════════


class BilevelLoop:
    """Top-level coordinator combining TaskLoop + EvolutionLoop.

    Provides a single ``run(task)`` entry point that:
    1.  Runs the inner :class:`TaskLoop` to execute the task.
    2.  Checks trigger conditions via :class:`TriggerEvaluator`.
    3.  If triggered, runs the outer :class:`EvolutionLoop`.
    4.  Returns the :class:`TaskResult`.

    Args:
        task_loop:      :class:`TaskLoop` for inner execution.
        evolution_loop: :class:`EvolutionLoop` for outer evolution.
        trigger_config: :class:`TriggerConfig` for trigger rules.
                        If ``None``, uses the evolution loop's config.
    """

    def __init__(
        self,
        task_loop: Optional[TaskLoop] = None,
        evolution_loop: Optional[EvolutionLoop] = None,
        trigger_config: Optional[TriggerConfig] = None,
    ) -> None:
        self._task_loop = task_loop or TaskLoop()
        self._evolution_loop = evolution_loop or EvolutionLoop()
        self._trigger_config = trigger_config or self._evolution_loop.trigger_config
        self._trigger_evaluator = TriggerEvaluator(self._trigger_config)

        # History
        self._results: List[TaskResult] = []
        self._evolution_count: int = 0

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------
    async def run(self, task: str) -> TaskResult:
        """Execute a task through the bilevel loop.

        1.  Inner loop: execute the task via :class:`TaskLoop`.
        2.  Record the result for trigger evaluation.
        3.  Check if evolution should be triggered.
        4.  If triggered, run the outer :class:`EvolutionLoop`.
        5.  Return the :class:`TaskResult`.

        Args:
            task: The task description.

        Returns:
            A :class:`TaskResult` with execution and evolution metadata.
        """
        # 1. Inner loop
        result = await self._task_loop.run(task)

        # 2. Record for trigger evaluation
        self._trigger_evaluator.record_result(result)

        # 3. Check triggers
        if self._trigger_evaluator.should_trigger(result):
            # 4. Outer loop
            variant = self._evolution_loop.evolve(result)
            self._evolution_count += 1
            self._trigger_evaluator.mark_evolved(result.task_signature)

            # If a variant was created, set up A/B testing
            if variant is not None and result.template_used is not None:
                try:
                    self._evolution_loop.create_experiment(
                        name=f"auto-ab-{self._evolution_count}",
                        control_template=result.template_used,
                        variant_template=variant,
                        min_samples=5,
                    )
                except Exception:
                    pass

        # 5. Store result
        self._results.append(result)
        return result

    # ------------------------------------------------------------------
    #  Convenience
    # ------------------------------------------------------------------
    async def run_batch(self, tasks: List[str]) -> List[TaskResult]:
        """Execute multiple tasks sequentially.

        Args:
            tasks: List of task descriptions.

        Returns:
            List of :class:`TaskResult` objects.
        """
        results: List[TaskResult] = []
        for task in tasks:
            result = await self.run(task)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------
    @property
    def task_loop(self) -> TaskLoop:
        return self._task_loop

    @property
    def evolution_loop(self) -> EvolutionLoop:
        return self._evolution_loop

    @property
    def trigger_evaluator(self) -> TriggerEvaluator:
        return self._trigger_evaluator

    @property
    def trigger_config(self) -> TriggerConfig:
        return self._trigger_config

    @property
    def results(self) -> List[TaskResult]:
        return list(self._results)

    @property
    def result_count(self) -> int:
        return len(self._results)

    @property
    def evolution_count(self) -> int:
        return self._evolution_count

    @property
    def last_result(self) -> Optional[TaskResult]:
        return self._results[-1] if self._results else None

    @property
    def success_rate(self) -> float:
        """Overall success rate across all tasks."""
        if not self._results:
            return 0.0
        successes = sum(1 for r in self._results if r.success)
        return successes / len(self._results)

    def reset(self) -> None:
        """Clear all accumulated state."""
        self._results.clear()
        self._evolution_count = 0
        self._trigger_evaluator.reset()

    def __repr__(self) -> str:
        return (
            f"BilevelLoop(tasks={self.result_count}, "
            f"evolved={self._evolution_count}, "
            f"success_rate={self.success_rate:.2f})"
        )
