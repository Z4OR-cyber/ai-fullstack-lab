"""Plugin registry — maintains plugin metadata and dependency relationships.

The registry is a passive store: it tracks what plugins exist, their
dependencies, and their load order, but does not instantiate or manage
plugin lifecycle (that's :class:`~.manager.PluginManager`'s job).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .base import PluginBase, PluginState


@dataclass
class PluginEntry:
    """Registry entry for a single plugin."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    plugin_class: Optional[type] = None
    instance: Optional[PluginBase] = None
    state: PluginState = PluginState.CREATED
    load_order: int = 0
    source: str = ""  # where it was loaded from (path / package / entry_point)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "dependencies": list(self.dependencies),
            "dependents": list(self.dependents),
            "state": self.state.value,
            "load_order": self.load_order,
            "source": self.source,
            "metadata": dict(self.metadata),
        }


class PluginRegistry:
    """In-memory registry of all known plugins.

    Supports:
      * Registration / unregistration of plugin classes or instances.
      * Dependency graph resolution (topological sort).
      * Reverse-dependency tracking (who depends on whom).
      * Lookup by name.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, PluginEntry] = {}

    # ── registration ──────────────────────────────────────────

    def register(
        self,
        name: str,
        *,
        version: str = "0.0.1",
        description: str = "",
        author: str = "",
        dependencies: Optional[List[str]] = None,
        plugin_class: Optional[type] = None,
        instance: Optional[PluginBase] = None,
        source: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PluginEntry:
        """Register a plugin.  Raises ``ValueError`` if already registered."""
        if name in self._entries:
            raise ValueError(f"Plugin '{name}' is already registered.")
        entry = PluginEntry(
            name=name,
            version=version,
            description=description,
            author=author,
            dependencies=list(dependencies or []),
            plugin_class=plugin_class,
            instance=instance,
            source=source,
            metadata=dict(metadata or {}),
        )
        self._entries[name] = entry
        self._update_dependents(name)
        return entry

    def unregister(self, name: str) -> PluginEntry:
        """Remove a plugin from the registry.  Raises ``KeyError`` if not found."""
        if name not in self._entries:
            raise KeyError(f"Plugin '{name}' is not registered.")
        entry = self._entries.pop(name)
        # Remove from dependents lists
        for other in self._entries.values():
            if name in other.dependents:
                other.dependents.remove(name)
        return entry

    # ── lookup ────────────────────────────────────────────────

    def get(self, name: str) -> Optional[PluginEntry]:
        return self._entries.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def list_plugins(self) -> List[PluginEntry]:
        """Return all registered entries, sorted by load order."""
        return sorted(self._entries.values(), key=lambda e: e.load_order)

    def names(self) -> List[str]:
        """Return sorted list of plugin names."""
        return sorted(self._entries.keys())

    # ── dependency resolution ─────────────────────────────────

    def _update_dependents(self, name: str) -> None:
        """For each dependency of *name*, add *name* to its dependents list."""
        entry = self._entries.get(name)
        if not entry:
            return
        for dep in entry.dependencies:
            dep_entry = self._entries.get(dep)
            if dep_entry and name not in dep_entry.dependents:
                dep_entry.dependents.append(name)

    def resolve_load_order(self) -> List[str]:
        """Return plugin names in dependency-safe order (topological sort).

        Raises ``ValueError`` if a cycle is detected or a dependency is missing.
        """
        # Kahn's algorithm
        in_degree: Dict[str, int] = {}
        graph: Dict[str, List[str]] = {}

        for name, entry in self._entries.items():
            in_degree.setdefault(name, 0)
            graph.setdefault(name, [])
            for dep in entry.dependencies:
                if dep not in self._entries:
                    raise ValueError(
                        f"Plugin '{name}' depends on missing plugin '{dep}'."
                    )
                graph.setdefault(dep, [])
                graph[dep].append(name)
                in_degree[name] = in_degree.get(name, 0) + 1

        queue: List[str] = sorted(n for n, d in in_degree.items() if d == 0)
        order: List[str] = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in graph.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    queue.sort()  # deterministic

        if len(order) != len(self._entries):
            cycle_nodes = set(self._entries) - set(order)
            raise ValueError(
                f"Dependency cycle detected among plugins: {sorted(cycle_nodes)}"
            )

        # Assign load_order
        for idx, name in enumerate(order):
            self._entries[name].load_order = idx

        return order

    def get_dependents(self, name: str) -> List[str]:
        """Return plugins that depend on *name* (direct dependents)."""
        entry = self._entries.get(name)
        return list(entry.dependents) if entry else []

    def get_dependencies(self, name: str) -> List[str]:
        """Return direct dependencies of *name*."""
        entry = self._entries.get(name)
        return list(entry.dependencies) if entry else []

    def can_unload(self, name: str) -> Tuple[bool, List[str]]:
        """Check whether *name* can be unloaded safely.

        Returns ``(True, [])`` if no other loaded plugin depends on it,
        otherwise ``(False, [list of blockers])``.
        """
        blockers: List[str] = []
        entry = self._entries.get(name)
        if not entry:
            return False, ["not registered"]
        for dep_name in entry.dependents:
            dep_entry = self._entries.get(dep_name)
            if dep_entry and dep_entry.state in (PluginState.INITIALIZED, PluginState.STARTED):
                blockers.append(dep_name)
        return (len(blockers) == 0, blockers)

    def update_state(self, name: str, state: PluginState) -> None:
        """Update the recorded state of a plugin."""
        entry = self._entries.get(name)
        if entry:
            entry.state = state
