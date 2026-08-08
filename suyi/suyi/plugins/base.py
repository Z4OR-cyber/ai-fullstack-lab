"""Plugin base class — defines the plugin contract for the Suyi framework.

A plugin is a self-contained extension that can register middleware, tools,
or skills into the agent runtime.  The lifecycle is::

    plugin = MyPlugin()
    plugin.on_init(context)      # called once after creation
    plugin.on_start(context)      # called when the agent starts
    ...
    plugin.on_stop(context)      # called when the agent shuts down

Hooks allow plugins to react to framework events without subclassing core
classes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class PluginState(str, Enum):
    """Lifecycle states of a plugin."""

    CREATED = "created"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"
    ERROR = "error"


# ── Hook types ───────────────────────────────────────────────

HookCallable = Callable[..., Any]
"""A hook is any callable that receives keyword arguments describing the event."""


@dataclass
class PluginContext:
    """Runtime context passed to plugins.

    Provides access to shared registries so plugins can register
    middleware, tools, or skills.
    """

    middleware: List[Any] = field(default_factory=list)
    tools: List[Any] = field(default_factory=list)
    skills: List[Any] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_middleware(self, mw: Any) -> None:
        self.middleware.append(mw)

    def add_tool(self, tool: Any) -> None:
        self.tools.append(tool)

    def add_skill(self, skill: Any) -> None:
        self.skills.append(skill)


class PluginBase(ABC):
    """Abstract base class for all Suyi plugins.

    Subclasses must override :meth:`on_init`, :meth:`on_start`, and
    :meth:`on_stop`.  They may optionally override the ``on_*`` hook
    methods to react to framework events.
    """

    #: Human-readable plugin name (unique within a PluginManager).
    name: str = ""

    #: Version string, used for dependency resolution.
    version: str = "0.0.1"

    #: Short description shown in listings.
    description: str = ""

    #: Author / maintainer.
    author: str = ""

    #: List of plugin names this plugin depends on.
    dependencies: List[str] = []

    #: Whether the plugin can be hot-loaded / hot-unloaded at runtime.
    hot_reloadable: bool = True

    def __init__(self) -> None:
        self.state: PluginState = PluginState.CREATED
        self.context: Optional[PluginContext] = None
        self._hooks: Dict[str, List[HookCallable]] = {}

    # ── lifecycle ────────────────────────────────────────────

    @abstractmethod
    def on_init(self, context: PluginContext) -> None:
        """Called once after the plugin is created.

        Use this to validate configuration, open resources, etc.
        """
        ...

    @abstractmethod
    def on_start(self, context: PluginContext) -> None:
        """Called when the agent starts (or the plugin is hot-loaded).

        Register middleware, tools, or skills here.
        """
        ...

    @abstractmethod
    def on_stop(self, context: PluginContext) -> None:
        """Called when the agent stops (or the plugin is hot-unloaded).

        Clean up resources, unregister hooks, etc.
        """
        ...

    # ── hooks ────────────────────────────────────────────────

    def register_hook(self, event_name: str, callback: HookCallable) -> None:
        """Register a callback for a named event/hook."""
        self._hooks.setdefault(event_name, []).append(callback)

    def unregister_hook(self, event_name: str, callback: HookCallable) -> None:
        """Remove a previously registered callback."""
        callbacks = self._hooks.get(event_name, [])
        if callback in callbacks:
            callbacks.remove(callback)

    def get_hooks(self, event_name: str) -> List[HookCallable]:
        """Return all callbacks registered for *event_name*."""
        return list(self._hooks.get(event_name, []))

    def trigger_hooks(self, event_name: str, **kwargs: Any) -> List[Any]:
        """Invoke all callbacks for *event_name* and collect results."""
        results: List[Any] = []
        for cb in self._hooks.get(event_name, []):
            try:
                results.append(cb(**kwargs))
            except Exception:  # noqa: BLE001
                pass
        return results

    # ── metadata helpers ─────────────────────────────────────

    def metadata(self) -> Dict[str, Any]:
        """Return a metadata dictionary describing this plugin."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "dependencies": list(self.dependencies),
            "hot_reloadable": self.hot_reloadable,
            "state": self.state.value,
        }

    def __repr__(self) -> str:
        return f"<Plugin {self.name!r} v{self.version} [{self.state.value}]>"
