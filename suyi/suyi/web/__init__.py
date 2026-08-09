"""
Suyi Web — Lightweight HTTP API server with authentication & security.

Exports:
    SuyiServer:  Async HTTP server built on the standard library.
    AuthConfig:  Authentication & CORS configuration dataclass.
    AuthManager: API Key + JWT authentication and CORS manager.

The server exposes a small REST API for interacting with a Suyi agent
without depending on Flask, FastAPI, or any third-party web framework.

Endpoints:
    POST /chat          — Send a message, get the agent's reply.
    GET  /memory        — View the memory system status.
    GET  /tools         — List registered tools.
    POST /skills/load   — Load a skill by name.
    GET  /health        — Health check (no auth required).
    GET  /sessions      — List persisted sessions.
    POST /auth/token    — Exchange API Key for JWT (no auth required).

Authentication:
    - API Key via ``Authorization: Bearer <key>`` or ``X-API-Key: <key>``
    - JWT (HS256) via ``Authorization: Bearer <jwt>``
    - Priority: JWT > API Key

Usage::

    from suyi.web import SuyiServer, AuthConfig
    from suyi.core import MockLLM, LLMResponse

    server = SuyiServer(
        llm=MockLLM([LLMResponse.text("Hi!")]),
        auth_config=AuthConfig(
            api_keys=["my-key"],
            jwt_secret="my-secret",
        ),
    )
    server.start(host="0.0.0.0", port=8080)
"""

from .server import SuyiServer
from .auth import AuthConfig, AuthManager

__all__ = [
    "SuyiServer",
    "AuthConfig",
    "AuthManager",
]
