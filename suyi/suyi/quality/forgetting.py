"""
Forgetting Engine — exponential decay, graded actions, and memory compression.

Implements the forgetting layer of the ALA self-evolution system.  Memories
decay over time according to an exponential curve whose time-constant
(``tau``) is determined by the memory's quality grade.  When the retention
quality drops below thresholds, the engine prescribes one of three actions:

- **DEGRADE**  — lower the memory's effective priority in retrieval.
- **COMPRESS** — convert an episodic memory into a semantic one (detail
  loss, pattern preservation).
- **PURGE**    — permanently remove the memory (irreversible).

Key design principles
---------------------

1.  **Exponential decay** — ``Q(t) = Q0 * e^(-t/tau)``, where ``Q0`` is
    the initial quality and ``tau`` is the grade-dependent time-constant.
2.  **Reinforcement** — memories that are repeatedly verified get their
    ``Q0`` boosted and ``tau`` extended (slower forgetting).
3.  **Contradiction penalty** — memories hit by contradicting evidence
    get their ``Q0`` reduced (faster forgetting).
4.  **Exceptions** — anti-patterns (failed results) are never purged;
    heavily-referenced memories (>10 refs) get 3× tau extension; user-
    pinned memories never forget.
5.  **Dry-run support** — every destructive action can be previewed
    without execution via ``is_dry_run=True``.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from .grader import (
    QualityScore,
    QualityAssessor,
    ResultQuality,
    SourceQuality,
)


# ═══════════════════════════════════════════════════════════════
#  ForgettingAction enum
# ═══════════════════════════════════════════════════════════════


class ForgettingAction(Enum):
    """Prescribed action for a memory under the forgetting policy.

    Members:
        DEGRADE:  Retention is moderate; lower retrieval priority but
                  keep the memory intact.
        COMPRESS: Retention is low; compress episodic → semantic
                  (discard details, keep abstract pattern).
        PURGE:    Retention is negligible; permanently remove.
    """

    DEGRADE = auto()
    COMPRESS = auto()
    PURGE = auto()


# ═══════════════════════════════════════════════════════════════
#  ForgettingCurve
# ═══════════════════════════════════════════════════════════════


class ForgettingCurve:
    """Exponential forgetting curve: ``Q(t) = Q0 * e^(-t/tau)``.

    The curve models how a memory's *retention quality* decays over
    time.  ``Q0`` is the initial quality (in [0, 1]), ``tau`` is the
    time-constant in seconds, and ``t`` is the elapsed time in seconds.

    Reinforcement and contradiction modify the curve parameters:

    - **Reinforcement** (repeated verification): boosts ``Q0`` by a
      factor and extends ``tau`` so the memory decays more slowly.
    - **Contradiction** (evidence against): reduces ``Q0`` so the
      memory decays faster.

    Attributes:
        q0:  Initial retention quality [0, 1].
        tau: Time-constant in seconds (∞ means never decays).
    """

    #: Maximum Q0 after reinforcement (capped at 1.0).
    MAX_Q0: float = 1.0

    #: Minimum Q0 after contradiction (floored at 0.0).
    MIN_Q0: float = 0.0

    #: Q0 boost per reinforcement event.
    REINFORCEMENT_BOOST: float = 0.1

    #: Tau multiplier per reinforcement event.
    REINFORCEMENT_TAU_FACTOR: float = 1.5

    #: Q0 penalty per contradiction event.
    CONTRADICTION_PENALTY: float = 0.2

    #: Tau reduction factor per contradiction event.
    CONTRADICTION_TAU_FACTOR: float = 0.5

    #: Tau multiplier for heavily-referenced memories (>10 refs).
    HIGH_REF_TAU_FACTOR: float = 3.0

    #: Reference count threshold for high-reference extension.
    HIGH_REF_THRESHOLD: int = 10

    def __init__(
        self,
        q0: float = 0.5,
        tau: float = 30.0 * 86_400.0,  # default 30 days in seconds
    ) -> None:
        if not (0.0 <= q0 <= 1.0):
            raise ValueError(f"q0 must be in [0, 1], got {q0}")
        if tau <= 0 and tau != math.inf:
            raise ValueError(f"tau must be > 0 or inf, got {tau}")
        self.q0: float = q0
        self.tau: float = tau

    # ------------------------------------------------------------------
    #  Core computation
    # ------------------------------------------------------------------
    def retention(self, elapsed_seconds: float) -> float:
        """Compute retention quality after *elapsed_seconds*.

        ``Q(t) = Q0 * e^(-t/tau)``

        If ``tau`` is infinite, retention is always ``Q0`` (no decay).

        Args:
            elapsed_seconds: Time elapsed since the memory was last
                reinforced (seconds).

        Returns:
            Retention quality in [0, Q0].
        """
        if self.tau == math.inf:
            return self.q0
        if elapsed_seconds <= 0:
            return self.q0
        return self.q0 * math.exp(-elapsed_seconds / self.tau)

    def retention_at_days(self, elapsed_days: float) -> float:
        """Convenience: retention after *elapsed_days*."""
        return self.retention(elapsed_days * 86_400.0)

    def time_until_threshold(self, threshold: float) -> float:
        """Time (seconds) until retention drops below *threshold*.

        Solves ``Q0 * e^(-t/tau) = threshold`` for ``t``.

        If the threshold is already above Q0, returns 0.
        If tau is infinite, returns infinity.

        Args:
            threshold: Target retention level.

        Returns:
            Seconds until the threshold is crossed.
        """
        if self.tau == math.inf:
            return math.inf
        if threshold >= self.q0:
            return 0.0
        if threshold <= 0:
            return math.inf
        # t = -tau * ln(threshold / Q0)
        return -self.tau * math.log(threshold / self.q0)

    # ------------------------------------------------------------------
    #  Reinforcement & contradiction
    # ------------------------------------------------------------------
    def reinforce(self, times: int = 1) -> "ForgettingCurve":
        """Apply reinforcement: boost Q0 and extend tau.

        Each reinforcement event:
        - ``Q0 = min(Q0 + REINFORCEMENT_BOOST, MAX_Q0)``
        - ``tau = tau * REINFORCEMENT_TAU_FACTOR``

        Returns a **new** ForgettingCurve (immutable operation).
        """
        new_q0 = self.q0
        new_tau = self.tau
        for _ in range(times):
            new_q0 = min(new_q0 + self.REINFORCEMENT_BOOST, self.MAX_Q0)
            if new_tau != math.inf:
                new_tau *= self.REINFORCEMENT_TAU_FACTOR
        return ForgettingCurve(q0=new_q0, tau=new_tau)

    def contradict(self, times: int = 1) -> "ForgettingCurve":
        """Apply contradiction: reduce Q0 and shrink tau.

        Each contradiction event:
        - ``Q0 = max(Q0 - CONTRADICTION_PENALTY, MIN_Q0)``
        - ``tau = tau * CONTRADICTION_TAU_FACTOR``

        Returns a **new** ForgettingCurve (immutable operation).
        """
        new_q0 = self.q0
        new_tau = self.tau
        for _ in range(times):
            new_q0 = max(new_q0 - self.CONTRADICTION_PENALTY, self.MIN_Q0)
            if new_tau != math.inf:
                new_tau *= self.CONTRADICTION_TAU_FACTOR
        return ForgettingCurve(q0=new_q0, tau=new_tau)

    def apply_high_reference(self, ref_count: int) -> "ForgettingCurve":
        """Extend tau if the memory is heavily referenced.

        If ``ref_count > HIGH_REF_THRESHOLD``, tau is multiplied by
        ``HIGH_REF_TAU_FACTOR``.

        Returns a **new** ForgettingCurve.
        """
        if ref_count > self.HIGH_REF_THRESHOLD and self.tau != math.inf:
            return ForgettingCurve(q0=self.q0, tau=self.tau * self.HIGH_REF_TAU_FACTOR)
        return ForgettingCurve(q0=self.q0, tau=self.tau)

    # ------------------------------------------------------------------
    #  Factory from QualityScore
    # ------------------------------------------------------------------
    @classmethod
    def from_quality(
        cls,
        quality: QualityScore,
        reinforcement_count: int = 0,
        contradiction_count: int = 0,
        reference_count: int = 0,
    ) -> "ForgettingCurve":
        """Build a ForgettingCurve from a :class:`QualityScore`.

        The initial ``Q0`` is the memory weight, and ``tau`` is the
        quality's ``decay_tau``.  Reinforcement, contradiction, and
        reference count are applied on top.

        Args:
            quality:               The memory's quality score.
            reinforcement_count:   Number of times this memory was
                verified / successfully used.
            contradiction_count:   Number of times contradicting
                evidence was encountered.
            reference_count:       Number of times this memory was
                referenced / retrieved.

        Returns:
            A configured :class:`ForgettingCurve`.
        """
        curve = cls(
            q0=quality.memory_weight,
            tau=quality.decay_tau,
        )
        if reinforcement_count > 0:
            curve = curve.reinforce(reinforcement_count)
        if contradiction_count > 0:
            curve = curve.contradict(contradiction_count)
        if reference_count > 0:
            curve = curve.apply_high_reference(reference_count)
        return curve

    # ------------------------------------------------------------------
    #  Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "q0": round(self.q0, 4),
            "tau": self.tau if self.tau != math.inf else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForgettingCurve":
        tau = data.get("tau")
        if tau is None:
            tau = math.inf
        return cls(q0=float(data["q0"]), tau=float(tau))

    def __repr__(self) -> str:
        tau_str = "inf" if self.tau == math.inf else f"{self.tau / 86_400:.1f}d"
        return f"ForgettingCurve(q0={self.q0:.3f}, tau={tau_str})"


# ═══════════════════════════════════════════════════════════════
#  MemoryRecord — lightweight memory descriptor
# ═══════════════════════════════════════════════════════════════


@dataclass
class MemoryRecord:
    """A lightweight descriptor of a memory for the forgetting engine.

    The engine does not need the full memory object — only the fields
    relevant to forgetting decisions.

    Attributes:
        id:               Unique memory identifier.
        quality:          The memory's :class:`QualityScore`.
        created_at:       Unix timestamp of creation.
        last_accessed:    Unix timestamp of last access.
        last_reinforced:  Unix timestamp of last reinforcement.
        reinforcement_count: Number of times reinforced.
        contradiction_count:  Number of contradictions encountered.
        reference_count:      Number of times referenced.
        is_user_pinned:   Whether the user has pinned this memory.
        is_episodic:      Whether this is an episodic memory
                          (eligible for compression to semantic).
        content:          The memory content (needed for compression).
        tags:             Optional tags.
    """

    id: str = ""
    quality: QualityScore = field(default_factory=QualityScore)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    last_reinforced: float = 0.0
    reinforcement_count: int = 0
    contradiction_count: int = 0
    reference_count: int = 0
    is_user_pinned: bool = False
    is_episodic: bool = False
    content: str = ""
    tags: List[str] = field(default_factory=list)

    @property
    def is_anti_pattern(self) -> bool:
        """True if this memory is an anti-pattern (FAILED result)."""
        return self.quality.is_anti_pattern

    @property
    def elapsed_seconds(self) -> float:
        """Seconds since last reinforcement (or creation if never reinforced)."""
        base = self.last_reinforced if self.last_reinforced > 0 else self.created_at
        return max(0.0, time.time() - base)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "quality": self.quality.to_dict(),
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "last_reinforced": self.last_reinforced,
            "reinforcement_count": self.reinforcement_count,
            "contradiction_count": self.contradiction_count,
            "reference_count": self.reference_count,
            "is_user_pinned": self.is_user_pinned,
            "is_episodic": self.is_episodic,
            "content": self.content,
            "tags": list(self.tags),
        }


# ═══════════════════════════════════════════════════════════════
#  Forgetting decision thresholds
# ═══════════════════════════════════════════════════════════════

#: Retention above this → keep memory as-is (no action needed).
THRESHOLD_KEEP: float = 0.5

#: Retention in [0.2, 0.5] → DEGRADE (lower priority).
THRESHOLD_DEGRADE: float = 0.2

#: Retention in [0.05, 0.2] → COMPRESS (episodic → semantic).
THRESHOLD_COMPRESS: float = 0.05

#: Retention below 0.05 → PURGE (irreversible removal).
THRESHOLD_PURGE: float = 0.05


# ═══════════════════════════════════════════════════════════════
#  ForgettingEngine
# ═══════════════════════════════════════════════════════════════


class ForgettingEngine:
    """The forgetting engine — evaluates memories and prescribes actions.

    The engine is the central coordinator for memory lifecycle
    management.  It:

    1.  **Evaluates** each memory's current retention using
        :class:`ForgettingCurve`.
    2.  **Prescribes** an action (DEGRADE / COMPRESS / PURGE) based on
        retention thresholds.
    3.  **Applies exceptions** — anti-patterns, user-pinned memories,
        and heavily-referenced memories get special treatment.
    4.  **Updates** memory quality after task completion.
    5.  **Compresses** episodic memories into semantic ones.

    All destructive operations (PURGE, COMPRESS) respect ``is_dry_run``
    — when True, the action is reported but not executed.

    Args:
        assessor:     Optional :class:`QualityAssessor` for quality
                      updates.  A default one is created if not provided.
        is_dry_run:   If True, no destructive actions are actually
                      performed; only reported.
        degrade_threshold:  Retention below this → DEGRADE.
        compress_threshold: Retention below this → COMPRESS.
        purge_threshold:    Retention below this → PURGE.
        high_ref_threshold: Reference count for tau extension.
        high_ref_tau_factor: Tau multiplier for high-ref memories.
    """

    def __init__(
        self,
        assessor: Optional[QualityAssessor] = None,
        is_dry_run: bool = False,
        degrade_threshold: float = THRESHOLD_DEGRADE,
        compress_threshold: float = THRESHOLD_COMPRESS,
        purge_threshold: float = THRESHOLD_PURGE,
        high_ref_threshold: int = ForgettingCurve.HIGH_REF_THRESHOLD,
        high_ref_tau_factor: float = ForgettingCurve.HIGH_REF_TAU_FACTOR,
    ) -> None:
        self.assessor = assessor or QualityAssessor()
        self.is_dry_run = is_dry_run
        self.degrade_threshold = degrade_threshold
        self.compress_threshold = compress_threshold
        self.purge_threshold = purge_threshold
        self.high_ref_threshold = high_ref_threshold
        self.high_ref_tau_factor = high_ref_tau_factor

    # ------------------------------------------------------------------
    #  Curve construction
    # ------------------------------------------------------------------
    def build_curve(self, memory: MemoryRecord) -> ForgettingCurve:
        """Build a :class:`ForgettingCurve` for a memory record.

        Applies reinforcement, contradiction, and high-reference
        extensions on top of the base quality-derived curve.
        """
        curve = ForgettingCurve.from_quality(
            quality=memory.quality,
            reinforcement_count=memory.reinforcement_count,
            contradiction_count=memory.contradiction_count,
            reference_count=memory.reference_count,
        )
        return curve

    # ------------------------------------------------------------------
    #  Evaluation
    # ------------------------------------------------------------------
    def retention(self, memory: MemoryRecord) -> float:
        """Compute the current retention quality of a memory.

        Args:
            memory: The memory record.

        Returns:
            Retention in [0, 1].
        """
        curve = self.build_curve(memory)
        return curve.retention(memory.elapsed_seconds)

    def evaluate(self, memory: MemoryRecord) -> ForgettingAction:
        """Determine the forgetting action for a memory.

        Decision logic (in priority order):

        1.  **User-pinned** → never forget (return DEGRADE as no-op).
        2.  **Anti-pattern** → never PURGE; can DEGRADE but not COMPRESS
            or PURGE.
        3.  Compute retention; map to action by thresholds:
            - retention ≥ 0.5  → DEGRADE (effectively no-op, kept as-is)
            - 0.2 ≤ retention < 0.5 → DEGRADE
            - 0.05 ≤ retention < 0.2 → COMPRESS
            - retention < 0.05 → PURGE

        Note: For user-pinned and anti-pattern memories, the action is
        always DEGRADE (the safest non-destructive action), since they
        should never be compressed or purged.

        Args:
            memory: The memory record.

        Returns:
            The prescribed :class:`ForgettingAction`.
        """
        # Exception 1: user-pinned → never forget
        if memory.is_user_pinned:
            return ForgettingAction.DEGRADE

        # Exception 2: anti-pattern → never PURGE or COMPRESS
        if memory.is_anti_pattern:
            return ForgettingAction.DEGRADE

        retention = self.retention(memory)

        if retention < self.purge_threshold:
            return ForgettingAction.PURGE
        if retention < self.degrade_threshold:
            return ForgettingAction.COMPRESS
        # Both DEGRADE and "keep" map to DEGRADE action
        # (DEGRADE is the mildest action — for retention ≥ 0.5 it's
        # effectively a no-op since the memory is already high quality.)
        return ForgettingAction.DEGRADE

    def evaluate_batch(
        self,
        memories: Sequence[MemoryRecord],
    ) -> List[Tuple[MemoryRecord, ForgettingAction, float]]:
        """Evaluate a batch of memories.

        Args:
            memories: List of memory records.

        Returns:
            List of ``(memory, action, retention)`` tuples.
        """
        results: List[Tuple[MemoryRecord, ForgettingAction, float]] = []
        for mem in memories:
            retention = self.retention(mem)
            action = self.evaluate(mem)
            results.append((mem, action, retention))
        return results

    # ------------------------------------------------------------------
    #  Execution
    # ------------------------------------------------------------------
    def execute(
        self,
        memory: MemoryRecord,
        action: Optional[ForgettingAction] = None,
        on_purge: Optional[Callable[[str], None]] = None,
        on_compress: Optional[Callable[[MemoryRecord], Any]] = None,
        on_degrade: Optional[Callable[[str], None]] = None,
    ) -> ForgettingAction:
        """Execute (or preview) a forgetting action on a memory.

        When ``is_dry_run`` is True, no callbacks are invoked — the
        action is only returned for reporting.

        Args:
            memory:     The memory record.
            action:     The action to execute.  If None, :meth:`evaluate`
                        is called to determine it.
            on_purge:   Callback invoked with the memory ID on PURGE.
            on_compress: Callback invoked with the memory record on
                        COMPRESS.  Should return the compressed result.
            on_degrade: Callback invoked with the memory ID on DEGRADE.

        Returns:
            The action that was (or would be) executed.
        """
        if action is None:
            action = self.evaluate(memory)

        if self.is_dry_run:
            return action

        if action == ForgettingAction.PURGE:
            # Double-check exceptions before purging
            if memory.is_user_pinned or memory.is_anti_pattern:
                # Safety net: never purge pinned or anti-pattern
                return ForgettingAction.DEGRADE
            if on_purge:
                on_purge(memory.id)
        elif action == ForgettingAction.COMPRESS:
            # Anti-patterns should not be compressed
            if memory.is_anti_pattern:
                return ForgettingAction.DEGRADE
            if on_compress:
                on_compress(memory)
        elif action == ForgettingAction.DEGRADE:
            if on_degrade:
                on_degrade(memory.id)

        return action

    def execute_batch(
        self,
        memories: Sequence[MemoryRecord],
        on_purge: Optional[Callable[[str], None]] = None,
        on_compress: Optional[Callable[[MemoryRecord], Any]] = None,
        on_degrade: Optional[Callable[[str], None]] = None,
    ) -> List[Tuple[str, ForgettingAction]]:
        """Execute forgetting actions on a batch of memories.

        Returns:
            List of ``(memory_id, action_executed)`` tuples.
        """
        results: List[Tuple[str, ForgettingAction]] = []
        for mem in memories:
            action = self.execute(
                mem,
                on_purge=on_purge,
                on_compress=on_compress,
                on_degrade=on_degrade,
            )
            results.append((mem.id, action))
        return results

    # ------------------------------------------------------------------
    #  Quality update after task completion
    # ------------------------------------------------------------------
    def update_quality(
        self,
        memories: Sequence[MemoryRecord],
        result_quality: ResultQuality,
        success: Optional[bool] = None,
        confirmed: bool = False,
        error: bool = False,
        contradiction: bool = False,
        new_evidence: int = 0,
        new_contradictions: int = 0,
    ) -> List[MemoryRecord]:
        """Update quality of memories after a task completes.

        For each memory:
        - Reassess the result quality based on outcome signals.
        - Accumulate evidence and contradiction counts.
        - Recompute confidence.
        - Update reinforcement / contradiction counters.
        - Update timestamps.

        Args:
            memories:           The memories involved in the task.
            result_quality:     The overall task result quality.
            success, confirmed, error, contradiction: Outcome signals.
            new_evidence:       Additional evidence found.
            new_contradictions: Additional contradictions found.

        Returns:
            List of updated :class:`MemoryRecord` objects (new instances).
        """
        now = time.time()
        updated: List[MemoryRecord] = []

        for mem in memories:
            # Use the assessor to compute the updated quality
            new_quality = self.assessor.update_after_task(
                current=mem.quality,
                success=success,
                confirmed=confirmed,
                error=error,
                contradiction=contradiction,
                new_evidence=new_evidence,
                new_contradictions=new_contradictions,
            )

            # If the overall result_quality is worse than the per-memory
            # assessment, downgrade to match.
            if result_quality.value < new_quality.result.value:
                new_quality = QualityScore(
                    source=new_quality.source,
                    result=result_quality,
                    confidence=new_quality.confidence,
                    evidence_count=new_quality.evidence_count,
                    contradiction_count=new_quality.contradiction_count,
                )

            # Update reinforcement / contradiction counters
            new_reinforcement = mem.reinforcement_count
            new_contradiction = mem.contradiction_count
            new_last_reinforced = mem.last_reinforced

            if result_quality == ResultQuality.VERIFIED or (
                success is True and not contradiction
            ):
                new_reinforcement += 1
                new_last_reinforced = now
            if result_quality == ResultQuality.FAILED or contradiction:
                new_contradiction += 1

            updated_mem = MemoryRecord(
                id=mem.id,
                quality=new_quality,
                created_at=mem.created_at,
                last_accessed=now,
                last_reinforced=new_last_reinforced,
                reinforcement_count=new_reinforcement,
                contradiction_count=new_contradiction,
                reference_count=mem.reference_count,
                is_user_pinned=mem.is_user_pinned,
                is_episodic=mem.is_episodic,
                content=mem.content,
                tags=list(mem.tags),
            )
            updated.append(updated_mem)

        return updated

    # ------------------------------------------------------------------
    #  Compression
    # ------------------------------------------------------------------
    def compress(self, memory: MemoryRecord) -> Dict[str, Any]:
        """Compress an episodic memory into a semantic one.

        Compression strategy:
        - Extract the core pattern / abstract from the content.
        - Discard tool-call details, timestamps, and verbose text.
        - Preserve tags and the essence of the content.

        This is a lossy operation — the original episodic memory should
        be purged after compression is confirmed.

        Args:
            memory: The episodic memory to compress.

        Returns:
            A dict representing the compressed semantic memory::

                {
                    "id": <original id>,
                    "content": <compressed summary>,
                    "tags": [...],
                    "source": "compressed",
                    "quality": <QualityScore dict>,
                }

        Raises:
            ValueError: If the memory is not episodic.
        """
        if not memory.is_episodic:
            raise ValueError(
                f"Cannot compress non-episodic memory {memory.id!r}"
            )

        # Extractive compression: keep the first few sentences
        content = memory.content or ""
        # Split on sentence boundaries
        import re
        sentences = re.split(r'[.!?。！？\n]+', content)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 2:
            compressed_content = content
        else:
            # Keep first 2 sentences as the abstract pattern
            compressed_content = ". ".join(sentences[:2])
            if len(compressed_content) > 300:
                compressed_content = compressed_content[:300] + "..."

        return {
            "id": memory.id,
            "content": f"[compressed] {compressed_content}",
            "tags": list(memory.tags),
            "source": "compressed",
            "quality": memory.quality.to_dict(),
            "original_created_at": memory.created_at,
        }

    def compress_batch(
        self,
        memories: Sequence[MemoryRecord],
    ) -> List[Dict[str, Any]]:
        """Compress multiple episodic memories.

        Non-episodic memories are skipped (not an error).

        Returns:
            List of compressed semantic-memory dicts.
        """
        results: List[Dict[str, Any]] = []
        for mem in memories:
            if not mem.is_episodic:
                continue
            if self.is_dry_run:
                # In dry-run, just report what would be compressed
                results.append({
                    "id": mem.id,
                    "content": "[dry-run] would compress",
                    "source": "dry_run",
                })
            else:
                results.append(self.compress(mem))
        return results

    # ------------------------------------------------------------------
    #  Reporting
    # ------------------------------------------------------------------
    def forgetting_report(
        self,
        memories: Sequence[MemoryRecord],
    ) -> Dict[str, Any]:
        """Generate a summary report of forgetting decisions.

        Args:
            memories: The memories to evaluate.

        Returns:
            A dict with::

                {
                    "total": <int>,
                    "actions": {
                        "DEGRADE": <int>,
                        "COMPRESS": <int>,
                        "PURGE": <int>,
                    },
                    "details": [
                        {
                            "id": ...,
                            "action": ...,
                            "retention": ...,
                            "is_anti_pattern": ...,
                            "is_user_pinned": ...,
                        },
                        ...
                    ],
                    "dry_run": <bool>,
                }
        """
        evaluations = self.evaluate_batch(memories)
        action_counts: Dict[str, int] = {
            "DEGRADE": 0,
            "COMPRESS": 0,
            "PURGE": 0,
        }
        details: List[Dict[str, Any]] = []

        for mem, action, retention in evaluations:
            action_counts[action.name] += 1
            details.append({
                "id": mem.id,
                "action": action.name,
                "retention": round(retention, 4),
                "is_anti_pattern": mem.is_anti_pattern,
                "is_user_pinned": mem.is_user_pinned,
            })

        return {
            "total": len(memories),
            "actions": action_counts,
            "details": details,
            "dry_run": self.is_dry_run,
        }

    def __repr__(self) -> str:
        mode = "dry-run" if self.is_dry_run else "live"
        return (
            f"ForgettingEngine(mode={mode}, "
            f"degrade<{self.degrade_threshold}, "
            f"compress<{self.compress_threshold}, "
            f"purge<{self.purge_threshold})"
        )
