"""工作流引擎 — 拓扑排序执行、并行节点、失败重试、状态追踪。

WorkflowEngine 按照 DAG 的拓扑顺序执行节点:
    - 同一层级的节点使用 asyncio.gather 并行执行
    - 支持条件分支（根据上下文选择走的边）
    - 支持失败重试（可配置每个节点的最大重试次数）
    - 实时状态追踪（记录每个节点的执行状态、结果、错误）
    - 失败策略：STOP（停止执行）、CONTINUE（继续执行后续节点）、RETRY（重试）

Usage::

    dag = DAG()
    n1 = dag.add_node(Node(name="step1", handler=async_fn1))
    n2 = dag.add_node(Node(name="step2", handler=async_fn2))
    dag.add_edge(n1.id, n2.id)

    engine = WorkflowEngine(dag)
    result = await engine.run({"input": "data"})
    print(result.success)
"""

from __future__ import annotations

import asyncio
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .dag import DAG, Node, NodeStatus, Edge, DAGValidationError


# ── 失败策略 ──────────────────────────────────────────────────

class FailurePolicy(str, Enum):
    """节点失败时的策略。"""
    STOP = "stop"        # 停止整个工作流
    CONTINUE = "continue"  # 继续执行其他节点
    RETRY = "retry"      # 重试当前节点


# ── 执行结果 ──────────────────────────────────────────────────

@dataclass
class WorkflowResult:
    """工作流执行结果。"""
    success: bool = True
    context: Dict[str, Any] = field(default_factory=dict)
    node_results: Dict[str, Any] = field(default_factory=dict)
    node_errors: Dict[str, str] = field(default_factory=dict)
    execution_time: float = 0.0
    nodes_executed: int = 0
    nodes_failed: int = 0
    nodes_skipped: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "execution_time": round(self.execution_time, 4),
            "nodes_executed": self.nodes_executed,
            "nodes_failed": self.nodes_failed,
            "nodes_skipped": self.nodes_skipped,
            "node_results": self.node_results,
            "node_errors": self.node_errors,
        }


# ── 工作流引擎 ────────────────────────────────────────────────

class WorkflowEngine:
    """工作流引擎 — 按 DAG 拓扑顺序执行节点。

    Args:
        dag: 要执行的 DAG。
        failure_policy: 默认失败策略。
        default_timeout: 默认节点超时时间（秒）。
    """

    def __init__(
        self,
        dag: DAG,
        failure_policy: FailurePolicy = FailurePolicy.STOP,
        default_timeout: float = 30.0,
    ) -> None:
        self.dag = dag
        self.failure_policy = failure_policy
        self.default_timeout = default_timeout

    async def run(self, context: Optional[Dict[str, Any]] = None) -> WorkflowResult:
        """执行工作流。

        Args:
            context: 初始上下文。

        Returns:
            执行结果。
        """
        ctx = dict(context or {})
        start_time = time.time()
        result = WorkflowResult(context=ctx)

        # 获取拓扑层级
        try:
            groups = self.dag.get_parallel_groups()
        except DAGValidationError as e:
            result.success = False
            result.execution_time = time.time() - start_time
            result.node_errors["__dag__"] = str(e)
            return result

        # 已完成的节点集合
        completed: set[str] = set()
        failed_nodes: set[str] = set()

        for group in groups:
            # 筛选可执行的节点：前驱全部成功且未被跳过
            executable: List[Node] = []
            for node_id in group:
                node = self.dag.nodes[node_id]
                # 检查前驱是否全部完成
                preds = self.dag.get_predecessors(node_id)
                if all(p.id in completed for p in preds):
                    # 检查条件边：至少有一条边从已完成的前驱指向此节点
                    reachable = self._is_reachable(node_id, completed, ctx)
                    if reachable:
                        executable.append(node)
                    else:
                        node.status = NodeStatus.SKIPPED
                        result.nodes_skipped += 1

            if not executable:
                continue

            # 并行执行同层节点
            tasks = [self._execute_node(node, ctx) for node in executable]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)

            for node, outcome in zip(executable, outcomes):
                if isinstance(outcome, Exception):
                    node.status = NodeStatus.FAILED
                    node.error = str(outcome)
                    result.node_errors[node.id] = str(outcome)
                    result.nodes_failed += 1
                    failed_nodes.add(node.id)

                    if self.failure_policy == FailurePolicy.STOP:
                        result.success = False
                        result.execution_time = time.time() - start_time
                        return result
                elif node.status == NodeStatus.SUCCESS:
                    completed.add(node.id)
                    result.node_results[node.id] = node.result
                    result.nodes_executed += 1
                else:
                    # FAILED after retries
                    result.node_errors[node.id] = node.error or "Unknown error"
                    result.nodes_failed += 1
                    failed_nodes.add(node.id)

                    if self.failure_policy == FailurePolicy.STOP:
                        result.success = False
                        result.execution_time = time.time() - start_time
                        return result

        result.execution_time = time.time() - start_time
        result.success = len(failed_nodes) == 0
        return result

    def _is_reachable(
        self,
        node_id: str,
        completed: set[str],
        context: Dict[str, Any],
    ) -> bool:
        """检查节点是否可达（至少有一条从已完成节点出发的条件边为 True）。"""
        # 如果没有前驱，总是可达
        preds = self.dag.get_predecessors(node_id)
        if not preds:
            return True

        for edge in self.dag.edges:
            if edge.target == node_id and edge.source in completed:
                if edge.should_traverse(context):
                    return True

        return False

    async def _execute_node(self, node: Node, context: Dict[str, Any]) -> Node:
        """执行单个节点（含重试）。"""
        max_retries = node.max_retries
        node.status = NodeStatus.RUNNING

        for attempt in range(1, max_retries + 1):
            node.attempts = attempt
            try:
                if node.handler is None:
                    node.result = None
                else:
                    result = node.handler(context)
                    # 支持 sync 和 async handler
                    if asyncio.iscoroutine(result):
                        result = await asyncio.wait_for(
                            result,
                            timeout=node.timeout or self.default_timeout,
                        )
                    node.result = result

                # 将结果存入上下文
                context[node.name or node.id] = node.result
                node.status = NodeStatus.SUCCESS
                node.error = None
                return node

            except asyncio.TimeoutError:
                node.error = f"Timeout after {node.timeout}s (attempt {attempt})"
            except Exception as e:
                node.error = f"{type(e).__name__}: {e}"

            # 如果是最后一次尝试，标记失败
            if attempt < max_retries:
                await asyncio.sleep(0)  # 让出控制权

        node.status = NodeStatus.FAILED
        return node

    def get_node_status(self, node_id: str) -> Optional[NodeStatus]:
        """获取节点状态。"""
        node = self.dag.nodes.get(node_id)
        return node.status if node else None

    def reset(self) -> None:
        """重置所有节点状态。"""
        for node in self.dag.nodes.values():
            node.status = NodeStatus.PENDING
            node.result = None
            node.error = None
            node.attempts = 0


__all__ = [
    "WorkflowEngine",
    "WorkflowResult",
    "FailurePolicy",
    "DAG",
    "Node",
    "NodeStatus",
    "Edge",
    "DAGValidationError",
]
