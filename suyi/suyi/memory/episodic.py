"""Episodic Memory — session log storage with age-based compression.

Episodic memory records individual conversation *turns* (episodes) across
sessions and applies **graded compression** based on message age (measured
in turns, not wall-clock time).  An importance score is computed for each
episode and used to evict low-value entries when storage grows too large.

Compression tiers
-----------------

==============  ===========  ====================================
Age (turns)     Tier         Action
==============  ===========  ====================================
``age ≤ 5``     **retain**   Keep original content verbatim.
``age ≤ 15``    **trim**     Drop tool *output*, keep tool *name*.
``age ≤ 30``    **summary**  Replace with a short extractive summary.
``age > 30``    **skip**     Omit entirely (as if forgotten).
==============  ===========  ====================================

Importance scoring
------------------

Each episode receives an importance score in [0, 1] based on:

- Role (user messages rank higher than tool output)
- Presence of tool calls (indicates active problem-solving)
- Content length (longer = more information, capped)
- Explicit tags or flags
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ..utils.token_counter import estimate_tokens


class Episode:
    """A single conversation turn stored in episodic memory.

    Attributes:
        id: Unique identifier.
        session_id: Identifier of the session this episode belongs to.
        turn_number: Turn index within the session (0-based).
        role: ``'user'``, ``'assistant'``, ``'tool'``, or ``'system'``.
        content: The message text.
        tool_calls: Optional list of tool-call dicts.
        tool_results: Optional list of tool-result dicts.
        timestamp: Unix timestamp of creation.
        importance: Importance score in [0, 1].
        tags: Optional list of string tags.
    """

    def __init__(
        self,
        role: str,
        content: str,
        session_id: str = "",
        turn_number: int = 0,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        timestamp: Optional[float] = None,
        importance: Optional[float] = None,
        tags: Optional[List[str]] = None,
        episode_id: Optional[str] = None,
    ) -> None:
        self.id: str = episode_id or str(uuid.uuid4())
        self.session_id: str = session_id
        self.turn_number: int = turn_number
        self.role: str = role
        self.content: str = content
        self.tool_calls: List[Dict[str, Any]] = tool_calls or []
        self.tool_results: List[Dict[str, Any]] = tool_results or []
        self.timestamp: float = timestamp or time.time()
        self.importance: float = (
            importance if importance is not None
            else _compute_importance(role, content, tool_calls)
        )
        self.tags: List[str] = tags or []

    # ------------------------------------------------------------------
    #  Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serialisable dict."""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'turn_number': self.turn_number,
            'role': self.role,
            'content': self.content,
            'tool_calls': self.tool_calls,
            'tool_results': self.tool_results,
            'timestamp': self.timestamp,
            'importance': self.importance,
            'tags': self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Episode":
        """Reconstruct an Episode from a dict."""
        return cls(
            role=data['role'],
            content=data['content'],
            session_id=data.get('session_id', ''),
            turn_number=data.get('turn_number', 0),
            tool_calls=data.get('tool_calls'),
            tool_results=data.get('tool_results'),
            timestamp=data.get('timestamp'),
            importance=data.get('importance'),
            tags=data.get('tags'),
            episode_id=data.get('id'),
        )

    def __repr__(self) -> str:
        return (
            f"Episode(id={self.id[:8]}, role={self.role!r}, "
            f"turn={self.turn_number}, importance={self.importance:.2f})"
        )


# ----------------------------------------------------------------------
#  Importance scoring
# ----------------------------------------------------------------------
def _compute_importance(
    role: str,
    content: str,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
) -> float:
    """Compute an importance score for an episode.

    Factors:
    - Base score: 0.3
    - User role: +0.2  (user intent is always important)
    - Assistant role: +0.1
    - Has tool calls: +0.15  (active problem-solving)
    - Content length: +min(len / 1000, 0.25)  (capped)

    Returns:
        Importance score clamped to [0, 1].
    """
    score = 0.3

    if role == 'user':
        score += 0.2
    elif role == 'assistant':
        score += 0.1

    if tool_calls:
        score += 0.15

    score += min(len(content) / 1000.0, 0.25)

    return min(max(score, 0.0), 1.0)


# ----------------------------------------------------------------------
#  Compression helpers
# ----------------------------------------------------------------------
def _compress_episode(ep: Episode, age: int) -> Optional[Dict[str, Any]]:
    """Apply age-based compression to a single episode.

    Args:
        ep: The episode to compress.
        age: Age in turns (number of turns since this episode).

    Returns:
        A compressed dict, or ``None`` if the episode should be skipped
        (age > 30).
    """
    if age <= 5:
        # Tier 1: retain verbatim
        return ep.to_dict()

    if age <= 15:
        # Tier 2: drop tool output, keep tool names
        compressed = ep.to_dict()
        if compressed.get('tool_results'):
            compressed['tool_results'] = [
                {'name': tr.get('name', '?'), '_output_dropped': True}
                for tr in compressed['tool_results']
            ]
        # Also trim very long content
        if len(compressed['content']) > 500:
            compressed['content'] = compressed['content'][:500] + '...'
        return compressed

    if age <= 30:
        # Tier 3: extractive summary
        summary = _summarize_content(ep.content)
        return {
            'id': ep.id,
            'session_id': ep.session_id,
            'turn_number': ep.turn_number,
            'role': ep.role,
            'content': f"[summary] {summary}",
            'tool_calls': [],
            'tool_results': [],
            'timestamp': ep.timestamp,
            'importance': ep.importance,
            'tags': ep.tags,
            '_compressed': True,
        }

    # Tier 4: skip entirely
    return None


def _summarize_content(text: str, max_sentences: int = 2) -> str:
    """Produce a simple extractive summary of *text*.

    Picks the first *max_sentences* sentences.  If the text is very
    short, returns it truncated.
    """
    if not text:
        return ""

    # Split on sentence-ending punctuation (handles both English and CJK)
    import re
    sentences = re.split(r'[.!?。！？\n]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return text[:200]

    picked = sentences[:max_sentences]
    summary = '. '.join(picked)
    if len(summary) > 300:
        summary = summary[:300] + '...'
    return summary


# ----------------------------------------------------------------------
#  EpisodicMemory
# ----------------------------------------------------------------------
class EpisodicMemory:
    """Episodic Memory — stores and compresses conversation session logs.

    Provides:
    - **Logging**: record individual turns as :class:`Episode` objects.
    - **Graded retrieval**: get compressed context for a given current
      turn, applying the four-tier age-based compression.
    - **Importance-based eviction**: when the store exceeds a maximum
      size, low-importance episodes are evicted first.
    - **Keyword search**: simple substring matching for quick lookups.
    - **JSON persistence**: all episodes are saved to a JSON file.

    Attributes:
        storage_path: Path to the JSON file used for persistence.
        max_episodes: Maximum number of episodes to retain.
        episodes: List of stored :class:`Episode` objects.
    """

    def __init__(
        self,
        storage_path: Optional[str] = None,
        max_episodes: int = 500,
    ) -> None:
        self.storage_path = storage_path
        self.max_episodes = max_episodes
        self.episodes: List[Episode] = []
        self._current_session_id: str = ""
        self._current_turn: int = 0

        if storage_path:
            self._load()

    # ------------------------------------------------------------------
    #  Session management
    # ------------------------------------------------------------------
    def start_session(self, session_id: Optional[str] = None) -> str:
        """Begin a new session, resetting the turn counter.

        Args:
            session_id: Optional explicit session ID.  Auto-generated if
                omitted.

        Returns:
            The session ID.
        """
        self._current_session_id = session_id or str(uuid.uuid4())
        self._current_turn = 0
        return self._current_session_id

    def end_session(self) -> None:
        """End the current session and persist to disk."""
        if self.storage_path:
            self._save()

    # ------------------------------------------------------------------
    #  Logging
    # ------------------------------------------------------------------
    def log_turn(
        self,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ) -> Episode:
        """Record a single conversation turn.

        Args:
            role: Message role.
            content: Message text.
            tool_calls: Optional tool-call metadata.
            tool_results: Optional tool-result data.
            tags: Optional tags for categorisation.
            session_id: Override the current session ID.

        Returns:
            The created :class:`Episode`.
        """
        sid = session_id or self._current_session_id or self.start_session()

        ep = Episode(
            role=role,
            content=content,
            session_id=sid,
            turn_number=self._current_turn,
            tool_calls=tool_calls,
            tool_results=tool_results,
            tags=tags,
        )
        self.episodes.append(ep)
        self._current_turn += 1

        # Evict if over capacity
        if len(self.episodes) > self.max_episodes:
            self._evict()

        return ep

    def log_session(self, messages: List[Dict[str, Any]]) -> None:
        """Log an entire session's worth of messages at once.

        Args:
            messages: List of message dicts (as exported by
                :meth:`WorkingMemory.export_session`).
        """
        sid = self.start_session()
        for msg in messages:
            self.log_turn(
                role=msg.get('role', 'unknown'),
                content=msg.get('content', ''),
                tool_calls=msg.get('tool_calls'),
                tool_results=msg.get('tool_results'),
                tags=msg.get('tags'),
                session_id=sid,
            )
        self.end_session()

    # ------------------------------------------------------------------
    #  Graded retrieval
    # ------------------------------------------------------------------
    def get_compressed_context(
        self,
        current_turn: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve episodes with age-based compression applied.

        Args:
            current_turn: The current turn number.  If ``None``, uses
                the most recent turn across all episodes.
            session_id: If provided, only retrieve episodes from this
                session.  Otherwise retrieves from all sessions.

        Returns:
            List of compressed episode dicts.  Episodes with age > 30
            are omitted entirely.
        """
        if current_turn is None:
            current_turn = max(
                (ep.turn_number for ep in self.episodes),
                default=0,
            )

        result: List[Dict[str, Any]] = []
        for ep in self.episodes:
            if session_id and ep.session_id != session_id:
                continue

            age = current_turn - ep.turn_number
            if age < 0:
                age = 0

            compressed = _compress_episode(ep, age)
            if compressed is not None:
                result.append(compressed)

        return result

    def get_session_summary(self, session_id: str) -> str:
        """Produce a text summary of an entire session.

        Uses the compression tier for age=30 (extractive summary) on
        every episode in the session, then concatenates.

        Args:
            session_id: The session to summarise.

        Returns:
            A multi-line summary string.
        """
        parts: List[str] = []
        for ep in self.episodes:
            if ep.session_id != session_id:
                continue
            summary = _summarize_content(ep.content)
            tool_info = ""
            if ep.tool_calls:
                names = [
                    tc.get('name') or tc.get('function', {}).get('name', '?')
                    for tc in ep.tool_calls
                ]
                tool_info = f" [tools: {', '.join(names)}]"
            parts.append(f"[{ep.role}{tool_info}] {summary}")

        return "\n".join(parts) if parts else ""

    # ------------------------------------------------------------------
    #  Keyword search
    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        top_k: int = 5,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Simple keyword search over episode contents.

        Ranks by the number of query terms found in the content.

        Args:
            query: Search query string.
            top_k: Maximum number of results.
            session_id: Optional session filter.

        Returns:
            List of matching episode dicts, ranked by relevance.
        """
        query_terms = [t.lower() for t in query.split() if t.strip()]
        if not query_terms:
            return []

        scored: List[Tuple[float, Episode]] = []
        for ep in self.episodes:
            if session_id and ep.session_id != session_id:
                continue
            content_lower = ep.content.lower()
            score = sum(1 for term in query_terms if term in content_lower)
            if score > 0:
                # Blend keyword score with importance
                final = score * 0.7 + ep.importance * 0.3
                scored.append((final, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep.to_dict() for _, ep in scored[:top_k]]

    # ------------------------------------------------------------------
    #  Eviction
    # ------------------------------------------------------------------
    def _evict(self) -> None:
        """Remove lowest-importance episodes until under capacity."""
        excess = len(self.episodes) - self.max_episodes
        if excess <= 0:
            return

        # Sort by importance ascending, evict the lowest
        self.episodes.sort(key=lambda ep: ep.importance)
        self.episodes = self.episodes[excess:]

    # ------------------------------------------------------------------
    #  Persistence
    # ------------------------------------------------------------------
    def _save(self) -> None:
        """Persist all episodes to the JSON storage file."""
        if not self.storage_path:
            return
        os.makedirs(os.path.dirname(self.storage_path) or '.', exist_ok=True)
        data = {
            'episodes': [ep.to_dict() for ep in self.episodes],
            'current_session_id': self._current_session_id,
            'current_turn': self._current_turn,
        }
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        """Load episodes from the JSON storage file."""
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.episodes = [
                Episode.from_dict(d) for d in data.get('episodes', [])
            ]
            self._current_session_id = data.get('current_session_id', '')
            self._current_turn = data.get('current_turn', 0)
        except (json.JSONDecodeError, KeyError):
            # Corrupt file — start fresh
            self.episodes = []

    def save(self) -> None:
        """Public save method (alias for internal ``_save``)."""
        self._save()

    # ------------------------------------------------------------------
    #  Utilities
    # ------------------------------------------------------------------
    def get_all_episodes(self) -> List[Episode]:
        """Return a copy of all stored episodes."""
        return list(self.episodes)

    def get_episodes_by_session(self, session_id: str) -> List[Episode]:
        """Return all episodes belonging to *session_id*."""
        return [ep for ep in self.episodes if ep.session_id == session_id]

    def get_session_ids(self) -> List[str]:
        """Return a list of unique session IDs."""
        seen: List[str] = []
        for ep in self.episodes:
            if ep.session_id and ep.session_id not in seen:
                seen.append(ep.session_id)
        return seen

    def __len__(self) -> int:
        return len(self.episodes)

    def __repr__(self) -> str:
        sessions = len(self.get_session_ids())
        return (
            f"EpisodicMemory(episodes={len(self.episodes)}, "
            f"sessions={sessions})"
        )
