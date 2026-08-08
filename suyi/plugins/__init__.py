"""Plugin System — extensible plugin architecture for Suyi.

Public API:
    - PluginManager: plugin discovery, loading, unloading, lifecycle management
    - PluginBase: abstract base class for all plugins
    - PluginContext: runtime context passed to plugins
    - PluginState: lifecycle state enum
    - PluginRegistry: plugin metadata and dependency management
    - PluginEntry: registry entry dataclass
    - load_from_file / load_from_package / load_from_entry_points / load_plugin
    - PluginLoadError
"""

from .base import PluginBase, PluginContext, PluginState, HookCallable
from .registry import PluginRegistry, PluginEntry
from .loader import (
    load_from_file,
    load_from_package,
    load_from_entry_points,
    load_plugin,
    PluginLoadError,
)
from .manager import PluginManager, PluginManagerError

__all__ = [
    "PluginManager",
    "PluginManagerError",
    "PluginBase",
    "PluginContext",
    "PluginState",
    "HookCallable",
    "PluginRegistry",
    "PluginEntry",
    "load_from_file",
    "load_from_package",
    "load_from_entry_points",
    "load_plugin",
    "PluginLoadError",
]
