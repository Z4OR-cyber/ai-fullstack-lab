"""Guardrails 中间件 — 在中间件链中集成内容过滤和输出验证.

钩子点:
    - before_llm_call: 输入内容过滤
        检测用户输入中的注入攻击、PII、敏感词、有害内容
        block 动作 → 设置 state.should_stop，阻止 LLM 调用
        redact 动作 → 替换历史中的敏感内容
        warn 动作 → 记录到 metadata 但放行
    - after_llm_call: 输出内容过滤 + 格式验证
        检测 LLM 输出中的有害内容、PII 泄露、危险代码、恶意 URL
        block → 修改 response.content 为安全提示
        redact → 替换输出中的敏感信息
        warn → 记录到 metadata

排序优先级: 15（在压缩之后，记忆注入之前）.
"""

from __future__ import annotations

from typing import Any, Optional

from ..core.loop import LLMResponse, LoopState
from ..middleware.base import MiddlewareBase
from .filters import ContentFilter, FilterResult, FilterAction, Strictness
from .validator import OutputValidator, ValidationResult

__all__ = ["GuardrailsMiddleware"]


class GuardrailsMiddleware(MiddlewareBase):
    """Guardrails 中间件 — 内容过滤 + 输出验证.

    在 before_llm_call 中过滤输入内容，
    在 after_llm_call 中过滤输出内容并验证格式.

    Args:
        content_filter: 可选的 ContentFilter 实例（不提供则创建默认）.
        output_validator: 可选的 OutputValidator 实例（不提供则创建默认）.
        strictness: 严格程度（传递给默认 ContentFilter）.
        block_on_filter: 是否在过滤 block 时停止 LLM 调用（默认 True）.

    使用示例::

        mw = GuardrailsMiddleware(strictness="moderate")
        # 或自定义组件
        mw = GuardrailsMiddleware(
            content_filter=ContentFilter(strictness="strict"),
            output_validator=OutputValidator(enable_url_validation=False),
        )
    """

    def __init__(
        self,
        content_filter: Optional[ContentFilter] = None,
        output_validator: Optional[OutputValidator] = None,
        strictness: str = Strictness.MODERATE,
        block_on_filter: bool = True,
    ) -> None:
        self.content_filter: ContentFilter = content_filter or ContentFilter(
            strictness=strictness
        )
        self.output_validator: OutputValidator = output_validator or OutputValidator()
        self.strictness: str = strictness
        self.block_on_filter: bool = block_on_filter

    @property
    def priority(self) -> int:
        """Guardrails 中间件优先级 15."""
        return 15

    # ── before_llm_call: 输入过滤 ──────────────────────────────

    async def before_llm_call(self, state: LoopState) -> LoopState:
        """在 LLM 调用前过滤输入内容.

        从最后一条用户消息中提取内容进行过滤，
        根据过滤结果决定是否阻止或修改输入.

        Args:
            state: 当前循环状态.

        Returns:
            可能修改后的 state.
        """
        # 提取最后一条用户消息
        last_user_msg: Optional[str] = self._get_last_user_message(state.history)
        if not last_user_msg:
            return state

        # 过滤输入
        result: FilterResult = self.content_filter.filter_input(last_user_msg)

        # 记录到 metadata
        filter_logs: list = state.metadata.setdefault("guardrails_input", [])
        filter_logs.append({
            "action": result.action,
            "reason": result.reason,
            "detected": result.detected,
        })

        # 根据动作处理
        if result.action == FilterAction.BLOCK:
            # 阻止 LLM 调用
            if self.block_on_filter:
                state.should_stop = True
                state.stop_reason = (
                    f"Input blocked by guardrails: {result.reason}"
                )
                state.metadata["guardrails_blocked"] = True

        elif result.action == FilterAction.REDACT:
            # 替换历史中的敏感内容
            self._replace_last_user_message(state, result.redacted_content)

        elif result.action == FilterAction.WARN:
            # 仅记录，放行
            pass

        return state

    # ── after_llm_call: 输出过滤 + 验证 ────────────────────────

    async def after_llm_call(
        self, response: LLMResponse, state: LoopState
    ) -> LLMResponse:
        """在 LLM 调用后过滤输出内容并验证格式.

        对 response.content 进行内容过滤和格式验证，
        根据结果可能修改或替换输出内容.

        Args:
            response: LLM 响应.
            state: 当前循环状态.

        Returns:
            可能修改后的 response.
        """
        if not response.content:
            return response

        # 1. 输出内容过滤
        filter_result: FilterResult = self.content_filter.filter_output(
            response.content
        )

        # 2. 输出格式验证
        validation_result: ValidationResult = self.output_validator.validate(
            response.content
        )

        # 记录到 metadata
        output_logs: list = state.metadata.setdefault("guardrails_output", [])
        output_logs.append({
            "filter_action": filter_result.action,
            "filter_reason": filter_result.reason,
            "validation_valid": validation_result.valid,
            "validation_issues": [
                issue.to_dict() for issue in validation_result.issues
            ],
        })

        # 根据过滤结果处理
        if filter_result.action == FilterAction.BLOCK:
            # 替换输出为安全提示
            response.content = (
                "[Output blocked by guardrails: "
                f"{filter_result.reason}]"
            )
            # 清除工具调用（防止执行被阻止的操作）
            response.tool_calls = []

        elif filter_result.action == FilterAction.REDACT:
            # 使用脱敏后的内容
            response.content = filter_result.redacted_content

        elif filter_result.action == FilterAction.WARN:
            # 记录但不修改
            pass

        # 根据验证结果处理
        if not validation_result.valid:
            # 有严重问题，使用清理后的输出
            if validation_result.sanitized_output:
                response.content = validation_result.sanitized_output

        return response

    # ── 辅助方法 ──────────────────────────────────────────────

    def _get_last_user_message(self, history: list[dict]) -> Optional[str]:
        """从历史中提取最后一条用户消息内容.

        Args:
            history: 对话历史.

        Returns:
            用户消息内容，或 None.
        """
        for msg in reversed(history):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                # 处理列表式内容
                if isinstance(content, list):
                    texts: list[str] = [
                        p.get("text", "")
                        for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    ]
                    return " ".join(texts) if texts else None
        return None

    def _replace_last_user_message(
        self, state: LoopState, new_content: str
    ) -> None:
        """替换历史中最后一条用户消息的内容.

        Args:
            state: 当前循环状态.
            new_content: 新的内容.
        """
        for msg in reversed(state.history):
            if msg.get("role") == "user":
                msg["content"] = new_content
                break
