"""
Structured Goal — 结构化目标模板测试.

覆盖：
    - StructuredGoal 所有字段和默认值
    - to_prompt() 格式化输出
    - validate() 完整性检查
    - to_dict() / from_dict() 序列化/反序列化
    - __str__ 人类可读格式
    - Priority 枚举
    - 边界条件和异常处理
"""

import pytest
from suyi.core.goal import StructuredGoal, Priority


# ═══════════════════════════════════════════════════════════════
# 基础构建与字段测试
# ═══════════════════════════════════════════════════════════════

class TestStructuredGoalFields:
    """测试 StructuredGoal 的字段定义和默认值。"""

    def test_minimal_goal(self):
        """只传必填字段 result，其余取默认值。"""
        goal = StructuredGoal(result="写一份报告")
        assert goal.result == "写一份报告"
        assert goal.info_sources == []
        assert goal.constraints == []
        assert goal.deliverables == []
        assert goal.priority == "normal"
        assert goal.timeout is None
        assert goal.tags == []

    def test_full_goal(self):
        """传入所有字段。"""
        goal = StructuredGoal(
            result="市场分析",
            info_sources=["行业报告", "竞品官网"],
            constraints=["字数不超过3000", "中文"],
            deliverables=["markdown文档", "数据表格"],
            priority="high",
            timeout=3600,
            tags=["market", "analysis"],
        )
        assert goal.result == "市场分析"
        assert len(goal.info_sources) == 2
        assert len(goal.constraints) == 2
        assert len(goal.deliverables) == 2
        assert goal.priority == "high"
        assert goal.timeout == 3600
        assert goal.tags == ["market", "analysis"]

    def test_default_priority_is_normal(self):
        """默认优先级为 normal。"""
        goal = StructuredGoal(result="测试")
        assert goal.priority == "normal"

    def test_all_priority_values(self):
        """所有优先级枚举值都合法。"""
        for p in ["low", "normal", "high", "critical"]:
            goal = StructuredGoal(result="测试", priority=p)
            assert goal.priority == p

    def test_invalid_priority_raises(self):
        """无效优先级应抛出 ValueError。"""
        with pytest.raises(ValueError, match="priority"):
            StructuredGoal(result="测试", priority="urgent")

    def test_empty_result_is_allowed(self):
        """空 result 允许创建（validate 会检测问题）。"""
        goal = StructuredGoal(result="")
        assert goal.result == ""

    def test_tags_default_independent(self):
        """不同实例的 tags 列表互不影响。"""
        g1 = StructuredGoal(result="A", tags=["x"])
        g2 = StructuredGoal(result="B")
        g1.tags.append("y")
        assert "y" not in g2.tags

    def test_info_sources_default_independent(self):
        """不同实例的 info_sources 列表互不影响。"""
        g1 = StructuredGoal(result="A", info_sources=["src1"])
        g2 = StructuredGoal(result="B")
        g1.info_sources.append("src2")
        assert "src2" not in g2.info_sources


# ═══════════════════════════════════════════════════════════════
# Priority 枚举测试
# ═══════════════════════════════════════════════════════════════

class TestPriorityEnum:
    """测试 Priority 枚举。"""

    def test_priority_values(self):
        assert Priority.LOW.value == "low"
        assert Priority.NORMAL.value == "normal"
        assert Priority.HIGH.value == "high"
        assert Priority.CRITICAL.value == "critical"

    def test_priority_is_str(self):
        """Priority 继承 str，可直接当字符串用。"""
        assert isinstance(Priority.HIGH, str)
        assert Priority.HIGH == "high"


# ═══════════════════════════════════════════════════════════════
# to_prompt() 测试
# ═══════════════════════════════════════════════════════════════

class TestToPrompt:
    """测试 to_prompt() 方法。"""

    def test_basic_prompt_structure(self):
        """基本 prompt 包含四个核心段落。"""
        goal = StructuredGoal(
            result="分析竞品",
            info_sources=["官网"],
            constraints=["中文"],
            deliverables=["报告"],
        )
        prompt = goal.to_prompt()
        assert "# 任务目标" in prompt
        assert "## 期望结果" in prompt
        assert "## 信息源" in prompt
        assert "## 约束条件" in prompt
        assert "## 交付物" in prompt
        assert "分析竞品" in prompt
        assert "- 官网" in prompt
        assert "- 中文" in prompt
        assert "- 报告" in prompt

    def test_prompt_with_empty_sources(self):
        """空信息源显示"未指定"。"""
        goal = StructuredGoal(result="测试")
        prompt = goal.to_prompt()
        assert "（未指定）" in prompt

    def test_prompt_with_empty_constraints(self):
        """空约束显示"无特殊约束"。"""
        goal = StructuredGoal(result="测试")
        prompt = goal.to_prompt()
        assert "（无特殊约束）" in prompt

    def test_prompt_omits_default_priority(self):
        """默认优先级 normal 不在 prompt 中显示。"""
        goal = StructuredGoal(result="测试", priority="normal")
        prompt = goal.to_prompt()
        assert "## 优先级" not in prompt

    def test_prompt_shows_non_default_priority(self):
        """非默认优先级在 prompt 中显示。"""
        goal = StructuredGoal(result="测试", priority="critical")
        prompt = goal.to_prompt()
        assert "## 优先级" in prompt
        assert "critical" in prompt

    def test_prompt_shows_timeout(self):
        """指定 timeout 时在 prompt 中显示。"""
        goal = StructuredGoal(result="测试", timeout=120)
        prompt = goal.to_prompt()
        assert "## 超时限制" in prompt
        assert "120 秒" in prompt

    def test_prompt_shows_tags(self):
        """指定 tags 时在 prompt 中显示。"""
        goal = StructuredGoal(result="测试", tags=["ai", "nlp"])
        prompt = goal.to_prompt()
        assert "## 标签" in prompt
        assert "ai, nlp" in prompt

    def test_prompt_multiple_sources(self):
        """多个信息源正确列出。"""
        goal = StructuredGoal(
            result="X", info_sources=["A", "B", "C"],
            constraints=["Y"], deliverables=["Z"],
        )
        prompt = goal.to_prompt()
        assert "- A" in prompt
        assert "- B" in prompt
        assert "- C" in prompt


# ═══════════════════════════════════════════════════════════════
# validate() 测试
# ═══════════════════════════════════════════════════════════════

class TestValidate:
    """测试 validate() 方法。"""

    def test_full_goal_valid(self):
        """完整目标返回空列表。"""
        goal = StructuredGoal(
            result="分析",
            info_sources=["src"],
            constraints=["con"],
            deliverables=["del"],
        )
        assert goal.validate() == []

    def test_missing_result(self):
        """空 result 报错。"""
        goal = StructuredGoal(
            result="",
            info_sources=["s"], constraints=["c"], deliverables=["d"],
        )
        issues = goal.validate()
        assert any("result" in i for i in issues)

    def test_missing_whitespace_result(self):
        """纯空白 result 也报错。"""
        goal = StructuredGoal(
            result="   ",
            info_sources=["s"], constraints=["c"], deliverables=["d"],
        )
        issues = goal.validate()
        assert any("result" in i for i in issues)

    def test_missing_sources(self):
        goal = StructuredGoal(
            result="r", constraints=["c"], deliverables=["d"],
        )
        issues = goal.validate()
        assert any("info_sources" in i for i in issues)

    def test_missing_constraints(self):
        goal = StructuredGoal(
            result="r", info_sources=["s"], deliverables=["d"],
        )
        issues = goal.validate()
        assert any("constraints" in i for i in issues)

    def test_missing_deliverables(self):
        goal = StructuredGoal(
            result="r", info_sources=["s"], constraints=["c"],
        )
        issues = goal.validate()
        assert any("deliverables" in i for i in issues)

    def test_minimal_goal_has_multiple_issues(self):
        """只传 result 的空目标，缺少三个要素。"""
        goal = StructuredGoal(result="只做一件事")
        issues = goal.validate()
        # 缺少 info_sources, constraints, deliverables
        assert len(issues) >= 3

    def test_invalid_timeout_negative(self):
        """负数 timeout 报错。"""
        goal = StructuredGoal(
            result="r", info_sources=["s"],
            constraints=["c"], deliverables=["d"],
            timeout=-10,
        )
        issues = goal.validate()
        assert any("timeout" in i for i in issues)

    def test_invalid_timeout_zero(self):
        """零 timeout 报错。"""
        goal = StructuredGoal(
            result="r", info_sources=["s"],
            constraints=["c"], deliverables=["d"],
            timeout=0,
        )
        issues = goal.validate()
        assert any("timeout" in i for i in issues)

    def test_valid_timeout(self):
        """正整数 timeout 不报错。"""
        goal = StructuredGoal(
            result="r", info_sources=["s"],
            constraints=["c"], deliverables=["d"],
            timeout=60,
        )
        issues = goal.validate()
        assert not any("timeout" in i for i in issues)


# ═══════════════════════════════════════════════════════════════
# to_dict() / from_dict() 测试
# ═══════════════════════════════════════════════════════════════

class TestSerialization:
    """测试序列化/反序列化。"""

    def test_to_dict_contains_all_fields(self):
        """to_dict 包含所有字段。"""
        goal = StructuredGoal(
            result="分析", info_sources=["A"],
            constraints=["B"], deliverables=["C"],
            priority="high", timeout=100, tags=["t1"],
        )
        d = goal.to_dict()
        assert d["result"] == "分析"
        assert d["info_sources"] == ["A"]
        assert d["constraints"] == ["B"]
        assert d["deliverables"] == ["C"]
        assert d["priority"] == "high"
        assert d["timeout"] == 100
        assert d["tags"] == ["t1"]

    def test_from_dict_roundtrip(self):
        """to_dict → from_dict 往返一致。"""
        original = StructuredGoal(
            result="测试", info_sources=["src"],
            constraints=["con"], deliverables=["del"],
            priority="critical", timeout=600, tags=["a", "b"],
        )
        d = original.to_dict()
        restored = StructuredGoal.from_dict(d)
        assert restored.result == original.result
        assert restored.info_sources == original.info_sources
        assert restored.constraints == original.constraints
        assert restored.deliverables == original.deliverables
        assert restored.priority == original.priority
        assert restored.timeout == original.timeout
        assert restored.tags == original.tags

    def test_from_dict_minimal(self):
        """只有 result 的字典也能反序列化。"""
        d = {"result": "最小目标"}
        goal = StructuredGoal.from_dict(d)
        assert goal.result == "最小目标"
        assert goal.info_sources == []
        assert goal.priority == "normal"

    def test_from_dict_missing_result_raises(self):
        """缺少 result 字段应抛出 KeyError。"""
        with pytest.raises(KeyError):
            StructuredGoal.from_dict({"info_sources": ["x"]})

    def test_to_dict_returns_copy(self):
        """to_dict 返回的列表是副本，修改不影响原对象。"""
        goal = StructuredGoal(result="X", tags=["a"])
        d = goal.to_dict()
        d["tags"].append("b")
        assert "b" not in goal.tags


# ═══════════════════════════════════════════════════════════════
# __str__ 测试
# ═══════════════════════════════════════════════════════════════

class TestStr:
    """测试 __str__ 人类可读格式。"""

    def test_basic_str(self):
        """基本格式包含 result。"""
        goal = StructuredGoal(result="完成报告")
        s = str(goal)
        assert "完成报告" in s

    def test_str_shows_counts(self):
        """显示各类列表的数量。"""
        goal = StructuredGoal(
            result="X", info_sources=["a", "b"],
            constraints=["c"], deliverables=["d"],
        )
        s = str(goal)
        assert "sources=2" in s
        assert "constraints=1" in s
        assert "deliverables=1" in s

    def test_str_omits_default_priority(self):
        """默认优先级不显示。"""
        goal = StructuredGoal(result="X")
        s = str(goal)
        assert "priority" not in s

    def test_str_shows_priority(self):
        """非默认优先级显示。"""
        goal = StructuredGoal(result="X", priority="high")
        s = str(goal)
        assert "priority=high" in s

    def test_str_shows_timeout(self):
        """指定 timeout 时显示。"""
        goal = StructuredGoal(result="X", timeout=300)
        s = str(goal)
        assert "timeout=300s" in s

    def test_str_shows_tags(self):
        """指定 tags 时显示。"""
        goal = StructuredGoal(result="X", tags=["fast", "important"])
        s = str(goal)
        assert "fast" in s
        assert "important" in s
