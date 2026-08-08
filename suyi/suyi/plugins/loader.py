"""Plugin loader — discovers and instantiates plugins from various sources.

Supported loading strategies:

1. **File path** — load a Python module from ``.py`` file, find ``PluginBase``
   subclasses within.
2. **Python package** — import a dotted module path, find ``PluginBase``
   subclasses.
3. **Entry points** — scan ``importlib.metadata`` entry points under a given
   group.

All strategies return a list of *instantiated* plugin objects.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .base import PluginBase


class PluginLoadError(Exception):
    """Raised when a plugin cannot be loaded."""


# ── helpers ───────────────────────────────────────────────────

def _find_plugin_classes(module: Any) -> List[Type[PluginBase]]:
    """Return all concrete PluginBase subclasses defined in *module*."""
    classes: List[Type[PluginBase]] = []
    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if (
            issubclass(obj, PluginBase)
            and obj is not PluginBase
            and obj.__module__ == module.__name__
        ):
            classes.append(obj)
    return classes


def _instantiate(cls: Type[PluginBase], **kwargs: Any) -> PluginBase:
    """Instantiate a plugin class, passing through kwargs if accepted."""
    try:
        sig = inspect.signature(cls.__init__)
        params = sig.parameters
        # PluginBase.__init__ takes only self, but subclasses may accept kwargs
        if any(p.kind == p.VAR_KEYWORD for p in params.values()):
            return cls(**kwargs)
        return cls()
    except Exception as exc:  # noqa: BLE001
        raise PluginLoadError(f"Failed to instantiate {cls.__name__}: {exc}") from exc


# ── loaders ───────────────────────────────────────────────────

def load_from_file(file_path: str | os.PathLike, **kwargs: Any) -> List[PluginBase]:
    """Load plugins from a ``.py`` file.

    Args:
        file_path: Path to the Python file.
        **kwargs: Passed to plugin constructors if accepted.

    Returns:
        List of instantiated plugin objects.

    Raises:
        PluginLoadError: If the file cannot be loaded.
    """
    path = Path(file_path)
    if not path.is_file():
        raise PluginLoadError(f"Plugin file not found: {file_path}")
    if path.suffix != ".py":
        raise PluginLoadError(f"Not a Python file: {file_path}")

    module_name = f"_suyi_plugin_{path.stem}_{abs(hash(str(path)))}"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise PluginLoadError(f"Cannot create module spec for {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001
        sys.modules.pop(module_name, None)
        raise PluginLoadError(f"Error executing {file_path}: {exc}") from exc

    classes = _find_plugin_classes(module)
    if not classes:
        sys.modules.pop(module_name, None)
        raise PluginLoadError(f"No PluginBase subclasses found in {file_path}")

    return [_instantiate(cls, **kwargs) for cls in classes]


def load_from_package(package_path: str, **kwargs: Any) -> List[PluginBase]:
    """Load plugins from an importable Python package.

    Args:
        package_path: Dotted module path (e.g. ``myapp.plugins.my_plugin``).
        **kwargs: Passed to plugin constructors.

    Returns:
        List of instantiated plugin objects.
    """
    try:
        module = importlib.import_module(package_path)
    except ImportError as exc:
        raise PluginLoadError(f"Cannot import package '{package_path}': {exc}") from exc

    classes = _find_plugin_classes(module)
    if not classes:
        raise PluginLoadError(f"No PluginBase subclasses found in '{package_path}'")

    return [_instantiate(cls, **kwargs) for cls in classes]


def load_from_entry_points(
    group: str = "suyi.plugins", **kwargs: Any
) -> List[PluginBase]:
    """Load plugins registered as entry points.

    Args:
        group: Entry point group name.
        **kwargs: Passed to plugin constructors.

    Returns:
        List of instantiated plugin objects.
    """
    plugins: List[PluginBase] = []
    try:
        from importlib.metadata import entry_points
    except ImportError:
        return plugins

    try:
        eps = entry_points(group=group)
    except TypeError:
        # Python < 3.10 — entry_points returns a dict
        all_eps = entry_points()
        eps = all_eps.get(group, [])

    for ep in eps:
        try:
            cls = ep.load()
            if isinstance(cls, type) and issubclass(cls, PluginBase) and cls is not PluginBase:
                plugins.append(_instantiate(cls, **kwargs))
        except Exception:  # noqa: BLE001
            pass

    return plugins


def load_plugin(
    source: str,
    *,
    source_type: str = "auto",
    **kwargs: Any,
) -> List[PluginBase]:
    """Universal loader — auto-detect source type.

    Args:
        source: File path, dotted package path, or entry point name.
        source_type: ``"file"``, ``"package"``, ``"entry_point"``, or ``"auto"``.
        **kwargs: Passed to plugin constructors.

    Returns:
        List of instantiated plugin objects.
    """
    if source_type == "auto":
        if os.path.isfile(source) and source.endswith(".py"):
            source_type = "file"
        elif "." in source and not source.endswith(".py"):
            source_type = "package"
        else:
            source_type = "file"  # try file as fallback

    if source_type == "file":
        return load_from_file(source, **kwargs)
    elif source_type == "package":
        return load_from_package(source, **kwargs)
    elif source_type == "entry_point":
        return load_from_entry_points(source, **kwargs)
    else:
        raise PluginLoadError(f"Unknown source_type: {source_type}")
