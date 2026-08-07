"""
Suyi MCP Module — Model Context Protocol support.

Exports:
    Protocol:
        MCPMessage, MCPError, MCPTool, MCPResource, MCPPrompt
        PROTOCOL_VERSION, method constants, error codes
        build_initialize_request, build_initialize_response, build_initialized_notification

    Transport:
        Transport (abstract), StdioTransport, TCPTransport, MemoryTransport

    Server:
        MCPServer, serve_on_transport

    Client:
        MCPClient, RemoteMCPTool

Usage::

    from suyi.mcp import (
        MCPServer, MCPClient, MemoryTransport,
        MCPTool, MCPResource, MCPPrompt,
    )
"""

from .protocol import (
    # Version
    PROTOCOL_VERSION,
    # Data classes
    MCPError,
    MCPMessage,
    MCPPrompt,
    MCPResource,
    MCPTool,
    # Method names
    METHOD_INITIALIZE,
    METHOD_INITIALIZED,
    METHOD_PING,
    METHOD_TOOLS_LIST,
    METHOD_TOOLS_CALL,
    METHOD_RESOURCES_LIST,
    METHOD_RESOURCES_READ,
    METHOD_PROMPTS_LIST,
    METHOD_PROMPTS_GET,
    # Error codes
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
    TOOL_NOT_FOUND,
    RESOURCE_NOT_FOUND,
    PROMPT_NOT_FOUND,
    # Handshake helpers
    build_initialize_request,
    build_initialize_response,
    build_initialized_notification,
    reset_id_counter,
)
from .transport import (
    Transport,
    StdioTransport,
    TCPTransport,
    MemoryTransport,
)
from .server import (
    MCPServer,
    serve_on_transport,
)
from .client import (
    MCPClient,
    RemoteMCPTool,
)

__all__ = [
    # Protocol version
    "PROTOCOL_VERSION",
    # Data classes
    "MCPError",
    "MCPMessage",
    "MCPPrompt",
    "MCPResource",
    "MCPTool",
    # Method names
    "METHOD_INITIALIZE",
    "METHOD_INITIALIZED",
    "METHOD_PING",
    "METHOD_TOOLS_LIST",
    "METHOD_TOOLS_CALL",
    "METHOD_RESOURCES_LIST",
    "METHOD_RESOURCES_READ",
    "METHOD_PROMPTS_LIST",
    "METHOD_PROMPTS_GET",
    # Error codes
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",
    "TOOL_NOT_FOUND",
    "RESOURCE_NOT_FOUND",
    "PROMPT_NOT_FOUND",
    # Handshake helpers
    "build_initialize_request",
    "build_initialize_response",
    "build_initialized_notification",
    "reset_id_counter",
    # Transport
    "Transport",
    "StdioTransport",
    "TCPTransport",
    "MemoryTransport",
    # Server
    "MCPServer",
    "serve_on_transport",
    # Client
    "MCPClient",
    "RemoteMCPTool",
]
