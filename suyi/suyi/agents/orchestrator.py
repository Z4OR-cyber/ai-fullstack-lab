"""
Orchestrator Agent — Task decomposition, parallel sub-agent dispatch, result aggregation.

Design principles (from architecture series article 4):
    - **编排者/执行者分离**: The orchestrator only has read-only + dispatch
      tools. It decomposes tasks, dispatches to sub-agents, and aggregates
      results. It does NOT execute side-effect operations directly.
    - **模型即调度器**: The LLM acts as the scheduler — it decomposes the
      task and determines which sub-agents to invoke. The orchestrator
      framework handles the mechanics of parallel execution.
    - **并行执行**: Sub-agents run in parallel via ThreadPoolExecutor.
      Each sub-agent runs in its own thread with its own asyncio event loop.
    - **权限交集**: Sub-agent tools = declared ∩ parent's tools.
    - **结果汇总**: After all sub-agents complete, the orchestrator
      aggregates their results into a final answer.

Flow::

    User Task
        │
        ▼
    ┌──────────────┐
    │  Decompose   │  ← LLM breaks task into subtasks
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │  Dispatch    │  ← ThreadPoolExecutor runs sub-agents in parallel
    │  (parallel)  │     agent1 ──→ result1
    │              │     agent2 ──→ result2
    │              │     agent3 ──→ result3
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │  Aggregate   │  ← Combine results into final answer
    └──────┬───────┘
           │
        Final
        Answer

Usage::

    from suyi.agents import OrchestratorAgent, SubAgentConfig
    from suyi.core import MockLLM, LLMResponse, FunctionTool

    # Tools available for delegation
    tool_pool = {
        "search": FunctionTool("search", "Search", lambda **k: "found"),
        "read_file": FunctionTool("read_file", "Read", lambda **k: "content"),
    }

    # Orchestrator's LLM: first decompose, then aggregate
    orch_llm = MockLLM([
        LLMResponse.text("SUBTASK: Research the topic\\nSUBTASK: Analyze findings"),
        LLMResponse.text("Combined research and analysis complete."),
    ])

    orchestrator = OrchestratorAgent(
        llm=orch_llm,
        tool_pool=tool_pool,
        max_workers=4,
    )

    # Register sub-agent configs
    orchestrator.register_subagent(SubAgentConfig(
        name="researcher",
        description="Research specialist",
        tool_names=["search", "read_file"],
    ))

    result = orchestrator.run_sync("Research and analyze Python asyncio")
    print(result.content)
"""

from __future__ import annotations

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..core.loop import (
    LLMInterface,
    LLMResponse,
    Tool,
    LoopResult,
    FunctionTool,
)
from ..core.budget import BudgetConfig
from .base import AgentConfig, AgentInstance, AgentState
from .subagent import SubAgentConfig, SubAgentManager


# ═══════════════════════════════════════════════════════════════
#  Data Types
# ═══════════════════════════════════════════════════════════════


@dataclass
class SubTask:
    """A decomposed subtask assigned to a sub-agent.

    Attributes:
        description: The subtask description / prompt for the sub-agent.
        subagent_name: Name of the sub-agent to assign this task to.
        index: Position in the decomposition (0-based).
    """

    description: str
    subagent_name: str = ""
    index: int = 0


@dataclass
class SubTaskResult:
    """Result of a single subtask execution.

    Attributes:
        subtask: The original subtask.
        subagent_name: Name of the sub-agent that executed it.
        success: Whether the sub-agent completed successfully.
        content: The sub-agent's final answer.
        error: Error message if the subtask failed.
        turns_used: Number of turns used by the sub-agent.
    """

    subtask: SubTask
    subagent_name: str
    success: bool
    content: str
    error: str = ""
    turns_used: int = 0


@dataclass
class OrchestratorResult:
    """Final result of the orchestrator's run.

    Attributes:
        content: The aggregated final answer.
        subtask_results: Results from each subtask.
        success: Whether all subtasks completed successfully.
        subtask_count: Number of subtasks executed.
        failed_count: Number of failed subtasks.
    """

    content: str
    subtask_results: list[SubTaskResult] = field(default_factory=list)
    success: bool = True
    subtask_count: int = 0
    failed_count: int = 0

    def __str__(self) -> str:
        return (
            f"OrchestratorResult(success={self.success}, "
            f"subtasks={self.subtask_count}, "
            f"failed={self.failed_count}, "
            f"content_len={len(self.content)})"
        )


# ═══════════════════════════════════════════════════════════════
#  Orchestrator Agent
# ═══════════════════════════════════════════════════════════════


class OrchestratorAgent:
    """Orchestrator agent that decomposes tasks and dispatches to sub-agents.

    The orchestrator follows a three-phase pattern:
        1. **Decompose**: Uses the LLM to break a complex task into subtasks.
        2. **Dispatch**: Runs sub-agents in parallel via ThreadPoolExecutor.
        3. **Aggregate**: Combines sub-agent results into a final answer.

    The orchestrator itself does NOT execute tools directly — it only
    decomposes, dispatches, and aggregates. Sub-agents do the actual work.

    Permission Model:
        The orchestrator has a `tool_pool` (all tools available for delegation).
        Sub-agents declare which tools they want, and the effective set is
        the intersection (sub-agent declared ∩ orchestrator's tool_pool).

    Attributes:
        llm: The orchestrator's LLM (used for decomposition and aggregation).
        tool_pool: Dict of tool_name → Tool available for delegation.
        max_workers: Maximum parallel sub-agents (ThreadPoolExecutor).
        subagent_manager: The SubAgentManager for lifecycle management.
    """

    def __init__(
        self,
        llm: LLMInterface,
        tool_pool: Optional[dict[str, Tool]] = None,
        max_workers: int = 4,
        max_subagents: int = 10,
        name: str = "orchestrator",
        budget_config: Optional[BudgetConfig] = None,
    ):
        self.llm = llm
        self.tool_pool: dict[str, Tool] = dict(tool_pool) if tool_pool else {}
        self.max_workers = max_workers
        self.name = name
        self.budget_config = budget_config or BudgetConfig()

        # Sub-agent manager with the orchestrator's tool pool
        self.subagent_manager = SubAgentManager(
            parent_tool_pool=self.tool_pool,
            max_concurrent=max_subagents,
        )

        # Registry of sub-agent configs (name → config)
        self._subagent_configs: dict[str, SubAgentConfig] = {}
        # Registry of sub-agent LLMs (name → LLM)
        self._subagent_llms: dict[str, LLMInterface] = {}

        # Track the last decomposition and result
        self._last_subtasks: list[SubTask] = []
        self._last_result: Optional[OrchestratorResult] = None

    # ── Sub-agent Registration ──────────────────────────────────

    def register_subagent(
        self,
        config: SubAgentConfig,
        llm: Optional[LLMInterface] = None,
    ) -> None:
        """Register a sub-agent configuration for use in dispatch.

        Registered sub-agents can be assigned subtasks during dispatch.
        If no LLM is provided, the orchestrator's LLM is shared (note:
        this is typically only for testing with MockLLM).

        Args:
            config: Sub-agent configuration.
            llm: LLM for the sub-agent (defaults to orchestrator's LLM).
        """
        self._subagent_configs[config.name] = config
        self._subagent_llms[config.name] = llm if llm is not None else self.llm

    @property
    def registered_subagents(self) -> list[str]:
        """Names of registered sub-agent configs."""
        return list(self._subagent_configs.keys())

    # ── Phase 1: Decompose ──────────────────────────────────────

    async def decompose(self, task: str) -> list[SubTask]:
        """Decompose a task into subtasks using the LLM.

        The LLM is prompted to break the task into subtasks. The response
        is parsed to extract subtask descriptions. Two formats are supported:

        1. **Line-based**: Lines starting with "SUBTASK:" are extracted.
           Example: ``SUBTASK: Research the topic``
        2. **JSON**: A JSON object with a "subtasks" array.
           Example: ``{"subtasks": ["Research", "Analyze"]}``

        If parsing fails, a single subtask with the original task is returned.

        Args:
            task: The task to decompose.

        Returns:
            List of SubTask objects.
        """
        decomposition_prompt = (
            f"Decompose the following task into independent subtasks.\n"
            f"Each subtask should be on a new line, prefixed with 'SUBTASK: '.\n"
            f"Task: {task}\n\n"
            f"Subtasks:"
        )

        response = await self.llm.chat(
            messages=[{"role": "user", "content": decomposition_prompt}],
            tools=[],
            system_prompt=(
                "You are a task orchestrator. Break down complex tasks "
                "into independent subtasks. Output each subtask on a new "
                "line prefixed with 'SUBTASK: '."
            ),
        )

        subtask_descriptions = self._parse_decomposition(response.content or "")
        subtasks = [
            SubTask(description=desc.strip(), index=i)
            for i, desc in enumerate(subtask_descriptions)
            if desc.strip()
        ]

        if not subtasks:
            # Fallback: treat the whole task as a single subtask
            subtasks = [SubTask(description=task, index=0)]

        self._last_subtasks = subtasks
        return subtasks

    @staticmethod
    def _parse_decomposition(content: str) -> list[str]:
        """Parse the LLM's decomposition response into subtask descriptions.

        Supports:
            1. JSON: {"subtasks": ["task1", "task2"]}
            2. Line-based: SUBTASK: task1
        """
        # Try JSON first
        try:
            # Find JSON in the response
            json_match = re.search(r'\{[^{}]*"subtasks"\s*:\s*\[.*?\]\s*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                if "subtasks" in data and isinstance(data["subtasks"], list):
                    return [str(s) for s in data["subtasks"]]
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fall back to line-based parsing
        subtasks = []
        for line in content.split("\n"):
            line = line.strip()
            if line.upper().startswith("SUBTASK:"):
                desc = line[len("SUBTASK:"):].strip()
                if desc:
                    subtasks.append(desc)
            elif line and line[0].isdigit() and "." in line[:4]:
                # "1. Do something" format
                parts = line.split(".", 1)
                if len(parts) == 2 and parts[1].strip():
                    subtasks.append(parts[1].strip())

        return subtasks

    # ── Phase 2: Dispatch (Parallel Execution) ──────────────────

    def dispatch(
        self,
        subtasks: list[SubTask],
        subagent_factory: Optional[Callable[[SubTask], tuple[SubAgentConfig, LLMInterface]]] = None,
    ) -> list[SubTaskResult]:
        """Dispatch subtasks to sub-agents in parallel via ThreadPoolExecutor.

        Each subtask is assigned to a sub-agent. If registered sub-agent
        configs exist, subtasks are assigned round-robin. Otherwise, a
        factory function or default config is used.

        Parallel execution:
            - Each sub-agent runs in its own thread.
            - Each thread creates its own asyncio event loop (via run_sync).
            - Failure isolation: one sub-agent's failure doesn't affect others.

        Args:
            subtasks: List of subtasks to dispatch.
            subagent_factory: Optional factory that returns (config, llm)
                for a given subtask. If None, uses registered configs or
                creates default sub-agents.

        Returns:
            List of SubTaskResult objects (one per subtask).
        """
        if not subtasks:
            return []

        # Assign subagents to subtasks
        assignments: list[tuple[SubTask, SubAgentConfig, LLMInterface]] = []
        registered_names = list(self._subagent_configs.keys())

        for i, subtask in enumerate(subtasks):
            if subagent_factory is not None:
                config, llm = subagent_factory(subtask)
            elif registered_names:
                # Round-robin assignment to registered sub-agents
                name = registered_names[i % len(registered_names)]
                config = self._subagent_configs[name]
                llm = self._subagent_llms[name]
                subtask.subagent_name = name
            else:
                # Create a default sub-agent config
                config = SubAgentConfig(
                    name=f"worker_{i}",
                    description=f"Worker agent for subtask {i}",
                    tool_names=list(self.tool_pool.keys()),
                )
                llm = self.llm
                subtask.subagent_name = config.name

            assignments.append((subtask, config, llm))

        # Create sub-agents (clear previous ones first)
        # Use unique names to avoid collision when the same config is reused
        self.subagent_manager.destroy_all()
        subagent_instances: list[tuple[SubTask, AgentInstance]] = []
        name_usage: dict[str, int] = {}  # base_name → count
        for subtask, config, llm in assignments:
            base_name = config.name
            if base_name in name_usage:
                name_usage[base_name] += 1
                unique_name = f"{base_name}_{name_usage[base_name]}"
            else:
                name_usage[base_name] = 0
                unique_name = base_name

            # Create a config copy with the unique name
            unique_config = SubAgentConfig(
                name=unique_name,
                description=config.description,
                system_prompt=config.system_prompt,
                tool_names=list(config.tool_names),
                budget_config=config.budget_config,
                middleware_chain=list(config.middleware_chain),
                max_tool_retries=config.max_tool_retries,
            )
            instance = self.subagent_manager.create_subagent(unique_config, llm=llm)
            subtask.subagent_name = unique_name
            subagent_instances.append((subtask, instance))

        # Run in parallel via ThreadPoolExecutor
        results: list[SubTaskResult] = [None] * len(subagent_instances)  # type: ignore

        def _execute_subtask(
            idx: int, subtask: SubTask, instance: AgentInstance
        ) -> tuple[int, SubTaskResult]:
            """Execute a single subtask (runs in a thread)."""
            try:
                loop_result = instance.run_sync(subtask.description)
                return idx, SubTaskResult(
                    subtask=subtask,
                    subagent_name=instance.name,
                    success=loop_result.is_complete,
                    content=loop_result.content,
                    turns_used=loop_result.turns_used,
                )
            except Exception as e:
                return idx, SubTaskResult(
                    subtask=subtask,
                    subagent_name=instance.name,
                    success=False,
                    content="",
                    error=str(e),
                )

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(subagent_instances))) as pool:
            futures = {
                pool.submit(_execute_subtask, i, st, inst): i
                for i, (st, inst) in enumerate(subagent_instances)
            }
            for future in as_completed(futures):
                idx, subtask_result = future.result()
                results[idx] = subtask_result

        return results  # type: ignore

    # ── Phase 3: Aggregate ──────────────────────────────────────

    async def aggregate(self, results: list[SubTaskResult]) -> str:
        """Aggregate sub-task results into a final answer.

        If all subtasks succeeded, the LLM is used to synthesize the
        results. If some failed, failure information is included.
        If the LLM call fails, a simple concatenation is used as fallback.

        Args:
            results: List of subtask results.

        Returns:
            The aggregated final answer string.
        """
        if not results:
            return "No subtasks were executed."

        # Build aggregation prompt
        parts: list[str] = []
        for i, r in enumerate(results):
            status = "✓" if r.success else "✗"
            content = r.content if r.success else f"FAILED: {r.error}"
            parts.append(f"Subtask {i} ({status}) [{r.subagent_name}]:\n{content}")

        subtask_summaries = "\n\n".join(parts)

        aggregation_prompt = (
            f"Synthesize the following subtask results into a coherent final answer.\n"
            f"Subtask results:\n\n{subtask_summaries}\n\n"
            f"Final answer:"
        )

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": aggregation_prompt}],
                tools=[],
                system_prompt=(
                    "You are a result aggregator. Synthesize multiple "
                    "subtask results into a clear, coherent final answer."
                ),
            )
            return response.content or subtask_summaries
        except Exception:
            # Fallback: simple concatenation
            return subtask_summaries

    # ── Full Orchestration Run ──────────────────────────────────

    async def run(self, task: str) -> OrchestratorResult:
        """Run the full orchestration: decompose → dispatch → aggregate.

        Args:
            task: The complex task to orchestrate.

        Returns:
            OrchestratorResult with the aggregated answer and subtask details.
        """
        # Phase 1: Decompose
        subtasks = await self.decompose(task)

        # Phase 2: Dispatch (parallel)
        subtask_results = self.dispatch(subtasks)

        # Phase 3: Aggregate
        content = await self.aggregate(subtask_results)

        # Build result
        failed = sum(1 for r in subtask_results if not r.success)
        result = OrchestratorResult(
            content=content,
            subtask_results=subtask_results,
            success=failed == 0,
            subtask_count=len(subtask_results),
            failed_count=failed,
        )

        self._last_result = result
        return result

    def run_sync(self, task: str) -> OrchestratorResult:
        """Sync convenience method for the full orchestration run."""
        return asyncio.run(self.run(task))

    # ── Properties ──────────────────────────────────────────────

    @property
    def last_subtasks(self) -> list[SubTask]:
        """Subtasks from the last decomposition."""
        return self._last_subtasks

    @property
    def last_result(self) -> Optional[OrchestratorResult]:
        """Result from the last run."""
        return self._last_result

    @property
    def subagent_count(self) -> int:
        """Number of currently managed sub-agents."""
        return self.subagent_manager.count

    def status(self) -> dict:
        """Return orchestrator status summary."""
        return {
            "name": self.name,
            "max_workers": self.max_workers,
            "tool_pool": sorted(self.tool_pool.keys()),
            "registered_subagents": list(self._subagent_configs.keys()),
            "subagent_manager": self.subagent_manager.status(),
            "last_subtask_count": len(self._last_subtasks),
            "has_result": self._last_result is not None,
        }

    def __repr__(self) -> str:
        return (
            f"OrchestratorAgent(name={self.name!r}, "
            f"tools={sorted(self.tool_pool.keys())}, "
            f"max_workers={self.max_workers}, "
            f"registered={list(self._subagent_configs.keys())})"
        )
