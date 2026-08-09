"""
Loop Template Memory — reusable execution patterns for the Agent Loop.

This module implements Phase 14 of the ALA (Adaptive Loop Architecture)
self-evolution system.  While Phase 13 added *quality* and *forgetting*
for individual memories, Phase 14 lets the agent remember **how** it
approached a task — the sequence of perceive → plan → execute → verify →
reflect phases, the tools it used, the order it called them, and when
it paused to reflect.

A *Loop Template* captures a proven execution pattern for a class of
tasks.  When the agent encounters a new task, it can look up a matching
template and follow its phase sequence and tool ordering instead of
planning from scratch.  Templates accumulate usage statistics
(success rate, average iterations, average cost) so the agent can
prefer templates that have worked well.

Key concepts
------------

1.  **LoopPhase** — a single step in the loop (perceive, plan, execute,
    verify, reflect) with an action description, the tools it uses,
    and a condition for proceeding.

2.  **LoopTemplate** — a complete reusable execution pattern:
    - A sequence of :class:`LoopPhase` objects.
    - The tools used and their call order.
    - Reflection points (steps after which the agent should pause).
    - Termination conditions.
    - Usage statistics (success rate, avg iterations, avg cost).
    - A :class:`QualityScore` (reused from Phase 13).
    - Parent/variant links for A/B testing and mutation tracking.

3.  **LoopTemplateStore** — persistence layer backed by
    :class:`SQLiteBackend`.  Provides FTS5 full-text search for
    template matching, ranking by task-signature similarity, success
    rate, confidence, and freshness.

4.  **DefaultTemplates** — three built-in templates:
    - **Standard ReAct** — the classic perceive → plan → execute loop.
    - **Plan-Execute** — plan fully, then execute sequentially.
    - **Reflective** — adds explicit reflection after each execution.

Template ranking formula
------------------------

When searching for the best template for a new task, each candidate is
scored::

    score = 0.4 * signature_similarity
          + 0.3 * success_rate
          + 0.2 * confidence
          + 0.1 * freshness

Where:

- **signature_similarity** ∈ [0, 1] — Jaccard similarity between the
  query's task signature tokens and the template's signature tokens.
- **success_rate** ∈ [0, 1] — historical success rate.
- **confidence** ∈ [0, 1] — from the template's :class:`QualityScore`.
- **freshness** ∈ [0, 1] — 1.0 if used today, decaying over 30 days.
"""

from __future__ import annotations

import json
import math
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .grader import QualityScore, ResultQuality, SourceQuality


# ═══════════════════════════════════════════════════════════════
#  LoopPhase dataclass
# ═══════════════════════════════════════════════════════════════

#: Valid phase names for a LoopPhase.
VALID_PHASE_NAMES = frozenset({
    "perceive", "plan", "execute", "verify", "reflect",
})


@dataclass
class LoopPhase:
    """A single phase in a Loop execution template.

    Attributes:
        name:      Phase name — one of ``perceive``, ``plan``,
                   ``execute``, ``verify``, ``reflect``.
        action:    Human-readable description of the action to take
                   in this phase.
        tools:     List of tool names available/used in this phase.
        condition: Condition string for proceeding to the next phase
                   (e.g. ``"confidence > 0.8"`` or ``"always"``).
    """

    name: str = "execute"
    action: str = ""
    tools: List[str] = field(default_factory=list)
    condition: str = "always"

    def __post_init__(self) -> None:
        if self.name not in VALID_PHASE_NAMES:
            raise ValueError(
                f"Invalid phase name {self.name!r}. "
                f"Must be one of: {sorted(VALID_PHASE_NAMES)}"
            )

    # ------------------------------------------------------------------
    #  Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "name": self.name,
            "action": self.action,
            "tools": list(self.tools),
            "condition": self.condition,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoopPhase":
        """Reconstruct from a dict (produced by :meth:`to_dict`)."""
        return cls(
            name=data.get("name", "execute"),
            action=data.get("action", ""),
            tools=list(data.get("tools", [])),
            condition=data.get("condition", "always"),
        )

    def __repr__(self) -> str:
        return (
            f"LoopPhase(name={self.name!r}, "
            f"action={self.action[:40]!r}, "
            f"tools={self.tools})"
        )


# ═══════════════════════════════════════════════════════════════
#  LoopTemplate dataclass
# ═══════════════════════════════════════════════════════════════


def _now_iso() -> str:
    """Return an ISO-8601 UTC timestamp string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _parse_iso(ts: str) -> float:
    """Parse an ISO-8601 timestamp to a Unix epoch float.

    Handles the ``Z`` suffix and basic formats.  Timestamps with a
    trailing ``Z`` are treated as UTC (using ``calendar.timegm``).
    Returns 0.0 on parse failure.
    """
    if not ts:
        return 0.0
    import calendar
    is_utc = ts.endswith("Z")
    clean = ts.rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            struct = time.strptime(clean, fmt)
            if is_utc:
                return float(calendar.timegm(struct))
            return time.mktime(struct)
        except (ValueError, OverflowError):
            continue
    return 0.0


@dataclass
class LoopTemplate:
    """A reusable Loop execution pattern for a class of tasks.

    Attributes:
        id:                    Unique identifier (UUID string).
        task_signature:        Canonical task type signature for
                               matching (normalised tokens).
        task_description:      Human-readable task description.
        phases:                Ordered list of :class:`LoopPhase`.
        tools:                 List of all tool names used.
        tool_order:            Preferred tool call order.
        reflection_points:     Step indices after which to reflect
                               (0-based, relative to phases).
        max_iterations:        Maximum loop iterations.
        termination_conditions: List of condition strings.
        success_count:         Number of successful uses.
        failure_count:         Number of failed uses.
        success_rate:          success_count / (success + failure).
        avg_iterations:        Average iterations per use.
        avg_cost:              Average cost per use.
        quality:               :class:`QualityScore` for this template.
        created_at:            ISO timestamp of creation.
        last_used:             ISO timestamp of last use.
        use_count:             Total times used.
        parent_id:             Parent template ID (evolution source).
        mutations:             List of mutation descriptions.
        variants:              List of variant template IDs (A/B test).
        is_active:             Whether this template is active.
    """

    id: str = ""
    task_signature: str = ""
    task_description: str = ""
    phases: List[LoopPhase] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    tool_order: List[str] = field(default_factory=list)
    reflection_points: List[int] = field(default_factory=list)
    max_iterations: int = 10
    termination_conditions: List[str] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    avg_iterations: float = 0.0
    avg_cost: float = 0.0
    quality: QualityScore = field(default_factory=QualityScore)
    created_at: str = field(default_factory=_now_iso)
    last_used: str = field(default_factory=_now_iso)
    use_count: int = 0
    parent_id: Optional[str] = None
    mutations: List[str] = field(default_factory=list)
    variants: List[str] = field(default_factory=list)
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
        # Compute initial success_rate
        total = self.success_count + self.failure_count
        if total > 0:
            self.success_rate = self.success_count / total

    # ------------------------------------------------------------------
    #  Derived properties
    # ------------------------------------------------------------------
    @property
    def total_uses(self) -> int:
        """Total number of uses (success + failure)."""
        return self.success_count + self.failure_count

    @property
    def is_proven(self) -> bool:
        """True if the template has been used successfully at least once."""
        return self.success_count > 0

    @property
    def confidence(self) -> float:
        """Shortcut to the quality's confidence value."""
        return self.quality.confidence

    @property
    def freshness(self) -> float:
        """Freshness score in [0, 1].

        1.0 if used today, decaying linearly to 0.0 over 30 days.
        """
        last = _parse_iso(self.last_used)
        if last <= 0:
            return 0.0
        now = time.time()
        elapsed_days = (now - last) / 86_400.0
        if elapsed_days <= 0:
            return 1.0
        if elapsed_days >= 30:
            return 0.0
        return round(1.0 - elapsed_days / 30.0, 4)

    # ------------------------------------------------------------------
    #  Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dict (full round-trip)."""
        return {
            "id": self.id,
            "task_signature": self.task_signature,
            "task_description": self.task_description,
            "phases": [p.to_dict() for p in self.phases],
            "tools": list(self.tools),
            "tool_order": list(self.tool_order),
            "reflection_points": list(self.reflection_points),
            "max_iterations": self.max_iterations,
            "termination_conditions": list(self.termination_conditions),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": round(self.success_rate, 4),
            "avg_iterations": round(self.avg_iterations, 4),
            "avg_cost": round(self.avg_cost, 4),
            "quality": self.quality.to_dict(),
            "created_at": self.created_at,
            "last_used": self.last_used,
            "use_count": self.use_count,
            "parent_id": self.parent_id,
            "mutations": list(self.mutations),
            "variants": list(self.variants),
            "is_active": self.is_active,
        }

    def to_db_dict(self) -> Dict[str, Any]:
        """Serialise to a dict suitable for ``SQLiteBackend.save_loop_template``.

        This flattens the phases/tools/etc. into ``*_json`` fields and
        extracts quality fields for the database columns.
        """
        return {
            "id": self.id,
            "task_signature": self.task_signature,
            "task_description": self.task_description,
            "phases_json": json.dumps(
                [p.to_dict() for p in self.phases], ensure_ascii=False,
            ),
            "tools_json": json.dumps(self.tools, ensure_ascii=False),
            "tool_order_json": json.dumps(self.tool_order, ensure_ascii=False),
            "reflection_points_json": json.dumps(
                self.reflection_points, ensure_ascii=False,
            ),
            "max_iterations": self.max_iterations,
            "termination_conditions_json": json.dumps(
                self.termination_conditions, ensure_ascii=False,
            ),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate,
            "avg_iterations": self.avg_iterations,
            "avg_cost": self.avg_cost,
            "source_quality": self.quality.source.grade_letter,
            "result_quality": self.quality.result.name,
            "confidence": self.quality.confidence,
            "evidence_count": self.quality.evidence_count,
            "contradiction_count": self.quality.contradiction_count,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "use_count": self.use_count,
            "parent_id": self.parent_id,
            "mutations": list(self.mutations),
            "variants": list(self.variants),
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoopTemplate":
        """Reconstruct from a dict (produced by :meth:`to_dict`).

        Also accepts the flattened ``*_json`` fields produced by
        :meth:`to_db_dict` / ``SQLiteBackend.get_loop_template``.
        """
        # Parse phases — accept either a list of dicts or a JSON string
        phases_raw = data.get("phases")
        if phases_raw is None:
            phases_raw = data.get("phases_json", "[]")
        if isinstance(phases_raw, str):
            try:
                phases_raw = json.loads(phases_raw)
            except (json.JSONDecodeError, TypeError):
                phases_raw = []
        phases = [
            LoopPhase.from_dict(p) if isinstance(p, dict) else p
            for p in phases_raw
        ]

        # Parse list fields — accept JSON strings or lists
        def _parse_list(key: str, json_key: str) -> List[Any]:
            val = data.get(key)
            if val is None:
                val = data.get(json_key, "[]")
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    return []
            return list(val) if val else []

        tools = _parse_list("tools", "tools_json")
        tool_order = _parse_list("tool_order", "tool_order_json")
        reflection_points = _parse_list("reflection_points", "reflection_points_json")
        termination_conditions = _parse_list(
            "termination_conditions", "termination_conditions_json",
        )

        # Parse quality — accept dict or individual fields
        quality_data = data.get("quality")
        if quality_data and isinstance(quality_data, dict):
            quality = QualityScore.from_dict(quality_data)
        elif quality_data and isinstance(quality_data, QualityScore):
            quality = quality_data
        else:
            # Reconstruct from flattened DB fields
            source_q = data.get("source_quality", "C")
            result_q = data.get("result_quality", "SPECULATIVE")
            try:
                source = (
                    SourceQuality[source_q]
                    if isinstance(source_q, str) and source_q in SourceQuality.__members__
                    else SourceQuality.from_label(str(source_q))
                )
            except (ValueError, KeyError):
                source = SourceQuality.C
            try:
                result = (
                    ResultQuality[result_q]
                    if isinstance(result_q, str) and result_q in ResultQuality.__members__
                    else ResultQuality.from_label(str(result_q))
                )
            except (ValueError, KeyError):
                result = ResultQuality.SPECULATIVE
            quality = QualityScore(
                source=source,
                result=result,
                confidence=float(data.get("confidence", 0.5)),
                evidence_count=int(data.get("evidence_count", 0)),
                contradiction_count=int(data.get("contradiction_count", 0)),
            )

        return cls(
            id=data.get("id", ""),
            task_signature=data.get("task_signature", ""),
            task_description=data.get("task_description", ""),
            phases=phases,
            tools=tools,
            tool_order=tool_order,
            reflection_points=[int(x) for x in reflection_points],
            max_iterations=int(data.get("max_iterations", 10)),
            termination_conditions=termination_conditions,
            success_count=int(data.get("success_count", 0)),
            failure_count=int(data.get("failure_count", 0)),
            success_rate=float(data.get("success_rate", 0.0)),
            avg_iterations=float(data.get("avg_iterations", 0.0)),
            avg_cost=float(data.get("avg_cost", 0.0)),
            quality=quality,
            created_at=data.get("created_at", _now_iso()),
            last_used=data.get("last_used", _now_iso()),
            use_count=int(data.get("use_count", 0)),
            parent_id=data.get("parent_id"),
            mutations=_parse_list("mutations", "mutations_json"),
            variants=_parse_list("variants", "variants_json"),
            is_active=bool(data.get("is_active", True)),
        )

    def __repr__(self) -> str:
        return (
            f"LoopTemplate(id={self.id[:8]}, "
            f"sig={self.task_signature[:30]!r}, "
            f"phases={len(self.phases)}, "
            f"success={self.success_rate:.0%}, "
            f"uses={self.use_count})"
        )


# ═══════════════════════════════════════════════════════════════
#  Signature similarity helper
# ═══════════════════════════════════════════════════════════════


def _tokenize_signature(signature: str) -> set:
    """Split a task signature into a set of tokens.

    Signatures use ``|`` as a token separator (consistent with
    :func:`anti_pattern.compute_signature`).  Falls back to
    whitespace splitting for plain-text signatures.
    """
    if not signature:
        return set()
    if "|" in signature:
        return {t for t in signature.split("|") if t}
    # Plain text — normalise and split on whitespace
    desc = signature.lower().strip()
    desc = re.sub(r"[^\w\s]", " ", desc)
    desc = re.sub(r"\s+", " ", desc)
    return {t for t in desc.split() if t}


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Jaccard similarity between two sets: |A∩B| / |A∪B|."""
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    intersection = set_a & set_b
    return len(intersection) / len(union)


def compute_task_signature(task_description: str) -> str:
    """Compute a canonical task signature for template matching.

    Similar to :func:`anti_pattern.compute_signature` but focused on
    task-type identification for loop templates.

    Args:
        task_description: The task description text.

    Returns:
        A canonical signature string with ``|``-separated sorted tokens.
    """
    if not task_description:
        return ""
    desc = task_description.lower().strip()
    desc = re.sub(r"[^\w\s]", " ", desc)
    desc = re.sub(r"\s+", " ", desc)
    tokens = desc.split() if desc else []
    tokens.sort()
    return "|".join(tokens) if tokens else ""


# ═══════════════════════════════════════════════════════════════
#  LoopTemplateStore
# ═══════════════════════════════════════════════════════════════


class LoopTemplateStore:
    """Storage and retrieval for Loop execution templates.

    Backed by :class:`SQLiteBackend`, this store provides:

    - **Persistence** — save/load templates to/from SQLite.
    - **Full-text search** — FTS5 search across task descriptions.
    - **Smart ranking** — find the best template by combining
      signature similarity, success rate, confidence, and freshness.
    - **Statistics** — update success/failure/iteration/cost stats.
    - **Lifecycle** — deactivate underperforming templates.

    Ranking weights::

        signature_similarity × 0.4
      + success_rate          × 0.3
      + confidence            × 0.2
      + freshness             × 0.1

    Args:
        backend: A :class:`SQLiteBackend` instance.  If ``None``,
                 a new in-memory backend is created (useful for tests).
    """

    #: Weight for task-signature similarity in ranking.
    WEIGHT_SIMILARITY: float = 0.4

    #: Weight for historical success rate in ranking.
    WEIGHT_SUCCESS_RATE: float = 0.3

    #: Weight for quality confidence in ranking.
    WEIGHT_CONFIDENCE: float = 0.2

    #: Weight for freshness (recent use) in ranking.
    WEIGHT_FRESHNESS: float = 0.1

    def __init__(self, backend: Optional[Any] = None) -> None:
        if backend is not None:
            self._backend = backend
        else:
            # Lazy import to avoid circular dependency at module level
            from ..persistence.sqlite_backend import SQLiteBackend
            import tempfile, os
            tmpdir = tempfile.mkdtemp()
            self._backend = SQLiteBackend(
                db_path=os.path.join(tmpdir, "loop_templates.db"),
            )

    # ------------------------------------------------------------------
    #  CRUD
    # ------------------------------------------------------------------
    def save_template(self, template: LoopTemplate) -> None:
        """Save a template to the SQLite backend.

        If a template with the same ID exists, it is updated.

        Args:
            template: The :class:`LoopTemplate` to save.
        """
        self._backend.save_loop_template(template.to_db_dict())

    def get_template(self, template_id: str) -> Optional[LoopTemplate]:
        """Retrieve a template by ID.

        Args:
            template_id: The template's unique ID.

        Returns:
            The :class:`LoopTemplate`, or ``None`` if not found.
        """
        row = self._backend.get_loop_template(template_id)
        if row is None:
            return None
        return LoopTemplate.from_dict(row)

    def list_templates(
        self,
        task_signature: Optional[str] = None,
    ) -> List[LoopTemplate]:
        """List templates, optionally filtered by task signature.

        Args:
            task_signature: If provided, only templates with this
                exact signature are returned.

        Returns:
            List of :class:`LoopTemplate` objects, ordered by
            success_rate then use_count (both descending).
        """
        rows = self._backend.list_loop_templates(task_signature)
        return [LoopTemplate.from_dict(r) for r in rows]

    # ------------------------------------------------------------------
    #  Smart matching
    # ------------------------------------------------------------------
    def find_best_template(
        self,
        task_description: str,
        task_signature: Optional[str] = None,
    ) -> Optional[LoopTemplate]:
        """Find the best matching template for a task.

        Combines FTS5 full-text search with ranking by:

        1.  **Signature similarity** (0.4) — Jaccard similarity between
            the query signature and each candidate's signature.
        2.  **Success rate** (0.3) — historical success rate.
        3.  **Confidence** (0.2) — from the template's quality score.
        4.  **Freshness** (0.1) — how recently the template was used.

        Only active templates are considered.

        Args:
            task_description: The new task's description.
            task_signature:   Optional pre-computed task signature.
                              If ``None``, computed from the description.

        Returns:
            The best-matching :class:`LoopTemplate`, or ``None`` if
            no templates match.
        """
        if not task_description and not task_signature:
            return None

        # Compute query signature if not provided
        query_sig = task_signature or compute_task_signature(task_description)
        query_tokens = _tokenize_signature(query_sig)

        # Gather candidates:
        # 1. Search by task_description (FTS5 / LIKE)
        search_results = self._backend.search_loop_templates(
            task_description or query_sig, limit=50,
        )

        # 2. Also search by signature tokens if we have them
        if query_sig:
            sig_results = self._backend.search_loop_templates(
                query_sig, limit=50,
            )
            # Merge by ID, avoiding duplicates
            seen_ids = {r["id"] for r in search_results}
            for r in sig_results:
                if r["id"] not in seen_ids:
                    search_results.append(r)
                    seen_ids.add(r["id"])

        # 3. Also list all active templates if search returned nothing
        if not search_results:
            all_active = self._backend.list_loop_templates()
            search_results = all_active

        if not search_results:
            return None

        # Rank candidates
        best_template: Optional[LoopTemplate] = None
        best_score: float = -1.0

        for row in search_results:
            template = LoopTemplate.from_dict(row)

            # Signature similarity
            tpl_tokens = _tokenize_signature(template.task_signature)
            if query_tokens and tpl_tokens:
                similarity = _jaccard_similarity(query_tokens, tpl_tokens)
            elif not query_tokens and not tpl_tokens:
                # No signature info — neutral
                similarity = 0.5
            else:
                # One has signature, the other doesn't — partial match
                similarity = 0.1

            # Success rate
            success_rate = template.success_rate

            # Confidence
            confidence = template.confidence

            # Freshness
            freshness = template.freshness

            # Combined score
            score = (
                self.WEIGHT_SIMILARITY * similarity
                + self.WEIGHT_SUCCESS_RATE * success_rate
                + self.WEIGHT_CONFIDENCE * confidence
                + self.WEIGHT_FRESHNESS * freshness
            )

            if score > best_score:
                best_score = score
                best_template = template

        return best_template

    # ------------------------------------------------------------------
    #  Statistics
    # ------------------------------------------------------------------
    def update_stats(
        self,
        template_id: str,
        success: bool,
        iterations: int,
        cost: float,
    ) -> None:
        """Update usage statistics for a template.

        Delegates to ``SQLiteBackend.update_loop_template_stats``.

        Args:
            template_id: The template's unique ID.
            success:     Whether the usage was successful.
            iterations:  Number of iterations used.
            cost:        Cost incurred.
        """
        self._backend.update_loop_template_stats(
            template_id, success, iterations, cost,
        )

    # ------------------------------------------------------------------
    #  Lifecycle
    # ------------------------------------------------------------------
    def deactivate_template(self, template_id: str) -> bool:
        """Deactivate a template (soft delete).

        Args:
            template_id: The template's unique ID.

        Returns:
            ``True`` if the template was found and deactivated.
        """
        return self._backend.deactivate_loop_template(template_id)

    # ------------------------------------------------------------------
    #  Evolution support
    # ------------------------------------------------------------------
    def create_variant(
        self,
        parent_id: str,
        mutations: List[str],
        modified_phases: Optional[List[LoopPhase]] = None,
        modified_tools: Optional[List[str]] = None,
        modified_tool_order: Optional[List[str]] = None,
        modified_max_iterations: Optional[int] = None,
        modified_reflection_points: Optional[List[int]] = None,
    ) -> Optional[LoopTemplate]:
        """Create a variant of an existing template (A/B testing).

        The variant inherits the parent's task signature and description
        but gets its own ID, parent_id link, and mutation record.

        Args:
            parent_id:               The parent template's ID.
            mutations:               List of mutation descriptions.
            modified_phases:         New phases (inherits parent's if None).
            modified_tools:          New tools (inherits if None).
            modified_tool_order:     New tool order (inherits if None).
            modified_max_iterations: New max iterations (inherits if None).
            modified_reflection_points: New reflection points (inherits if None).

        Returns:
            The new variant :class:`LoopTemplate`, or ``None`` if the
            parent was not found.
        """
        parent = self.get_template(parent_id)
        if parent is None:
            return None

        variant = LoopTemplate(
            id=str(uuid.uuid4()),
            task_signature=parent.task_signature,
            task_description=parent.task_description,
            phases=modified_phases if modified_phases is not None else list(parent.phases),
            tools=modified_tools if modified_tools is not None else list(parent.tools),
            tool_order=(
                modified_tool_order
                if modified_tool_order is not None
                else list(parent.tool_order)
            ),
            reflection_points=(
                modified_reflection_points
                if modified_reflection_points is not None
                else list(parent.reflection_points)
            ),
            max_iterations=(
                modified_max_iterations
                if modified_max_iterations is not None
                else parent.max_iterations
            ),
            termination_conditions=list(parent.termination_conditions),
            quality=QualityScore(
                source=parent.quality.source,
                result=parent.quality.result,
                confidence=parent.quality.confidence,
                evidence_count=parent.quality.evidence_count,
                contradiction_count=parent.quality.contradiction_count,
            ),
            parent_id=parent_id,
            mutations=list(mutations),
            variants=[],
            is_active=True,
        )
        self.save_template(variant)

        # Register the variant in the parent's variants list
        parent.variants.append(variant.id)
        self.save_template(parent)

        return variant

    # ------------------------------------------------------------------
    #  Queries
    # ------------------------------------------------------------------
    def count(self) -> int:
        """Return the number of active templates."""
        return len(self.list_templates())

    def count_all(self) -> int:
        """Return the total number of templates (including inactive)."""
        rows = self._backend.list_loop_templates()
        active_count = len(rows)
        # Also count inactive by querying directly
        conn = self._backend._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM loop_templates WHERE is_active = 0",
        ).fetchone()
        return active_count + row["cnt"]

    def get_variants(self, template_id: str) -> List[LoopTemplate]:
        """Get all variants of a template.

        Args:
            template_id: The parent template's ID.

        Returns:
            List of variant :class:`LoopTemplate` objects.
        """
        parent = self.get_template(template_id)
        if parent is None:
            return []
        variants: List[LoopTemplate] = []
        for vid in parent.variants:
            v = self.get_template(vid)
            if v is not None:
                variants.append(v)
        return variants

    def __repr__(self) -> str:
        return f"LoopTemplateStore(active={self.count()})"


# ═══════════════════════════════════════════════════════════════
#  DefaultTemplates — built-in Loop templates
# ═══════════════════════════════════════════════════════════════


class DefaultTemplates:
    """Factory for built-in Loop templates.

    Provides three canonical templates that cover the most common
    agent execution patterns:

    - **Standard ReAct** — perceive → plan → execute → (loop)
    - **Plan-Execute** — plan fully → execute steps → verify
    - **Reflective** — perceive → plan → execute → reflect → (loop)
    """

    @staticmethod
    def standard_react() -> LoopTemplate:
        """Create the standard ReAct loop template.

        The classic Reason-Act loop:
        1. Perceive — observe the current state.
        2. Plan — decide what to do next.
        3. Execute — call the chosen tool.
        4. Loop back to perceive until done.

        Returns:
            A :class:`LoopTemplate` for the standard ReAct pattern.
        """
        return LoopTemplate(
            id="default-react-001",
            task_signature=compute_task_signature("standard react loop task"),
            task_description="Standard ReAct loop: perceive, plan, execute, repeat.",
            phases=[
                LoopPhase(
                    name="perceive",
                    action="Observe current state and gather context.",
                    tools=[],
                    condition="always",
                ),
                LoopPhase(
                    name="plan",
                    action="Decide next action based on observations.",
                    tools=[],
                    condition="always",
                ),
                LoopPhase(
                    name="execute",
                    action="Execute the planned tool call.",
                    tools=[],
                    condition="always",
                ),
            ],
            tools=[],
            tool_order=[],
            reflection_points=[],
            max_iterations=10,
            termination_conditions=[
                "no_more_tool_calls",
                "budget_exhausted",
                "max_iterations_reached",
            ],
            quality=QualityScore(
                source=SourceQuality.B,
                result=ResultQuality.TRUSTED,
                confidence=0.7,
                evidence_count=2,
            ),
            is_active=True,
        )

    @staticmethod
    def plan_execute() -> LoopTemplate:
        """Create the plan-then-execute loop template.

        1. Perceive — observe state.
        2. Plan — create a full plan with all steps.
        3. Execute — execute each planned step in order.
        4. Verify — check that all steps completed successfully.

        Returns:
            A :class:`LoopTemplate` for the plan-execute pattern.
        """
        return LoopTemplate(
            id="default-plan-exec-001",
            task_signature=compute_task_signature("plan execute sequential task"),
            task_description="Plan-Execute: plan fully, then execute steps sequentially.",
            phases=[
                LoopPhase(
                    name="perceive",
                    action="Observe current state and identify all requirements.",
                    tools=[],
                    condition="always",
                ),
                LoopPhase(
                    name="plan",
                    action="Create a comprehensive plan with all steps.",
                    tools=[],
                    condition="always",
                ),
                LoopPhase(
                    name="execute",
                    action="Execute each planned step in order.",
                    tools=[],
                    condition="steps_remaining",
                ),
                LoopPhase(
                    name="verify",
                    action="Verify all steps completed successfully.",
                    tools=[],
                    condition="always",
                ),
            ],
            tools=[],
            tool_order=[],
            reflection_points=[],
            max_iterations=15,
            termination_conditions=[
                "all_steps_complete",
                "verification_passed",
                "budget_exhausted",
                "max_iterations_reached",
            ],
            quality=QualityScore(
                source=SourceQuality.B,
                result=ResultQuality.TRUSTED,
                confidence=0.65,
                evidence_count=1,
            ),
            is_active=True,
        )

    @staticmethod
    def reflective() -> LoopTemplate:
        """Create the reflective loop template.

        1. Perceive — observe state.
        2. Plan — decide next action.
        3. Execute — call the tool.
        4. Reflect — evaluate the result and adjust strategy.
        5. Loop back to perceive.

        Returns:
            A :class:`LoopTemplate` for the reflective pattern.
        """
        return LoopTemplate(
            id="default-reflective-001",
            task_signature=compute_task_signature("reflective loop self improving task"),
            task_description="Reflective loop: perceive, plan, execute, reflect, repeat.",
            phases=[
                LoopPhase(
                    name="perceive",
                    action="Observe current state and recent results.",
                    tools=[],
                    condition="always",
                ),
                LoopPhase(
                    name="plan",
                    action="Decide next action, considering past reflections.",
                    tools=[],
                    condition="always",
                ),
                LoopPhase(
                    name="execute",
                    action="Execute the planned tool call.",
                    tools=[],
                    condition="always",
                ),
                LoopPhase(
                    name="reflect",
                    action="Evaluate the result, identify improvements.",
                    tools=[],
                    condition="always",
                ),
            ],
            tools=[],
            tool_order=[],
            reflection_points=[2],  # reflect after the 3rd phase (0-indexed)
            max_iterations=12,
            termination_conditions=[
                "no_more_tool_calls",
                "reflection_converged",
                "budget_exhausted",
                "max_iterations_reached",
            ],
            quality=QualityScore(
                source=SourceQuality.B,
                result=ResultQuality.SPECULATIVE,
                confidence=0.6,
                evidence_count=1,
            ),
            is_active=True,
        )

    @staticmethod
    def all_defaults() -> List[LoopTemplate]:
        """Return all three default templates as a list.

        Returns:
            List of :class:`LoopTemplate` objects.
        """
        return [
            DefaultTemplates.standard_react(),
            DefaultTemplates.plan_execute(),
            DefaultTemplates.reflective(),
        ]
