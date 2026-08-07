"""
Sub-Agent Manager — Creation, destruction, state tracking, and lifecycle management.

Design principles (from architecture series article 4):
    - **权限交集**: Sub-agent tools = declared tools ∩ parent's tools.
      This prevents privilege escalation — a sub-agent can never use
      tools the parent doesn't have.
    - **上下文隔离**: Sub-agents start with fresh context. No parent
      history is passed in.
    - **生命周期管理**: The manager tracks all sub-agents, enforces
      concurrency limits, and handles cleanup.
    - **子Agent不能再派子Agent**: By default, sub-agents cannot spawn
      further sub-agents (can_spawn_subagents=False), preventing
      infinite recursion.

Usage::

    from suyi.agents import SubAgentManager, SubAgentConfig
    from suyi.core import MockLLM, LLMResponse, FunctionTool

    # Parent has these tools
    parent_tools = {
        "search": FunctionTool("search", "Search", lambda **k: "result"),
        "read_file": FunctionTool("read_file", "Read", lambda **k: "content"),
        "write_file": FunctionTool("write_file", "Write", lambda **k: "ok"),
    }

    manager = SubAgentManager(
        parent_tool_pool=parent_tools,
        max_concurrent=5,
    )

    # Sub-agent declares it wants search + write_file
    config = SubAgentConfig(
        name="researcher",
        description="Research specialist",
        tool_names=["search", "read_file", "delete_file"],  # delete_file not in parent
    )
    agent = manager.create_subagent(config, llm=MockLLM([LLMResponse.text("Done")]))
    # Effective tools: search + read_file (intersection, delete_file excluded)
    assert agent.tool_names == {"search", "read_file"}
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core.budget import BudgetConfig
from ..core.loop import LLMInterface, Middleware, Tool
from .base import AgentConfig, AgentInstance, AgentState


# ═══════════════════════════════════════════════════════════════
#  Sub-Agent Configuration
# ═══════════════════════════════════════════════════════════════


@dataclass
class SubAgentConfig:
    """Configuration for a sub-agent (lightweight, tool-name-based).

    Unlike AgentConfig which carries Tool objects, SubAgentConfig
    declares tool *names* (strings). The SubAgentManager resolves
    these to actual Tool objects by intersecting with the parent's
    tool pool.

    Attributes:
        name: Unique sub-agent name.
        description: Human-readable description for orchestration.
        system_prompt: System prompt for the sub-agent's LLM calls.
        tool_names: Declared tool names (will be intersected with
            parent's tools to determine effective tool set).
        budget_config: Budget configuration (should be ≤ parent's).
        middleware_chain: Optional middleware for the sub-agent.
        max_tool_retries: Max retry attempts for tool calls.
    """

    name: str
    description: str = ""
    system_prompt: str = ""
    tool_names: list[str] = field(default_factory=list)
    budget_config: BudgetConfig = field(default_factory=BudgetConfig)
    middleware_chain: list[Middleware] = field(default_factory=list)
    max_tool_retries: int = 2


# ═══════════════════════════════════════════════════════════════
#  Sub-Agent Manager
# ═══════════════════════════════════════════════════════════════


class SubAgentManager:
    """Manages the lifecycle of sub-agents.

    Responsibilities:
        1. **Create** sub-agents with permission intersection.
        2. **Track** state of all sub-agents (idle/running/completed/failed).
        3. **Enforce** concurrency limits (max_concurrent).
        4. **Destroy** sub-agents and clean up resources.
        5. **Report** status of all managed sub-agents.

    Permission Intersection:
        When creating a sub-agent, the declared tool_names are intersected
        with the parent's tool pool. Only tools in BOTH sets are given to
        the sub-agent. This ensures sub-agents cannot escalate privileges::

            effective_tools = {
                name: tool
                for name, tool in parent_tool_pool.items()
                if name in declared_tool_names
            }

    Thread Safety:
        All operations are protected by a threading.Lock, making the
        manager safe for concurrent access from multiple threads
        (e.g., when using ThreadPoolExecutor for parallel dispatch).

    Attributes:
        parent_tool_pool: Dict of tool_name → Tool from the parent agent.
        max_concurrent: Maximum number of concurrent running sub-agents.
    """

    def __init__(
        self,
        parent_tool_pool: Optional[dict[str, Tool]] = None,
        max_concurrent: int = 5,
    ):
        self.parent_tool_pool: dict[str, Tool] = dict(parent_tool_pool) if parent_tool_pool else {}
        self.max_concurrent = max_concurrent
        self._subagents: dict[str, AgentInstance] = {}
        self._lock = threading.Lock()

    # ── Permission Intersection ─────────────────────────────────

    def compute_effective_tools(self, declared_tool_names: list[str]) -> list[Tool]:
        """Compute the effective tool set via permission intersection.

        effective = {tool for name, tool in parent_pool if name in declared}

        Args:
            declared_tool_names: Tool names declared by the sub-agent config.

        Returns:
            List of Tool objects that are in both the parent's pool
            and the declared set.
        """
        declared_set = set(declared_tool_names)
        return [
            tool
            for name, tool in self.parent_tool_pool.items()
            if name in declared_set
        ]

    # ── Create ──────────────────────────────────────────────────

    def create_subagent(
        self,
        config: SubAgentConfig,
        llm: LLMInterface,
        memory_manager: Optional[Any] = None,
    ) -> AgentInstance:
        """Create and register a new sub-agent.

        The sub-agent's tools are computed by intersecting its declared
        tool_names with the parent's tool pool. Sub-agents are created
        with can_spawn_subagents=False by default (no recursive spawning).

        Args:
            config: Sub-agent configuration.
            llm: LLM interface for the sub-agent.
            memory_manager: Optional memory manager.

        Returns:
            The created AgentInstance.

        Raises:
            ValueError: If a sub-agent with the same name already exists.
        """
        with self._lock:
            if config.name in self._subagents:
                raise ValueError(
                    f"Sub-agent '{config.name}' already exists. "
                    f"Use destroy_subagent() first or choose a different name."
                )

            # Permission intersection
            effective_tools = self.compute_effective_tools(config.tool_names)

            # Build full AgentConfig
            agent_config = AgentConfig(
                name=config.name,
                role=config.description,
                description=config.description,
                system_prompt=config.system_prompt,
                tools=effective_tools,
                budget_config=config.budget_config,
                middleware_chain=list(config.middleware_chain),
                max_tool_retries=config.max_tool_retries,
                can_spawn_subagents=False,  # Sub-agents can't spawn further sub-agents
            )

            instance = AgentInstance(agent_config, llm=llm, memory_manager=memory_manager)
            self._subagents[config.name] = instance
            return instance

    # ── Destroy ─────────────────────────────────────────────────

    def destroy_subagent(self, name: str) -> bool:
        """Destroy a sub-agent and remove it from the registry.

        The agent is terminated (state → TERMINATED) and removed.
        If the agent is currently running, it will be marked for
        termination but may complete its current operation.

        Args:
            name: Name of the sub-agent to destroy.

        Returns:
            True if the sub-agent was found and destroyed, False otherwise.
        """
        with self._lock:
            instance = self._subagents.get(name)
            if instance is None:
                return False
            instance.terminate()
            del self._subagents[name]
            return True

    def destroy_all(self) -> int:
        """Destroy all sub-agents.

        Returns:
            Number of sub-agents destroyed.
        """
        with self._lock:
            count = len(self._subagents)
            for instance in self._subagents.values():
                instance.terminate()
            self._subagents.clear()
            return count

    # ── Query ───────────────────────────────────────────────────

    def get_subagent(self, name: str) -> Optional[AgentInstance]:
        """Retrieve a sub-agent by name."""
        with self._lock:
            return self._subagents.get(name)

    def list_subagents(self) -> list[dict]:
        """Return a list of all sub-agents with their status."""
        with self._lock:
            return [instance.to_dict() for instance in self._subagents.values()]

    def get_by_state(self, state: AgentState) -> list[AgentInstance]:
        """Return all sub-agents in the given state."""
        with self._lock:
            return [
                instance
                for instance in self._subagents.values()
                if instance.state == state
            ]

    # ── State Tracking ──────────────────────────────────────────

    @property
    def count(self) -> int:
        """Total number of managed sub-agents."""
        with self._lock:
            return len(self._subagents)

    @property
    def active_count(self) -> int:
        """Number of currently running sub-agents."""
        with self._lock:
            return sum(
                1
                for inst in self._subagents.values()
                if inst.state == AgentState.RUNNING
            )

    @property
    def idle_count(self) -> int:
        """Number of idle sub-agents."""
        with self._lock:
            return sum(
                1
                for inst in self._subagents.values()
                if inst.state == AgentState.IDLE
            )

    @property
    def completed_count(self) -> int:
        """Number of completed sub-agents."""
        with self._lock:
            return sum(
                1
                for inst in self._subagents.values()
                if inst.state == AgentState.COMPLETED
            )

    @property
    def failed_count(self) -> int:
        """Number of failed sub-agents."""
        with self._lock:
            return sum(
                1
                for inst in self._subagents.values()
                if inst.state == AgentState.FAILED
            )

    def can_create_more(self) -> bool:
        """Check if more sub-agents can be created (within concurrency limit)."""
        with self._lock:
            return len(self._subagents) < self.max_concurrent

    # ── Status Report ───────────────────────────────────────────

    def status(self) -> dict:
        """Return a summary of the manager's state."""
        with self._lock:
            return {
                "total": len(self._subagents),
                "idle": sum(1 for i in self._subagents.values() if i.state == AgentState.IDLE),
                "running": sum(1 for i in self._subagents.values() if i.state == AgentState.RUNNING),
                "completed": sum(1 for i in self._subagents.values() if i.state == AgentState.COMPLETED),
                "failed": sum(1 for i in self._subagents.values() if i.state == AgentState.FAILED),
                "terminated": sum(1 for i in self._subagents.values() if i.state == AgentState.TERMINATED),
                "max_concurrent": self.max_concurrent,
                "parent_tools": sorted(self.parent_tool_pool.keys()),
            }

    def __repr__(self) -> str:
        return (
            f"SubAgentManager("
            f"count={self.count}, "
            f"active={self.active_count}, "
            f"max={self.max_concurrent})"
        )
