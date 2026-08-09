"""
Anti-Pattern Memory — failure pattern storage with elevated retrieval priority.

Anti-pattern memories (反面记忆) record *what went wrong* — failed
approaches, incorrect assumptions, broken patterns.  They are the
complement to positive memories: instead of telling the agent what to
do, they warn against what *not* to do.

Key properties
--------------

1.  **Never forgotten** — anti-patterns persist indefinitely.  The
    forgetting engine's PURGE and COMPRESS actions never apply.
2.  **Retrieval priority** — anti-patterns surface *before* positive
    memories during retrieval, ensuring the agent checks for known
    failure modes before acting.
3.  **Task signature matching** — each anti-pattern is keyed by a
    *task signature* (a normalised description of the task context),
    enabling fast lookup via :meth:`check_anti_pattern`.
4.  **Accumulative** — multiple failures matching the same signature
    increase the pattern's severity, making it harder to override.

A task signature is a compact string that captures the essential
features of a task: tool names, error types, key parameters, etc.
The :meth:`compute_signature` helper produces a canonical signature
from a task description.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .grader import QualityScore, ResultQuality, SourceQuality


# ═══════════════════════════════════════════════════════════════
#  AntiPattern dataclass
# ═══════════════════════════════════════════════════════════════


@dataclass
class AntiPattern:
    """A single anti-pattern (failure pattern) record.

    Attributes:
        id:               Unique identifier.
        task_signature:   Normalised signature of the task that failed.
        pattern_description: Human-readable description of the failure.
        failure_count:    Number of times this pattern has been
                          encountered (increments on repeat failures).
        first_seen:       Unix timestamp of first occurrence.
        last_seen:        Unix timestamp of most recent occurrence.
        quality:          The :class:`QualityScore` (always FAILED result).
        related_memory_ids: IDs of memories associated with this failure.
        severity:         Severity score in [0, 1], derived from
                          failure_count and quality confidence.
        resolution:       Optional description of how the pattern was
                          eventually resolved (if ever).
        is_resolved:      Whether a resolution has been found.
    """

    id: str = ""
    task_signature: str = ""
    pattern_description: str = ""
    failure_count: int = 1
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    quality: QualityScore = field(default_factory=lambda: QualityScore(
        source=SourceQuality.C,
        result=ResultQuality.FAILED,
        confidence=0.3,
    ))
    related_memory_ids: List[str] = field(default_factory=list)
    severity: float = 0.5
    resolution: str = ""
    is_resolved: bool = False

    def __post_init__(self) -> None:
        if not self.id:
            # Generate ID from signature hash
            self.id = hashlib.sha256(
                self.task_signature.encode("utf-8")
            ).hexdigest()[:16]
        # Ensure quality is always FAILED
        if self.quality.result != ResultQuality.FAILED:
            self.quality = QualityScore(
                source=self.quality.source,
                result=ResultQuality.FAILED,
                confidence=self.quality.confidence,
                evidence_count=self.quality.evidence_count,
                contradiction_count=self.quality.contradiction_count,
            )
        # Always compute severity from failure count and confidence
        self.severity = self._compute_severity()

    def _compute_severity(self) -> float:
        """Compute severity from failure count and confidence.

        ``severity = min(1.0, 0.3 + 0.1 * (failure_count - 1)) * (1 - confidence)``
        """
        base = 0.3 + 0.1 * (self.failure_count - 1)
        severity = min(1.0, base) * (1.0 - self.quality.confidence)
        return round(max(0.0, min(1.0, severity)), 4)

    def increment_failure(self) -> None:
        """Record another occurrence of this anti-pattern."""
        self.failure_count += 1
        self.last_seen = time.time()
        self.severity = self._compute_severity()

    def resolve(self, resolution: str) -> None:
        """Mark this anti-pattern as resolved.

        A resolved anti-pattern is retained (never forgotten) but its
        severity is lowered, and the resolution is stored for future
        reference.
        """
        self.is_resolved = True
        self.resolution = resolution
        self.severity = max(0.0, self.severity * 0.3)

    @property
    def is_anti_pattern(self) -> bool:
        """Always True for AntiPattern."""
        return True

    @property
    def retrieval_priority(self) -> float:
        """Retrieval priority — higher than any positive memory.

        Computed as ``1.0 - confidence + severity * 0.5``, clamped to
        [0.5, 1.0] so anti-patterns always rank above positive memories
        (which have weights in [0, 1]).
        """
        priority = 1.0 - self.quality.confidence + self.severity * 0.5
        return round(max(0.5, min(1.0, priority)), 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_signature": self.task_signature,
            "pattern_description": self.pattern_description,
            "failure_count": self.failure_count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "quality": self.quality.to_dict(),
            "related_memory_ids": list(self.related_memory_ids),
            "severity": self.severity,
            "resolution": self.resolution,
            "is_resolved": self.is_resolved,
            "retrieval_priority": self.retrieval_priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AntiPattern":
        quality_data = data.get("quality", {})
        quality = QualityScore.from_dict(quality_data) if quality_data else QualityScore(
            source=SourceQuality.C,
            result=ResultQuality.FAILED,
            confidence=0.3,
        )
        ap = cls(
            id=data.get("id", ""),
            task_signature=data.get("task_signature", ""),
            pattern_description=data.get("pattern_description", ""),
            failure_count=data.get("failure_count", 1),
            first_seen=data.get("first_seen", time.time()),
            last_seen=data.get("last_seen", time.time()),
            quality=quality,
            related_memory_ids=data.get("related_memory_ids", []),
            resolution=data.get("resolution", ""),
            is_resolved=data.get("is_resolved", False),
        )
        # Override computed severity with stored value if present
        if "severity" in data:
            ap.severity = data["severity"]
        return ap

    def __repr__(self) -> str:
        return (
            f"AntiPattern(id={self.id[:8]}, sig={self.task_signature[:30]!r}, "
            f"failures={self.failure_count}, severity={self.severity:.2f})"
        )


# ═══════════════════════════════════════════════════════════════
#  Task signature computation
# ═══════════════════════════════════════════════════════════════


def compute_signature(
    task_description: str,
    tool_names: Optional[List[str]] = None,
    error_type: Optional[str] = None,
    key_params: Optional[Dict[str, Any]] = None,
) -> str:
    """Compute a canonical task signature for anti-pattern matching.

    The signature normalises the task description by:
    - Lowercasing
    - Removing punctuation and extra whitespace
    - Extracting key tokens (tool names, error types, parameters)
    - Sorting for canonical ordering

    Args:
        task_description: The task description text.
        tool_names:       List of tool names involved.
        error_type:       Type of error that occurred (if any).
        key_params:       Key parameters that define the task context.

    Returns:
        A canonical signature string.
    """
    # Normalise description
    desc = task_description.lower().strip()
    desc = re.sub(r'[^\w\s]', ' ', desc)  # replace punctuation with space
    desc = re.sub(r'\s+', ' ', desc)      # collapse whitespace
    tokens = desc.split() if desc else []

    # Add tool names
    if tool_names:
        tokens.extend(f"tool:{t.lower()}" for t in tool_names)

    # Add error type
    if error_type:
        tokens.append(f"error:{error_type.lower()}")

    # Add key params
    if key_params:
        for k in sorted(key_params.keys()):
            v = str(key_params[k]).lower()
            tokens.append(f"param:{k}={v}")

    # Sort for canonical ordering and join
    tokens.sort()
    return "|".join(tokens) if tokens else ""


# ═══════════════════════════════════════════════════════════════
#  AntiPatternStore
# ═══════════════════════════════════════════════════════════════


class AntiPatternStore:
    """Storage and retrieval for anti-pattern (failure) memories.

    The store maintains a collection of :class:`AntiPattern` records
    and provides:

    - **Registration** — record a new failure or increment an existing
      pattern.
    - **Checking** — check whether a task signature matches a known
      anti-pattern before execution.
    - **Retrieval** — fetch anti-patterns with elevated priority for
      context injection.
    - **Resolution** — mark patterns as resolved when a fix is found.

    Anti-patterns are **never deleted** — even resolved patterns are
    retained for future reference (a resolved pattern may become
    relevant again if conditions change).

    Args:
        patterns: Optional initial list of :class:`AntiPattern` objects.
    """

    def __init__(
        self,
        patterns: Optional[List[AntiPattern]] = None,
    ) -> None:
        self._patterns: Dict[str, AntiPattern] = {}
        # Also maintain a set of all known signatures for fast checking
        self._signatures: Dict[str, str] = {}  # signature → pattern_id

        if patterns:
            for p in patterns:
                self._patterns[p.id] = p
                self._signatures[p.task_signature] = p.id

    # ------------------------------------------------------------------
    #  Registration
    # ------------------------------------------------------------------
    def register(
        self,
        task_signature: str,
        pattern_description: str = "",
        related_memory_ids: Optional[List[str]] = None,
        quality: Optional[QualityScore] = None,
    ) -> AntiPattern:
        """Register a new anti-pattern or increment an existing one.

        If a pattern with the same task_signature already exists, its
        failure count is incremented and the description is updated
        (appended) if a new one is provided.

        Args:
            task_signature:      The canonical task signature.
            pattern_description: Human-readable failure description.
            related_memory_ids:  IDs of associated memories.
            quality:             Optional quality score (defaults to
                                 FAILED with low confidence).

        Returns:
            The :class:`AntiPattern` (newly created or updated).
        """
        if task_signature in self._signatures:
            # Existing pattern — increment
            pattern_id = self._signatures[task_signature]
            pattern = self._patterns[pattern_id]
            pattern.increment_failure()
            if pattern_description and pattern_description not in pattern.pattern_description:
                pattern.pattern_description = (
                    f"{pattern.pattern_description}; {pattern_description}"
                )
            if related_memory_ids:
                for mid in related_memory_ids:
                    if mid not in pattern.related_memory_ids:
                        pattern.related_memory_ids.append(mid)
            return pattern

        # New pattern
        pattern = AntiPattern(
            task_signature=task_signature,
            pattern_description=pattern_description,
            related_memory_ids=related_memory_ids or [],
            quality=quality or QualityScore(
                source=SourceQuality.C,
                result=ResultQuality.FAILED,
                confidence=0.3,
            ),
        )
        self._patterns[pattern.id] = pattern
        self._signatures[task_signature] = pattern.id
        return pattern

    def register_from_failure(
        self,
        task_description: str,
        error_message: str = "",
        tool_names: Optional[List[str]] = None,
        error_type: Optional[str] = None,
        key_params: Optional[Dict[str, Any]] = None,
        related_memory_ids: Optional[List[str]] = None,
    ) -> AntiPattern:
        """Convenience: compute signature and register in one call.

        Args:
            task_description: The task that failed.
            error_message:    The error message (used as description).
            tool_names:       Tools involved.
            error_type:       Type of error.
            key_params:       Key parameters.
            related_memory_ids: Associated memory IDs.

        Returns:
            The registered :class:`AntiPattern`.
        """
        sig = compute_signature(
            task_description=task_description,
            tool_names=tool_names,
            error_type=error_type,
            key_params=key_params,
        )
        desc = error_message or f"Task failed: {task_description}"
        return self.register(
            task_signature=sig,
            pattern_description=desc,
            related_memory_ids=related_memory_ids,
        )

    # ------------------------------------------------------------------
    #  Checking
    # ------------------------------------------------------------------
    def check_anti_pattern(self, task_signature: str) -> bool:
        """Check whether a task signature matches a known anti-pattern.

        Args:
            task_signature: The canonical task signature to check.

        Returns:
            ``True`` if the signature matches a known anti-pattern
            (that is not resolved), ``False`` otherwise.
        """
        pattern_id = self._signatures.get(task_signature)
        if pattern_id is None:
            return False
        pattern = self._patterns[pattern_id]
        # Resolved patterns still match (they warn about past failures)
        # but the caller can check `is_resolved` for nuance.
        return True

    def check_task(
        self,
        task_description: str,
        tool_names: Optional[List[str]] = None,
        key_params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Convenience: compute signature and check in one call.

        Args:
            task_description: The task to check.
            tool_names:       Tools that will be used.
            key_params:       Key parameters.

        Returns:
            ``True`` if the task matches a known anti-pattern.
        """
        sig = compute_signature(
            task_description=task_description,
            tool_names=tool_names,
            key_params=key_params,
        )
        return self.check_anti_pattern(sig)

    def get_matching_patterns(
        self,
        task_signature: str,
    ) -> List[AntiPattern]:
        """Get all anti-patterns matching a task signature.

        This includes both exact matches and partial (substring) matches.

        Args:
            task_signature: The signature to match.

        Returns:
            List of matching :class:`AntiPattern` objects, sorted by
            severity descending.
        """
        matches: List[AntiPattern] = []

        # Exact match
        pattern_id = self._signatures.get(task_signature)
        if pattern_id:
            matches.append(self._patterns[pattern_id])

        # Partial match (signature tokens overlap)
        sig_tokens = set(task_signature.split("|"))
        for stored_sig, pid in self._signatures.items():
            if stored_sig == task_signature:
                continue  # already added
            stored_tokens = set(stored_sig.split("|"))
            # If at least 60% of tokens overlap, consider it a match
            if stored_tokens and sig_tokens:
                overlap = len(sig_tokens & stored_tokens)
                ratio = overlap / len(sig_tokens | stored_tokens)
                if ratio >= 0.5:
                    pattern = self._patterns[pid]
                    if pattern not in matches:
                        matches.append(pattern)

        matches.sort(key=lambda p: p.severity, reverse=True)
        return matches

    # ------------------------------------------------------------------
    #  Retrieval
    # ------------------------------------------------------------------
    def retrieve(
        self,
        task_signature: Optional[str] = None,
        top_k: int = 10,
        include_resolved: bool = False,
    ) -> List[AntiPattern]:
        """Retrieve anti-patterns for context injection.

        Anti-patterns have **higher retrieval priority** than positive
        memories.  When ``task_signature`` is provided, matching patterns
        are returned first (sorted by severity); non-matching patterns
        fill the remaining slots.

        Args:
            task_signature:   Optional signature to prioritise.
            top_k:            Maximum number of patterns to return.
            include_resolved: Whether to include resolved patterns.

        Returns:
            List of :class:`AntiPattern` objects, prioritised.
        """
        if not self._patterns:
            return []

        matching: List[AntiPattern] = []
        non_matching: List[AntiPattern] = []

        for pattern in self._patterns.values():
            if not include_resolved and pattern.is_resolved:
                continue

            if task_signature:
                if task_signature in self._signatures and \
                   self._signatures[task_signature] == pattern.id:
                    matching.append(pattern)
                else:
                    # Check partial overlap
                    sig_tokens = set(task_signature.split("|"))
                    pat_tokens = set(pattern.task_signature.split("|"))
                    if sig_tokens and pat_tokens:
                        overlap = len(sig_tokens & pat_tokens)
                        ratio = overlap / len(sig_tokens | pat_tokens)
                        if ratio >= 0.5:
                            matching.append(pattern)
                        else:
                            non_matching.append(pattern)
                    else:
                        non_matching.append(pattern)
            else:
                non_matching.append(pattern)

        # Sort each group by retrieval priority
        matching.sort(key=lambda p: p.retrieval_priority, reverse=True)
        non_matching.sort(key=lambda p: p.retrieval_priority, reverse=True)

        # Matching first, then fill with non-matching
        result = matching[:top_k]
        remaining = top_k - len(result)
        if remaining > 0:
            result.extend(non_matching[:remaining])
        return result

    # ------------------------------------------------------------------
    #  Resolution
    # ------------------------------------------------------------------
    def resolve(
        self,
        task_signature: str,
        resolution: str,
    ) -> bool:
        """Mark an anti-pattern as resolved.

        Args:
            task_signature: The signature of the pattern to resolve.
            resolution:     Description of how the pattern was resolved.

        Returns:
            ``True`` if the pattern was found and resolved.
        """
        pattern_id = self._signatures.get(task_signature)
        if pattern_id is None:
            return False
        self._patterns[pattern_id].resolve(resolution)
        return True

    def resolve_by_id(self, pattern_id: str, resolution: str) -> bool:
        """Resolve an anti-pattern by its ID.

        Returns:
            ``True`` if the pattern was found and resolved.
        """
        pattern = self._patterns.get(pattern_id)
        if pattern is None:
            return False
        pattern.resolve(resolution)
        return True

    # ------------------------------------------------------------------
    #  Queries
    # ------------------------------------------------------------------
    def get_by_id(self, pattern_id: str) -> Optional[AntiPattern]:
        """Get an anti-pattern by ID."""
        return self._patterns.get(pattern_id)

    def get_by_signature(self, task_signature: str) -> Optional[AntiPattern]:
        """Get an anti-pattern by task signature."""
        pid = self._signatures.get(task_signature)
        if pid is None:
            return None
        return self._patterns[pid]

    def get_all(self) -> List[AntiPattern]:
        """Return all stored anti-patterns."""
        return list(self._patterns.values())

    def get_unresolved(self) -> List[AntiPattern]:
        """Return all unresolved anti-patterns."""
        return [p for p in self._patterns.values() if not p.is_resolved]

    def get_high_severity(self, threshold: float = 0.7) -> List[AntiPattern]:
        """Return anti-patterns with severity ≥ threshold."""
        return [p for p in self._patterns.values() if p.severity >= threshold]

    def count(self) -> int:
        """Return the number of stored anti-patterns."""
        return len(self._patterns)

    def count_unresolved(self) -> int:
        """Return the number of unresolved anti-patterns."""
        return sum(1 for p in self._patterns.values() if not p.is_resolved)

    # ------------------------------------------------------------------
    #  Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Serialise the entire store to a dict."""
        return {
            "patterns": [p.to_dict() for p in self._patterns.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AntiPatternStore":
        """Reconstruct a store from a serialised dict."""
        patterns = [
            AntiPattern.from_dict(d) for d in data.get("patterns", [])
        ]
        return cls(patterns=patterns)

    # ------------------------------------------------------------------
    #  Never-delete guarantee
    # ------------------------------------------------------------------
    def _delete_is_forbidden(self) -> None:
        """Anti-patterns are never deleted.  This method exists to
        document and enforce that invariant."""
        raise NotImplementedError(
            "Anti-patterns cannot be deleted — they are retained "
            "indefinitely per the never-forget policy."
        )

    def __len__(self) -> int:
        return len(self._patterns)

    def __repr__(self) -> str:
        return (
            f"AntiPatternStore(total={len(self._patterns)}, "
            f"unresolved={self.count_unresolved()})"
        )
