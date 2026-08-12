"""
Suyi Auto Router — 智能LLM路由器.

根据任务复杂度自动选择最优模型，通过OmniRoute Gateway路由到不同LLM：
    - 简单任务 → 快速/低成本模型（如 gemini-flash, gpt-4o-mini）
    - 标准任务 → 平衡型模型（如 gpt-4o, deepseek-chat）
    - 复杂任务 → 高质量模型（如 o1, claude-opus）

设计要点：
    - 实现 LLMInterface 协议，可无缝替换任何现有 LLM 适配器
    - 五维复杂度分析：prompt长度 / 工具数 / 关键词 / 多步指示 / 系统提示
    - 支持运行时动态发现 OmniRoute 可用模型并自动分类
    - 路由决策日志，可观测可追溯
    - 高层模型失败自动降级到低层
    - 纯 Python + httpx，无新依赖

Usage::

    from suyi.llm import AutoRouter, OmniRouteAdapter

    # 基本用法
    adapter = OmniRouteAdapter(api_key="sk-...")
    router = AutoRouter(adapter)

    # 自定义模型分层
    router = AutoRouter(
        adapter,
        model_tiers={
            "simple": ["gemini-flash", "gpt-4o-mini"],
            "standard": ["gpt-4o", "deepseek-chat"],
            "complex": ["o1-preview", "claude-opus-4"],
        },
    )

    # 自动发现模型（需OmniRoute运行中）
    await router.discover_models()

    # 作为 LLMInterface 使用
    response = await router.chat(messages, tools, system_prompt)
    print(router.last_decision)  # 查看路由决策
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from ..core.loop import LLMResponse, ToolCall

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 模型层级
# ═══════════════════════════════════════════════════════════════

class ModelTier(str, Enum):
    """模型层级枚举。"""
    SIMPLE = "simple"      # 快速低成本
    STANDARD = "standard"  # 平衡型
    COMPLEX = "complex"    # 高质量

    @classmethod
    def from_score(cls, score: int) -> "ModelTier":
        """根据复杂度分数（0-100）返回层级。"""
        if score <= 35:
            return cls.SIMPLE
        elif score <= 70:
            return cls.STANDARD
        else:
            return cls.COMPLEX


# ═══════════════════════════════════════════════════════════════
# 路由决策记录
# ═══════════════════════════════════════════════════════════════

@dataclass
class RoutingDecision:
    """单次路由决策记录。"""
    timestamp: float
    complexity_score: int                # 0-100
    tier: ModelTier
    selected_model: str
    fallback_used: bool = False          # 是否触发了降级
    original_model: Optional[str] = None  # 降级前的模型
    success: bool = True
    error: Optional[str] = None
    latency_ms: float = 0.0
    # 评分明细
    score_breakdown: dict[str, int] = field(default_factory=dict)
    # 任务摘要（前100字符）
    task_summary: str = ""

    def __repr__(self) -> str:
        status = "✓" if self.success else "✗"
        fb = f" (fallback→{self.selected_model})" if self.fallback_used else ""
        return (
            f"RoutingDecision[{status}] "
            f"score={self.complexity_score} tier={self.tier.value} "
            f"model={self.selected_model}{fb} "
            f"latency={self.latency_ms:.0f}ms"
        )


# ═══════════════════════════════════════════════════════════════
# 任务复杂度分析器
# ═══════════════════════════════════════════════════════════════

# 复杂度关键词 — 命中越多，任务越复杂
_COMPLEXITY_KEYWORDS: list[str] = [
    # 分析类
    "analyze", "analysis", "compare", "evaluate", "assess", "investigate",
    "审计", "分析", "评估", "对比", "调研", "审查",
    # 工程类
    "refactor", "architecture", "design", "optimize", "debug", "review",
    "重构", "架构", "设计", "优化", "调试", "审查",
    # 深度类
    "comprehensive", "thorough", "detailed", "deep", "complex", "advanced",
    "全面", "深入", "详细", "复杂", "高级",
    # 安全类
    "security", "vulnerability", "exploit", "penetration", "audit",
    "安全", "漏洞", "渗透", "攻击",
    # 推理类
    "reason", "deduce", "infer", "conclude", "derive",
    "推理", "推导", "结论",
]

# 简单任务关键词 — 命中越多，任务越简单
_SIMPLICITY_KEYWORDS: list[str] = [
    "hello", "hi", "thanks", "ok", "summarize", "translate", "format",
    "list", "name", "what is",
    "你好", "谢谢", "总结", "翻译", "格式化", "列出", "是什么",
]


class TaskComplexity:
    """
    任务复杂度分析器。

    五维评分：
        1. Prompt 长度 — 总字符数（消息+系统提示）
        2. 工具数量 — 可用工具越多，推理越复杂
        3. 关键词匹配 — 复杂/简单关键词加权
        4. 多步指示 — 对话历史中的工具调用结果、轮次
        5. 系统提示复杂度 — 长系统提示意味着更复杂的角色设定

    返回 0-100 的综合分数和各维度明细。
    """

    @staticmethod
    def estimate(
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> tuple[int, dict[str, int]]:
        """
        估算任务复杂度。

        Args:
            messages:      对话消息列表
            tools:         工具定义列表
            system_prompt: 系统提示词

        Returns:
            (score 0-100, breakdown dict)
        """
        breakdown: dict[str, int] = {}

        # ── 1. Prompt 长度 ──────────────────────────────
        total_chars = len(system_prompt or "")
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                # 多模态消息（content是列表）
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        total_chars += len(part["text"])

        if total_chars < 500:
            breakdown["prompt_length"] = 5
        elif total_chars < 2000:
            breakdown["prompt_length"] = 15
        elif total_chars < 5000:
            breakdown["prompt_length"] = 30
        elif total_chars < 10000:
            breakdown["prompt_length"] = 40
        else:
            breakdown["prompt_length"] = 45

        # ── 2. 工具数量 ─────────────────────────────────
        tool_count = len(tools)
        if tool_count == 0:
            breakdown["tool_count"] = 5
        elif tool_count <= 3:
            breakdown["tool_count"] = 15
        elif tool_count <= 8:
            breakdown["tool_count"] = 25
        else:
            breakdown["tool_count"] = 35

        # ── 3. 关键词匹配 ───────────────────────────────
        # 合并所有文本用于关键词匹配
        all_text = (system_prompt or "").lower()
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                all_text += " " + content.lower()
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        all_text += " " + part["text"].lower()

        complex_hits = sum(1 for kw in _COMPLEXITY_KEYWORDS if kw in all_text)
        simple_hits = sum(1 for kw in _SIMPLICITY_KEYWORDS if kw in all_text)

        keyword_score = min(complex_hits * 5, 25) - min(simple_hits * 3, 15)
        breakdown["keywords"] = max(keyword_score, 0)

        # ── 4. 多步指示 ─────────────────────────────────
        multi_step_score = 0

        # 工具调用结果在历史中 → 多步推理
        tool_results = sum(1 for m in messages if m.get("role") == "tool")
        if tool_results > 0:
            multi_step_score += min(tool_results * 3, 15)

        # 对话轮次多 → 上下文复杂
        msg_count = len(messages)
        if msg_count > 10:
            multi_step_score += 15
        elif msg_count > 5:
            multi_step_score += 10
        elif msg_count > 2:
            multi_step_score += 5

        # 代码块存在 → 技术性任务
        code_block_pattern = re.compile(r"```[\s\S]*?```")
        code_blocks = len(code_block_pattern.findall(all_text))
        if code_blocks > 0:
            multi_step_score += min(code_blocks * 5, 15)

        breakdown["multi_step"] = min(multi_step_score, 30)

        # ── 5. 系统提示复杂度 ───────────────────────────
        sys_len = len(system_prompt or "")
        if sys_len > 3000:
            breakdown["system_prompt"] = 20
        elif sys_len > 1000:
            breakdown["system_prompt"] = 12
        elif sys_len > 300:
            breakdown["system_prompt"] = 6
        else:
            breakdown["system_prompt"] = 2

        # ── 汇总 ────────────────────────────────────────
        raw_total = sum(breakdown.values())
        # 归一化到 0-100（理论最大约 155）
        score = min(int(raw_total / 155 * 100), 100)

        return score, breakdown


# ═══════════════════════════════════════════════════════════════
# 模型自动分类器
# ═══════════════════════════════════════════════════════════════

# 模型名称关键词 → 层级映射（用于自动分类OmniRoute返回的模型）
_MODEL_TIER_KEYWORDS: dict[ModelTier, list[str]] = {
    ModelTier.SIMPLE: [
        "flash", "mini", "nano", "haiku", "small", "lite", "tiny",
        "fast", "turbo-instruct", "8b", "7b", "1b", "3b",
        "best-free",  # OmniRoute auto/best-free 变体
    ],
    ModelTier.COMPLEX: [
        "o1", "o3", "opus", "ultra", "max", "thinking", "reasoning",
        "pro-1.5", "pro-preview", "405b", "70b", "frontier",
        "claude-3-opus", "gpt-4-turbo", "gpt-4.5",
        "auto/coding",  # OmniRoute auto/coding 变体（质量优先编码）
    ],
    ModelTier.STANDARD: [
        "4o", "sonnet", "chat", "pro", "plus", "medium", "balanced",
        "deepseek", "qwen", "llama", "mistral", "gemma",
    ],
}


class ModelClassifier:
    """根据模型名称自动分类到对应层级。"""

    @staticmethod
    def classify(model_id: str) -> ModelTier:
        """
        根据模型ID/名称推断层级。

        策略（优先级从高到低）：
        1. 先检查 COMPLEX 关键词（推理/旗舰模型优先匹配，
           即使名称含 "mini" 也应为 COMPLEX，如 o3-mini）
        2. 再检查 SIMPLE 关键词（低成本模型）
        3. 最后检查 STANDARD 关键词
        4. 都不匹配 → 默认 STANDARD
        """
        model_lower = model_id.lower()

        # 先检查 COMPLEX（推理/旗舰模型优先匹配）
        for kw in _MODEL_TIER_KEYWORDS[ModelTier.COMPLEX]:
            if kw in model_lower:
                return ModelTier.COMPLEX

        # 检查 SIMPLE
        for kw in _MODEL_TIER_KEYWORDS[ModelTier.SIMPLE]:
            if kw in model_lower:
                return ModelTier.SIMPLE

        # 检查 STANDARD
        for kw in _MODEL_TIER_KEYWORDS[ModelTier.STANDARD]:
            if kw in model_lower:
                return ModelTier.STANDARD

        # 默认 STANDARD
        return ModelTier.STANDARD

    @staticmethod
    def classify_batch(model_ids: list[str]) -> dict[ModelTier, list[str]]:
        """批量分类模型，返回 {tier: [model_ids]}。"""
        result: dict[ModelTier, list[str]] = {
            ModelTier.SIMPLE: [],
            ModelTier.STANDARD: [],
            ModelTier.COMPLEX: [],
        }
        for mid in model_ids:
            tier = ModelClassifier.classify(mid)
            result[tier].append(mid)
        return result


# ═══════════════════════════════════════════════════════════════
# AutoRouter — 智能路由器
# ═══════════════════════════════════════════════════════════════

# 默认模型分层（当无法从OmniRoute动态发现时使用）
# 使用 OmniRoute auto 变体，由 Gateway 自动路由到最佳 Provider
_DEFAULT_MODEL_TIERS: dict[ModelTier, list[str]] = {
    ModelTier.SIMPLE: [
        "auto/best-free",       # 零成本路由（优先使用免费 Provider）
    ],
    ModelTier.STANDARD: [
        "auto",                 # 默认 LKGP 路由（平衡质量与成本）
    ],
    ModelTier.COMPLEX: [
        "auto/coding",          # 质量优先编码任务路由
    ],
}


class AutoRouter:
    """
    智能LLM路由器。

    实现 LLMInterface 协议，根据任务复杂度自动选择最优模型。
    包装 OmniRouteAdapter（或任何 OpenAIAdapter 子类），
    在每次 chat 调用前分析任务复杂度，选择对应层级的模型。

    Attributes:
        adapter:          被包装的 LLM 适配器（通常是 OmniRouteAdapter）
        model_tiers:      各层级对应的模型列表
        strategy:         选模型策略 ("first"=取第一个可用, "random"=随机, "round_robin"=轮询)
        enable_fallback:  是否启用降级（高层失败→低层重试）
        history:          路由历史记录（最近N条）
    """

    def __init__(
        self,
        adapter: Any,
        model_tiers: Optional[dict[ModelTier, list[str]]] = None,
        strategy: str = "round_robin",
        enable_fallback: bool = True,
        history_size: int = 100,
        enable_logging: bool = True,
    ):
        """
        Args:
            adapter:         LLM适配器实例（需实现chat方法，通常是OmniRouteAdapter）
            model_tiers:     自定义模型分层。None则使用默认值或动态发现结果
            strategy:        模型选择策略
                             "first"      - 总是用该层级的第一个模型
                             "random"     - 随机选择
                             "round_robin" - 轮询（默认）
            enable_fallback: 高层模型失败时自动降级到低层重试
            history_size:    路由历史记录保留条数
            enable_logging:  是否记录路由日志
        """
        self.adapter = adapter
        self.model_tiers = model_tiers or dict(_DEFAULT_MODEL_TIERS)
        self.strategy = strategy
        self.enable_fallback = enable_fallback
        self.enable_logging = enable_logging

        # 轮询计数器（每个层级独立）
        self._rr_counters: dict[ModelTier, int] = {
            ModelTier.SIMPLE: 0,
            ModelTier.STANDARD: 0,
            ModelTier.COMPLEX: 0,
        }

        # 路由历史
        self.history: deque[RoutingDecision] = deque(maxlen=history_size)

        # 最近一次决策
        self.last_decision: Optional[RoutingDecision] = None

    # ── 模型选择 ────────────────────────────────────────────────

    def _select_model(self, tier: ModelTier) -> str:
        """
        根据层级和策略选择具体模型。

        Args:
            tier: 目标层级

        Returns:
            选中的模型ID

        Raises:
            ValueError: 该层级没有可用模型
        """
        models = self.model_tiers.get(tier, [])
        if not models:
            # 降级到 STANDARD
            models = self.model_tiers.get(ModelTier.STANDARD, [])
            if not models:
                # 最终降级到任意可用模型
                for t in self.model_tiers.values():
                    if t:
                        models = t
                        break
        if not models:
            raise ValueError("没有可用模型")

        if self.strategy == "first":
            return models[0]
        elif self.strategy == "random":
            import random
            return random.choice(models)
        else:  # round_robin
            idx = self._rr_counters[tier] % len(models)
            self._rr_counters[tier] += 1
            return models[idx]

    def _get_fallback_tier(self, tier: ModelTier) -> Optional[ModelTier]:
        """获取降级目标层级。"""
        if tier == ModelTier.COMPLEX:
            return ModelTier.STANDARD
        elif tier == ModelTier.STANDARD:
            return ModelTier.SIMPLE
        else:
            return None

    # ── 模型发现 ────────────────────────────────────────────────

    async def discover_models(self) -> dict[ModelTier, list[str]]:
        """
        从OmniRoute动态发现可用模型并自动分类。

        调用 adapter.list_models()（OmniRouteAdapter特有方法）获取
        可用模型列表，然后按名称自动分类到三个层级。

        如果发现失败，保持现有模型分层不变。

        Returns:
            更新后的 model_tiers 字典
        """
        try:
            # OmniRouteAdapter 有 list_models 方法
            if hasattr(self.adapter, "list_models"):
                raw_models = await self.adapter.list_models()
                model_ids = [
                    m.get("id", "") if isinstance(m, dict) else str(m)
                    for m in raw_models
                ]
                model_ids = [m for m in model_ids if m]

                if model_ids:
                    classified = ModelClassifier.classify_batch(model_ids)
                    # 只更新有模型的层级，保留默认值作为fallback
                    for tier in ModelTier:
                        if classified[tier]:
                            self.model_tiers[tier] = classified[tier]

                    if self.enable_logging:
                        for tier in ModelTier:
                            count = len(self.model_tiers.get(tier, []))
                            logger.info(
                                "AutoRouter 模型发现: %s = %d 个模型",
                                tier.value, count,
                            )
                    return self.model_tiers
        except Exception as e:
            logger.warning("AutoRouter 模型发现失败: %s", e)

        return self.model_tiers

    # ── LLMInterface 实现 ──────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> LLMResponse:
        """
        智能路由对话请求。

        1. 分析任务复杂度
        2. 选择对应层级模型
        3. 设置adapter的model属性
        4. 调用adapter.chat
        5. 如果失败且enable_fallback，降级重试
        6. 记录路由决策
        """
        # 1. 分析复杂度
        score, breakdown = TaskComplexity.estimate(messages, tools, system_prompt)
        tier = ModelTier.from_score(score)

        # 2. 生成任务摘要
        task_summary = self._extract_summary(messages, system_prompt)

        # 3. 选择模型
        selected_model = self._select_model(tier)
        original_model = selected_model

        # 4. 调用（含降级）
        start_time = time.monotonic()
        fallback_used = False
        error_msg: Optional[str] = None
        response: Optional[LLMResponse] = None

        current_tier = tier
        while True:
            try:
                # 设置adapter的模型
                if hasattr(self.adapter, "model"):
                    self.adapter.model = selected_model

                response = await self.adapter.chat(messages, tools, system_prompt)
                break

            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    "AutoRouter 模型 %s 失败: %s", selected_model, e,
                )

                if not self.enable_fallback:
                    break

                # 尝试同层级的下一个模型
                same_tier_models = self.model_tiers.get(current_tier, [])
                if len(same_tier_models) > 1:
                    # 尝试同层级其他模型
                    for alt_model in same_tier_models:
                        if alt_model != selected_model:
                            try:
                                if hasattr(self.adapter, "model"):
                                    self.adapter.model = alt_model
                                response = await self.adapter.chat(
                                    messages, tools, system_prompt,
                                )
                                selected_model = alt_model
                                fallback_used = True
                                error_msg = None
                                break
                            except Exception as e2:
                                logger.warning(
                                    "AutoRouter 同层模型 %s 也失败: %s",
                                    alt_model, e2,
                                )
                                continue
                    if response is not None:
                        break

                # 降级到更低层级
                next_tier = self._get_fallback_tier(current_tier)
                if next_tier is None:
                    break  # 已经是最低层级

                try:
                    fallback_model = self._select_model(next_tier)
                    if hasattr(self.adapter, "model"):
                        self.adapter.model = fallback_model
                    response = await self.adapter.chat(
                        messages, tools, system_prompt,
                    )
                    selected_model = fallback_model
                    fallback_used = True
                    error_msg = None
                    break
                except Exception as e3:
                    logger.warning(
                        "AutoRouter 降级到 %s 也失败: %s",
                        next_tier.value, e3,
                    )
                    current_tier = next_tier
                    error_msg = str(e3)
                    continue

        latency_ms = (time.monotonic() - start_time) * 1000

        # 5. 记录决策
        decision = RoutingDecision(
            timestamp=time.time(),
            complexity_score=score,
            tier=tier,
            selected_model=selected_model,
            fallback_used=fallback_used,
            original_model=original_model if fallback_used else None,
            success=response is not None,
            error=error_msg,
            latency_ms=latency_ms,
            score_breakdown=breakdown,
            task_summary=task_summary,
        )
        self.last_decision = decision
        self.history.append(decision)

        if self.enable_logging:
            logger.info("AutoRouter 路由: %s", decision)

        # 6. 返回结果或抛出异常
        if response is not None:
            return response
        else:
            raise RuntimeError(
                f"AutoRouter 所有模型均失败，最后错误: {error_msg}"
            )

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ):
        """
        流式对话——同样经过智能路由。

        注意：流式模式不支持自动降级（流开始后无法回退）。
        如果选定模型失败，直接抛出异常。
        """
        score, breakdown = TaskComplexity.estimate(messages, tools, system_prompt)
        tier = ModelTier.from_score(score)
        selected_model = self._select_model(tier)

        if hasattr(self.adapter, "model"):
            self.adapter.model = selected_model

        task_summary = self._extract_summary(messages, system_prompt)
        start_time = time.monotonic()

        try:
            # 委托给adapter的chat_stream
            if hasattr(self.adapter, "chat_stream"):
                async for chunk in self.adapter.chat_stream(
                    messages, tools, system_prompt,
                ):
                    yield chunk
            else:
                raise RuntimeError("adapter 不支持 chat_stream")

            latency_ms = (time.monotonic() - start_time) * 1000
            decision = RoutingDecision(
                timestamp=time.time(),
                complexity_score=score,
                tier=tier,
                selected_model=selected_model,
                success=True,
                latency_ms=latency_ms,
                score_breakdown=breakdown,
                task_summary=task_summary,
            )
            self.last_decision = decision
            self.history.append(decision)

        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            decision = RoutingDecision(
                timestamp=time.time(),
                complexity_score=score,
                tier=tier,
                selected_model=selected_model,
                success=False,
                error=str(e),
                latency_ms=latency_ms,
                score_breakdown=breakdown,
                task_summary=task_summary,
            )
            self.last_decision = decision
            self.history.append(decision)
            raise

    # ── 辅助方法 ────────────────────────────────────────────────

    @staticmethod
    def _extract_summary(messages: list[dict], system_prompt: str) -> str:
        """提取任务摘要（前100字符）。"""
        # 优先取第一条用户消息
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content[:100]
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and "text" in part:
                            return part["text"][:100]
        # 回退到系统提示
        if system_prompt:
            return system_prompt[:100]
        return ""

    # ── 路由统计 ────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """
        获取路由统计信息。

        Returns:
            {
                "total_requests": 总请求数,
                "success_rate": 成功率,
                "fallback_rate": 降级率,
                "tier_distribution": {tier: count},
                "avg_latency_ms": 平均延迟,
                "model_usage": {model: count},
            }
        """
        total = len(self.history)
        if total == 0:
            return {
                "total_requests": 0,
                "success_rate": 0.0,
                "fallback_rate": 0.0,
                "tier_distribution": {},
                "avg_latency_ms": 0.0,
                "model_usage": {},
            }

        success_count = sum(1 for d in self.history if d.success)
        fallback_count = sum(1 for d in self.history if d.fallback_used)

        tier_dist: dict[str, int] = {}
        model_usage: dict[str, int] = {}
        total_latency = 0.0

        for d in self.history:
            tier_key = d.tier.value
            tier_dist[tier_key] = tier_dist.get(tier_key, 0) + 1
            model_usage[d.selected_model] = model_usage.get(d.selected_model, 0) + 1
            total_latency += d.latency_ms

        return {
            "total_requests": total,
            "success_rate": round(success_count / total, 4),
            "fallback_rate": round(fallback_count / total, 4),
            "tier_distribution": tier_dist,
            "avg_latency_ms": round(total_latency / total, 1),
            "model_usage": model_usage,
        }

    def get_recent_decisions(self, n: int = 10) -> list[RoutingDecision]:
        """获取最近N条路由决策。"""
        return list(self.history)[-n:] if self.history else []

    # ── 生命周期 ────────────────────────────────────────────────

    async def close(self) -> None:
        """关闭底层adapter。"""
        if hasattr(self.adapter, "close"):
            await self.adapter.close()

    async def __aenter__(self) -> "AutoRouter":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    # ── 代理adapter的特有方法 ──────────────────────────────────

    async def health_check(self) -> dict:
        """代理adapter的健康检查。"""
        if hasattr(self.adapter, "health_check"):
            return await self.adapter.health_check()
        return {"status": "unknown"}

    async def list_models(self) -> list[dict]:
        """代理adapter的模型列表。"""
        if hasattr(self.adapter, "list_models"):
            return await self.adapter.list_models()
        return []

    @property
    def available_models(self) -> dict[ModelTier, list[str]]:
        """当前各层级可用模型。"""
        return dict(self.model_tiers)
