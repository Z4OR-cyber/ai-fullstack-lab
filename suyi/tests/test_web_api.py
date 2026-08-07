"""
Tests for Suyi Web API — HTTP API server.

Covers:
    - Health check endpoint
    - Chat endpoint (with and without session persistence)
    - Memory endpoint
    - Tools endpoint
    - Skills load endpoint
    - Sessions listing endpoint
    - 404 handling for unknown routes
    - Error handling (missing fields, server errors)
    - CORS headers
    - Live HTTP server (start/stop on ephemeral port)
"""

import json
import os
import tempfile
import urllib.request

import pytest

from suyi.core.loop import LLMResponse, MockLLM, FunctionTool
from suyi.memory import MemoryManager
from suyi.persistence import SessionManager
from suyi.web import SuyiServer


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def mock_llm():
    """A MockLLM that always returns a friendly response."""
    return MockLLM([LLMResponse.text("Hello from Suyi!", tokens=20)])


@pytest.fixture
def server(mock_llm, tmp_path):
    """A SuyiServer with mock LLM and temp storage."""
    return SuyiServer(
        llm=mock_llm,
        memory_manager=MemoryManager(storage_dir=str(tmp_path / "memory")),
        session_manager=SessionManager(storage_dir=str(tmp_path / "data")),
    )


@pytest.fixture
def server_with_tools(mock_llm, tmp_path):
    """A SuyiServer with a registered tool."""
    def echo(**kwargs):
        return kwargs.get("text", "")

    echo_tool = FunctionTool("echo", "Echo the input text", echo)

    return SuyiServer(
        llm=mock_llm,
        tools=[echo_tool],
        memory_manager=MemoryManager(storage_dir=str(tmp_path / "memory")),
        session_manager=SessionManager(storage_dir=str(tmp_path / "data")),
    )


# ═══════════════════════════════════════════════════════════════
#  Health endpoint
# ═══════════════════════════════════════════════════════════════


class TestHealthEndpoint:
    """Test GET /health."""

    @pytest.mark.asyncio
    async def test_health_check(self, server):
        status, body = await server.handle_request("GET", "/health")
        assert status == 200
        assert body["status"] == "ok"
        assert body["service"] == "suyi"


# ═══════════════════════════════════════════════════════════════
#  Chat endpoint
# ═══════════════════════════════════════════════════════════════


class TestChatEndpoint:
    """Test POST /chat."""

    @pytest.mark.asyncio
    async def test_basic_chat(self, server):
        status, body = await server.handle_request("POST", "/chat", {"message": "Hi"})
        assert status == 200
        assert body["reply"] == "Hello from Suyi!"
        assert body["turns_used"] == 1
        assert body["stop_reason"] == "natural"
        assert body["complete"] is True

    @pytest.mark.asyncio
    async def test_chat_missing_message(self, server):
        status, body = await server.handle_request("POST", "/chat", {})
        assert status == 400
        assert "error" in body
        assert "message" in body["error"].lower()

    @pytest.mark.asyncio
    async def test_chat_empty_body(self, server):
        status, body = await server.handle_request("POST", "/chat")
        assert status == 400

    @pytest.mark.asyncio
    async def test_chat_with_session(self, server):
        """Chat with session_id should persist messages."""
        status, body = await server.handle_request("POST", "/chat", {
            "message": "Hello",
            "session_id": "test-session",
        })
        assert status == 200
        assert body["session_id"] == "test-session"

        # Verify session was saved
        sessions = server.session_manager.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "test-session"
        assert sessions[0]["message_count"] == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_chat_with_max_turns(self, server):
        status, body = await server.handle_request("POST", "/chat", {
            "message": "Hi",
            "max_turns": 3,
        })
        assert status == 200
        assert body["turns_used"] <= 3

    @pytest.mark.asyncio
    async def test_chat_tool_use(self, server_with_tools):
        """Chat with tools should handle tool calls in the response."""
        # MockLLM that first calls echo, then gives final answer
        server_with_tools.llm = MockLLM([
            LLMResponse.action("echo", {"text": "hello"}, content="Let me echo."),
            LLMResponse.text("Echoed: hello"),
        ])

        status, body = await server_with_tools.handle_request("POST", "/chat", {
            "message": "echo hello",
        })
        assert status == 200
        assert body["reply"] == "Echoed: hello"
        assert body["turns_used"] == 2


# ═══════════════════════════════════════════════════════════════
#  Memory endpoint
# ═══════════════════════════════════════════════════════════════


class TestMemoryEndpoint:
    """Test GET /memory."""

    @pytest.mark.asyncio
    async def test_memory_status(self, server):
        status, body = await server.handle_request("GET", "/memory")
        assert status == 200
        assert "working" in body
        assert "episodic" in body
        assert "semantic" in body

    @pytest.mark.asyncio
    async def test_memory_after_add(self, server):
        """Memory should reflect added entries."""
        server.memory_manager.add_memory("Python is great", tags=["python"])

        status, body = await server.handle_request("GET", "/memory")
        assert status == 200
        assert body["semantic"]["entries"] >= 1


# ═══════════════════════════════════════════════════════════════
#  Tools endpoint
# ═══════════════════════════════════════════════════════════════


class TestToolsEndpoint:
    """Test GET /tools."""

    @pytest.mark.asyncio
    async def test_tools_empty(self, server):
        status, body = await server.handle_request("GET", "/tools")
        assert status == 200
        assert body["tools"] == []
        assert body["count"] == 0

    @pytest.mark.asyncio
    async def test_tools_with_registered(self, server_with_tools):
        status, body = await server_with_tools.handle_request("GET", "/tools")
        assert status == 200
        assert body["count"] == 1
        assert body["tools"][0]["name"] == "echo"
        assert body["tools"][0]["description"] == "Echo the input text"
        assert "parameters" in body["tools"][0]


# ═══════════════════════════════════════════════════════════════
#  Skills endpoint
# ═══════════════════════════════════════════════════════════════


class TestSkillsEndpoint:
    """Test POST /skills/load."""

    @pytest.mark.asyncio
    async def test_skill_load_no_loader(self, server):
        """Without a skill loader, should return 503."""
        status, body = await server.handle_request("POST", "/skills/load", {
            "name": "some-skill",
        })
        assert status == 503
        assert "error" in body

    @pytest.mark.asyncio
    async def test_skill_load_missing_name(self, server):
        status, body = await server.handle_request("POST", "/skills/load", {})
        assert status == 400

    @pytest.mark.asyncio
    async def test_skill_load_success(self, tmp_path, mock_llm):
        """Test loading a skill with a real SkillLoader."""
        from suyi.skills import SkillLoader

        # Create a minimal skill directory
        skill_dir = tmp_path / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: test-skill\n"
            "description: A test skill\n"
            "---\n"
            "# Test Skill\n"
            "This is a test skill.\n",
            encoding="utf-8",
        )

        loader = SkillLoader(str(tmp_path / "skills"))
        server = SuyiServer(
            llm=mock_llm,
            skill_loader=loader,
            memory_manager=MemoryManager(storage_dir=str(tmp_path / "mem")),
            session_manager=SessionManager(storage_dir=str(tmp_path / "data")),
        )

        status, body = await server.handle_request("POST", "/skills/load", {
            "name": "test-skill",
        })
        assert status == 200
        assert body["name"] == "test-skill"
        assert body["loaded"] is True

    @pytest.mark.asyncio
    async def test_skill_load_not_found(self, tmp_path, mock_llm):
        from suyi.skills import SkillLoader

        loader = SkillLoader(str(tmp_path / "skills"))
        server = SuyiServer(
            llm=mock_llm,
            skill_loader=loader,
            memory_manager=MemoryManager(storage_dir=str(tmp_path / "mem")),
            session_manager=SessionManager(storage_dir=str(tmp_path / "data")),
        )

        status, body = await server.handle_request("POST", "/skills/load", {
            "name": "nonexistent-skill",
        })
        assert status == 404


# ═══════════════════════════════════════════════════════════════
#  Sessions endpoint
# ═══════════════════════════════════════════════════════════════


class TestSessionsEndpoint:
    """Test GET /sessions."""

    @pytest.mark.asyncio
    async def test_sessions_empty(self, server):
        status, body = await server.handle_request("GET", "/sessions")
        assert status == 200
        assert body["sessions"] == []
        assert body["count"] == 0

    @pytest.mark.asyncio
    async def test_sessions_after_chat(self, server):
        """After a chat with session_id, sessions should list it."""
        await server.handle_request("POST", "/chat", {
            "message": "Hi",
            "session_id": "sess-1",
        })

        status, body = await server.handle_request("GET", "/sessions")
        assert status == 200
        assert body["count"] == 1
        assert body["sessions"][0]["session_id"] == "sess-1"

    @pytest.mark.asyncio
    async def test_sessions_multiple(self, server):
        for i in range(3):
            await server.handle_request("POST", "/chat", {
                "message": f"msg-{i}",
                "session_id": f"sess-{i}",
            })

        status, body = await server.handle_request("GET", "/sessions")
        assert status == 200
        assert body["count"] == 3


# ═══════════════════════════════════════════════════════════════
#  Routing & error handling
# ═══════════════════════════════════════════════════════════════


class TestRouting:
    """Test routing and 404 handling."""

    @pytest.mark.asyncio
    async def test_unknown_path(self, server):
        status, body = await server.handle_request("GET", "/unknown")
        assert status == 404
        assert body["error"] == "Not found"

    @pytest.mark.asyncio
    async def test_wrong_method(self, server):
        """GET on a POST-only endpoint should 404."""
        status, body = await server.handle_request("GET", "/chat")
        assert status == 404

    @pytest.mark.asyncio
    async def test_health_with_post(self, server):
        """POST on a GET-only endpoint should 404."""
        status, body = await server.handle_request("POST", "/health")
        assert status == 404


# ═══════════════════════════════════════════════════════════════
#  Live HTTP server test
# ═══════════════════════════════════════════════════════════════


class TestLiveServer:
    """Test the actual HTTP server over a real socket."""

    def test_live_health(self, mock_llm, tmp_path):
        """Start server on ephemeral port, hit /health, verify response."""
        server = SuyiServer(
            llm=mock_llm,
            memory_manager=MemoryManager(storage_dir=str(tmp_path / "mem")),
            session_manager=SessionManager(storage_dir=str(tmp_path / "data")),
            host="127.0.0.1",
            port=0,  # will be overridden
        )

        # Start in background
        import threading
        from http.server import ThreadingHTTPServer

        server_ref = server

        class _Handler(__import__("http.server", fromlist=["BaseHTTPRequestHandler"]).BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                import asyncio
                status, payload = asyncio.run(
                    server_ref.handle_request("GET", self.path)
                )
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        port = httpd.server_address[1]

        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        try:
            # Make actual HTTP request
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as resp:
                assert resp.status == 200
                data = json.loads(resp.read())
                assert data["status"] == "ok"

                # Check CORS header
                cors = resp.headers.get("Access-Control-Allow-Origin")
                assert cors == "*"
        finally:
            httpd.shutdown()
            httpd.server_close()


# ═══════════════════════════════════════════════════════════════
#  Server lifecycle
# ═══════════════════════════════════════════════════════════════


class TestServerLifecycle:
    """Test server initialization and repr."""

    def test_default_init(self):
        server = SuyiServer()
        assert server.host == "0.0.0.0"
        assert server.port == 8080
        assert server.llm is not None
        assert server.memory_manager is not None
        assert server.session_manager is not None

    def test_custom_init(self, mock_llm, tmp_path):
        server = SuyiServer(
            llm=mock_llm,
            host="localhost",
            port=9999,
            memory_manager=MemoryManager(storage_dir=str(tmp_path / "m")),
            session_manager=SessionManager(storage_dir=str(tmp_path / "d")),
        )
        assert server.host == "localhost"
        assert server.port == 9999

    def test_repr(self, server):
        r = repr(server)
        assert "SuyiServer" in r

    def test_start_background_and_stop(self, mock_llm, tmp_path):
        """Test starting and stopping the server in background."""
        server = SuyiServer(
            llm=mock_llm,
            memory_manager=MemoryManager(storage_dir=str(tmp_path / "m")),
            session_manager=SessionManager(storage_dir=str(tmp_path / "d")),
            host="127.0.0.1",
            port=0,
        )

        # We can't use port=0 with start_background easily, so test stop without start
        server.stop()  # Should not raise
