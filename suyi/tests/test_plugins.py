"""Tests for the Plugin System (Phase 11)."""

from __future__ import annotations

import os
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

from suyi.plugins import (
    PluginBase,
    PluginContext,
    PluginState,
    PluginManager,
    PluginManagerError,
    PluginRegistry,
    PluginEntry,
    load_from_file,
    load_from_package,
    load_plugin,
    PluginLoadError,
)


# ── Test plugin fixtures ──────────────────────────────────────

class HelloPlugin(PluginBase):
    name = "hello"
    version = "1.0.0"
    description = "A simple hello plugin"

    def on_init(self, context: PluginContext) -> None:
        context.metadata["hello_inited"] = True

    def on_start(self, context: PluginContext) -> None:
        context.add_middleware({"name": "hello_mw"})
        context.add_tool({"name": "hello_tool"})

    def on_stop(self, context: PluginContext) -> None:
        context.metadata["hello_stopped"] = True


class WorldPlugin(PluginBase):
    name = "world"
    version = "2.0.0"
    description = "A world plugin"
    dependencies = ["hello"]

    def on_init(self, context: PluginContext) -> None:
        context.metadata["world_inited"] = True

    def on_start(self, context: PluginContext) -> None:
        context.add_skill({"name": "world_skill"})

    def on_stop(self, context: PluginContext) -> None:
        pass


class IndependentPlugin(PluginBase):
    name = "independent"
    version = "0.1.0"

    def on_init(self, context: PluginContext) -> None:
        pass

    def on_start(self, context: PluginContext) -> None:
        pass

    def on_stop(self, context: PluginContext) -> None:
        pass


# ── PluginBase tests ──────────────────────────────────────────

class TestPluginBase:
    def test_plugin_initial_state(self):
        p = HelloPlugin()
        assert p.state == PluginState.CREATED
        assert p.name == "hello"
        assert p.version == "1.0.0"

    def test_plugin_metadata(self):
        p = HelloPlugin()
        m = p.metadata()
        assert m["name"] == "hello"
        assert m["version"] == "1.0.0"
        assert m["description"] == "A simple hello plugin"
        assert m["hot_reloadable"] is True
        assert m["state"] == "created"

    def test_plugin_repr(self):
        p = HelloPlugin()
        r = repr(p)
        assert "hello" in r
        assert "1.0.0" in r

    def test_hook_registration(self):
        p = HelloPlugin()
        called = []

        def hook(**kwargs):
            called.append(kwargs)

        p.register_hook("test_event", hook)
        assert len(p.get_hooks("test_event")) == 1

        p.trigger_hooks("test_event", key="value")
        assert len(called) == 1
        assert called[0] == {"key": "value"}

    def test_hook_unregistration(self):
        p = HelloPlugin()

        def hook(**kwargs):
            pass

        p.register_hook("test_event", hook)
        assert len(p.get_hooks("test_event")) == 1

        p.unregister_hook("test_event", hook)
        assert len(p.get_hooks("test_event")) == 0

    def test_hook_trigger_returns_results(self):
        p = HelloPlugin()

        def hook1(**kwargs):
            return "result1"

        def hook2(**kwargs):
            return "result2"

        p.register_hook("evt", hook1)
        p.register_hook("evt", hook2)
        results = p.trigger_hooks("evt")
        assert results == ["result1", "result2"]

    def test_hook_trigger_swallows_exceptions(self):
        p = HelloPlugin()

        def bad_hook(**kwargs):
            raise RuntimeError("boom")

        def good_hook(**kwargs):
            return "ok"

        p.register_hook("evt", bad_hook)
        p.register_hook("evt", good_hook)
        results = p.trigger_hooks("evt")
        assert results == ["ok"]  # bad_hook's exception is swallowed

    def test_get_hooks_for_nonexistent_event(self):
        p = HelloPlugin()
        assert p.get_hooks("nonexistent") == []

    def test_plugin_base_is_abstract(self):
        with pytest.raises(TypeError):
            PluginBase()  # cannot instantiate ABC


# ── PluginContext tests ──────────────────────────────────────

class TestPluginContext:
    def test_context_defaults(self):
        ctx = PluginContext()
        assert ctx.middleware == []
        assert ctx.tools == []
        assert ctx.skills == []
        assert ctx.config == {}
        assert ctx.metadata == {}

    def test_add_middleware(self):
        ctx = PluginContext()
        ctx.add_middleware("mw1")
        assert ctx.middleware == ["mw1"]

    def test_add_tool(self):
        ctx = PluginContext()
        ctx.add_tool("tool1")
        assert ctx.tools == ["tool1"]

    def test_add_skill(self):
        ctx = PluginContext()
        ctx.add_skill("skill1")
        assert ctx.skills == ["skill1"]


# ── PluginRegistry tests ─────────────────────────────────────

class TestPluginRegistry:
    def test_register_and_get(self):
        reg = PluginRegistry()
        entry = reg.register("test", version="1.0", description="Test plugin")
        assert entry.name == "test"
        assert entry.version == "1.0"
        assert reg.get("test") is entry
        assert "test" in reg
        assert len(reg) == 1

    def test_duplicate_register_raises(self):
        reg = PluginRegistry()
        reg.register("test")
        with pytest.raises(ValueError, match="already registered"):
            reg.register("test")

    def test_unregister(self):
        reg = PluginRegistry()
        reg.register("a")
        reg.register("b")
        removed = reg.unregister("a")
        assert removed.name == "a"
        assert "a" not in reg
        assert len(reg) == 1

    def test_unregister_nonexistent_raises(self):
        reg = PluginRegistry()
        with pytest.raises(KeyError):
            reg.unregister("nonexistent")

    def test_list_plugins_sorted(self):
        reg = PluginRegistry()
        reg.register("c", dependencies=["a", "b"])
        reg.register("a")
        reg.register("b")
        order = reg.resolve_load_order()
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("c")

    def test_names_sorted(self):
        reg = PluginRegistry()
        reg.register("z")
        reg.register("a")
        reg.register("m")
        assert reg.names() == ["a", "m", "z"]

    def test_resolve_load_order_simple(self):
        reg = PluginRegistry()
        reg.register("a")
        reg.register("b", dependencies=["a"])
        reg.register("c", dependencies=["b"])
        order = reg.resolve_load_order()
        assert order == ["a", "b", "c"]

    def test_resolve_load_order_missing_dependency(self):
        reg = PluginRegistry()
        reg.register("a", dependencies=["missing"])
        with pytest.raises(ValueError, match="missing plugin"):
            reg.resolve_load_order()

    def test_resolve_load_order_cycle(self):
        reg = PluginRegistry()
        reg.register("a", dependencies=["b"])
        reg.register("b", dependencies=["a"])
        with pytest.raises(ValueError, match="cycle"):
            reg.resolve_load_order()

    def test_dependents_tracking(self):
        reg = PluginRegistry()
        reg.register("a")
        reg.register("b", dependencies=["a"])
        reg.register("c", dependencies=["a"])
        assert reg.get_dependents("a") == ["b", "c"]
        assert reg.get_dependencies("b") == ["a"]

    def test_can_unload_no_dependents(self):
        reg = PluginRegistry()
        reg.register("a")
        can, blockers = reg.can_unload("a")
        assert can is True
        assert blockers == []

    def test_can_unload_with_started_dependent(self):
        reg = PluginRegistry()
        reg.register("a")
        reg.register("b", dependencies=["a"])
        reg.update_state("b", PluginState.STARTED)
        can, blockers = reg.can_unload("a")
        assert can is False
        assert "b" in blockers

    def test_can_unload_with_stopped_dependent(self):
        reg = PluginRegistry()
        reg.register("a")
        reg.register("b", dependencies=["a"])
        reg.update_state("b", PluginState.STOPPED)
        can, blockers = reg.can_unload("a")
        assert can is True

    def test_update_state(self):
        reg = PluginRegistry()
        reg.register("a")
        reg.update_state("a", PluginState.STARTED)
        assert reg.get("a").state == PluginState.STARTED

    def test_load_order_assignment(self):
        reg = PluginRegistry()
        reg.register("c", dependencies=["a"])
        reg.register("a")
        reg.register("b", dependencies=["a"])
        order = reg.resolve_load_order()
        for idx, name in enumerate(order):
            assert reg.get(name).load_order == idx

    def test_unregister_removes_from_dependents(self):
        reg = PluginRegistry()
        reg.register("a")
        reg.register("b", dependencies=["a"])
        assert "b" in reg.get("a").dependents
        reg.unregister("b")
        assert "b" not in reg.get("a").dependents


# ── PluginLoader tests ────────────────────────────────────────

class TestPluginLoader:
    def test_load_from_file(self, tmp_path):
        plugin_code = textwrap.dedent('''
            from suyi.plugins import PluginBase, PluginContext

            class FilePlugin(PluginBase):
                name = "file_plugin"
                version = "1.0.0"

                def on_init(self, context):
                    pass

                def on_start(self, context):
                    pass

                def on_stop(self, context):
                    pass
        ''')
        f = tmp_path / "my_plugin.py"
        f.write_text(plugin_code)

        plugins = load_from_file(str(f))
        assert len(plugins) == 1
        assert plugins[0].name == "file_plugin"

    def test_load_from_file_not_found(self):
        with pytest.raises(PluginLoadError, match="not found"):
            load_from_file("/nonexistent/path/plugin.py")

    def test_load_from_file_wrong_extension(self, tmp_path):
        f = tmp_path / "plugin.txt"
        f.write_text("not python")
        with pytest.raises(PluginLoadError, match="Not a Python file"):
            load_from_file(str(f))

    def test_load_from_file_no_plugins(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("x = 1\n")
        with pytest.raises(PluginLoadError, match="No PluginBase"):
            load_from_file(str(f))

    def test_load_from_file_execution_error(self, tmp_path):
        f = tmp_path / "broken.py"
        f.write_text("raise RuntimeError('broken')\n")
        with pytest.raises(PluginLoadError, match="Error executing"):
            load_from_file(str(f))

    def test_load_from_package(self):
        # suyi.plugins.base has PluginBase but it's abstract
        # so loading should raise PluginLoadError
        with pytest.raises(PluginLoadError, match="No PluginBase"):
            load_from_package("suyi.plugins.base")

    def test_load_from_package_not_found(self):
        with pytest.raises(PluginLoadError, match="Cannot import"):
            load_from_package("nonexistent_pkg_xyz123")

    def test_load_plugin_auto_file(self, tmp_path):
        f = tmp_path / "auto_plugin.py"
        f.write_text(textwrap.dedent('''
            from suyi.plugins import PluginBase, PluginContext

            class AutoPlugin(PluginBase):
                name = "auto"
                def on_init(self, c): pass
                def on_start(self, c): pass
                def on_stop(self, c): pass
        '''))
        plugins = load_plugin(str(f))
        assert len(plugins) == 1
        assert plugins[0].name == "auto"

    def test_load_plugin_auto_package(self):
        with pytest.raises(PluginLoadError, match="No PluginBase"):
            load_plugin("suyi.plugins.base")

    def test_load_plugin_unknown_source_type(self):
        with pytest.raises(PluginLoadError):
            load_plugin("whatever", source_type="unknown_type")


# ── PluginManager tests ───────────────────────────────────────

class TestPluginManager:
    def test_load_and_start(self):
        mgr = PluginManager()
        p = HelloPlugin()
        entry = mgr.load(p)
        assert entry.name == "hello"
        assert entry.state == PluginState.INITIALIZED

        mgr.start("hello")
        assert entry.state == PluginState.STARTED
        assert len(mgr.get_middleware()) == 1
        assert len(mgr.get_tools()) == 1

    def test_load_duplicate_raises(self):
        mgr = PluginManager()
        mgr.load(HelloPlugin())
        with pytest.raises(PluginManagerError, match="already loaded"):
            mgr.load(HelloPlugin())

    def test_load_empty_name_raises(self):
        mgr = PluginManager()

        class NoName(PluginBase):
            name = ""
            def on_init(self, c): pass
            def on_start(self, c): pass
            def on_stop(self, c): pass

        with pytest.raises(PluginManagerError, match="non-empty name"):
            mgr.load(NoName())

    def test_start_not_found(self):
        mgr = PluginManager()
        with pytest.raises(PluginManagerError, match="not found"):
            mgr.start("nonexistent")

    def test_start_dependency_not_started(self):
        mgr = PluginManager()
        mgr.load(HelloPlugin())
        mgr.load(WorldPlugin())
        # hello not started yet, so starting world should fail
        with pytest.raises(PluginManagerError, match="dependency.*not started"):
            mgr.start("world")

    def test_start_all_in_order(self):
        mgr = PluginManager()
        mgr.load(HelloPlugin())
        mgr.load(WorldPlugin())
        mgr.start_all()

        assert mgr.get("hello").state == PluginState.STARTED
        assert mgr.get("world").state == PluginState.STARTED

        # world should have registered a skill
        assert len(mgr.get_skills()) == 1

    def test_stop(self):
        mgr = PluginManager()
        mgr.load(HelloPlugin())
        mgr.start("hello")
        mgr.stop("hello")
        assert mgr.get("hello").state == PluginState.STOPPED

    def test_stop_all_reverse_order(self):
        mgr = PluginManager()
        mgr.load(HelloPlugin())
        mgr.load(WorldPlugin())
        mgr.start_all()

        mgr.stop_all()
        assert mgr.get("hello").state == PluginState.STOPPED
        assert mgr.get("world").state == PluginState.STOPPED

    def test_unload(self):
        mgr = PluginManager()
        mgr.load(IndependentPlugin())
        entry = mgr.unload("independent")
        assert entry.name == "independent"
        assert "independent" not in mgr.registry

    def test_unload_with_dependent_raises(self):
        mgr = PluginManager()
        mgr.load(HelloPlugin())
        mgr.load(WorldPlugin())
        mgr.start_all()
        with pytest.raises(PluginManagerError, match="depended on by"):
            mgr.unload("hello")

    def test_unload_not_found(self):
        mgr = PluginManager()
        with pytest.raises(PluginManagerError, match="not found"):
            mgr.unload("nonexistent")

    def test_hot_load_after_start_all(self):
        mgr = PluginManager()
        mgr.load(HelloPlugin())
        mgr.start_all()

        # Now load another plugin after start_all
        mgr.load(IndependentPlugin())
        # Should be auto-started because mgr is in started state
        assert mgr.get("independent").state == PluginState.STARTED

    def test_reload_from_file(self, tmp_path):
        f = tmp_path / "reload_plugin.py"
        f.write_text(textwrap.dedent('''
            from suyi.plugins import PluginBase, PluginContext

            class ReloadPlugin(PluginBase):
                name = "reload"
                version = "1.0.0"
                def on_init(self, c): pass
                def on_start(self, c): pass
                def on_stop(self, c): pass
        '''))

        mgr = PluginManager()
        entries = mgr.load_file(str(f))
        assert len(entries) == 1
        mgr.start("reload")

        # Reload
        new_entry = mgr.reload("reload")
        assert new_entry is not None
        assert new_entry.state == PluginState.STARTED

    def test_reload_directly_loaded_returns_none(self):
        mgr = PluginManager()
        mgr.load(HelloPlugin())
        result = mgr.reload("hello")
        assert result is None  # directly loaded, no source to reload from

    def test_get_not_found(self):
        mgr = PluginManager()
        assert mgr.get("nonexistent") is None

    def test_list_plugins(self):
        mgr = PluginManager()
        mgr.load(HelloPlugin())
        mgr.load(IndependentPlugin())
        plugins = mgr.list_plugins()
        assert len(plugins) == 2

    def test_is_started(self):
        mgr = PluginManager()
        assert mgr.is_started() is False
        mgr.load(HelloPlugin())
        mgr.start_all()
        assert mgr.is_started() is True

    def test_get_context(self):
        mgr = PluginManager()
        ctx = mgr.get_context()
        assert isinstance(ctx, PluginContext)

    def test_on_init_failure(self):
        mgr = PluginManager()

        class BadPlugin(PluginBase):
            name = "bad"
            def on_init(self, c):
                raise RuntimeError("init failed")
            def on_start(self, c): pass
            def on_stop(self, c): pass

        with pytest.raises(PluginManagerError, match="on_init failed"):
            mgr.load(BadPlugin())

    def test_on_start_failure(self):
        mgr = PluginManager()

        class StartFailPlugin(PluginBase):
            name = "startfail"
            def on_init(self, c): pass
            def on_start(self, c):
                raise RuntimeError("start failed")
            def on_stop(self, c): pass

        mgr.load(StartFailPlugin())
        with pytest.raises(PluginManagerError, match="on_start failed"):
            mgr.start("startfail")
        assert mgr.get("startfail").state == PluginState.ERROR

    def test_load_file(self, tmp_path):
        f = tmp_path / "test_load.py"
        f.write_text(textwrap.dedent('''
            from suyi.plugins import PluginBase, PluginContext

            class TestLoadPlugin(PluginBase):
                name = "test_load"
                version = "1.0.0"
                def on_init(self, c): pass
                def on_start(self, c): pass
                def on_stop(self, c): pass
        '''))
        mgr = PluginManager()
        entries = mgr.load_file(str(f))
        assert len(entries) == 1
        assert entries[0].name == "test_load"

    def test_plugin_with_hooks(self):
        mgr = PluginManager()

        class HookPlugin(PluginBase):
            name = "hook_plugin"
            def on_init(self, c): pass
            def on_start(self, c):
                self.register_hook("on_message", lambda **kw: "handled")
            def on_stop(self, c): pass

        mgr.load(HookPlugin())
        mgr.start("hook_plugin")
        plugin = mgr.get("hook_plugin")
        results = plugin.trigger_hooks("on_message", message="hi")
        assert results == ["handled"]

    def test_stop_already_stopped(self):
        mgr = PluginManager()
        mgr.load(HelloPlugin())
        mgr.start("hello")
        mgr.stop("hello")
        # Should not raise
        mgr.stop("hello")
        assert mgr.get("hello").state == PluginState.STOPPED

    def test_start_already_started(self):
        mgr = PluginManager()
        mgr.load(HelloPlugin())
        mgr.start("hello")
        mgr.start("hello")  # idempotent
        assert mgr.get("hello").state == PluginState.STARTED
