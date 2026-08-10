"""
Suyi Web — Lightweight HTTP API server with authentication & security.

Exports:
    SuyiServer:  Async HTTP server built on the standard library.
    AuthConfig:  Authentication & CORS configuration dataclass.
    AuthManager: API Key + JWT authentication and CORS manager.
    RBACManager: Role-Based Access Control manager.
    AuditLogger: Security audit log recorder.

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

Authorization (RBAC):
    - Role-based access control via ``RBACManager``
    - Roles: ADMIN / DEVELOPER / OPERATOR / VIEWER
    - Permissions: READ / WRITE / EXECUTE / DELETE / MANAGE_USERS / VIEW_AUDIT_LOG
    - Auditable actions recorded via ``AuditLogger``

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
from .rbac import (
    RBACManager,
    Role,
    Permission,
    ROLE_PERMISSIONS,
)
from .audit_log import (
    AuditLogger,
    AuditEntry,
    AuditResult,
    AuditLevel,
)

__all__ = [
    "SuyiServer",
    "AuthConfig",
    "AuthManager",
    "RBACManager",
    "Role",
    "Permission",
    "ROLE_PERMISSIONS",
    "AuditLogger",
    "AuditEntry",
    "AuditResult",
    "AuditLevel",
]
