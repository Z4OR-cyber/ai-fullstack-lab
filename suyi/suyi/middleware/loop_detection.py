"""循环检测中间件 — 监控 LLM 输出是否陷入死循环.

检测策略:
    1. 在 ``after_llm_call`` 中检查最近 ``window_size`` 轮的 tool_calls
    2. 同一工具 + 相同参数出现超过 ``max_repeats`` 次 → 判定为死循环
    3. 注入警告消息到对话历史
    4. 连续触发 2 次 → 设置 ``state.should_stop = True`` 终止循环

    在 ``before_tool_call`` 中记录工具调用签名并检查是否重复.

排序优先级: 30（在记忆注入后执行，监控输出行为）
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from typing import Any, Optional

from ..core.loop import LLMResponse, LoopState, ToolCall
from .base import MiddlewareBase

__all__ = ["LoopDetectionMiddleware"]

# 警告消息内容
_LOOP_WARNING_MESSAGE: str = (
    "检测到可能的循环行为，请尝试不同方法"
)

# 调用签名哈希的前缀长度
_HASH_PREFIX_LEN: int = 16


class LoopDetectionMiddleware(MiddlewareBase):
    """循环检测中间件.

    参数:
        max_repeats:  同一工具调用最多重复 N 次告警（超过则判定为死循环）
        window_size:  检查的最近轮数窗口大小
    """

    def __init__(
        self,
        max_repeats: int = 3,
        window_size: int = 5,
    ) -> None:
        self.max_repeats: int = max_repeats
        self.window_size: int = window_size

        # 跨轮次的工具调用签名记录（滚动窗口）
        self._call_signatures: deque[str] = deque(maxlen=window_size)
        # 连续触发警告的次数
        self._consecutive_warnings: int = 0

    @property
    def priority(self) -> int:
        """循环检测优先级（30）."""
        return 30

    async def after_llm_call(
        self, response: LLMResponse, state: LoopState
    ) -> LLMResponse:
        """在 LLM 调用后检查是否陷入循环.

        流程:
            1. 提取本次响应中的 tool_calls 签名
            2. 将签名加入滚动窗口
            3. 统计每个签名的出现次数
            4. 任一签名超过 max_repeats → 注入警告并递增连续触发计数
            5. 连续触发 2 次 → 设置 should_stop
        """
        if not response.tool_calls:
            return response

        # 记录本次响应中所有工具调用的签名
        current_signatures: list[str] = []
        for tc in response.tool_calls:
            sig: str = self._make_signature(tc.name, tc.arguments)
            self._call_signatures.append(sig)
            current_signatures.append(sig)

        # 统计窗口内每个签名的出现次数
        sig_counts: dict[str, int] = {}
        for s in self._call_signatures:
            sig_counts[s] = sig_counts.get(s, 0) + 1

        # 检查是否有签名超过重复上限
        loop_detected: bool = False
        for sig, count in sig_counts.items():
            if count > self.max_repeats:
                loop_detected = True
                break

        if not loop_detected:
            # 未检测到循环，重置连续触发计数
            self._consecutive_warnings = 0
            return response

        # ── 检测到循环 ──────────────────────────────────────────

        # 递增连续触发计数
        self._consecutive_warnings += 1

        # 在 metadata 中记录警告
        state.metadata["loop_warning"] = True
        state.metadata["loop_consecutive_count"] = self._consecutive_warnings

        # 记录重复的工具调用详情
        repeated_tools: list[dict[str, Any]] = []
        for sig, count in sig_counts.items():
            if count > self.max_repeats:
                repeated_tools.append({
                    "signature": sig,
                    "count": count,
                    "max_repeats": self.max_repeats,
                })
        state.metadata["loop_repeated_tools"] = repeated_tools

        # 注入警告消息到对话历史
        warning_msg: dict = {
            "role": "system",
            "content": _LOOP_WARNING_MESSAGE,
        }
        state.history.append(warning_msg)

        # 连续触发 2 次 → 终止循环
        if self._consecutive_warnings >= 2:
            state.should_stop = True
            state.stop_reason = (
                f"循环检测中间件: 连续 {self._consecutive_warnings} 次检测到死循环，"
                f"已自动终止"
            )

        return response

    async def before_tool_call(
        self, tool_name: str, arguments: dict, state: LoopState
    ) -> tuple[str, dict]:
        """在工具调用前记录签名并检查是否重复.

        此方法不阻止工具调用（返回原始参数），仅记录和检查.
        实际的循环判定在 ``after_llm_call`` 中完成.

        参数:
            tool_name:  工具名称
            arguments:  工具参数
            state:      当前循环状态

        返回:
            (tool_name, arguments) 原始值（不做修改）
        """
        sig: str = self._make_signature(tool_name, arguments)

        # 检查是否在窗口中已存在
        existing_count: int = sum(
            1 for s in self._call_signatures if s == sig
        )

        if existing_count >= self.max_repeats:
            # 记录到 metadata 供调试
            state.metadata.setdefault("loop_tool_warning", []).append({
                "tool": tool_name,
                "signature": sig,
                "existing_count": existing_count,
            })

        return tool_name, arguments

    # ── 内部方法 ────────────────────────────────────────────────

    def _make_signature(self, tool_name: str, arguments: dict) -> str:
        """生成工具调用的唯一签名.

        签名 = tool_name + 参数哈希，用于判断是否为重复调用.

        参数:
            tool_name:  工具名称
            arguments:  工具参数

        返回:
            调用签名字符串
        """
        # 将参数排序后序列化，确保相同参数生成相同哈希
        try:
            args_str: str = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            # 不可序列化的参数，退化为字符串表示
            args_str = str(sorted(arguments.items(), key=lambda x: str(x)))

        # 生成 MD5 哈希（取前 16 位即可，避免过长）
        args_hash: str = hashlib.md5(args_str.encode("utf-8")).hexdigest()[:_HASH_PREFIX_LEN]

        return f"{tool_name}:{args_hash}"
