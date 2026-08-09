"""
Lightweight HTTP API server built on the Python standard library.

No Flask, no FastAPI — just :mod:`http.server` + :mod:`asyncio`.

Endpoints
---------

+-------------------+--------+-------------------------------------------+
| Path              | Method | Description                               |
+===================+========+===========================================+
| ``/chat``         | POST   | Send a message, receive the agent reply.  |
| ``/memory``       | GET    | View memory system status.                |
| ``/tools``        | GET    | List registered tools.                    |
| ``/skills/load``  | POST   | Load a skill by name.                     |
| ``/health``       | GET    | Health-check ping.                        |
| ``/sessions``     | GET    | List persisted sessions.                  |
+-------------------+--------+-------------------------------------------+

CORS is enabled on all responses (``Access-Control-Allow-Origin: *``).

The server is designed so that the core request logic lives in the
async :meth:`SuyiServer.handle_request` method, which is trivially
testable without starting a real socket.
"""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from ..core.loop import (
    AgentLoop,
    LLMInterface,
    LLMResponse,
    MockLLM,
    Tool,
    LoopResult,
)
from ..core.budget import BudgetTracker, BudgetConfig
from ..core.context import ContextAssembler, IdentityConfig
from ..memory import MemoryManager
from ..persistence import SessionManager
from ..skills import SkillLoader
from .auth import AuthConfig, AuthManager


# ═══════════════════════════════════════════════════════════════
#  Server
# ═══════════════════════════════════════════════════════════════


class SuyiServer:
    """
    Async HTTP API server for Suyi agents.

    Args:
        llm:             An LLM interface (e.g. MockLLM, OpenAIAdapter).
        tools:           Optional list of Tool instances.
        memory_manager:  Optional MemoryManager.  A fresh one is created
                         if not provided.
        session_manager: Optional SessionManager.  A fresh one is created
                         if not provided.
        skill_loader:    Optional SkillLoader for the /skills/load endpoint.
        system_prompt:   System prompt for the agent loop.
        host:            Bind address (default ``0.0.0.0``).
        port:            Bind port (default ``8080``).
        auth_config:     Optional AuthConfig for authentication & CORS.
                         If not provided, a default config is used
                         (auth_enabled=True but no credentials → not active).
    """

    def __init__(
        self,
        llm: Optional[LLMInterface] = None,
        tools: Optional[list[Tool]] = None,
        memory_manager: Optional[MemoryManager] = None,
        session_manager: Optional[SessionManager] = None,
        skill_loader: Optional[SkillLoader] = None,
        system_prompt: str = "",
        host: str = "0.0.0.0",
        port: int = 8080,
        auth_config: Optional[AuthConfig] = None,
    ) -> None:
        self.llm = llm or MockLLM([LLMResponse.text("Hello from Suyi!")])
        self.tools: dict[str, Tool] = {t.name: t for t in (tools or [])}
        self.memory_manager = memory_manager or MemoryManager()
        self.session_manager = session_manager or SessionManager()
        self.skill_loader = skill_loader
        self.system_prompt = system_prompt
        self.host = host
        self.port = port

        # 认证与安全
        self.auth_config: AuthConfig = auth_config or AuthConfig()
        self.auth_manager: AuthManager = AuthManager(self.auth_config)

        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    #  Core request handler (async, testable without a socket)
    # ------------------------------------------------------------------

    async def handle_request(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> tuple[int, dict[str, Any]]:
        """
        Process a single request.

        Args:
            method:  HTTP method (``"GET"`` or ``"POST"``).
            path:    Request path (e.g. ``"/chat"``).
            body:    Parsed JSON body for POST requests.
            headers: Request headers dict (for authentication).
                     If not provided, auth check is skipped when
                     no credentials are configured.

        Returns:
            A ``(status_code, response_dict)`` tuple.
        """
        body = body or {}
        headers = headers or {}

        # ── 认证检查 ──────────────────────────────────────────
        # 仅在认证生效且路径不豁免时检查
        if (
            self.auth_manager.is_auth_active()
            and not self.auth_manager.is_exempt(method, path)
        ):
            allowed, error = self.auth_manager.authenticate(headers)
            if not allowed:
                return 401, error

        # ── Route ───────────────────────────────────────────────
        if path == "/health" and method == "GET":
            return 200, {"status": "ok", "service": "suyi"}

        if path == "/auth/token" and method == "POST":
            return self.auth_manager.create_token_response(headers, body)

        if path == "/chat" and method == "POST":
            return await self._handle_chat(body)

        if path == "/memory" and method == "GET":
            return self._handle_memory()

        if path == "/tools" and method == "GET":
            return self._handle_tools()

        if path == "/skills/load" and method == "POST":
            return await self._handle_skill_load(body)

        if path == "/sessions" and method == "GET":
            return self._handle_sessions()

        # ── Not found ──────────────────────────────────────────
        return 404, {"error": "Not found", "path": path, "method": method}

    # ------------------------------------------------------------------
    #  Endpoint implementations
    # ------------------------------------------------------------------

    async def _handle_chat(self, body: dict) -> tuple[int, dict]:
        """POST /chat — run the agent loop and return the reply."""
        message = body.get("message", "")
        if not message:
            return 400, {"error": "Missing 'message' field in request body."}

        session_id = body.get("session_id")

        # Build a fresh AgentLoop for this request
        budget_tracker = BudgetTracker(BudgetConfig(max_turns=body.get("max_turns", 10)))
        context_assembler = ContextAssembler(
            identity=IdentityConfig(name="suyi", instructions=self.system_prompt),
            tool_defs=[t.to_definition() for t in self.tools.values()] if self.tools else [],
        )

        loop = AgentLoop(
            llm=self.llm,
            tools=list(self.tools.values()) if self.tools else None,
            budget_tracker=budget_tracker,
            context_assembler=context_assembler,
        )

        try:
            result: LoopResult = await loop.run(message)
        except Exception as e:
            return 500, {"error": str(e), "type": type(e).__name__}

        response: dict[str, Any] = {
            "reply": result.content,
            "turns_used": result.turns_used,
            "stop_reason": result.stop_reason,
            "complete": result.is_complete,
        }

        # Persist to session if requested
        if session_id:
            if not self.session_manager.session_exists(session_id):
                self.session_manager.create_session(session_id)
            self.session_manager.add_message(session_id, "user", message)
            self.session_manager.add_message(session_id, "assistant", result.content)
            self.session_manager.save_session(session_id)
            response["session_id"] = session_id

        return 200, response

    def _handle_memory(self) -> tuple[int, dict]:
        """GET /memory — return memory system status."""
        try:
            status = self.memory_manager.get_status()
            return 200, status
        except Exception as e:
            return 500, {"error": str(e)}

    def _handle_tools(self) -> tuple[int, dict]:
        """GET /tools — list registered tools."""
        tools_list = []
        for name, tool in self.tools.items():
            tools_list.append({
                "name": name,
                "description": tool.description,
                "permission": tool.default_permission,
                "parameters": tool.parameters,
            })
        return 200, {"tools": tools_list, "count": len(tools_list)}

    async def _handle_skill_load(self, body: dict) -> tuple[int, dict]:
        """POST /skills/load — load a skill by name."""
        skill_name = body.get("name", "")
        if not skill_name:
            return 400, {"error": "Missing 'name' field in request body."}

        if self.skill_loader is None:
            return 503, {"error": "No skill loader configured."}

        try:
            content = self.skill_loader.load_skill(skill_name)
            if content is None:
                return 404, {"error": f"Skill '{skill_name}' not found."}
            return 200, {
                "name": skill_name,
                "description": content.description if hasattr(content, "description") else "",
                "loaded": True,
            }
        except Exception as e:
            return 500, {"error": str(e)}

    def _handle_sessions(self) -> tuple[int, dict]:
        """GET /sessions — list persisted sessions."""
        sessions = self.session_manager.list_sessions()
        return 200, {"sessions": sessions, "count": len(sessions)}

    # ------------------------------------------------------------------
    #  HTTP server lifecycle
    # ------------------------------------------------------------------

    def start(self, host: Optional[str] = None, port: Optional[int] = None) -> None:
        """Start the HTTP server (blocking call).

        Args:
            host: Override the bind address.
            port: Override the bind port.
        """
        host = host or self.host
        port = port or self.port

        server_ref = self  # closure capture

        class _Handler(BaseHTTPRequestHandler):
            """Inner request handler — delegates to the server."""

            def log_message(self, fmt: str, *args: Any) -> None:
                # Suppress default logging
                pass

            def _headers_to_dict(self) -> dict[str, str]:
                """将 HTTP 请求头转为普通字典（供认证检查使用）."""
                return {k: v for k, v in self.headers.items()}

            def _set_cors_headers(self) -> None:
                """设置可配置的 CORS 响应头."""
                origin = self.headers.get("Origin")
                cors_headers = server_ref.auth_manager.get_cors_headers(origin)
                for key, value in cors_headers.items():
                    self.send_header(key, value)

            def _send_json(self, status: int, payload: dict) -> None:
                body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body_bytes)))
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(body_bytes)

            def _read_body(self) -> dict:
                length = int(self.headers.get("Content-Length", 0))
                if length == 0:
                    return {}
                raw = self.rfile.read(length)
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return {}

            def do_OPTIONS(self) -> None:  # noqa: N802
                """处理 CORS 预检请求."""
                self.send_response(204)
                self._set_cors_headers()
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802
                req_headers = self._headers_to_dict()
                status, payload = asyncio.run(
                    server_ref.handle_request("GET", self.path, headers=req_headers)
                )
                self._send_json(status, payload)

            def do_POST(self) -> None:  # noqa: N802
                body = self._read_body()
                req_headers = self._headers_to_dict()
                status, payload = asyncio.run(
                    server_ref.handle_request("POST", self.path, body, req_headers)
                )
                self._send_json(status, payload)

        self._httpd = ThreadingHTTPServer((host, port), _Handler)
        self._httpd.serve_forever()

    def start_background(self, host: Optional[str] = None, port: Optional[int] = None) -> None:
        """Start the server in a background daemon thread (non-blocking)."""
        self._thread = threading.Thread(
            target=self.start, args=(host, port), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the HTTP server if running."""
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def __repr__(self) -> str:
        return (
            f"SuyiServer(host={self.host!r}, port={self.port}, "
            f"tools={list(self.tools.keys())})"
        )
