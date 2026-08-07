"""
Agent Instance — Encapsulates AgentLoop + Memory + Tools as an independent agent.

Design principles (from architecture series article 4):
    - **子Agent即配置**: An agent is defined by its configuration
      (name, role, description, system_prompt, tools, model).
    - **上下文隔离**: Each agent runs in its own fresh context.
      Parent history is NOT passed in — the agent starts with a clean slate.
    - **只交回最后一条消息**: After execution, only the final result
      is returned to the caller, not the full conversation history.
    - **权限内聚**: The agent's tool set is fixed at creation time
      and cannot be expanded during execution.

The AgentInstance wraps the existing AgentLoop, providing a higher-level
interface with name/role/description, state tracking, and lifecycle
management. It serves as the building block for multi-agent systems.

Usage::

    from suyi.agents import AgentInstance, AgentConfig
    from suyi.core import MockLLM, LLMResponse

    config = AgentConfig(
        name="researcher",
        role="Information retrieval specialist",
        description="Searches and organizes information from various sources.",
        system_prompt="You are an expert researcher. Find relevant information.",
    )
    agent = AgentInstance(config, llm=MockLLM([LLMResponse.text("Found it!")]))
    result = await agent.run("Search for Python asyncio patterns")
    print(result.content)  # "Found it!"
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from ..core.loop import (
    AgentLoop,
    LLMInterface,
    LLMResponse,
    Middleware,
    Tool,
    LoopResult,
)
from ..core.budget import BudgetTracker, BudgetConfig
from ..core.context import ContextAssembler, IdentityConfig


# ═══════════════════════════════════════════════════════════════
#  Agent State
# ═══════════════════════════════════════════════════════════════


class AgentState(Enum):
    """Lifecycle states of an agent instance.

    Transitions::

        IDLE → RUNNING → COMPLETED
                         ↘ FAILED
        *    → TERMINATED  (external destroy)
    """

    IDLE = "idle"          # Created but not yet started
    RUNNING = "running"    # Currently executing a task
    COMPLETED = "completed"  # Finished successfully
    FAILED = "failed"      # Finished with errors
    TERMINATED = "terminated"  # Destroyed by manager


# ═══════════════════════════════════════════════════════════════
#  Agent Configuration
# ═══════════════════════════════════════════════════════════════


@dataclass
class AgentConfig:
    """Configuration for an AgentInstance.

    This is the "sub-agent as configuration" pattern: an agent is fully
    defined by its configuration, making it easy to create, serialize,
    and manage agent instances.

    Attributes:
        name: Unique identifier for the agent.
        role: Short role description (e.g. "Researcher", "Code Reviewer").
        description: Human-readable description for orchestration decisions.
        system_prompt: The system prompt for the agent's LLM calls.
        tools: List of Tool objects available to this agent.
        budget_config: Budget configuration for the agent's loop.
        middleware_chain: Middleware chain for the agent's loop.
        max_tool_retries: Maximum retry attempts for tool calls.
        can_spawn_subagents: Whether this agent can create sub-agents.
            (Default False — only orchestrators should spawn sub-agents.)
    """

    name: str
    role: str = ""
    description: str = ""
    system_prompt: str = ""
    tools: list[Tool] = field(default_factory=list)
    budget_config: BudgetConfig = field(default_factory=BudgetConfig)
    middleware_chain: list[Middleware] = field(default_factory=list)
    max_tool_retries: int = 2
    can_spawn_subagents: bool = False

    def to_identity(self) -> IdentityConfig:
        """Convert to IdentityConfig for the ContextAssembler."""
        instructions = self.system_prompt
        if not instructions and self.description:
            instructions = self.description
        return IdentityConfig(
            name=self.name,
            description=self.role or self.description,
            instructions=instructions,
        )


# ═══════════════════════════════════════════════════════════════
#  Agent Instance
# ═══════════════════════════════════════════════════════════════


class AgentInstance:
    """An independent agent instance wrapping AgentLoop + Memory + Tools.

    This is the fundamental building block of the multi-agent system.
    Each instance has:
        - A unique name and role
        - Its own AgentLoop (ReAct cycle)
        - Its own tool set (fixed at creation)
        - Its own budget tracker
        - State tracking for lifecycle management

    The instance provides both async and sync execution interfaces.
    Sub-agents created by the SubAgentManager are AgentInstances.

    Key design decisions:
        - **Context isolation**: run() starts with a fresh history.
          No parent context is injected — the agent starts clean.
        - **Last-message-only return**: run() returns a LoopResult,
          but callers typically only use result.content (the final answer).
        - **State tracking**: The instance tracks its own state
          (IDLE/RUNNING/COMPLETED/FAILED/TERMINATED).

    Attributes:
        config: The AgentConfig used to create this instance.
        llm: The LLM interface (injectable, MockLLM for testing).
        instance_id: Unique runtime ID (UUID-based).
        state: Current lifecycle state.
    """

    def __init__(
        self,
        config: AgentConfig,
        llm: LLMInterface,
        memory_manager: Optional[Any] = None,
    ):
        self.config = config
        self.llm = llm
        self.memory_manager = memory_manager
        self.instance_id: str = f"agent_{config.name}_{uuid.uuid4().hex[:8]}"
        self._state: AgentState = AgentState.IDLE
        self._last_result: Optional[LoopResult] = None

        # Build the internal AgentLoop
        self._budget_tracker = BudgetTracker(config.budget_config)
        self._context_assembler = ContextAssembler(
            identity=config.to_identity(),
            tool_defs=[t.to_definition() for t in config.tools] if config.tools else [],
        )
        self._loop = AgentLoop(
            llm=llm,
            tools=list(config.tools) if config.tools else None,
            budget_tracker=self._budget_tracker,
            context_assembler=self._context_assembler,
            middleware_chain=list(config.middleware_chain) if config.middleware_chain else None,
            max_tool_retries=config.max_tool_retries,
        )

    # ── Properties ──────────────────────────────────────────────

    @property
    def name(self) -> str:
        """Agent's unique name."""
        return self.config.name

    @property
    def role(self) -> str:
        """Agent's role description."""
        return self.config.role

    @property
    def description(self) -> str:
        """Agent's human-readable description."""
        return self.config.description

    @property
    def state(self) -> AgentState:
        """Current lifecycle state."""
        return self._state

    @property
    def is_idle(self) -> bool:
        return self._state == AgentState.IDLE

    @property
    def is_running(self) -> bool:
        return self._state == AgentState.RUNNING

    @property
    def is_terminated(self) -> bool:
        return self._state == AgentState.TERMINATED

    @property
    def last_result(self) -> Optional[LoopResult]:
        """The result of the last run(), or None if never run."""
        return self._last_result

    @property
    def tool_names(self) -> set[str]:
        """Set of tool names available to this agent."""
        return {t.name for t in self.config.tools}

    @property
    def can_spawn_subagents(self) -> bool:
        """Whether this agent can create sub-agents."""
        return self.config.can_spawn_subagents

    # ── Execution ───────────────────────────────────────────────

    async def run(self, task: str) -> LoopResult:
        """Run the agent on a task (async).

        The agent starts with a fresh context — only the task string
        is provided. The full ReAct loop runs until completion or
        budget exhaustion.

        Args:
            task: The task description / user message.

        Returns:
            LoopResult containing the final answer and metadata.

        Raises:
            RuntimeError: If the agent is terminated or already running.
        """
        if self._state == AgentState.TERMINATED:
            raise RuntimeError(f"Agent '{self.name}' has been terminated.")
        if self._state == AgentState.RUNNING:
            raise RuntimeError(f"Agent '{self.name}' is already running.")

        # Reset budget tracker for a fresh run
        self._budget_tracker.reset()
        self._state = AgentState.RUNNING

        try:
            result = await self._loop.run(task)
            self._last_result = result
            if result.is_complete:
                self._state = AgentState.COMPLETED
            else:
                self._state = AgentState.FAILED
            return result
        except Exception:
            self._state = AgentState.FAILED
            raise

    def run_sync(self, task: str) -> LoopResult:
        """Run the agent on a task (sync convenience method).

        Creates a new asyncio event loop and runs the async method.
        Safe to call from threads (each call gets its own loop).

        Args:
            task: The task description / user message.

        Returns:
            LoopResult containing the final answer and metadata.
        """
        return asyncio.run(self.run(task))

    # ── Lifecycle ───────────────────────────────────────────────

    def reset(self) -> None:
        """Reset the agent to IDLE state for reuse.

        Clears the last result and resets state. Does NOT reset
        the budget tracker (that happens at the start of run()).
        """
        if self._state == AgentState.RUNNING:
            raise RuntimeError(f"Cannot reset agent '{self.name}' while running.")
        self._state = AgentState.IDLE
        self._last_result = None

    def terminate(self) -> None:
        """Terminate the agent. It cannot be used again after this."""
        self._state = AgentState.TERMINATED

    # ── Representation ──────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"AgentInstance(name={self.config.name!r}, "
            f"role={self.config.role!r}, "
            f"state={self._state.value})"
        )

    def to_dict(self) -> dict:
        """Return a summary dict for status reporting."""
        return {
            "name": self.config.name,
            "role": self.config.role,
            "description": self.config.description,
            "instance_id": self.instance_id,
            "state": self._state.value,
            "tool_names": sorted(self.tool_names),
            "can_spawn_subagents": self.config.can_spawn_subagents,
            "has_result": self._last_result is not None,
        }
