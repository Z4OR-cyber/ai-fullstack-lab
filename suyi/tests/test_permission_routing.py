"""
Permission-Aware Routing — 权限感知路由测试.

覆盖：
    - TaskComplexity.detect_sensitive_operations() 敏感关键词检测
    - RoutingDecision.requires_trusted_model 字段
    - RoutingDecision.__repr__ trusted 标记
    - AutoRouter 敏感操作强制 STANDARD+ 层级
    - 非敏感操作正常路由
    - score_breakdown 中的 trusted_model_required
    - 边界条件：空消息、多模态消息等
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from suyi.llm.auto_router import (
    AutoRouter,
    ModelTier,
    TaskComplexity,
    RoutingDecision,
    _SENSITIVE_OPERATION_KEYWORDS,
    _DEFAULT_MODEL_TIERS,
)
from suyi.core.loop import LLMResponse, ToolCall


# ═══════════════════════════════════════════════════════════════
# 测试辅助
# ═══════════════════════════════════════════════════════════════

class FakeAdapter:
    """模拟LLM适配器，用于测试AutoRouter。"""

    def __init__(self):
        self.model = "auto"
        self.call_count = 0
        self._client = None

    async def chat(self, messages, tools, system_prompt) -> LLMResponse:
        self.call_count += 1
        return LLMResponse(
            content="ok",
            tool_calls=[],
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

    async def chat_stream(self, messages, tools, system_prompt):
        yield {"content": "ok"}


def make_messages(text: str, role: str = "user") -> list[dict]:
    """快捷构建消息列表。"""
    return [{"role": role, "content": text}]


# ═══════════════════════════════════════════════════════════════
# TaskComplexity.detect_sensitive_operations() 测试
# ═══════════════════════════════════════════════════════════════

class TestDetectSensitiveOperations:
    """测试敏感操作检测。"""

    def test_no_sensitive_keywords(self):
        """不含敏感关键词时返回 False。"""
        messages = make_messages("你好，请帮我翻译这段文字")
        assert TaskComplexity.detect_sensitive_operations(messages, "") is False

    def test_file_write_detection(self):
        """检测文件写入关键词。"""
        messages = make_messages("请 write_file 把这个内容保存到文件")
        assert TaskComplexity.detect_sensitive_operations(messages, "") is True

    def test_code_execution_detection(self):
        """检测代码执行关键词。"""
        messages = make_messages("执行代码 subprocess.run(['ls'])")
        assert TaskComplexity.detect_sensitive_operations(messages, "") is True

    def test_security_audit_detection(self):
        """检测安全审计关键词。"""
        messages = make_messages("对系统进行 security_audit")
        assert TaskComplexity.detect_sensitive_operations(messages, "") is True

    def test_database_operation_detection(self):
        """检测数据库操作关键词。"""
        messages = make_messages("请 execute_sql DROP TABLE users")
        assert TaskComplexity.detect_sensitive_operations(messages, "") is True

    def test_system_config_detection(self):
        """检测系统配置关键词。"""
        messages = make_messages("需要 system_config 修改配置")
        assert TaskComplexity.detect_sensitive_operations(messages, "") is True

    def test_credential_handling_detection(self):
        """检测凭证处理关键词。"""
        messages = make_messages("帮我 decrypt 这个 password")
        assert TaskComplexity.detect_sensitive_operations(messages, "") is True

    def test_chinese_keywords_detection(self):
        """中文敏感关键词也能检测。"""
        messages = make_messages("请写入文件到 /etc/passwd")
        assert TaskComplexity.detect_sensitive_operations(messages, "") is True

    def test_system_prompt_detection(self):
        """从 system_prompt 中检测敏感关键词。"""
        messages = make_messages("你好")
        system_prompt = "你是一个助手，可以 execute_code 执行代码"
        assert TaskComplexity.detect_sensitive_operations(messages, system_prompt) is True

    def test_empty_inputs(self):
        """空消息和空 system_prompt 返回 False。"""
        assert TaskComplexity.detect_sensitive_operations([], "") is False
        assert TaskComplexity.detect_sensitive_operations([], None) is False

    def test_multimodal_message(self):
        """多模态消息（content 为列表）也能检测。"""
        messages = [{
            "role": "user",
            "content": [{"type": "text", "text": "请 write_file 保存"}],
        }]
        assert TaskComplexity.detect_sensitive_operations(messages, "") is True


# ═══════════════════════════════════════════════════════════════
# score_breakdown 中的 trusted_model_required 测试
# ═══════════════════════════════════════════════════════════════

class TestScoreBreakdown:
    """测试 estimate() 的 breakdown 中包含 trusted_model_required。"""

    def test_breakdown_has_trusted_key(self):
        """breakdown 包含 trusted_model_required 键。"""
        _, breakdown = TaskComplexity.estimate(
            make_messages("hello"), [], ""
        )
        assert "trusted_model_required" in breakdown

    def test_breakdown_no_sensitive(self):
        """无敏感操作时 trusted_model_required 为 0。"""
        _, breakdown = TaskComplexity.estimate(
            make_messages("翻译这段文字"), [], ""
        )
        assert breakdown["trusted_model_required"] == 0

    def test_breakdown_with_sensitive(self):
        """有敏感操作时 trusted_model_required > 0。"""
        _, breakdown = TaskComplexity.estimate(
            make_messages("请 write_file 保存代码"), [], ""
        )
        assert breakdown["trusted_model_required"] > 0

    def test_score_not_inflated_by_trusted(self):
        """trusted_model_required 不影响综合分数。"""
        score_normal, _ = TaskComplexity.estimate(
            make_messages("a" * 200), [], "x" * 100,
        )
        score_sensitive, _ = TaskComplexity.estimate(
            make_messages("write_file " + "a" * 200), [], "x" * 100,
        )
        # 两者分数应该接近（敏感检测不参与归一化）
        assert abs(score_normal - score_sensitive) <= 5


# ═══════════════════════════════════════════════════════════════
# RoutingDecision.requires_trusted_model 测试
# ═══════════════════════════════════════════════════════════════

class TestRoutingDecisionTrusted:
    """测试 RoutingDecision 的 trusted 相关字段。"""

    def test_default_not_trusted(self):
        """默认 requires_trusted_model 为 False。"""
        d = RoutingDecision(
            timestamp=0, complexity_score=50,
            tier=ModelTier.STANDARD, selected_model="auto",
        )
        assert d.requires_trusted_model is False

    def test_trusted_true(self):
        """可以设置 requires_trusted_model=True。"""
        d = RoutingDecision(
            timestamp=0, complexity_score=50,
            tier=ModelTier.STANDARD, selected_model="auto",
            requires_trusted_model=True,
        )
        assert d.requires_trusted_model is True

    def test_repr_shows_trusted(self):
        """__repr__ 显示 [trusted] 标记。"""
        d = RoutingDecision(
            timestamp=0, complexity_score=50,
            tier=ModelTier.STANDARD, selected_model="auto",
            requires_trusted_model=True,
        )
        assert "[trusted]" in repr(d)

    def test_repr_no_trusted(self):
        """__repr__ 不显示 [trusted] 当不需要时。"""
        d = RoutingDecision(
            timestamp=0, complexity_score=50,
            tier=ModelTier.STANDARD, selected_model="auto",
            requires_trusted_model=False,
        )
        assert "[trusted]" not in repr(d)


# ═══════════════════════════════════════════════════════════════
# AutoRouter 权限感知路由测试
# ═══════════════════════════════════════════════════════════════

class TestAutoRouterPermissionRouting:
    """测试 AutoRouter 的权限感知路由行为。"""

    @pytest.fixture
    def router(self):
        """创建测试用路由器。"""
        adapter = FakeAdapter()
        return AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["gemini-flash"],
                ModelTier.STANDARD: ["gpt-4o"],
                ModelTier.COMPLEX: ["o1-preview"],
            },
            strategy="first",
            enable_fallback=False,
        )

    @pytest.mark.asyncio
    async def test_sensitive_promotes_simple_to_standard(self, router):
        """敏感操作 + 简单任务 → 强制使用 STANDARD 层级。"""
        messages = make_messages("hi")  # 很短，正常会是 SIMPLE
        system_prompt = "你可以 write_file 保存文件"  # 但含敏感操作
        await router.chat(messages, [], system_prompt)
        decision = router.last_decision
        assert decision.requires_trusted_model is True
        assert decision.tier == ModelTier.STANDARD

    @pytest.mark.asyncio
    async def test_non_sensitive_stays_simple(self, router):
        """非敏感 + 简单任务 → 保持 SIMPLE。"""
        messages = make_messages("你好")
        await router.chat(messages, [], "")
        decision = router.last_decision
        assert decision.requires_trusted_model is False
        # 短消息 + 无工具 → SIMPLE
        assert decision.tier == ModelTier.SIMPLE

    @pytest.mark.asyncio
    async def test_sensitive_with_already_complex_stays_complex(self, router):
        """敏感操作 + 已经是复杂任务 → 不降级，保持 COMPLEX。"""
        # 构造一个长文本使其复杂度达到 COMPLEX
        long_text = "analyze " * 200 + "write_file"
        messages = make_messages(long_text)
        await router.chat(messages, [{"name": "t1"}] * 10, "x" * 3000)
        decision = router.last_decision
        assert decision.requires_trusted_model is True
        # 应该是 COMPLEX 或至少 STANDARD（不应是 SIMPLE）
        assert decision.tier != ModelTier.SIMPLE

    @pytest.mark.asyncio
    async def test_decision_records_trusted_flag(self, router):
        """决策记录正确反映 trusted 标记。"""
        messages = make_messages("请 execute_code 运行脚本")
        await router.chat(messages, [], "")
        decision = router.last_decision
        assert decision.requires_trusted_model is True
        assert decision.score_breakdown.get("trusted_model_required", 0) > 0

    @pytest.mark.asyncio
    async def test_non_sensitive_decision_no_trusted(self, router):
        """非敏感操作的决策不带 trusted 标记。"""
        messages = make_messages("帮我翻译这段话")
        await router.chat(messages, [], "")
        decision = router.last_decision
        assert decision.requires_trusted_model is False

    @pytest.mark.asyncio
    async def test_history_preserves_trusted_flag(self, router):
        """历史记录中保留 trusted 标记。"""
        # 先执行一个敏感操作
        await router.chat(make_messages("write_file test"), [], "")
        assert router.history[-1].requires_trusted_model is True

        # 再执行一个非敏感操作
        await router.chat(make_messages("hello"), [], "")
        assert router.history[-1].requires_trusted_model is False

        # 历史第一条还是 True
        decisions = router.get_recent_decisions(2)
        assert decisions[0].requires_trusted_model is True
        assert decisions[1].requires_trusted_model is False


# ═══════════════════════════════════════════════════════════════
# 边界条件测试
# ═══════════════════════════════════════════════════════════════

class TestPermissionEdgeCases:
    """权限感知路由的边界条件。"""

    def test_empty_messages_no_false_positive(self):
        """空消息不应误判为敏感操作。"""
        assert TaskComplexity.detect_sensitive_operations([], "") is False

    def test_partial_keyword_no_match(self):
        """关键词的部分匹配不应触发（如 'write' 不是 'write_file'）。"""
        messages = make_messages("please write a poem about the sea")
        # 'write' 本身不在敏感关键词列表中
        assert TaskComplexity.detect_sensitive_operations(messages, "") is False

    def test_case_sensitivity(self):
        """检测是大小写不敏感的。"""
        messages = make_messages("WRITE_FILE important stuff")
        assert TaskComplexity.detect_sensitive_operations(messages, "") is True

    def test_multiple_sensitive_keywords(self):
        """多个敏感关键词命中时正确累计。"""
        messages = make_messages("write_file and execute_code and decrypt password")
        _, breakdown = TaskComplexity.estimate(messages, [], "")
        assert breakdown["trusted_model_required"] >= 3
