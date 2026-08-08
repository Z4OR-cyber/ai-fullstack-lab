"""Plugin manager — orchestrates plugin discovery, loading, and lifecycle.

The :class:`PluginManager` ties together :class:`~.loader`,
:class:`~.registry`, and :class:`~.base` to provide a single entry point
for plugin management.

Usage::

    mgr = PluginManager()

    # Load a plugin from a file
    mgr.load_file("my_plugin.py")

    # Or from an importable package
    mgr.load_package("myapp.plugins.logger")

    # Start all plugins
    mgr.start_all()

    # Hot-unload a specific plugin
    mgr.unload("logger")

    # Stop everything
    mgr.stop_all()
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .base import PluginBase, PluginContext, PluginState
from .loader import load_from_file, load_from_package, load_plugin, PluginLoadError
from .registry import PluginEntry, PluginRegistry


class PluginManagerError(Exception):
    """General plugin manager error."""


class PluginManager:
    """Central plugin lifecycle manager.

    Attributes:
        registry: The :class:`PluginRegistry` instance.
        context: The :class:`PluginContext` shared with all plugins.
    """

    def __init__(self, context: Optional[PluginContext] = None) -> None:
        self.registry = PluginRegistry()
        self.context = context or PluginContext()
        self._started: bool = False

    # ── loading ───────────────────────────────────────────────

    def load(self, plugin: PluginBase, *, source: str = "direct") -> PluginEntry:
        """Register and initialize an already-instantiated plugin.

        Args:
            plugin: A PluginBase instance.
            source: Origin description for the registry.

        Returns:
            The registry entry.

        Raises:
            PluginManagerError: If a plugin with the same name is already loaded.
        """
        if not plugin.name:
            raise PluginManagerError("Plugin must have a non-empty name.")

        if plugin.name in self.registry:
            raise PluginManagerError(f"Plugin '{plugin.name}' is already loaded.")

        # Initialize
        plugin.state = PluginState.CREATED
        plugin.context = self.context
        try:
            plugin.on_init(self.context)
        except Exception as exc:  # noqa: BLE001
            plugin.state = PluginState.ERROR
            raise PluginManagerError(f"on_init failed for '{plugin.name}': {exc}") from exc

        plugin.state = PluginState.INITIALIZED

        entry = self.registry.register(
            name=plugin.name,
            version=plugin.version,
            description=plugin.description,
            author=plugin.author,
            dependencies=plugin.dependencies,
            instance=plugin,
            source=source,
        )
        entry.state = PluginState.INITIALIZED

        # If manager is already started, auto-start the new plugin
        if self._started and plugin.hot_reloadable:
            self.start(plugin.name)

        return entry

    def load_file(self, file_path: str, **kwargs: Any) -> List[PluginEntry]:
        """Load plugins from a ``.py`` file and register them."""
        plugins = load_from_file(file_path, **kwargs)
        return [self.load(p, source=f"file:{file_path}") for p in plugins]

    def load_package(self, package_path: str, **kwargs: Any) -> List[PluginEntry]:
        """Load plugins from a Python package and register them."""
        plugins = load_from_package(package_path, **kwargs)
        return [self.load(p, source=f"package:{package_path}") for p in plugins]

    def load_source(
        self, source: str, *, source_type: str = "auto", **kwargs: Any
    ) -> List[PluginEntry]:
        """Auto-detect and load plugins from *source*."""
        plugins = load_plugin(source, source_type=source_type, **kwargs)
        return [self.load(p, source=source) for p in plugins]

    # ── lifecycle ─────────────────────────────────────────────

    def start(self, name: str) -> None:
        """Start a single plugin by name."""
        entry = self.registry.get(name)
        if entry is None:
            raise PluginManagerError(f"Plugin '{name}' not found.")
        if entry.instance is None:
            raise PluginManagerError(f"Plugin '{name}' has no instance.")
        if entry.state == PluginState.STARTED:
            return  # already started

        # Check dependencies are started
        for dep_name in entry.dependencies:
            dep = self.registry.get(dep_name)
            if dep is None:
                raise PluginManagerError(
                    f"Cannot start '{name}': dependency '{dep_name}' is not loaded."
                )
            if dep.state != PluginState.STARTED:
                raise PluginManagerError(
                    f"Cannot start '{name}': dependency '{dep_name}' is not started."
                )

        try:
            entry.instance.on_start(self.context)
            entry.instance.state = PluginState.STARTED
            entry.state = PluginState.STARTED
        except Exception as exc:  # noqa: BLE001
            entry.instance.state = PluginState.ERROR
            entry.state = PluginState.ERROR
            raise PluginManagerError(f"on_start failed for '{name}': {exc}") from exc

    def start_all(self) -> None:
        """Start all registered plugins in dependency-safe order."""
        self._started = True
        order = self.registry.resolve_load_order()
        for name in order:
            entry = self.registry.get(name)
            if entry and entry.state == PluginState.INITIALIZED:
                self.start(name)

    def stop(self, name: str) -> None:
        """Stop a single plugin by name."""
        entry = self.registry.get(name)
        if entry is None:
            raise PluginManagerError(f"Plugin '{name}' not found.")
        if entry.instance is None:
            return
        if entry.state not in (PluginState.STARTED, PluginState.ERROR):
            return  # not running

        try:
            entry.instance.on_stop(self.context)
        except Exception:  # noqa: BLE001
            pass

        entry.instance.state = PluginState.STOPPED
        entry.state = PluginState.STOPPED

    def stop_all(self) -> None:
        """Stop all running plugins in reverse dependency order."""
        self._started = False
        order = self.registry.resolve_load_order()
        for name in reversed(order):
            entry = self.registry.get(name)
            if entry and entry.state in (PluginState.STARTED, PluginState.ERROR):
                self.stop(name)

    # ── unloading ────────────────────────────────────────────

    def unload(self, name: str) -> PluginEntry:
        """Hot-unload a plugin: stop it, then remove from registry.

        Raises ``PluginManagerError`` if other started plugins depend on it.
        """
        entry = self.registry.get(name)
        if entry is None:
            raise PluginManagerError(f"Plugin '{name}' not found.")

        can_unload, blockers = self.registry.can_unload(name)
        if not can_unload:
            raise PluginManagerError(
                f"Cannot unload '{name}': depended on by {blockers}"
            )

        # Stop if running
        if entry.state in (PluginState.STARTED, PluginState.ERROR):
            self.stop(name)

        # Unregister
        removed = self.registry.unregister(name)
        return removed

    # ── reload ───────────────────────────────────────────────

    def reload(self, name: str) -> Optional[PluginEntry]:
        """Hot-reload a plugin: unload then reload from the same source.

        Returns the new registry entry, or ``None`` if the plugin could not
        be reloaded (e.g., loaded directly without a file/package source).
        """
        entry = self.registry.get(name)
        if entry is None:
            raise PluginManagerError(f"Plugin '{name}' not found.")

        source = entry.source
        was_started = entry.state == PluginState.STARTED

        # Unload
        self.unload(name)

        # Reload from source
        if source.startswith("file:"):
            file_path = source[len("file:"):]
            entries = self.load_file(file_path)
        elif source.startswith("package:"):
            pkg = source[len("package:"):]
            entries = self.load_package(pkg)
        else:
            # Directly loaded — cannot reload from source
            return None

        if entries:
            new_entry = entries[0]
            if was_started:
                self.start(new_entry.name)
            return new_entry

        return None

    # ── queries ───────────────────────────────────────────────

    def get(self, name: str) -> Optional[PluginBase]:
        """Return the plugin instance, or ``None``."""
        entry = self.registry.get(name)
        return entry.instance if entry else None

    def list_plugins(self) -> List[PluginEntry]:
        """Return all registry entries."""
        return self.registry.list_plugins()

    def get_middleware(self) -> List[Any]:
        """Return all middleware registered by plugins."""
        return list(self.context.middleware)

    def get_tools(self) -> List[Any]:
        """Return all tools registered by plugins."""
        return list(self.context.tools)

    def get_skills(self) -> List[Any]:
        """Return all skills registered by plugins."""
        return list(self.context.skills)

    def is_started(self) -> bool:
        """Whether :meth:`start_all` has been called."""
        return self._started

    # ── context access ───────────────────────────────────────

    def get_context(self) -> PluginContext:
        """Return the shared plugin context."""
        return self.context
