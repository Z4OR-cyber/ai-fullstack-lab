"""Tests for Swarm Coordinator — 自治多智能体协作。"""

import pytest

from suyi.agents.swarm import (
    TaskStatus,
    SharedTask,
    SwarmGoal,
    SwarmAgentInfo,
    SharedTaskBoard,
    SwarmCoordinator,
)
from suyi.agents.base import AgentInstance, AgentConfig
from suyi.core.loop import MockLLM, LLMResponse


def _make_agent(name: str, responses=None):
    """创建测试用 agent。"""
    if responses is None:
        responses = [LLMResponse.text(f"Output from {name}")]
    config = AgentConfig(name=name, description=f"Test agent {name}")
    return AgentInstance(config=config, llm=MockLLM(responses))


class TestSharedTask:
    """SharedTask 数据结构测试。"""

    def test_creation(self):
        task = SharedTask(
            title="Test task",
            description="A test task",
            required_capabilities={"research"},
        )
        assert task.title == "Test task"
        assert task.status == TaskStatus.PENDING
        assert task.id

    def test_to_dict(self):
        task = SharedTask(title="Test", required_capabilities={"a", "b"})
        d = task.to_dict()
        assert d["title"] == "Test"
        assert set(d["required_capabilities"]) == {"a", "b"}
        assert d["status"] == "pending"


class TestSwarmGoal:
    """SwarmGoal 数据结构测试。"""

    def test_creation(self):
        goal = SwarmGoal(
            objective="Research AI agents",
            constraints=["No external APIs"],
            max_agents=3,
            hitl_threshold=0.7,
            required_capabilities={"research"},
        )
        assert goal.objective == "Research AI agents"
        assert goal.max_agents == 3
        assert goal.hitl_threshold == 0.7
        assert "research" in goal.required_capabilities


class TestSharedTaskBoard:
    """SharedTaskBoard 共享任务板测试。"""

    def test_publish_and_get(self):
        board = SharedTaskBoard()
        task = board.publish(SharedTask(title="Test"))
        assert board.total_tasks == 1
        assert board.get_task(task.id) is not None

    def test_claim(self):
        board = SharedTaskBoard()
        task = board.publish(SharedTask(title="Test"))
        claimed = board.claim(task.id, "agent1")
        assert claimed is not None
        assert claimed.status == TaskStatus.CLAIMED
        assert claimed.assigned_agent == "agent1"

    def test_claim_already_claimed(self):
        board = SharedTaskBoard()
        task = board.publish(SharedTask(title="Test"))
        board.claim(task.id, "agent1")
        # 再次认领应该失败
        result = board.claim(task.id, "agent2")
        assert result is None

    def test_update_status(self):
        board = SharedTaskBoard()
        task = board.publish(SharedTask(title="Test"))
        board.claim(task.id, "agent1")
        updated = board.update_status(
            task.id, TaskStatus.COMPLETED, output_data={"result": "done"}
        )
        assert updated.status == TaskStatus.COMPLETED
        assert updated.output_data == {"result": "done"}

    def test_get_pending_tasks(self):
        board = SharedTaskBoard()
        board.publish(SharedTask(title="T1", priority=1))
        board.publish(SharedTask(title="T2", priority=3))
        board.publish(SharedTask(title="T3", priority=2))

        pending = board.get_pending_tasks()
        assert len(pending) == 3
        # 按优先级排序
        assert pending[0].title == "T2"  # priority=3

    def test_get_pending_with_capability_filter(self):
        board = SharedTaskBoard()
        board.publish(SharedTask(title="T1", required_capabilities={"research"}))
        board.publish(SharedTask(title="T2", required_capabilities={"writing"}))

        # 只有 research 能力的 agent 只能看到 T1
        pending = board.get_pending_tasks(capabilities={"research"})
        assert len(pending) == 1
        assert pending[0].title == "T1"

    def test_get_tasks_by_status(self):
        board = SharedTaskBoard()
        t1 = board.publish(SharedTask(title="T1"))
        t2 = board.publish(SharedTask(title="T2"))
        board.update_status(t1.id, TaskStatus.COMPLETED)

        completed = board.get_tasks_by_status(TaskStatus.COMPLETED)
        assert len(completed) == 1
        pending = board.get_tasks_by_status(TaskStatus.PENDING)
        assert len(pending) == 1

    def test_get_tasks_by_agent(self):
        board = SharedTaskBoard()
        t1 = board.publish(SharedTask(title="T1"))
        board.claim(t1.id, "agent1")

        tasks = board.get_tasks_by_agent("agent1")
        assert len(tasks) == 1

    def test_subscribe(self):
        board = SharedTaskBoard()
        notifications = []
        unsub = board.subscribe(lambda t: notifications.append(t))

        task = board.publish(SharedTask(title="Test"))
        assert len(notifications) == 1

        board.claim(task.id, "agent1")
        assert len(notifications) == 2

        unsub()
        board.update_status(task.id, TaskStatus.COMPLETED)
        assert len(notifications) == 2  # 取消订阅后不再收到

    def test_clear_completed(self):
        board = SharedTaskBoard()
        t1 = board.publish(SharedTask(title="T1"))
        t2 = board.publish(SharedTask(title="T2"))
        board.update_status(t1.id, TaskStatus.COMPLETED)

        cleared = board.clear_completed()
        assert cleared == 1
        assert board.total_tasks == 1

    def test_properties(self):
        board = SharedTaskBoard()
        t1 = board.publish(SharedTask(title="T1"))
        t2 = board.publish(SharedTask(title="T2"))
        board.update_status(t1.id, TaskStatus.COMPLETED)

        assert board.total_tasks == 2
        assert board.pending_count == 1
        assert board.completed_count == 1

    def test_repr(self):
        board = SharedTaskBoard()
        assert "SharedTaskBoard" in repr(board)


class TestSwarmAgentInfo:
    """SwarmAgentInfo agent 信息测试。"""

    def test_can_accept_task(self):
        agent = _make_agent("a1")
        info = SwarmAgentInfo(
            agent_id="a1",
            agent=agent,
            capability_tags={"research", "writing"},
        )
        assert info.can_accept_task({"research"}) is True
        assert info.can_accept_task({"coding"}) is False
        assert info.can_accept_task(set()) is True

    def test_max_concurrent(self):
        agent = _make_agent("a1")
        info = SwarmAgentInfo(
            agent_id="a1",
            agent=agent,
            capability_tags={"research"},
            max_concurrent_tasks=2,
        )
        assert info.can_accept_task({"research"}) is True
        info.current_task_count = 2
        assert info.can_accept_task({"research"}) is False


class TestSwarmCoordinator:
    """SwarmCoordinator 协调器测试。"""

    def test_register_agent(self):
        swarm = SwarmCoordinator()
        agent = _make_agent("a1")
        info = swarm.register_agent("a1", agent, capability_tags={"research"})
        assert info.agent_id == "a1"
        assert swarm.get_agent_info("a1") is not None
        assert len(swarm.list_agents()) == 1

    def test_unregister_agent(self):
        swarm = SwarmCoordinator()
        agent = _make_agent("a1")
        swarm.register_agent("a1", agent)
        assert swarm.unregister_agent("a1") is True
        assert swarm.get_agent_info("a1") is None

    def test_find_capable_agents(self):
        swarm = SwarmCoordinator()
        swarm.register_agent("a1", _make_agent("a1"), capability_tags={"research"})
        swarm.register_agent("a2", _make_agent("a2"), capability_tags={"writing"})

        capable = swarm.find_capable_agents({"research"})
        assert len(capable) == 1
        assert capable[0].agent_id == "a1"

    def test_publish_task(self):
        swarm = SwarmCoordinator()
        task = SharedTask(title="Test")
        published = swarm.publish_task(task)
        assert swarm.task_board.get_task(task.id) is not None

    def test_decompose_goal(self):
        swarm = SwarmCoordinator()
        goal = SwarmGoal(objective="Test goal")
        sub_tasks = [
            {"title": "T1", "required_capabilities": {"research"}, "priority": 2},
            {"title": "T2", "required_capabilities": {"writing"}, "priority": 1},
        ]
        published = swarm.decompose_goal(goal, sub_tasks)
        assert len(published) == 2
        assert swarm.task_board.total_tasks == 2

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """成功执行任务。"""
        swarm = SwarmCoordinator()
        swarm.register_agent(
            "a1", _make_agent("a1", [LLMResponse.text("Research done")]),
            capability_tags={"research"},
        )

        goal = SwarmGoal(objective="Research", max_agents=1, hitl_threshold=0.0)
        swarm.publish_task(SharedTask(
            title="Research task",
            description="Do research",
            required_capabilities={"research"},
            input_data={"prompt": "Research AI agents"},
        ))

        result = await swarm.execute(goal)
        assert result["completed"] == 1
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_execute_no_capable_agents(self):
        """无可用 agent。"""
        swarm = SwarmCoordinator()
        swarm.register_agent("a1", _make_agent("a1"), capability_tags={"writing"})

        goal = SwarmGoal(objective="Research", max_agents=1)
        swarm.publish_task(SharedTask(
            title="Research",
            required_capabilities={"research"},
        ))

        result = await swarm.execute(goal)
        assert result["success"] is False
        assert "No capable agents" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_execute_with_guardrails(self):
        """带 Guardrails 集成执行。"""
        # 创建简单的 mock guardrails
        class MockGuardrails:
            def filter_input(self, content):
                class Result:
                    passed = True
                    reason = ""
                return Result()

            def validate(self, content):
                class Result:
                    valid = True
                    reason = ""
                return Result()

        swarm = SwarmCoordinator(guardrails=MockGuardrails())
        swarm.register_agent(
            "a1", _make_agent("a1", [LLMResponse.text("Done")]),
            capability_tags={"research"},
        )

        goal = SwarmGoal(objective="Test", max_agents=1, hitl_threshold=0.0)
        swarm.publish_task(SharedTask(
            title="Task",
            required_capabilities={"research"},
            input_data={"prompt": "Do something"},
        ))

        result = await swarm.execute(goal)
        assert result["completed"] == 1

    @pytest.mark.asyncio
    async def test_execute_guardrails_blocks_input(self):
        """Guardrails 阻止输入。"""
        class BlockingGuardrails:
            def filter_input(self, content):
                class Result:
                    passed = False
                    reason = "Blocked content"
                return Result()

        swarm = SwarmCoordinator(guardrails=BlockingGuardrails())
        swarm.register_agent(
            "a1", _make_agent("a1", [LLMResponse.text("Done")]),
            capability_tags={"research"},
        )

        goal = SwarmGoal(objective="Test", max_agents=1, hitl_threshold=0.0)
        swarm.publish_task(SharedTask(
            title="Task",
            required_capabilities={"research"},
            input_data={"prompt": "Blocked content"},
        ))

        result = await swarm.execute(goal)
        assert result["failed"] == 1

    @pytest.mark.asyncio
    async def test_execute_multiple_agents(self):
        """多个 agent 并行执行。"""
        swarm = SwarmCoordinator()
        swarm.register_agent(
            "a1", _make_agent("a1", [LLMResponse.text("Result A")]),
            capability_tags={"research"},
        )
        swarm.register_agent(
            "a2", _make_agent("a2", [LLMResponse.text("Result B")]),
            capability_tags={"writing"},
        )

        goal = SwarmGoal(objective="Multi-task", max_agents=2, hitl_threshold=0.0)
        swarm.publish_task(SharedTask(
            title="Research", required_capabilities={"research"},
            input_data={"prompt": "Research"},
        ))
        swarm.publish_task(SharedTask(
            title="Write", required_capabilities={"writing"},
            input_data={"prompt": "Write"},
        ))

        result = await swarm.execute(goal)
        assert result["completed"] == 2

    def test_get_status(self):
        """获取状态。"""
        swarm = SwarmCoordinator()
        swarm.register_agent("a1", _make_agent("a1"), capability_tags={"research"})
        swarm.publish_task(SharedTask(title="T1"))

        status = swarm.get_status()
        assert status["agents"] == 1
        assert status["task_board"]["total"] == 1

    def test_get_execution_log(self):
        """获取执行日志。"""
        swarm = SwarmCoordinator()
        assert swarm.get_execution_log() == []

    def test_repr(self):
        """repr 方法。"""
        swarm = SwarmCoordinator()
        assert "SwarmCoordinator" in repr(swarm)
