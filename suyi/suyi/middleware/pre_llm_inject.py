"""Pre-LLM-Call 自动记忆注入中间件。

在 before_llm_call 钩子中:
    1. 以当前用户消息为 query，并行查询记忆层
    2. 每条结果附带 relevance_score，低于阈值（默认 0.7）过滤
    3. 维护 session 级 injected_keys 集合，避免重复注入
    4. 注入格式: [Memory · {layer} · score={score}] {content}
    5. Ground Truth 注入时附加强制指令

优先级: 15（在 Guardrails 之后，MemoryInjectMiddleware 之前）
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set

from ..core.loop import LoopState
from .base import MiddlewareBase

__all__ = ["PreLLMInjectMiddleware"]


# Ground Truth 强制指令前缀
_GROUND_TRUTH_PREFIX = (
    "以下内容是你的权威记忆上下文，回答时必须优先参考"
)


class PreLLMInjectMiddleware(MiddlewareBase):
    """Pre-LLM 记忆注入中间件。

    在 LLM 调用前自动查询多层记忆并注入相关内容。

    参数:
        memory_manager: MemoryManager 实例（需支持 retrieve_relevant 和各层检索）。
        relevance_threshold: 相关性阈值，低于此值的记忆不注入（默认 0.7）。
        max_entries: 每次最多注入的记忆条目数（默认 5）。
    """

    def __init__(
        self,
        memory_manager: Any,
        relevance_threshold: float = 0.7,
        max_entries: int = 5,
    ) -> None:
        self.memory_manager = memory_manager
        self.relevance_threshold = relevance_threshold
        self.max_entries = max_entries
        # session 级已注入 key 集合
        self._injected_keys: Set[str] = set()

    @property
    def name(self) -> str:
        return "PreLLMInjectMiddleware"

    @property
    def priority(self) -> int:
        return 15

    def reset_session(self) -> None:
        """重置 session 级状态（新会话时调用）。"""
        self._injected_keys.clear()

    async def before_llm_call(self, state: LoopState) -> LoopState:
        """在 LLM 调用前注入相关记忆。

        流程:
            1. 从最后一条 user message 提取 query
            2. 并行查询记忆层（Ground Truth → Facts → Semantic → Wiki）
            3. 过滤低相关性和已注入的记忆
            4. 格式化并注入到上下文
        """
        # 提取 query
        query = self._extract_query(state.history)
        if not query:
            return state

        # 收集各层记忆
        all_memories: List[Dict[str, Any]] = []
        all_memories.extend(self._query_ground_truth(query))
        all_memories.extend(self._query_facts(query))
        all_memories.extend(self._query_semantic(query))
        all_memories.extend(self._query_wiki(query))

        if not all_memories:
            return state

        # 过滤: 相关性阈值 + 去重
        filtered: List[Dict[str, Any]] = []
        for mem in all_memories:
            score = mem.get("score", 0.0)
            relevance = mem.get("relevance_score", score)
            if relevance < self.relevance_threshold:
                continue

            key = self._get_memory_key(mem)
            if key and key in self._injected_keys:
                continue

            filtered.append(mem)
            if key:
                self._injected_keys.add(key)

            if len(filtered) >= self.max_entries:
                break

        if not filtered:
            return state

        # 格式化注入文本
        injection_text = self._format_injection(filtered)

        # 插入到上下文消息开头
        injection_msg = {"role": "system", "content": injection_text}

        if state.context is not None and state.context.messages is not None:
            state.context.messages.insert(0, injection_msg)
        else:
            state.history.insert(0, injection_msg)

        # 记录注入元数据
        state.metadata["pre_llm_injected_count"] = len(filtered)
        state.metadata["pre_llm_injected_layers"] = list(
            {m.get("layer", "unknown") for m in filtered}
        )

        return state

    # ── 内部方法 ────────────────────────────────────────────

    def _extract_query(self, history: List[Dict[str, Any]]) -> str:
        """从对话历史中提取最后一条 user message。"""
        for msg in reversed(history):
            if msg.get("role") == "user":
                content = str(msg.get("content", ""))
                if content.strip():
                    return content.strip()
        # 回退: 使用最后一条消息
        if history:
            content = str(history[-1].get("content", ""))
            if content.strip():
                return content.strip()
        return ""

    def _query_ground_truth(self, query: str) -> List[Dict[str, Any]]:
        """查询 Ground Truth 层。"""
        mgr = self.memory_manager
        if hasattr(mgr, "ground_truth"):
            try:
                results = mgr.ground_truth.retrieve(query, top_k=self.max_entries)
                for r in results:
                    r["layer"] = "ground_truth"
                    # Ground Truth 的 relevance_score 设为 1.0
                    r.setdefault("relevance_score", 1.0)
                    r.setdefault("score", 1.0)
                return results
            except Exception:
                pass
        return []

    def _query_facts(self, query: str) -> List[Dict[str, Any]]:
        """查询结构化事实层。"""
        mgr = self.memory_manager
        if hasattr(mgr, "structured_facts"):
            try:
                results = mgr.structured_facts.retrieve(query, top_k=self.max_entries)
                for r in results:
                    r["layer"] = "facts"
                return results
            except Exception:
                pass
        return []

    def _query_semantic(self, query: str) -> List[Dict[str, Any]]:
        """查询语义记忆层。"""
        mgr = self.memory_manager
        if hasattr(mgr, "retrieve_relevant"):
            try:
                results = mgr.retrieve_relevant(query, top_k=self.max_entries)
                for r in results:
                    r.setdefault("layer", "semantic")
                return results
            except Exception:
                pass
        return []

    def _query_wiki(self, query: str) -> List[Dict[str, Any]]:
        """查询 Wiki 层。"""
        mgr = self.memory_manager
        if hasattr(mgr, "auto_wiki"):
            try:
                results = mgr.auto_wiki.retrieve(query, top_k=self.max_entries)
                return results
            except Exception:
                pass
        return []

    def _format_injection(self, memories: List[Dict[str, Any]]) -> str:
        """格式化注入文本。

        格式: [Memory · {layer} · score={score}] {content}
        Ground Truth 条目附加强制指令。
        """
        lines: List[str] = []

        # 分离 Ground Truth 和其他记忆
        ground_truth_mems = [m for m in memories if m.get("layer") == "ground_truth"]
        other_mems = [m for m in memories if m.get("layer") != "ground_truth"]

        # Ground Truth 注入（带强制指令）
        if ground_truth_mems:
            lines.append(f"[{time.strftime('%H:%M:%S')}] { _GROUND_TRUTH_PREFIX }")
            for mem in ground_truth_mems:
                layer = mem.get("layer", "ground_truth")
                score = mem.get("score", 1.0)
                content = self._get_content(mem)
                lines.append(f"[Memory · {layer} · score={score:.2f}] {content}")

        # 其他记忆注入
        if other_mems:
            if lines:
                lines.append("")  # 空行分隔
            for mem in other_mems:
                layer = mem.get("layer", "unknown")
                score = mem.get("score", 0.0)
                content = self._get_content(mem)
                lines.append(f"[Memory · {layer} · score={score:.2f}] {content}")

        return "\n".join(lines)

    def _get_content(self, mem: Dict[str, Any]) -> str:
        """从记忆条目中提取内容文本。"""
        # 结构化事实的特殊格式
        if mem.get("layer") == "facts":
            entity = mem.get("entity", "")
            attribute = mem.get("attribute", "")
            value = mem.get("value", "")
            if entity and attribute:
                return f"{entity}.{attribute} = {value}"
        # Wiki 页面的特殊格式
        if mem.get("layer") == "wiki":
            title = mem.get("title", "")
            summary = mem.get("summary", "")
            content = mem.get("content", "")
            if title:
                return f"[{title}] {summary}" if summary else f"[{title}] {content}"
        # 通用: 优先 content 字段
        return str(mem.get("content", ""))

    def _get_memory_key(self, mem: Dict[str, Any]) -> str:
        """获取记忆条目的唯一标识。"""
        # 优先使用 id
        for field in ("id", "content"):
            val = mem.get(field)
            if val:
                return str(val)[:100]
        return ""

    def __repr__(self) -> str:
        return (
            f"PreLLMInjectMiddleware("
            f"threshold={self.relevance_threshold}, "
            f"max={self.max_entries})"
        )
