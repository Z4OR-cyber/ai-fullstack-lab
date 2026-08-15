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
# v1.7.0: 请求可重建自检（Harness 借鉴点 ②）
from .request_checkpoint import (
    RequestCheckpoint,
    RequestReconstructionValidator,
    RequestNotReconstructableError,
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
    # v1.7.0: 只读标记。read_only=True 的工具可并行执行；read_only=False
    # （默认，保守策略）视为写工具，在 AgentLoop._execute_tools 中串行执行，
    # 保证写操作不并发、互斥安全。借鉴 Harness 文章的执行调度思路.
    read_only: bool = False

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
        read_only: Optional[bool] = None,
    ):
        self.name = name
        self.description = description
        self._func = func
        self.parameters = parameters or {"type": "object", "properties": {}}
        self.default_permission = default_permission
        # v1.7.0: 标记工具是否只读。只读工具（如查询、搜索）可在
        # _execute_tools 中并行执行；写工具（如创建、修改、删除）串行执行，
        # 通过 asyncio.Lock 保证互斥。默认 None 表示"未显式设置"，此时
        # 沿用类属性（子类可用类属性覆盖 read_only=True）；显式传 True/False
        # 则写入实例属性，优先级最高.
        if read_only is not None:
            self.read_only = read_only

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
        template: Any = None,
        # ── v1.7.0: Harness 借鉴点 ② 请求可重建自检 ──────────
        request_validator: Optional[RequestReconstructionValidator] = None,
        enable_request_checkpoint: bool = False,
        # ── v1.7.0: Harness 借鉴点 ③ 写工具互斥锁 ────────────
        write_lock: Optional[asyncio.Lock] = None,
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

        # Phase 16: optional LoopTemplate for template-driven execution.
        # When set, run() uses _loop_with_template instead of _loop.
        self.template = template

        # Interrupt / resume support
        self._interrupt_requested: bool = False
        self._resume_state: Optional[tuple[list[dict], int]] = None

        # ── v1.7.0: 请求可重建自检（Harness ②）──────────────
        # 当 enable_request_checkpoint=True 时，每次调用 LLM 前用
        # request_validator 对 (messages, tools, system_prompt) 做一次
        # "序列化→反序列化→checksum 比对"。校验通过的 checkpoint 存入
        # state.metadata["last_checkpoint"]；校验失败采用 fail-open 策略
        # （记录 checkpoint_error 但不阻断 loop），因为校验本身的 bug
        # 不应导致生产 agent 停摆。request_validator 为 None 时内部自动
        # 创建一个默认实例（仅当 enable_request_checkpoint=True 时才使用）.
        self.enable_request_checkpoint = enable_request_checkpoint
        self.request_validator: RequestReconstructionValidator = (
            request_validator or RequestReconstructionValidator()
        )

        # ── v1.7.0: 写工具串行锁（Harness ③）────────────────
        # 所有 read_only=False 的工具在同一个 lock 内串行执行，保证写操作
        # 不并发。外部可注入共享 lock（例如多个 AgentLoop 实例共用），
        # 未注入则内部新建。注意：asyncio.Lock 必须在事件循环内创建/使用，
        # 这里延迟到首次使用时绑定（见 _get_write_lock）.
        self._write_lock_optional: Optional[asyncio.Lock] = write_lock
        self._write_lock_bound: Optional[asyncio.Lock] = None

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

    # ── v1.7.0: 请求可重建自检 & 写锁 ────────────────────────

    def _get_write_lock(self) -> asyncio.Lock:
        """获取写工具互斥锁（延迟绑定到当前事件循环）.

        asyncio.Lock 在 Python 3.10 之前不能跨事件循环使用；为安全起见，
        在首次调用时（已处于事件循环中）创建或复用 lock.
        """
        if self._write_lock_optional is not None:
            return self._write_lock_optional
        if self._write_lock_bound is None:
            self._write_lock_bound = asyncio.Lock()
        return self._write_lock_bound

    def _checkpoint_request(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
        state: LoopState,
        model_hint: Optional[str] = None,
    ) -> Optional[RequestCheckpoint]:
        """在发送 LLM 请求前做可重建自检（fail-open）.

        策略：
            - 若 ``enable_request_checkpoint`` 为 False，直接返回 None
              （向后兼容，零开销）.
            - 校验通过：把 checkpoint 写入 state.metadata["last_checkpoint"]
              并清理上轮 checkpoint_error.
            - 校验失败：采用 **fail-open** —— 记录 checkpoint_error 到
              state.metadata，打日志，但 **不抛异常**，让 loop 继续发送请求.
              理由：校验是安全网而非功能本身；若因校验器 bug 阻断 agent
              生产流量，代价远大于降级为无校验运行. checkpoint_error 可供
              审计/告警系统消费.

        Args:
            messages:      即将发给 LLM 的 messages.
            tools:         工具字典列表.
            system_prompt: 系统提示词.
            state:         当前 loop state，用于写入 metadata.
            model_hint:    模型标识（可选）.

        Returns:
            成功时返回 :class:`RequestCheckpoint`，未启用或失败时返回 None.
        """
        if not self.enable_request_checkpoint:
            return None

        try:
            checkpoint = self.request_validator.validate(
                messages=messages,
                tools=tools,
                system_prompt=system_prompt,
                model_hint=model_hint,
            )
        except RequestNotReconstructableError as e:
            # fail-open：记录错误但不阻断请求
            state.metadata["checkpoint_error"] = {
                "error": str(e),
                "reason": e.reason,
                "field_path": e.field_path,
            }
            print(
                f"[RequestCheckpoint] VALIDATION FAILED (fail-open, "
                f"request will still be sent): {e}",
                flush=True,
            )
            return None
        except Exception as e:
            # 兜底：校验器自身出现非预期异常也不能炸 loop
            state.metadata["checkpoint_error"] = {
                "error": f"Validator internal error: {e}",
                "reason": "internal_error",
                "field_path": None,
            }
            print(
                f"[RequestCheckpoint] INTERNAL ERROR (fail-open): {e}",
                flush=True,
            )
            return None

        # 校验通过：写入 checkpoint 并清理上轮错误
        state.metadata["last_checkpoint"] = checkpoint.to_dict()
        state.metadata.pop("checkpoint_error", None)
        return checkpoint

    # ── Interrupt / Resume ─────────────────────────────────────

    def request_interrupt(self) -> None:
        """Request the loop to stop at the next check point."""
        self._interrupt_requested = True

    @property
    def can_resume(self) -> bool:
        """True if there's a saved state to resume from."""
        return self._resume_state is not None

    # ── Main Loop ──────────────────────────────────────────────

    async def run(
        self,
        user_message: str,
        template: Any = None,
    ) -> LoopResult:
        """
        Run the agent loop with a user message.

        Returns a LoopResult containing the final answer and metadata.
        If the budget is exhausted, returns partial results with explanation.
        If interrupted, saves state for potential resume.

        Phase 16: If a ``template`` is passed (or was set in
        ``__init__``), the loop executes in template-driven mode,
        following the template's phases, reflection points, and
        termination conditions.
        """
        self.budget_tracker.start()
        self._interrupt_requested = False
        history: list[dict] = [{"role": "user", "content": user_message}]

        effective_template = template or self.template
        if effective_template is not None:
            return await self._loop_with_template(history, effective_template)
        return await self._loop(history)

    async def run_with_template(
        self,
        user_message: str,
        template: Any,
    ) -> LoopResult:
        """Run the loop using a specific LoopTemplate.

        This is a convenience wrapper around :meth:`run` with an
        explicit template parameter.

        Args:
            user_message: The user's input message.
            template:     A LoopTemplate (or duck-typed object with
                          ``phases``, ``max_iterations``,
                          ``reflection_points``, and
                          ``termination_conditions`` attributes).

        Returns:
            A :class:`LoopResult` with the final answer.
        """
        return await self.run(user_message, template=template)

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
            # v1.7.0: 请求可重建自检（Harness ②）——发送前做序列化→反序列化
            # →checksum 比对。fail-open：失败不阻断请求，错误写入 state.metadata.
            self._checkpoint_request(
                messages=context.messages,
                tools=tool_dicts,
                system_prompt=context.system_prompt,
                state=state,
            )
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

    # ── Template-Driven Loop (Phase 16) ──────────────────────

    async def _loop_with_template(
        self,
        history: list[dict],
        template: Any,
    ) -> LoopResult:
        """Template-driven loop — executes phases from a LoopTemplate.

        Instead of the standard ReAct ``while True`` cycle, this loop
        iterates up to ``template.max_iterations`` times, and within
        each iteration it walks through ``template.phases`` in order.

        For each phase:

        - **perceive** / **plan** — call the LLM with a phase-specific
          system prompt (no tool execution).
        - **execute** — standard ReAct turn: call LLM, execute tool
          calls if any, append results.
        - **verify** — call the LLM to verify the current state.
        - **reflect** — call the LLM for reflection; the output is
          appended to history as context for subsequent phases.

        At ``template.reflection_points`` (step indices), an extra
        reflection turn is inserted.

        Termination conditions checked after each phase:

        - Budget exhausted.
        - External interrupt.
        - No tool calls in an ``execute`` phase (natural completion).
        - ``max_iterations`` reached.

        Args:
            history:   Conversation history (starts with user message).
            template:  A LoopTemplate (or duck-typed object with
                       ``phases``, ``max_iterations``,
                       ``reflection_points``, and
                       ``termination_conditions``).

        Returns:
            A :class:`LoopResult`.
        """
        max_iterations = getattr(template, "max_iterations", 10)
        phases = getattr(template, "phases", [])
        reflection_points = set(getattr(template, "reflection_points", []))
        termination_conditions = getattr(template, "termination_conditions", [])

        if not phases:
            # No phases defined — fall back to standard loop
            return await self._loop(history)

        last_content: str = ""
        iteration: int = 0

        for iteration in range(max_iterations):
            # ── Budget check ──────────────────────────────────
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

            # ── Interrupt check ───────────────────────────────
            if self._interrupt_requested:
                self._resume_state = (
                    list(history),
                    self.budget_tracker.turns_used,
                )
                budget_status = self.budget_tracker.status()
                return LoopResult(
                    content="Agent interrupted by external request.",
                    interrupted=True,
                    history=history,
                    turns_used=self.budget_tracker.turns_used,
                    budget_status=budget_status,
                    stop_reason="interrupted",
                )

            completed_all_phases = True

            for step_idx, phase in enumerate(phases):
                # ── Inter-phase budget check ─────────────────
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

                # ── Inter-phase interrupt check ──────────────
                if self._interrupt_requested:
                    self._resume_state = (
                        list(history),
                        self.budget_tracker.turns_used,
                    )
                    budget_status = self.budget_tracker.status()
                    return LoopResult(
                        content="Agent interrupted by external request.",
                        interrupted=True,
                        history=history,
                        turns_used=self.budget_tracker.turns_used,
                        budget_status=budget_status,
                        stop_reason="interrupted",
                    )

                phase_name = getattr(phase, "name", "execute")
                phase_action = getattr(phase, "action", "")
                phase_tools = getattr(phase, "tools", [])
                phase_condition = getattr(phase, "condition", "always")

                # ── Assemble context ──────────────────────────
                budget_status = self.budget_tracker.status()
                budget_constraint = (
                    self.budget_tracker.format_constraint_as_instruction()
                )
                context = await self.context_assembler.assemble(
                    messages=history,
                    budget_constraint=budget_constraint,
                    budget_status=budget_status,
                )

                # ── Middleware: before_llm_call ──────────────
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

                # ── Build phase-specific system prompt ────────
                phase_prompt = self._build_phase_prompt(
                    phase_name, phase_action, context.system_prompt,
                )

                # ── Call LLM ──────────────────────────────────
                tool_dicts = [td.to_dict() for td in context.tool_defs]
                # v1.7.0: 请求可重建自检（Harness ②）—— fail-open
                self._checkpoint_request(
                    messages=context.messages,
                    tools=tool_dicts,
                    system_prompt=phase_prompt,
                    state=state,
                )
                response = await self.llm.chat(
                    messages=context.messages,
                    tools=tool_dicts,
                    system_prompt=phase_prompt,
                )

                # ── Middleware: after_llm_call ───────────────
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

                # ── Record budget ────────────────────────────
                self.budget_tracker.record_turn(
                    tokens_used=response.total_tokens
                )

                # ── Phase-specific handling ───────────────────
                if response.tool_calls:
                    # Tool calls → execute (regardless of phase name)
                    assistant_msg: dict = {
                        "role": "assistant",
                        "content": response.content or "",
                    }
                    if response.tool_calls:
                        assistant_msg["tool_calls"] = [
                            tc.to_dict() for tc in response.tool_calls
                        ]
                    history.append(assistant_msg)

                    tool_results = await self._execute_tools(
                        response.tool_calls, state
                    )
                    for result in tool_results:
                        history.append(result.to_message())

                    last_content = response.content or last_content
                else:
                    # No tool calls → text response
                    if response.content:
                        last_content = response.content

                    # For 'reflect' phase, append the reflection
                    # to history as context for future phases.
                    if phase_name == "reflect" and response.content:
                        history.append({
                            "role": "assistant",
                            "content": f"[Reflection] {response.content}",
                        })
                    elif phase_name == "execute":
                        # Natural completion in execute phase
                        return LoopResult(
                            content=last_content,
                            partial=False,
                            history=history,
                            turns_used=self.budget_tracker.turns_used,
                            budget_status=self.budget_tracker.status(),
                            stop_reason="natural",
                        )
                    elif phase_name == "verify":
                        # Verification result — check for completion
                        if "no_more_tool_calls" in termination_conditions:
                            # Treat verify-without-tool-calls as completion
                            pass

                    history.append({
                        "role": "assistant",
                        "content": response.content or "",
                    })

                # ── Reflection point ──────────────────────────
                if step_idx in reflection_points:
                    reflect_prompt = (
                        "Reflect on the execution so far. "
                        "Summarize what has been done, what worked, "
                        "and what needs adjustment."
                    )
                    reflect_context = await self.context_assembler.assemble(
                        messages=history,
                        budget_constraint="",
                        budget_status=self.budget_tracker.status(),
                    )
                    reflect_response = await self.llm.chat(
                        messages=reflect_context.messages,
                        tools=[],
                        system_prompt=reflect_prompt,
                    )
                    self.budget_tracker.record_turn(
                        tokens_used=reflect_response.total_tokens
                    )
                    if reflect_response.content:
                        history.append({
                            "role": "assistant",
                            "content": (
                                f"[Reflection] {reflect_response.content}"
                            ),
                        })

                # ── Check phase condition ─────────────────────
                if phase_condition == "never":
                    completed_all_phases = False
                    break

            # ── Check termination conditions ──────────────────
            if "no_more_tool_calls" in termination_conditions:
                # If the last execute phase had no tool calls, we
                # already returned above.  Reaching here means
                # all phases completed with tool calls.
                pass

            if "max_iterations_reached" in termination_conditions:
                if iteration + 1 >= max_iterations:
                    break

        # ── Return final result ──────────────────────────────
        budget_status = self.budget_tracker.status()
        return LoopResult(
            content=last_content or "Task completed via template.",
            partial=False,
            history=history,
            turns_used=self.budget_tracker.turns_used,
            budget_status=budget_status,
            stop_reason="natural",
        )

    @staticmethod
    def _build_phase_prompt(
        phase_name: str,
        phase_action: str,
        base_prompt: str,
    ) -> str:
        """Build a phase-specific system prompt.

        Args:
            phase_name:  Name of the current phase.
            phase_action: Action description for the phase.
            base_prompt:  The base system prompt from context assembly.

        Returns:
            A system prompt string with phase context appended.
        """
        phase_descriptions = {
            "perceive": (
                "You are in the PERCEIVE phase. Observe the current "
                "state and gather context. Do not execute any tools yet."
            ),
            "plan": (
                "You are in the PLAN phase. Decide what to do next "
                "based on observations. Outline your approach."
            ),
            "execute": (
                "You are in the EXECUTE phase. Execute the planned "
                "action by calling the appropriate tools."
            ),
            "verify": (
                "You are in the VERIFY phase. Check that previous "
                "actions achieved the expected result."
            ),
            "reflect": (
                "You are in the REFLECT phase. Evaluate the execution, "
                "identify what worked and what to improve."
            ),
        }
        phase_intro = phase_descriptions.get(
            phase_name,
            f"You are in the {phase_name.upper()} phase.",
        )
        action_line = f"Action: {phase_action}" if phase_action else ""
        parts = [base_prompt, phase_intro]
        if action_line:
            parts.append(action_line)
        return "\n\n".join(p for p in parts if p)

    # ── Tool Execution ─────────────────────────────────────────

    async def _execute_tools(
        self,
        tool_calls: list[ToolCall],
        state: LoopState,
    ) -> list[ToolResult]:
        """
        执行工具调用（v1.7.0：只读并行 + 写工具串行 + 有序提交）.

        调度策略（借鉴 Harness 文章 ③）：
            1. **分组**：按 ``tool.read_only`` 将 tool_calls 拆成两组，
               保持各自在原列表中的相对顺序.
            2. **只读组并行**：用 ``asyncio.gather(return_exceptions=True)``
               并发执行所有 read_only=True 的工具，一个失败不影响其他.
            3. **写组串行**：在 ``async with self._write_lock`` 内按原顺序
               逐个 await 写工具。保证任意时刻只有一个写工具在执行，避免
               并发写冲突（如同时写文件、同时改数据库）.
            4. **有序提交**：两组全部完成后，用 ``tool_call_id`` 映射回
               **原始 tool_calls 的顺序**，返回与输入顺序完全一致的
               ``list[ToolResult]``。即使只读工具并行完成的先后不一，最终
               history 中 tool 消息的顺序也与 LLM 请求的 tool_calls 对齐，
               符合 OpenAI/Anthropic 等 API 对 tool 消息顺序的要求.

        异常隔离：
            - gather 的 exception 转成 ``ToolResult(success=False)``；
            - 串行写工具单个失败也包装为失败 ToolResult，不影响其他写工具.

        Args:
            tool_calls: LLM 请求的工具调用列表（顺序即提交顺序）.
            state:      当前 loop state.

        Returns:
            与 ``tool_calls`` 顺序一致的 :class:`ToolResult` 列表.
        """

        async def execute_single(tc: ToolCall) -> ToolResult:
            """执行单个工具调用（含权限检查、中间件、重试）."""
            return await self._execute_single_tool(tc, state)

        # ── ① 按 read_only 分组（保持原顺序）──────────────────
        read_only_calls: list[tuple[int, ToolCall]] = []
        write_calls: list[tuple[int, ToolCall]] = []
        for idx, tc in enumerate(tool_calls):
            tool = self.tools.get(tc.name)
            # 未注册的工具归入写组（保守策略：串行执行，由 _execute_single_tool
            # 返回 "tool not available" 错误）。已注册工具按 read_only 标记分组.
            if tool is not None and getattr(tool, "read_only", False):
                read_only_calls.append((idx, tc))
            else:
                write_calls.append((idx, tc))

        # 用原索引映射最终结果，保证有序提交
        indexed_results: dict[int, ToolResult] = {}

        # ── ② 只读组：并行执行（return_exceptions 隔离失败）───
        if read_only_calls:
            read_only_results = await asyncio.gather(
                *[execute_single(tc) for _, tc in read_only_calls],
                return_exceptions=True,
            )
            for (orig_idx, tc), r in zip(read_only_calls, read_only_results):
                indexed_results[orig_idx] = self._coerce_tool_result(tc, r)

        # ── ③ 写组：在 write_lock 内串行执行 ─────────────────
        if write_calls:
            write_lock = self._get_write_lock()
            async with write_lock:
                for orig_idx, tc in write_calls:
                    try:
                        r = await execute_single(tc)
                    except Exception as e:
                        # 单个写工具抛异常也不中断后续写工具
                        r = e
                    indexed_results[orig_idx] = self._coerce_tool_result(tc, r)

        # ── ④ 按原 tool_calls 顺序合并结果（有序提交）─────────
        final_results: list[ToolResult] = [
            indexed_results[i] for i in range(len(tool_calls))
        ]
        return final_results

    @staticmethod
    def _coerce_tool_result(
        tc: ToolCall,
        result: Any,
    ) -> ToolResult:
        """把 gather 的原始返回值（ToolResult / Exception / 其他）统一转为
        失败/成功的 :class:`ToolResult`.

        这是 v1.7.0 从旧 ``_execute_tools`` 提取的异常隔离逻辑，供并行组
        和串行组共用，避免重复代码.
        """
        if isinstance(result, ToolResult):
            return result
        if isinstance(result, Exception):
            return ToolResult(
                tool_call_id=tc.id,
                tool_name=tc.name,
                success=False,
                content=f"Tool execution crashed with unexpected error: {result}",
                attempts=0,
            )
        # 不应发生，但兜底
        return ToolResult(
            tool_call_id=tc.id,
            tool_name=tc.name,
            success=False,
            content="Tool execution returned unexpected result type.",
        )

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
