"""
Suyi Streaming — Real-time streaming output handler.

Exports:
    StreamHandler:   Async-generator-based streaming processor.
    StreamChunk:     Dataclass representing a single streamed chunk.
    StreamCallbacks: Callback protocol for token / tool / complete events.

Design:
    - Wraps an :class:`~suyi.core.loop.LLMInterface` that supports
      ``chat_stream`` (e.g. :class:`~suyi.llm.OpenAIAdapter`).
    - Yields :class:`StreamChunk` objects via ``async for``.
    - Detects tool-call boundaries in the stream, pauses text output,
      executes the tool, then continues.
    - Callbacks: ``on_token``, ``on_tool_call``, ``on_complete``.

Usage::

    from suyi.streaming import StreamHandler

    handler = StreamHandler(
        llm=openai_adapter,
        tools=[search_tool],
        system_prompt="You are a helpful assistant.",
    )
    async for chunk in handler.stream("What is the weather?"):
        if chunk.type == "token":
            print(chunk.content, end="", flush=True)
        elif chunk.type == "tool_call":
            print(f"\\n[Tool: {chunk.content}]")
        elif chunk.type == "complete":
            print(f"\\n--- Done ({chunk.metadata.get('tokens', 0)} tokens) ---")
"""

from .handler import StreamHandler, StreamChunk, StreamCallbacks

__all__ = [
    "StreamHandler",
    "StreamChunk",
    "StreamCallbacks",
]
