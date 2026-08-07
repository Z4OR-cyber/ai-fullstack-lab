"""对话压缩中间件 — 在 token 预算使用率超过阈值时自动压缩历史消息.

压缩策略:
    1. 保留最近 N 条消息不压缩（确保当前上下文完整）
    2. 将较早的消息用 LLM 生成摘要（如果有 LLM 引用）
    3. 无 LLM 时使用简单截断策略（保留每条消息前 100 字符 + 角色标记）
    4. 用摘要替换原始消息，并在 metadata 中记录压缩事件

排序优先级: 10（最先执行，为后续所有中间件减负）
"""

from __future__ import annotations

from typing import Any, Optional

from ..core.loop import LLMInterface, LLMResponse, LoopState
from ..utils.token_counter import estimate_messages_tokens, estimate_tokens
from ..utils.text import extract_summary
from .base import MiddlewareBase

__all__ = ["SummarizationMiddleware"]

# 默认 token 预算（当无法从 budget_status 获取时使用）
_DEFAULT_TOKEN_BUDGET: int = 8192

# 简单截断时保留的每条消息最大字符数
_TRUNCATE_CHARS: int = 100

# 压缩时保留的最近消息条数（占历史的 1/4，最少 4 条，最多 15 条）
_RECENT_KEEP_MIN: int = 4
_RECENT_KEEP_MAX: int = 15


class SummarizationMiddleware(MiddlewareBase):
    """对话压缩中间件.

    在 ``before_llm_call`` 钩子中检查 token 使用率，
    超过阈值时自动压缩较早的历史消息.

    参数:
        threshold:    token 预算使用率达到多少时触发压缩（0.0–1.0）
        max_messages: 历史消息数超过此值才考虑压缩
        llm:          可选的 LLM 接口引用，用于生成高质量摘要
    """

    def __init__(
        self,
        threshold: float = 0.7,
        max_messages: int = 50,
        llm: Optional[LLMInterface] = None,
    ) -> None:
        self.threshold: float = threshold
        self.max_messages: int = max_messages
        self.llm: Optional[LLMInterface] = llm

    @property
    def priority(self) -> int:
        """压缩中间件优先级最高（10）."""
        return 10

    async def before_llm_call(self, state: LoopState) -> LoopState:
        """在 LLM 调用前检查并压缩历史消息.

        流程:
            1. 消息数不足 → 跳过
            2. 估算 token 使用率 → 低于阈值则跳过
            3. 分割为「待压缩」和「保留」两部分
            4. 生成摘要（LLM 或简单截断）
            5. 用摘要消息替换原始消息
            6. 记录压缩事件到 metadata
        """
        history: list[dict] = state.history

        # 消息数不足，无需压缩
        if len(history) <= self.max_messages:
            return state

        # 估算 token 使用率
        usage_rate: float = self._estimate_usage_rate(state)
        if usage_rate < self.threshold:
            return state

        # 计算保留最近消息的条数
        recent_count: int = min(
            max(len(history) // 4, _RECENT_KEEP_MIN),
            _RECENT_KEEP_MAX,
        )

        # 分割历史
        old_messages: list[dict] = history[:-recent_count]
        recent_messages: list[dict] = history[-recent_count:]

        if not old_messages:
            return state

        # 生成摘要
        if self.llm is not None:
            summary: str = await self._summarize_with_llm(old_messages)
        else:
            summary = self._simple_truncate(old_messages)

        # 用摘要替换原始消息
        summary_message: dict = {
            "role": "system",
            "content": (
                f"[对话摘要] 以下是对之前 {len(old_messages)} 条消息的压缩摘要:\n\n"
                f"{summary}"
            ),
        }

        # 直接修改 state.history（列表原地替换）
        state.history.clear()
        state.history.append(summary_message)
        state.history.extend(recent_messages)

        # 记录压缩事件
        state.metadata.setdefault("summarization", []).append({
            "compressed_count": len(old_messages),
            "usage_rate_before": round(usage_rate, 4),
            "threshold": self.threshold,
            "method": "llm" if self.llm else "truncate",
        })

        return state

    # ── 内部方法 ────────────────────────────────────────────────

    def _estimate_usage_rate(self, state: LoopState) -> float:
        """估算当前 token 预算使用率.

        优先使用 budget_status 中的 token 利用率；
        若不可用，则用历史消息 token 估算值除以默认预算.

        参数:
            state: 当前循环状态

        返回:
            token 使用率（0.0–1.0+）
        """
        # 尝试从 budget_status 获取
        if state.context is not None and state.context.budget_status is not None:
            utilization: dict[str, float] = (
                state.context.budget_status.utilization()
            )
            token_rate: float = utilization.get("tokens", 0.0)
            if token_rate > 0:
                return token_rate

        # 回退：估算历史消息的 token 总量与预算之比
        total_tokens: int = estimate_messages_tokens(state.history)
        budget: int = _DEFAULT_TOKEN_BUDGET

        # 尝试从 budget_status 获取预算上限
        if state.context is not None and state.context.budget_status is not None:
            budget = state.context.budget_status.tokens_max or budget

        return total_tokens / budget if budget > 0 else 0.0

    async def _summarize_with_llm(self, messages: list[dict]) -> str:
        """使用 LLM 生成对话摘要.

        将历史消息拼接后请求 LLM 生成简洁摘要.

        参数:
            messages: 待压缩的消息列表

        返回:
            摘要文本
        """
        # 拼接消息内容
        conversation: str = "\n".join(
            f"[{msg.get('role', 'unknown')}]: {msg.get('content', '')}"
            for msg in messages
        )

        # 构造摘要请求
        prompt: str = (
            "请将以下对话历史压缩为简洁的摘要，保留关键信息和决策:\n\n"
            f"{conversation}\n\n"
            "摘要:"
        )

        try:
            response: LLMResponse = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                tools=[],
                system_prompt="你是一个对话摘要生成器，请简洁地总结对话要点。",
            )
            if response.content:
                return response.content
        except Exception:
            pass  # LLM 失败时回退到简单截断

        return self._simple_truncate(messages)

    def _simple_truncate(self, messages: list[dict]) -> str:
        """简单截断策略 — 无 LLM 时的降级方案.

        保留每条消息的前 100 字符 + 角色标记，拼接为摘要文本.

        参数:
            messages: 待压缩的消息列表

        返回:
            截断后的摘要文本
        """
        truncated_parts: list[str] = []
        for msg in messages:
            role: str = msg.get("role", "unknown")
            content: str = str(msg.get("content", ""))
            # 截取前 _TRUNCATE_CHARS 字符
            snippet: str = extract_summary(content, max_length=_TRUNCATE_CHARS)
            truncated_parts.append(f"[{role}] {snippet}")

        return "\n".join(truncated_parts)
