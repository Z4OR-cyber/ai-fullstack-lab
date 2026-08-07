"""
Suyi Web — Lightweight HTTP API server.

Exports:
    SuyiServer:  Async HTTP server built on the standard library.

The server exposes a small REST API for interacting with a Suyi agent
without depending on Flask, FastAPI, or any third-party web framework.

Endpoints:
    POST /chat          — Send a message, get the agent's reply.
    GET  /memory        — View the memory system status.
    GET  /tools         — List registered tools.
    POST /skills/load   — Load a skill by name.
    GET  /health        — Health check.
    GET  /sessions      — List persisted sessions.

Usage::

    from suyi.web import SuyiServer
    from suyi.core import MockLLM, LLMResponse

    server = SuyiServer(llm=MockLLM([LLMResponse.text("Hi!")]))
    server.start(host="0.0.0.0", port=8080)
"""

from .server import SuyiServer

__all__ = [
    "SuyiServer",
]
