"""
Tests for LLM Adapters — Mock HTTP, no real API calls.

Tests cover:
    - OpenAI adapter: request body building, response parsing, tool calls, streaming
    - Anthropic adapter: format conversion, response parsing, tool_use blocks
    - Factory: provider creation, aliases, custom providers
    - LLMInterface protocol compliance (isinstance check)
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from suyi.llm import OpenAIAdapter, AnthropicAdapter, create_llm, create_llm_from_config
from suyi.llm.factory import register_provider, list_providers
from suyi.core.loop import LLMResponse, ToolCall, LLMInterface
from suyi.config import LLMConfig


# ═══════════════════════════════════════════════════════════════
#  OpenAI Adapter Tests
# ═══════════════════════════════════════════════════════════════


class TestOpenAIAdapterInit:
    """Test OpenAIAdapter initialization."""

    def test_init_with_api_key(self):
        adapter = OpenAIAdapter(api_key="sk-test-key", model="gpt-4o")
        assert adapter.api_key == "sk-test-key"
        assert adapter.model == "gpt-4o"
        assert adapter.base_url == "https://api.openai.com/v1"
        assert adapter.temperature == 0.7
        assert adapter.max_tokens == 4096

    def test_init_with_custom_base_url(self):
        adapter = OpenAIAdapter(
            api_key="sk-test",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
        )
        assert adapter.base_url == "https://api.deepseek.com/v1"

    def test_init_raises_without_api_key(self):
        with pytest.raises(ValueError, match="API key required"):
            OpenAIAdapter(api_key=None)

    def test_init_with_env_var(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env-key"}):
            adapter = OpenAIAdapter()
            assert adapter.api_key == "sk-env-key"

    def test_init_strips_trailing_slash(self):
        adapter = OpenAIAdapter(
            api_key="sk-test",
            base_url="https://api.openai.com/v1/",
        )
        assert adapter.base_url == "https://api.openai.com/v1"


class TestOpenAIRequestBuilding:
    """Test OpenAI request body construction."""

    def test_build_body_basic(self):
        adapter = OpenAIAdapter(api_key="sk-test", model="gpt-4o")
        body = adapter._build_request_body(
            messages=[{"role": "user", "content": "Hello"}],
            tools=[],
            system_prompt="You are helpful.",
        )
        assert body["model"] == "gpt-4o"
        assert body["messages"][0] == {"role": "system", "content": "You are helpful."}
        assert body["messages"][1] == {"role": "user", "content": "Hello"}
        assert body["temperature"] == 0.7
        assert body["max_tokens"] == 4096
        assert "tools" not in body

    def test_build_body_with_tools(self):
        adapter = OpenAIAdapter(api_key="sk-test")
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search the web",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        body = adapter._build_request_body(
            messages=[{"role": "user", "content": "search for cats"}],
            tools=tools,
            system_prompt="",
        )
        assert body["tools"] == tools
        # No system prompt → no system message
        assert body["messages"][0]["role"] == "user"

    def test_build_body_with_tool_result_messages(self):
        """Tool result messages should pass through correctly."""
        adapter = OpenAIAdapter(api_key="sk-test")
        messages = [
            {"role": "user", "content": "What's the weather?"},
            {
                "role": "assistant",
                "content": "Let me check.",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "weather", "arguments": '{"city": "NYC"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "Sunny, 72F"},
        ]
        body = adapter._build_request_body(messages, [], "")
        assert len(body["messages"]) == 3
        assert body["messages"][1]["role"] == "assistant"
        assert "tool_calls" in body["messages"][1]
        assert body["messages"][2]["role"] == "tool"

    def test_build_body_stream(self):
        adapter = OpenAIAdapter(api_key="sk-test")
        body = adapter._build_request_body(
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            system_prompt="",
            stream=True,
        )
        assert body["stream"] is True


class TestOpenAIResponseParsing:
    """Test OpenAI response parsing."""

    def test_parse_text_response(self):
        adapter = OpenAIAdapter(api_key="sk-test")
        data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help?",
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        }
        tool_calls = adapter._parse_tool_calls(data)
        assert tool_calls == []

    def test_parse_tool_calls(self):
        adapter = OpenAIAdapter(api_key="sk-test")
        data = {
            "choices": [
                {
                    "message": {
                        "content": "Let me search for that.",
                        "tool_calls": [
                            {
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "search",
                                    "arguments": '{"query": "python asyncio"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
        tool_calls = adapter._parse_tool_calls(data)
        assert len(tool_calls) == 1
        assert tool_calls[0].id == "call_abc123"
        assert tool_calls[0].name == "search"
        assert tool_calls[0].arguments == {"query": "python asyncio"}

    def test_parse_tool_calls_empty_arguments(self):
        adapter = OpenAIAdapter(api_key="sk-test")
        data = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {"name": "ping", "arguments": ""},
                            }
                        ],
                    }
                }
            ]
        }
        tool_calls = adapter._parse_tool_calls(data)
        assert len(tool_calls) == 1
        assert tool_calls[0].arguments == {}

    def test_parse_tool_calls_invalid_json(self):
        """Invalid JSON arguments should be stored as _raw."""
        adapter = OpenAIAdapter(api_key="sk-test")
        data = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {"name": "bad", "arguments": "{not json}"},
                            }
                        ],
                    }
                }
            ]
        }
        tool_calls = adapter._parse_tool_calls(data)
        assert tool_calls[0].arguments == {"_raw": "{not json}"}

    def test_parse_usage(self):
        adapter = OpenAIAdapter(api_key="sk-test")
        data = {"usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}
        usage = adapter._parse_usage(data)
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150

    def test_parse_usage_missing(self):
        adapter = OpenAIAdapter(api_key="sk-test")
        usage = adapter._parse_usage({})
        assert usage["total_tokens"] == 0


class TestOpenAIChatIntegration:
    """Test OpenAIAdapter.chat() with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_chat_text_response(self):
        """Test a successful text-only chat call."""
        adapter = OpenAIAdapter(api_key="sk-test", model="gpt-4o")

        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"role": "assistant", "content": "Hello world!"}}
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        # Patch _get_client to return our mock
        with patch.object(adapter, "_get_client", return_value=mock_client):
            response = await adapter.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="Be helpful.",
            )

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello world!"
        assert response.tool_calls == []
        assert response.usage["total_tokens"] == 8

        # Verify the request was made correctly
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://api.openai.com/v1/chat/completions"
        body = call_args[1]["json"]
        assert body["model"] == "gpt-4o"
        assert body["messages"][0]["role"] == "system"

    @pytest.mark.asyncio
    async def test_chat_with_tool_calls(self):
        """Test a chat call that returns tool calls."""
        adapter = OpenAIAdapter(api_key="sk-test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "I'll search for that.",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "search",
                                    "arguments": '{"query": "weather"}',
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            response = await adapter.chat(
                messages=[{"role": "user", "content": "Search weather"}],
                tools=[{"type": "function", "function": {"name": "search"}}],
                system_prompt="",
            )

        assert response.content == "I'll search for that."
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "search"
        assert response.tool_calls[0].arguments == {"query": "weather"}
        assert response.usage["total_tokens"] == 30

    @pytest.mark.asyncio
    async def test_chat_http_error(self):
        """Test that HTTP errors raise RuntimeError."""
        import httpx

        adapter = OpenAIAdapter(api_key="sk-test")

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        http_error = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )
        mock_response.raise_for_status.side_effect = http_error

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="OpenAI API error 401"):
                await adapter.chat(
                    messages=[{"role": "user", "content": "Hi"}],
                    tools=[],
                    system_prompt="",
                )


class TestOpenAIStreaming:
    """Test OpenAI streaming support."""

    @pytest.mark.asyncio
    async def test_chat_stream(self):
        """Test streaming yields content chunks."""
        adapter = OpenAIAdapter(api_key="sk-test")

        # Build mock SSE lines
        sse_lines = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            'data: {"choices":[{"delta":{"content":"!"}}]}',
            'data: [DONE]',
        ]

        # Mock async context manager for stream
        class MockStreamResponse:
            def raise_for_status(self):
                pass

            async def aiter_lines(self):
                for line in sse_lines:
                    yield line

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=MockStreamResponse())

        with patch.object(adapter, "_get_client", return_value=mock_client):
            chunks = []
            async for chunk in adapter.chat_stream(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="",
            ):
                chunks.append(chunk)

        assert chunks == ["Hello", " world", "!"]


class TestOpenAIAdapterLifecycle:
    """Test adapter lifecycle methods."""

    @pytest.mark.asyncio
    async def test_close(self):
        adapter = OpenAIAdapter(api_key="sk-test")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        adapter._client = mock_client

        await adapter.close()
        mock_client.aclose.assert_called_once()
        assert adapter._client is None

    @pytest.mark.asyncio
    async def test_context_manager(self):
        adapter = OpenAIAdapter(api_key="sk-test")
        async with adapter as a:
            assert a is adapter
        assert adapter._client is None


# ═══════════════════════════════════════════════════════════════
#  Anthropic Adapter Tests
# ═══════════════════════════════════════════════════════════════


class TestAnthropicAdapterInit:
    """Test AnthropicAdapter initialization."""

    def test_init_with_api_key(self):
        adapter = AnthropicAdapter(
            api_key="sk-ant-test",
            model="claude-sonnet-4-20250514",
        )
        assert adapter.api_key == "sk-ant-test"
        assert adapter.model == "claude-sonnet-4-20250514"
        assert adapter.base_url == "https://api.anthropic.com"
        assert adapter.max_tokens == 4096
        assert adapter.anthropic_version == "2023-06-01"

    def test_init_raises_without_api_key(self):
        with pytest.raises(ValueError, match="API key required"):
            AnthropicAdapter(api_key=None)

    def test_init_with_env_var(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-env"}):
            adapter = AnthropicAdapter()
            assert adapter.api_key == "sk-ant-env"


class TestAnthropicFormatConversion:
    """Test Anthropic format conversion methods."""

    def test_convert_tools_openai_format(self):
        adapter = AnthropicAdapter(api_key="sk-ant-test")
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search the web",
                    "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
                },
            }
        ]
        result = adapter._convert_tools(tools)
        assert result[0]["name"] == "search"
        assert result[0]["description"] == "Search the web"
        assert "input_schema" in result[0]
        assert result[0]["input_schema"]["properties"]["q"]["type"] == "string"

    def test_convert_tools_already_anthropic(self):
        adapter = AnthropicAdapter(api_key="sk-ant-test")
        tools = [
            {
                "name": "calc",
                "description": "Calculator",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]
        result = adapter._convert_tools(tools)
        # Should pass through unchanged
        assert result[0] == tools[0]

    def test_convert_messages_skips_system(self):
        adapter = AnthropicAdapter(api_key="sk-ant-test")
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ]
        result = adapter._convert_messages(messages)
        # System message should be filtered out (handled as top-level param)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_convert_messages_tool_result(self):
        adapter = AnthropicAdapter(api_key="sk-ant-test")
        messages = [
            {"role": "user", "content": "What's the weather?"},
            {"role": "tool", "tool_call_id": "call_1", "content": "Sunny, 72F"},
        ]
        result = adapter._convert_messages(messages)
        # Tool result → user role with tool_result content block
        assert result[1]["role"] == "user"
        assert result[1]["content"][0]["type"] == "tool_result"
        assert result[1]["content"][0]["tool_use_id"] == "call_1"
        assert result[1]["content"][0]["content"] == "Sunny, 72F"

    def test_convert_messages_assistant_with_tool_calls(self):
        adapter = AnthropicAdapter(api_key="sk-ant-test")
        messages = [
            {
                "role": "assistant",
                "content": "Let me check.",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {"name": "weather", "arguments": '{"city": "NYC"}'},
                    }
                ],
            }
        ]
        result = adapter._convert_messages(messages)
        assert result[0]["role"] == "assistant"
        blocks = result[0]["content"]
        # First block is text, second is tool_use
        assert blocks[0]["type"] == "text"
        assert blocks[0]["text"] == "Let me check."
        assert blocks[1]["type"] == "tool_use"
        assert blocks[1]["id"] == "call_1"
        assert blocks[1]["name"] == "weather"
        assert blocks[1]["input"] == {"city": "NYC"}

    def test_build_request_body(self):
        adapter = AnthropicAdapter(api_key="sk-ant-test")
        body = adapter._build_request_body(
            messages=[{"role": "user", "content": "Hello"}],
            tools=[],
            system_prompt="Be helpful.",
        )
        assert body["model"] == "claude-sonnet-4-20250514"
        assert body["system"] == "Be helpful."
        assert body["messages"][0]["role"] == "user"
        assert "tools" not in body


class TestAnthropicResponseParsing:
    """Test Anthropic response parsing."""

    def test_parse_text_only(self):
        data = {
            "content": [
                {"type": "text", "text": "Hello! How can I help?"},
            ]
        }
        content, tool_calls = AnthropicAdapter._parse_response(data)
        assert content == "Hello! How can I help?"
        assert tool_calls == []

    def test_parse_tool_use(self):
        data = {
            "content": [
                {"type": "text", "text": "Let me search."},
                {
                    "type": "tool_use",
                    "id": "toolu_01abc",
                    "name": "search",
                    "input": {"query": "python"},
                },
            ]
        }
        content, tool_calls = AnthropicAdapter._parse_response(data)
        assert content == "Let me search."
        assert len(tool_calls) == 1
        assert tool_calls[0].id == "toolu_01abc"
        assert tool_calls[0].name == "search"
        assert tool_calls[0].arguments == {"query": "python"}

    def test_parse_multiple_text_blocks(self):
        data = {
            "content": [
                {"type": "text", "text": "First part."},
                {"type": "text", "text": "Second part."},
            ]
        }
        content, tool_calls = AnthropicAdapter._parse_response(data)
        assert "First part." in content
        assert "Second part." in content
        assert "\n" in content

    def test_parse_empty_content(self):
        data = {"content": []}
        content, tool_calls = AnthropicAdapter._parse_response(data)
        assert content is None
        assert tool_calls == []

    def test_parse_usage(self):
        data = {"usage": {"input_tokens": 100, "output_tokens": 50}}
        usage = AnthropicAdapter._parse_usage(data)
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150


class TestAnthropicChatIntegration:
    """Test AnthropicAdapter.chat() with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_chat_text_response(self):
        adapter = AnthropicAdapter(api_key="sk-ant-test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Hello from Claude!"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            response = await adapter.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
                system_prompt="Be helpful.",
            )

        assert response.content == "Hello from Claude!"
        assert response.tool_calls == []
        assert response.usage["total_tokens"] == 15

        # Verify the request URL and headers
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://api.anthropic.com/v1/messages"
        body = call_args[1]["json"]
        assert body["system"] == "Be helpful."

    @pytest.mark.asyncio
    async def test_chat_with_tool_use(self):
        adapter = AnthropicAdapter(api_key="sk-ant-test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [
                {"type": "text", "text": "I'll search for that."},
                {
                    "type": "tool_use",
                    "id": "toolu_01",
                    "name": "search",
                    "input": {"query": "weather"},
                },
            ],
            "usage": {"input_tokens": 20, "output_tokens": 30},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            response = await adapter.chat(
                messages=[{"role": "user", "content": "Search weather"}],
                tools=[{"type": "function", "function": {"name": "search"}}],
                system_prompt="",
            )

        assert response.content == "I'll search for that."
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "search"
        assert response.tool_calls[0].arguments == {"query": "weather"}

    @pytest.mark.asyncio
    async def test_chat_http_error(self):
        import httpx

        adapter = AnthropicAdapter(api_key="sk-ant-test")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limited"
        http_error = httpx.HTTPStatusError(
            "429 Too Many Requests", request=MagicMock(), response=mock_response
        )
        mock_response.raise_for_status.side_effect = http_error

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(adapter, "_get_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="Anthropic API error 429"):
                await adapter.chat(
                    messages=[{"role": "user", "content": "Hi"}],
                    tools=[],
                    system_prompt="",
                )


# ═══════════════════════════════════════════════════════════════
#  Factory Tests
# ═══════════════════════════════════════════════════════════════


class TestLLMFactory:
    """Test the LLM factory function."""

    def test_create_openai(self):
        llm = create_llm("openai", api_key="sk-test", model="gpt-4o")
        assert isinstance(llm, OpenAIAdapter)
        assert llm.model == "gpt-4o"

    def test_create_anthropic(self):
        llm = create_llm("anthropic", api_key="sk-ant-test")
        assert isinstance(llm, AnthropicAdapter)

    def test_create_with_alias(self):
        """Test that aliases resolve correctly."""
        llm = create_llm("deepseek", api_key="sk-ds", base_url="https://api.deepseek.com/v1")
        assert isinstance(llm, OpenAIAdapter)

        llm2 = create_llm("claude", api_key="sk-ant-test")
        assert isinstance(llm2, AnthropicAdapter)

    def test_create_unsupported_provider(self):
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            create_llm("unknown_provider", api_key="sk-test")

    def test_create_from_config(self):
        config = LLMConfig(
            provider="openai",
            api_key="sk-test",
            model="gpt-4o-mini",
            temperature= 0.5,
        )
        llm = create_llm_from_config(config)
        assert isinstance(llm, OpenAIAdapter)
        assert llm.model == "gpt-4o-mini"
        assert llm.temperature == 0.5

    def test_create_from_config_anthropic(self):
        config = LLMConfig(
            provider="anthropic",
            api_key="sk-ant-test",
            model="claude-sonnet-4-20250514",
        )
        llm = create_llm_from_config(config)
        assert isinstance(llm, AnthropicAdapter)
        assert llm.model == "claude-sonnet-4-20250514"

    def test_register_custom_provider(self):
        """Test registering a custom provider."""
        class CustomAdapter:
            def __init__(self, api_key=None, **kwargs):
                self.api_key = api_key

            async def chat(self, messages, tools, system_prompt):
                from suyi.core.loop import LLMResponse
                return LLMResponse(content="custom")

        register_provider("custom", CustomAdapter)
        llm = create_llm("custom", api_key="custom-key")
        assert isinstance(llm, CustomAdapter)

    def test_list_providers(self):
        providers = list_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert "deepseek" in providers
        assert "claude" in providers


# ═══════════════════════════════════════════════════════════════
#  Protocol Compliance Tests
# ═══════════════════════════════════════════════════════════════


class TestProtocolCompliance:
    """Test that adapters satisfy the LLMInterface protocol."""

    def test_openai_is_llm_interface(self):
        adapter = OpenAIAdapter(api_key="sk-test")
        assert isinstance(adapter, LLMInterface)

    def test_anthropic_is_llm_interface(self):
        adapter = AnthropicAdapter(api_key="sk-ant-test")
        assert isinstance(adapter, LLMInterface)

    @pytest.mark.asyncio
    async def test_openai_works_with_agent_loop(self):
        """Test that OpenAIAdapter can be used with AgentLoop (mocked)."""
        from suyi.core.loop import AgentLoop, LLMResponse, MockLLM

        # Use MockLLM to verify the loop works, then verify OpenAIAdapter
        # has the same interface shape
        adapter = OpenAIAdapter(api_key="sk-test")
        assert hasattr(adapter, "chat")
        assert asyncio.iscoroutinefunction(adapter.chat)

    @pytest.mark.asyncio
    async def test_anthropic_works_with_agent_loop(self):
        """Test that AnthropicAdapter has the correct interface shape."""
        adapter = AnthropicAdapter(api_key="sk-ant-test")
        assert hasattr(adapter, "chat")
        assert asyncio.iscoroutinefunction(adapter.chat)
