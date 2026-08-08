"""Workflow Engine — DAG 定义与工作流执行引擎。

公共 API:
    - DAG: 有向无环图
    - Node / NodeStatus: 节点与节点状态
    - Edge: 边（可带条件）
    - WorkflowEngine: 工作流执行引擎
    - WorkflowResult: 执行结果
    - FailurePolicy: 失败策略
"""

from .dag import Node, NodeStatus, Edge, DAG, DAGValidationError
from .engine import WorkflowEngine, WorkflowResult, FailurePolicy

__all__ = [
    "DAG",
    "Node",
    "NodeStatus",
    "Edge",
    "DAGValidationError",
    "WorkflowEngine",
    "WorkflowResult",
    "FailurePolicy",
]
