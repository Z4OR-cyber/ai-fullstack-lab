"""
Suyi Persistence — Session persistence via JSON files.

Exports:
    SessionManager:  Create, save, load, list, delete, and export sessions.
    SessionData:     Dataclass representing a serializable session snapshot.

Design:
    - JSON file storage — no database dependency.
    - Each session saves: conversation history, memory snapshot,
      agent state, timestamps, and metadata.
    - Sessions are stored under ``<storage_dir>/sessions/``.
    - ``load_session`` restores full conversation state so an agent
      can resume from a previous interaction.

Usage::

    from suyi.persistence import SessionManager

    mgr = SessionManager(storage_dir="./data")
    session_id = mgr.create_session()
    mgr.add_message(session_id, "user", "Hello!")
    mgr.add_message(session_id, "assistant", "Hi there!")
    mgr.save_session(session_id)

    # Later — restore
    data = mgr.load_session(session_id)
    print(data.history)  # Full conversation restored
"""

from .session import SessionManager, SessionData

__all__ = [
    "SessionManager",
    "SessionData",
]
