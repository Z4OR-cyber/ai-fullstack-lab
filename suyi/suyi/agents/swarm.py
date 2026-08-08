"""Swarm Coordinator — 自治多智能体协作模式。

实现 SwarmCoordinator + SharedTaskBoard（黑板模式）:
    - Agent 能力标签匹配（capability_tags）
    - SwarmGoal 数据结构: {objective, constraints, max_agents, hitl_threshold}
    - 与 Guardrails 集成: 每个 Agent 操作过 Guardrails 检查

工作流程:
    1. 创建 SwarmGoal（目标、约束、最大 agent 数、HITL 阈值）
    2. SwarmCoordinator 分解目标为子任务，发布到 SharedTaskBoard
    3. 有匹配能力的 Agent 认领并执行任务
    4. 每次操作经过 Guardrails 检查
    5. 结果写回 SharedTaskBoard
    6. 超过 hitl_threshold 的操作触发人工审查
"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .base import AgentInstance
from ..core.loop import LoopResult


# ── 任务状态枚举 ──────────────────────────────────────────────

class TaskStatus(str, Enum):
    """共享任务板上任务的状态。"""

    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NEEDS_REVIEW = "needs_review"


# ── 任务数据结构 ──────────────────────────────────────────────

@dataclass
class SharedTask:
    """共享任务板上的单个任务。

    Attributes:
        id: 任务 ID。
        title: 任务标题。
        description: 任务描述。
        required_capabilities: 所需能力标签集合。
        assigned_agent: 被分配的 agent ID。
        status: 任务状态。
        input_data: 输入数据。
        output_data: 输出数据。
        priority: 优先级（数字越大越优先）。
        created_at: 创建时间。
        updated_at: 更新时间。
        error: 错误信息。
        guardrails_checked: 是否通过 Guardrails 检查。
    """

    title: str
    description: str = ""
    required_capabilities: Set[str] = field(default_factory=set)
    input_data: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    assigned_agent: str = ""
    status: TaskStatus = TaskStatus.PENDING
    output_data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error: str = ""
    guardrails_checked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "required_capabilities": list(self.required_capabilities),
            "input_data": self.input_data,
            "assigned_agent": self.assigned_agent,
            "status": self.status.value,
            "output_data": self.output_data,
            "priority": self.priority,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
            "guardrails_checked": self.guardrails_checked,
        }

    def __repr__(self) -> str:
        return (
            f"SharedTask(id={self.id[:8]}, title={self.title!r}, "
            f"status={self.status.value}, "
            f"agent={self.assigned_agent!r})"
        )


# ── SwarmGoal 数据结构 ────────────────────────────────────────

@dataclass
class SwarmGoal:
    """Swarm 目标定义。

    Attributes:
        objective: 目标描述。
        constraints: 约束条件列表。
        max_agents: 最大 agent 数量。
        hitl_threshold: 触发人工审查的阈值（0-1，表示置信度低于此值时需要人工审查）。
        required_capabilities: 完成目标所需的能力标签集合。
        deadline: 可选的截止时间（Unix 时间戳）。
    """

    objective: str
    constraints: List[str] = field(default_factory=list)
    max_agents: int = 5
    hitl_threshold: float = 0.7
    required_capabilities: Set[str] = field(default_factory=set)
    deadline: Optional[float] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __repr__(self) -> str:
        return (
            f"SwarmGoal(id={self.id[:8]}, "
            f"objective={self.objective[:30]!r}, "
            f"max_agents={self.max_agents})"
        )


# ── Agent 注册信息 ────────────────────────────────────────────

@dataclass
class SwarmAgentInfo:
    """Swarm 中注册的 agent 信息。

    Attributes:
        agent_id: agent 标识。
        agent: AgentInstance 实例。
        capability_tags: 能力标签集合。
        max_concurrent_tasks: 最大并发任务数。
        current_task_count: 当前正在执行的任务数。
    """

    agent_id: str
    agent: AgentInstance
    capability_tags: Set[str] = field(default_factory=set)
    max_concurrent_tasks: int = 1
    current_task_count: int = 0

    def can_accept_task(self, required_capabilities: Set[str]) -> bool:
        """检查 agent 是否能接受任务。"""
        if self.current_task_count >= self.max_concurrent_tasks:
            return False
        # 能力标签匹配: agent 的能力必须包含所有所需能力
        if required_capabilities and not required_capabilities.issubset(self.capability_tags):
            return False
        return True

    def __repr__(self) -> str:
        return (
            f"SwarmAgentInfo(id={self.agent_id!r}, "
            f"tags={self.capability_tags}, "
            f"tasks={self.current_task_count}/{self.max_concurrent_tasks})"
        )


# ── SharedTaskBoard ───────────────────────────────────────────

class SharedTaskBoard:
    """共享任务板 — 黑板模式实现。

    线程安全的共享任务管理，支持:
        - 发布任务
        - 认领任务（能力匹配）
        - 更新任务状态
        - 订阅任务变更

    Attributes:
        tasks: 所有任务字典 (task_id → SharedTask)。
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, SharedTask] = {}
        self._lock = threading.RLock()
        self._subscribers: List[Callable[[SharedTask], None]] = []

    def publish(self, task: SharedTask) -> SharedTask:
        """发布新任务到任务板。

        Args:
            task: 要发布的任务。

        Returns:
            已发布的任务。
        """
        with self._lock:
            self._tasks[task.id] = task
            subscribers = list(self._subscribers)

        for callback in subscribers:
            try:
                callback(task)
            except Exception:
                pass

        return task

    def claim(
        self,
        task_id: str,
        agent_id: str,
        required_capabilities: Optional[Set[str]] = None,
    ) -> Optional[SharedTask]:
        """认领任务。

        Args:
            task_id: 任务 ID。
            agent_id: 认领的 agent ID。
            required_capabilities: 如果提供，验证 agent 能力。

        Returns:
            认领的任务，如果认领失败则返回 None。
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status != TaskStatus.PENDING:
                return None

            task.assigned_agent = agent_id
            task.status = TaskStatus.CLAIMED
            task.updated_at = time.time()
            subscribers = list(self._subscribers)

        for callback in subscribers:
            try:
                callback(task)
            except Exception:
                pass

        return task

    def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        output_data: Optional[Dict[str, Any]] = None,
        error: str = "",
    ) -> Optional[SharedTask]:
        """更新任务状态。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            task.status = status
            task.updated_at = time.time()
            if output_data is not None:
                task.output_data = output_data
            if error:
                task.error = error
            subscribers = list(self._subscribers)

        for callback in subscribers:
            try:
                callback(task)
            except Exception:
                pass

        return task

    def get_pending_tasks(
        self,
        capabilities: Optional[Set[str]] = None,
    ) -> List[SharedTask]:
        """获取待处理任务。

        Args:
            capabilities: 如果提供，只返回能力匹配的任务。

        Returns:
            待处理任务列表（按优先级排序）。
        """
        with self._lock:
            pending = [
                t for t in self._tasks.values()
                if t.status == TaskStatus.PENDING
            ]

        if capabilities is not None:
            pending = [
                t for t in pending
                if not t.required_capabilities
                or t.required_capabilities.issubset(capabilities)
            ]

        pending.sort(key=lambda t: t.priority, reverse=True)
        return pending

    def get_task(self, task_id: str) -> Optional[SharedTask]:
        """获取单个任务。"""
        with self._lock:
            return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[SharedTask]:
        """获取所有任务。"""
        with self._lock:
            return list(self._tasks.values())

    def get_tasks_by_status(self, status: TaskStatus) -> List[SharedTask]:
        """按状态获取任务。"""
        with self._lock:
            return [t for t in self._tasks.values() if t.status == status]

    def get_tasks_by_agent(self, agent_id: str) -> List[SharedTask]:
        """获取分配给某 agent 的所有任务。"""
        with self._lock:
            return [t for t in self._tasks.values() if t.assigned_agent == agent_id]

    def subscribe(self, callback: Callable[[SharedTask], None]) -> Callable[[], None]:
        """订阅任务变更。"""
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe():
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    def clear_completed(self) -> int:
        """清除已完成/失败/取消的任务。

        Returns:
            清除的任务数。
        """
        with self._lock:
            to_remove = [
                tid for tid, t in self._tasks.items()
                if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            ]
            for tid in to_remove:
                del self._tasks[tid]
            return len(to_remove)

    @property
    def total_tasks(self) -> int:
        """总任务数。"""
        with self._lock:
            return len(self._tasks)

    @property
    def pending_count(self) -> int:
        """待处理任务数。"""
        with self._lock:
            return sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING)

    @property
    def completed_count(self) -> int:
        """已完成任务数。"""
        with self._lock:
            return sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED)

    def __repr__(self) -> str:
        return f"SharedTaskBoard(total={self.total_tasks}, pending={self.pending_count})"


# ── SwarmCoordinator ──────────────────────────────────────────

class SwarmCoordinator:
    """Swarm 协调器 — 自治多智能体协作。

    管理一组 agent，通过 SharedTaskBoard 分配和执行任务。
    支持 Guardrails 集成和 HITL 阈值检查。

    Usage::

        swarm = SwarmCoordinator()
        swarm.register_agent("researcher", agent, tags={"research", "search"})
        swarm.register_agent("writer", agent2, tags={"writing", "summarize"})

        goal = SwarmGoal(
            objective="Research and write a report on AI agents",
            max_agents=2,
            hitl_threshold=0.6,
        )

        # 发布子任务
        swarm.publish_task(SharedTask(
            title="Research",
            required_capabilities={"research"},
            input_data={"topic": "AI agents"},
        ))

        result = await swarm.execute(goal)
    """

    def __init__(
        self,
        task_board: Optional[SharedTaskBoard] = None,
        guardrails: Optional[Any] = None,
    ) -> None:
        """初始化 Swarm 协调器。

        Args:
            task_board: 共享任务板（None 时自动创建）。
            guardrails: Guardrails 实例（ContentFilter/OutputValidator），
                        用于检查每个 agent 的输入和输出。
        """
        self.task_board = task_board or SharedTaskBoard()
        self.guardrails = guardrails
        self._agents: Dict[str, SwarmAgentInfo] = {}
        self._lock = threading.RLock()
        # 执行日志
        self.execution_log: List[Dict[str, Any]] = []

    # ── Agent 管理 ────────────────────────────────────────────

    def register_agent(
        self,
        agent_id: str,
        agent: AgentInstance,
        capability_tags: Optional[Set[str]] = None,
        max_concurrent_tasks: int = 1,
    ) -> SwarmAgentInfo:
        """注册 agent 到 swarm。"""
        with self._lock:
            info = SwarmAgentInfo(
                agent_id=agent_id,
                agent=agent,
                capability_tags=capability_tags or set(),
                max_concurrent_tasks=max_concurrent_tasks,
            )
            self._agents[agent_id] = info
            return info

    def unregister_agent(self, agent_id: str) -> bool:
        """注销 agent。"""
        with self._lock:
            return self._agents.pop(agent_id, None) is not None

    def get_agent_info(self, agent_id: str) -> Optional[SwarmAgentInfo]:
        """获取 agent 信息。"""
        with self._lock:
            return self._agents.get(agent_id)

    def list_agents(self) -> List[SwarmAgentInfo]:
        """列出所有已注册的 agent。"""
        with self._lock:
            return list(self._agents.values())

    def find_capable_agents(
        self,
        required_capabilities: Set[str],
    ) -> List[SwarmAgentInfo]:
        """查找有指定能力的 agent。"""
        with self._lock:
            return [
                info for info in self._agents.values()
                if info.can_accept_task(required_capabilities)
            ]

    # ── 任务管理 ──────────────────────────────────────────────

    def publish_task(self, task: SharedTask) -> SharedTask:
        """发布任务到任务板。"""
        return self.task_board.publish(task)

    def decompose_goal(
        self,
        goal: SwarmGoal,
        sub_tasks: List[Dict[str, Any]],
    ) -> List[SharedTask]:
        """将目标分解为子任务并发布。

        Args:
            goal: Swarm 目标。
            sub_tasks: 子任务定义列表，每个字典包含:
                - title: 任务标题
                - description: 任务描述
                - required_capabilities: 所需能力集合
                - input_data: 输入数据
                - priority: 优先级

        Returns:
            已发布的 SharedTask 列表。
        """
        published: List[SharedTask] = []
        for st_def in sub_tasks:
            task = SharedTask(
                title=st_def.get("title", "Untitled"),
                description=st_def.get("description", ""),
                required_capabilities=set(st_def.get("required_capabilities", set())),
                input_data=st_def.get("input_data", {}),
                priority=st_def.get("priority", 0),
            )
            published.append(self.publish_task(task))
        return published

    # ── Guardrails 集成 ────────────────────────────────────────

    def _check_guardrails_input(self, content: str) -> tuple[bool, str]:
        """检查输入是否通过 Guardrails。

        Returns:
            (是否通过, 原因/错误信息)。
        """
        if self.guardrails is None:
            return True, ""
        try:
            if hasattr(self.guardrails, "filter_input"):
                result = self.guardrails.filter_input(content)
                # FilterResult 通常有 passed 属性
                if hasattr(result, "passed"):
                    return result.passed, getattr(result, "reason", "")
                elif isinstance(result, dict):
                    return result.get("passed", True), result.get("reason", "")
        except Exception as e:
            return False, f"Guardrails error: {e}"
        return True, ""

    def _check_guardrails_output(self, content: str) -> tuple[bool, str]:
        """检查输出是否通过 Guardrails。

        Returns:
            (是否通过, 原因/错误信息)。
        """
        if self.guardrails is None:
            return True, ""
        try:
            if hasattr(self.guardrails, "validate"):
                result = self.guardrails.validate(content)
                if hasattr(result, "valid"):
                    return result.valid, getattr(result, "reason", "")
                elif isinstance(result, dict):
                    return result.get("valid", True), result.get("reason", "")
            elif hasattr(self.guardrails, "filter_output"):
                result = self.guardrails.filter_output(content)
                if hasattr(result, "passed"):
                    return result.passed, getattr(result, "reason", "")
        except Exception as e:
            return False, f"Guardrails error: {e}"
        return True, ""

    # ── 任务执行 ──────────────────────────────────────────────

    async def _execute_task(
        self,
        task: SharedTask,
        agent_info: SwarmAgentInfo,
        goal: SwarmGoal,
    ) -> Dict[str, Any]:
        """执行单个任务。

        Returns:
            执行结果字典。
        """
        log_entry: Dict[str, Any] = {
            "task_id": task.id,
            "task_title": task.title,
            "agent_id": agent_info.agent_id,
            "start_time": time.time(),
        }

        # 标记任务为运行中
        self.task_board.update_status(task.id, TaskStatus.RUNNING)
        agent_info.current_task_count += 1

        # 准备输入
        input_text = task.input_data.get("prompt", task.description or task.title)

        # Guardrails 输入检查
        passed, reason = self._check_guardrails_input(input_text)
        task.guardrails_checked = passed
        if not passed:
            log_entry["status"] = "blocked_by_guardrails"
            log_entry["error"] = f"Input blocked: {reason}"
            log_entry["end_time"] = time.time()
            self.execution_log.append(log_entry)
            self.task_board.update_status(
                task.id, TaskStatus.FAILED, error=f"Input blocked: {reason}"
            )
            agent_info.current_task_count -= 1
            return {"success": False, "error": f"Input blocked: {reason}"}

        # 执行 agent
        try:
            loop_result: LoopResult = await agent_info.agent.run(input_text)
            output = loop_result.content or ""
            success = loop_result.is_complete
            error = "" if success else loop_result.stop_reason
        except Exception as e:
            output = ""
            success = False
            error = str(e)

        # Guardrails 输出检查
        if success and output:
            passed, reason = self._check_guardrails_output(output)
            if not passed:
                success = False
                error = f"Output blocked: {reason}"
                task.guardrails_checked = False

        # HITL 阈值检查
        needs_review = False
        if success and goal.hitl_threshold > 0:
            # 如果 agent 结果置信度低于阈值，标记需要人工审查
            confidence = 1.0  # 默认高置信度
            # 如果 loop_result 有 metadata 中的置信度信息
            if hasattr(loop_result, "metadata") and loop_result.metadata:
                confidence = loop_result.metadata.get("confidence", 1.0)
            if confidence < goal.hitl_threshold:
                needs_review = True

        # 更新任务状态
        output_data = {"output": output, "agent_id": agent_info.agent_id}
        if needs_review:
            self.task_board.update_status(task.id, TaskStatus.NEEDS_REVIEW, output_data)
        elif success:
            self.task_board.update_status(task.id, TaskStatus.COMPLETED, output_data)
        else:
            self.task_board.update_status(task.id, TaskStatus.FAILED, output_data, error)

        agent_info.current_task_count -= 1

        log_entry["status"] = "completed" if success else "failed"
        log_entry["needs_review"] = needs_review
        log_entry["error"] = error
        log_entry["end_time"] = time.time()
        log_entry["duration"] = log_entry["end_time"] - log_entry["start_time"]
        self.execution_log.append(log_entry)

        return {
            "success": success,
            "output": output,
            "needs_review": needs_review,
            "error": error,
        }

    async def execute(self, goal: SwarmGoal) -> Dict[str, Any]:
        """执行 Swarm 目标。

        从任务板获取待处理任务，分配给有能力且空闲的 agent 执行。

        Args:
            goal: Swarm 目标。

        Returns:
            执行结果摘要。
        """
        results: List[Dict[str, Any]] = []
        active_agents = 0
        max_agents = min(goal.max_agents, len(self._agents))

        # 获取待处理任务
        pending_tasks = self.task_board.get_pending_tasks()

        # 为每个任务找到合适的 agent
        task_agent_pairs: List[tuple[SharedTask, SwarmAgentInfo]] = []
        used_agents: Set[str] = set()

        for task in pending_tasks:
            if len(used_agents) >= max_agents:
                break

            capable = self.find_capable_agents(task.required_capabilities)
            for agent_info in capable:
                if agent_info.agent_id not in used_agents:
                    task_agent_pairs.append((task, agent_info))
                    used_agents.add(agent_info.agent_id)
                    break

        if not task_agent_pairs:
            return {
                "success": False,
                "completed": 0,
                "failed": 0,
                "needs_review": 0,
                "total": len(pending_tasks),
                "error": "No capable agents available for pending tasks.",
            }

        # 并行执行任务
        coroutines = [
            self._execute_task(task, agent_info, goal)
            for task, agent_info in task_agent_pairs
        ]
        task_results = await asyncio.gather(*coroutines, return_exceptions=True)

        completed = 0
        failed = 0
        needs_review = 0

        for result in task_results:
            if isinstance(result, Exception):
                failed += 1
                results.append({"success": False, "error": str(result)})
            elif isinstance(result, dict):
                if result.get("needs_review"):
                    needs_review += 1
                elif result.get("success"):
                    completed += 1
                else:
                    failed += 1
                results.append(result)

        return {
            "success": failed == 0,
            "completed": completed,
            "failed": failed,
            "needs_review": needs_review,
            "total": len(task_agent_pairs),
            "results": results,
            "goal_id": goal.id,
        }

    def execute_sync(self, goal: SwarmGoal) -> Dict[str, Any]:
        """同步执行便捷方法。"""
        return asyncio.run(self.execute(goal))

    # ── 状态查询 ──────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """获取 swarm 当前状态。"""
        with self._lock:
            return {
                "agents": len(self._agents),
                "agents_info": [
                    {
                        "agent_id": info.agent_id,
                        "capabilities": list(info.capability_tags),
                        "current_tasks": info.current_task_count,
                        "max_tasks": info.max_concurrent_tasks,
                    }
                    for info in self._agents.values()
                ],
                "task_board": {
                    "total": self.task_board.total_tasks,
                    "pending": self.task_board.pending_count,
                    "completed": self.task_board.completed_count,
                },
                "execution_log_count": len(self.execution_log),
            }

    def get_execution_log(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的执行日志。"""
        return self.execution_log[-limit:]

    def __repr__(self) -> str:
        return (
            f"SwarmCoordinator(agents={len(self._agents)}, "
            f"tasks={self.task_board.total_tasks})"
        )


__all__ = [
    "TaskStatus",
    "SharedTask",
    "SwarmGoal",
    "SwarmAgentInfo",
    "SharedTaskBoard",
    "SwarmCoordinator",
]
