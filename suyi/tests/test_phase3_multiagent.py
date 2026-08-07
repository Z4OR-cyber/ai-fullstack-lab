"""Suyi Phase 3 多Agent系统测试.

Tests:
    1. AgentInstance 基础功能与生命周期
    2. SubAgentManager 创建/销毁/状态追踪/权限交集
    3. OrchestratorAgent 任务分解与并行执行
    4. Pipeline 管道链串行数据流
    5. Blackboard 共享黑板读写与订阅
    6. Voting 投票决策三种策略
    7. 集成场景：编排者 + 管道 + 黑板
"""

import asyncio
import threading
import time
import pytest

from suyi.core.loop import (
    MockLLM,
    LLMResponse,
    FunctionTool,
    Tool,
)
from suyi.core.budget import BudgetConfig
from suyi.agents import (
    AgentInstance,
    AgentConfig,
    AgentState,
    SubAgentConfig,
    SubAgentManager,
    OrchestratorAgent,
    SubTask,
    SubTaskResult,
    OrchestratorResult,
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


# ═══════════════════════════════════════════════════════════════
#  Helper: create a simple mock tool
# ═══════════════════════════════════════════════════════════════


def make_tool(name, result="ok"):
    """Create a simple FunctionTool for testing."""
    return FunctionTool(
        name=name,
        description=f"Test tool: {name}",
        func=lambda **kwargs: result,
        default_permission="auto",
    )


# ═══════════════════════════════════════════════════════════════
#  1. AgentInstance Tests
# ═══════════════════════════════════════════════════════════════


class TestAgentInstance:
    """AgentInstance 基础功能与生命周期测试."""

    def test_create_agent(self):
        """Agent can be created with config and LLM."""
        config = AgentConfig(
            name="test_agent",
            role="tester",
            description="A test agent",
            system_prompt="You are a test agent.",
        )
        agent = AgentInstance(config, llm=MockLLM([LLMResponse.text("Hello")]))
        assert agent.name == "test_agent"
        assert agent.role == "tester"
        assert agent.description == "A test agent"
        assert agent.state == AgentState.IDLE
        assert agent.is_idle
        assert agent.instance_id.startswith("agent_test_agent_")

    def test_run_sync_simple(self):
        """Agent can execute a task and return a result."""
        config = AgentConfig(name="worker", description="Worker")
        agent = AgentInstance(
            config,
            llm=MockLLM([LLMResponse.text("Task completed!")]),
        )
        result = agent.run_sync("Do the task")
        assert result.content == "Task completed!"
        assert result.is_complete
        assert agent.state == AgentState.COMPLETED
        assert agent.last_result is result

    def test_run_async(self):
        """Agent can run asynchronously."""
        config = AgentConfig(name="async_worker")
        agent = AgentInstance(
            config,
            llm=MockLLM([LLMResponse.text("Async done")]),
        )

        async def _run():
            return await agent.run("Do async work")

        result = asyncio.run(_run())
        assert result.content == "Async done"
        assert agent.state == AgentState.COMPLETED

    def test_agent_with_tools(self):
        """Agent can use tools during execution."""
        search_tool = make_tool("search", "Found: Python asyncio")
        config = AgentConfig(
            name="researcher",
            tools=[search_tool],
            budget_config=BudgetConfig(max_turns=5),
        )
        # LLM: first call tool, then return final answer
        agent = AgentInstance(
            config,
            llm=MockLLM([
                LLMResponse.action("search", {"query": "asyncio"}),
                LLMResponse.text("Based on search: Python asyncio is great."),
            ]),
        )
        result = agent.run_sync("Search for asyncio")
        assert "asyncio" in result.content.lower()
        assert agent.state == AgentState.COMPLETED

    def test_tool_names_property(self):
        """Agent exposes its tool names."""
        tools = [make_tool("search"), make_tool("read_file"), make_tool("write_file")]
        config = AgentConfig(name="worker", tools=tools)
        agent = AgentInstance(config, llm=MockLLM())
        assert agent.tool_names == {"search", "read_file", "write_file"}

    def test_reset(self):
        """Agent can be reset to IDLE for reuse."""
        config = AgentConfig(name="reusable")
        agent = AgentInstance(
            config,
            llm=MockLLM([LLMResponse.text("First run")]),
        )
        agent.run_sync("First task")
        assert agent.state == AgentState.COMPLETED
        agent.reset()
        assert agent.state == AgentState.IDLE
        assert agent.last_result is None

    def test_terminate(self):
        """Agent can be terminated and cannot run after."""
        config = AgentConfig(name="doomed")
        agent = AgentInstance(config, llm=MockLLM())
        agent.terminate()
        assert agent.is_terminated
        with pytest.raises(RuntimeError, match="terminated"):
            agent.run_sync("Try to run")

    def test_cannot_run_while_running(self):
        """Running agent cannot be called again simultaneously."""
        config = AgentConfig(name="busy")
        agent = AgentInstance(config, llm=MockLLM([LLMResponse.text("Working")]))
        agent._state = AgentState.RUNNING
        with pytest.raises(RuntimeError, match="already running"):
            agent.run_sync("Second call")

    def test_to_dict(self):
        """Agent can serialize its status."""
        config = AgentConfig(
            name="status_agent",
            role="monitor",
            description="Status check",
            tools=[make_tool("check")],
        )
        agent = AgentInstance(config, llm=MockLLM())
        d = agent.to_dict()
        assert d["name"] == "status_agent"
        assert d["role"] == "monitor"
        assert d["state"] == "idle"
        assert "check" in d["tool_names"]
        assert d["can_spawn_subagents"] is False

    def test_can_spawn_subagents_flag(self):
        """can_spawn_subagents defaults to False."""
        config = AgentConfig(name="worker")
        agent = AgentInstance(config, llm=MockLLM())
        assert agent.can_spawn_subagents is False

        config2 = AgentConfig(name="orchestrator", can_spawn_subagents=True)
        agent2 = AgentInstance(config2, llm=MockLLM())
        assert agent2.can_spawn_subagents is True


# ═══════════════════════════════════════════════════════════════
#  2. SubAgentManager Tests
# ═══════════════════════════════════════════════════════════════


class TestSubAgentManager:
    """SubAgentManager 创建/销毁/状态追踪/权限交集测试."""

    def test_create_subagent(self):
        """Sub-agent can be created with config and LLM."""
        tool_pool = {
            "search": make_tool("search"),
            "read_file": make_tool("read_file"),
        }
        manager = SubAgentManager(parent_tool_pool=tool_pool, max_concurrent=5)
        config = SubAgentConfig(
            name="researcher",
            description="Research specialist",
            tool_names=["search", "read_file"],
        )
        agent = manager.create_subagent(config, llm=MockLLM([LLMResponse.text("Done")]))
        assert agent.name == "researcher"
        assert agent.state == AgentState.IDLE
        assert manager.count == 1

    def test_permission_intersection(self):
        """Sub-agent tools = declared ∩ parent's tools."""
        tool_pool = {
            "search": make_tool("search"),
            "read_file": make_tool("read_file"),
            "write_file": make_tool("write_file"),
        }
        manager = SubAgentManager(parent_tool_pool=tool_pool)

        # Sub-agent declares search + delete_file (delete not in parent)
        config = SubAgentConfig(
            name="worker",
            tool_names=["search", "read_file", "delete_file"],
        )
        agent = manager.create_subagent(config, llm=MockLLM())

        # Effective tools: search + read_file (intersection)
        assert agent.tool_names == {"search", "read_file"}
        assert "delete_file" not in agent.tool_names

    def test_permission_intersection_empty(self):
        """Sub-agent with no matching tools gets empty tool set."""
        tool_pool = {"search": make_tool("search")}
        manager = SubAgentManager(parent_tool_pool=tool_pool)
        config = SubAgentConfig(
            name="worker",
            tool_names=["bash", "delete_file"],  # None in parent
        )
        agent = manager.create_subagent(config, llm=MockLLM())
        assert agent.tool_names == set()

    def test_subagent_cannot_spawn(self):
        """Created sub-agents have can_spawn_subagents=False."""
        tool_pool = {"search": make_tool("search")}
        manager = SubAgentManager(parent_tool_pool=tool_pool)
        config = SubAgentConfig(name="worker", tool_names=["search"])
        agent = manager.create_subagent(config, llm=MockLLM())
        assert agent.can_spawn_subagents is False

    def test_destroy_subagent(self):
        """Sub-agent can be destroyed."""
        tool_pool = {"search": make_tool("search")}
        manager = SubAgentManager(parent_tool_pool=tool_pool)
        config = SubAgentConfig(name="temp", tool_names=["search"])
        manager.create_subagent(config, llm=MockLLM())
        assert manager.count == 1

        result = manager.destroy_subagent("temp")
        assert result is True
        assert manager.count == 0

    def test_destroy_nonexistent(self):
        """Destroying non-existent sub-agent returns False."""
        manager = SubAgentManager()
        assert manager.destroy_subagent("ghost") is False

    def test_destroy_all(self):
        """All sub-agents can be destroyed at once."""
        tool_pool = {"search": make_tool("search")}
        manager = SubAgentManager(parent_tool_pool=tool_pool)
        for i in range(3):
            manager.create_subagent(
                SubAgentConfig(name=f"worker_{i}", tool_names=["search"]),
                llm=MockLLM(),
            )
        assert manager.count == 3
        count = manager.destroy_all()
        assert count == 3
        assert manager.count == 0

    def test_duplicate_name_raises(self):
        """Creating a sub-agent with duplicate name raises ValueError."""
        manager = SubAgentManager(parent_tool_pool={"search": make_tool("search")})
        manager.create_subagent(
            SubAgentConfig(name="dup", tool_names=["search"]),
            llm=MockLLM(),
        )
        with pytest.raises(ValueError, match="already exists"):
            manager.create_subagent(
                SubAgentConfig(name="dup", tool_names=["search"]),
                llm=MockLLM(),
            )

    def test_state_tracking(self):
        """Manager tracks sub-agent states correctly."""
        tool_pool = {"search": make_tool("search")}
        manager = SubAgentManager(parent_tool_pool=tool_pool)

        config = SubAgentConfig(name="runner", tool_names=["search"])
        agent = manager.create_subagent(
            config,
            llm=MockLLM([LLMResponse.text("Done")]),
        )

        assert manager.idle_count == 1
        assert manager.active_count == 0

        agent.run_sync("Do work")

        assert manager.completed_count == 1
        assert manager.idle_count == 0

    def test_get_by_state(self):
        """Can filter sub-agents by state."""
        tool_pool = {"search": make_tool("search")}
        manager = SubAgentManager(parent_tool_pool=tool_pool)

        a1 = manager.create_subagent(
            SubAgentConfig(name="idle_one", tool_names=["search"]),
            llm=MockLLM([LLMResponse.text("ok")]),
        )
        a2 = manager.create_subagent(
            SubAgentConfig(name="done_one", tool_names=["search"]),
            llm=MockLLM([LLMResponse.text("ok")]),
        )
        a2.run_sync("work")

        idle = manager.get_by_state(AgentState.IDLE)
        completed = manager.get_by_state(AgentState.COMPLETED)
        assert len(idle) == 1
        assert idle[0].name == "idle_one"
        assert len(completed) == 1
        assert completed[0].name == "done_one"

    def test_list_subagents(self):
        """Can list all sub-agents with their status."""
        tool_pool = {"search": make_tool("search")}
        manager = SubAgentManager(parent_tool_pool=tool_pool)
        manager.create_subagent(
            SubAgentConfig(name="a1", tool_names=["search"]),
            llm=MockLLM(),
        )
        manager.create_subagent(
            SubAgentConfig(name="a2", tool_names=["search"]),
            llm=MockLLM(),
        )
        lst = manager.list_subagents()
        assert len(lst) == 2
        names = {d["name"] for d in lst}
        assert names == {"a1", "a2"}

    def test_status_report(self):
        """Status returns a summary dict."""
        tool_pool = {"search": make_tool("search"), "read": make_tool("read")}
        manager = SubAgentManager(parent_tool_pool=tool_pool, max_concurrent=3)
        manager.create_subagent(
            SubAgentConfig(name="a1", tool_names=["search"]),
            llm=MockLLM(),
        )
        status = manager.status()
        assert status["total"] == 1
        assert status["idle"] == 1
        assert status["max_concurrent"] == 3
        assert "search" in status["parent_tools"]

    def test_concurrency_limit(self):
        """can_create_more respects max_concurrent."""
        tool_pool = {"search": make_tool("search")}
        manager = SubAgentManager(parent_tool_pool=tool_pool, max_concurrent=2)
        assert manager.can_create_more() is True
        manager.create_subagent(SubAgentConfig(name="a1", tool_names=["search"]), llm=MockLLM())
        manager.create_subagent(SubAgentConfig(name="a2", tool_names=["search"]), llm=MockLLM())
        assert manager.can_create_more() is False

    def test_thread_safety(self):
        """Manager is thread-safe for concurrent access."""
        tool_pool = {"search": make_tool("search")}
        manager = SubAgentManager(parent_tool_pool=tool_pool, max_concurrent=10)

        def create_agent(i):
            manager.create_subagent(
                SubAgentConfig(name=f"agent_{i}", tool_names=["search"]),
                llm=MockLLM(),
            )

        threads = [threading.Thread(target=create_agent, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert manager.count == 5


# ═══════════════════════════════════════════════════════════════
#  3. OrchestratorAgent Tests
# ═══════════════════════════════════════════════════════════════


class TestOrchestratorAgent:
    """OrchestratorAgent 任务分解与并行执行测试."""

    def test_decompose_line_based(self):
        """Orchestrator can decompose tasks (line-based format)."""
        orch_llm = MockLLM([
            LLMResponse.text(
                "SUBTASK: Research Python asyncio\n"
                "SUBTASK: Analyze the findings\n"
                "SUBTASK: Write a summary report"
            ),
        ])
        orchestrator = OrchestratorAgent(llm=orch_llm, tool_pool={})

        subtasks = asyncio.run(orchestrator.decompose("Research and analyze asyncio"))

        assert len(subtasks) == 3
        assert "Research" in subtasks[0].description
        assert "Analyze" in subtasks[1].description
        assert "Write" in subtasks[2].description
        assert subtasks[0].index == 0
        assert subtasks[2].index == 2

    def test_decompose_json_format(self):
        """Orchestrator can parse JSON-formatted decomposition."""
        orch_llm = MockLLM([
            LLMResponse.text('{"subtasks": ["Task A", "Task B", "Task C"]}'),
        ])
        orchestrator = OrchestratorAgent(llm=orch_llm)

        subtasks = asyncio.run(orchestrator.decompose("Do ABC"))

        assert len(subtasks) == 3
        assert subtasks[0].description == "Task A"
        assert subtasks[1].description == "Task B"
        assert subtasks[2].description == "Task C"

    def test_decompose_numbered_format(self):
        """Orchestrator can parse numbered list format."""
        orch_llm = MockLLM([
            LLMResponse.text(
                "1. First step\n"
                "2. Second step\n"
                "3. Third step"
            ),
        ])
        orchestrator = OrchestratorAgent(llm=orch_llm)

        subtasks = asyncio.run(orchestrator.decompose("Multi-step task"))

        assert len(subtasks) == 3
        assert "First step" in subtasks[0].description

    def test_decompose_fallback_single(self):
        """When LLM returns no parseable subtasks, fallback to single task."""
        orch_llm = MockLLM([
            LLMResponse.text("I don't know how to decompose this."),
        ])
        orchestrator = OrchestratorAgent(llm=orch_llm)

        subtasks = asyncio.run(orchestrator.decompose("Unclear task"))

        assert len(subtasks) == 1
        assert subtasks[0].description == "Unclear task"

    def test_dispatch_parallel(self):
        """Orchestrator dispatches subtasks in parallel via ThreadPoolExecutor."""
        tool_pool = {
            "search": make_tool("search", "search result"),
            "read_file": make_tool("read_file", "file content"),
        }

        # Orchestrator LLM: decompose, then aggregate
        orch_llm = MockLLM([
            LLMResponse.text("SUBTASK: Find info\nSUBTASK: Read details"),
            LLMResponse.text("Aggregated result from both subtasks."),
        ])

        orchestrator = OrchestratorAgent(
            llm=orch_llm,
            tool_pool=tool_pool,
            max_workers=4,
        )
        orchestrator.register_subagent(
            SubAgentConfig(name="worker", tool_names=["search", "read_file"]),
            llm=MockLLM([LLMResponse.text("Subtask completed")]),
        )

        # Dispatch with explicit subtasks
        subtasks = [
            SubTask(description="Find info", subagent_name="worker", index=0),
            SubTask(description="Read details", subagent_name="worker", index=1),
        ]
        results = orchestrator.dispatch(subtasks)

        assert len(results) == 2
        assert all(r.success for r in results)
        assert "completed" in results[0].content.lower()

    def test_full_run_sync(self):
        """Full orchestration: decompose → dispatch → aggregate."""
        tool_pool = {
            "search": make_tool("search", "found it"),
        }

        # Orchestrator LLM: 1) decompose, 2) aggregate
        orch_llm = MockLLM([
            LLMResponse.text("SUBTASK: Search for topic A\nSUBTASK: Search for topic B"),
            LLMResponse.text("Combined findings from topic A and B."),
        ])

        orchestrator = OrchestratorAgent(
            llm=orch_llm,
            tool_pool=tool_pool,
            max_workers=4,
        )
        orchestrator.register_subagent(
            SubAgentConfig(name="researcher", tool_names=["search"]),
            llm=MockLLM([LLMResponse.text("Found relevant information.")]),
        )

        result = orchestrator.run_sync("Research topics A and B")

        assert result.success
        assert result.subtask_count == 2
        assert result.failed_count == 0
        assert "Combined" in result.content
        assert len(result.subtask_results) == 2
        assert all(r.success for r in result.subtask_results)

    def test_orchestrator_failure_isolation(self):
        """One sub-agent failure doesn't prevent others from completing."""
        tool_pool = {"search": make_tool("search")}

        orch_llm = MockLLM([
            LLMResponse.text("SUBTASK: Task 1\nSUBTASK: Task 2"),
            LLMResponse.text("Partial results aggregated."),
        ])

        orchestrator = OrchestratorAgent(
            llm=orch_llm,
            tool_pool=tool_pool,
        )

        # Use a factory: first subtask succeeds, second fails
        call_count = [0]

        def factory(subtask):
            call_count[0] += 1
            if call_count[0] == 1:
                return SubAgentConfig(name="good", tool_names=["search"]), MockLLM([
                    LLMResponse.text("Success!")
                ])
            else:
                # Return an LLM that raises
                class FailingLLM:
                    async def chat(self, messages, tools, system_prompt):
                        raise RuntimeError("LLM crashed")
                return SubAgentConfig(name="bad", tool_names=["search"]), FailingLLM()

        subtasks = [
            SubTask(description="Task 1", index=0),
            SubTask(description="Task 2", index=1),
        ]
        results = orchestrator.dispatch(subtasks, subagent_factory=factory)

        assert len(results) == 2
        # At least one should succeed
        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]
        assert len(successes) >= 1
        assert len(failures) >= 1

    def test_orchestrator_with_registered_subagents(self):
        """Orchestrator uses registered sub-agent configs for dispatch."""
        tool_pool = {"search": make_tool("search"), "read": make_tool("read")}

        orch_llm = MockLLM([
            LLMResponse.text("SUBTASK: Do A\nSUBTASK: Do B"),
            LLMResponse.text("Aggregated."),
        ])

        orchestrator = OrchestratorAgent(llm=orch_llm, tool_pool=tool_pool)
        orchestrator.register_subagent(
            SubAgentConfig(name="worker_a", tool_names=["search"]),
            llm=MockLLM([LLMResponse.text("A done")]),
        )
        orchestrator.register_subagent(
            SubAgentConfig(name="worker_b", tool_names=["read"]),
            llm=MockLLM([LLMResponse.text("B done")]),
        )

        assert "worker_a" in orchestrator.registered_subagents
        assert "worker_b" in orchestrator.registered_subagents

        result = orchestrator.run_sync("Do A and B")
        assert result.success
        assert result.subtask_count == 2

    def test_orchestrator_status(self):
        """Orchestrator provides a status summary."""
        tool_pool = {"search": make_tool("search")}
        orch = OrchestratorAgent(
            llm=MockLLM(),
            tool_pool=tool_pool,
            max_workers=2,
        )
        orch.register_subagent(
            SubAgentConfig(name="worker", tool_names=["search"]),
            llm=MockLLM(),
        )
        status = orch.status()
        assert status["name"] == "orchestrator"
        assert status["max_workers"] == 2
        assert "search" in status["tool_pool"]
        assert "worker" in status["registered_subagents"]

    def test_orchestrator_permission_intersection_in_dispatch(self):
        """Sub-agents in dispatch get permission-intersected tools."""
        tool_pool = {
            "search": make_tool("search"),
            "read_file": make_tool("read_file"),
            "write_file": make_tool("write_file"),
        }

        orch_llm = MockLLM([
            LLMResponse.text("SUBTASK: Research"),
            LLMResponse.text("Done."),
        ])

        orchestrator = OrchestratorAgent(llm=orch_llm, tool_pool=tool_pool)

        # Sub-agent declares search + delete_file (delete not in pool)
        orchestrator.register_subagent(
            SubAgentConfig(
                name="researcher",
                tool_names=["search", "read_file", "delete_file"],
            ),
            llm=MockLLM([LLMResponse.text("Researched")]),
        )

        result = orchestrator.run_sync("Research something")
        assert result.success

        # Check that the sub-agent only got intersection tools
        subagent = orchestrator.subagent_manager.get_subagent("researcher")
        assert subagent is not None
        assert subagent.tool_names == {"search", "read_file"}
        assert "delete_file" not in subagent.tool_names

    def test_last_subtasks_tracked(self):
        """Orchestrator tracks the last decomposition."""
        orch_llm = MockLLM([
            LLMResponse.text("SUBTASK: Task X\nSUBTASK: Task Y"),
            LLMResponse.text("Aggregated."),
        ])
        orchestrator = OrchestratorAgent(llm=orch_llm)
        orchestrator.register_subagent(
            SubAgentConfig(name="w"),
            llm=MockLLM([LLMResponse.text("ok")]),
        )

        orchestrator.run_sync("Do X and Y")

        assert len(orchestrator.last_subtasks) == 2
        assert "Task X" in orchestrator.last_subtasks[0].description


# ═══════════════════════════════════════════════════════════════
#  4. Pipeline Tests
# ═══════════════════════════════════════════════════════════════


class TestPipeline:
    """Pipeline 管道链串行数据流测试."""

    def test_pipeline_basic(self):
        """Pipeline passes output of each stage to the next."""
        agent1 = AgentInstance(
            AgentConfig(name="stage1"),
            llm=MockLLM([LLMResponse.text("Stage 1 output")]),
        )
        agent2 = AgentInstance(
            AgentConfig(name="stage2"),
            llm=MockLLM([LLMResponse.text("Stage 2 processed: Stage 1 output")]),
        )
        agent3 = AgentInstance(
            AgentConfig(name="stage3"),
            llm=MockLLM([LLMResponse.text("Final: Stage 2 processed: Stage 1 output")]),
        )

        pipeline = Pipeline([
            PipelineStage(agent=agent1, name="extract"),
            PipelineStage(agent=agent2, name="analyze"),
            PipelineStage(agent=agent3, name="report"),
        ])

        result = pipeline.run_sync("Raw input data")

        assert result.success
        assert result.final_output == "Final: Stage 2 processed: Stage 1 output"
        assert len(result.stage_outputs) == 3
        assert result.stage_outputs[0] == ("extract", "Stage 1 output")
        assert result.stage_outputs[1] == ("analyze", "Stage 2 processed: Stage 1 output")

    def test_pipeline_single_stage(self):
        """Pipeline with one stage works correctly."""
        agent = AgentInstance(
            AgentConfig(name="only"),
            llm=MockLLM([LLMResponse.text("Only output")]),
        )
        pipeline = Pipeline([PipelineStage(agent=agent)])
        result = pipeline.run_sync("Input")
        assert result.success
        assert result.final_output == "Only output"

    def test_pipeline_stage_names_default(self):
        """Stage names default to agent names."""
        agent1 = AgentInstance(AgentConfig(name="alpha"), llm=MockLLM())
        agent2 = AgentInstance(AgentConfig(name="beta"), llm=MockLLM())
        pipeline = Pipeline([
            PipelineStage(agent=agent1),
            PipelineStage(agent=agent2),
        ])
        assert pipeline.stage_names == ["alpha", "beta"]

    def test_pipeline_transform(self):
        """Pipeline applies transform function before passing to agent."""
        agent = AgentInstance(
            AgentConfig(name="transformed"),
            llm=MockLLM([LLMResponse.text("Processed")]),
        )
        pipeline = Pipeline([
            PipelineStage(
                agent=agent,
                transform=lambda x: f"PREFIX: {x}",
            ),
        ])
        result = pipeline.run_sync("original")
        assert result.success
        assert result.final_output == "Processed"

    def test_pipeline_failure_stops(self):
        """Pipeline stops on stage failure."""
        # Agent with very low budget → budget exhaustion → partial result
        agent1 = AgentInstance(
            AgentConfig(
                name="stage1",
                budget_config=BudgetConfig(max_turns=1, max_tokens=1),
            ),
            # This response has tool calls, so it won't terminate naturally
            # and will exhaust the budget on the next turn
            llm=MockLLM([
                LLMResponse.action("nonexistent_tool", {}),
            ]),
        )
        agent2 = AgentInstance(
            AgentConfig(name="stage2"),
            llm=MockLLM([LLMResponse.text("Should not reach")]),
        )
        pipeline = Pipeline([
            PipelineStage(agent=agent1, name="first"),
            PipelineStage(agent=agent2, name="second"),
        ])

        result = pipeline.run_sync("input")

        assert not result.success
        assert result.failed_stage == "first"
        # Second stage should not have run
        assert len(result.stage_outputs) < 2

    def test_pipeline_exception_handling(self):
        """Pipeline handles exceptions gracefully."""
        class CrashingAgent:
            name = "crasher"
            config = AgentConfig(name="crasher")
            state = AgentState.IDLE
            is_idle = True
            is_terminated = False
            can_spawn_subagents = False
            tool_names = set()
            last_result = None
            instance_id = "crasher"

            async def run(self, task):
                raise RuntimeError("Agent crashed!")

            def run_sync(self, task):
                raise RuntimeError("Agent crashed!")

            def to_dict(self):
                return {"name": "crasher", "state": "idle"}

        pipeline = Pipeline([
            PipelineStage(agent=CrashingAgent(), name="crash_stage"),  # type: ignore
        ])

        result = pipeline.run_sync("input")
        assert not result.success
        assert result.failed_stage == "crash_stage"
        assert "crashed" in result.error

    def test_pipeline_empty_raises(self):
        """Empty pipeline raises ValueError."""
        with pytest.raises(ValueError, match="at least one stage"):
            Pipeline([])

    def test_pipeline_async_run(self):
        """Pipeline can run asynchronously."""
        agent = AgentInstance(
            AgentConfig(name="async_stage"),
            llm=MockLLM([LLMResponse.text("Async result")]),
        )
        pipeline = Pipeline([PipelineStage(agent=agent)])

        async def _run():
            return await pipeline.run("input")

        result = asyncio.run(_run())
        assert result.success
        assert result.final_output == "Async result"


# ═══════════════════════════════════════════════════════════════
#  5. Blackboard Tests
# ═══════════════════════════════════════════════════════════════


class TestBlackboard:
    """Blackboard 共享黑板读写与订阅测试."""

    def test_write_and_read(self):
        """Can write and read values."""
        bb = Blackboard()
        bb.write("research", "findings", {"topic": "AI", "summary": "Great"})
        data = bb.read("research", "findings")
        assert data == {"topic": "AI", "summary": "Great"}

    def test_read_nonexistent(self):
        """Reading non-existent key returns None."""
        bb = Blackboard()
        assert bb.read("missing", "key") is None
        assert bb.read("existing", "missing") is None

    def test_write_overwrite(self):
        """Writing to existing key updates value and increments version."""
        bb = Blackboard()
        bb.write("tasks", "task1", "v1")
        bb.write("tasks", "task1", "v2")

        entry = bb.read_entry("tasks", "task1")
        assert entry is not None
        assert entry.value == "v2"
        assert entry.version == 2

    def test_partitions(self):
        """Partitions provide namespace isolation."""
        bb = Blackboard()
        bb.write("partition_a", "key1", "value_a")
        bb.write("partition_b", "key1", "value_b")

        assert bb.read("partition_a", "key1") == "value_a"
        assert bb.read("partition_b", "key1") == "value_b"
        assert "partition_a" in bb.list_partitions()
        assert "partition_b" in bb.list_partitions()

    def test_read_partition(self):
        """Can read all key-values in a partition."""
        bb = Blackboard()
        bb.write("data", "key1", "val1")
        bb.write("data", "key2", "val2")
        bb.write("other", "key3", "val3")

        all_data = bb.read_partition("data")
        assert all_data == {"key1": "val1", "key2": "val2"}

    def test_delete(self):
        """Can delete individual keys."""
        bb = Blackboard()
        bb.write("data", "key1", "val1")
        assert bb.delete("data", "key1") is True
        assert bb.read("data", "key1") is None
        assert bb.delete("data", "key1") is False

    def test_clear_partition(self):
        """Can clear all entries in a partition."""
        bb = Blackboard()
        bb.write("data", "k1", "v1")
        bb.write("data", "k2", "v2")
        count = bb.clear_partition("data")
        assert count == 2
        assert bb.read_partition("data") == {}

    def test_subscribe(self):
        """Subscribers are notified on writes."""
        bb = Blackboard()
        notifications = []

        unsub = bb.subscribe("research", lambda entry: notifications.append(entry))

        bb.write("research", "key1", "value1")
        assert len(notifications) == 1
        assert notifications[0].value == "value1"
        assert notifications[0].partition == "research"
        assert notifications[0].key == "key1"

        # Unsubscribe
        unsub()
        bb.write("research", "key2", "value2")
        assert len(notifications) == 1  # No new notification

    def test_subscribe_multiple(self):
        """Multiple subscribers all receive notifications."""
        bb = Blackboard()
        received_a = []
        received_b = []

        bb.subscribe("data", lambda e: received_a.append(e))
        bb.subscribe("data", lambda e: received_b.append(e))

        bb.write("data", "key", "value")

        assert len(received_a) == 1
        assert len(received_b) == 1
        assert bb.subscriber_count("data") == 2

    def test_subscribe_partition_isolation(self):
        """Subscribers only receive notifications for their partition."""
        bb = Blackboard()
        research_notifications = []
        analysis_notifications = []

        bb.subscribe("research", lambda e: research_notifications.append(e))
        bb.subscribe("analysis", lambda e: analysis_notifications.append(e))

        bb.write("research", "key", "val")
        assert len(research_notifications) == 1
        assert len(analysis_notifications) == 0

    def test_subscriber_error_isolation(self):
        """Subscriber errors don't break the blackboard."""
        bb = Blackboard()

        def bad_callback(entry):
            raise RuntimeError("Subscriber crashed")

        bb.subscribe("data", bad_callback)

        # Write should not raise despite bad subscriber
        bb.write("data", "key", "value")
        assert bb.read("data", "key") == "value"

    def test_list_keys(self):
        """Can list all keys in a partition."""
        bb = Blackboard()
        bb.write("data", "k1", "v1")
        bb.write("data", "k2", "v2")
        keys = bb.list_keys("data")
        assert set(keys) == {"k1", "k2"}

    def test_total_entries(self):
        """Can count total entries across partitions."""
        bb = Blackboard()
        bb.write("a", "k1", "v1")
        bb.write("a", "k2", "v2")
        bb.write("b", "k3", "v3")
        assert bb.total_entries() == 3

    def test_author_tracking(self):
        """Blackboard tracks who wrote each entry."""
        bb = Blackboard()
        bb.write("data", "key", "value", author="agent_1")
        entry = bb.read_entry("data", "key")
        assert entry.author == "agent_1"

    def test_thread_safety(self):
        """Blackboard is thread-safe for concurrent writes."""
        bb = Blackboard()

        def write_data(partition):
            for i in range(20):
                bb.write(partition, f"key_{i}", f"value_{i}")

        threads = [
            threading.Thread(target=write_data, args=(f"part_{p}",))
            for p in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert bb.total_entries() == 80
        for p in range(4):
            assert len(bb.list_keys(f"part_{p}")) == 20


# ═══════════════════════════════════════════════════════════════
#  6. Voting Tests
# ═══════════════════════════════════════════════════════════════


class TestVoting:
    """Voting 投票决策三种策略测试."""

    def test_majority_basic(self):
        """Majority voting: most votes wins."""
        voting = Voting(strategy=VotingStrategy.MAJORITY)
        voting.add_vote("agent1", "option_a")
        voting.add_vote("agent2", "option_b")
        voting.add_vote("agent3", "option_a")

        result = voting.decide()
        assert result.winner == "option_a"
        assert result.strategy == VotingStrategy.MAJORITY
        assert result.tallies["option_a"] == 2.0
        assert result.tallies["option_b"] == 1.0
        assert result.total_votes == 3
        assert not result.is_tie

    def test_majority_tie(self):
        """Majority voting detects ties."""
        voting = Voting(strategy=VotingStrategy.MAJORITY)
        voting.add_vote("agent1", "option_a")
        voting.add_vote("agent2", "option_b")

        result = voting.decide()
        assert result.is_tie
        assert result.margin == 0.0

    def test_majority_margin(self):
        """Majority voting calculates margin correctly."""
        voting = Voting(strategy=VotingStrategy.MAJORITY)
        voting.add_vote("a1", "X")
        voting.add_vote("a2", "X")
        voting.add_vote("a3", "X")
        voting.add_vote("a4", "Y")
        voting.add_vote("a5", "Y")

        result = voting.decide()
        assert result.winner == "X"
        assert result.margin == 1.0  # 3 - 2

    def test_weighted_basic(self):
        """Weighted voting: highest total weight wins."""
        voting = Voting(strategy=VotingStrategy.WEIGHTED)
        voting.add_vote("agent1", "option_a", weight=2.0)
        voting.add_vote("agent2", "option_b", weight=1.0)
        voting.add_vote("agent3", "option_a", weight=1.5)

        result = voting.decide()
        assert result.winner == "option_a"
        assert result.tallies["option_a"] == 3.5
        assert result.tallies["option_b"] == 1.0
        assert result.margin == 2.5

    def test_weighted_upset(self):
        """Weighted voting: minority can win with higher weights."""
        voting = Voting(strategy=VotingStrategy.WEIGHTED)
        # 3 votes for B (weight 1 each = 3.0) vs 1 vote for A (weight 5.0)
        voting.add_vote("a1", "B", weight=1.0)
        voting.add_vote("a2", "B", weight=1.0)
        voting.add_vote("a3", "B", weight=1.0)
        voting.add_vote("a4", "A", weight=5.0)

        result = voting.decide()
        assert result.winner == "A"  # Weighted upsets majority
        assert result.tallies["A"] == 5.0
        assert result.tallies["B"] == 3.0

    def test_confidence_basic(self):
        """Confidence voting: highest total confidence wins."""
        voting = Voting(strategy=VotingStrategy.CONFIDENCE)
        voting.add_vote("agent1", "option_a", confidence=0.9)
        voting.add_vote("agent2", "option_b", confidence=0.7)
        voting.add_vote("agent3", "option_a", confidence=0.8)

        result = voting.decide()
        assert result.winner == "option_a"
        assert result.tallies["option_a"] == pytest.approx(1.7)
        assert result.tallies["option_b"] == pytest.approx(0.7)

    def test_confidence_upset(self):
        """Confidence voting: fewer high-confidence votes can win."""
        voting = Voting(strategy=VotingStrategy.CONFIDENCE)
        # 3 low-confidence votes for B vs 1 high-confidence vote for A
        voting.add_vote("a1", "B", confidence=0.3)
        voting.add_vote("a2", "B", confidence=0.3)
        voting.add_vote("a3", "B", confidence=0.3)
        voting.add_vote("a4", "A", confidence=0.95)

        result = voting.decide()
        assert result.winner == "A"  # 0.95 > 0.9
        assert result.tallies["A"] == pytest.approx(0.95)
        assert result.tallies["B"] == pytest.approx(0.9)

    def test_no_votes(self):
        """Voting with no votes returns empty winner."""
        voting = Voting(strategy=VotingStrategy.MAJORITY)
        result = voting.decide()
        assert result.winner == ""
        assert result.total_votes == 0
        assert result.tallies == {}

    def test_single_vote(self):
        """Single vote always wins."""
        voting = Voting(strategy=VotingStrategy.MAJORITY)
        voting.add_vote("agent1", "only_option")
        result = voting.decide()
        assert result.winner == "only_option"
        assert not result.is_tie

    def test_reset(self):
        """Voting can be reset for a new round."""
        voting = Voting(strategy=VotingStrategy.MAJORITY)
        voting.add_vote("a1", "X")
        voting.add_vote("a2", "Y")
        assert voting.vote_count == 2

        voting.reset()
        assert voting.vote_count == 0
        assert voting.choices == set()

    def test_choices_property(self):
        """Voting tracks all unique choices."""
        voting = Voting(strategy=VotingStrategy.MAJORITY)
        voting.add_vote("a1", "X")
        voting.add_vote("a2", "Y")
        voting.add_vote("a3", "Z")
        voting.add_vote("a4", "X")

        assert voting.choices == {"X", "Y", "Z"}

    def test_vote_with_reason(self):
        """Votes can include reasoning."""
        voting = Voting(strategy=VotingStrategy.MAJORITY)
        vote = voting.add_vote("agent1", "option_a", reason="It's the safest choice")
        assert vote.reason == "It's the safest choice"

        result = voting.decide()
        assert result.votes[0].reason == "It's the safest choice"

    def test_add_vote_obj(self):
        """Can add pre-constructed Vote objects."""
        voting = Voting(strategy=VotingStrategy.WEIGHTED)
        voting.add_vote_obj(Vote(voter="a1", choice="X", weight=3.0))
        voting.add_vote_obj(Vote(voter="a2", choice="Y", weight=1.0))

        result = voting.decide()
        assert result.winner == "X"

    def test_three_way_vote(self):
        """Voting works with three or more options."""
        voting = Voting(strategy=VotingStrategy.MAJORITY)
        voting.add_vote("a1", "A")
        voting.add_vote("a2", "B")
        voting.add_vote("a3", "C")
        voting.add_vote("a4", "A")
        voting.add_vote("a5", "B")

        result = voting.decide()
        assert result.winner == "A"  # A has 2, B has 2, C has 1 → tie between A and B
        # Actually A and B both have 2 votes → tie
        assert result.is_tie

    def test_default_strategy_is_majority(self):
        """Default voting strategy is majority."""
        voting = Voting()
        assert voting.strategy == VotingStrategy.MAJORITY


# ═══════════════════════════════════════════════════════════════
#  7. Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestMultiAgentIntegration:
    """集成场景测试：编排者 + 管道 + 黑板 + 投票."""

    def test_orchestrator_with_blackboard(self):
        """Orchestrator dispatches sub-agents that share results via blackboard."""
        tool_pool = {"search": make_tool("search", "found")}
        bb = Blackboard()

        # Sub-agent writes to blackboard
        class BlackboardAgent:
            """Mock agent that writes to blackboard."""
            def __init__(self, name, bb, llm):
                self.name = name
                self._bb = bb
                self._llm = llm
                self.config = AgentConfig(name=name)
                self.state = AgentState.IDLE
                self.is_idle = True
                self.is_terminated = False
                self.can_spawn_subagents = False
                self.tool_names = set()
                self.last_result = None
                self.instance_id = name

            async def run(self, task):
                self.state = AgentState.RUNNING
                result = await self._llm.chat(
                    [{"role": "user", "content": task}], [], "You are a worker."
                )
                self._bb.write("results", self.name, result.content, author=self.name)
                self.state = AgentState.COMPLETED
                from suyi.core.loop import LoopResult
                return LoopResult(content=result.content, stop_reason="natural")

            def run_sync(self, task):
                return asyncio.run(self.run(task))

            def to_dict(self):
                return {"name": self.name, "state": self.state.value}

        # Not using BlackboardAgent for this test — use standard agents
        orch_llm = MockLLM([
            LLMResponse.text("SUBTASK: Find info about X\nSUBTASK: Find info about Y"),
            LLMResponse.text("Aggregated X and Y info."),
        ])

        orchestrator = OrchestratorAgent(llm=orch_llm, tool_pool=tool_pool)
        orchestrator.register_subagent(
            SubAgentConfig(name="finder_x", tool_names=["search"]),
            llm=MockLLM([LLMResponse.text("Found X info")]),
        )
        orchestrator.register_subagent(
            SubAgentConfig(name="finder_y", tool_names=["search"]),
            llm=MockLLM([LLMResponse.text("Found Y info")]),
        )

        result = orchestrator.run_sync("Find info about X and Y")
        assert result.success
        assert result.subtask_count == 2

    def test_pipeline_then_voting(self):
        """Pipeline output can be used for voting decisions."""
        # Three agents process the same input through a pipeline
        agents = []
        for i in range(3):
            agent = AgentInstance(
                AgentConfig(name=f"analyzer_{i}"),
                llm=MockLLM([LLMResponse.text(f"Analysis_{i}")]),
            )
            agents.append(agent)

        # Run each agent's pipeline
        results = []
        for agent in agents:
            pipeline = Pipeline([PipelineStage(agent=agent)])
            result = pipeline.run_sync("Analyze this data")
            results.append(result.final_output)

        # Vote on the best analysis
        voting = Voting(strategy=VotingStrategy.MAJORITY)
        # Simulate votes based on results
        voting.add_vote("judge1", results[0])
        voting.add_vote("judge2", results[0])
        voting.add_vote("judge3", results[1])

        vote_result = voting.decide()
        assert vote_result.winner == "Analysis_0"
        assert vote_result.total_votes == 3

    def test_orchestrator_full_lifecycle(self):
        """Full lifecycle: orchestrator creates, runs, and cleans up sub-agents."""
        tool_pool = {"search": make_tool("search")}

        orch_llm = MockLLM([
            LLMResponse.text("SUBTASK: Task 1\nSUBTASK: Task 2\nSUBTASK: Task 3"),
            LLMResponse.text("All three tasks completed successfully."),
        ])

        orchestrator = OrchestratorAgent(
            llm=orch_llm,
            tool_pool=tool_pool,
            max_workers=3,
        )
        orchestrator.register_subagent(
            SubAgentConfig(name="worker", tool_names=["search"]),
            llm=MockLLM([LLMResponse.text("Task done")]),
        )

        # Before run
        assert orchestrator.subagent_count == 0

        result = orchestrator.run_sync("Do three tasks")

        # After run
        assert result.success
        assert result.subtask_count == 3
        assert result.failed_count == 0
        assert all(r.success for r in result.subtask_results)

        # Sub-agents were created during dispatch
        assert orchestrator.subagent_count > 0

        # All sub-agents should be in COMPLETED state
        status = orchestrator.subagent_manager.status()
        assert status["completed"] == status["total"]

    def test_blackboard_as_shared_memory(self):
        """Multiple agents can communicate via blackboard."""
        bb = Blackboard()

        # Agent 1 writes research findings
        bb.write("research", "topic", "Python asyncio", author="researcher")
        bb.write("research", "summary", "Asyncio is great for IO-bound tasks", author="researcher")

        # Agent 2 reads and writes analysis
        topic = bb.read("research", "topic")
        summary = bb.read("research", "summary")
        bb.write("analysis", "conclusion", f"Based on '{topic}': {summary}", author="analyst")

        # Agent 3 reads analysis and writes final report
        conclusion = bb.read("analysis", "conclusion")
        bb.write("report", "final", f"FINAL REPORT: {conclusion}", author="reporter")

        final = bb.read("report", "final")
        assert "FINAL REPORT" in final
        assert "Python asyncio" in final
        assert "Asyncio is great" in final

        # Verify all partitions
        assert set(bb.list_partitions()) == {"research", "analysis", "report"}
        assert bb.total_entries() == 4

    def test_voting_with_orchestrator_results(self):
        """Voting can be used to select best orchestrator result."""
        # Simulate two orchestrator runs with different results
        result_a = OrchestratorResult(
            content="Approach A: Use ThreadPoolExecutor",
            subtask_count=3,
            success=True,
        )
        result_b = OrchestratorResult(
            content="Approach B: Use asyncio.gather",
            subtask_count=3,
            success=True,
        )

        # Three judges vote
        voting = Voting(strategy=VotingStrategy.WEIGHTED)
        voting.add_vote("judge1", "A", weight=2.0, confidence=0.9)
        voting.add_vote("judge2", "B", weight=1.5, confidence=0.7)
        voting.add_vote("judge3", "A", weight=1.0, confidence=0.8)

        decision = voting.decide()
        assert decision.winner == "A"
        assert decision.tallies["A"] == 3.0
        assert decision.tallies["B"] == 1.5
