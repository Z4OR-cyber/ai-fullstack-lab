"""
MCP Client — Connect to external MCP servers and use their tools.

The :class:`MCPClient` connects to an MCP server over any transport,
performs the protocol handshake, and provides methods to:

    - List and call remote tools
    - List and read remote resources
    - List and get remote prompts

Remote tools can be adapted to Suyi's :class:`~suyi.tools.base.AgentTool`
via :class:`RemoteMCPTool`, allowing them to be used in the agent loop
just like local tools.

Usage::

    from suyi.mcp import MCPClient, MemoryTransport

    client_t, server_t = MemoryTransport.create_pair()
    client = MCPClient(client_t)
    info = await client.connect()  # handshake
    tools = await client.list_tools()
    result = await client.call_tool("search", {"query": "cats"})
    agent_tools = await client.get_tools_as_agent_tools()
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional, Union

from ..tools.base import AgentTool, ToolContext, ToolParameter, ToolResult
from .protocol import (
    PROTOCOL_VERSION,
    MCPError,
    MCPMessage,
    MCPPrompt,
    MCPResource,
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
    build_initialize_request,
    build_initialized_notification,
)
from .transport import Transport


# ═══════════════════════════════════════════════════════════════
#  Remote MCP Tool Adapter
# ═══════════════════════════════════════════════════════════════


class RemoteMCPTool(AgentTool):
    """An :class:`~suyi.tools.base.AgentTool` that wraps a remote MCP tool.

    Calls are forwarded to the MCP server via the :class:`MCPClient`.

    The ``execute`` method is synchronous (per ``AgentTool`` contract).
    If called from within a running event loop, it spawns a separate
    thread to avoid deadlock. For async contexts, use
    :meth:`execute_async` instead.
    """

    def __init__(self, mcp_tool: MCPTool, client: "MCPClient"):
        self._mcp_tool = mcp_tool
        self._client = client

    @property
    def name(self) -> str:
        return self._mcp_tool.name

    @property
    def description(self) -> str:
        return self._mcp_tool.description

    @property
    def default_permission(self) -> str:
        return "auto"

    @property
    def parameters(self) -> list[ToolParameter]:
        """Convert the MCP inputSchema to ToolParameter list."""
        schema = self._mcp_tool.inputSchema
        params: list[ToolParameter] = []
        properties = schema.get("properties", {})
        required_set = set(schema.get("required", []))
        for pname, prop in properties.items():
            params.append(
                ToolParameter(
                    name=pname,
                    type=prop.get("type", "string"),
                    description=prop.get("description", ""),
                    required=pname in required_set,
                    default=prop.get("default"),
                )
            )
        return params

    def to_schema(self) -> dict:
        """Generate tool schema from MCP tool descriptor."""
        return {
            "name": self._mcp_tool.name,
            "description": self._mcp_tool.description,
            "parameters": self._mcp_tool.inputSchema,
        }

    def execute(self, input_data: dict, context: ToolContext) -> ToolResult:
        """Execute the remote tool synchronously.

        If called from within a running event loop, spawns a separate
        thread to run the async call. Otherwise uses ``asyncio.run()``.
        """
        try:
            asyncio.get_running_loop()
            # We're inside an event loop — use a separate thread
            import concurrent.futures
            import threading

            result_box: list[Any] = []
            error_box: list[Exception] = []

            def _run():
                try:
                    new_loop = asyncio.new_event_loop()
                    try:
                        result_box.append(
                            new_loop.run_until_complete(
                                self._client.call_tool(
                                    self._mcp_tool.name, input_data
                                )
                            )
                        )
                    finally:
                        new_loop.close()
                except Exception as e:
                    error_box.append(e)

            thread = threading.Thread(target=_run)
            thread.start()
            thread.join(timeout=30)

            if error_box:
                return ToolResult(success=False, error=str(error_box[0]))
            if not result_box:
                return ToolResult(success=False, error="Tool execution timed out")
            return self._to_tool_result(result_box[0])

        except RuntimeError:
            # No running loop — safe to use asyncio.run()
            pass

        result = asyncio.run(
            self._client.call_tool(self._mcp_tool.name, input_data)
        )
        return self._to_tool_result(result)

    async def execute_async(
        self, input_data: dict, context: ToolContext
    ) -> ToolResult:
        """Execute the remote tool asynchronously."""
        result = await self._client.call_tool(self._mcp_tool.name, input_data)
        return self._to_tool_result(result)

    @staticmethod
    def _to_tool_result(result: dict) -> ToolResult:
        """Convert an MCP call result dict to a :class:`ToolResult`."""
        content = result.get("content", [])
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        text = "".join(text_parts)

        if result.get("isError"):
            return ToolResult(success=False, error=text or "Remote tool error")
        return ToolResult(success=True, output=text)

    def __repr__(self) -> str:
        return f"RemoteMCPTool(name={self.name!r})"


# ═══════════════════════════════════════════════════════════════
#  MCP Client
# ═══════════════════════════════════════════════════════════════


class MCPClient:
    """MCP Client — connects to an external MCP server.

    Performs the protocol handshake and provides methods to list/call
    tools, list/read resources, and list/get prompts.

    Args:
        transport: The transport to use for communication.
        name:      Client name (sent during handshake).
        version:   Client version.
    """

    def __init__(
        self,
        transport: Transport,
        name: str = "suyi-mcp-client",
        version: str = "1.0.0",
    ):
        self._transport = transport
        self._name = name
        self._version = version
        self._next_id: int = 1
        self._server_info: Optional[dict] = None
        self._protocol_version: Optional[str] = None
        self._initialized: bool = False

    # ── Properties ─────────────────────────────────────────────

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def server_info(self) -> Optional[dict]:
        return self._server_info

    @property
    def protocol_version(self) -> Optional[str]:
        return self._protocol_version

    # ── Internal ───────────────────────────────────────────────

    def _get_id(self) -> int:
        """Generate the next request ID."""
        id_val = self._next_id
        self._next_id += 1
        return id_val

    async def _request(
        self,
        method: str,
        params: Optional[dict] = None,
    ) -> Any:
        """Send a JSON-RPC request and wait for the response.

        Skips any notifications received while waiting for the response.
        """
        msg = MCPMessage.request(method, params, self._get_id())
        await self._transport.send(msg)

        # Wait for the response, skipping notifications
        while True:
            response = await self._transport.recv()
            if response.is_response or response.is_error:
                break
            # If it's a notification, ignore and keep waiting

        if response.is_error:
            error = response.error
            raise RuntimeError(
                f"Request '{method}' failed: "
                f"{error.code} {error.message}"
                + (f" ({error.data})" if error.data else "")
            )

        return response.result

    # ── Connection Lifecycle ───────────────────────────────────

    async def connect(self) -> dict:
        """Perform the MCP initialize handshake.

        Sends an ``initialize`` request, receives the server's response,
        and sends the ``notifications/initialized`` notification.

        Returns:
            The server's initialize response result (serverInfo, capabilities, etc.)
        """
        # Send initialize request
        init_msg = build_initialize_request(self._name, self._version)
        init_msg.id = self._get_id()
        await self._transport.send(init_msg)

        # Wait for response (skip notifications)
        while True:
            response = await self._transport.recv()
            if response.is_response or response.is_error:
                break

        if response.is_error:
            raise RuntimeError(
                f"Initialize failed: {response.error.code} {response.error.message}"
            )

        result = response.result or {}
        self._server_info = result.get("serverInfo", {})
        self._protocol_version = result.get("protocolVersion", PROTOCOL_VERSION)

        # Send initialized notification
        notification = build_initialized_notification()
        await self._transport.send(notification)

        self._initialized = True
        return result

    async def close(self) -> None:
        """Close the transport."""
        await self._transport.close()

    # ── Tool Operations ────────────────────────────────────────

    async def list_tools(self) -> list[MCPTool]:
        """Get the list of tools from the server."""
        result = await self._request(METHOD_TOOLS_LIST)
        tools_data = result.get("tools", []) if result else []
        return [MCPTool.from_dict(t) for t in tools_data]

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Call a tool on the server.

        Args:
            name:      Tool name.
            arguments: Tool arguments.

        Returns:
            The call result dict with ``content`` and ``isError`` keys.
        """
        return await self._request(
            METHOD_TOOLS_CALL, {"name": name, "arguments": arguments}
        )

    async def get_tools_as_agent_tools(self) -> list[AgentTool]:
        """Fetch remote tools and wrap them as :class:`AgentTool` instances.

        Returns a list of :class:`RemoteMCPTool` objects that can be
        registered with an :class:`~suyi.core.loop.AgentLoop`.
        """
        tools = await self.list_tools()
        return [RemoteMCPTool(t, self) for t in tools]

    # ── Resource Operations ────────────────────────────────────

    async def list_resources(self) -> list[MCPResource]:
        """Get the list of resources from the server."""
        result = await self._request(METHOD_RESOURCES_LIST)
        resources_data = result.get("resources", []) if result else []
        return [MCPResource.from_dict(r) for r in resources_data]

    async def read_resource(self, uri: str) -> dict:
        """Read a resource from the server.

        Args:
            uri: Resource URI.

        Returns:
            The resource contents dict.
        """
        return await self._request(METHOD_RESOURCES_READ, {"uri": uri})

    # ── Prompt Operations ──────────────────────────────────────

    async def list_prompts(self) -> list[MCPPrompt]:
        """Get the list of prompts from the server."""
        result = await self._request(METHOD_PROMPTS_LIST)
        prompts_data = result.get("prompts", []) if result else []
        return [MCPPrompt.from_dict(p) for p in prompts_data]

    async def get_prompt(self, name: str, arguments: Optional[dict] = None) -> dict:
        """Get a prompt from the server.

        Args:
            name:      Prompt name.
            arguments: Optional prompt arguments.

        Returns:
            The prompt result dict.
        """
        params: dict = {"name": name}
        if arguments:
            params["arguments"] = arguments
        return await self._request(METHOD_PROMPTS_GET, params)

    # ── Utility ────────────────────────────────────────────────

    async def ping(self) -> bool:
        """Ping the server. Returns True if the server responds."""
        try:
            await self._request(METHOD_PING)
            return True
        except Exception:
            return False
