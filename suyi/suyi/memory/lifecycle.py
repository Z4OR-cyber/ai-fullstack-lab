"""Memory Lifecycle — four-stage memory management.

Manages the transition of memory entries through four stages, implementing
a *gradient forgetting* mechanism inspired by biological memory
consolidation:

::

    fresh  →  consolidation  →  compression  →  forgetting

Confidence model
----------------

Confidence is computed as::

    confidence = base_score × time_decay × (1 + success × 0.1 − fail × 0.05)

where ``time_decay = exp(−days / half_life)`` and ``half_life = 7`` days.

Stage transitions
-----------------

================  ===============  ==========================================
Stage             Condition        Action
================  ===============  ==========================================
**fresh**          confidence > 0.8  Candidate for consolidation → promote to
                                   long-term semantic memory.
**consolidation**  0.2 < conf ≤ 0.8  Normal — no action needed.
**compression**    conf ≤ 0.2 AND   Compress to a short summary, keep the
                  days unaccessed   summary only.
                  ≥ half_life
**forgetting**     conf ≤ 0.2 AND   Delete the entry entirely.
                  days unaccessed
                  ≥ 2 × half_life
================  ===============  ==========================================
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple


class MemoryLifecycle:
    """Memory lifecycle manager — drives the four-stage forgetting process.

    The lifecycle operates on semantic-memory entries (or any dict with
    the required fields) and returns actions to be executed by the
    :class:`~evoagent.memory.MemoryManager`.

    Attributes:
        half_life: Time-decay half-life in days (default 7).
        consolidate_threshold: Confidence above which an entry is a
            consolidation candidate (default 0.8).
        forget_threshold: Confidence below which an entry is at risk of
            forgetting (default 0.2).
    """

    # Stage constants
    FRESH = 'fresh'
    CONSOLIDATION = 'consolidation'
    COMPRESSION = 'compression'
    FORGETTING = 'forgetting'

    ALL_STAGES = (FRESH, CONSOLIDATION, COMPRESSION, FORGETTING)

    def __init__(
        self,
        half_life: float = 7.0,
        consolidate_threshold: float = 0.8,
        forget_threshold: float = 0.2,
    ) -> None:
        self.half_life = half_life
        self.consolidate_threshold = consolidate_threshold
        self.forget_threshold = forget_threshold

    # ------------------------------------------------------------------
    #  Confidence computation
    # ------------------------------------------------------------------
    @staticmethod
    def compute_time_decay(days: float, half_life: float = 7.0) -> float:
        """Compute exponential time decay.

        ``decay = exp(−days / half_life)``

        At ``days == half_life``, decay ≈ 0.37 (e⁻¹).
        At ``days == 0``, decay = 1.0 (no decay).

        Args:
            days: Number of days since last access.
            half_life: Half-life in days.

        Returns:
            Decay factor in (0, 1].
        """
        if days <= 0:
            return 1.0
        return math.exp(-days / half_life)

    def compute_confidence(
        self,
        base_score: float,
        success_count: int,
        fail_count: int,
        days_since_access: float,
    ) -> float:
        """Compute the current confidence of a memory entry.

        .. math::
            \\text{confidence} = \\text{base} \\times
            e^{-d/h} \\times (1 + 0.1 \\cdot s - 0.05 \\cdot f)

        Args:
            base_score: The base confidence / importance score [0, 1].
            success_count: Number of successful uses.
            fail_count: Number of failed uses.
            days_since_access: Days since the entry was last accessed.

        Returns:
            Confidence score clamped to [0, 1].
        """
        decay = self.compute_time_decay(days_since_access, self.half_life)
        modifier = 1.0 + success_count * 0.1 - fail_count * 0.05
        confidence = base_score * decay * modifier
        return max(0.0, min(1.0, confidence))

    def compute_confidence_for_entry(self, entry: Dict[str, Any]) -> float:
        """Compute confidence for a memory entry dict.

        The dict must contain: ``confidence`` (base), ``success_count``,
        ``fail_count``, and ``last_accessed`` (Unix timestamp).

        Args:
            entry: A memory entry dict.

        Returns:
            Current confidence score.
        """
        base = entry.get('confidence', 0.5)
        success = entry.get('success_count', 0)
        fail = entry.get('fail_count', 0)
        last_accessed = entry.get('last_accessed', time.time())
        days = (time.time() - last_accessed) / 86400.0
        return self.compute_confidence(base, success, fail, days)

    # ------------------------------------------------------------------
    #  Stage determination
    # ------------------------------------------------------------------
    def determine_stage(
        self,
        confidence: float,
        days_since_access: float,
    ) -> str:
        """Determine the lifecycle stage for an entry.

        Args:
            confidence: Current confidence score.
            days_since_access: Days since last access.

        Returns:
            One of :attr:`ALL_STAGES`.
        """
        if confidence > self.consolidate_threshold:
            return self.FRESH

        if confidence <= self.forget_threshold:
            # Check if old enough for forgetting
            if days_since_access >= 2 * self.half_life:
                return self.FORGETTING
            elif days_since_access >= self.half_life:
                return self.COMPRESSION
            else:
                return self.CONSOLIDATION

        return self.CONSOLIDATION

    def determine_stage_for_entry(self, entry: Dict[str, Any]) -> str:
        """Determine the lifecycle stage for a memory entry dict."""
        confidence = self.compute_confidence_for_entry(entry)
        last_accessed = entry.get('last_accessed', time.time())
        days = (time.time() - last_accessed) / 86400.0
        return self.determine_stage(confidence, days)

    # ------------------------------------------------------------------
    #  Batch processing
    # ------------------------------------------------------------------
    def process_entries(
        self,
        entries: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Process a batch of entries and classify them by lifecycle stage.

        Args:
            entries: List of memory entry dicts.

        Returns:
            A dict mapping stage names to lists of entries::

                {
                    'fresh': [...],
                    'consolidation': [...],
                    'compression': [...],
                    'forgetting': [...],
                }
        """
        result: Dict[str, List[Dict[str, Any]]] = {
            stage: [] for stage in self.ALL_STAGES
        }
        for entry in entries:
            # Compute updated confidence
            updated_conf = self.compute_confidence_for_entry(entry)
            entry = dict(entry)
            entry['_computed_confidence'] = round(updated_conf, 4)

            last_accessed = entry.get('last_accessed', time.time())
            days = (time.time() - last_accessed) / 86400.0
            stage = self.determine_stage(updated_conf, days)
            result[stage].append(entry)
        return result

    # ------------------------------------------------------------------
    #  Action generation
    # ------------------------------------------------------------------
    def get_consolidation_candidates(
        self,
        entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Return entries that should be promoted to long-term memory.

        An entry is a consolidation candidate when its computed
        confidence exceeds :attr:`consolidate_threshold`.

        Args:
            entries: List of memory entry dicts.

        Returns:
            List of entries to consolidate, each with an added
            ``_computed_confidence`` field.
        """
        candidates: List[Dict[str, Any]] = []
        for entry in entries:
            conf = self.compute_confidence_for_entry(entry)
            if conf > self.consolidate_threshold:
                e = dict(entry)
                e['_computed_confidence'] = round(conf, 4)
                candidates.append(e)
        return candidates

    def get_forgetting_candidates(
        self,
        entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Return entries that should be forgotten (deleted).

        An entry is a forgetting candidate when its confidence is below
        :attr:`forget_threshold` **and** it has been unaccessed for at
        least ``2 × half_life`` days.

        Args:
            entries: List of memory entry dicts.

        Returns:
            List of entries to forget.
        """
        candidates: List[Dict[str, Any]] = []
        now = time.time()
        for entry in entries:
            conf = self.compute_confidence_for_entry(entry)
            last_accessed = entry.get('last_accessed', now)
            days = (now - last_accessed) / 86400.0
            if conf <= self.forget_threshold and days >= 2 * self.half_life:
                e = dict(entry)
                e['_computed_confidence'] = round(conf, 4)
                candidates.append(e)
        return candidates

    def get_compression_candidates(
        self,
        entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Return entries that should be compressed to summaries.

        An entry is a compression candidate when its confidence is below
        :attr:`forget_threshold` **and** it has been unaccessed for at
        least ``half_life`` days (but less than ``2 × half_life``).

        Args:
            entries: List of memory entry dicts.

        Returns:
            List of entries to compress.
        """
        candidates: List[Dict[str, Any]] = []
        now = time.time()
        for entry in entries:
            conf = self.compute_confidence_for_entry(entry)
            last_accessed = entry.get('last_accessed', now)
            days = (now - last_accessed) / 86400.0
            if (conf <= self.forget_threshold
                    and self.half_life <= days < 2 * self.half_life):
                e = dict(entry)
                e['_computed_confidence'] = round(conf, 4)
                candidates.append(e)
        return candidates

    # ------------------------------------------------------------------
    #  Summary helper
    # ------------------------------------------------------------------
    @staticmethod
    def summarize_entry(entry: Dict[str, Any], max_chars: int = 200) -> str:
        """Produce a short summary of an entry's content.

        Simple truncation-based summarisation.  In a full system this
        would call a small LLM, but for this framework a truncation
        heuristic is sufficient.

        Args:
            entry: A memory entry dict.
            max_chars: Maximum characters in the summary.

        Returns:
            A summary string.
        """
        content = entry.get('content', '')
        if len(content) <= max_chars:
            return content
        # Try to cut at a sentence boundary
        cut = content[:max_chars]
        # Find last sentence-ending punctuation
        for punct in ['. ', '。', '!', '？', '?']:
            idx = cut.rfind(punct)
            if idx > max_chars * 0.5:
                return cut[:idx + len(punct)].strip()
        return cut.rstrip() + '...'

    # ------------------------------------------------------------------
    #  Reporting
    # ------------------------------------------------------------------
    def lifecycle_report(
        self,
        entries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate a summary report of the lifecycle state of entries.

        Args:
            entries: List of memory entry dicts.

        Returns:
            A dict with counts per stage and a list of recommended
            actions.
        """
        classified = self.process_entries(entries)
        report: Dict[str, Any] = {
            'total': len(entries),
            'stages': {stage: len(items) for stage, items in classified.items()},
            'actions': [],
        }

        # Consolidation actions
        for entry in classified[self.FRESH]:
            report['actions'].append({
                'action': 'consolidate',
                'entry_id': entry.get('id'),
                'confidence': entry.get('_computed_confidence'),
            })

        # Compression actions
        for entry in classified[self.COMPRESSION]:
            report['actions'].append({
                'action': 'compress',
                'entry_id': entry.get('id'),
                'confidence': entry.get('_computed_confidence'),
                'summary': self.summarize_entry(entry),
            })

        # Forgetting actions
        for entry in classified[self.FORGETTING]:
            report['actions'].append({
                'action': 'forget',
                'entry_id': entry.get('id'),
                'confidence': entry.get('_computed_confidence'),
            })

        return report

    def __repr__(self) -> str:
        return (
            f"MemoryLifecycle(half_life={self.half_life}d, "
            f"consolidate>{self.consolidate_threshold}, "
            f"forget<{self.forget_threshold})"
        )
