"""
AutoRouter 智能LLM路由器 — 全面测试。

覆盖：
    - TaskComplexity 五维评分
    - ModelClassifier 模型分类
    - ModelTier 边界条件
    - AutoRouter 路由决策
    - AutoRouter 降级fallback
    - AutoRouter 轮询策略
    - AutoRouter 统计
    - AutoRouter 模型发现
    - AutoRouter 流式
    - AutoRouter LLMInterface协议兼容
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from suyi.llm.auto_router import (
    AutoRouter,
    ModelTier,
    ModelClassifier,
    TaskComplexity,
    RoutingDecision,
    _DEFAULT_MODEL_TIERS,
    _COMPLEXITY_KEYWORDS,
    _SIMPLICITY_KEYWORDS,
)
from suyi.core.loop import LLMResponse, ToolCall


# ═══════════════════════════════════════════════════════════════
# 测试辅助
# ═══════════════════════════════════════════════════════════════

class FakeAdapter:
    """模拟LLM适配器，用于测试AutoRouter。"""

    def __init__(self, fail_models: set[str] | None = None):
        self.model = "auto"
        self._fail_models = fail_models or set()
        self.call_count = 0
        self._client = None

    async def chat(self, messages, tools, system_prompt) -> LLMResponse:
        self.call_count += 1
        if self.model in self._fail_models:
            raise RuntimeError(f"模拟失败: {self.model}")
        return LLMResponse(
            content=f"[{self.model}] 回复",
            tool_calls=[],
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    async def chat_stream(self, messages, tools, system_prompt):
        if self.model in self._fail_models:
            raise RuntimeError(f"模拟流式失败: {self.model}")
        for chunk in ["Hello", " ", "World"]:
            yield chunk

    async def close(self):
        pass

    async def list_models(self):
        return [
            {"id": "gpt-4o-mini", "object": "model"},
            {"id": "gpt-4o", "object": "model"},
            {"id": "openai/o1-preview", "object": "model"},
            {"id": "google/gemini-flash-1.5", "object": "model"},
            {"id": "anthropic/claude-3.5-sonnet", "object": "model"},
            {"id": "anthropic/claude-3-opus", "object": "model"},
            {"id": "deepseek-chat", "object": "model"},
            {"id": "deepseek-coder", "object": "model"},
        ]

    async def health_check(self):
        return {"status": "ok"}


def make_messages(text: str, count: int = 1) -> list[dict]:
    """生成对话消息。"""
    return [{"role": "user", "content": text} for _ in range(count)]


def make_tools(count: int) -> list[dict]:
    """生成工具定义。"""
    return [
        {"type": "function", "function": {"name": f"tool_{i}", "description": f"Tool {i}"}}
        for i in range(count)
    ]


# ═══════════════════════════════════════════════════════════════
# TaskComplexity 测试
# ═══════════════════════════════════════════════════════════════

class TestTaskComplexity:

    def test_simple_short_message(self):
        """短消息+无工具 → 低分。"""
        messages = make_messages("hello")
        score, breakdown = TaskComplexity.estimate(messages, [], "")
        assert 0 <= score <= 35
        assert breakdown["prompt_length"] == 5
        assert breakdown["tool_count"] == 5

    def test_long_message(self):
        """长消息 → prompt_length高分。"""
        long_text = "x" * 6000
        messages = make_messages(long_text)
        score, breakdown = TaskComplexity.estimate(messages, [], "")
        assert breakdown["prompt_length"] == 40
        assert score > 20

    def test_very_long_message(self):
        """超长消息 → prompt_length最高分。"""
        long_text = "x" * 12000
        messages = make_messages(long_text)
        score, breakdown = TaskComplexity.estimate(messages, [], "")
        assert breakdown["prompt_length"] == 45

    def test_many_tools(self):
        """工具数多 → tool_count高分。"""
        messages = make_messages("test")
        tools = make_tools(10)
        score, breakdown = TaskComplexity.estimate(messages, tools, "")
        assert breakdown["tool_count"] == 35

    def test_no_tools(self):
        """无工具 → tool_count最低分。"""
        messages = make_messages("test")
        score, breakdown = TaskComplexity.estimate(messages, [], "")
        assert breakdown["tool_count"] == 5

    def test_medium_tools(self):
        """中等工具数。"""
        messages = make_messages("test")
        tools = make_tools(5)
        score, breakdown = TaskComplexity.estimate(messages, tools, "")
        assert breakdown["tool_count"] == 25

    def test_complex_keywords(self):
        """复杂关键词 → keywords高分。"""
        text = "Please analyze and debug the architecture, then evaluate security vulnerabilities."
        messages = make_messages(text)
        score, breakdown = TaskComplexity.estimate(messages, [], "")
        assert breakdown["keywords"] >= 15
        assert score > 15

    def test_chinese_complex_keywords(self):
        """中文复杂关键词。"""
        text = "请深入分析架构设计，全面审查安全漏洞并进行渗透测试"
        messages = make_messages(text)
        score, breakdown = TaskComplexity.estimate(messages, [], "")
        assert breakdown["keywords"] >= 15

    def test_simple_keywords_reduce_score(self):
        """简单关键词降低复杂度。"""
        text = "hello, thanks, what is this? please summarize"
        messages = make_messages(text)
        score, breakdown = TaskComplexity.estimate(messages, [], "")
        # 简单关键词会减少分数，但不能低于0
        assert breakdown["keywords"] >= 0

    def test_multi_step_tool_results(self):
        """工具调用结果在历史中 → multi_step加分。"""
        messages = [
            {"role": "user", "content": "search for X"},
            {"role": "assistant", "content": "calling tool"},
            {"role": "tool", "content": "result data", "tool_call_id": "1"},
            {"role": "tool", "content": "more data", "tool_call_id": "2"},
        ]
        score, breakdown = TaskComplexity.estimate(messages, [], "")
        assert breakdown["multi_step"] >= 6  # 2 tool results * 3

    def test_many_messages(self):
        """消息轮次多 → multi_step加分。"""
        messages = make_messages("msg", count=12)
        score, breakdown = TaskComplexity.estimate(messages, [], "")
        assert breakdown["multi_step"] >= 15

    def test_code_blocks(self):
        """代码块存在 → multi_step加分。"""
        text = "Fix this:\n```python\nprint('hello')\n```\nAnd this:\n```js\nconsole.log('hi')\n```"
        messages = make_messages(text)
        score, breakdown = TaskComplexity.estimate(messages, [], "")
        assert breakdown["multi_step"] >= 10  # 2 code blocks * 5

    def test_long_system_prompt(self):
        """长系统提示 → system_prompt高分。"""
        sys_prompt = "x" * 4000
        messages = make_messages("test")
        score, breakdown = TaskComplexity.estimate(messages, [], sys_prompt)
        assert breakdown["system_prompt"] == 20

    def test_short_system_prompt(self):
        """短系统提示。"""
        messages = make_messages("test")
        score, breakdown = TaskComplexity.estimate(messages, [], "be helpful")
        assert breakdown["system_prompt"] == 2

    def test_score_range(self):
        """分数在0-100范围内。"""
        # 极简
        score1, _ = TaskComplexity.estimate(make_messages("hi"), [], "")
        assert 0 <= score1 <= 100

        # 极复杂
        complex_text = " ".join(_COMPLEXITY_KEYWORDS) + " " + "x" * 6000
        many_tools = make_tools(20)
        messages = make_messages(complex_text, count=15)
        score2, _ = TaskComplexity.estimate(messages, many_tools, "x" * 4000)
        assert 0 <= score2 <= 100
        assert score2 > score1

    def test_multimodal_content(self):
        """多模态消息内容（content为列表）。"""
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "analyze this image for security vulnerabilities"},
                {"type": "image_url", "image_url": {"url": "data:..."}},
            ],
        }]
        score, breakdown = TaskComplexity.estimate(messages, [], "")
        assert breakdown["keywords"] > 0
        assert score > 0

    def test_empty_inputs(self):
        """空输入。"""
        score, breakdown = TaskComplexity.estimate([], [], "")
        assert score >= 0
        assert all(v >= 0 for v in breakdown.values())

    def test_none_system_prompt(self):
        """None系统提示。"""
        score, breakdown = TaskComplexity.estimate(
            make_messages("test"), [], None,
        )
        assert score >= 0


# ═══════════════════════════════════════════════════════════════
# ModelTier 测试
# ═══════════════════════════════════════════════════════════════

class TestModelTier:

    def test_from_score_simple(self):
        assert ModelTier.from_score(0) == ModelTier.SIMPLE
        assert ModelTier.from_score(35) == ModelTier.SIMPLE

    def test_from_score_standard(self):
        assert ModelTier.from_score(36) == ModelTier.STANDARD
        assert ModelTier.from_score(70) == ModelTier.STANDARD

    def test_from_score_complex(self):
        assert ModelTier.from_score(71) == ModelTier.COMPLEX
        assert ModelTier.from_score(100) == ModelTier.COMPLEX

    def test_boundary_values(self):
        """边界值测试。"""
        assert ModelTier.from_score(35) == ModelTier.SIMPLE
        assert ModelTier.from_score(36) == ModelTier.STANDARD
        assert ModelTier.from_score(70) == ModelTier.STANDARD
        assert ModelTier.from_score(71) == ModelTier.COMPLEX

    def test_enum_values(self):
        assert ModelTier.SIMPLE.value == "simple"
        assert ModelTier.STANDARD.value == "standard"
        assert ModelTier.COMPLEX.value == "complex"


# ═══════════════════════════════════════════════════════════════
# ModelClassifier 测试
# ═══════════════════════════════════════════════════════════════

class TestModelClassifier:

    def test_classify_simple_models(self):
        assert ModelClassifier.classify("gpt-4o-mini") == ModelTier.SIMPLE
        assert ModelClassifier.classify("google/gemini-flash-1.5") == ModelTier.SIMPLE
        assert ModelClassifier.classify("claude-3-haiku") == ModelTier.SIMPLE
        assert ModelClassifier.classify("llama-3-8b") == ModelTier.SIMPLE
        assert ModelClassifier.classify("qwen-7b") == ModelTier.SIMPLE

    def test_classify_complex_models(self):
        assert ModelClassifier.classify("openai/o1-preview") == ModelTier.COMPLEX
        assert ModelClassifier.classify("anthropic/claude-3-opus") == ModelTier.COMPLEX
        assert ModelClassifier.classify("gpt-4-turbo") == ModelTier.COMPLEX
        assert ModelClassifier.classify("o3-mini") == ModelTier.COMPLEX

    def test_classify_standard_models(self):
        assert ModelClassifier.classify("gpt-4o") == ModelTier.STANDARD
        assert ModelClassifier.classify("anthropic/claude-3.5-sonnet") == ModelTier.STANDARD
        assert ModelClassifier.classify("deepseek-chat") == ModelTier.STANDARD
        assert ModelClassifier.classify("deepseek-coder") == ModelTier.STANDARD

    def test_classify_unknown_model(self):
        """未知模型默认STANDARD。"""
        assert ModelClassifier.classify("some-random-model") == ModelTier.STANDARD
        assert ModelClassifier.classify("custom-llm-v2") == ModelTier.STANDARD

    def test_classify_batch(self):
        model_ids = [
            "gpt-4o-mini",
            "gpt-4o",
            "openai/o1-preview",
            "deepseek-chat",
            "google/gemini-flash",
        ]
        result = ModelClassifier.classify_batch(model_ids)
        assert "gpt-4o-mini" in result[ModelTier.SIMPLE]
        assert "google/gemini-flash" in result[ModelTier.SIMPLE]
        assert "gpt-4o" in result[ModelTier.STANDARD]
        assert "deepseek-chat" in result[ModelTier.STANDARD]
        assert "openai/o1-preview" in result[ModelTier.COMPLEX]

    def test_classify_empty(self):
        result = ModelClassifier.classify_batch([])
        assert result[ModelTier.SIMPLE] == []
        assert result[ModelTier.STANDARD] == []
        assert result[ModelTier.COMPLEX] == []

    def test_simple_takes_priority(self):
        """SIMPLE优先匹配——避免 'mini' 在 'pro-mini' 中被误判。"""
        # "flash" 应该优先匹配为 SIMPLE
        assert ModelClassifier.classify("google/gemini-flash-1.5-pro") == ModelTier.SIMPLE


# ═══════════════════════════════════════════════════════════════
# RoutingDecision 测试
# ═══════════════════════════════════════════════════════════════

class TestRoutingDecision:

    def test_repr_success(self):
        d = RoutingDecision(
            timestamp=1000.0,
            complexity_score=50,
            tier=ModelTier.STANDARD,
            selected_model="gpt-4o",
            success=True,
            latency_ms=123.4,
        )
        repr_str = repr(d)
        assert "✓" in repr_str
        assert "50" in repr_str
        assert "gpt-4o" in repr_str

    def test_repr_failure(self):
        d = RoutingDecision(
            timestamp=1000.0,
            complexity_score=80,
            tier=ModelTier.COMPLEX,
            selected_model="o1",
            success=False,
            error="timeout",
            latency_ms=5000.0,
        )
        repr_str = repr(d)
        assert "✗" in repr_str

    def test_repr_with_fallback(self):
        d = RoutingDecision(
            timestamp=1000.0,
            complexity_score=80,
            tier=ModelTier.COMPLEX,
            selected_model="gpt-4o",
            fallback_used=True,
            original_model="o1",
            success=True,
            latency_ms=2000.0,
        )
        repr_str = repr(d)
        assert "fallback" in repr_str


# ═══════════════════════════════════════════════════════════════
# AutoRouter 测试
# ═══════════════════════════════════════════════════════════════

class TestAutoRouter:

    def test_init_defaults(self):
        adapter = FakeAdapter()
        router = AutoRouter(adapter)
        assert router.adapter is adapter
        assert router.strategy == "round_robin"
        assert router.enable_fallback is True
        assert len(router.history) == 0
        assert router.last_decision is None

    def test_init_custom_model_tiers(self):
        adapter = FakeAdapter()
        custom_tiers = {
            ModelTier.SIMPLE: ["model-a"],
            ModelTier.STANDARD: ["model-b"],
            ModelTier.COMPLEX: ["model-c"],
        }
        router = AutoRouter(adapter, model_tiers=custom_tiers)
        assert router.model_tiers[ModelTier.SIMPLE] == ["model-a"]
        assert router.model_tiers[ModelTier.COMPLEX] == ["model-c"]

    @pytest.mark.asyncio
    async def test_chat_simple_task(self):
        """简单任务路由到SIMPLE模型。"""
        adapter = FakeAdapter()
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["cheap-model"],
                ModelTier.STANDARD: ["mid-model"],
                ModelTier.COMPLEX: ["expensive-model"],
            },
            strategy="first",
        )
        response = await router.chat(
            messages=make_messages("hi"),
            tools=[],
            system_prompt="",
        )
        assert response.content == "[cheap-model] 回复"
        assert router.last_decision.tier == ModelTier.SIMPLE
        assert router.last_decision.selected_model == "cheap-model"
        assert router.last_decision.success is True

    @pytest.mark.asyncio
    async def test_chat_complex_task(self):
        """复杂任务路由到COMPLEX模型。"""
        adapter = FakeAdapter()
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["cheap-model"],
                ModelTier.STANDARD: ["mid-model"],
                ModelTier.COMPLEX: ["expensive-model"],
            },
            strategy="first",
        )
        complex_text = " ".join(["analyze", "debug", "architecture", "security", "vulnerability"] * 3)
        complex_text += " " + "x" * 5000
        response = await router.chat(
            messages=make_messages(complex_text),
            tools=make_tools(15),
            system_prompt="x" * 4000,
        )
        assert "expensive-model" in response.content
        assert router.last_decision.tier == ModelTier.COMPLEX

    @pytest.mark.asyncio
    async def test_chat_standard_task(self):
        """中等任务路由到STANDARD模型。"""
        adapter = FakeAdapter()
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["cheap-model"],
                ModelTier.STANDARD: ["mid-model"],
                ModelTier.COMPLEX: ["expensive-model"],
            },
            strategy="first",
        )
        # 中等长度消息 + 中等工具数 + 分析关键词 + 中等系统提示
        text = "Please help me analyze and review this code. " + "Here is some context. " * 150
        sys_prompt = "You are a helpful coding assistant. " + "Follow best practices. " * 40
        response = await router.chat(
            messages=make_messages(text),
            tools=make_tools(5),
            system_prompt=sys_prompt,
        )
        assert "mid-model" in response.content
        assert router.last_decision.tier == ModelTier.STANDARD

    @pytest.mark.asyncio
    async def test_fallback_to_lower_tier(self):
        """COMPLEX模型失败 → 降级到STANDARD。"""
        adapter = FakeAdapter(fail_models={"expensive-model"})
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["cheap-model"],
                ModelTier.STANDARD: ["mid-model"],
                ModelTier.COMPLEX: ["expensive-model"],
            },
            strategy="first",
            enable_fallback=True,
        )
        # 构造复杂任务
        complex_text = " ".join(["analyze", "debug", "architecture", "security"] * 5)
        complex_text += " " + "x" * 5000
        response = await router.chat(
            messages=make_messages(complex_text),
            tools=make_tools(15),
            system_prompt="x" * 4000,
        )
        # 应该降级到 STANDARD
        assert "mid-model" in response.content
        assert router.last_decision.fallback_used is True
        assert router.last_decision.original_model == "expensive-model"

    @pytest.mark.asyncio
    async def test_fallback_same_tier(self):
        """同层级多个模型时，第一个失败→第二个成功。"""
        adapter = FakeAdapter(fail_models={"mid-model-1"})
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["cheap-model"],
                ModelTier.STANDARD: ["mid-model-1", "mid-model-2"],
                ModelTier.COMPLEX: ["expensive-model"],
            },
            strategy="first",
            enable_fallback=True,
        )
        text = "Please help me review and debug this code. " + "Additional context here. " * 150
        sys_prompt = "You are a coding assistant. " + "Follow guidelines. " * 40
        response = await router.chat(
            messages=make_messages(text),
            tools=make_tools(5),
            system_prompt=sys_prompt,
        )
        assert "mid-model-2" in response.content
        assert router.last_decision.fallback_used is True

    @pytest.mark.asyncio
    async def test_no_fallback_all_fail(self):
        """所有模型都失败 → 抛出异常。"""
        adapter = FakeAdapter(fail_models={"cheap-model", "mid-model", "expensive-model"})
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["cheap-model"],
                ModelTier.STANDARD: ["mid-model"],
                ModelTier.COMPLEX: ["expensive-model"],
            },
            strategy="first",
            enable_fallback=True,
        )
        with pytest.raises(RuntimeError, match="所有模型均失败"):
            await router.chat(
                messages=make_messages("hi"),
                tools=[],
                system_prompt="",
            )

    @pytest.mark.asyncio
    async def test_fallback_disabled(self):
        """禁用fallback → 首个模型失败直接抛异常。"""
        adapter = FakeAdapter(fail_models={"expensive-model"})
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["cheap-model"],
                ModelTier.STANDARD: ["mid-model"],
                ModelTier.COMPLEX: ["expensive-model"],
            },
            strategy="first",
            enable_fallback=False,
        )
        complex_text = " ".join(["analyze", "debug", "architecture", "security"] * 5)
        complex_text += " " + "x" * 5000
        with pytest.raises(RuntimeError):
            await router.chat(
                messages=make_messages(complex_text),
                tools=make_tools(15),
                system_prompt="x" * 4000,
            )

    @pytest.mark.asyncio
    async def test_round_robin_strategy(self):
        """轮询策略 — 同层级模型轮流使用。"""
        adapter = FakeAdapter()
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["m1", "m2", "m3"],
                ModelTier.STANDARD: ["s1"],
                ModelTier.COMPLEX: ["c1"],
            },
            strategy="round_robin",
        )
        # 连续3次简单任务
        for i in range(3):
            await router.chat(
                messages=make_messages("hi"),
                tools=[],
                system_prompt="",
            )
        # 应该轮询了 m1, m2, m3
        models_used = [d.selected_model for d in router.history]
        assert models_used == ["m1", "m2", "m3"]

    @pytest.mark.asyncio
    async def test_first_strategy(self):
        """first策略 — 总是用第一个。"""
        adapter = FakeAdapter()
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["m1", "m2", "m3"],
                ModelTier.STANDARD: ["s1"],
                ModelTier.COMPLEX: ["c1"],
            },
            strategy="first",
        )
        for i in range(3):
            await router.chat(
                messages=make_messages("hi"),
                tools=[],
                system_prompt="",
            )
        models_used = [d.selected_model for d in router.history]
        assert all(m == "m1" for m in models_used)

    @pytest.mark.asyncio
    async def test_history_recorded(self):
        """路由历史记录。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter, strategy="first")
        for i in range(5):
            await router.chat(
                messages=make_messages(f"msg {i}"),
                tools=[],
                system_prompt="",
            )
        assert len(router.history) == 5
        assert all(isinstance(d, RoutingDecision) for d in router.history)

    @pytest.mark.asyncio
    async def test_history_size_limit(self):
        """历史记录上限。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter, strategy="first", history_size=3)
        for i in range(5):
            await router.chat(
                messages=make_messages(f"msg {i}"),
                tools=[],
                system_prompt="",
            )
        assert len(router.history) == 3

    @pytest.mark.asyncio
    async def test_last_decision(self):
        """last_decision记录最近一次。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter, strategy="first")
        await router.chat(make_messages("hi"), [], "")
        assert router.last_decision is not None
        assert router.last_decision.success is True
        assert router.last_decision.complexity_score >= 0

    @pytest.mark.asyncio
    async def test_decision_score_breakdown(self):
        """决策记录包含评分明细。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter, strategy="first")
        await router.chat(make_messages("hi"), [], "")
        breakdown = router.last_decision.score_breakdown
        assert "prompt_length" in breakdown
        assert "tool_count" in breakdown
        assert "keywords" in breakdown
        assert "multi_step" in breakdown
        assert "system_prompt" in breakdown

    @pytest.mark.asyncio
    async def test_decision_task_summary(self):
        """决策记录包含任务摘要。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter, strategy="first")
        await router.chat(make_messages("Hello, world!"), [], "")
        assert router.last_decision.task_summary == "Hello, world!"

    @pytest.mark.asyncio
    async def test_decision_latency(self):
        """决策记录包含延迟。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter, strategy="first")
        await router.chat(make_messages("hi"), [], "")
        assert router.last_decision.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_get_stats_empty(self):
        """空历史统计。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter)
        stats = router.get_stats()
        assert stats["total_requests"] == 0
        assert stats["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_stats_with_history(self):
        """有历史记录的统计。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter, strategy="first")
        # 简单任务
        await router.chat(make_messages("hi"), [], "")
        await router.chat(make_messages("hello"), [], "")
        # 中等任务
        med_text = "Please analyze and review this. " + "Context. " * 200
        med_sys = "You are an assistant. " + "Instructions. " * 50
        await router.chat(make_messages(med_text), make_tools(5), med_sys)
        stats = router.get_stats()
        assert stats["total_requests"] == 3
        assert stats["success_rate"] == 1.0
        assert stats["fallback_rate"] == 0.0
        assert "simple" in stats["tier_distribution"]
        assert "standard" in stats["tier_distribution"]

    @pytest.mark.asyncio
    async def test_get_stats_with_failures(self):
        """含失败记录的统计。"""
        adapter = FakeAdapter(fail_models={"expensive-model"})
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["cheap"],
                ModelTier.STANDARD: ["mid"],
                ModelTier.COMPLEX: ["expensive-model"],
            },
            strategy="first",
        )
        # 复杂任务触发降级
        complex_text = " ".join(["analyze", "debug", "security"] * 5) + " " + "x" * 6000
        await router.chat(make_messages(complex_text), make_tools(15), "x" * 4000)
        stats = router.get_stats()
        assert stats["total_requests"] == 1
        assert stats["fallback_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_get_recent_decisions(self):
        """获取最近N条决策。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter, strategy="first")
        for i in range(5):
            await router.chat(make_messages(f"msg{i}"), [], "")
        recent = router.get_recent_decisions(3)
        assert len(recent) == 3
        # 应该是最新的3条
        assert recent[-1].task_summary == "msg4"

    @pytest.mark.asyncio
    async def test_get_recent_decisions_empty(self):
        """空历史获取最近决策。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter)
        assert router.get_recent_decisions(5) == []

    @pytest.mark.asyncio
    async def test_discover_models(self):
        """动态模型发现。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter)
        tiers = await router.discover_models()
        # FakeAdapter返回8个模型
        assert len(tiers[ModelTier.SIMPLE]) > 0  # gpt-4o-mini, gemini-flash
        assert len(tiers[ModelTier.STANDARD]) > 0  # gpt-4o, deepseek-chat等
        assert len(tiers[ModelTier.COMPLEX]) > 0  # o1-preview, claude-opus

    @pytest.mark.asyncio
    async def test_discover_models_failure(self):
        """模型发现失败时保持现有配置。"""
        adapter = FakeAdapter()
        adapter.list_models = AsyncMock(side_effect=RuntimeError("connection failed"))
        router = AutoRouter(adapter)
        original_tiers = dict(router.model_tiers)
        tiers = await router.discover_models()
        assert tiers == original_tiers  # 保持不变

    @pytest.mark.asyncio
    async def test_chat_stream(self):
        """流式对话路由。"""
        adapter = FakeAdapter()
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["stream-model"],
                ModelTier.STANDARD: ["s"],
                ModelTier.COMPLEX: ["c"],
            },
            strategy="first",
        )
        chunks = []
        async for chunk in router.chat_stream(make_messages("hi"), [], ""):
            chunks.append(chunk)
        assert chunks == ["Hello", " ", "World"]
        assert router.last_decision is not None
        assert router.last_decision.selected_model == "stream-model"

    @pytest.mark.asyncio
    async def test_chat_stream_failure(self):
        """流式对话失败记录。"""
        adapter = FakeAdapter(fail_models={"stream-model"})
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["stream-model"],
                ModelTier.STANDARD: ["s"],
                ModelTier.COMPLEX: ["c"],
            },
            strategy="first",
        )
        with pytest.raises(RuntimeError):
            async for _ in router.chat_stream(make_messages("hi"), [], ""):
                pass
        assert router.last_decision is not None
        assert router.last_decision.success is False

    @pytest.mark.asyncio
    async def test_health_check_proxy(self):
        """健康检查代理。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter)
        result = await router.health_check()
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_list_models_proxy(self):
        """模型列表代理。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter)
        models = await router.list_models()
        assert len(models) == 8

    @pytest.mark.asyncio
    async def test_available_models_property(self):
        """available_models属性。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter)
        models = router.available_models
        assert ModelTier.SIMPLE in models
        assert ModelTier.STANDARD in models
        assert ModelTier.COMPLEX in models

    @pytest.mark.asyncio
    async def test_close(self):
        """close方法。"""
        adapter = FakeAdapter()
        router = AutoRouter(adapter)
        await router.close()  # 不应抛出异常

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """异步上下文管理器。"""
        adapter = FakeAdapter()
        async with AutoRouter(adapter) as router:
            response = await router.chat(make_messages("hi"), [], "")
            assert response is not None

    @pytest.mark.asyncio
    async def test_adapter_model_set(self):
        """确认adapter的model属性被正确设置。"""
        adapter = FakeAdapter()
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["target-model"],
                ModelTier.STANDARD: ["s"],
                ModelTier.COMPLEX: ["c"],
            },
            strategy="first",
        )
        await router.chat(make_messages("hi"), [], "")
        assert adapter.model == "target-model"

    @pytest.mark.asyncio
    async def test_empty_tier_fallback_to_standard(self):
        """层级为空时回退到STANDARD。"""
        adapter = FakeAdapter()
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: [],
                ModelTier.STANDARD: ["standard-model"],
                ModelTier.COMPLEX: [],
            },
            strategy="first",
        )
        # 简单任务但SIMPLE层为空 → 用STANDARD
        response = await router.chat(make_messages("hi"), [], "")
        assert "standard-model" in response.content

    @pytest.mark.asyncio
    async def test_all_tiers_empty_raises(self):
        """所有层级都为空 → 抛出异常。"""
        adapter = FakeAdapter()
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: [],
                ModelTier.STANDARD: [],
                ModelTier.COMPLEX: [],
            },
            strategy="first",
        )
        with pytest.raises(ValueError, match="没有可用模型"):
            await router.chat(make_messages("hi"), [], "")

    @pytest.mark.asyncio
    async def test_multiple_requests_different_tiers(self):
        """多次请求路由到不同层级。"""
        adapter = FakeAdapter()
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["simple-m"],
                ModelTier.STANDARD: ["standard-m"],
                ModelTier.COMPLEX: ["complex-m"],
            },
            strategy="first",
        )
        # 简单
        await router.chat(make_messages("hi"), [], "")
        # 中等
        med_text = "Please analyze and review this code. " + "Context here. " * 200
        med_sys = "You are an assistant. " + "Instructions. " * 50
        await router.chat(make_messages(med_text), make_tools(5), med_sys)
        # 复杂
        complex_text = " ".join(["analyze", "debug", "security", "architecture"] * 5) + " " + "x" * 6000
        await router.chat(make_messages(complex_text), make_tools(15), "x" * 4000)

        tiers_used = [d.tier for d in router.history]
        assert ModelTier.SIMPLE in tiers_used
        assert ModelTier.STANDARD in tiers_used
        assert ModelTier.COMPLEX in tiers_used

    @pytest.mark.asyncio
    async def test_random_strategy(self):
        """随机策略 — 至少能选出模型。"""
        adapter = FakeAdapter()
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["r1", "r2", "r3"],
                ModelTier.STANDARD: ["s1"],
                ModelTier.COMPLEX: ["c1"],
            },
            strategy="random",
        )
        response = await router.chat(make_messages("hi"), [], "")
        assert response is not None
        assert router.last_decision.selected_model in ["r1", "r2", "r3"]

    @pytest.mark.asyncio
    async def test_tool_result_in_history_increases_complexity(self):
        """工具调用结果在消息历史中 → 更高复杂度评分。"""
        adapter = FakeAdapter()
        router = AutoRouter(
            adapter,
            model_tiers={
                ModelTier.SIMPLE: ["simple"],
                ModelTier.STANDARD: ["standard"],
                ModelTier.COMPLEX: ["complex"],
            },
            strategy="first",
        )
        # 无工具结果
        await router.chat(make_messages("hello"), [], "")
        score_no_tools = router.last_decision.complexity_score

        # 有工具结果
        messages_with_tools = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "let me check"},
            {"role": "tool", "content": "result", "tool_call_id": "1"},
            {"role": "tool", "content": "more", "tool_call_id": "2"},
        ]
        await router.chat(messages_with_tools, [], "")
        score_with_tools = router.last_decision.complexity_score

        assert score_with_tools > score_no_tools
