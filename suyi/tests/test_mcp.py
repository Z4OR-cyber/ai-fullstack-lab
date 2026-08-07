"""
Tests for MCP Module — Protocol, Transport, Server, and Client.

Tests cover:
    - Protocol: message serialization/deserialization, data classes, handshake helpers
    - Transport: MemoryTransport send/recv/close
    - Server: tool/resource/prompt registration, message handling, tool call
    - Client: connect handshake, list/call tools, list/read resources
    - Integration: client ↔ server via MemoryTransport

No real network I/O — all tests use MemoryTransport or direct message handling.
"""

import asyncio
import json
import pytest

from suyi.mcp import (
    # Protocol
    PROTOCOL_VERSION,
    MCPError,
    MCPMessage,
    MCPTool,
    MCPResource,
    MCPPrompt,
    METHOD_INITIALIZE,
    METHOD_INITIALIZED,
    METHOD_PING,
    METHOD_TOOLS_LIST,
    METHOD_TOOLS_CALL,
    METHOD_RESOURCES_LIST,
    METHOD_RESOURCES_READ,
    METHOD_PROMPTS_LIST,
    METHOD_PROMPTS_GET,
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
    TOOL_NOT_FOUND,
    RESOURCE_NOT_FOUND,
    PROMPT_NOT_FOUND,
    build_initialize_request,
    build_initialize_response,
    build_initialized_notification,
    reset_id_counter,
    # Transport
    Transport,
    StdioTransport,
    TCPTransport,
    MemoryTransport,
    # Server
    MCPServer,
    serve_on_transport,
    # Client
    MCPClient,
    RemoteMCPTool,
)
from suyi.tools.base import AgentTool, ToolContext, ToolParameter, ToolResult


# ═══════════════════════════════════════════════════════════════
#  Test Fixtures
# ═══════════════════════════════════════════════════════════════


class EchoTool(AgentTool):
    """Simple test tool that echoes its input."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo back the input text."

    @property
    def default_permission(self) -> str:
        return "auto"

    @property
    def parameters(self) -> list:
        return [
            ToolParameter(
                name="text",
                type="string",
                description="Text to echo.",
                required=True,
            )
        ]

    def execute(self, input_data: dict, context: ToolContext) -> ToolResult:
        text = input_data.get("text", "")
        return ToolResult(success=True, output=f"Echo: {text}")


class FailingTool(AgentTool):
    """Test tool that always fails."""

    @property
    def name(self) -> str:
        return "fail"

    @property
    def description(self) -> str:
        return "A tool that always fails."

    @property
    def default_permission(self) -> str:
        return "auto"

    def execute(self, input_data: dict, context: ToolContext) -> ToolResult:
        return ToolResult(success=False, error="Intentional failure")


@pytest.fixture(autouse=True)
def reset_ids():
    """Reset the ID counter before each test."""
    reset_id_counter()
    yield


# ═══════════════════════════════════════════════════════════════
#  Protocol Tests
# ═══════════════════════════════════════════════════════════════


class TestMCPMessage:
    """Test MCPMessage serialization and type predicates."""

    def test_request_creation(self):
        msg = MCPMessage.request("tools/list", {"cursor": "abc"}, 1)
        assert msg.is_request
        assert not msg.is_notification
        assert not msg.is_response
        assert not msg.is_error
        assert msg.method == "tools/list"
        assert msg.params == {"cursor": "abc"}
        assert msg.id == 1

    def test_notification_creation(self):
        msg = MCPMessage.notification("notifications/initialized")
        assert msg.is_notification
        assert not msg.is_request
        assert msg.method == "notifications/initialized"
        assert msg.id is None

    def test_response_creation(self):
        msg = MCPMessage.response({"tools": []}, 1)
        assert msg.is_response
        assert not msg.is_request
        assert msg.result == {"tools": []}
        assert msg.id == 1
        assert msg.method is None

    def test_error_response_creation(self):
        msg = MCPMessage.error_response(-32601, "Method not found", 1)
        assert msg.is_error
        assert not msg.is_response
        assert msg.error.code == -32601
        assert msg.error.message == "Method not found"
        assert msg.id == 1

    def test_error_response_with_data(self):
        msg = MCPMessage.error_response(-32001, "Tool not found", 1, data={"name": "foo"})
        assert msg.error.data == {"name": "foo"}

    def test_to_json_and_from_json(self):
        original = MCPMessage.request("tools/call", {"name": "echo", "arguments": {"text": "hi"}}, 42)
        json_str = original.to_json()
        restored = MCPMessage.from_json(json_str)
        assert restored.method == "tools/call"
        assert restored.params == {"name": "echo", "arguments": {"text": "hi"}}
        assert restored.id == 42
        assert restored.is_request

    def test_to_dict_and_from_dict(self):
        original = MCPMessage.error_response(-32600, "Bad request", 5)
        d = original.to_dict()
        assert d["jsonrpc"] == "2.0"
        assert d["error"]["code"] == -32600
        restored = MCPMessage.from_dict(d)
        assert restored.is_error
        assert restored.error.code == -32600

    def test_auto_id_generation(self):
        """Request without explicit ID should auto-generate one."""
        msg1 = MCPMessage.request("ping")
        msg2 = MCPMessage.request("ping")
        assert msg1.id is not None
        assert msg2.id is not None
        assert msg1.id != msg2.id  # IDs should be unique

    def test_notification_has_no_result_or_error(self):
        msg = MCPMessage.notification("test/notification", {"key": "value"})
        d = msg.to_dict()
        assert "result" not in d
        assert "error" not in d
        assert "id" not in d

    def test_response_has_no_method(self):
        msg = MCPMessage.response({"ok": True}, 1)
        d = msg.to_dict()
        assert "method" not in d

    def test_repr(self):
        msg = MCPMessage.request("ping", id=1)
        r = repr(msg)
        assert "request" in r
        assert "ping" in r


class TestMCPError:
    """Test MCPError data class."""

    def test_error_creation(self):
        err = MCPError(code=-32700, message="Parse error")
        assert err.code == -32700
        assert err.message == "Parse error"
        assert err.data is None

    def test_error_with_data(self):
        err = MCPError(code=-32001, message="Not found", data={"id": 42})
        assert err.data == {"id": 42}

    def test_to_dict_without_data(self):
        err = MCPError(code=-32600, message="Invalid")
        d = err.to_dict()
        assert "data" not in d
        assert d["code"] == -32600

    def test_to_dict_with_data(self):
        err = MCPError(code=-32600, message="Invalid", data="extra")
        d = err.to_dict()
        assert d["data"] == "extra"

    def test_from_dict(self):
        d = {"code": -32601, "message": "Not found", "data": {"key": "val"}}
        err = MCPError.from_dict(d)
        assert err.code == -32601
        assert err.message == "Not found"
        assert err.data == {"key": "val"}

    def test_from_dict_without_data(self):
        d = {"code": -32601, "message": "Not found"}
        err = MCPError.from_dict(d)
        assert err.data is None


class TestMCPTool:
    """Test MCPTool descriptor."""

    def test_tool_creation(self):
        tool = MCPTool(
            name="search",
            description="Search the web",
            inputSchema={"type": "object", "properties": {"q": {"type": "string"}}},
        )
        assert tool.name == "search"
        assert tool.description == "Search the web"
        assert tool.inputSchema["type"] == "object"

    def test_tool_defaults(self):
        tool = MCPTool(name="test")
        assert tool.description == ""
        assert tool.inputSchema == {"type": "object", "properties": {}}

    def test_tool_to_dict(self):
        tool = MCPTool(name="calc", description="Calculator", inputSchema={"type": "object"})
        d = tool.to_dict()
        assert d["name"] == "calc"
        assert d["description"] == "Calculator"
        assert d["inputSchema"] == {"type": "object"}

    def test_tool_from_dict(self):
        d = {"name": "calc", "description": "Calc", "inputSchema": {"type": "object"}}
        tool = MCPTool.from_dict(d)
        assert tool.name == "calc"
        assert tool.inputSchema == {"type": "object"}

    def test_tool_from_dict_snake_case(self):
        """Should handle input_schema (snake_case) as well."""
        d = {"name": "calc", "description": "Calc", "input_schema": {"type": "object"}}
        tool = MCPTool.from_dict(d)
        assert tool.inputSchema == {"type": "object"}


class TestMCPResource:
    """Test MCPResource descriptor."""

    def test_resource_creation(self):
        res = MCPResource(uri="file:///test.txt", name="test", description="A test file", mimeType="text/plain")
        assert res.uri == "file:///test.txt"
        assert res.name == "test"
        assert res.description == "A test file"
        assert res.mimeType == "text/plain"

    def test_resource_defaults(self):
        res = MCPResource(uri="file:///test.txt")
        assert res.name == ""
        assert res.description == ""
        assert res.mimeType == ""

    def test_resource_to_dict(self):
        res = MCPResource(uri="file:///test.txt", name="test", description="desc", mimeType="text/plain")
        d = res.to_dict()
        assert d["uri"] == "file:///test.txt"
        assert d["name"] == "test"
        assert d["description"] == "desc"
        assert d["mimeType"] == "text/plain"

    def test_resource_to_dict_omits_empty(self):
        res = MCPResource(uri="file:///test.txt", name="test")
        d = res.to_dict()
        assert "description" not in d
        assert "mimeType" not in d

    def test_resource_from_dict(self):
        d = {"uri": "file:///x", "name": "x", "description": "d", "mimeType": "text/plain"}
        res = MCPResource.from_dict(d)
        assert res.uri == "file:///x"
        assert res.mimeType == "text/plain"

    def test_resource_from_dict_snake_case(self):
        d = {"uri": "file:///x", "name": "x", "mime_type": "text/plain"}
        res = MCPResource.from_dict(d)
        assert res.mimeType == "text/plain"


class TestMCPPrompt:
    """Test MCPPrompt descriptor."""

    def test_prompt_creation(self):
        prompt = MCPPrompt(name="summarize", description="Summarize text", arguments=[{"name": "text", "type": "string"}])
        assert prompt.name == "summarize"
        assert prompt.description == "Summarize text"
        assert len(prompt.arguments) == 1

    def test_prompt_defaults(self):
        prompt = MCPPrompt(name="test")
        assert prompt.description == ""
        assert prompt.arguments == []

    def test_prompt_to_dict(self):
        prompt = MCPPrompt(name="summarize", description="Summarize", arguments=[{"name": "text"}])
        d = prompt.to_dict()
        assert d["name"] == "summarize"
        assert d["arguments"] == [{"name": "text"}]

    def test_prompt_to_dict_omits_empty_arguments(self):
        prompt = MCPPrompt(name="test", description="d")
        d = prompt.to_dict()
        assert "arguments" not in d

    def test_prompt_from_dict(self):
        d = {"name": "summarize", "description": "Summarize", "arguments": [{"name": "text"}]}
        prompt = MCPPrompt.from_dict(d)
        assert prompt.name == "summarize"
        assert len(prompt.arguments) == 1


class TestProtocolHandshake:
    """Test protocol handshake helper functions."""

    def test_build_initialize_request(self):
        msg = build_initialize_request("my-client", "2.0.0")
        assert msg.is_request
        assert msg.method == METHOD_INITIALIZE
        assert msg.params["protocolVersion"] == PROTOCOL_VERSION
        assert msg.params["clientInfo"]["name"] == "my-client"
        assert msg.params["clientInfo"]["version"] == "2.0.0"

    def test_build_initialize_response(self):
        msg = build_initialize_response("my-server", "1.0.0", 1)
        assert msg.is_response
        assert msg.id == 1
        assert msg.result["protocolVersion"] == PROTOCOL_VERSION
        assert msg.result["serverInfo"]["name"] == "my-server"
        assert "tools" in msg.result["capabilities"]

    def test_build_initialized_notification(self):
        msg = build_initialized_notification()
        assert msg.is_notification
        assert msg.method == METHOD_INITIALIZED


# ═══════════════════════════════════════════════════════════════
#  Transport Tests
# ═══════════════════════════════════════════════════════════════


class TestMemoryTransport:
    """Test MemoryTransport paired transport."""

    @pytest.mark.asyncio
    async def test_create_pair(self):
        client_t, server_t = MemoryTransport.create_pair()
        assert isinstance(client_t, Transport)
        assert isinstance(server_t, Transport)

    @pytest.mark.asyncio
    async def test_send_recv(self):
        """Messages sent on one transport are received on the other."""
        client_t, server_t = MemoryTransport.create_pair()

        msg = MCPMessage.request("ping", id=1)
        await client_t.send(msg)

        received = await server_t.recv()
        assert received.method == "ping"
        assert received.id == 1

    @pytest.mark.asyncio
    async def test_bidirectional(self):
        """Both directions work."""
        client_t, server_t = MemoryTransport.create_pair()

        # Client → Server
        req = MCPMessage.request("ping", id=1)
        await client_t.send(req)
        got = await server_t.recv()
        assert got.method == "ping"

        # Server → Client
        resp = MCPMessage.response({}, 1)
        await server_t.send(resp)
        got = await client_t.recv()
        assert got.is_response
        assert got.id == 1

    @pytest.mark.asyncio
    async def test_close(self):
        client_t, server_t = MemoryTransport.create_pair()
        await client_t.close()
        assert client_t._closed

    @pytest.mark.asyncio
    async def test_send_after_close_raises(self):
        client_t, _ = MemoryTransport.create_pair()
        await client_t.close()
        with pytest.raises(RuntimeError, match="closed"):
            await client_t.send(MCPMessage.request("ping"))

    @pytest.mark.asyncio
    async def test_multiple_messages_in_order(self):
        client_t, server_t = MemoryTransport.create_pair()

        for i in range(5):
            await client_t.send(MCPMessage.request(f"method_{i}", id=f"msg_{i}"))

        for i in range(5):
            msg = await server_t.recv()
            assert msg.method == f"method_{i}"
            assert msg.id == f"msg_{i}"


class TestTransportTypes:
    """Test that transport classes exist and have correct interface."""

    def test_stdio_transport_exists(self):
        t = StdioTransport()
        assert isinstance(t, Transport)

    def test_tcp_transport_exists(self):
        t = TCPTransport(host="localhost", port=8080)
        assert isinstance(t, Transport)
        assert t.host == "localhost"
        assert t.port == 8080

    def test_memory_transport_exists(self):
        t = MemoryTransport(asyncio.Queue(), asyncio.Queue())
        assert isinstance(t, Transport)


# ═══════════════════════════════════════════════════════════════
#  Server Tests
# ═══════════════════════════════════════════════════════════════


class TestMCPServerInit:
    """Test MCPServer initialization and registration."""

    def test_init_defaults(self):
        server = MCPServer()
        assert server.name == "suyi-mcp-server"
        assert server.version == "1.0.0"
        assert not server.is_initialized

    def test_init_custom(self):
        server = MCPServer(name="my-server", version="2.0.0")
        assert server.name == "my-server"
        assert server.version == "2.0.0"

    def test_register_tool(self):
        server = MCPServer()
        server.register_tool(EchoTool())
        assert "echo" in server.tool_names

    def test_register_resource(self):
        server = MCPServer()
        resource = MCPResource(uri="file:///test", name="test")
        server.register_resource(resource, handler=lambda: "content")
        assert "file:///test" in server.resource_uris

    def test_register_prompt(self):
        server = MCPServer()
        prompt = MCPPrompt(name="summarize", description="Summarize")
        server.register_prompt(prompt)
        assert "summarize" in server.prompt_names


class TestMCPServerHandling:
    """Test MCPServer message handling."""

    @pytest.mark.asyncio
    async def test_handle_initialize(self):
        server = MCPServer(name="test-server", version="1.0.0")
        req = MCPMessage.request(METHOD_INITIALIZE, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        }, 1)
        resp = await server.handle_message(req)
        assert resp is not None
        assert resp.is_response
        assert resp.id == 1
        assert resp.result["protocolVersion"] == PROTOCOL_VERSION
        assert resp.result["serverInfo"]["name"] == "test-server"

    @pytest.mark.asyncio
    async def test_handle_initialized_notification(self):
        server = MCPServer()
        notif = MCPMessage.notification(METHOD_INITIALIZED)
        resp = await server.handle_message(notif)
        assert resp is None  # Notifications get no response
        assert server.is_initialized

    @pytest.mark.asyncio
    async def test_handle_ping(self):
        server = MCPServer()
        req = MCPMessage.request(METHOD_PING, id=1)
        resp = await server.handle_message(req)
        assert resp is not None
        assert resp.is_response
        assert resp.id == 1

    @pytest.mark.asyncio
    async def test_handle_tools_list_empty(self):
        server = MCPServer()
        req = MCPMessage.request(METHOD_TOOLS_LIST, id=1)
        resp = await server.handle_message(req)
        assert resp.is_response
        assert resp.result["tools"] == []

    @pytest.mark.asyncio
    async def test_handle_tools_list_with_tools(self):
        server = MCPServer()
        server.register_tool(EchoTool())
        req = MCPMessage.request(METHOD_TOOLS_LIST, id=1)
        resp = await server.handle_message(req)
        tools = resp.result["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "echo"
        assert tools[0]["description"] == "Echo back the input text."
        assert "inputSchema" in tools[0]

    @pytest.mark.asyncio
    async def test_handle_tools_call_success(self):
        server = MCPServer()
        server.register_tool(EchoTool())
        req = MCPMessage.request(METHOD_TOOLS_CALL, {
            "name": "echo",
            "arguments": {"text": "hello"},
        }, 1)
        resp = await server.handle_message(req)
        assert resp.is_response
        assert resp.result["isError"] is False
        content = resp.result["content"]
        assert len(content) == 1
        assert content[0]["type"] == "text"
        assert "Echo: hello" in content[0]["text"]

    @pytest.mark.asyncio
    async def test_handle_tools_call_not_found(self):
        server = MCPServer()
        req = MCPMessage.request(METHOD_TOOLS_CALL, {
            "name": "nonexistent",
            "arguments": {},
        }, 1)
        resp = await server.handle_message(req)
        assert resp.is_error
        assert resp.error.code == TOOL_NOT_FOUND

    @pytest.mark.asyncio
    async def test_handle_tools_call_missing_name(self):
        server = MCPServer()
        req = MCPMessage.request(METHOD_TOOLS_CALL, {"arguments": {}}, 1)
        resp = await server.handle_message(req)
        assert resp.is_error
        assert resp.error.code == INVALID_PARAMS

    @pytest.mark.asyncio
    async def test_handle_tools_call_failure(self):
        server = MCPServer()
        server.register_tool(FailingTool())
        req = MCPMessage.request(METHOD_TOOLS_CALL, {
            "name": "fail",
            "arguments": {},
        }, 1)
        resp = await server.handle_message(req)
        assert resp.is_response
        assert resp.result["isError"] is True
        assert "Intentional failure" in resp.result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_handle_resources_list_empty(self):
        server = MCPServer()
        req = MCPMessage.request(METHOD_RESOURCES_LIST, id=1)
        resp = await server.handle_message(req)
        assert resp.is_response
        assert resp.result["resources"] == []

    @pytest.mark.asyncio
    async def test_handle_resources_list_with_resources(self):
        server = MCPServer()
        resource = MCPResource(uri="file:///test", name="test", description="A file", mimeType="text/plain")
        server.register_resource(resource, handler=lambda: "file content")
        req = MCPMessage.request(METHOD_RESOURCES_LIST, id=1)
        resp = await server.handle_message(req)
        resources = resp.result["resources"]
        assert len(resources) == 1
        assert resources[0]["uri"] == "file:///test"

    @pytest.mark.asyncio
    async def test_handle_resources_read(self):
        server = MCPServer()
        resource = MCPResource(uri="file:///test", name="test", mimeType="text/plain")
        server.register_resource(resource, handler=lambda: "Hello, World!")
        req = MCPMessage.request(METHOD_RESOURCES_READ, {"uri": "file:///test"}, 1)
        resp = await server.handle_message(req)
        assert resp.is_response
        contents = resp.result["contents"]
        assert len(contents) == 1
        assert contents[0]["uri"] == "file:///test"
        assert contents[0]["text"] == "Hello, World!"

    @pytest.mark.asyncio
    async def test_handle_resources_read_not_found(self):
        server = MCPServer()
        req = MCPMessage.request(METHOD_RESOURCES_READ, {"uri": "file:///nonexistent"}, 1)
        resp = await server.handle_message(req)
        assert resp.is_error
        assert resp.error.code == RESOURCE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_handle_resources_read_missing_uri(self):
        server = MCPServer()
        req = MCPMessage.request(METHOD_RESOURCES_READ, {}, 1)
        resp = await server.handle_message(req)
        assert resp.is_error
        assert resp.error.code == INVALID_PARAMS

    @pytest.mark.asyncio
    async def test_handle_prompts_list(self):
        server = MCPServer()
        prompt = MCPPrompt(name="summarize", description="Summarize text")
        server.register_prompt(prompt)
        req = MCPMessage.request(METHOD_PROMPTS_LIST, id=1)
        resp = await server.handle_message(req)
        prompts = resp.result["prompts"]
        assert len(prompts) == 1
        assert prompts[0]["name"] == "summarize"

    @pytest.mark.asyncio
    async def test_handle_prompts_get(self):
        server = MCPServer()
        prompt = MCPPrompt(name="summarize", description="Summarize text")
        server.register_prompt(prompt)
        req = MCPMessage.request(METHOD_PROMPTS_GET, {"name": "summarize"}, 1)
        resp = await server.handle_message(req)
        assert resp.is_response
        assert resp.result["description"] == "Summarize text"

    @pytest.mark.asyncio
    async def test_handle_prompts_get_not_found(self):
        server = MCPServer()
        req = MCPMessage.request(METHOD_PROMPTS_GET, {"name": "nonexistent"}, 1)
        resp = await server.handle_message(req)
        assert resp.is_error
        assert resp.error.code == PROMPT_NOT_FOUND

    @pytest.mark.asyncio
    async def test_handle_unknown_method(self):
        server = MCPServer()
        req = MCPMessage.request("unknown/method", id=1)
        resp = await server.handle_message(req)
        assert resp.is_error
        assert resp.error.code == METHOD_NOT_FOUND

    @pytest.mark.asyncio
    async def test_handle_non_request(self):
        """A response message should get an error."""
        server = MCPServer()
        msg = MCPMessage.response({"data": True}, 1)
        resp = await server.handle_message(msg)
        assert resp is not None
        assert resp.is_error
        assert resp.error.code == INVALID_REQUEST

    @pytest.mark.asyncio
    async def test_handle_tool_with_dict_output(self):
        """Test that dict output is JSON-serialized."""

        class DictTool(AgentTool):
            @property
            def name(self):
                return "dict_tool"

            @property
            def description(self):
                return "Returns a dict"

            @property
            def default_permission(self):
                return "auto"

            def execute(self, input_data, context):
                return ToolResult(success=True, output={"key": "value", "num": 42})

        server = MCPServer()
        server.register_tool(DictTool())
        req = MCPMessage.request(METHOD_TOOLS_CALL, {"name": "dict_tool", "arguments": {}}, 1)
        resp = await server.handle_message(req)
        assert resp.result["isError"] is False
        text = resp.result["content"][0]["text"]
        parsed = json.loads(text)
        assert parsed == {"key": "value", "num": 42}


# ═══════════════════════════════════════════════════════════════
#  Client Tests
# ═══════════════════════════════════════════════════════════════


class TestMCPClient:
    """Test MCPClient with MemoryTransport."""

    @pytest.mark.asyncio
    async def test_connect_handshake(self):
        """Test the initialize/initialized handshake."""
        client_t, server_t = MemoryTransport.create_pair()
        server = MCPServer(name="test-server", version="1.0.0")
        client = MCPClient(client_t, name="test-client", version="1.0.0")

        # Run server handler in background
        async def run_server():
            # Receive initialize request
            req = await server_t.recv()
            resp = await server.handle_message(req)
            await server_t.send(resp)
            # Receive initialized notification
            notif = await server_t.recv()
            await server.handle_message(notif)

        server_task = asyncio.create_task(run_server())

        result = await client.connect()
        await server_task

        assert client.is_initialized
        assert client.server_info["name"] == "test-server"
        assert client.protocol_version == PROTOCOL_VERSION
        assert result["serverInfo"]["name"] == "test-server"

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test listing tools through the client."""
        client_t, server_t = MemoryTransport.create_pair()
        server = MCPServer(name="test", version="1.0")
        server.register_tool(EchoTool())
        client = MCPClient(client_t)

        # Simulate server response
        async def server_handler():
            req = await server_t.recv()
            resp = await server.handle_message(req)
            await server_t.send(resp)

        task = asyncio.create_task(server_handler())
        tools = await client.list_tools()
        await task

        assert len(tools) == 1
        assert tools[0].name == "echo"
        assert tools[0].description == "Echo back the input text."

    @pytest.mark.asyncio
    async def test_call_tool(self):
        """Test calling a tool through the client."""
        client_t, server_t = MemoryTransport.create_pair()
        server = MCPServer(name="test", version="1.0")
        server.register_tool(EchoTool())
        client = MCPClient(client_t)

        async def server_handler():
            req = await server_t.recv()
            resp = await server.handle_message(req)
            await server_t.send(resp)

        task = asyncio.create_task(server_handler())
        result = await client.call_tool("echo", {"text": "world"})
        await task

        assert result["isError"] is False
        assert "Echo: world" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_call_tool_error(self):
        """Test calling a non-existent tool returns an error."""
        client_t, server_t = MemoryTransport.create_pair()
        server = MCPServer(name="test", version="1.0")
        client = MCPClient(client_t)

        async def server_handler():
            req = await server_t.recv()
            resp = await server.handle_message(req)
            await server_t.send(resp)

        task = asyncio.create_task(server_handler())

        with pytest.raises(RuntimeError, match="failed"):
            await client.call_tool("nonexistent", {})
        await task

    @pytest.mark.asyncio
    async def test_list_resources(self):
        """Test listing resources through the client."""
        client_t, server_t = MemoryTransport.create_pair()
        server = MCPServer(name="test", version="1.0")
        server.register_resource(
            MCPResource(uri="file:///data", name="data", description="Data file", mimeType="application/json"),
            handler=lambda: '{"key": "value"}',
        )
        client = MCPClient(client_t)

        async def server_handler():
            req = await server_t.recv()
            resp = await server.handle_message(req)
            await server_t.send(resp)

        task = asyncio.create_task(server_handler())
        resources = await client.list_resources()
        await task

        assert len(resources) == 1
        assert resources[0].uri == "file:///data"
        assert resources[0].name == "data"

    @pytest.mark.asyncio
    async def test_read_resource(self):
        """Test reading a resource through the client."""
        client_t, server_t = MemoryTransport.create_pair()
        server = MCPServer(name="test", version="1.0")
        server.register_resource(
            MCPResource(uri="file:///data", name="data", mimeType="application/json"),
            handler=lambda: '{"key": "value"}',
        )
        client = MCPClient(client_t)

        async def server_handler():
            req = await server_t.recv()
            resp = await server.handle_message(req)
            await server_t.send(resp)

        task = asyncio.create_task(server_handler())
        result = await client.read_resource("file:///data")
        await task

        contents = result["contents"]
        assert len(contents) == 1
        assert contents[0]["uri"] == "file:///data"
        assert contents[0]["text"] == '{"key": "value"}'

    @pytest.mark.asyncio
    async def test_list_prompts(self):
        """Test listing prompts through the client."""
        client_t, server_t = MemoryTransport.create_pair()
        server = MCPServer(name="test", version="1.0")
        server.register_prompt(MCPPrompt(name="summarize", description="Summarize text"))
        client = MCPClient(client_t)

        async def server_handler():
            req = await server_t.recv()
            resp = await server.handle_message(req)
            await server_t.send(resp)

        task = asyncio.create_task(server_handler())
        prompts = await client.list_prompts()
        await task

        assert len(prompts) == 1
        assert prompts[0].name == "summarize"

    @pytest.mark.asyncio
    async def test_ping(self):
        """Test pinging the server."""
        client_t, server_t = MemoryTransport.create_pair()
        server = MCPServer(name="test", version="1.0")
        client = MCPClient(client_t)

        async def server_handler():
            req = await server_t.recv()
            resp = await server.handle_message(req)
            await server_t.send(resp)

        task = asyncio.create_task(server_handler())
        result = await client.ping()
        await task

        assert result is True

    @pytest.mark.asyncio
    async def test_get_tools_as_agent_tools(self):
        """Test getting remote tools as AgentTool instances."""
        client_t, server_t = MemoryTransport.create_pair()
        server = MCPServer(name="test", version="1.0")
        server.register_tool(EchoTool())
        client = MCPClient(client_t)

        async def server_handler():
            req = await server_t.recv()
            resp = await server.handle_message(req)
            await server_t.send(resp)

        task = asyncio.create_task(server_handler())
        agent_tools = await client.get_tools_as_agent_tools()
        await task

        assert len(agent_tools) == 1
        assert isinstance(agent_tools[0], RemoteMCPTool)
        assert agent_tools[0].name == "echo"


# ═══════════════════════════════════════════════════════════════
#  RemoteMCPTool Tests
# ═══════════════════════════════════════════════════════════════


class TestRemoteMCPTool:
    """Test the RemoteMCPTool adapter."""

    def test_tool_properties(self):
        """Test that RemoteMCPTool exposes the MCP tool's properties."""
        mcp_tool = MCPTool(
            name="search",
            description="Search the web",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        )
        # Client not needed for property tests
        tool = RemoteMCPTool(mcp_tool, client=None)
        assert tool.name == "search"
        assert tool.description == "Search the web"
        assert tool.default_permission == "auto"

    def test_tool_parameters(self):
        """Test parameter conversion from inputSchema."""
        mcp_tool = MCPTool(
            name="search",
            description="Search",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query"},
                    "limit": {"type": "integer", "description": "Max results"},
                },
                "required": ["query"],
            },
        )
        tool = RemoteMCPTool(mcp_tool, client=None)
        params = tool.parameters
        assert len(params) == 2
        query_param = next(p for p in params if p.name == "query")
        assert query_param.required is True
        limit_param = next(p for p in params if p.name == "limit")
        assert limit_param.required is False

    def test_tool_to_schema(self):
        """Test schema generation."""
        mcp_tool = MCPTool(
            name="calc",
            description="Calculator",
            inputSchema={"type": "object", "properties": {"expr": {"type": "string"}}},
        )
        tool = RemoteMCPTool(mcp_tool, client=None)
        schema = tool.to_schema()
        assert schema["name"] == "calc"
        assert schema["description"] == "Calculator"
        assert schema["parameters"] == mcp_tool.inputSchema

    @pytest.mark.asyncio
    async def test_execute_async(self):
        """Test async execution of a remote tool."""
        client_t, server_t = MemoryTransport.create_pair()
        server = MCPServer(name="test", version="1.0")
        server.register_tool(EchoTool())
        client = MCPClient(client_t)

        mcp_tool = MCPTool(name="echo", description="Echo", inputSchema={"type": "object", "properties": {}})
        tool = RemoteMCPTool(mcp_tool, client)

        async def server_handler():
            req = await server_t.recv()
            resp = await server.handle_message(req)
            await server_t.send(resp)

        task = asyncio.create_task(server_handler())
        result = await tool.execute_async({"text": "hello"}, ToolContext())
        await task

        assert result.success
        assert "Echo: hello" in result.output

    @pytest.mark.asyncio
    async def test_execute_async_error(self):
        """Test async execution when the remote tool fails."""
        client_t, server_t = MemoryTransport.create_pair()
        server = MCPServer(name="test", version="1.0")
        server.register_tool(FailingTool())
        client = MCPClient(client_t)

        mcp_tool = MCPTool(name="fail", description="Fail", inputSchema={"type": "object", "properties": {}})
        tool = RemoteMCPTool(mcp_tool, client)

        async def server_handler():
            req = await server_t.recv()
            resp = await server.handle_message(req)
            await server_t.send(resp)

        task = asyncio.create_task(server_handler())
        result = await tool.execute_async({}, ToolContext())
        await task

        assert not result.success
        assert "Intentional failure" in result.error

    def test_result_to_tool_result_success(self):
        """Test conversion of MCP result to ToolResult."""
        mcp_result = {
            "content": [{"type": "text", "text": "Hello"}],
            "isError": False,
        }
        tr = RemoteMCPTool._to_tool_result(mcp_result)
        assert tr.success
        assert tr.output == "Hello"

    def test_result_to_tool_result_error(self):
        """Test conversion of error MCP result to ToolResult."""
        mcp_result = {
            "content": [{"type": "text", "text": "Something went wrong"}],
            "isError": True,
        }
        tr = RemoteMCPTool._to_tool_result(mcp_result)
        assert not tr.success
        assert "Something went wrong" in tr.error

    def test_result_to_tool_result_multiple_content(self):
        """Test merging multiple text content blocks."""
        mcp_result = {
            "content": [
                {"type": "text", "text": "Part 1. "},
                {"type": "text", "text": "Part 2."},
            ],
            "isError": False,
        }
        tr = RemoteMCPTool._to_tool_result(mcp_result)
        assert tr.output == "Part 1. Part 2."


# ═══════════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestMCPIntegration:
    """Full client ↔ server integration tests via MemoryTransport."""

    @pytest.mark.asyncio
    async def test_full_handshake_and_tool_call(self):
        """Test complete flow: handshake → list tools → call tool."""
        client_t, server_t = MemoryTransport.create_pair()

        server = MCPServer(name="integration-server", version="1.0.0")
        server.register_tool(EchoTool())

        client = MCPClient(client_t, name="integration-client")

        # Server background handler
        async def server_loop():
            try:
                while True:
                    msg = await server_t.recv()
                    resp = await server.handle_message(msg)
                    if resp is not None:
                        await server_t.send(resp)
            except (EOFError, RuntimeError):
                pass

        server_task = asyncio.create_task(server_loop())

        # 1. Handshake
        info = await client.connect()
        assert info["serverInfo"]["name"] == "integration-server"

        # 2. List tools
        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "echo"

        # 3. Call tool
        result = await client.call_tool("echo", {"text": "integration test"})
        assert result["isError"] is False
        assert "Echo: integration test" in result["content"][0]["text"]

        # Cleanup
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_full_handshake_and_resources(self):
        """Test complete flow: handshake → list resources → read resource."""
        client_t, server_t = MemoryTransport.create_pair()

        server = MCPServer(name="res-server", version="1.0.0")
        server.register_resource(
            MCPResource(uri="config://app", name="app_config", description="App config", mimeType="application/json"),
            handler=lambda: '{"debug": true}',
        )

        client = MCPClient(client_t)

        async def server_loop():
            try:
                while True:
                    msg = await server_t.recv()
                    resp = await server.handle_message(msg)
                    if resp is not None:
                        await server_t.send(resp)
            except (EOFError, RuntimeError):
                pass

        server_task = asyncio.create_task(server_loop())

        await client.connect()

        resources = await client.list_resources()
        assert len(resources) == 1
        assert resources[0].uri == "config://app"

        content = await client.read_resource("config://app")
        assert content["contents"][0]["text"] == '{"debug": true}'

        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_client_skips_notifications(self):
        """Test that the client skips notifications while waiting for responses."""
        client_t, server_t = MemoryTransport.create_pair()

        server = MCPServer(name="test", version="1.0")
        client = MCPClient(client_t)

        # Server sends a notification before the response
        async def server_handler():
            # Send a random notification first
            notif = MCPMessage.notification("some/notification", {"data": 1})
            await server_t.send(notif)
            # Then process the actual request
            req = await server_t.recv()
            resp = await server.handle_message(req)
            await server_t.send(resp)

        task = asyncio.create_task(server_handler())

        # Client should skip the notification and get the response
        result = await client.ping()
        assert result is True
        await task

    @pytest.mark.asyncio
    async def test_serve_on_transport(self):
        """Test the serve_on_transport helper function."""
        client_t, server_t = MemoryTransport.create_pair()

        server = MCPServer(name="serve-test", version="1.0")
        server.register_tool(EchoTool())

        # Start server in background
        server_task = asyncio.create_task(serve_on_transport(server, server_t))

        client = MCPClient(client_t)

        # Initialize
        await client.connect()

        # List tools
        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "echo"

        # Call tool
        result = await client.call_tool("echo", {"text": "serve test"})
        assert "Echo: serve test" in result["content"][0]["text"]

        # Close client transport to end server loop
        await client_t.close()
        try:
            await asyncio.wait_for(server_task, timeout=2)
        except (asyncio.TimeoutError, RuntimeError):
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
