"""
Streaming output handler — real-time token streaming with tool-call support.

Design overview
---------------

The :class:`StreamHandler` wraps an :class:`~suyi.core.loop.LLMInterface`
and exposes an **async generator** that yields :class:`StreamChunk`
objects.  Consumers simply do::

    async for chunk in handler.stream("Hello"):
        ...

Two streaming modes are supported:

1. **Simulated streaming** (default, works with *any* LLM):
   Calls ``llm.chat()`` once per turn, then splits the returned
   ``content`` into small token-like chunks via :meth:`_chunk_text`.

2. **Real streaming** (``real_stream=True`` when the LLM exposes a
   ``chat_stream`` async generator, e.g. :class:`~suyi.llm.OpenAIAdapter`):
   Uses ``llm.chat_stream()`` for live token delivery.

In both modes the handler:

- Detects tool calls in the LLM response (via ``llm.chat``).
- Pauses text output, yields a ``tool_call`` chunk.
- Executes the tool (with retry, mirroring AgentLoop semantics).
- Yields a ``tool_result`` chunk.
- Appends results to history and continues the ReAct loop.
- Terminates with a ``complete`` chunk when no more tool calls remain.

Callbacks
~~~~~~~~~

Three optional callbacks can be registered:

- ``on_token(str)``        — called for every text token.
- ``on_tool_call(ToolCall)`` — called when a tool is invoked.
- ``on_complete(dict)``    — called with summary metadata at the end.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional, Protocol

from ..core.loop import (
    LLMInterface,
    LLMResponse,
    ToolCall,
    Tool,
    ToolResult,
)


# ═══════════════════════════════════════════════════════════════
#  Data structures
# ═══════════════════════════════════════════════════════════════


@dataclass
class StreamChunk:
    """A single chunk emitted by :meth:`StreamHandler.stream`.

    Attributes:
        type:     ``"token"``, ``"tool_call"``, ``"tool_result"``,
                  or ``"complete"``.
        content:  The chunk's text content (token text, tool name,
                  tool output, or final answer).
        metadata: Optional dict with extra info (tool arguments,
                  turn count, token count, etc.).
    """

    type: str
    content: str = ""
    metadata: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        preview = self.content[:40] + ("..." if len(self.content) > 40 else "")
        return f"StreamChunk(type={self.type!r}, content={preview!r})"


class StreamCallbacks(Protocol):
    """Optional callback protocol for streaming events."""

    on_token: Optional[Callable[[str], None]]
    on_tool_call: Optional[Callable[[ToolCall], None]]
    on_complete: Optional[Callable[[dict], None]]


# ═══════════════════════════════════════════════════════════════
#  Stream Handler
# ═══════════════════════════════════════════════════════════════


class StreamHandler:
    """
    Async-generator-based streaming output processor.

    Args:
        llm:           An object implementing :class:`LLMInterface`.
        tools:         Optional list of :class:`Tool` instances.
        system_prompt: System prompt forwarded to the LLM.
        chunk_size:    Character count per simulated token (default 5).
        max_turns:     Maximum ReAct turns before forced termination.
        real_stream:   If ``True`` and the LLM exposes ``chat_stream``,
                       use real streaming for text tokens.
        on_token:      Callback invoked for each text token.
        on_tool_call:  Callback invoked when a tool is called.
        on_complete:   Callback invoked with summary metadata at the end.
    """

    def __init__(
        self,
        llm: LLMInterface,
        tools: Optional[list[Tool]] = None,
        system_prompt: str = "",
        chunk_size: int = 5,
        max_turns: int = 10,
        real_stream: bool = False,
        on_token: Optional[Callable[[str], None]] = None,
        on_tool_call: Optional[Callable[[ToolCall], None]] = None,
        on_complete: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self.llm = llm
        self.tools: dict[str, Tool] = {t.name: t for t in (tools or [])}
        self.system_prompt = system_prompt
        self.chunk_size = max(1, chunk_size)
        self.max_turns = max(1, max_turns)
        self.real_stream = real_stream and hasattr(llm, "chat_stream")
        self.on_token = on_token
        self.on_tool_call = on_tool_call
        self.on_complete = on_complete

        self._total_tokens: int = 0
        self._turns_used: int = 0

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    async def stream(self, query: str) -> AsyncIterator[StreamChunk]:
        """
        Stream the agent's response to *query*.

        Yields :class:`StreamChunk` objects until the conversation
        completes (no more tool calls) or ``max_turns`` is reached.
        """
        history: list[dict] = [{"role": "user", "content": query}]
        self._total_tokens = 0
        self._turns_used = 0

        tool_dicts = self._build_tool_dicts()

        while self._turns_used < self.max_turns:
            self._turns_used += 1

            # ── Get LLM response ────────────────────────────────
            response = await self.llm.chat(
                messages=history,
                tools=tool_dicts,
                system_prompt=self.system_prompt,
            )
            self._total_tokens += response.total_tokens

            # ── Stream text content ─────────────────────────────
            if response.content:
                if self.real_stream and not response.tool_calls:
                    # Real streaming — only when no tool calls expected
                    async for token in self.llm.chat_stream(  # type: ignore[attr-defined]
                        messages=history,
                        tools=tool_dicts,
                        system_prompt=self.system_prompt,
                    ):
                        yield StreamChunk(type="token", content=token)
                        self._fire_token(token)
                else:
                    # Simulated streaming — chunk the text
                    for chunk in self._chunk_text(response.content):
                        yield StreamChunk(type="token", content=chunk)
                        self._fire_token(chunk)

            # ── No tool calls → conversation complete ───────────
            if not response.tool_calls:
                summary = {
                    "turns": self._turns_used,
                    "tokens": self._total_tokens,
                    "final_answer": response.content or "",
                    "stop_reason": "natural",
                }
                yield StreamChunk(
                    type="complete",
                    content=response.content or "",
                    metadata=summary,
                )
                self._fire_complete(summary)
                return

            # ── Append assistant message to history ─────────────
            assistant_msg: dict = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [tc.to_dict() for tc in response.tool_calls],
            }
            history.append(assistant_msg)

            # ── Execute tool calls ──────────────────────────────
            for tc in response.tool_calls:
                yield StreamChunk(
                    type="tool_call",
                    content=tc.name,
                    metadata={"arguments": tc.arguments, "call_id": tc.id},
                )
                self._fire_tool_call(tc)

                result = await self._execute_tool(tc)
                history.append(result.to_message())

                yield StreamChunk(
                    type="tool_result",
                    content=result.content,
                    metadata={
                        "tool": tc.name,
                        "success": result.success,
                        "attempts": result.attempts,
                    },
                )

        # ── Max turns reached ───────────────────────────────────
        summary = {
            "turns": self._turns_used,
            "tokens": self._total_tokens,
            "final_answer": "",
            "stop_reason": "max_turns",
        }
        yield StreamChunk(
            type="complete",
            content="",
            metadata=summary,
        )
        self._fire_complete(summary)

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed across all turns."""
        return self._total_tokens

    @property
    def turns_used(self) -> int:
        """Number of ReAct turns executed."""
        return self._turns_used

    # ------------------------------------------------------------------
    #  Internals
    # ------------------------------------------------------------------

    def _build_tool_dicts(self) -> list[dict]:
        """Convert registered tools to the definition format expected by the LLM."""
        result: list[dict] = []
        for tool in self.tools.values():
            td = tool.to_definition()
            result.append({
                "type": "function",
                "function": {
                    "name": td.name,
                    "description": td.description,
                    "parameters": td.parameters,
                },
            })
        return result

    def _chunk_text(self, text: str) -> list[str]:
        """Split *text* into token-sized chunks for simulated streaming."""
        if not text:
            return []
        return [
            text[i : i + self.chunk_size]
            for i in range(0, len(text), self.chunk_size)
        ]

    async def _execute_tool(self, tc: ToolCall) -> ToolResult:
        """Execute a single tool call with basic error handling."""
        tool = self.tools.get(tc.name)

        if tool is None:
            available = ", ".join(self.tools.keys()) or "none"
            return ToolResult(
                tool_call_id=tc.id,
                tool_name=tc.name,
                success=False,
                content=f"Tool '{tc.name}' is not available. Available: {available}",
            )

        # Permission check (simplified — mirror AgentLoop logic)
        permission = tool.check_permission(tc.arguments)
        if permission == "block":
            return ToolResult(
                tool_call_id=tc.id,
                tool_name=tc.name,
                success=False,
                content=f"Tool '{tc.name}' was blocked by permission policy.",
            )

        try:
            output = await tool.run(**tc.arguments)
            return ToolResult(
                tool_call_id=tc.id,
                tool_name=tc.name,
                success=True,
                content=output,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=tc.id,
                tool_name=tc.name,
                success=False,
                content=f"Tool '{tc.name}' failed: {e}",
            )

    # ── Callback dispatchers ────────────────────────────────────

    def _fire_token(self, token: str) -> None:
        if self.on_token:
            self.on_token(token)

    def _fire_tool_call(self, tc: ToolCall) -> None:
        if self.on_tool_call:
            self.on_tool_call(tc)

    def _fire_complete(self, summary: dict) -> None:
        if self.on_complete:
            self.on_complete(summary)

    def __repr__(self) -> str:
        return (
            f"StreamHandler(tools={list(self.tools.keys())}, "
            f"real_stream={self.real_stream}, "
            f"chunk_size={self.chunk_size})"
        )
