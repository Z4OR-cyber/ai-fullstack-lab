"""记忆注入中间件 — 在 LLM 调用前自动注入相关记忆.

工作流程:
    1. 从最后一条 user message 提取关键词
    2. 调用 ``memory_manager.retrieve_relevant(query)`` 获取相关记忆
    3. 将记忆用 XML 标签 ``<injected_memories>`` 包裹，插入到消息开头
    4. 避免重复注入：检查已注入的记忆 ID 列表

排序优先级: 20（在压缩后执行，注入相关记忆）
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..core.loop import LoopState
from ..utils.text import encode_xml_tag
from .base import MiddlewareBase

__all__ = ["MemoryInjectMiddleware"]

# 简单英文停用词表（用于关键词提取时过滤）
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "to", "of", "in", "on", "at", "by", "for", "with", "about", "as",
    "into", "like", "through", "after", "over", "between", "out",
    "against", "during", "without", "before", "under", "around",
    "and", "but", "or", "so", "if", "because", "when", "while",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
    "this", "that", "these", "those", "what", "which", "who", "whom",
    "how", "why", "where", "there", "here", "not", "no", "yes",
    "的", "了", "是", "在", "我", "你", "他", "她", "它", "们",
    "和", "与", "或", "但", "也", "都", "就", "还", "又", "才",
    "这", "那", "些", "个", "中", "上", "下", "里", "外", "前",
    "吗", "呢", "吧", "啊", "哦", "嗯", "给", "把", "被", "让",
    "什么", "怎么", "为什么", "哪里", "哪个", "哪些",
})

# 关键词提取时最多保留的词数
_MAX_KEYWORDS: int = 10

# 记忆条目中用于唯一标识的字段名
_MEMORY_ID_FIELDS: tuple[str, ...] = ("id", "content")


class MemoryInjectMiddleware(MiddlewareBase):
    """记忆注入中间件.

    在 ``before_llm_call`` 钩子中从对话历史提取关键词，
    检索相关记忆并注入到上下文消息中.

    参数:
        memory_manager: MemoryManager 实例，提供 ``retrieve_relevant`` 方法
        max_entries:     每次最多注入的记忆条目数
    """

    def __init__(
        self,
        memory_manager: Any,
        max_entries: int = 5,
    ) -> None:
        self.memory_manager: Any = memory_manager
        self.max_entries: int = max_entries
        # 跨轮次跟踪已注入的记忆 ID，避免重复注入
        self._injected_ids: set[str] = set()

    @property
    def priority(self) -> int:
        """记忆注入优先级（20）."""
        return 20

    async def before_llm_call(self, state: LoopState) -> LoopState:
        """在 LLM 调用前注入相关记忆.

        流程:
            1. 从最后一条 user message 提取关键词
            2. 调用 memory_manager.retrieve_relevant 检索
            3. 过滤已注入的记忆（去重）
            4. 将新记忆用 XML 标签包裹，插入到消息开头
            5. 更新已注入 ID 列表
        """
        # 提取查询关键词
        query: str = self._extract_query(state.history)
        if not query:
            return state

        # 检索相关记忆
        try:
            memories: list[dict] = self.memory_manager.retrieve_relevant(
                query, top_k=self.max_entries
            )
        except Exception:
            return state

        if not memories:
            return state

        # 过滤已注入的记忆
        new_memories: list[dict] = []
        for mem in memories:
            mem_id: str = self._get_memory_id(mem)
            if mem_id and mem_id in self._injected_ids:
                continue
            new_memories.append(mem)
            if mem_id:
                self._injected_ids.add(mem_id)

        if not new_memories:
            return state

        # 构造注入文本
        memory_text: str = self._format_memories(new_memories)
        memory_block: str = encode_xml_tag("injected_memories", memory_text)

        # 插入到上下文消息开头
        memory_msg: dict = {"role": "system", "content": memory_block}

        # 优先修改 context.messages（影响当前 LLM 调用）
        if state.context is not None and state.context.messages is not None:
            state.context.messages.insert(0, memory_msg)
        else:
            # 回退：修改 history（影响后续上下文组装）
            state.history.insert(0, memory_msg)

        # 在 metadata 中记录注入事件
        state.metadata["injected_memory_count"] = len(new_memories)
        state.metadata["injected_memory_ids"] = [
            self._get_memory_id(m) for m in new_memories
        ]

        return state

    # ── 内部方法 ────────────────────────────────────────────────

    def _extract_query(self, history: list[dict]) -> str:
        """从对话历史中提取最后一条 user message 作为查询.

        如果没有 user message，则使用最后一条消息的内容.

        参数:
            history: 对话历史消息列表

        返回:
            提取的查询字符串（可能为空）
        """
        # 从后往前找最后一条 user 消息
        for msg in reversed(history):
            if msg.get("role") == "user":
                content: str = str(msg.get("content", ""))
                if content:
                    return self._extract_keywords(content)

        # 回退：使用最后一条消息
        if history:
            content = str(history[-1].get("content", ""))
            if content:
                return self._extract_keywords(content)

        return ""

    def _extract_keywords(self, text: str) -> str:
        """从文本中提取关键词，用于记忆检索.

        策略:
            1. 按空格和标点分词
            2. 过滤停用词
            3. 保留较长的词（≥2字符）
            4. 最多保留 _MAX_KEYWORDS 个

        参数:
            text: 原始文本

        返回:
            关键词拼接的查询字符串
        """
        # 按非字母数字字符分词
        tokens: list[str] = re.split(r"[^\w]+", text.lower())
        # 过滤停用词和短词
        keywords: list[str] = [
            t for t in tokens
            if len(t) >= 2 and t not in _STOP_WORDS
        ]
        # 去重并限制数量
        seen: set[str] = set()
        unique_keywords: list[str] = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
            if len(unique_keywords) >= _MAX_KEYWORDS:
                break

        return " ".join(unique_keywords)

    def _format_memories(self, memories: list[dict]) -> str:
        """将记忆列表格式化为可读文本.

        参数:
            memories: 记忆条目列表

        返回:
            格式化后的记忆文本
        """
        lines: list[str] = []
        for i, mem in enumerate(memories, 1):
            content: str = str(mem.get("content", ""))
            layer: str = str(mem.get("layer", "unknown"))
            score: float = float(mem.get("score", 0.0))
            lines.append(f"  {i}. [{layer}] (score={score:.2f}) {content}")

        return "\n".join(lines)

    def _get_memory_id(self, mem: dict) -> str:
        """获取记忆条目的唯一标识.

        优先使用 id 字段，其次使用 content 的前 50 字符作为标识.

        参数:
            mem: 记忆条目字典

        返回:
            记忆的唯一标识字符串
        """
        for field in _MEMORY_ID_FIELDS:
            val: Any = mem.get(field)
            if val:
                return str(val)[:50]
        return ""
