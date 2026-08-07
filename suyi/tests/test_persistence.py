"""
Tests for Suyi Persistence — Session management via JSON files.

Covers:
    - Session creation and ID generation
    - Adding messages, memory snapshots, agent state
    - Save / load round-trip
    - Session listing and deletion
    - Export functionality
    - Error handling (missing sessions, missing files)
    - SessionData serialisation / deserialisation
"""

import json
import os
import tempfile

import pytest

from suyi.persistence import SessionManager, SessionData


# ═══════════════════════════════════════════════════════════════
#  SessionData tests
# ═══════════════════════════════════════════════════════════════


class TestSessionData:
    """Test the SessionData dataclass."""

    def test_defaults(self):
        data = SessionData(session_id="s1")
        assert data.session_id == "s1"
        assert data.history == []
        assert data.memory_snapshot == {}
        assert data.agent_state == {}
        assert data.created_at == ""
        assert data.updated_at == ""
        assert data.metadata == {}

    def test_to_dict(self):
        data = SessionData(
            session_id="s1",
            history=[{"role": "user", "content": "hi"}],
            memory_snapshot={"key": "value"},
            agent_state={"name": "suyi"},
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-02T00:00:00Z",
            metadata={"topic": "test"},
        )
        d = data.to_dict()
        assert d["session_id"] == "s1"
        assert d["history"] == [{"role": "user", "content": "hi"}]
        assert d["memory_snapshot"] == {"key": "value"}
        assert d["agent_state"] == {"name": "suyi"}
        assert d["created_at"] == "2025-01-01T00:00:00Z"
        assert d["updated_at"] == "2025-01-02T00:00:00Z"
        assert d["metadata"] == {"topic": "test"}

    def test_from_dict(self):
        d = {
            "session_id": "s2",
            "history": [{"role": "assistant", "content": "hello"}],
            "memory_snapshot": {"entries": 5},
            "agent_state": {"state": "idle"},
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
            "metadata": {"user": "alice"},
        }
        data = SessionData.from_dict(d)
        assert data.session_id == "s2"
        assert data.history == [{"role": "assistant", "content": "hello"}]
        assert data.memory_snapshot == {"entries": 5}
        assert data.agent_state == {"state": "idle"}
        assert data.metadata == {"user": "alice"}

    def test_round_trip(self):
        original = SessionData(
            session_id="rt",
            history=[{"role": "user", "content": "test"}],
            memory_snapshot={"a": 1},
            agent_state={"b": 2},
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-02T00:00:00Z",
            metadata={"c": 3},
        )
        d = original.to_dict()
        restored = SessionData.from_dict(d)
        assert restored.session_id == original.session_id
        assert restored.history == original.history
        assert restored.memory_snapshot == original.memory_snapshot
        assert restored.agent_state == original.agent_state
        assert restored.metadata == original.metadata

    def test_from_dict_missing_fields(self):
        """from_dict should handle missing fields gracefully."""
        data = SessionData.from_dict({"session_id": "s3"})
        assert data.session_id == "s3"
        assert data.history == []
        assert data.memory_snapshot == {}

    def test_repr(self):
        data = SessionData(session_id="repr_test", history=[{}, {}])
        r = repr(data)
        assert "repr_test" in r
        assert "messages=2" in r


# ═══════════════════════════════════════════════════════════════
#  SessionManager tests
# ═══════════════════════════════════════════════════════════════


class TestSessionManagerCreate:
    """Test session creation."""

    def test_create_session_auto_id(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session()
        assert sid.startswith("sess_")
        assert mgr.get_session(sid) is not None

    def test_create_session_explicit_id(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session(session_id="my-session")
        assert sid == "my-session"
        data = mgr.get_session(sid)
        assert data is not None
        assert data.session_id == "my-session"

    def test_create_session_with_metadata(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session(metadata={"topic": "math"})
        data = mgr.get_session(sid)
        assert data.metadata == {"topic": "math"}

    def test_create_session_has_timestamps(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session()
        data = mgr.get_session(sid)
        assert data.created_at != ""
        assert data.updated_at != ""

    def test_sessions_dir_created(self, tmp_path):
        storage = str(tmp_path / "deep" / "nested")
        mgr = SessionManager(storage_dir=storage)
        assert os.path.isdir(os.path.join(storage, "sessions"))


class TestSessionManagerMessages:
    """Test message operations."""

    def test_add_message(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session()
        mgr.add_message(sid, "user", "Hello")
        mgr.add_message(sid, "assistant", "Hi there!")
        history = mgr.get_history(sid)
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Hello"}
        assert history[1] == {"role": "assistant", "content": "Hi there!"}

    def test_add_message_with_extra(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session()
        mgr.add_message(sid, "tool", "result", tool_call_id="call_1")
        history = mgr.get_history(sid)
        assert history[0]["tool_call_id"] == "call_1"

    def test_add_message_updates_timestamp(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session()
        data = mgr.get_session(sid)
        original_ts = data.updated_at
        mgr.add_message(sid, "user", "msg")
        assert data.updated_at >= original_ts

    def test_add_message_missing_session(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        with pytest.raises(KeyError):
            mgr.add_message("nonexistent", "user", "hello")


class TestSessionManagerSnapshots:
    """Test memory snapshot and agent state."""

    def test_set_memory_snapshot(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session()
        snapshot = {"semantic": {"entries": 10}, "episodic": {"episodes": 5}}
        mgr.set_memory_snapshot(sid, snapshot)
        data = mgr.get_session(sid)
        assert data.memory_snapshot == snapshot

    def test_set_agent_state(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session()
        state = {"name": "suyi", "state": "running", "tools": ["search"]}
        mgr.set_agent_state(sid, state)
        data = mgr.get_session(sid)
        assert data.agent_state == state

    def test_update_metadata(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session(metadata={"a": 1})
        mgr.update_metadata(sid, {"b": 2})
        data = mgr.get_session(sid)
        assert data.metadata == {"a": 1, "b": 2}

    def test_update_metadata_merges(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session(metadata={"x": 1})
        mgr.update_metadata(sid, {"x": 2, "y": 3})
        data = mgr.get_session(sid)
        assert data.metadata["x"] == 2
        assert data.metadata["y"] == 3


class TestSessionManagerPersistence:
    """Test save / load round-trip."""

    def test_save_and_load(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session()
        mgr.add_message(sid, "user", "Hello")
        mgr.add_message(sid, "assistant", "Hi!")
        mgr.set_memory_snapshot(sid, {"entries": 3})
        mgr.set_agent_state(sid, {"name": "suyi"})

        path = mgr.save_session(sid)
        assert os.path.exists(path)

        # Create a new manager to simulate fresh start
        mgr2 = SessionManager(storage_dir=str(tmp_path))
        data = mgr2.load_session(sid)
        assert data.session_id == sid
        assert len(data.history) == 2
        assert data.history[0]["content"] == "Hello"
        assert data.memory_snapshot == {"entries": 3}
        assert data.agent_state == {"name": "suyi"}

    def test_save_creates_json_file(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session()
        mgr.add_message(sid, "user", "test")
        path = mgr.save_session(sid)

        with open(path, "r") as f:
            content = json.load(f)
        assert content["session_id"] == sid
        assert len(content["history"]) == 1

    def test_load_nonexistent_file(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            mgr.load_session("does-not-exist")

    def test_save_missing_session(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        with pytest.raises(KeyError):
            mgr.save_session("nonexistent")


class TestSessionManagerList:
    """Test session listing."""

    def test_list_empty(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sessions = mgr.list_sessions()
        assert sessions == []

    def test_list_with_sessions(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        s1 = mgr.create_session(session_id="s1")
        mgr.add_message(s1, "user", "msg1")
        mgr.save_session(s1)

        s2 = mgr.create_session(session_id="s2")
        mgr.add_message(s2, "user", "msg2")
        mgr.add_message(s2, "user", "msg3")
        mgr.save_session(s2)

        sessions = mgr.list_sessions()
        assert len(sessions) == 2
        ids = {s["session_id"] for s in sessions}
        assert ids == {"s1", "s2"}

    def test_list_message_count(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session(session_id="count-test")
        mgr.add_message(sid, "user", "a")
        mgr.add_message(sid, "assistant", "b")
        mgr.save_session(sid)

        sessions = mgr.list_sessions()
        assert sessions[0]["message_count"] == 2

    def test_list_sorted_by_updated_desc(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        s1 = mgr.create_session(session_id="first")
        mgr.save_session(s1)

        s2 = mgr.create_session(session_id="second")
        mgr.save_session(s2)

        sessions = mgr.list_sessions()
        # Most recently updated should be first
        assert sessions[0]["session_id"] == "second"


class TestSessionManagerDelete:
    """Test session deletion."""

    def test_delete_session(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session()
        mgr.save_session(sid)
        assert mgr.session_exists(sid)

        deleted = mgr.delete_session(sid)
        assert deleted is True
        assert not mgr.session_exists(sid)

    def test_delete_nonexistent(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        deleted = mgr.delete_session("ghost")
        assert deleted is False

    def test_delete_removes_from_memory(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session()
        mgr.add_message(sid, "user", "hello")
        mgr.delete_session(sid)
        assert mgr.get_session(sid) is None


class TestSessionManagerExport:
    """Test session export."""

    def test_export_default_path(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session(session_id="export-test")
        mgr.add_message(sid, "user", "data")
        path = mgr.export_session(sid)

        assert os.path.exists(path)
        assert "export-test_export.json" in path

        with open(path, "r") as f:
            content = json.load(f)
        assert content["session_id"] == "export-test"

    def test_export_custom_path(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session()
        mgr.add_message(sid, "user", "msg")

        custom_path = str(tmp_path / "custom_export.json")
        result = mgr.export_session(sid, export_path=custom_path)
        assert result == custom_path
        assert os.path.exists(custom_path)


class TestSessionManagerMisc:
    """Test utility methods."""

    def test_session_exists_in_memory(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session()
        assert mgr.session_exists(sid)

    def test_session_exists_on_disk(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        sid = mgr.create_session()
        mgr.save_session(sid)

        mgr2 = SessionManager(storage_dir=str(tmp_path))
        assert mgr2.session_exists(sid)

    def test_session_not_exists(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        assert not mgr.session_exists("nope")

    def test_get_session_none(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        assert mgr.get_session("missing") is None

    def test_repr(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        r = repr(mgr)
        assert "SessionManager" in r
        assert "active=0" in r

    def test_multiple_sessions_independent(self, tmp_path):
        mgr = SessionManager(storage_dir=str(tmp_path))
        s1 = mgr.create_session(session_id="s1")
        s2 = mgr.create_session(session_id="s2")

        mgr.add_message(s1, "user", "msg for s1")
        mgr.add_message(s2, "user", "msg for s2")
        mgr.add_message(s2, "assistant", "reply for s2")

        assert len(mgr.get_history(s1)) == 1
        assert len(mgr.get_history(s2)) == 2
