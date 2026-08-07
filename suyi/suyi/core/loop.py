"""
Agent Loop — ReAct cycle with budget management, tool execution, and middleware.

    ┌──────────────────────────────────────────────────┐
    │  while True:                                       │
    │    ① Budget check (loop top — single chokepoint)   │
    │    ② Assemble context (4 layers, cache-friendly)   │
    │    ③ Middleware: before_llm_call                   │
    │    ④ Call LLM (injectable interface)               │
    │    ⑤ Middleware: after_llm_call                    │
    │    ⑥ Record budget usage                           │
    │    ⑦ No tool calls? → return Final Answer          │
    │    ⑧ Execute tools (permission + retry, parallel)  │
    │    ⑨ Append results to history                     │
    └──────────────────────────────────────────────────┘

Key features:
    - Pure Python + asyncio (no external dependencies)
    - Injectable LLM interface (MockLLM for no-API testing)
    - Parallel tool calls with failure isolation (asyncio.gather + return_exceptions)
    - Middleware hooks at 4 points in the cycle
    - Tool execution retry (max 2 retries, error fed back to model)
    - Interrupt and resume support
    - Budget exhaustion returns partial results with explanation
    - Stream-parse optimization: permission pre-check on tool name recognition
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol, runtime_checkable, Awaitable

from .budget import BudgetTracker, BudgetStatus, BudgetLevel, BudgetConfig
from .context import (
    ContextAssembler,
    AssembledContext,
    ToolDefinition,
    MemoryBackend,
)


# ═══════════════════════════════════════════════════════════════
#  LLM Interface (Injectable)
# ═══════════════════════════════════════════════════════════════


@dataclass
class ToolCall:
    """A tool call requested by the LLM."""

    id: str
    name: str
    arguments: dict

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.arguments,
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ToolCall":
        fn = d.get("function", d)
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            name=fn.get("name", ""),
            arguments=fn.get("arguments", {}),
        )


@dataclass
class LLMResponse:
    """
    Response from the LLM — may contain text content and/or tool calls.

    In the ReAct pattern:
        content     = Thought (reasoning text)
        tool_calls  = Actions (tools to execute)
    When tool_calls is empty, content is the Final Answer.
    """

    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)

    # ── Convenience constructors for testing ──────────────────

    @staticmethod
    def text(content: str, tokens: int = 50) -> "LLMResponse":
        """Create a text-only response (no tool calls → Final Answer)."""
        return LLMResponse(
            content=content,
            tool_calls=[],
            usage={
                "prompt_tokens": 0,
                "completion_tokens": tokens,
                "total_tokens": tokens,
            },
        )

    @staticmethod
    def action(
        name: str,
        arguments: Optional[dict] = None,
        content: Optional[str] = None,
        call_id: Optional[str] = None,
        tokens: int = 50,
    ) -> "LLMResponse":
        """Create a response with a single tool call (Thought + Action)."""
        return LLMResponse(
            content=content,
            tool_calls=[
                ToolCall(
                    id=call_id or f"call_{name}_{uuid.uuid4().hex[:8]}",
                    name=name,
                    arguments=arguments or {},
                )
            ],
            usage={
                "prompt_tokens": 0,
                "completion_tokens": tokens,
                "total_tokens": tokens,
            },
        )

    @staticmethod
    def actions(
        *calls: tuple[str, dict],
        content: Optional[str] = None,
        tokens: int = 80,
    ) -> "LLMResponse":
        """
        Create a response with multiple parallel tool calls.
        Each call is a (name, arguments) tuple.
        """
        tool_calls = [
            ToolCall(
                id=f"call_{name}_{uuid.uuid4().hex[:8]}",
                name=name,
                arguments=arguments,
            )
            for name, arguments in calls
        ]
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": 0,
                "completion_tokens": tokens,
                "total_tokens": tokens,
            },
        )


@runtime_checkable
class LLMInterface(Protocol):
    """
    Injectable LLM interface — any callable matching this protocol works.

    async def chat(self, messages, tools, system_prompt) -> LLMResponse

    This decouples the loop from any specific model provider.
    """

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> LLMResponse:
        ...


class MockLLM:
    """
    Mock LLM for testing without API calls.

    Plays back a scripted sequence of responses. When the script runs out,
    returns a default final answer to avoid infinite loops.

    Usage:
        mock = MockLLM([
            LLMResponse.action("search", {"query": "weather"}),
            LLMResponse.text("The weather is sunny today."),
        ])
        loop = AgentLoop(llm=mock, ...)
        result = await loop.run("What's the weather?")
    """

    def __init__(self, responses: Optional[list[LLMResponse]] = None):
        self._responses: list[LLMResponse] = list(responses) if responses else []
        self._index: int = 0
        self.call_log: list[dict] = []

    def add_response(self, response: LLMResponse) -> None:
        """Append a response to the script."""
        self._responses.append(response)

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> LLMResponse:
        # Log the call for inspection in tests
        self.call_log.append(
            {
                "messages_count": len(messages),
                "tools_count": len(tools),
                "system_prompt_len": len(system_prompt),
            }
        )

        if self._index < len(self._responses):
            resp = self._responses[self._index]
            self._index += 1
            return resp

        # Default: return a final answer to avoid infinite loops
        return LLMResponse.text(
            "I have completed the task based on available information.",
            tokens=30,
        )

    @property
    def calls_made(self) -> int:
        return len(self.call_log)

    def reset(self) -> None:
        """Reset to the beginning of the script."""
        self._index = 0
        self.call_log.clear()


# ═══════════════════════════════════════════════════════════════
#  Tool Base
# ═══════════════════════════════════════════════════════════════


class Tool:
    """
    Base class for agent tools.

    Subclasses should:
        - Set name, description, parameters, default_permission
        - Implement async run(**kwargs) -> str
        - Optionally override assess_risk() for runtime risk evaluation

    Permission levels:
        'auto'    — Execute without confirmation
        'confirm' — Requires user confirmation (via permission_callback)
        'block'   — Never execute

    Permission decision chain:
        assess_risk(arguments) → if not None, use that
        → else use default_permission
    """

    name: str = ""
    description: str = ""
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    default_permission: str = "auto"

    async def run(self, **kwargs) -> str:
        """Execute the tool and return a string result."""
        raise NotImplementedError(f"Tool '{self.name}' has not implemented run()")

    def assess_risk(self, arguments: dict) -> Optional[str]:
        """
        Runtime risk assessment.

        Returns:
            'auto'  — safe to execute
            'block' — dangerous, do not execute
            None    — use default_permission
        """
        return None

    def check_permission(self, arguments: dict) -> str:
        """
        Full permission check following the decision chain:
            assess_risk() → block hard limit → default_permission
        """
        risk = self.assess_risk(arguments)
        if risk is not None:
            return risk
        return self.default_permission

    def to_definition(self) -> ToolDefinition:
        """Convert to a ToolDefinition for the context assembler."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )


class FunctionTool(Tool):
    """Wrap a simple async or sync function as a Tool."""

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable[..., Any],
        parameters: Optional[dict] = None,
        default_permission: str = "auto",
    ):
        self.name = name
        self.description = description
        self._func = func
        self.parameters = parameters or {"type": "object", "properties": {}}
        self.default_permission = default_permission

    async def run(self, **kwargs) -> str:
        result = self._func(**kwargs)
        if asyncio.iscoroutine(result):
            result = await result
        return str(result)


# ═══════════════════════════════════════════════════════════════
#  Middleware
# ═══════════════════════════════════════════════════════════════


@dataclass
class LoopState:
    """
    Mutable state passed through middleware hooks.
    Middleware can read/modify this to influence loop behavior.

    Fields:
        history:    Conversation history (mutable)
        turn:       Current turn number (0-indexed)
        context:    The assembled context for this turn
        metadata:   Free-form dict for middleware to stash data
        should_stop:  Set True by middleware to request termination
        stop_reason:  Reason for termination (if should_stop)
    """

    history: list[dict]
    turn: int
    context: Optional[AssembledContext] = None
    metadata: dict = field(default_factory=dict)
    should_stop: bool = False
    stop_reason: Optional[str] = None


class Middleware:
    """
    Base middleware class — override hooks as needed.
    All hooks are async and receive/return the relevant objects.

    Hook points:
        before_llm_call  — modify state before LLM call (e.g., compress history)
        after_llm_call   — modify response after LLM call (e.g., detect loops)
        before_tool_call — modify/block tool call before execution
        after_tool_call  — modify tool output after execution

    Ordering principle (from spec):
        compression → memory injection → subagent limits → loop detection → clarification
    """

    async def before_llm_call(self, state: LoopState) -> LoopState:
        """Called before each LLM call. Can modify state (e.g., compress history)."""
        return state

    async def after_llm_call(
        self, response: LLMResponse, state: LoopState
    ) -> LLMResponse:
        """Called after each LLM call. Can modify response (e.g., detect loops)."""
        return response

    async def before_tool_call(
        self, tool_name: str, arguments: dict, state: LoopState
    ) -> tuple[str, dict]:
        """Called before each tool execution. Can modify arguments."""
        return tool_name, arguments

    async def after_tool_call(
        self,
        tool_name: str,
        arguments: dict,
        output: str,
        state: LoopState,
    ) -> str:
        """Called after each tool execution. Can modify output."""
        return output


# ═══════════════════════════════════════════════════════════════
#  Result Types
# ═══════════════════════════════════════════════════════════════


@dataclass
class ToolResult:
    """Result of a single tool execution."""

    tool_call_id: str
    tool_name: str
    success: bool
    content: str
    attempts: int = 1

    def to_message(self) -> dict:
        """Convert to a tool message for the conversation history."""
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "name": self.tool_name,
            "content": self.content,
        }


@dataclass
class LoopResult:
    """
    Final result of an agent loop run.

    Attributes:
        content:       The agent's final answer (or explanation if partial)
        partial:       True if the loop ended due to budget exhaustion
        interrupted:   True if the loop was interrupted externally
        history:       Full conversation history
        turns_used:    Number of turns executed
        budget_status: Final budget status snapshot
        stop_reason:   Why the loop stopped:
                           'natural'           — model returned final answer
                           'budget_exhausted'  — budget ran out
                           'interrupted'       — external interrupt
                           'middleware'        — middleware requested stop
    """

    content: str
    partial: bool = False
    interrupted: bool = False
    history: list[dict] = field(default_factory=list)
    turns_used: int = 0
    budget_status: Optional[BudgetStatus] = None
    stop_reason: str = "natural"

    @property
    def is_complete(self) -> bool:
        """True if the loop ended naturally (not partial/interrupted)."""
        return not self.partial and not self.interrupted

    def __str__(self) -> str:
        status = "complete" if self.is_complete else self.stop_reason
        return (
            f"LoopResult(stop={status}, turns={self.turns_used}, "
            f"content_len={len(self.content)})"
        )


# Permission callback type — for 'confirm' permission level
PermissionCallback = Callable[[str, dict], Awaitable[bool]]


# ═══════════════════════════════════════════════════════════════
#  Agent Loop (Core)
# ═══════════════════════════════════════════════════════════════


class AgentLoop:
    """
    The core ReAct agent loop.

    Thought → Action → Observation → ... → Final Answer

    Features:
        - Three-dimensional budget management (turns + tokens + wall-clock)
        - Four-layer context assembly with stable prefix caching
        - Injectable LLM interface (use MockLLM for testing)
        - Parallel tool execution with failure isolation
        - Middleware hooks at 4 points in the cycle
        - Tool execution retry (max 2 retries, error fed back to model)
        - Interrupt and resume support
        - Budget exhaustion returns partial results with explanation

    Usage:
        # Simple
        loop = AgentLoop(llm=MockLLM([LLMResponse.text("Hello!")]))
        result = await loop.run("Hi")

        # With tools
        search_tool = FunctionTool("search", "Search the web", my_search_func)
        loop = AgentLoop(
            llm=my_llm,
            tools=[search_tool],
            budget_tracker=BudgetTracker(BudgetConfig(max_turns=10)),
        )
        result = await loop.run("Search for cats")
    """

    def __init__(
        self,
        llm: LLMInterface,
        tools: Optional[list[Tool]] = None,
        budget_tracker: Optional[BudgetTracker] = None,
        context_assembler: Optional[ContextAssembler] = None,
        middleware_chain: Optional[list[Middleware]] = None,
        max_tool_retries: int = 2,
        permission_callback: Optional[PermissionCallback] = None,
    ):
        self.llm = llm
        self.tools: dict[str, Tool] = {}

        self.budget_tracker = budget_tracker or BudgetTracker()

        # If no assembler provided, create one (tool_defs populated below)
        if context_assembler is not None:
            self.context_assembler = context_assembler
        else:
            self.context_assembler = ContextAssembler()

        # Register tools after context_assembler is set
        if tools:
            for tool in tools:
                self.register_tool(tool)

        self.middleware_chain: list[Middleware] = middleware_chain or []
        self.max_tool_retries = max_tool_retries
        self.permission_callback = permission_callback

        # Interrupt / resume support
        self._interrupt_requested: bool = False
        self._resume_state: Optional[tuple[list[dict], int]] = None

    # ── Tool Registration ──────────────────────────────────────

    def register_tool(self, tool: Tool) -> None:
        """Register a tool with the agent."""
        self.tools[tool.name] = tool
        # Keep context assembler's tool definitions in sync
        self.context_assembler.tool_defs = [
            t.to_definition() for t in self.tools.values()
        ]

    def unregister_tool(self, name: str) -> None:
        """Remove a tool from the agent."""
        self.tools.pop(name, None)
        self.context_assembler.tool_defs = [
            t.to_definition() for t in self.tools.values()
        ]

    # ── Interrupt / Resume ─────────────────────────────────────

    def request_interrupt(self) -> None:
        """Request the loop to stop at the next check point."""
        self._interrupt_requested = True

    @property
    def can_resume(self) -> bool:
        """True if there's a saved state to resume from."""
        return self._resume_state is not None

    # ── Main Loop ──────────────────────────────────────────────

    async def run(self, user_message: str) -> LoopResult:
        """
        Run the agent loop with a user message.

        Returns a LoopResult containing the final answer and metadata.
        If the budget is exhausted, returns partial results with explanation.
        If interrupted, saves state for potential resume.
        """
        self.budget_tracker.start()
        self._interrupt_requested = False
        history: list[dict] = [{"role": "user", "content": user_message}]
        return await self._loop(history)

    async def resume(self) -> LoopResult:
        """
        Resume the loop from a previously interrupted state.

        Returns a LoopResult. Raises RuntimeError if no saved state exists.
        """
        if self._resume_state is None:
            raise RuntimeError("No saved state to resume from.")
        history, _prev_turns = self._resume_state
        self._resume_state = None
        self._interrupt_requested = False
        return await self._loop(history)

    async def _loop(self, history: list[dict]) -> LoopResult:
        """Internal loop implementation — shared by run() and resume()."""
        while True:
            # ── ① Budget check (loop top — single chokepoint) ───
            # Adding a new termination condition? Put it here.
            if self.budget_tracker.is_exhausted():
                budget_status = self.budget_tracker.status()
                return LoopResult(
                    content=self.budget_tracker.exhaustion_message(),
                    partial=True,
                    history=history,
                    turns_used=self.budget_tracker.turns_used,
                    budget_status=budget_status,
                    stop_reason="budget_exhausted",
                )

            # ── Check for external interrupt ────────────────────
            if self._interrupt_requested:
                self._resume_state = (
                    list(history),
                    self.budget_tracker.turns_used,
                )
                budget_status = self.budget_tracker.status()
                return LoopResult(
                    content=(
                        "Agent interrupted by external request. "
                        "Call resume() to continue."
                    ),
                    interrupted=True,
                    history=history,
                    turns_used=self.budget_tracker.turns_used,
                    budget_status=budget_status,
                    stop_reason="interrupted",
                )

            # ── ② Assemble context (4 layers) ──────────────────
            budget_status = self.budget_tracker.status()
            budget_constraint = (
                self.budget_tracker.format_constraint_as_instruction()
            )
            context = await self.context_assembler.assemble(
                messages=history,
                budget_constraint=budget_constraint,
                budget_status=budget_status,
            )

            # ── ③ Middleware: before_llm_call ──────────────────
            state = LoopState(
                history=history,
                turn=self.budget_tracker.turns_used,
                context=context,
            )
            for mw in self.middleware_chain:
                state = await mw.before_llm_call(state)
                if state.should_stop:
                    return LoopResult(
                        content=state.stop_reason or "Stopped by middleware.",
                        partial=True,
                        history=history,
                        turns_used=self.budget_tracker.turns_used,
                        budget_status=budget_status,
                        stop_reason="middleware",
                    )

            # ── ④ Call LLM (injectable interface) ──────────────
            tool_dicts = [td.to_dict() for td in context.tool_defs]
            response = await self.llm.chat(
                messages=context.messages,
                tools=tool_dicts,
                system_prompt=context.system_prompt,
            )

            # ── ⑤ Middleware: after_llm_call ───────────────────
            for mw in self.middleware_chain:
                response = await mw.after_llm_call(response, state)
                if state.should_stop:
                    return LoopResult(
                        content=state.stop_reason or "Stopped by middleware.",
                        partial=True,
                        history=history,
                        turns_used=self.budget_tracker.turns_used,
                        budget_status=budget_status,
                        stop_reason="middleware",
                    )

            # ── ⑥ Record budget usage ──────────────────────────
            self.budget_tracker.record_turn(tokens_used=response.total_tokens)

            # ── ⑦ Natural termination: no tool calls ───────────
            if not response.tool_calls:
                return LoopResult(
                    content=response.content or "",
                    partial=False,
                    history=history,
                    turns_used=self.budget_tracker.turns_used,
                    budget_status=self.budget_tracker.status(),
                    stop_reason="natural",
                )

            # ── Append assistant message (Thought + Actions) ───
            assistant_msg: dict = {
                "role": "assistant",
                "content": response.content or "",
            }
            if response.tool_calls:
                assistant_msg["tool_calls"] = [
                    tc.to_dict() for tc in response.tool_calls
                ]
            history.append(assistant_msg)

            # ── ⑧ Execute tools (permission + retry, parallel) ─
            tool_results = await self._execute_tools(response.tool_calls, state)

            # ── ⑨ Append tool results to history (Observations) ─
            for result in tool_results:
                history.append(result.to_message())

    # ── Tool Execution ─────────────────────────────────────────

    async def _execute_tools(
        self,
        tool_calls: list[ToolCall],
        state: LoopState,
    ) -> list[ToolResult]:
        """
        Execute tool calls in parallel with failure isolation.

        Uses asyncio.gather(return_exceptions=True) — the Python equivalent
        of Promise.allSettled — so one tool failure doesn't prevent others
        from executing.

        Stream-parse optimization note:
            When streaming is implemented, permission pre-checks can start
            as soon as tool names are recognized, before the full response
            is parsed. Here we pre-check in the permission step of each tool.
        """

        async def execute_single(tc: ToolCall) -> ToolResult:
            return await self._execute_single_tool(tc, state)

        # Parallel execution with failure isolation
        raw_results = await asyncio.gather(
            *[execute_single(tc) for tc in tool_calls],
            return_exceptions=True,
        )

        # Convert any raw exceptions to error ToolResults
        final_results: list[ToolResult] = []
        for i, r in enumerate(raw_results):
            if isinstance(r, Exception):
                tc = tool_calls[i]
                final_results.append(
                    ToolResult(
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                        success=False,
                        content=(
                            f"Tool execution crashed with unexpected "
                            f"error: {r}"
                        ),
                        attempts=0,
                    )
                )
            elif isinstance(r, ToolResult):
                final_results.append(r)
            else:
                # Shouldn't happen, but handle gracefully
                tc = tool_calls[i]
                final_results.append(
                    ToolResult(
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                        success=False,
                        content="Tool execution returned unexpected result type.",
                    )
                )

        return final_results

    async def _execute_single_tool(
        self,
        tc: ToolCall,
        state: LoopState,
    ) -> ToolResult:
        """
        Execute a single tool call with permission check, middleware, and retry.

        Retry policy:
            - Maximum max_tool_retries additional attempts (default 2, so 3 total)
            - On final failure, the error message is returned as the tool result
              content, which gets fed back to the model in the next turn
        """
        tool = self.tools.get(tc.name)

        # ── Tool not found ──────────────────────────────────
        if tool is None:
            available = ", ".join(self.tools.keys()) or "none"
            return ToolResult(
                tool_call_id=tc.id,
                tool_name=tc.name,
                success=False,
                content=(
                    f"Tool '{tc.name}' is not available. "
                    f"Available tools: {available}"
                ),
            )

        # ── Permission check ────────────────────────────────
        permission = tool.check_permission(tc.arguments)
        if permission == "block":
            return ToolResult(
                tool_call_id=tc.id,
                tool_name=tc.name,
                success=False,
                content=f"Tool '{tc.name}' was blocked by permission policy.",
            )
        if permission == "confirm":
            if self.permission_callback is not None:
                try:
                    approved = await self.permission_callback(
                        tc.name, tc.arguments
                    )
                except Exception as e:
                    return ToolResult(
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                        success=False,
                        content=f"Permission callback error: {e}",
                    )
                if not approved:
                    return ToolResult(
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                        success=False,
                        content=f"Tool '{tc.name}' was not approved by user.",
                    )
            else:
                # No callback configured → safest default is to block
                return ToolResult(
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                    success=False,
                    content=(
                        f"Tool '{tc.name}' requires confirmation but no "
                        f"permission callback is configured."
                    ),
                )

        # ── Execute with retry ───────────────────────────────
        last_error: Optional[Exception] = None
        total_attempts = self.max_tool_retries + 1  # initial + retries

        for attempt in range(1, total_attempts + 1):
            # Reset to original arguments each attempt (middleware may modify)
            current_name = tc.name
            current_args = dict(tc.arguments)

            # Middleware: before_tool_call
            try:
                for mw in self.middleware_chain:
                    current_name, current_args = await mw.before_tool_call(
                        current_name, current_args, state
                    )
            except Exception as e:
                return ToolResult(
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                    success=False,
                    content=f"Middleware before_tool_call failed: {e}",
                    attempts=attempt,
                )

            # Execute tool
            try:
                output = await tool.run(**current_args)

                # Middleware: after_tool_call
                for mw in self.middleware_chain:
                    output = await mw.after_tool_call(
                        current_name, current_args, output, state
                    )

                return ToolResult(
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                    success=True,
                    content=output,
                    attempts=attempt,
                )

            except Exception as e:
                last_error = e
                if attempt < total_attempts:
                    # Retry with same arguments
                    continue
                # Exhausted all retries
                break

        # ── All retries failed — error fed back to model ─────
        error_msg = (
            f"Tool '{tc.name}' failed after {total_attempts} attempt(s)"
        )
        if last_error:
            error_msg += f": {last_error}"

        return ToolResult(
            tool_call_id=tc.id,
            tool_name=tc.name,
            success=False,
            content=error_msg,
            attempts=total_attempts,
        )
