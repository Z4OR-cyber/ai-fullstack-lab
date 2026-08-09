"""Suyi Phase 1 集成测试.

验证三大核心模块（Memory + Core + Tools）的导入、功能和交叉引用.
"""

import tempfile
import pytest


class TestMemorySystem:
    """记忆系统测试."""

    def test_memory_manager_init(self):
        from suyi import MemoryManager
        mgr = MemoryManager(storage_dir=tempfile.mkdtemp())
        assert mgr is not None

    def test_add_and_retrieve(self):
        from suyi import MemoryManager
        mgr = MemoryManager(storage_dir=tempfile.mkdtemp())
        mgr.add_memory("Python GIL prevents true multithreading", tags=["python"])
        mgr.add_memory("Rust uses ownership model for memory safety", tags=["rust"])
        results = mgr.retrieve_relevant("Python threading")
        assert len(results) > 0
        assert "Python" in results[0].get("content", "") or "GIL" in results[0].get("content", "")

    def test_three_layers(self):
        from suyi.memory import WorkingMemory, EpisodicMemory, SemanticMemory
        wm = WorkingMemory()
        em = EpisodicMemory()
        sm = SemanticMemory()
        assert wm is not None
        assert em is not None
        assert sm is not None

    def test_lifecycle(self):
        from suyi import MemoryLifecycle
        lc = MemoryLifecycle()
        assert lc is not None


class TestToolSystem:
    """工具系统测试."""

    def test_builtin_tools(self):
        from suyi import get_builtin_tools
        tools = get_builtin_tools()
        names = [t.name for t in tools]
        assert "bash" in names
        assert "read_file" in names
        assert "write_file" in names
        assert "search" in names
        assert "skill" in names

    def test_permission_auto(self):
        from suyi import BashTool, PERMISSION_AUTO
        bash = BashTool()
        risk = bash.assess_risk({"command": "ls -la"}, {})
        assert risk == PERMISSION_AUTO

    def test_permission_block(self):
        from suyi import BashTool, PERMISSION_BLOCK
        bash = BashTool()
        risk = bash.assess_risk({"command": "rm -rf /"}, {})
        assert risk == PERMISSION_BLOCK

    def test_tool_schema(self):
        from suyi import BashTool
        bash = BashTool()
        schema = bash.to_schema()
        assert schema["name"] == "bash"
        assert "description" in schema

    def test_permission_manager(self):
        from suyi import PermissionManager
        pm = PermissionManager()
        assert pm is not None


class TestCoreLoop:
    """核心循环测试."""

    def test_mock_llm(self):
        from suyi import MockLLM, LLMResponse
        mock = MockLLM([
            LLMResponse.action("search", {"query": "test"}),
            LLMResponse.text("Done."),
        ])
        assert len(mock._responses) == 2

    def test_budget_tracker(self):
        from suyi import BudgetTracker, BudgetConfig
        budget = BudgetTracker(config=BudgetConfig(max_tokens=8192))
        status = budget.status()
        assert status.turns_used == 0

    def test_context_assembler(self):
        from suyi import ContextAssembler, IdentityConfig, ProjectRules
        ctx = ContextAssembler(
            identity=IdentityConfig(name="Suyi"),
            project_rules=ProjectRules(rules=["Be helpful"]),
        )
        assert ctx is not None


class TestUtils:
    """工具函数测试."""

    def test_estimate_tokens_english(self):
        from suyi import estimate_tokens
        tokens = estimate_tokens("Hello World")
        assert tokens > 0

    def test_estimate_tokens_chinese(self):
        from suyi import estimate_tokens
        tokens = estimate_tokens("你好世界")
        assert tokens > 0

    def test_token_counter_class(self):
        from suyi import TokenCounter
        assert TokenCounter.count("Hello") > 0

    def test_strip_html(self):
        from suyi import strip_html
        result = strip_html("<p>Hello</p>")
        assert "Hello" in result
        assert "<" not in result

    def test_extract_summary(self):
        from suyi import extract_summary
        text = "This is a long sentence. It has multiple parts. The end."
        summary = extract_summary(text, max_length=20)
        assert len(summary) <= 30  # allow slight overflow for sentence boundary

    def test_encode_xml_tag(self):
        from suyi import encode_xml_tag
        result = encode_xml_tag("test", "content")
        assert "<test>" in result
        assert "content" in result


class TestIntegration:
    """端到端集成测试."""

    def test_full_chain(self):
        from suyi import (
            MemoryManager,
            ContextAssembler,
            IdentityConfig,
            ProjectRules,
            BudgetTracker,
            BudgetConfig,
            MockLLM,
            LLMResponse,
            get_builtin_tools,
        )

        # Memory
        mgr = MemoryManager(storage_dir=tempfile.mkdtemp())
        mgr.add_memory("Test memory entry", tags=["test"])
        results = mgr.retrieve_relevant("test")
        assert len(results) > 0

        # Tools
        tools = get_builtin_tools()
        assert len(tools) >= 5

        # Context
        ctx = ContextAssembler(
            identity=IdentityConfig(name="Suyi"),
            project_rules=ProjectRules(rules=["Be helpful"]),
        )

        # Budget
        budget = BudgetTracker(config=BudgetConfig(max_tokens=8192))
        assert budget.status().level.value == "normal"

        # LLM
        mock = MockLLM([
            LLMResponse.text("Final answer."),
        ])
        assert len(mock._responses) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
