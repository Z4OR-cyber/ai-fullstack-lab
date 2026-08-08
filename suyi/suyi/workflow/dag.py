"""DAG 定义 — 节点(Node)和边(Edge)，支持条件分支、并行节点、循环检测。

提供:
    - Node: 工作流节点（携带异步执行函数）
    - Edge: 连接边（可带条件函数）
    - DAG: 有向无环图（添加节点/边、拓扑排序、循环检测）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


# ── 节点状态 ──────────────────────────────────────────────────

class NodeStatus(str, Enum):
    """节点执行状态。"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# ── 节点 ──────────────────────────────────────────────────────

@dataclass
class Node:
    """工作流节点。

    Attributes:
        id: 节点唯一标识。
        name: 节点名称。
        handler: 异步执行函数 async (context) -> Any。
        config: 节点配置（如重试次数、超时等）。
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    handler: Optional[Callable] = None
    config: Dict[str, Any] = field(default_factory=dict)

    # 运行时状态
    status: NodeStatus = NodeStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    attempts: int = 0

    @property
    def max_retries(self) -> int:
        return self.config.get("max_retries", 3)

    @property
    def timeout(self) -> float:
        return self.config.get("timeout", 30.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "attempts": self.attempts,
            "error": self.error,
        }

    def __repr__(self) -> str:
        return f"Node(id={self.id[:8]}, name={self.name!r}, status={self.status.value})"


# ── 边 ────────────────────────────────────────────────────────

@dataclass
class Edge:
    """工作流边 — 连接两个节点。

    Attributes:
        source: 源节点 ID。
        target: 目标节点 ID。
        condition: 条件函数 (context) -> bool，为 True 时才走这条边。
        name: 边名称（用于调试）。
    """

    source: str
    target: str
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    name: str = ""

    def should_traverse(self, context: Dict[str, Any]) -> bool:
        """检查是否应该走这条边。"""
        if self.condition is None:
            return True
        try:
            return bool(self.condition(context))
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "name": self.name,
            "has_condition": self.condition is not None,
        }


# ── DAG ───────────────────────────────────────────────────────

class DAGValidationError(Exception):
    """DAG 验证错误。"""


class DAG:
    """有向无环图 — 工作流定义。

    管理节点和边，提供拓扑排序和循环检测。
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self._adjacency: Dict[str, List[str]] = {}

    def add_node(self, node: Node) -> Node:
        """添加节点。"""
        if node.id in self.nodes:
            raise DAGValidationError(f"Node '{node.id}' already exists")
        self.nodes[node.id] = node
        self._adjacency.setdefault(node.id, [])
        return node

    def add_edge(
        self,
        source: str,
        target: str,
        condition: Optional[Callable] = None,
        name: str = "",
    ) -> Edge:
        """添加边。

        Args:
            source: 源节点 ID。
            target: 目标节点 ID。
            condition: 条件函数。
            name: 边名称。

        Returns:
            创建的 Edge。

        Raises:
            DAGValidationError: 如果节点不存在或添加边后形成环。
        """
        if source not in self.nodes:
            raise DAGValidationError(f"Source node '{source}' does not exist")
        if target not in self.nodes:
            raise DAGValidationError(f"Target node '{target}' does not exist")

        edge = Edge(source=source, target=target, condition=condition, name=name)
        self.edges.append(edge)
        self._adjacency.setdefault(source, []).append(target)

        # 检测环
        if self._has_cycle():
            self.edges.pop()
            self._adjacency[source].remove(target)
            raise DAGValidationError(
                f"Adding edge {source} -> {target} would create a cycle"
            )

        return edge

    def remove_node(self, node_id: str) -> None:
        """移除节点及其所有关联边。"""
        if node_id not in self.nodes:
            return
        del self.nodes[node_id]
        self._adjacency.pop(node_id, None)
        self.edges = [
            e for e in self.edges if e.source != node_id and e.target != node_id
        ]
        # 清理邻接表
        for src in self._adjacency:
            self._adjacency[src] = [
                t for t in self._adjacency[src] if t != node_id
            ]

    def get_roots(self) -> List[Node]:
        """获取入度为 0 的根节点。"""
        targets = {e.target for e in self.edges}
        return [self.nodes[nid] for nid in self.nodes if nid not in targets]

    def get_leaves(self) -> List[Node]:
        """获取出度为 0 的叶子节点。"""
        sources = {e.source for e in self.edges}
        return [self.nodes[nid] for nid in self.nodes if nid not in sources]

    def get_successors(self, node_id: str, context: Optional[Dict[str, Any]] = None) -> List[Node]:
        """获取节点的后继节点（考虑条件边）。

        Args:
            node_id: 节点 ID。
            context: 上下文（用于条件判断）。

        Returns:
            后继节点列表。
        """
        ctx = context or {}
        result: List[Node] = []
        for edge in self.edges:
            if edge.source == node_id and edge.should_traverse(ctx):
                target = self.nodes.get(edge.target)
                if target:
                    result.append(target)
        return result

    def get_predecessors(self, node_id: str) -> List[Node]:
        """获取节点的前驱节点。"""
        result: List[Node] = []
        for edge in self.edges:
            if edge.target == node_id:
                source = self.nodes.get(edge.source)
                if source:
                    result.append(source)
        return result

    def topological_sort(self) -> List[str]:
        """拓扑排序，返回节点 ID 列表。

        Raises:
            DAGValidationError: 如果图中存在环。
        """
        if self._has_cycle():
            raise DAGValidationError("DAG contains a cycle, cannot sort")

        # Kahn's algorithm
        in_degree: Dict[str, int] = {nid: 0 for nid in self.nodes}
        for edge in self.edges:
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result: List[str] = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)
            for successor in self._adjacency.get(node_id, []):
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)

        if len(result) != len(self.nodes):
            raise DAGValidationError("DAG contains a cycle, cannot sort")

        return result

    def _has_cycle(self) -> bool:
        """检测是否有环（DFS）。"""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {nid: WHITE for nid in self.nodes}

        def dfs(node_id: str) -> bool:
            color[node_id] = GRAY
            for neighbor in self._adjacency.get(node_id, []):
                if color.get(neighbor, WHITE) == GRAY:
                    return True
                if color.get(neighbor, WHITE) == WHITE:
                    if dfs(neighbor):
                        return True
            color[node_id] = BLACK
            return False

        for nid in self.nodes:
            if color[nid] == WHITE:
                if dfs(nid):
                    return True
        return False

    def get_parallel_groups(self) -> List[List[str]]:
        """获取可并行执行的节点组（按拓扑层级分组）。

        Returns:
            节点 ID 组列表，每组内的节点可并行执行。
        """
        if self._has_cycle():
            raise DAGValidationError("DAG contains a cycle")

        in_degree: Dict[str, int] = {nid: 0 for nid in self.nodes}
        for edge in self.edges:
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        groups: List[List[str]] = []
        current_level = [nid for nid, deg in in_degree.items() if deg == 0]
        visited: Set[str] = set()

        while current_level:
            groups.append(current_level)
            next_level: List[str] = []
            for nid in current_level:
                visited.add(nid)
                for successor in self._adjacency.get(nid, []):
                    in_degree[successor] -= 1
                    if in_degree[successor] == 0 and successor not in visited:
                        next_level.append(successor)
            current_level = next_level

        return groups

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
        }

    def __repr__(self) -> str:
        return f"DAG(nodes={self.node_count}, edges={self.edge_count})"


__all__ = [
    "Node",
    "NodeStatus",
    "Edge",
    "DAG",
    "DAGValidationError",
]
