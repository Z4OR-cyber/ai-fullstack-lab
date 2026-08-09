"""
Quality Grading System — source and result quality assessment for memories.

This module implements the quality grading layer of the ALA (Adaptive
Loop Architecture) self-evolution system.  Every memory and every task
result is assigned a quality grade that influences:

- **Storage weight** (``memory_weight``) — higher-grade memories are
  stored with greater priority and surface higher in retrieval.
- **Forgetting speed** (``decay_tau``) — lower-grade memories decay
  faster.  Grade-S memories effectively never decay; grade-D memories
  decay within a day.

Grade taxonomy
--------------

Source Quality (where the information came from)::

    S — verified      (cross-checked against multiple authoritative sources)
    A — authoritative (official docs, primary source, expert verified)
    B — reliable      (reputable secondary source, consistent with priors)
    C — uncertain     (single source, unverified, or conflicting evidence)
    D — speculative   (LLM reasoning without evidence, guess, hypothesis)

Result Quality (what happened when the memory was used)::

    VERIFIED    — independently confirmed by evidence
    TRUSTED     — used successfully, no contradiction observed
    SPECULATIVE — used but not confirmed; partial or ambiguous outcome
    FAILED      — led to an error, contradiction, or wrong answer
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════════


class SourceQuality(Enum):
    """Quality grade for the *source* of a memory.

    Ordered from highest (S) to lowest (D).  The numeric ``value``
    attribute provides a monotonic rank for comparisons.
    """

    S = 5  # verified
    A = 4  # authoritative
    B = 3  # reliable
    C = 2  # uncertain
    D = 1  # speculative

    @classmethod
    def from_label(cls, label: str) -> "SourceQuality":
        """Create from a human-readable label (case-insensitive).

        Recognised labels: ``verified``, ``authoritative``, ``reliable``,
        ``uncertain``, ``speculative``, or the single-letter grade
        ``S``/``A``/``B``/``C``/``D``.
        """
        mapping = {
            "s": cls.S, "verified": cls.S,
            "a": cls.A, "authoritative": cls.A,
            "b": cls.B, "reliable": cls.B,
            "c": cls.C, "uncertain": cls.C,
            "d": cls.D, "speculative": cls.D,
        }
        key = label.strip().lower()
        if key not in mapping:
            raise ValueError(f"Unknown source quality label: {label!r}")
        return mapping[key]

    @property
    def label(self) -> str:
        """Human-readable label."""
        labels = {
            SourceQuality.S: "verified",
            SourceQuality.A: "authoritative",
            SourceQuality.B: "reliable",
            SourceQuality.C: "uncertain",
            SourceQuality.D: "speculative",
        }
        return labels[self]

    @property
    def grade_letter(self) -> str:
        """Single-letter grade (``'S'``, ``'A'``, …)."""
        return self.name


class ResultQuality(Enum):
    """Quality grade for the *outcome* of using a memory.

    Ordered from best (VERIFIED) to worst (FAILED).
    """

    VERIFIED = 4      # independently confirmed
    TRUSTED = 3       # used successfully, no contradiction
    SPECULATIVE = 2   # used but unconfirmed
    FAILED = 1        # led to error or contradiction

    @classmethod
    def from_label(cls, label: str) -> "ResultQuality":
        """Create from a human-readable label (case-insensitive)."""
        mapping = {
            "verified": cls.VERIFIED,
            "trusted": cls.TRUSTED,
            "speculative": cls.SPECULATIVE,
            "failed": cls.FAILED,
        }
        key = label.strip().lower()
        if key not in mapping:
            raise ValueError(f"Unknown result quality label: {label!r}")
        return mapping[key]

    @property
    def label(self) -> str:
        """Human-readable label (lowercase)."""
        return self.name.lower()

    @property
    def is_failure(self) -> bool:
        """True when the result is a failure (contradiction or error)."""
        return self == ResultQuality.FAILED


# ═══════════════════════════════════════════════════════════════
#  Decay tau mapping
# ═══════════════════════════════════════════════════════════════

# Number of seconds per day — used for tau conversion.
_SECONDS_PER_DAY: float = 86_400.0


def _source_decay_tau_days(source: SourceQuality) -> float:
    """Return the decay half-life (in days) for a given source grade.

    - S → infinity (never decays from age alone)
    - A → 90 days
    - B → 30 days
    - C → 7 days
    - D → 1 day
    """
    return {
        SourceQuality.S: math.inf,
        SourceQuality.A: 90.0,
        SourceQuality.B: 30.0,
        SourceQuality.C: 7.0,
        SourceQuality.D: 1.0,
    }[source]


def _failed_decay_tau_days() -> float:
    """Failed results get infinite tau so they persist as anti-patterns."""
    return math.inf


# ═══════════════════════════════════════════════════════════════
#  QualityScore dataclass
# ═══════════════════════════════════════════════════════════════


@dataclass
class QualityScore:
    """Composite quality assessment for a single memory.

    Attributes:
        source:              Source quality grade.
        result:              Result quality grade.
        confidence:          Overall confidence in [0.0, 1.0].
        evidence_count:      Number of supporting evidence items.
        contradiction_count: Number of contradicting evidence items.
    """

    source: SourceQuality = SourceQuality.C
    result: ResultQuality = ResultQuality.SPECULATIVE
    confidence: float = 0.5
    evidence_count: int = 0
    contradiction_count: int = 0

    # ------------------------------------------------------------------
    #  Validation
    # ------------------------------------------------------------------
    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceQuality):
            raise TypeError(
                f"source must be SourceQuality, got {type(self.source).__name__}"
            )
        if not isinstance(self.result, ResultQuality):
            raise TypeError(
                f"result must be ResultQuality, got {type(self.result).__name__}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be in [0, 1], got {self.confidence}"
            )
        if self.evidence_count < 0:
            raise ValueError(
                f"evidence_count must be >= 0, got {self.evidence_count}"
            )
        if self.contradiction_count < 0:
            raise ValueError(
                f"contradiction_count must be >= 0, got {self.contradiction_count}"
            )

    # ------------------------------------------------------------------
    #  Derived properties
    # ------------------------------------------------------------------
    @property
    def memory_weight(self) -> float:
        """Storage / retrieval weight in [0.0, 1.0].

        Higher weight → stored with higher priority, surfaces earlier
        in retrieval.  Computed from source grade, result quality,
        confidence, and the evidence-vs-contradiction balance.
        """
        # Source weight: S=1.0, A=0.8, B=0.6, C=0.4, D=0.2
        source_weight = self.source.value / SourceQuality.S.value  # normalise to [0,1]

        # Result weight: VERIFIED=1.0, TRUSTED=0.75, SPECULATIVE=0.5, FAILED=0.0
        result_weight = {
            ResultQuality.VERIFIED: 1.0,
            ResultQuality.TRUSTED: 0.75,
            ResultQuality.SPECULATIVE: 0.5,
            ResultQuality.FAILED: 0.0,
        }[self.result]

        # Evidence balance: more evidence and fewer contradictions → higher
        total = self.evidence_count + self.contradiction_count
        if total > 0:
            evidence_ratio = self.evidence_count / total
        else:
            evidence_ratio = 0.5  # neutral when no evidence

        # Weighted blend: 40 % source, 30 % result, 20 % confidence, 10 % evidence
        weight = (
            source_weight * 0.40
            + result_weight * 0.30
            + self.confidence * 0.20
            + evidence_ratio * 0.10
        )
        return round(max(0.0, min(1.0, weight)), 4)

    @property
    def decay_tau(self) -> float:
        """Decay time-constant in **seconds**.

        Determines how quickly the memory's retention decays under the
        forgetting curve ``Q(t) = Q0 * e^(-t/tau)``.

        - Based on source grade (S=∞, A=90d, B=30d, C=7d, D=1d).
        - If result is FAILED, tau = ∞ (persists as anti-pattern).
        """
        if self.result == ResultQuality.FAILED:
            return math.inf
        tau_days = _source_decay_tau_days(self.source)
        return tau_days * _SECONDS_PER_DAY

    @property
    def decay_tau_days(self) -> float:
        """Decay time-constant in **days** (convenience accessor)."""
        return self.decay_tau / _SECONDS_PER_DAY

    @property
    def is_anti_pattern(self) -> bool:
        """True when this memory should be treated as a反面记忆 (anti-pattern).

        A memory is an anti-pattern when its result is FAILED.
        """
        return self.result == ResultQuality.FAILED

    @property
    def net_evidence(self) -> int:
        """Net evidence count (evidence - contradictions)."""
        return self.evidence_count - self.contradiction_count

    # ------------------------------------------------------------------
    #  Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "source": self.source.name,
            "result": self.result.name,
            "confidence": round(self.confidence, 4),
            "evidence_count": self.evidence_count,
            "contradiction_count": self.contradiction_count,
            "memory_weight": self.memory_weight,
            "decay_tau_days": self.decay_tau_days
            if self.decay_tau != math.inf
            else None,
            "is_anti_pattern": self.is_anti_pattern,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualityScore":
        """Reconstruct from a dict (produced by :meth:`to_dict`)."""
        source = data.get("source", "C")
        result = data.get("result", "SPECULATIVE")
        if isinstance(source, str):
            source = (
                SourceQuality.from_label(source)
                if source.lower() not in ("s", "a", "b", "c", "d")
                else SourceQuality[source]
            )
        elif isinstance(source, SourceQuality):
            pass  # already an enum
        if isinstance(result, str):
            result = ResultQuality[result] if result.isupper() else ResultQuality.from_label(result)
        elif isinstance(result, ResultQuality):
            pass
        return cls(
            source=source,
            result=result,
            confidence=float(data.get("confidence", 0.5)),
            evidence_count=int(data.get("evidence_count", 0)),
            contradiction_count=int(data.get("contradiction_count", 0)),
        )

    def __repr__(self) -> str:
        return (
            f"QualityScore(source={self.source.grade_letter}, "
            f"result={self.result.name}, "
            f"confidence={self.confidence:.2f}, "
            f"evidence={self.evidence_count}, "
            f"contradictions={self.contradiction_count}, "
            f"weight={self.memory_weight:.2f})"
        )


# ═══════════════════════════════════════════════════════════════
#  QualityAssessor
# ═══════════════════════════════════════════════════════════════


class QualityAssessor:
    """Automatic quality assessment engine.

    Given a source description and optional result metadata, produces a
    :class:`QualityScore`.  The assessor uses heuristics that map
    qualitative source descriptors to the S–D grading scale and result
    outcomes to the VERIFIED–FAILED scale.

    The assessor is **stateless** — all context is passed per call,
    making it trivially mockable for testing.
    """

    # Maps source descriptor keywords to SourceQuality grades.
    # Higher entries take priority when multiple keywords match.
    _SOURCE_KEYWORDS: List[Tuple[str, SourceQuality]] = [
        # S-grade keywords
        ("cross-check", SourceQuality.S),
        ("crosscheck", SourceQuality.S),
        ("multi-source verified", SourceQuality.S),
        ("independently verified", SourceQuality.S),
        ("triple-checked", SourceQuality.S),
        # A-grade keywords
        ("official", SourceQuality.A),
        ("authoritative", SourceQuality.A),
        ("primary source", SourceQuality.A),
        ("expert verified", SourceQuality.A),
        ("documentation", SourceQuality.A),
        ("api docs", SourceQuality.A),
        ("peer-reviewed", SourceQuality.A),
        # B-grade keywords
        ("reliable", SourceQuality.B),
        ("reputable", SourceQuality.B),
        ("secondary source", SourceQuality.B),
        ("trusted secondary", SourceQuality.B),
        ("consistency", SourceQuality.B),
        ("consistent with", SourceQuality.B),
        # C-grade keywords
        ("uncertain", SourceQuality.C),
        ("unverified", SourceQuality.C),
        ("single source", SourceQuality.C),
        ("conflicting", SourceQuality.C),
        ("ambiguous", SourceQuality.C),
        # D-grade keywords
        ("speculative", SourceQuality.D),
        ("guess", SourceQuality.D),
        ("hypothesis", SourceQuality.D),
        ("llm reasoning", SourceQuality.D),
        ("no evidence", SourceQuality.D),
        ("assumption", SourceQuality.D),
    ]

    def __init__(self) -> None:
        # Pre-sort keywords by grade descending so higher grades
        # are matched first.
        self._sorted_keywords = sorted(
            self._SOURCE_KEYWORDS,
            key=lambda x: x[1].value,
            reverse=True,
        )

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------
    def assess_source(self, source_description: str) -> SourceQuality:
        """Determine the source quality from a text description.

        Scans for keyword matches; the highest-grade matching keyword
        wins.  If no keyword matches, defaults to ``C`` (uncertain).

        Args:
            source_description: Free-text description of where the
                information came from.

        Returns:
            The assessed :class:`SourceQuality`.
        """
        if not source_description:
            return SourceQuality.C

        desc_lower = source_description.lower()
        for keyword, grade in self._sorted_keywords:
            if keyword in desc_lower:
                return grade
        return SourceQuality.C

    def assess_result(
        self,
        success: Optional[bool] = None,
        confirmed: bool = False,
        error: bool = False,
        contradiction: bool = False,
    ) -> ResultQuality:
        """Determine the result quality from outcome signals.

        Priority order:
            1. ``contradiction`` or ``error`` → FAILED
            2. ``confirmed`` → VERIFIED
            3. ``success == True`` → TRUSTED
            4. ``success == False`` → FAILED
            5. otherwise → SPECULATIVE

        Args:
            success: Whether the task using this memory succeeded.
                ``None`` means unknown.
            confirmed: Whether the result was independently confirmed.
            error: Whether an error occurred.
            contradiction: Whether contradicting evidence was found.

        Returns:
            The assessed :class:`ResultQuality`.
        """
        if contradiction or error:
            return ResultQuality.FAILED
        if confirmed:
            return ResultQuality.VERIFIED
        if success is True:
            return ResultQuality.TRUSTED
        if success is False:
            return ResultQuality.FAILED
        return ResultQuality.SPECULATIVE

    def assess(
        self,
        source_description: str = "",
        success: Optional[bool] = None,
        confirmed: bool = False,
        error: bool = False,
        contradiction: bool = False,
        evidence_count: int = 0,
        contradiction_count: int = 0,
        base_confidence: Optional[float] = None,
    ) -> QualityScore:
        """Full assessment — produces a :class:`QualityScore`.

        Combines source assessment and result assessment, then computes
        a confidence score based on evidence, contradictions, and the
        source/result grades.

        Args:
            source_description:  Text describing the information source.
            success:             Whether the memory was used successfully.
            confirmed:           Whether independently confirmed.
            error:               Whether an error occurred.
            contradiction:       Whether contradicting evidence found.
            evidence_count:      Number of supporting evidence items.
            contradiction_count: Number of contradicting evidence items.
            base_confidence:     Optional override for the base confidence.
                If ``None``, it is computed from source and result grades.

        Returns:
            A :class:`QualityScore`.
        """
        source = self.assess_source(source_description)
        result = self.assess_result(
            success=success,
            confirmed=confirmed,
            error=error,
            contradiction=contradiction,
        )

        # Auto-count contradictions / evidence from boolean flags
        eff_contradiction_count = contradiction_count
        eff_evidence_count = evidence_count
        if contradiction and contradiction_count == 0:
            eff_contradiction_count = max(eff_contradiction_count, 1)
        if confirmed and evidence_count == 0:
            eff_evidence_count = max(eff_evidence_count, 1)

        # Compute confidence
        if base_confidence is not None:
            confidence = max(0.0, min(1.0, base_confidence))
        else:
            confidence = self._compute_confidence(
                source, result,
                eff_evidence_count, eff_contradiction_count,
            )

        return QualityScore(
            source=source,
            result=result,
            confidence=confidence,
            evidence_count=eff_evidence_count,
            contradiction_count=eff_contradiction_count,
        )

    def assess_from_dict(self, data: Dict[str, Any]) -> QualityScore:
        """Assess quality from a metadata dict.

        Recognised keys: ``source_description``, ``success``, ``confirmed``,
        ``error``, ``contradiction``, ``evidence_count``,
        ``contradiction_count``, ``base_confidence``.

        If ``source`` and ``result`` are already present as grade strings,
        they are used directly instead of re-assessing.
        """
        # Allow direct specification
        source = data.get("source")
        result = data.get("result")
        if source is not None and result is not None:
            if isinstance(source, str):
                source = (
                    SourceQuality[source]
                    if source.isupper() and source in SourceQuality.__members__
                    else SourceQuality.from_label(source)
                )
            if isinstance(result, str):
                result = (
                    ResultQuality[result]
                    if result.isupper() and result in ResultQuality.__members__
                    else ResultQuality.from_label(result)
                )
            confidence = data.get("confidence", 0.5)
            return QualityScore(
                source=source,
                result=result,
                confidence=float(confidence),
                evidence_count=int(data.get("evidence_count", 0)),
                contradiction_count=int(data.get("contradiction_count", 0)),
            )

        return self.assess(
            source_description=data.get("source_description", ""),
            success=data.get("success"),
            confirmed=data.get("confirmed", False),
            error=data.get("error", False),
            contradiction=data.get("contradiction", False),
            evidence_count=int(data.get("evidence_count", 0)),
            contradiction_count=int(data.get("contradiction_count", 0)),
            base_confidence=data.get("base_confidence"),
        )

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_confidence(
        source: SourceQuality,
        result: ResultQuality,
        evidence_count: int,
        contradiction_count: int,
    ) -> float:
        """Compute a confidence score from grades and evidence.

        Formula::

            base = (source_rank + result_rank) / (max_source + max_result)
            evidence_factor = 1 + 0.1 * evidence_count
            contradiction_factor = 1 - 0.15 * contradiction_count
            confidence = base * evidence_factor * contradiction_factor

        Clamped to [0, 1].
        """
        max_source = SourceQuality.S.value  # 5
        max_result = ResultQuality.VERIFIED.value  # 4
        base = (source.value + result.value) / (max_source + max_result)
        evidence_factor = 1.0 + 0.1 * evidence_count
        contradiction_factor = 1.0 - 0.15 * contradiction_count
        confidence = base * evidence_factor * contradiction_factor
        return round(max(0.0, min(1.0, confidence)), 4)

    # ------------------------------------------------------------------
    #  Update after task completion
    # ------------------------------------------------------------------
    def update_after_task(
        self,
        current: QualityScore,
        success: Optional[bool] = None,
        confirmed: bool = False,
        error: bool = False,
        contradiction: bool = False,
        new_evidence: int = 0,
        new_contradictions: int = 0,
    ) -> QualityScore:
        """Produce an updated QualityScore after a task completes.

        The source grade is preserved (it doesn't change with use); the
        result grade is reassessed; evidence and contradiction counts
        accumulate; confidence is recomputed.

        Args:
            current:            The current quality score.
            success, confirmed, error, contradiction: Outcome signals.
            new_evidence:       Additional evidence items found.
            new_contradictions: Additional contradictions found.

        Returns:
            A new :class:`QualityScore` with updated fields.
        """
        new_result = self.assess_result(
            success=success,
            confirmed=confirmed,
            error=error,
            contradiction=contradiction,
        )

        # If the new result is worse than the current, downgrade.
        # If better, upgrade.  If the current was FAILED and the new
        # result is better, we allow upgrade (recovery).
        if new_result.value > current.result.value:
            result = new_result
        elif new_result.value < current.result.value:
            result = new_result
        else:
            result = current.result

        evidence_count = current.evidence_count + new_evidence
        contradiction_count = current.contradiction_count + new_contradictions

        confidence = self._compute_confidence(
            current.source, result, evidence_count, contradiction_count,
        )

        return QualityScore(
            source=current.source,
            result=result,
            confidence=confidence,
            evidence_count=evidence_count,
            contradiction_count=contradiction_count,
        )

    def __repr__(self) -> str:
        return "QualityAssessor()"
