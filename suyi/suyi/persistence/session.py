"""
Session persistence — JSON file-based session management.

Each session is stored as a single JSON file containing:
    - session_id:      Unique identifier.
    - history:         Full conversation history (list of message dicts).
    - memory_snapshot: Serialised memory state (working / semantic / episodic).
    - agent_state:     Agent lifecycle state and configuration summary.
    - created_at:      ISO-8601 timestamp.
    - updated_at:      ISO-8601 timestamp of last modification.
    - metadata:        Free-form dict for user / application data.

All file I/O is synchronous (JSON files are small); the AgentLoop itself
remains fully async.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional


def _iso_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class SessionData:
    """
    A serialisable session snapshot.

    Attributes:
        session_id:      Unique session identifier.
        history:         Conversation history (list of message dicts).
        memory_snapshot: Serialised memory state dict.
        agent_state:     Agent state dict (name, role, state, tools, etc.).
        created_at:      Creation timestamp (ISO-8601).
        updated_at:      Last update timestamp (ISO-8601).
        metadata:        Free-form application metadata.
    """

    session_id: str
    history: list[dict] = field(default_factory=list)
    memory_snapshot: dict = field(default_factory=dict)
    agent_state: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for JSON."""
        return {
            "session_id": self.session_id,
            "history": self.history,
            "memory_snapshot": self.memory_snapshot,
            "agent_state": self.agent_state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SessionData":
        """Deserialise from a plain dict."""
        return cls(
            session_id=d.get("session_id", ""),
            history=d.get("history", []),
            memory_snapshot=d.get("memory_snapshot", {}),
            agent_state=d.get("agent_state", {}),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            metadata=d.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return (
            f"SessionData(id={self.session_id!r}, "
            f"messages={len(self.history)}, "
            f"updated={self.updated_at})"
        )


class SessionManager:
    """
    File-based session manager.

    Stores each session as ``<storage_dir>/sessions/<session_id>.json``.

    Args:
        storage_dir: Root data directory.  Sessions are written to
            ``<storage_dir>/sessions/``.  Defaults to ``./data``.
    """

    def __init__(self, storage_dir: str = "./data") -> None:
        self.storage_dir = storage_dir
        self.sessions_dir = os.path.join(storage_dir, "sessions")
        os.makedirs(self.sessions_dir, exist_ok=True)

        # In-memory cache of active sessions (not yet saved to disk)
        self._active: dict[str, SessionData] = {}

    # ------------------------------------------------------------------
    #  Session lifecycle
    # ------------------------------------------------------------------

    def create_session(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """Create a new session and return its ID.

        Args:
            session_id: Optional explicit ID (auto-generated if omitted).
            metadata:   Optional initial metadata dict.

        Returns:
            The session ID.
        """
        if session_id is None:
            session_id = f"sess_{int(time.time())}_{os.urandom(4).hex()}"

        now = _iso_timestamp()
        data = SessionData(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self._active[session_id] = data
        return session_id

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        **extra: Any,
    ) -> None:
        """Append a message to a session's history (in memory).

        Args:
            session_id: Target session.
            role:       Message role (``user``, ``assistant``, ``tool`` …).
            content:    Message content.
            **extra:    Additional fields merged into the message dict.

        Raises:
            KeyError: If the session does not exist.
        """
        data = self._get_or_raise(session_id)
        msg: dict[str, Any] = {"role": role, "content": content}
        msg.update(extra)
        data.history.append(msg)
        data.updated_at = _iso_timestamp()

    def set_memory_snapshot(self, session_id: str, snapshot: dict) -> None:
        """Store a memory system snapshot for the session."""
        data = self._get_or_raise(session_id)
        data.memory_snapshot = snapshot
        data.updated_at = _iso_timestamp()

    def set_agent_state(self, session_id: str, state: dict) -> None:
        """Store agent state (name, role, lifecycle state, tools, …)."""
        data = self._get_or_raise(session_id)
        data.agent_state = state
        data.updated_at = _iso_timestamp()

    def update_metadata(self, session_id: str, metadata: dict) -> None:
        """Merge *metadata* into the session's metadata dict."""
        data = self._get_or_raise(session_id)
        data.metadata.update(metadata)
        data.updated_at = _iso_timestamp()

    # ------------------------------------------------------------------
    #  Persistence (disk I/O)
    # ------------------------------------------------------------------

    def save_session(self, session_id: str) -> str:
        """Write the session to a JSON file.

        Returns:
            The file path that was written.

        Raises:
            KeyError: If the session does not exist.
        """
        data = self._get_or_raise(session_id)
        data.updated_at = _iso_timestamp()
        path = self._session_path(session_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def load_session(self, session_id: str) -> SessionData:
        """Load a session from disk and cache it in memory.

        Args:
            session_id: The session to load.

        Returns:
            The restored :class:`SessionData`.

        Raises:
            FileNotFoundError: If no saved file exists for the session.
        """
        path = self._session_path(session_id)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Session file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        data = SessionData.from_dict(d)
        self._active[session_id] = data
        return data

    def delete_session(self, session_id: str) -> bool:
        """Delete a session from disk and memory.

        Returns:
            ``True`` if a file was deleted, ``False`` otherwise.
        """
        self._active.pop(session_id, None)
        path = self._session_path(session_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    # ------------------------------------------------------------------
    #  Listing & export
    # ------------------------------------------------------------------

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all saved sessions on disk.

        Returns:
            A list of summary dicts (``session_id``, ``created_at``,
            ``updated_at``, ``message_count``, ``metadata``),
            sorted by ``updated_at`` descending.
        """
        results: list[dict[str, Any]] = []
        if not os.path.isdir(self.sessions_dir):
            return results

        for fname in os.listdir(self.sessions_dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self.sessions_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                results.append({
                    "session_id": d.get("session_id", fname[:-5]),
                    "created_at": d.get("created_at", ""),
                    "updated_at": d.get("updated_at", ""),
                    "message_count": len(d.get("history", [])),
                    "metadata": d.get("metadata", {}),
                })
            except (json.JSONDecodeError, OSError):
                continue

        results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return results

    def export_session(self, session_id: str, export_path: Optional[str] = None) -> str:
        """Export a session to a JSON file.

        If *export_path* is ``None``, writes to
        ``<sessions_dir>/<session_id>_export.json``.

        Returns:
            The path written.
        """
        data = self._get_or_raise(session_id)
        if export_path is None:
            export_path = os.path.join(
                self.sessions_dir, f"{session_id}_export.json"
            )
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)
        return export_path

    # ------------------------------------------------------------------
    #  Convenience accessors
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Return the in-memory session data, or ``None`` if not loaded."""
        return self._active.get(session_id)

    def get_history(self, session_id: str) -> list[dict]:
        """Return the conversation history for a session."""
        data = self._get_or_raise(session_id)
        return data.history

    def session_exists(self, session_id: str) -> bool:
        """Check whether a session exists (in memory or on disk)."""
        if session_id in self._active:
            return True
        return os.path.exists(self._session_path(session_id))

    # ------------------------------------------------------------------
    #  Internals
    # ------------------------------------------------------------------

    def _session_path(self, session_id: str) -> str:
        """Return the on-disk path for a session ID."""
        return os.path.join(self.sessions_dir, f"{session_id}.json")

    def _get_or_raise(self, session_id: str) -> SessionData:
        """Get session from cache, or raise KeyError."""
        data = self._active.get(session_id)
        if data is None:
            raise KeyError(f"Session '{session_id}' not found. "
                           f"Call create_session() or load_session() first.")
        return data

    def __repr__(self) -> str:
        return (
            f"SessionManager(sessions_dir={self.sessions_dir!r}, "
            f"active={len(self._active)})"
        )
