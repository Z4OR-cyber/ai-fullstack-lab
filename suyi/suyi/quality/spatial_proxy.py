"""
Spatial Topology Proxy — models the spatial / topological relationships
between services in the environment.

This module implements the **Spatial** function of the World Proxy
six-function matrix.  It maintains a directed graph of service nodes
and the edges (relationships) between them, enabling:

- **Topology mapping** — register services and their dependencies.
- **Path finding** — BFS shortest-path between any two services.
- **Bottleneck detection** — identify single points of failure (nodes
  that lie on all paths between critical pairs).
- **Capability lookup** — map a capability to the set of services that
  provide it.
- **Alternative routing** — when a service fails, suggest alternative
  paths through the remaining topology.

Persistence
------------
When a :class:`~suyi.persistence.sqlite_backend.SQLiteBackend` is
injected, the full graph is serialised to JSON and stored under a single
key.  When no backend is provided, an in-memory adjacency list is used.

Usage::

    from suyi.quality.spatial_proxy import (
        ServiceNode,
        ServiceEdge,
        ServiceTopologyMapper,
    )

    mapper = ServiceTopologyMapper()
    mapper.register_node("api-gateway", "gateway", ["routing", "auth"], "/api")
    mapper.register_node("user-svc", "microservice", ["user"], "/users")
    mapper.register_edge("api-gateway", "user-svc", "depends_on", 1.0)

    neighbors = mapper.get_neighbors("api-gateway")
    path = mapper.find_path("api-gateway", "user-svc")
    bottlenecks = mapper.find_bottlenecks()
    caps = mapper.get_capability_map()
"""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from suyi.persistence.sqlite_backend import SQLiteBackend


# ═══════════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════════


class RelationType(Enum):
    """Type of relationship between two service nodes."""

    DEPENDS_ON = auto()    # from_node depends on to_node
    CALLS = auto()         # from_node calls to_node (RPC/API)
    PROVIDES_FOR = auto()  # from_node provides a service for to_node
    REPLICA_OF = auto()    # from_node is a replica of to_node
    CUSTOM = auto()        # user-defined relation

    @classmethod
    def from_label(cls, label: str) -> "RelationType":
        """Create from a human-readable label (case-insensitive).

        Recognised labels: ``depends_on``, ``calls``, ``provides_for``,
        ``replica_of``, ``custom``.
        """
        mapping = {
            "depends_on": cls.DEPENDS_ON,
            "calls": cls.CALLS,
            "provides_for": cls.PROVIDES_FOR,
            "replica_of": cls.REPLICA_OF,
            "custom": cls.CUSTOM,
        }
        key = label.strip().lower()
        if key not in mapping:
            # Unknown labels map to CUSTOM
            return cls.CUSTOM
        return mapping[key]

    @property
    def label(self) -> str:
        """Human-readable label."""
        return self.name.lower()


class NodeHealth(Enum):
    """Health status of a service node."""

    HEALTHY = auto()
    DEGRADED = auto()
    UNHEALTHY = auto()
    UNKNOWN = auto()

    @classmethod
    def from_label(cls, label: str) -> "NodeHealth":
        """Create from a human-readable label (case-insensitive)."""
        mapping = {
            "healthy": cls.HEALTHY,
            "degraded": cls.DEGRADED,
            "unhealthy": cls.UNHEALTHY,
            "unknown": cls.UNKNOWN,
        }
        key = label.strip().lower()
        if key not in mapping:
            return cls.UNKNOWN
        return mapping[key]

    @property
    def label(self) -> str:
        """Human-readable label."""
        return self.name.lower()

    @property
    def is_available(self) -> bool:
        """``True`` when the node can serve traffic (HEALTHY or DEGRADED)."""
        return self in (NodeHealth.HEALTHY, NodeHealth.DEGRADED)


# ═══════════════════════════════════════════════════════════════
#  Dataclasses
# ═══════════════════════════════════════════════════════════════


@dataclass
class ServiceNode:
    """A service node in the topology graph.

    Attributes:
        name:         Unique identifier for the node.
        node_type:    Type of the service (e.g. ``"gateway"``,
                      ``"microservice"``, ``"database"``).
        capabilities: List of capabilities this service provides.
        endpoint:     Endpoint URL or address.
        health:       Current health status.
        metadata:     Optional additional metadata.
    """

    name: str
    node_type: str = "service"
    capabilities: List[str] = field(default_factory=list)
    endpoint: str = ""
    health: NodeHealth = NodeHealth.UNKNOWN
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "name": self.name,
            "node_type": self.node_type,
            "capabilities": list(self.capabilities),
            "endpoint": self.endpoint,
            "health": self.health.name,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceNode":
        """Reconstruct from a dict (produced by :meth:`to_dict`)."""
        health_raw = data.get("health", "UNKNOWN")
        if isinstance(health_raw, str):
            health = NodeHealth.from_label(health_raw)
        elif isinstance(health_raw, NodeHealth):
            health = health_raw
        else:
            health = NodeHealth.UNKNOWN
        return cls(
            name=data.get("name", ""),
            node_type=data.get("node_type", "service"),
            capabilities=list(data.get("capabilities", [])),
            endpoint=data.get("endpoint", ""),
            health=health,
            metadata=dict(data.get("metadata", {})),
        )

    def __repr__(self) -> str:
        return (
            f"ServiceNode(name={self.name!r}, type={self.node_type!r}, "
            f"health={self.health.label}, caps={len(self.capabilities)})"
        )


@dataclass
class ServiceEdge:
    """A directed edge between two service nodes.

    Attributes:
        from_node:     Name of the source node.
        to_node:       Name of the target node.
        relation_type: Type of relationship.
        weight:        Edge weight (higher = stronger dependency).
        metadata:      Optional additional metadata.
    """

    from_node: str
    to_node: str
    relation_type: RelationType = RelationType.DEPENDS_ON
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "from_node": self.from_node,
            "to_node": self.to_node,
            "relation_type": self.relation_type.name,
            "weight": self.weight,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceEdge":
        """Reconstruct from a dict (produced by :meth:`to_dict`)."""
        rel_raw = data.get("relation_type", "DEPENDS_ON")
        if isinstance(rel_raw, str):
            relation_type = RelationType.from_label(rel_raw)
        elif isinstance(rel_raw, RelationType):
            relation_type = rel_raw
        else:
            relation_type = RelationType.DEPENDS_ON
        return cls(
            from_node=data.get("from_node", ""),
            to_node=data.get("to_node", ""),
            relation_type=relation_type,
            weight=float(data.get("weight", 1.0)),
            metadata=dict(data.get("metadata", {})),
        )

    def __repr__(self) -> str:
        return (
            f"ServiceEdge({self.from_node!r} → {self.to_node!r}, "
            f"rel={self.relation_type.label}, w={self.weight:.1f})"
        )


# ═══════════════════════════════════════════════════════════════
#  ServiceTopologyMapper
# ═══════════════════════════════════════════════════════════════


class ServiceTopologyMapper:
    """Maintains a directed graph of service nodes and edges.

    The mapper uses an adjacency-list representation internally and
    supports:

    - **Node/edge registration** — add services and relationships.
    - **Neighbour queries** — find direct neighbours of a node.
    - **Path finding** — BFS shortest-path between two nodes.
    - **Bottleneck detection** — find nodes that lie on all paths
      between every source-sink pair (single points of failure).
    - **Capability mapping** — map capabilities to providing nodes.
    - **Alternative routing** — when a node fails, suggest detours.

    Args:
        backend: Optional :class:`SQLiteBackend` for persistence.
    """

    #: Key under which the full graph is persisted.
    _STORAGE_KEY: str = "spatial:topology"

    def __init__(self, backend: Optional[SQLiteBackend] = None) -> None:
        self._backend = backend
        self._nodes: Dict[str, ServiceNode] = {}
        # Adjacency list: node_name -> list of (target, edge)
        self._adj: Dict[str, List[Tuple[str, ServiceEdge]]] = defaultdict(list)
        # Reverse adjacency: node_name -> list of (source, edge)
        self._radj: Dict[str, List[Tuple[str, ServiceEdge]]] = defaultdict(list)
        # Load from backend if available
        if self._backend is not None:
            self._load_from_backend()

    # ------------------------------------------------------------------
    #  Node registration
    # ------------------------------------------------------------------

    def register_node(
        self,
        name: str,
        node_type: str = "service",
        capabilities: Optional[List[str]] = None,
        endpoint: str = "",
        health: NodeHealth = NodeHealth.UNKNOWN,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceNode:
        """Register a service node.

        If a node with the same name already exists, it is updated
        with the new attributes (edges are preserved).

        Args:
            name:         Unique node identifier.
            node_type:    Type of the service.
            capabilities: List of capability strings.
            endpoint:     Endpoint URL or address.
            health:       Health status.
            metadata:     Optional metadata dict.

        Returns:
            The registered :class:`ServiceNode`.
        """
        node = ServiceNode(
            name=name,
            node_type=node_type,
            capabilities=capabilities or [],
            endpoint=endpoint,
            health=health,
            metadata=metadata or {},
        )
        self._nodes[name] = node
        # Ensure adjacency entries exist
        if name not in self._adj:
            self._adj[name] = []
        if name not in self._radj:
            self._radj[name] = []
        self._persist()
        return node

    def update_node_health(self, name: str, health: NodeHealth) -> bool:
        """Update the health status of a registered node.

        Args:
            name:   Node name.
            health: New health status.

        Returns:
            ``True`` if the node was found and updated.
        """
        node = self._nodes.get(name)
        if node is None:
            return False
        node.health = health
        self._persist()
        return True

    # ------------------------------------------------------------------
    #  Edge registration
    # ------------------------------------------------------------------

    def register_edge(
        self,
        from_node: str,
        to_node: str,
        relation_type: RelationType = RelationType.DEPENDS_ON,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ServiceEdge]:
        """Register a directed edge between two nodes.

        Both nodes must already be registered.  If either node does not
        exist, the edge is not created and ``None`` is returned.

        If an edge with the same ``(from, to, relation_type)`` already
        exists, its weight and metadata are updated.

        Args:
            from_node:     Source node name.
            to_node:       Target node name.
            relation_type: Type of relationship.
            weight:        Edge weight (higher = stronger).
            metadata:      Optional metadata.

        Returns:
            The created/updated :class:`ServiceEdge`, or ``None`` if
            either endpoint is not registered.
        """
        if from_node not in self._nodes or to_node not in self._nodes:
            return None

        # Check for existing edge with same (from, to, relation_type)
        for i, (target, edge) in enumerate(self._adj[from_node]):
            if target == to_node and edge.relation_type == relation_type:
                edge.weight = weight
                if metadata:
                    edge.metadata.update(metadata)
                self._persist()
                return edge

        edge = ServiceEdge(
            from_node=from_node,
            to_node=to_node,
            relation_type=relation_type,
            weight=weight,
            metadata=metadata or {},
        )
        self._adj[from_node].append((to_node, edge))
        self._radj[to_node].append((from_node, edge))
        self._persist()
        return edge

    # ------------------------------------------------------------------
    #  Neighbour queries
    # ------------------------------------------------------------------

    def get_neighbors(
        self,
        node_name: str,
        direction: str = "both",
    ) -> List[str]:
        """Return the names of neighbouring nodes.

        Args:
            node_name: The node whose neighbours to return.
            direction: ``"out"`` for outgoing edges only, ``"in"`` for
                incoming edges only, or ``"both"`` for all neighbours.

        Returns:
            Sorted list of neighbour node names.  Returns an empty list
            if the node is not registered.
        """
        if node_name not in self._nodes:
            return []

        neighbors: Set[str] = set()
        if direction in ("out", "both"):
            for target, _ in self._adj.get(node_name, []):
                neighbors.add(target)
        if direction in ("in", "both"):
            for source, _ in self._radj.get(node_name, []):
                neighbors.add(source)
        return sorted(neighbors)

    def get_outgoing_edges(self, node_name: str) -> List[ServiceEdge]:
        """Return all outgoing edges from a node."""
        return [edge for _, edge in self._adj.get(node_name, [])]

    def get_incoming_edges(self, node_name: str) -> List[ServiceEdge]:
        """Return all incoming edges to a node."""
        return [edge for _, edge in self._radj.get(node_name, [])]

    # ------------------------------------------------------------------
    #  Path finding (BFS)
    # ------------------------------------------------------------------

    def find_path(
        self,
        from_node: str,
        to_node: str,
        exclude: Optional[Set[str]] = None,
    ) -> Optional[List[str]]:
        """Find the shortest path between two nodes using BFS.

        Args:
            from_node: Starting node name.
            to_node:   Target node name.
            exclude:   Optional set of node names to exclude (treat as
                failed / unreachable).

        Returns:
            List of node names from *from_node* to *to_node* inclusive,
            or ``None`` if no path exists.
        """
        if from_node not in self._nodes or to_node not in self._nodes:
            return None
        if from_node == to_node:
            return [from_node]

        exclude = exclude or set()
        if from_node in exclude or to_node in exclude:
            return None

        # BFS
        queue: deque[Tuple[str, List[str]]] = deque()
        queue.append((from_node, [from_node]))
        visited: Set[str] = {from_node}

        while queue:
            current, path = queue.popleft()
            for target, _ in self._adj.get(current, []):
                if target in visited or target in exclude:
                    continue
                new_path = path + [target]
                if target == to_node:
                    return new_path
                visited.add(target)
                queue.append((target, new_path))

        return None

    def find_all_paths(
        self,
        from_node: str,
        to_node: str,
        exclude: Optional[Set[str]] = None,
        max_depth: int = 10,
    ) -> List[List[str]]:
        """Find all simple paths between two nodes (DFS, depth-limited).

        Args:
            from_node: Starting node name.
            to_node:   Target node name.
            exclude:   Optional set of nodes to exclude.
            max_depth: Maximum path length (number of edges).

        Returns:
            List of paths, each a list of node names.
        """
        if from_node not in self._nodes or to_node not in self._nodes:
            return []
        if from_node == to_node:
            return [[from_node]]

        exclude = exclude or set()
        if from_node in exclude or to_node in exclude:
            return []

        results: List[List[str]] = []

        def _dfs(node: str, path: List[str], visited: Set[str]) -> None:
            if len(path) - 1 >= max_depth:
                return
            for target, _ in self._adj.get(node, []):
                if target in visited or target in exclude:
                    continue
                new_path = path + [target]
                if target == to_node:
                    results.append(new_path)
                    continue
                visited.add(target)
                _dfs(target, new_path, visited)
                visited.discard(target)

        _dfs(from_node, [from_node], {from_node})
        return results

    # ------------------------------------------------------------------
    #  Dependency graph
    # ------------------------------------------------------------------

    def get_dependency_graph(self) -> Dict[str, Any]:
        """Return the complete dependency graph as a dict.

        The returned dict has two keys:

        - ``"nodes"`` — list of node dicts (from
          :meth:`ServiceNode.to_dict`).
        - ``"edges"`` — list of edge dicts (from
          :meth:`ServiceEdge.to_dict`).
        """
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [
                edge.to_dict()
                for adj_list in self._adj.values()
                for _, edge in adj_list
            ],
        }

    # ------------------------------------------------------------------
    #  Bottleneck detection
    # ------------------------------------------------------------------

    def find_bottlenecks(self) -> List[str]:
        """Identify single points of failure (bottleneck nodes).

        A bottleneck is a node (other than the source and sink) that
        lies on **every** path between at least one source-sink pair.
        Such nodes are single points of failure — if they go down, the
        source cannot reach the sink.

        The algorithm:
        1. Enumerate all source-sink pairs (nodes with outgoing but no
           incoming edges vs. nodes with incoming but no outgoing edges).
           If no natural sources/sinks exist, all node pairs are checked.
        2. For each pair, find all simple paths.
        3. A node is a bottleneck if it appears in every path for at
           least one pair.

        Returns:
            Sorted list of bottleneck node names.
        """
        if len(self._nodes) < 3:
            return []

        # Identify source nodes (no incoming edges) and sink nodes
        # (no outgoing edges)
        sources: List[str] = []
        sinks: List[str] = []
        for name in self._nodes:
            has_out = len(self._adj.get(name, [])) > 0
            has_in = len(self._radj.get(name, [])) > 0
            if has_out and not has_in:
                sources.append(name)
            if has_in and not has_out:
                sinks.append(name)

        # If no natural sources/sinks, use all nodes that can reach others
        if not sources or not sinks:
            # Fall back: check all pairs where a path exists
            node_names = list(self._nodes.keys())
            for i, src in enumerate(node_names):
                for dst in node_names:
                    if src == dst:
                        continue
                    if self.find_path(src, dst) is not None:
                        if not sources:
                            sources = [src]
                        if not sinks:
                            sinks = [dst]
                        break
                if sources and sinks:
                    break
            if not sources or not sinks:
                return []

        bottlenecks: Set[str] = set()

        for src in sources:
            for sink in sinks:
                if src == sink:
                    continue
                paths = self.find_all_paths(src, sink, max_depth=len(self._nodes))
                if len(paths) <= 1:
                    continue  # No alternative paths → no bottleneck to find

                # Find nodes common to ALL paths (excluding src and sink)
                common: Optional[Set[str]] = None
                for path in paths:
                    intermediate = set(path[1:-1])  # exclude endpoints
                    if common is None:
                        common = intermediate
                    else:
                        common &= intermediate
                    if not common:
                        break

                if common:
                    bottlenecks.update(common)

        return sorted(bottlenecks)

    # ------------------------------------------------------------------
    #  Capability mapping
    # ------------------------------------------------------------------

    def get_capability_map(self) -> Dict[str, List[str]]:
        """Return a mapping of capability → list of providing nodes.

        Returns:
            Dict where each key is a capability string and the value is
            a sorted list of node names that provide that capability.
        """
        cap_map: Dict[str, List[str]] = defaultdict(list)
        for name, node in self._nodes.items():
            for cap in node.capabilities:
                cap_map[cap].append(name)
        return {cap: sorted(nodes) for cap, nodes in cap_map.items()}

    def find_nodes_by_capability(self, capability: str) -> List[str]:
        """Return nodes that provide a given capability.

        Args:
            capability: The capability to search for.

        Returns:
            Sorted list of node names.
        """
        return sorted(
            name for name, node in self._nodes.items()
            if capability in node.capabilities
        )

    # ------------------------------------------------------------------
    #  Alternative routing
    # ------------------------------------------------------------------

    def suggest_alternatives(
        self,
        node_name: str,
    ) -> Dict[str, Any]:
        """Suggest alternative paths when a node fails.

        When *node_name* goes down, this method finds all source-sink
        pairs whose shortest path previously went through the node, and
        suggests alternative routes that bypass it.

        Args:
            node_name: The name of the (failed) node.

        Returns:
            A dict with:

            - ``"affected_pairs"``: list of ``(source, sink)`` tuples
              whose paths were affected.
            - ``"alternatives"``: list of dicts, each with
              ``"source"``, ``"sink"``, ``"alternative_path"`` (list
              of node names or ``None`` if no detour exists), and
              ``"original_path"``.
            - ``"unreachable_pairs"``: list of pairs that have no
              alternative path.
        """
        if node_name not in self._nodes:
            return {
                "affected_pairs": [],
                "alternatives": [],
                "unreachable_pairs": [],
            }

        exclude: Set[str] = {node_name}
        affected_pairs: List[Tuple[str, str]] = []
        alternatives: List[Dict[str, Any]] = []
        unreachable: List[Tuple[str, str]] = []

        node_names = list(self._nodes.keys())
        for src in node_names:
            if src == node_name:
                continue
            for dst in node_names:
                if src == dst:
                    continue
                original = self.find_path(src, dst)
                if original is None:
                    continue
                if node_name not in original:
                    continue  # path didn't go through the failed node

                affected_pairs.append((src, dst))
                alt_path = self.find_path(src, dst, exclude=exclude)
                if alt_path is not None:
                    alternatives.append({
                        "source": src,
                        "sink": dst,
                        "original_path": original,
                        "alternative_path": alt_path,
                    })
                else:
                    unreachable.append((src, dst))
                    alternatives.append({
                        "source": src,
                        "sink": dst,
                        "original_path": original,
                        "alternative_path": None,
                    })

        return {
            "affected_pairs": affected_pairs,
            "alternatives": alternatives,
            "unreachable_pairs": unreachable,
        }

    # ------------------------------------------------------------------
    #  Utility queries
    # ------------------------------------------------------------------

    def get_node(self, name: str) -> Optional[ServiceNode]:
        """Return a node by name, or ``None`` if not found."""
        return self._nodes.get(name)

    def get_all_nodes(self) -> List[ServiceNode]:
        """Return all registered nodes."""
        return list(self._nodes.values())

    def get_all_edges(self) -> List[ServiceEdge]:
        """Return all registered edges."""
        edges: List[ServiceEdge] = []
        for adj_list in self._adj.values():
            for _, edge in adj_list:
                edges.append(edge)
        return edges

    def node_count(self) -> int:
        """Return the number of registered nodes."""
        return len(self._nodes)

    def edge_count(self) -> int:
        """Return the number of registered edges."""
        return sum(len(adj) for adj in self._adj.values())

    def has_node(self, name: str) -> bool:
        """Check whether a node is registered."""
        return name in self._nodes

    def has_edge(self, from_node: str, to_node: str) -> bool:
        """Check whether an edge exists between two nodes."""
        return any(t == to_node for t, _ in self._adj.get(from_node, []))

    # ------------------------------------------------------------------
    #  Serialisation
    # ------------------------------------------------------------------

    def to_json(self) -> str:
        """Serialise the full graph to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the full graph to a dict."""
        return self.get_dependency_graph()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceTopologyMapper":
        """Reconstruct a mapper from a serialised dict (in-memory only)."""
        mapper = cls(backend=None)
        for node_data in data.get("nodes", []):
            node = ServiceNode.from_dict(node_data)
            mapper._nodes[node.name] = node
            mapper._adj[node.name] = []
            mapper._radj[node.name] = []
        for edge_data in data.get("edges", []):
            edge = ServiceEdge.from_dict(edge_data)
            if edge.from_node in mapper._nodes and edge.to_node in mapper._nodes:
                mapper._adj[edge.from_node].append((edge.to_node, edge))
                mapper._radj[edge.to_node].append((edge.from_node, edge))
        return mapper

    @classmethod
    def from_json(cls, json_str: str) -> "ServiceTopologyMapper":
        """Reconstruct a mapper from a JSON string."""
        return cls.from_dict(json.loads(json_str))

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        """Persist the full graph to the backend (if available)."""
        if self._backend is None:
            return
        self._backend.set(self._STORAGE_KEY, self.to_dict())

    def _load_from_backend(self) -> None:
        """Load the full graph from the backend (if available)."""
        assert self._backend is not None
        data = self._backend.get(self._STORAGE_KEY)
        if data is None:
            return
        # Reconstruct in-memory without persisting again
        for node_data in data.get("nodes", []):
            node = ServiceNode.from_dict(node_data)
            self._nodes[node.name] = node
            self._adj[node.name] = []
            self._radj[node.name] = []
        for edge_data in data.get("edges", []):
            edge = ServiceEdge.from_dict(edge_data)
            if edge.from_node in self._nodes and edge.to_node in self._nodes:
                self._adj[edge.from_node].append((edge.to_node, edge))
                self._radj[edge.to_node].append((edge.from_node, edge))

    def __repr__(self) -> str:
        backend_type = "SQLiteBackend" if self._backend else "in-memory"
        return (
            f"ServiceTopologyMapper(backend={backend_type}, "
            f"nodes={self.node_count()}, edges={self.edge_count()})"
        )
