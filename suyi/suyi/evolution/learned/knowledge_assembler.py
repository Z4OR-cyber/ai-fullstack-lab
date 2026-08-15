"""三级知识注入器 — 将旁路知识分层组装为 system prompt 片段.

三级结构（来自双循环架构图"检索反哺内循环"思想）：

    **Tier 1 — 蒸馏原则（稳定）**
        高 confidence 的 ``guideline`` 条目，每次都注入，类似 system prompt
        的固定部分。对应"稳定不动"的主干。

    **Tier 2 — 案例知识（动态检索）**
        ``success_pattern`` 和 ``failure_lesson`` 条目，根据当前 query
        做 TF-IDF 语义检索 top_k。对应"实时反哺内循环"。

    **Tier 3 — 专项技能（按任务路由）**
        ``style`` 或带特定标签的条目，根据任务类型标签匹配。对应
        "按需加载的专项能力"。

集成方式：本类实现 async ``retrieve(query, top_k)``，使其本身可作为
:class:`~suyi.core.context.MemoryBackend` 使用，直接插入
:class:`~suyi.core.context.ContextAssembler` 而无需修改其公开接口。
retrieve 返回三级合并后的条目列表，每条带 ``tier`` 标记。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .retriever import KnowledgeRetriever
from .store import KnowledgeEntry, LearnedKnowledgeStore


@dataclass
class KnowledgeTier:
    """一级知识的组装结果.

    Attributes:
        tier: 层级编号（1/2/3）.
        name: 层级名称.
        entries: 该层级包含的知识条目.
        section_text: 格式化后的 XML section 文本.
    """

    tier: int
    name: str
    entries: List[KnowledgeEntry] = field(default_factory=list)
    section_text: str = ""


class ThreeTierKnowledgeInjector:
    """三级旁路知识注入器，兼容 MemoryBackend Protocol.

    Usage::

        store = LearnedKnowledgeStore()
        retriever = KnowledgeRetriever(store)
        injector = ThreeTierKnowledgeInjector(store, retriever)

        # 作为 MemoryBackend 直接给 ContextAssembler
        assembler = ContextAssembler(memory_backend=injector)

        # 或显式组装三级知识
        tiers = await injector.inject(query, task_tags=["文件操作"])
        prompt = injector.format_for_system_prompt(tiers)
    """

    # Tier 名称
    TIER1_NAME = "蒸馏原则"
    TIER2_NAME = "案例知识"
    TIER3_NAME = "专项技能"

    # XML section 标签名
    TIER1_TAG = "learned_principles"
    TIER2_TAG = "learned_cases"
    TIER3_TAG = "learned_specialization"

    def __init__(
        self,
        store: LearnedKnowledgeStore,
        retriever: KnowledgeRetriever,
        tier1_max: int = 5,
        tier2_top_k: int = 3,
        tier3_max: int = 2,
        tier1_min_confidence: float = 0.6,
    ) -> None:
        """
        Args:
            store: 旁路知识存储.
            retriever: 知识检索器（用于 Tier2 语义检索）.
            tier1_max: Tier1 最多注入的原则条目数.
            tier2_top_k: Tier2 语义检索返回数.
            tier3_max: Tier3 最多注入的专项条目数.
            tier1_min_confidence: Tier1 条目的最低置信度.
        """
        self.store = store
        self.retriever = retriever
        self.tier1_max = tier1_max
        self.tier2_top_k = tier2_top_k
        self.tier3_max = tier3_max
        self.tier1_min_confidence = tier1_min_confidence

    # ── 三级组装 ─────────────────────────────────────────

    async def inject(
        self,
        query: str,
        task_tags: Optional[List[str]] = None,
        bureau: str = "default",
    ) -> List[KnowledgeTier]:
        """组装三级知识.

        Args:
            query: 当前用户查询（用于 Tier2 语义检索）.
            task_tags: 当前任务标签（用于 Tier3 路由）.
            bureau: 业务域，不同 bureau 知识隔离.

        Returns:
            三个 :class:`KnowledgeTier`（tier 1/2/3，始终返回 3 项，
            某层无内容时 entries 为空、section_text 为空串）.
        """
        task_tags = task_tags or []

        tier1_entries = self._build_tier1(bureau)
        tier2_entries = await self._build_tier2(query, bureau)
        tier3_entries = self._build_tier3(task_tags, bureau)

        tier1 = KnowledgeTier(
            tier=1,
            name=self.TIER1_NAME,
            entries=tier1_entries,
            section_text=self._format_section(self.TIER1_TAG, tier1_entries),
        )
        tier2 = KnowledgeTier(
            tier=2,
            name=self.TIER2_NAME,
            entries=tier2_entries,
            section_text=self._format_section(self.TIER2_TAG, tier2_entries),
        )
        tier3 = KnowledgeTier(
            tier=3,
            name=self.TIER3_NAME,
            entries=tier3_entries,
            section_text=self._format_section(self.TIER3_TAG, tier3_entries),
        )

        return [tier1, tier2, tier3]

    def format_for_system_prompt(self, tiers: List[KnowledgeTier]) -> str:
        """将三级知识格式化为 XML 风格的 system prompt 片段.

        生成三个 section：
            <learned_principles> ... </learned_principles>
            <learned_cases> ... </learned_cases>
            <learned_specialization> ... </learned_specialization>

        空层级不会输出任何内容（连标签也不输出），避免污染 prompt.

        Args:
            tiers: :meth:`inject` 返回的层级列表.

        Returns:
            可直接拼接到 system prompt 的文本片段.
        """
        sections = [t.section_text for t in tiers if t.section_text]
        return "\n\n".join(sections)

    # ── MemoryBackend 适配 ───────────────────────────────

    async def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """MemoryBackend Protocol 实现.

        组装三级知识并展平为 dict 列表，每个 dict 带 ``tier`` 标记，
        可直接被 ContextAssembler 的 memory 层消费。

        Args:
            query: 查询文本.
            top_k: 总返回上限（三级合并后截断）.

        Returns:
            dict 列表，每项含 content/source/confidence/tier 等字段.
        """
        tiers = await self.inject(query)
        items: List[Dict[str, Any]] = []
        # 按层级顺序加入：先原则，再案例，再专项
        for tier in tiers:
            for entry in tier.entries:
                items.append({
                    "content": entry.content,
                    "source": f"learned_knowledge/tier{tier.tier}",
                    "confidence": round(entry.confidence, 4),
                    "tier": tier.tier,
                    "id": entry.id,
                    "title": entry.title,
                    "category": entry.category,
                })
                if len(items) >= top_k:
                    return items
        return items

    # ── 各层构建 ─────────────────────────────────────────

    def _build_tier1(self, bureau: str) -> List[KnowledgeEntry]:
        """Tier1：高置信度 guideline，每次注入（稳定原则）."""
        guidelines = self.store.list(bureau=bureau, category="guideline")
        # 过滤置信度并按置信度降序
        filtered = [
            e for e in guidelines if e.confidence >= self.tier1_min_confidence
        ]
        filtered.sort(key=lambda e: e.confidence, reverse=True)
        return filtered[: self.tier1_max]

    async def _build_tier2(
        self, query: str, bureau: str
    ) -> List[KnowledgeEntry]:
        """Tier2：根据 query 语义检索 success_pattern / failure_lesson."""
        if not query:
            return []

        # 分别检索两类，合并去重后取 top_k
        pattern_entries = self.store.list(bureau=bureau, category="success_pattern")
        lesson_entries = self.store.list(bureau=bureau, category="failure_lesson")
        candidates = pattern_entries + lesson_entries
        if not candidates:
            return []

        # 使用 retriever 的语义检索（它会跨全部条目检索，这里用 top_k*2
        # 然后过滤出本层两类并按相似度排序）
        results = self.retriever.retrieve_entries(query, top_k=len(candidates))
        tier2: List[KnowledgeEntry] = []
        seen_ids = set()
        for entry, _score in results:
            if entry.category in ("success_pattern", "failure_lesson"):
                if entry.bureau == bureau and entry.id not in seen_ids:
                    tier2.append(entry)
                    seen_ids.add(entry.id)
            if len(tier2) >= self.tier2_top_k:
                break
        return tier2

    def _build_tier3(
        self, task_tags: List[str], bureau: str
    ) -> List[KnowledgeEntry]:
        """Tier3：按任务标签路由 style 或带特定 tags 的条目."""
        style_entries = self.store.list(bureau=bureau, category="style")
        if not task_tags:
            # 无任务标签时，按置信度返回高置信 style
            style_entries.sort(key=lambda e: e.confidence, reverse=True)
            return style_entries[: self.tier3_max]

        tag_set = set(task_tags)
        matched: List[tuple[KnowledgeEntry, int]] = []
        for entry in style_entries:
            # 计算标签重叠数作为路由分数
            overlap = len(tag_set & set(entry.tags))
            if overlap > 0:
                matched.append((entry, overlap))
        # 也支持任意类别但标签匹配的专项条目（非 guideline，因为已在 tier1）
        for entry in self.store.list(bureau=bureau):
            if entry.category in ("guideline", "style"):
                continue
            if entry.id in {e.id for e, _ in matched}:
                continue
            overlap = len(tag_set & set(entry.tags))
            if overlap > 0:
                matched.append((entry, overlap))

        matched.sort(key=lambda x: (x[1], x[0].confidence), reverse=True)
        return [entry for entry, _ in matched[: self.tier3_max]]

    # ── 格式化 ───────────────────────────────────────────

    def _format_section(
        self, tag: str, entries: List[KnowledgeEntry]
    ) -> str:
        """将一组条目格式化为 <tag>...</tag> XML section."""
        if not entries:
            return ""
        lines: List[str] = []
        for entry in entries:
            # 每条以 "- 标题：内容" 形式呈现
            prefix = f"[{entry.category}] " if entry.category else ""
            title = f"{entry.title} — " if entry.title else ""
            lines.append(f"- {prefix}{title}{entry.content}")
        body = "\n".join(lines)
        return f"<{tag}>\n{body}\n</{tag}>"
