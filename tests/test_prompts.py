"""
Tests for Suyi Prompts module — templates, manager, library.

Covers:
    - PromptTemplate: variable interpolation, partial, compose, validate
    - SystemPrompt: identity, rules, constraints, bilingual
    - ReActPrompt: ReAct loop template rendering
    - ToolPrompt: tool description formatting
    - MultiAgentPrompt: multi-agent collaboration template
    - PromptManager: register, get, update, rollback, file loading, export/import
    - PromptLibrary: predefined templates, categories, languages
"""

import json
import os
import time

import pytest

from suyi.prompts import (
    PromptTemplate,
    SystemPrompt,
    ReActPrompt,
    ToolPrompt,
    MultiAgentPrompt,
    PromptManager,
    TemplateVersion,
    PromptLibrary,
    get_library,
    get_template,
    render_template,
)


# ═══════════════════════════════════════════════════════════════
#  PromptTemplate Tests
# ═══════════════════════════════════════════════════════════════


class TestPromptTemplate:
    """Test PromptTemplate base class."""

    def test_basic_render(self):
        tpl = PromptTemplate("Hello, {name}!")
        result = tpl.render(name="World")
        assert result == "Hello, World!"

    def test_multiple_variables(self):
        tpl = PromptTemplate("{greeting}, {name}! You are {role}.")
        result = tpl.render(greeting="Hi", name="Alice", role="admin")
        assert result == "Hi, Alice! You are admin."

    def test_variable_extraction(self):
        tpl = PromptTemplate("Hello {name}, your age is {age}")
        assert "name" in tpl.variables
        assert "age" in tpl.variables
        assert len(tpl.variables) == 2

    def test_no_variables(self):
        tpl = PromptTemplate("Static text with no variables.")
        assert tpl.variables == []
        result = tpl.render()
        assert result == "Static text with no variables."

    def test_duplicate_variables(self):
        tpl = PromptTemplate("{name} says hello. {name} is here.")
        assert tpl.variables == ["name"]
        result = tpl.render(name="Alice")
        assert "Alice" in result

    def test_missing_variable_raises(self):
        tpl = PromptTemplate("Hello {name} and {role}")
        with pytest.raises(KeyError, match="Missing required"):
            tpl.render(name="Alice")

    def test_render_safe(self):
        tpl = PromptTemplate("Hello {name}, you are {role}.")
        result = tpl.render_safe(name="Alice")
        assert "Alice" in result
        # Missing variable replaced with empty string
        assert "you are ." in result

    def test_partial(self):
        tpl = PromptTemplate("Hello {name}, you are {role}.")
        partial = tpl.partial(name="Alice")
        assert "Alice" in partial.template
        assert "{role}" in partial.template
        full = partial.render(role="admin")
        assert "Alice" in full
        assert "admin" in full

    def test_validate(self):
        tpl = PromptTemplate("Hello {name}, you are {role}.")
        missing = tpl.validate(name="Alice")
        assert missing == ["role"]
        complete = tpl.validate(name="Alice", role="admin")
        assert complete == []

    def test_compose(self):
        tpl1 = PromptTemplate("Part 1: {a}")
        tpl2 = PromptTemplate("Part 2: {b}")
        combined = tpl1.compose(tpl2)
        result = combined.render(a="hello", b="world")
        assert "Part 1: hello" in result
        assert "Part 2: world" in result

    def test_compose_custom_separator(self):
        tpl1 = PromptTemplate("A={a}")
        tpl2 = PromptTemplate("B={b}")
        combined = tpl1.compose(tpl2, separator=" | ")
        result = combined.render(a="1", b="2")
        assert result == "A=1 | B=2"

    def test_escaped_braces(self):
        tpl = PromptTemplate("Use {{name}} as a literal, but {actual} is a variable.")
        result = tpl.render(actual="value")
        assert "{name}" in result
        assert "value" in result

    def test_repr(self):
        tpl = PromptTemplate("Hello {name}", name="greeting")
        r = repr(tpl)
        assert "greeting" in r
        assert "name" in r

    def test_str(self):
        tpl = PromptTemplate("Hello {name}")
        assert str(tpl) == "Hello {name}"

    def test_len(self):
        tpl = PromptTemplate("Hello {name}!")
        assert len(tpl) == len("Hello {name}!")

    def test_equality(self):
        tpl1 = PromptTemplate("Hello {name}", name="greeting")
        tpl2 = PromptTemplate("Hello {name}", name="greeting")
        tpl3 = PromptTemplate("Hi {name}", name="greeting")
        assert tpl1 == tpl2
        assert tpl1 != tpl3

    def test_name_default(self):
        tpl = PromptTemplate("test")
        assert tpl.name == "PromptTemplate"

    def test_description(self):
        tpl = PromptTemplate("test", description="A test template")
        assert tpl.description == "A test template"


# ═══════════════════════════════════════════════════════════════
#  SystemPrompt Tests
# ═══════════════════════════════════════════════════════════════


class TestSystemPrompt:
    """Test SystemPrompt template."""

    def test_default_render(self):
        sys = SystemPrompt(identity="A helpful assistant.")
        result = sys.render()
        assert "A helpful assistant." in result
        assert "## Rules" in result or "## 规则" in result

    def test_with_rules(self):
        sys = SystemPrompt(
            identity="Assistant",
            rules=["Be concise.", "Be accurate."],
        )
        result = sys.render()
        assert "- Be concise." in result
        assert "- Be accurate." in result

    def test_with_constraints(self):
        sys = SystemPrompt(
            identity="Assistant",
            constraints=["Do not hallucinate.", "Stay on topic."],
        )
        result = sys.render()
        assert "- Do not hallucinate." in result

    def test_chinese(self):
        sys = SystemPrompt(
            identity="助手",
            rules=["简洁", "准确"],
            language="zh",
        )
        result = sys.render()
        assert "助手" in result
        assert "## 身份" in result

    def test_add_rule(self):
        sys = SystemPrompt(identity="Assistant")
        sys.add_rule("Always be polite.")
        result = sys.render()
        assert "Always be polite." in result

    def test_add_constraint(self):
        sys = SystemPrompt(identity="Assistant")
        sys.add_constraint("Never share personal data.")
        result = sys.render()
        assert "Never share personal data." in result

    def test_empty_rules_and_constraints(self):
        sys = SystemPrompt(identity="Assistant")
        result = sys.render()
        assert "No specific rules." in result or "No specific constraints." in result

    def test_custom_template(self):
        custom = "ID: {identity}\nRules: {rules}\nConstraints: {constraints}"
        sys = SystemPrompt(
            identity="Test",
            rules=["r1"],
            constraints=["c1"],
            template=custom,
        )
        result = sys.render()
        assert "ID: Test" in result
        assert "Rules: - r1" in result


# ═══════════════════════════════════════════════════════════════
#  ReActPrompt Tests
# ═══════════════════════════════════════════════════════════════


class TestReActPrompt:
    """Test ReActPrompt template."""

    def test_render(self):
        prompt = ReActPrompt()
        result = prompt.render(
            tools_desc="search: Search the web",
            history_desc="User: Hello",
            budget_desc="Max 10 turns",
            task_desc="Find the weather",
        )
        assert "search: Search the web" in result
        assert "User: Hello" in result
        assert "Max 10 turns" in result
        assert "Find the weather" in result

    def test_default_values(self):
        prompt = ReActPrompt()
        result = prompt.render()
        # Should render with empty strings
        assert "ReAct" in result
        assert "Thought" in result

    def test_variables_list(self):
        prompt = ReActPrompt()
        assert "tools_desc" in prompt.variables
        assert "history_desc" in prompt.variables
        assert "budget_desc" in prompt.variables
        assert "task_desc" in prompt.variables

    def test_custom_template(self):
        custom = "Tools: {tools_desc} | History: {history_desc} | Budget: {budget_desc} | Task: {task_desc}"
        prompt = ReActPrompt(template=custom)
        result = prompt.render(
            tools_desc="t1", history_desc="h1", budget_desc="b1", task_desc="t2"
        )
        assert result == "Tools: t1 | History: h1 | Budget: b1 | Task: t2"


# ═══════════════════════════════════════════════════════════════
#  ToolPrompt Tests
# ═══════════════════════════════════════════════════════════════


class TestToolPrompt:
    """Test ToolPrompt template."""

    def test_render(self):
        prompt = ToolPrompt()
        result = prompt.render(
            tool_name="search",
            tool_description="Search the web for information",
            tool_parameters='{"query": "string"}',
        )
        assert "search" in result
        assert "Search the web" in result
        assert "query" in result

    def test_format_tools(self):
        tools = [
            {"name": "search", "description": "Search the web", "parameters": {"query": "string"}},
            {"name": "calc", "description": "Calculate", "parameters": {"expr": "string"}},
        ]
        result = ToolPrompt.format_tools(tools)
        assert "search" in result
        assert "calc" in result
        assert "Search the web" in result

    def test_format_tools_empty(self):
        result = ToolPrompt.format_tools([])
        assert result == ""

    def test_format_tools_no_params(self):
        tools = [{"name": "noop", "description": "Does nothing"}]
        result = ToolPrompt.format_tools(tools)
        assert "noop" in result
        assert "{}" in result


# ═══════════════════════════════════════════════════════════════
#  MultiAgentPrompt Tests
# ═══════════════════════════════════════════════════════════════


class TestMultiAgentPrompt:
    """Test MultiAgentPrompt template."""

    def test_render(self):
        prompt = MultiAgentPrompt()
        result = prompt.render(
            orchestrator_desc="You coordinate tasks",
            agent_descriptions="Agent1: coder\nAgent2: reviewer",
            collaboration_rules="Share results",
        )
        assert "You coordinate tasks" in result
        assert "Agent1: coder" in result
        assert "Share results" in result

    def test_variables(self):
        prompt = MultiAgentPrompt()
        assert "orchestrator_desc" in prompt.variables
        assert "agent_descriptions" in prompt.variables
        assert "collaboration_rules" in prompt.variables


# ═══════════════════════════════════════════════════════════════
#  PromptManager Tests
# ═══════════════════════════════════════════════════════════════


class TestPromptManager:
    """Test PromptManager."""

    @pytest.fixture
    def mgr(self):
        return PromptManager()

    def test_register_and_get(self, mgr):
        tpl = PromptTemplate("Hello {name}!", name="greeting")
        mgr.register(tpl)
        retrieved = mgr.get("greeting")
        assert retrieved.template == "Hello {name}!"

    def test_get_not_found(self, mgr):
        with pytest.raises(KeyError, match="not found"):
            mgr.get("nonexistent")

    def test_render(self, mgr):
        mgr.register(PromptTemplate("Hello {name}!", name="greeting"))
        result = mgr.render("greeting", name="World")
        assert result == "Hello World!"

    def test_render_safe(self, mgr):
        mgr.register(PromptTemplate("Hi {name}!", name="greeting"))
        result = mgr.render_safe("greeting")
        assert "Hi !" in result

    def test_update_creates_new_version(self, mgr):
        mgr.register(PromptTemplate("v1 {x}", name="test"))
        v = mgr.update("test", PromptTemplate("v2 {x}", name="test"))
        assert v == 2
        latest = mgr.get("test")
        assert latest.template == "v2 {x}"

    def test_get_specific_version(self, mgr):
        mgr.register(PromptTemplate("v1 {x}", name="test"))
        mgr.update("test", PromptTemplate("v2 {x}", name="test"))
        mgr.update("test", PromptTemplate("v3 {x}", name="test"))

        v1 = mgr.get("test", version=1)
        assert v1.template == "v1 {x}"
        v3 = mgr.get("test", version=3)
        assert v3.template == "v3 {x}"

    def test_get_invalid_version(self, mgr):
        mgr.register(PromptTemplate("v1 {x}", name="test"))
        with pytest.raises(ValueError, match="Version 99 not found"):
            mgr.get("test", version=99)

    def test_rollback(self, mgr):
        mgr.register(PromptTemplate("v1 {x}", name="test"))
        mgr.update("test", PromptTemplate("v2 {x}", name="test"))
        mgr.update("test", PromptTemplate("v3 {x}", name="test"))

        rolled = mgr.rollback("test")
        assert rolled.template == "v2 {x}"
        assert mgr.get_version_count("test") == 2

    def test_rollback_multiple_steps(self, mgr):
        mgr.register(PromptTemplate("v1", name="test"))
        mgr.update("test", PromptTemplate("v2", name="test"))
        mgr.update("test", PromptTemplate("v3", name="test"))

        rolled = mgr.rollback("test", steps=2)
        assert rolled.template == "v1"

    def test_rollback_insufficient_versions(self, mgr):
        mgr.register(PromptTemplate("v1", name="test"))
        with pytest.raises(ValueError, match="Cannot rollback"):
            mgr.rollback("test")

    def test_update_not_found(self, mgr):
        with pytest.raises(KeyError, match="not found"):
            mgr.update("nonexistent", PromptTemplate("test"))

    def test_list_templates(self, mgr):
        mgr.register(PromptTemplate("a", name="t1"))
        mgr.register(PromptTemplate("b", name="t2"))
        names = mgr.list_templates()
        assert "t1" in names
        assert "t2" in names

    def test_has(self, mgr):
        mgr.register(PromptTemplate("test", name="exists"))
        assert mgr.has("exists")
        assert not mgr.has("nope")

    def test_remove(self, mgr):
        mgr.register(PromptTemplate("test", name="t1"))
        mgr.remove("t1")
        assert not mgr.has("t1")

    def test_validate_template(self, mgr):
        mgr.register(PromptTemplate("Hello {a} and {b}", name="test"))
        missing = mgr.validate_template("test", a="1")
        assert missing == ["b"]

    def test_get_versions(self, mgr):
        mgr.register(PromptTemplate("v1", name="test"))
        mgr.update("test", PromptTemplate("v2", name="test"))
        versions = mgr.get_versions("test")
        assert len(versions) == 2
        assert versions[0].version == 1
        assert versions[1].version == 2

    def test_get_version_count(self, mgr):
        mgr.register(PromptTemplate("v1", name="test"))
        assert mgr.get_version_count("test") == 1
        mgr.update("test", PromptTemplate("v2", name="test"))
        assert mgr.get_version_count("test") == 2
        assert mgr.get_version_count("nonexistent") == 0

    def test_load_from_file(self, mgr, tmp_path):
        filepath = tmp_path / "greeting.txt"
        filepath.write_text("Hello {name}!", encoding="utf-8")

        tpl = mgr.load_from_file(str(filepath))
        assert tpl.name == "greeting"
        assert tpl.template == "Hello {name}!"
        assert mgr.has("greeting")

    def test_load_from_file_with_name(self, mgr, tmp_path):
        filepath = tmp_path / "custom.txt"
        filepath.write_text("Test {var}", encoding="utf-8")

        tpl = mgr.load_from_file(str(filepath), name="my_template")
        assert tpl.name == "my_template"

    def test_load_from_file_not_found(self, mgr):
        with pytest.raises(FileNotFoundError):
            mgr.load_from_file("/nonexistent/path.txt")

    def test_load_from_dir(self, mgr, tmp_path):
        (tmp_path / "t1.txt").write_text("Template 1 {a}", encoding="utf-8")
        (tmp_path / "t2.md").write_text("Template 2 {b}", encoding="utf-8")
        (tmp_path / "t3.prompt").write_text("Template 3 {c}", encoding="utf-8")
        (tmp_path / "ignore.json").write_text("{}", encoding="utf-8")

        loaded = mgr.load_from_dir(str(tmp_path))
        assert "t1" in loaded
        assert "t2" in loaded
        assert "t3" in loaded
        assert "ignore" not in loaded

    def test_load_from_dir_not_found(self, mgr):
        with pytest.raises(FileNotFoundError):
            mgr.load_from_dir("/nonexistent/dir")

    def test_reload_unchanged(self, mgr, tmp_path):
        filepath = tmp_path / "test.txt"
        filepath.write_text("v1 {x}", encoding="utf-8")
        mgr.load_from_file(str(filepath))

        reloaded = mgr.reload()
        assert reloaded == []  # No changes

    def test_reload_changed(self, mgr, tmp_path):
        filepath = tmp_path / "test.txt"
        filepath.write_text("v1 {x}", encoding="utf-8")
        mgr.load_from_file(str(filepath))

        # Modify file
        time.sleep(0.1)
        filepath.write_text("v2 {x}", encoding="utf-8")

        reloaded = mgr.reload()
        assert "test" in reloaded
        latest = mgr.get("test")
        assert latest.template == "v2 {x}"

    def test_check_changed(self, mgr, tmp_path):
        filepath = tmp_path / "test.txt"
        filepath.write_text("v1", encoding="utf-8")
        mgr.load_from_file(str(filepath))

        # No changes
        assert mgr.check_changed() == []

        # Modify
        time.sleep(0.1)
        filepath.write_text("v2", encoding="utf-8")
        changed = mgr.check_changed()
        assert "test" in changed

    def test_export_import(self, mgr, tmp_path):
        mgr.register(PromptTemplate("Hello {name}!", name="greeting"))
        mgr.register(PromptTemplate("Bye {name}!", name="farewell"))

        filepath = str(tmp_path / "export.json")
        mgr.export(filepath)

        assert os.path.exists(filepath)

        # Import into new manager
        new_mgr = PromptManager()
        count = new_mgr.import_data(filepath)
        assert count == 2
        assert new_mgr.has("greeting")
        assert new_mgr.has("farewell")

    def test_export_returns_json_string(self, mgr):
        mgr.register(PromptTemplate("test {x}", name="t1"))
        json_str = mgr.export()
        data = json.loads(json_str)
        assert "templates" in data
        assert "t1" in data["templates"]

    def test_import_from_json_string(self, mgr):
        mgr.register(PromptTemplate("test {x}", name="t1"))
        json_str = mgr.export()

        new_mgr = PromptManager()
        count = new_mgr.import_data(json_str)
        assert count == 1

    def test_stats(self, mgr):
        mgr.register(PromptTemplate("t1 {x}", name="t1"))
        mgr.register(PromptTemplate("t2 {x}", name="t2"))
        mgr.update("t1", PromptTemplate("t1 v2 {x}", name="t1"))

        stats = mgr.stats()
        assert stats["template_count"] == 2
        assert stats["total_versions"] == 3

    def test_repr(self, mgr):
        mgr.register(PromptTemplate("t1", name="t1"))
        r = repr(mgr)
        assert "PromptManager" in r

    def test_len(self, mgr):
        mgr.register(PromptTemplate("t1", name="t1"))
        mgr.register(PromptTemplate("t2", name="t2"))
        assert len(mgr) == 2

    def test_contains(self, mgr):
        mgr.register(PromptTemplate("t1", name="t1"))
        assert "t1" in mgr
        assert "t2" not in mgr

    def test_chainable_register(self, mgr):
        mgr.register(PromptTemplate("t1", name="t1")).register(PromptTemplate("t2", name="t2"))
        assert len(mgr) == 2


# ═══════════════════════════════════════════════════════════════
#  TemplateVersion Tests
# ═══════════════════════════════════════════════════════════════


class TestTemplateVersion:
    """Test TemplateVersion dataclass."""

    def test_creation(self):
        tpl = PromptTemplate("test {x}", name="test")
        v = TemplateVersion(version=1, template=tpl)
        assert v.version == 1
        assert v.timestamp > 0

    def test_to_dict(self):
        tpl = PromptTemplate("test {x}", name="test")
        v = TemplateVersion(version=2, template=tpl, description="Updated")
        d = v.to_dict()
        assert d["version"] == 2
        assert d["template_str"] == "test {x}"
        assert d["version_description"] == "Updated"


# ═══════════════════════════════════════════════════════════════
#  PromptLibrary Tests
# ═══════════════════════════════════════════════════════════════


class TestPromptLibrary:
    """Test PromptLibrary predefined templates."""

    @pytest.fixture
    def lib(self):
        return PromptLibrary()

    def test_has_predefined_templates(self, lib):
        assert lib.has("system_general_en")
        assert lib.has("system_code_en")
        assert lib.has("system_research_en")
        assert lib.has("system_general_zh")
        assert lib.has("system_code_zh")
        assert lib.has("system_research_zh")
        assert lib.has("react_standard_en")
        assert lib.has("react_compact_en")
        assert lib.has("react_standard_zh")
        assert lib.has("tool_selection_guide_en")
        assert lib.has("tool_format_en")
        assert lib.has("orchestrator_en")
        assert lib.has("worker_en")
        assert lib.has("reviewer_en")

    def test_render_system_general_en(self, lib):
        result = lib.render("system_general_en")
        assert "helpful" in result.lower() or "assistant" in result.lower()

    def test_render_system_general_zh(self, lib):
        result = lib.render("system_general_zh")
        assert "助手" in result

    def test_render_react_standard_en(self, lib):
        result = lib.render(
            "react_standard_en",
            tools_desc="search: Search",
            history_desc="User: Hi",
            budget_desc="10 turns",
            task_desc="",
        )
        assert "ReAct" in result
        assert "search" in result

    def test_render_react_compact_en(self, lib):
        result = lib.render(
            "react_compact_en",
            tools_desc="t1",
            history_desc="h1",
            budget_desc="b1",
            task_desc="task1",
        )
        assert "t1" in result
        assert "task1" in result

    def test_list_templates(self, lib):
        names = lib.list_templates()
        assert len(names) >= 14

    def test_list_by_category_system(self, lib):
        system_templates = lib.list_by_category("system")
        assert len(system_templates) >= 6
        assert "system_general_en" in system_templates

    def test_list_by_category_react(self, lib):
        react_templates = lib.list_by_category("react")
        assert len(react_templates) >= 3
        assert "react_standard_en" in react_templates

    def test_list_by_category_tool(self, lib):
        tool_templates = lib.list_by_category("tool")
        assert len(tool_templates) >= 2

    def test_list_by_category_agent(self, lib):
        agent_templates = lib.list_by_category("agent")
        assert len(agent_templates) >= 3

    def test_list_by_language_en(self, lib):
        en_templates = lib.list_by_language("en")
        assert len(en_templates) >= 8

    def test_list_by_language_zh(self, lib):
        zh_templates = lib.list_by_language("zh")
        assert len(zh_templates) >= 4

    def test_add_custom(self, lib):
        lib.add("custom", PromptTemplate("Custom {x}"))
        assert lib.has("custom")
        result = lib.render("custom", x="value")
        assert "value" in result

    def test_stats(self, lib):
        stats = lib.stats()
        assert stats["template_count"] >= 14
        assert "categories" in stats
        assert "languages" in stats
        assert stats["categories"]["system"] >= 6
        assert stats["languages"]["en"] >= 8

    def test_manager_access(self, lib):
        mgr = lib.manager
        assert isinstance(mgr, PromptManager)

    def test_render_safe(self, lib):
        result = lib.render_safe("react_standard_en")
        # Should not raise, missing vars replaced with empty strings
        assert isinstance(result, str)

    def test_repr(self, lib):
        r = repr(lib)
        assert "PromptLibrary" in r

    def test_len(self, lib):
        assert len(lib) >= 14

    def test_contains(self, lib):
        assert "system_general_en" in lib
        assert "nonexistent" not in lib

    def test_orchestrator_render(self, lib):
        result = lib.render(
            "orchestrator_en",
            agent_descriptions="A1: coder",
            collaboration_rules="Share info",
            task="Build app",
        )
        assert "Orchestrator Agent" in result
        assert "A1: coder" in result
        assert "Share info" in result
        assert "Build app" in result

    def test_worker_render(self, lib):
        result = lib.render(
            "worker_en",
            agent_name="coder",
            specialty="Python",
            sub_task="Write tests",
            tools_desc="pytest",
        )
        assert "coder" in result
        assert "Python" in result
        assert "Write tests" in result

    def test_reviewer_render(self, lib):
        result = lib.render(
            "reviewer_en",
            work_to_review="Some code here",
        )
        assert "Some code here" in result
        assert "Correctness" in result


# ═══════════════════════════════════════════════════════════════
#  Convenience Functions Tests
# ═══════════════════════════════════════════════════════════════


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_get_library_singleton(self):
        lib1 = get_library()
        lib2 = get_library()
        assert lib1 is lib2

    def test_get_template(self):
        tpl = get_template("system_general_en")
        assert tpl is not None
        assert tpl.name == "system_general_en"

    def test_render_template(self):
        result = render_template(
            "react_standard_en",
            tools_desc="t1",
            history_desc="h1",
            budget_desc="b1",
            task_desc="",
        )
        assert "ReAct" in result
