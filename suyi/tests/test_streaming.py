"""
Tests for Suyi Streaming — real-time streaming output handler.

Covers:
    - StreamChunk dataclass
    - Simulated streaming (text chunking)
    - Tool call detection and execution
    - Multi-turn ReAct streaming
    - Callbacks (on_token, on_tool_call, on_complete)
    - Max turns termination
    - Error handling (tool not found, tool failure)
"""

import asyncio

import pytest

from suyi.core.loop import (
    LLMResponse,
    MockLLM,
    ToolCall,
    FunctionTool,
)
from suyi.streaming import (
    StreamHandler,
    StreamChunk,
    StreamCallbacks,
)


# ═══════════════════════════════════════════════════════════════
#  StreamChunk tests
# ═══════════════════════════════════════════════════════════════


class TestStreamChunk:
    """Test the StreamChunk dataclass."""

    def test_defaults(self):
        chunk = StreamChunk(type="token")
        assert chunk.type == "token"
        assert chunk.content == ""
        assert chunk.metadata == {}

    def test_with_values(self):
        chunk = StreamChunk(
            type="tool_call",
            content="search",
            metadata={"query": "weather"},
        )
        assert chunk.type == "tool_call"
        assert chunk.content == "search"
        assert chunk.metadata == {"query": "weather"}

    def test_repr(self):
        chunk = StreamChunk(type="token", content="This is a very long token text that exceeds the preview limit")
        r = repr(chunk)
        assert "token" in r
        assert "..." in r  # truncated preview

    def test_repr_short_content(self):
        chunk = StreamChunk(type="complete", content="done")
        r = repr(chunk)
        assert "complete" in r
        assert "done" in r


# ═══════════════════════════════════════════════════════════════
#  Basic streaming tests
# ═══════════════════════════════════════════════════════════════


class TestStreamBasic:
    """Test basic streaming without tools."""

    @pytest.mark.asyncio
    async def test_simple_text_stream(self):
        """MockLLM returns a text response — should yield token chunks + complete."""
        llm = MockLLM([LLMResponse.text("Hello, world!")])
        handler = StreamHandler(llm=llm, chunk_size=5)

        chunks = []
        async for chunk in handler.stream("Hi"):
            chunks.append(chunk)

        # Should have token chunks + 1 complete chunk
        token_chunks = [c for c in chunks if c.type == "token"]
        complete_chunks = [c for c in chunks if c.type == "complete"]

        assert len(token_chunks) > 0
        assert len(complete_chunks) == 1

        # Verify the assembled text
        full_text = "".join(c.content for c in token_chunks)
        assert full_text == "Hello, world!"

    @pytest.mark.asyncio
    async def test_chunk_size(self):
        """Verify that chunk_size controls token size."""
        llm = MockLLM([LLMResponse.text("ABCDEFGHIJ")])  # 10 chars
        handler = StreamHandler(llm=llm, chunk_size=3)

        chunks = []
        async for chunk in handler.stream("test"):
            chunks.append(chunk)

        token_chunks = [c for c in chunks if c.type == "token"]
        # 10 chars / 3 = 4 chunks (3+3+3+1)
        assert len(token_chunks) == 4
        assert token_chunks[0].content == "ABC"
        assert token_chunks[1].content == "DEF"
        assert token_chunks[2].content == "GHI"
        assert token_chunks[3].content == "J"

    @pytest.mark.asyncio
    async def test_complete_chunk_metadata(self):
        """Verify complete chunk has correct metadata."""
        llm = MockLLM([LLMResponse.text("Done", tokens=42)])
        handler = StreamHandler(llm=llm)

        chunks = []
        async for chunk in handler.stream("test"):
            chunks.append(chunk)

        complete = [c for c in chunks if c.type == "complete"][0]
        assert complete.metadata["stop_reason"] == "natural"
        assert complete.metadata["turns"] == 1
        assert complete.metadata["tokens"] == 42
        assert complete.metadata["final_answer"] == "Done"

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """LLM returns empty content — should still yield complete."""
        llm = MockLLM([LLMResponse(content=None, tool_calls=[])])
        handler = StreamHandler(llm=llm)

        chunks = []
        async for chunk in handler.stream("test"):
            chunks.append(chunk)

        token_chunks = [c for c in chunks if c.type == "token"]
        complete_chunks = [c for c in chunks if c.type == "complete"]

        assert len(token_chunks) == 0
        assert len(complete_chunks) == 1
        assert complete_chunks[0].content == ""


# ═══════════════════════════════════════════════════════════════
#  Tool call streaming tests
# ═══════════════════════════════════════════════════════════════


class TestStreamToolCalls:
    """Test streaming with tool calls."""

    @pytest.mark.asyncio
    async def test_single_tool_call(self):
        """LLM calls a tool, then gives final answer."""
        def echo(**kwargs):
            return kwargs.get("text", "")

        echo_tool = FunctionTool("echo", "Echo tool", echo)

        llm = MockLLM([
            LLMResponse.action("echo", {"text": "hello"}, content="Let me echo that."),
            LLMResponse.text("Echoed: hello"),
        ])

        handler = StreamHandler(llm=llm, tools=[echo_tool])

        chunks = []
        async for chunk in handler.stream("echo hello"):
            chunks.append(chunk)

        types = [c.type for c in chunks]

        # Should have: tokens, tool_call, tool_result, tokens, complete
        assert "tool_call" in types
        assert "tool_result" in types
        assert "complete" in types

        # Verify tool call chunk
        tool_call_chunk = [c for c in chunks if c.type == "tool_call"][0]
        assert tool_call_chunk.content == "echo"
        assert tool_call_chunk.metadata["arguments"] == {"text": "hello"}

        # Verify tool result chunk
        tool_result_chunk = [c for c in chunks if c.type == "tool_result"][0]
        assert tool_result_chunk.content == "hello"
        assert tool_result_chunk.metadata["success"] is True

        # Verify final answer
        complete_chunk = [c for c in chunks if c.type == "complete"][0]
        assert complete_chunk.content == "Echoed: hello"
        assert complete_chunk.metadata["turns"] == 2

    @pytest.mark.asyncio
    async def test_tool_not_found(self):
        """LLM calls a non-existent tool — should yield error result."""
        llm = MockLLM([
            LLMResponse.action("nonexistent", {"x": 1}),
            LLMResponse.text("OK"),
        ])

        handler = StreamHandler(llm=llm, tools=[])

        chunks = []
        async for chunk in handler.stream("test"):
            chunks.append(chunk)

        tool_result = [c for c in chunks if c.type == "tool_result"][0]
        assert tool_result_chunk_success_false(chunks)
        assert "not available" in tool_result.content

    @pytest.mark.asyncio
    async def test_tool_failure(self):
        """Tool raises an exception — should yield error result."""
        def failing(**kwargs):
            raise RuntimeError("boom")

        fail_tool = FunctionTool("fail", "Always fails", failing)

        llm = MockLLM([
            LLMResponse.action("fail", {}),
            LLMResponse.text("Recovered"),
        ])

        handler = StreamHandler(llm=llm, tools=[fail_tool])

        chunks = []
        async for chunk in handler.stream("test"):
            chunks.append(chunk)

        tool_result = [c for c in chunks if c.type == "tool_result"][0]
        assert tool_result.metadata["success"] is False
        assert "boom" in tool_result.content

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_one_turn(self):
        """LLM requests multiple tools in a single turn."""
        def add(**kwargs):
            return str(kwargs.get("a", 0) + kwargs.get("b", 0))

        add_tool = FunctionTool("add", "Add numbers", add)

        llm = MockLLM([
            LLMResponse.actions(
                ("add", {"a": 1, "b": 2}),
                ("add", {"a": 3, "b": 4}),
                content="Adding two pairs",
            ),
            LLMResponse.text("Results: 3 and 7"),
        ])

        handler = StreamHandler(llm=llm, tools=[add_tool])

        chunks = []
        async for chunk in handler.stream("add"):
            chunks.append(chunk)

        tool_calls = [c for c in chunks if c.type == "tool_call"]
        tool_results = [c for c in chunks if c.type == "tool_result"]

        assert len(tool_calls) == 2
        assert len(tool_results) == 2
        assert tool_results[0].content == "3"
        assert tool_results[1].content == "7"

    @pytest.mark.asyncio
    async def test_multi_turn_react(self):
        """Multiple turns of thought → action → observation → answer."""
        def search(**kwargs):
            return f"Found: {kwargs.get('query', '')}"

        search_tool = FunctionTool("search", "Search", search)

        llm = MockLLM([
            LLMResponse.action("search", {"query": "python"}, content="Searching..."),
            LLMResponse.action("search", {"query": "asyncio"}, content="Searching more..."),
            LLMResponse.text("Done searching!"),
        ])

        handler = StreamHandler(llm=llm, tools=[search_tool])

        chunks = []
        async for chunk in handler.stream("search"):
            chunks.append(chunk)

        complete = [c for c in chunks if c.type == "complete"][0]
        assert complete.metadata["turns"] == 3
        assert complete.metadata["stop_reason"] == "natural"


def tool_result_chunk_success_false(chunks):
    """Helper: check if any tool_result chunk has success=False."""
    for c in chunks:
        if c.type == "tool_result" and c.metadata.get("success") is False:
            return True
    return False


# ═══════════════════════════════════════════════════════════════
#  Callback tests
# ═══════════════════════════════════════════════════════════════


class TestStreamCallbacks:
    """Test callback invocation."""

    @pytest.mark.asyncio
    async def test_on_token_callback(self):
        llm = MockLLM([LLMResponse.text("Hello!")])
        tokens = []
        handler = StreamHandler(llm=llm, chunk_size=2, on_token=lambda t: tokens.append(t))

        async for _ in handler.stream("test"):
            pass

        assert len(tokens) > 0
        assert "".join(tokens) == "Hello!"

    @pytest.mark.asyncio
    async def test_on_tool_call_callback(self):
        def echo(**kwargs):
            return kwargs.get("text", "")

        echo_tool = FunctionTool("echo", "Echo", echo)
        tool_calls_received = []

        llm = MockLLM([
            LLMResponse.action("echo", {"text": "hi"}),
            LLMResponse.text("Done"),
        ])

        handler = StreamHandler(
            llm=llm,
            tools=[echo_tool],
            on_tool_call=lambda tc: tool_calls_received.append(tc),
        )

        async for _ in handler.stream("test"):
            pass

        assert len(tool_calls_received) == 1
        assert tool_calls_received[0].name == "echo"
        assert tool_calls_received[0].arguments == {"text": "hi"}

    @pytest.mark.asyncio
    async def test_on_complete_callback(self):
        llm = MockLLM([LLMResponse.text("Finished", tokens=99)])
        complete_data = []
        handler = StreamHandler(
            llm=llm,
            on_complete=lambda s: complete_data.append(s),
        )

        async for _ in handler.stream("test"):
            pass

        assert len(complete_data) == 1
        assert complete_data[0]["tokens"] == 99
        assert complete_data[0]["stop_reason"] == "natural"

    @pytest.mark.asyncio
    async def test_all_callbacks_together(self):
        def echo(**kwargs):
            return kwargs.get("text", "")

        echo_tool = FunctionTool("echo", "Echo", echo)
        events = []

        llm = MockLLM([
            LLMResponse.action("echo", {"text": "cb"}, content="Calling echo"),
            LLMResponse.text("All done", tokens=10),
        ])

        handler = StreamHandler(
            llm=llm,
            tools=[echo_tool],
            on_token=lambda t: events.append(("token", t)),
            on_tool_call=lambda tc: events.append(("tool_call", tc.name)),
            on_complete=lambda s: events.append(("complete", s["stop_reason"])),
        )

        async for _ in handler.stream("test"):
            pass

        event_types = [e[0] for e in events]
        assert "token" in event_types
        assert "tool_call" in event_types
        assert "complete" in event_types

        # tool_call should come after initial tokens, before final tokens
        first_tool_idx = event_types.index("tool_call")
        last_token_before = max(
            i for i, t in enumerate(event_types) if t == "token" and i < first_tool_idx
        ) if any(t == "token" and i < first_tool_idx for i, t in enumerate(event_types)) else -1

        # complete should be last
        assert event_types[-1] == "complete"


# ═══════════════════════════════════════════════════════════════
#  Edge case tests
# ═══════════════════════════════════════════════════════════════


class TestStreamEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_max_turns(self):
        """Handler should stop after max_turns even if LLM keeps calling tools."""
        def echo(**kwargs):
            return "ok"

        echo_tool = FunctionTool("echo", "Echo", echo)

        # LLM always calls a tool, never gives a final answer
        llm = MockLLM([
            LLMResponse.action("echo", {}),
            LLMResponse.action("echo", {}),
            LLMResponse.action("echo", {}),
            LLMResponse.text("This shouldn't be reached"),
        ])

        handler = StreamHandler(llm=llm, tools=[echo_tool], max_turns=2)

        chunks = []
        async for chunk in handler.stream("test"):
            chunks.append(chunk)

        complete = [c for c in chunks if c.type == "complete"][0]
        assert complete.metadata["stop_reason"] == "max_turns"
        assert complete.metadata["turns"] == 2

    @pytest.mark.asyncio
    async def test_blocked_tool(self):
        """Tool with 'block' permission should not execute."""
        def dangerous(**kwargs):
            return "should not see this"

        dangerous_tool = FunctionTool(
            "dangerous", "Dangerous tool", dangerous,
            default_permission="block",
        )

        llm = MockLLM([
            LLMResponse.action("dangerous", {}),
            LLMResponse.text("OK"),
        ])

        handler = StreamHandler(llm=llm, tools=[dangerous_tool])

        chunks = []
        async for chunk in handler.stream("test"):
            chunks.append(chunk)

        tool_result = [c for c in chunks if c.type == "tool_result"][0]
        assert tool_result.metadata["success"] is False
        assert "blocked" in tool_result.content

    @pytest.mark.asyncio
    async def test_handler_properties(self):
        """Test total_tokens and turns_used properties."""
        llm = MockLLM([
            LLMResponse.text("answer", tokens=77),
        ])

        handler = StreamHandler(llm=llm)

        async for _ in handler.stream("test"):
            pass

        assert handler.total_tokens == 77
        assert handler.turns_used == 1

    @pytest.mark.asyncio
    async def test_real_stream_fallback(self):
        """When real_stream=True but LLM lacks chat_stream, should fall back to simulated."""
        llm = MockLLM([LLMResponse.text("Fallback works")])
        handler = StreamHandler(llm=llm, real_stream=True)

        # real_stream should be False because MockLLM doesn't have chat_stream
        assert handler.real_stream is False

        chunks = []
        async for chunk in handler.stream("test"):
            chunks.append(chunk)

        token_chunks = [c for c in chunks if c.type == "token"]
        assert len(token_chunks) > 0
        assert "".join(c.content for c in token_chunks) == "Fallback works"

    @pytest.mark.asyncio
    async def test_no_tools_registered(self):
        """Handler with no tools should work fine for text-only responses."""
        llm = MockLLM([LLMResponse.text("No tools needed")])
        handler = StreamHandler(llm=llm, tools=None)

        chunks = []
        async for chunk in handler.stream("test"):
            chunks.append(chunk)

        types = [c.type for c in chunks]
        assert "tool_call" not in types
        assert "complete" in types

    @pytest.mark.asyncio
    async def test_repr(self):
        llm = MockLLM()
        handler = StreamHandler(llm=llm, chunk_size=10)
        r = repr(handler)
        assert "StreamHandler" in r
        assert "chunk_size=10" in r
