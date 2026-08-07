"""
Suyi Multi-Agent System (Phase 3).

Provides the building blocks for multi-agent collaboration:

    - **AgentInstance**: Wraps AgentLoop + Memory + Tools into an
      independent agent with name/role/description and lifecycle tracking.
    - **SubAgentManager**: Creates, tracks, and destroys sub-agents
      with permission intersection (declared ∩ parent's tools).
    - **OrchestratorAgent**: Decomposes tasks, dispatches to sub-agents
      in parallel (ThreadPoolExecutor), and aggregates results.
    - **Patterns**: Three collaboration patterns:
        - Pipeline: serial data flow (A → B → C)
        - Blackboard: shared storage with partitions + pub/sub
        - Voting: majority / weighted / confidence decision

Quick start::

    from suyi.agents import (
        AgentInstance, AgentConfig,
        OrchestratorAgent, SubAgentConfig,
        Pipeline, PipelineStage,
        Blackboard, Voting, VotingStrategy,
    )
    from suyi.core import MockLLM, LLMResponse

    # Create a simple agent
    agent = AgentInstance(
        config=AgentConfig(name="worker", description="A worker agent"),
        llm=MockLLM([LLMResponse.text("Done!")]),
    )
    result = await agent.run("Do something")
"""

from __future__ import annotations

from .base import (
    AgentInstance,
    AgentConfig,
    AgentState,
)
from .subagent import (
    SubAgentConfig,
    SubAgentManager,
)
from .orchestrator import (
    OrchestratorAgent,
    SubTask,
    SubTaskResult,
    OrchestratorResult,
)
from .patterns import (
    Pipeline,
    PipelineStage,
    PipelineResult,
    Blackboard,
    BlackboardEntry,
    Voting,
    Vote,
    VoteResult,
    VotingStrategy,
)

__all__ = [
    # Base
    "AgentInstance",
    "AgentConfig",
    "AgentState",
    # Sub-agent management
    "SubAgentConfig",
    "SubAgentManager",
    # Orchestrator
    "OrchestratorAgent",
    "SubTask",
    "SubTaskResult",
    "OrchestratorResult",
    # Collaboration patterns
    "Pipeline",
    "PipelineStage",
    "PipelineResult",
    "Blackboard",
    "BlackboardEntry",
    "Voting",
    "Vote",
    "VoteResult",
    "VotingStrategy",
]
