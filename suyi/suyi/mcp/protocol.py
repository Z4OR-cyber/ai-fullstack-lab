"""
MCP Protocol — Model Context Protocol data structures and JSON-RPC 2.0 messaging.

Implements the core protocol primitives:
    - MCPMessage: JSON-RPC 2.0 message envelope (request / response / error / notification)
    - MCPTool: Tool descriptor
    - MCPResource: Resource descriptor
    - MCPPrompt: Prompt template descriptor
    - Protocol version negotiation helpers
    - Standard method names and error codes

No third-party MCP SDK dependency — pure Python.

Reference: Model Context Protocol Specification (2024-11-05)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional, Union

# ═══════════════════════════════════════════════════════════════
#  Protocol Version
# ═══════════════════════════════════════════════════════════════

PROTOCOL_VERSION = "2024-11-05"

# ═══════════════════════════════════════════════════════════════
#  JSON-RPC 2.0 Standard Error Codes
# ═══════════════════════════════════════════════════════════════

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# MCP-specific error codes (server-defined range -32000 to -32099)
TOOL_NOT_FOUND = -32001
RESOURCE_NOT_FOUND = -32002
PROMPT_NOT_FOUND = -32003

# ═══════════════════════════════════════════════════════════════
#  Standard Method Names
# ═══════════════════════════════════════════════════════════════

METHOD_INITIALIZE = "initialize"
METHOD_INITIALIZED = "notifications/initialized"
METHOD_PING = "ping"

METHOD_TOOLS_LIST = "tools/list"
METHOD_TOOLS_CALL = "tools/call"

METHOD_RESOURCES_LIST = "resources/list"
METHOD_RESOURCES_READ = "resources/read"

METHOD_PROMPTS_LIST = "prompts/list"
METHOD_PROMPTS_GET = "prompts/get"


# ═══════════════════════════════════════════════════════════════
#  Error Object
# ═══════════════════════════════════════════════════════════════


@dataclass
class MCPError:
    """JSON-RPC 2.0 error object.

    Attributes:
        code:    Numeric error code.
        message: Short error description.
        data:    Optional additional error data.
    """

    code: int
    message: str
    data: Optional[Any] = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "MCPError":
        return cls(
            code=d.get("code", 0),
            message=d.get("message", ""),
            data=d.get("data"),
        )

    def __str__(self) -> str:
        return f"MCPError(code={self.code}, message={self.message!r})"


# ═══════════════════════════════════════════════════════════════
#  Message Envelope
# ═══════════════════════════════════════════════════════════════


@dataclass
class MCPMessage:
    """JSON-RPC 2.0 message envelope.

    A message can be one of four types:
    - **Request**:      has ``method`` and ``id`` (expects a response)
    - **Notification**: has ``method`` but no ``id`` (no response expected)
    - **Response**:     has ``result`` and ``id`` (no method)
    - **Error**:        has ``error`` and ``id`` (no method)

    Attributes:
        jsonrpc: Protocol version string, always "2.0".
        method:  Method name (for requests and notifications).
        params:  Method parameters (for requests and notifications).
        id:      Request/response correlation ID.
        result:  Result data (for responses).
        error:   Error object (for error responses).
    """

    jsonrpc: str = "2.0"
    method: Optional[str] = None
    params: Optional[dict] = None
    id: Optional[Union[int, str]] = None
    result: Optional[Any] = None
    error: Optional[MCPError] = None

    # ── Type predicates ────────────────────────────────────────

    @property
    def is_request(self) -> bool:
        """True if this is a JSON-RPC request (method + id)."""
        return self.method is not None and self.id is not None

    @property
    def is_notification(self) -> bool:
        """True if this is a notification (method, no id)."""
        return self.method is not None and self.id is None

    @property
    def is_response(self) -> bool:
        """True if this is a successful response (result + id, no method)."""
        return self.method is None and self.id is not None and self.error is None

    @property
    def is_error(self) -> bool:
        """True if this is an error response (error + id, no method)."""
        return self.method is None and self.id is not None and self.error is not None

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict:
        """Convert to a plain dict for JSON serialization."""
        d: dict[str, Any] = {"jsonrpc": "2.0"}
        if self.method is not None:
            d["method"] = self.method
        if self.params is not None:
            d["params"] = self.params
        if self.id is not None:
            d["id"] = self.id
        if self.result is not None:
            d["result"] = self.result
        if self.error is not None:
            d["error"] = self.error.to_dict()
        return d

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict) -> "MCPMessage":
        """Deserialize from a plain dict."""
        error = None
        if d.get("error") is not None:
            error = MCPError.from_dict(d["error"])
        return cls(
            jsonrpc=d.get("jsonrpc", "2.0"),
            method=d.get("method"),
            params=d.get("params"),
            id=d.get("id"),
            result=d.get("result"),
            error=error,
        )

    @classmethod
    def from_json(cls, s: str) -> "MCPMessage":
        """Deserialize from a JSON string."""
        return cls.from_dict(json.loads(s))

    # ── Factory methods ────────────────────────────────────────

    @staticmethod
    def request(
        method: str,
        params: Optional[dict] = None,
        id: Optional[Union[int, str]] = None,
    ) -> "MCPMessage":
        """Create a JSON-RPC request."""
        return MCPMessage(method=method, params=params, id=id or _next_id())

    @staticmethod
    def notification(
        method: str, params: Optional[dict] = None
    ) -> "MCPMessage":
        """Create a JSON-RPC notification (no id, no response expected)."""
        return MCPMessage(method=method, params=params)

    @staticmethod
    def response(result: Any, id: Union[int, str]) -> "MCPMessage":
        """Create a successful JSON-RPC response."""
        return MCPMessage(result=result, id=id)

    @staticmethod
    def error_response(
        code: int,
        message: str,
        id: Union[int, str],
        data: Optional[Any] = None,
    ) -> "MCPMessage":
        """Create an error JSON-RPC response."""
        return MCPMessage(
            error=MCPError(code=code, message=message, data=data),
            id=id,
        )

    def __repr__(self) -> str:
        if self.is_request:
            return f"MCPMessage(request, method={self.method!r}, id={self.id})"
        if self.is_notification:
            return f"MCPMessage(notification, method={self.method!r})"
        if self.is_error:
            return f"MCPMessage(error, id={self.id}, error={self.error})"
        return f"MCPMessage(response, id={self.id})"


# ── ID counter for auto-generated request IDs ─────────────────

_id_counter: int = 0


def _next_id() -> int:
    """Generate the next sequential request ID."""
    global _id_counter
    _id_counter += 1
    return _id_counter


def reset_id_counter() -> None:
    """Reset the ID counter (for testing)."""
    global _id_counter
    _id_counter = 0


# ═══════════════════════════════════════════════════════════════
#  Descriptors
# ═══════════════════════════════════════════════════════════════


@dataclass
class MCPTool:
    """MCP tool descriptor.

    Attributes:
        name:        Tool name (unique identifier).
        description: Human-readable description.
        inputSchema: JSON Schema describing the tool's input parameters.
    """

    name: str
    description: str = ""
    inputSchema: dict = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MCPTool":
        return cls(
            name=d.get("name", ""),
            description=d.get("description", ""),
            inputSchema=d.get(
                "inputSchema",
                d.get("input_schema", {"type": "object", "properties": {}}),
            ),
        )


@dataclass
class MCPResource:
    """MCP resource descriptor.

    Attributes:
        uri:         Unique resource URI (e.g., "file:///path/to/file").
        name:        Human-readable name.
        description: Optional description.
        mimeType:    Optional MIME type.
    """

    uri: str
    name: str = ""
    description: str = ""
    mimeType: str = ""

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"uri": self.uri, "name": self.name}
        if self.description:
            d["description"] = self.description
        if self.mimeType:
            d["mimeType"] = self.mimeType
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "MCPResource":
        return cls(
            uri=d.get("uri", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            mimeType=d.get("mimeType", d.get("mime_type", "")),
        )


@dataclass
class MCPPrompt:
    """MCP prompt template descriptor.

    Attributes:
        name:        Prompt name (unique identifier).
        description: Human-readable description.
        arguments:   List of argument descriptors.
    """

    name: str
    description: str = ""
    arguments: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"name": self.name, "description": self.description}
        if self.arguments:
            d["arguments"] = self.arguments
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "MCPPrompt":
        return cls(
            name=d.get("name", ""),
            description=d.get("description", ""),
            arguments=d.get("arguments", []),
        )


# ═══════════════════════════════════════════════════════════════
#  Protocol Handshake Helpers
# ═══════════════════════════════════════════════════════════════


def build_initialize_request(
    client_name: str = "suyi-mcp-client",
    client_version: str = "1.0.0",
) -> MCPMessage:
    """Build the ``initialize`` request message for the MCP handshake.

    The client sends this as the first message after connecting.
    """
    return MCPMessage.request(
        METHOD_INITIALIZE,
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": client_name, "version": client_version},
        },
    )


def build_initialize_response(
    server_name: str,
    server_version: str,
    id: Union[int, str],
) -> MCPMessage:
    """Build the ``initialize`` response message.

    The server sends this in reply to an ``initialize`` request,
    declaring its protocol version and capabilities.
    """
    return MCPMessage.response(
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {},
            },
            "serverInfo": {"name": server_name, "version": server_version},
        },
        id,
    )


def build_initialized_notification() -> MCPMessage:
    """Build the ``notifications/initialized`` message.

    The client sends this after receiving and accepting the
    ``initialize`` response, completing the handshake.
    """
    return MCPMessage.notification(METHOD_INITIALIZED)
