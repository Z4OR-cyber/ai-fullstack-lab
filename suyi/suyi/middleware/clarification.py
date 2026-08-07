"""澄清中间件 — 检测低置信度信号并在需要时请求用户澄清.

检测策略:
    1. 分析 LLM response 的 content，检测不确定词（"我不确定"、"可能"、"也许"等）
    2. response 没有调用工具也没有给出明确答案
    3. 连续 2 轮没有实质进展（无工具调用、无明确答案）

触发时:
    - 在 state.metadata 中设置 ``needs_clarification=True``
    - 生成 ``clarification_question`` 供外层逻辑使用
    - 不直接中断循环，由外层逻辑决定是否暂停

排序优先级: 40（最后执行，所有中间件处理完再决定是否澄清）
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..core.loop import LLMResponse, LoopState
from .base import MiddlewareBase

__all__ = ["ClarificationMiddleware"]

# 不确定词列表（中英文）
_UNCERTAINTY_PATTERNS: list[str] = [
    # 中文不确定表达
    r"我不确定", r"不太确定", r"不确定", r"不太清楚",
    r"可能", r"也许", r"大概", r"或许", r"似乎",
    r"应该", r"也许吧", r"可能吧",
    r"我不知道", r"不清楚", r"不了解",
    r"无法确定", r"难以判断", r"不太好说",
    # 英文不确定表达
    r"[Ii]('?m)?\s+not\s+sure", r"[Ii]\s+think", r"[Mm]aybe",
    r"[Pp]erhaps", r"[Pp]ossibly", r"[Ll]ikely",
    r"[Ii]\s+don'?t\s+know", r"[Uu]ncertain", r"[Aa]pproximately",
    r"[Ii]\s+cannot\s+determine", r"[Nn]ot\s+certain",
]

# 编译正则模式
_UNCERTAINTY_REGEX: re.Pattern[str] = re.compile(
    "|".join(_UNCERTAINTY_PATTERNS)
)

# 明确答案的最小内容长度（短于这个长度且无工具调用视为无实质进展）
_MIN_SUBSTANTIVE_LENGTH: int = 10


class ClarificationMiddleware(MiddlewareBase):
    """澄清中间件.

    参数:
        confidence_threshold: 置信度低于此值时触发澄清（0.0–1.0）
                               值越高越容易触发澄清
    """

    def __init__(
        self,
        confidence_threshold: float = 0.5,
    ) -> None:
        self.confidence_threshold: float = confidence_threshold

        # 跨轮次跟踪无实质进展的轮数
        self._no_progress_count: int = 0

    @property
    def priority(self) -> int:
        """澄清中间件优先级最低（40）."""
        return 40

    async def after_llm_call(
        self, response: LLMResponse, state: LoopState
    ) -> LLMResponse:
        """在 LLM 调用后分析响应，检测低置信度信号.

        流程:
            1. 检测不确定词
            2. 检测无工具调用且无明确答案
            3. 检测连续无实质进展
            4. 若触发，设置 metadata 标记和澄清问题
        """
        content: str = response.content or ""

        # 计算置信度（0.0–1.0）
        confidence: float = self._assess_confidence(response)

        # 判断是否需要澄清
        needs_clarification: bool = False
        clarification_question: str = ""

        # 信号1：置信度低于阈值
        if confidence < self.confidence_threshold:
            needs_clarification = True
            clarification_question = self._generate_clarification_question(
                content, reason="low_confidence"
            )

        # 信号2：无工具调用且内容过短（无明确答案）
        has_tool_calls: bool = bool(response.tool_calls)
        is_substantive: bool = len(content.strip()) >= _MIN_SUBSTANTIVE_LENGTH

        if not has_tool_calls and not is_substantive:
            self._no_progress_count += 1
            if self._no_progress_count >= 2:
                needs_clarification = True
                clarification_question = self._generate_clarification_question(
                    content, reason="no_progress"
                )
        else:
            # 有实质进展，重置计数
            self._no_progress_count = 0

        # 信号3：包含不确定词且无工具调用
        if not has_tool_calls and self._has_uncertainty(content):
            needs_clarification = True
            clarification_question = self._generate_clarification_question(
                content, reason="uncertainty_expressed"
            )

        # 设置 metadata（不中断循环，由外层逻辑决定）
        if needs_clarification:
            state.metadata["needs_clarification"] = True
            state.metadata["clarification_question"] = clarification_question
            state.metadata["confidence_score"] = round(confidence, 4)

        return response

    # ── 内部方法 ────────────────────────────────────────────────

    def _assess_confidence(self, response: LLMResponse) -> float:
        """评估 LLM 响应的置信度.

        评分规则:
            - 基础分 1.0（高置信度）
            - 包含不确定词 → 扣分（每个不确定词扣 0.15，最低 0.1）
            - 无工具调用且内容短 → 扣 0.2
            - 有工具调用 → 加 0.1（说明在积极行动，上限 1.0）

        参数:
            response: LLM 响应

        返回:
            置信度分数（0.0–1.0）
        """
        content: str = response.content or ""
        confidence: float = 1.0

        # 不确定词扣分
        matches: list[str] = _UNCERTAINTY_REGEX.findall(content)
        if matches:
            confidence -= min(len(matches) * 0.15, 0.6)

        # 无工具调用且内容短
        if not response.tool_calls and len(content.strip()) < _MIN_SUBSTANTIVE_LENGTH:
            confidence -= 0.2

        # 有工具调用说明在积极行动
        if response.tool_calls:
            confidence = min(confidence + 0.1, 1.0)

        return max(confidence, 0.0)

    def _has_uncertainty(self, content: str) -> bool:
        """检测文本中是否包含不确定词.

        参数:
            content: 待检测的文本

        返回:
            是否包含不确定词
        """
        return bool(_UNCERTAINTY_REGEX.search(content))

    def _generate_clarification_question(
        self,
        content: str,
        reason: str,
    ) -> str:
        """根据检测到的低置信度信号生成澄清问题.

        参数:
            content: LLM 响应内容
            reason:  触发原因（low_confidence / no_progress / uncertainty_expressed）

        返回:
            澄清问题字符串
        """
        if reason == "no_progress":
            return (
                "Agent 连续多轮没有实质进展。"
                "请问您的具体需求是什么？可以提供更多细节吗？"
            )
        elif reason == "uncertainty_expressed":
            return (
                "Agent 表达了不确定性。"
                "请问您能提供更明确的方向或补充信息吗？"
            )
        else:  # low_confidence
            return (
                "Agent 对当前任务的把握不足。"
                "请问您希望 Agent 重点关注哪个方面？"
            )
