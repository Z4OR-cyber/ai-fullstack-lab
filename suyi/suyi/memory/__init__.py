"""Memory System — three-layer memory with lifecycle management.

Exports :class:`MemoryManager` which provides a unified API over three
memory layers:

- **Working Memory** (:class:`~.working.WorkingMemory`) — current
  conversation context, dynamically assembled each turn.
- **Episodic Memory** (:class:`~.episodic.EpisodicMemory`) — session
  logs with age-based graded compression.
- **Semantic Memory** (:class:`~.semantic.SemanticMemory`) — cross-session
  knowledge base with TF-IDF retrieval.

The :class:`~.lifecycle.MemoryLifecycle` drives a four-stage forgetting
process (fresh → consolidation → compression → forgetting) that
automatically promotes high-confidence memories and evicts stale ones.

Quick start
-----------

::

    from suyi.memory import MemoryManager

    mgr = MemoryManager()
    mgr.add_memory("Python GIL prevents true multithreading", tags=["python"])
    results = mgr.retrieve_relevant("Python threading")
    mgr.consolidate()
    mgr.cleanup()
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from .working import WorkingMemory, BudgetStatus
from .episodic import EpisodicMemory, Episode
from .semantic import SemanticMemory, MemoryEntry
from .lifecycle import MemoryLifecycle


class MemoryManager:
    """Unified manager for the three-layer memory system.

    Coordinates working, episodic, and semantic memory, and runs the
    lifecycle engine to consolidate / compress / forget entries.

    Attributes:
        working: The :class:`WorkingMemory` instance.
        episodic: The :class:`EpisodicMemory` instance.
        semantic: The :class:`SemanticMemory` instance.
        lifecycle: The :class:`MemoryLifecycle` instance.
        storage_dir: Directory used for JSON persistence.
    """

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        token_budget: int = 8192,
        system_prompt: str = "",
    ) -> None:
        """Initialise the memory system.

        Args:
            storage_dir: Directory for JSON persistence files.  If
                ``None``, defaults to ``.evoagent_memory`` in the
                current working directory.  If the directory cannot be
                created, falls back to in-memory mode (no persistence).
            token_budget: Token budget for working memory.
            system_prompt: Initial system prompt for working memory.
        """
        # Resolve storage directory
        if storage_dir is None:
            storage_dir = os.path.join(os.getcwd(), '.evoagent_memory')

        self.storage_dir = storage_dir
        try:
            os.makedirs(storage_dir, exist_ok=True)
            self._persist = True
        except OSError:
            # Fallback: in-memory only
            self._persist = False
            storage_dir = None

        # Build file paths
        episodic_path = None
        semantic_path = None
        if self._persist and storage_dir:
            episodic_path = os.path.join(storage_dir, 'episodic.json')
            semantic_path = os.path.join(storage_dir, 'semantic.json')

        # Create the three layers
        self.working = WorkingMemory(
            token_budget=token_budget,
            system_prompt=system_prompt,
        )
        self.episodic = EpisodicMemory(
            storage_path=episodic_path,
        )
        self.semantic = SemanticMemory(
            storage_path=semantic_path,
        )
        self.lifecycle = MemoryLifecycle()

    # ------------------------------------------------------------------
    #  Working memory passthrough
    # ------------------------------------------------------------------
    def add_message(
        self,
        role: str,
        content: str,
        **metadata: Any,
    ) -> None:
        """Add a message to the current working-memory session."""
        self.working.add_message(role, content, **metadata)

    def build_context(self) -> Dict[str, Any]:
        """Build the conversation context (delegates to WorkingMemory).

        Returns:
            Dict with ``system_prompt``, ``messages``, ``budget_status``.
        """
        return self.working.build_context()

    # ------------------------------------------------------------------
    #  Unified add_memory
    # ------------------------------------------------------------------
    def add_memory(
        self,
        content: str,
        layer: str = 'auto',
        tags: Optional[List[str]] = None,
        confidence: float = 0.5,
        role: str = 'user',
        source: str = 'manual',
        **kwargs: Any,
    ) -> Any:
        """Add a memory entry to the appropriate layer.

        When ``layer='auto'`` (default), the method decides based on
        context:

        - If called within an active session (working memory has
          messages), adds to **working** memory as a message.
        - Otherwise, adds to **semantic** memory as a knowledge entry.

        Explicit layer values: ``'working'``, ``'episodic'``,
        ``'semantic'``.

        Args:
            content: The content to store.
            layer: Target layer or ``'auto'``.
            tags: Optional tags (semantic memory only).
            confidence: Initial confidence (semantic memory only).
            role: Message role (working / episodic only).
            source: Origin label (semantic memory only).
            **kwargs: Additional fields passed through.

        Returns:
            The created object (message dict, :class:`Episode`, or
            :class:`MemoryEntry`).
        """
        if layer == 'auto':
            # Heuristic: if working memory is active, treat as a message;
            # otherwise store as semantic knowledge.
            if self.working.get_turn_count() > 0:
                layer = 'working'
            else:
                layer = 'semantic'

        if layer == 'working':
            self.working.add_message(role, content, **kwargs)
            return {'role': role, 'content': content, **kwargs}

        if layer == 'episodic':
            return self.episodic.log_turn(
                role=role,
                content=content,
                tags=tags,
                **kwargs,
            )

        if layer == 'semantic':
            return self.semantic.add(
                content=content,
                tags=tags,
                confidence=confidence,
                source=source,
                **kwargs,
            )

        raise ValueError(f"Unknown layer: {layer!r}")

    # ------------------------------------------------------------------
    #  Unified retrieve_relevant
    # ------------------------------------------------------------------
    def retrieve_relevant(
        self,
        query: str,
        top_k: int = 5,
        include_episodic: bool = True,
        include_semantic: bool = True,
        tag_filter: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant memories across episodic and semantic layers.

        Searches both layers, merges results, and ranks by combined
        relevance.  Retrieved semantic entries are also injected into
        working memory for the next :meth:`build_context` call.

        Args:
            query: Natural-language query.
            top_k: Maximum results per layer.
            include_episodic: Search episodic memory.
            include_semantic: Search semantic memory.
            tag_filter: Optional tag filter (semantic only).

        Returns:
            Merged list of memory dicts, each with a ``layer`` field
            and a ``score`` field, sorted by score descending.
        """
        results: List[Dict[str, Any]] = []

        if include_semantic:
            semantic_results = self.semantic.retrieve(
                query=query,
                top_k=top_k,
                tag_filter=tag_filter,
            )
            for r in semantic_results:
                r['layer'] = 'semantic'
                results.append(r)

        if include_episodic:
            episodic_results = self.episodic.search(query=query, top_k=top_k)
            for r in episodic_results:
                r['layer'] = 'episodic'
                r.setdefault('score', r.get('importance', 0.5))
                results.append(r)

        # Sort by score descending
        results.sort(key=lambda x: x.get('score', 0.0), reverse=True)

        # Inject top results into working memory
        if results:
            self.working.inject_memories(results[:top_k])

        return results[:top_k]

    # ------------------------------------------------------------------
    #  Consolidation
    # ------------------------------------------------------------------
    def consolidate(self) -> Dict[str, Any]:
        """Run the memory consolidation process.

        This performs three operations:

        1. **Promote**: high-confidence episodic memories are extracted
           and added to semantic memory.
        2. **Consolidate**: high-confidence semantic entries are marked
           as ``source='consolidated'``.
        3. **Update**: confidence values are recomputed for all semantic
           entries based on the lifecycle model.

        Returns:
            A summary dict with counts of promoted / consolidated /
            updated entries.
        """
        report: Dict[str, Any] = {
            'promoted': 0,
            'consolidated': 0,
            'updated': 0,
            'timestamp': time.time(),
        }

        # --- 1. Promote high-importance episodic entries to semantic ---
        # Find episodes with high importance that haven't been promoted yet
        promoted_ids: set = {
            e.source.replace('episodic:', '')
            for e in self.semantic.entries
            if e.source.startswith('episodic:')
        }

        for ep in self.episodic.episodes:
            if ep.id in promoted_ids:
                continue
            # Use importance as base confidence
            conf = self.lifecycle.compute_confidence(
                base_score=ep.importance,
                success_count=0,
                fail_count=0,
                days_since_access=(time.time() - ep.timestamp) / 86400.0,
            )
            if conf > self.lifecycle.consolidate_threshold:
                self.semantic.add(
                    content=ep.content,
                    tags=ep.tags,
                    confidence=conf,
                    source=f'episodic:{ep.id}',
                )
                report['promoted'] += 1

        # --- 2. Consolidate high-confidence semantic entries ---
        semantic_dicts = [e.to_dict() for e in self.semantic.entries]
        consolidation_candidates = self.lifecycle.get_consolidation_candidates(
            semantic_dicts
        )
        for candidate in consolidation_candidates:
            entry = self.semantic.get_by_id(candidate['id'])
            if entry and entry.source != 'consolidated':
                entry.source = 'consolidated'
                report['consolidated'] += 1

        # --- 3. Update confidence values ---
        for entry in self.semantic.entries:
            new_conf = self.lifecycle.compute_confidence_for_entry(
                entry.to_dict()
            )
            entry.confidence = new_conf
            report['updated'] += 1

        # Persist
        self.semantic.save()
        self.episodic.save()

        return report

    # ------------------------------------------------------------------
    #  Cleanup
    # ------------------------------------------------------------------
    def cleanup(self) -> Dict[str, Any]:
        """Run the memory cleanup / forgetting process.

        Performs:

        1. **Compress**: low-confidence semantic entries that haven't
           been accessed in ``half_life`` days are replaced with short
           summaries.
        2. **Forget**: entries below the forget threshold that haven't
           been accessed in ``2 × half_life`` days are deleted.
        3. **Evict**: episodic memory is trimmed to capacity.

        Returns:
            A summary dict with counts of compressed / forgotten /
           evicted entries.
        """
        report: Dict[str, Any] = {
            'compressed': 0,
            'forgotten': 0,
            'evicted': 0,
            'timestamp': time.time(),
        }

        semantic_dicts = [e.to_dict() for e in self.semantic.entries]

        # --- 1. Compression candidates ---
        compression_candidates = self.lifecycle.get_compression_candidates(
            semantic_dicts
        )
        for candidate in compression_candidates:
            entry = self.semantic.get_by_id(candidate['id'])
            if entry:
                # Replace content with summary
                entry.content = self.lifecycle.summarize_entry(entry.to_dict())
                entry.tags = entry.tags + ['_compressed']
                report['compressed'] += 1

        # --- 2. Forgetting candidates ---
        forgetting_candidates = self.lifecycle.get_forgetting_candidates(
            semantic_dicts
        )
        for candidate in forgetting_candidates:
            if self.semantic.delete(candidate['id']):
                report['forgotten'] += 1

        # --- 3. Episodic eviction ---
        before_episodic = len(self.episodic.episodes)
        self.episodic._evict()
        report['evicted'] = before_episodic - len(self.episodic.episodes)

        # Persist
        self.semantic.save()
        self.episodic.save()

        return report

    # ------------------------------------------------------------------
    #  Session lifecycle
    # ------------------------------------------------------------------
    def start_session(self, session_id: Optional[str] = None) -> str:
        """Start a new conversation session.

        - Begins a new episodic session.
        - Clears working memory.
        - Optionally loads a summary of the previous session.

        Args:
            session_id: Optional explicit session ID.

        Returns:
            The session ID.
        """
        self.working.clear()
        return self.episodic.start_session(session_id)

    def end_session(self) -> None:
        """End the current session.

        - Logs all working-memory messages to episodic memory.
        - Runs consolidation.
        - Persists to disk.
        """
        messages = self.working.export_session()
        if messages:
            self.episodic.log_session(messages)
        self.episodic.end_session()

    # ------------------------------------------------------------------
    #  Status / reporting
    # ------------------------------------------------------------------
    def get_status(self) -> Dict[str, Any]:
        """Return a snapshot of the memory system's state.

        Returns:
            A dict with counts and budget info for each layer.
        """
        context = self.working.build_context()
        budget = context['budget_status']

        semantic_dicts = [e.to_dict() for e in self.semantic.entries]
        lifecycle_report = self.lifecycle.lifecycle_report(semantic_dicts)

        return {
            'working': {
                'messages': len(self.working.messages),
                'turn_count': self.working.get_turn_count(),
                'budget': budget.to_dict(),
            },
            'episodic': {
                'episodes': len(self.episodic),
                'sessions': len(self.episodic.get_session_ids()),
            },
            'semantic': {
                'entries': len(self.semantic),
                'vocabulary': len(self.semantic.tfidf.vocabulary),
            },
            'lifecycle': lifecycle_report,
            'storage_dir': self.storage_dir,
            'persistence': self._persist,
        }

    def __repr__(self) -> str:
        return (
            f"MemoryManager("
            f"working={self.working!r}, "
            f"episodic={self.episodic!r}, "
            f"semantic={self.semantic!r})"
        )


# ----------------------------------------------------------------------
#  Public exports
# ----------------------------------------------------------------------
__all__ = [
    'MemoryManager',
    'WorkingMemory',
    'BudgetStatus',
    'EpisodicMemory',
    'Episode',
    'SemanticMemory',
    'MemoryEntry',
    'MemoryLifecycle',
]
