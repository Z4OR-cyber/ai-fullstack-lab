"""
MCP Server — Expose Suyi tools, resources, and prompts via the MCP protocol.

The :class:`MCPServer` adapts Suyi's :class:`~suyi.tools.base.AgentTool`
instances to MCP tools, making them callable by any MCP-compatible client.

Key features:
    - Register Suyi ``AgentTool`` instances as MCP tools
    - Register static resources and prompt templates
    - Handle JSON-RPC 2.0 request/response cycle
    - Protocol version negotiation (initialize/initialized)
    - Serve over any :class:`~suyi.mcp.transport.Transport` (stdio, TCP, memory)

Usage::

    from suyi.mcp import MCPServer, MemoryTransport
    from suyi.tools import BashTool

    server = MCPServer(name="my-server", version="1.0.0")
    server.register_tool(BashTool())

    # Serve over memory transport (for testing)
    client_t, server_t = MemoryTransport.create_pair()
    import asyncio
    asyncio.run(server.serve_once(server_t, initialize_msg))
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable, Optional, Union

from ..tools.base import AgentTool, ToolContext, ToolParameter, ToolResult
from .protocol import (
    PROTOCOL_VERSION,
    MCPError,
    MCPMessage,
    MCPResource,
    MCPPrompt,
    MCPTool,
    # Methods
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
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
    TOOL_NOT_FOUND,
    RESOURCE_NOT_FOUND,
    PROMPT_NOT_FOUND,
    build_initialize_response,
)
from .transport import Transport


class MCPServer:
    """MCP Server — exposes tools, resources, and prompts via MCP protocol.

    Adapts Suyi's :class:`~suyi.tools.base.AgentTool` to MCP tools.
    Handles JSON-RPC 2.0 request/response over any transport.

    Args:
        name:    Server name (reported in initialize response).
        version: Server version.
    """

    def __init__(
        self,
        name: str = "suyi-mcp-server",
        version: str = "1.0.0",
    ):
        self.name = name
        self.version = version

        self._tools: dict[str, AgentTool] = {}
        self._resources: dict[str, MCPResource] = {}
        self._resource_handlers: dict[str, Callable[[], Any]] = {}
        self._prompts: dict[str, MCPPrompt] = {}

        self._initialized = False
        self._client_info: Optional[dict] = None

    # ── Registration ───────────────────────────────────────────

    def register_tool(self, tool: AgentTool) -> None:
        """Register a Suyi AgentTool as an MCP tool."""
        self._tools[tool.name] = tool

    def register_resource(
        self,
        resource: MCPResource,
        handler: Optional[Callable[[], Any]] = None,
    ) -> None:
        """Register an MCP resource with an optional read handler.

        Args:
            resource: Resource descriptor.
            handler:  Callable that returns the resource content when read.
                      If None, the resource URI is returned as text.
        """
        self._resources[resource.uri] = resource
        if handler is not None:
            self._resource_handlers[resource.uri] = handler

    def register_prompt(self, prompt: MCPPrompt) -> None:
        """Register an MCP prompt template."""
        self._prompts[prompt.name] = prompt

    # ── Properties ─────────────────────────────────────────────

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    @property
    def resource_uris(self) -> list[str]:
        return list(self._resources.keys())

    @property
    def prompt_names(self) -> list[str]:
        return list(self._prompts.keys())

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    # ── Message Handling ───────────────────────────────────────

    async def handle_message(
        self, message: MCPMessage
    ) -> Optional[MCPMessage]:
        """Handle a single MCP message.

        Returns:
            - A response :class:`MCPMessage` for requests.
            - ``None`` for notifications (no response expected).
        """
        # Notifications don't get responses
        if message.is_notification:
            if message.method == METHOD_INITIALIZED:
                self._initialized = True
            return None

        # Validate it's a request
        if not message.is_request:
            return MCPMessage.error_response(
                INVALID_REQUEST,
                "Message is not a valid request",
                message.id if message.id is not None else 0,
            )

        method = message.method
        params = message.params or {}
        msg_id = message.id

        try:
            handler = self._METHOD_HANDLERS.get(method)
            if handler is None:
                return MCPMessage.error_response(
                    METHOD_NOT_FOUND,
                    f"Unknown method: {method}",
                    msg_id,
                )
            return await handler(self, params, msg_id)
        except Exception as e:
            return MCPMessage.error_response(
                INTERNAL_ERROR,
                f"Internal error: {e}",
                msg_id,
            )

    # ── Method Handlers ────────────────────────────────────────

    async def _handle_initialize(
        self, params: dict, msg_id: Union[int, str]
    ) -> MCPMessage:
        """Handle the ``initialize`` request."""
        self._client_info = params.get("clientInfo", {})
        client_protocol = params.get("protocolVersion", PROTOCOL_VERSION)
        # Negotiate protocol version — use server's version
        negotiated = PROTOCOL_VERSION if client_protocol == PROTOCOL_VERSION else PROTOCOL_VERSION
        return MCPMessage.response(
            {
                "protocolVersion": negotiated,
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {},
                },
                "serverInfo": {"name": self.name, "version": self.version},
            },
            msg_id,
        )

    async def _handle_ping(
        self, params: dict, msg_id: Union[int, str]
    ) -> MCPMessage:
        """Handle the ``ping`` request."""
        return MCPMessage.response({}, msg_id)

    async def _handle_tools_list(
        self, params: dict, msg_id: Union[int, str]
    ) -> MCPMessage:
        """Handle the ``tools/list`` request."""
        tools = []
        for tool in self._tools.values():
            schema = tool.to_schema()
            tools.append(
                MCPTool(
                    name=schema["name"],
                    description=schema.get("description", ""),
                    inputSchema=schema.get("parameters", {"type": "object", "properties": {}}),
                ).to_dict()
            )
        return MCPMessage.response({"tools": tools}, msg_id)

    async def _handle_tools_call(
        self, params: dict, msg_id: Union[int, str]
    ) -> MCPMessage:
        """Handle the ``tools/call`` request."""
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        if not name:
            return MCPMessage.error_response(
                INVALID_PARAMS,
                "Missing 'name' parameter",
                msg_id,
            )

        tool = self._tools.get(name)
        if tool is None:
            return MCPMessage.error_response(
                TOOL_NOT_FOUND,
                f"Tool not found: {name}",
                msg_id,
            )

        # Execute the tool
        context = ToolContext()
        result = tool.execute(arguments, context)
        if asyncio.iscoroutine(result):
            result = await result

        # Convert ToolResult to MCP call result
        content: list[dict] = []
        if result.success:
            output = result.output
            if isinstance(output, str):
                content.append({"type": "text", "text": output})
            elif isinstance(output, (dict, list)):
                content.append(
                    {"type": "text", "text": json.dumps(output, ensure_ascii=False)}
                )
            else:
                content.append({"type": "text", "text": str(output)})
        else:
            error_text = result.error or "Tool execution failed"
            content.append({"type": "text", "text": error_text})

        return MCPMessage.response(
            {"content": content, "isError": not result.success},
            msg_id,
        )

    async def _handle_resources_list(
        self, params: dict, msg_id: Union[int, str]
    ) -> MCPMessage:
        """Handle the ``resources/list`` request."""
        resources = [r.to_dict() for r in self._resources.values()]
        return MCPMessage.response({"resources": resources}, msg_id)

    async def _handle_resources_read(
        self, params: dict, msg_id: Union[int, str]
    ) -> MCPMessage:
        """Handle the ``resources/read`` request."""
        uri = params.get("uri", "")
        if not uri:
            return MCPMessage.error_response(
                INVALID_PARAMS,
                "Missing 'uri' parameter",
                msg_id,
            )

        resource = self._resources.get(uri)
        if resource is None:
            return MCPMessage.error_response(
                RESOURCE_NOT_FOUND,
                f"Resource not found: {uri}",
                msg_id,
            )

        # Call the handler if registered, otherwise return empty
        handler = self._resource_handlers.get(uri)
        if handler is not None:
            content_val = handler()
        else:
            content_val = ""

        contents = [
            {
                "uri": uri,
                "mimeType": resource.mimeType or "text/plain",
                "text": str(content_val),
            }
        ]
        return MCPMessage.response({"contents": contents}, msg_id)

    async def _handle_prompts_list(
        self, params: dict, msg_id: Union[int, str]
    ) -> MCPMessage:
        """Handle the ``prompts/list`` request."""
        prompts = [p.to_dict() for p in self._prompts.values()]
        return MCPMessage.response({"prompts": prompts}, msg_id)

    async def _handle_prompts_get(
        self, params: dict, msg_id: Union[int, str]
    ) -> MCPMessage:
        """Handle the ``prompts/get`` request."""
        name = params.get("name", "")
        prompt = self._prompts.get(name)
        if prompt is None:
            return MCPMessage.error_response(
                PROMPT_NOT_FOUND,
                f"Prompt not found: {name}",
                msg_id,
            )
        # Return a basic message structure
        return MCPMessage.response(
            {
                "description": prompt.description,
                "messages": [],
            },
            msg_id,
        )

    # ── Method dispatch table (class-level for clarity) ────────

    _METHOD_HANDLERS: dict[str, Any] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    # Register handlers in the dispatch table
    # (done after class definition below)


# Populate the dispatch table
MCPServer._METHOD_HANDLERS = {
    METHOD_INITIALIZE: MCPServer._handle_initialize,
    METHOD_PING: MCPServer._handle_ping,
    METHOD_TOOLS_LIST: MCPServer._handle_tools_list,
    METHOD_TOOLS_CALL: MCPServer._handle_tools_call,
    METHOD_RESOURCES_LIST: MCPServer._handle_resources_list,
    METHOD_RESOURCES_READ: MCPServer._handle_resources_read,
    METHOD_PROMPTS_LIST: MCPServer._handle_prompts_list,
    METHOD_PROMPTS_GET: MCPServer._handle_prompts_get,
}


# ═══════════════════════════════════════════════════════════════
#  Server Runner
# ═══════════════════════════════════════════════════════════════


async def serve_on_transport(
    server: MCPServer,
    transport: Transport,
) -> None:
    """Run the MCP server on a transport until the connection closes.

    Reads messages from the transport, dispatches them to the server,
    and sends back responses (if any).
    """
    try:
        while True:
            message = await transport.recv()
            response = await server.handle_message(message)
            if response is not None:
                await transport.send(response)
    except (EOFError, RuntimeError, ConnectionResetError):
        pass
    finally:
        await transport.close()
