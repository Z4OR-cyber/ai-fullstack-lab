"""语义去重器 — 旁路知识入库前三策略判定（skip/merge/append）.

新蒸馏出的知识条目在写入 store 前，需要与已有条目比较语义相似度，
避免知识库膨胀并合并重复经验。三种策略：

    - **SKIP**：高度相似（≥ skip_threshold），说明该知识已存在。
      不新增，而是在已有条目上追加来源引用并提升置信度。
    - **MERGE**：中等相似（merge_threshold ~ skip_threshold），
      两条知识相关但不完全相同，标记为可合并。纯 numpy 实现做
      简单拼接，不调用 LLM（接口预留 llm_fn 供未来增强）。
    - **APPEND**：低相似（< merge_threshold），作为新知识追加。

相似度基于 :mod:`retriever` 中的 TF-IDF 余弦相似度。注意：
只在 **同一 bureau + 同一 category** 内比较，跨类知识不互相去重。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, TYPE_CHECKING

import numpy as np

from .retriever import tokenize
from .store import KnowledgeEntry

if TYPE_CHECKING:
    from .store import LearnedKnowledgeStore


class DeduplicationResult(Enum):
    """去重决策结果."""

    SKIP = "skip"
    MERGE = "merge"
    APPEND = "append"


@dataclass
class DedupDecision:
    """一次去重判定的结果.

    Attributes:
        action: 采取的动作（SKIP / MERGE / APPEND）.
        target_id: SKIP/MERGE 时命中的目标条目 ID.
        merged_content: MERGE 时合并后的新内容（纯规则拼接）.
        reason: 人类可读的判定原因.
        similarity: 与最相似条目的相似度（0-1）.
    """

    action: DeduplicationResult
    target_id: Optional[str] = None
    merged_content: Optional[str] = None
    reason: str = ""
    similarity: float = 0.0


def _cosine_similarity(text_a: str, text_b: str) -> float:
    """计算两段文本的 TF 余弦相似度（不依赖 retriever 缓存，轻量内联）.

    用于去重时的成对比较。使用共享 token 词表构建词频向量。
    """
    tokens_a = tokenize(text_a)
    tokens_b = tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0

    vocab: dict[str, int] = {}
    vec_a = np.zeros(max(len(tokens_a), len(tokens_b)) + 8, dtype=np.float64)
    vec_b = np.zeros_like(vec_a)

    for tok in tokens_a:
        idx = vocab.setdefault(tok, len(vocab))
        if idx >= len(vec_a):
            vec_a = np.resize(vec_a, idx + 8)
            vec_b = np.resize(vec_b, idx + 8)
        vec_a[idx] += 1.0
    for tok in tokens_b:
        idx = vocab.setdefault(tok, len(vocab))
        if idx >= len(vec_a):
            vec_a = np.resize(vec_a, idx + 8)
            vec_b = np.resize(vec_b, idx + 8)
        vec_b[idx] += 1.0

    # 截断到实际词表大小
    size = len(vocab)
    vec_a = vec_a[:size]
    vec_b = vec_b[:size]

    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


class SemanticDeduplicator:
    """旁路知识语义去重器.

    Usage::

        dedup = SemanticDeduplicator(store, skip_threshold=0.85, merge_threshold=0.55)
        decision = dedup.decide(new_content, bureau="default", category="success_pattern")
        dedup.apply(decision, new_entry)
    """

    def __init__(
        self,
        store: "LearnedKnowledgeStore",
        skip_threshold: float = 0.85,
        merge_threshold: float = 0.55,
        llm_fn: Optional[Callable[[str, str], str]] = None,
    ) -> None:
        """
        Args:
            store: 旁路知识存储.
            skip_threshold: SKIP 阈值（≥ 此值视为重复）.
            merge_threshold: MERGE 阈值（≥ 此值且 < skip 视为可合并）.
            llm_fn: 可选的 LLM 合并函数，签名
                ``(content_a, content_b) -> merged_content``。
                为 None 时使用纯规则拼接。
        """
        self.store = store
        self.skip_threshold = skip_threshold
        self.merge_threshold = merge_threshold
        self.llm_fn = llm_fn

    def decide(
        self,
        new_content: str,
        bureau: str = "default",
        category: str = "guideline",
        new_title: str = "",
    ) -> DedupDecision:
        """判定新内容应执行的去重策略.

        仅与同 bureau + 同 category 的条目比较。

        Args:
            new_content: 待入库的新规则正文.
            bureau: 业务域.
            category: 知识类别.
            new_title: 新条目标题（参与相似度计算，可选）.

        Returns:
            :class:`DedupDecision` 判定结果.
        """
        candidates = self.store.list(bureau=bureau, category=category)
        if not candidates:
            return DedupDecision(
                action=DeduplicationResult.APPEND,
                reason="库中无同类条目，直接追加",
                similarity=0.0,
            )

        query_text = f"{new_title} {new_content}".strip()
        best_sim = -1.0
        best_entry: Optional[KnowledgeEntry] = None

        for entry in candidates:
            existing_text = f"{entry.title} {entry.content}"
            sim = _cosine_similarity(query_text, existing_text)
            if sim > best_sim:
                best_sim = sim
                best_entry = entry

        assert best_entry is not None

        if best_sim >= self.skip_threshold:
            return DedupDecision(
                action=DeduplicationResult.SKIP,
                target_id=best_entry.id,
                reason=f"与条目 {best_entry.id} 高度相似 (sim={best_sim:.3f})，跳过新增",
                similarity=best_sim,
            )

        if best_sim >= self.merge_threshold:
            merged = self._merge_content(best_entry.content, new_content)
            return DedupDecision(
                action=DeduplicationResult.MERGE,
                target_id=best_entry.id,
                merged_content=merged,
                reason=(
                    f"与条目 {best_entry.id} 中等相似 (sim={best_sim:.3f})，"
                    f"标记合并"
                ),
                similarity=best_sim,
            )

        return DedupDecision(
            action=DeduplicationResult.APPEND,
            reason=f"无显著相似条目 (best_sim={best_sim:.3f})，追加新知识",
            similarity=best_sim,
        )

    def apply(
        self,
        decision: DedupDecision,
        entry: KnowledgeEntry,
    ) -> Optional[str]:
        """执行去重决策.

        - SKIP：不新增，在目标条目上追加 source_ids 并提升 confidence.
        - MERGE：更新目标条目 content，合并 source_ids/tags.
        - APPEND：将 entry 写入 store.

        Args:
            decision: :meth:`decide` 返回的决策.
            entry: 待入库的新条目（APPEND 时使用）.

        Returns:
            最终生效的条目 ID（SKIP/MERGE 返回目标 ID，APPEND 返回新 ID）；
            若操作失败返回 None.
        """
        if decision.action == DeduplicationResult.SKIP:
            if not decision.target_id:
                return None
            target = self.store.get(decision.target_id)
            if target is None:
                return None
            # 追加来源引用（去重）
            existing_sources = set(target.source_ids)
            for sid in entry.source_ids:
                if sid not in existing_sources:
                    target.source_ids.append(sid)
                    existing_sources.add(sid)
            # 置信度随来源数量提升（来源越多越可信），上限 1.0
            # 每条新来源贡献 +0.05，但受相似度折扣
            boost = 0.05 * len(entry.source_ids)
            target.confidence = min(1.0, target.confidence + boost)
            # 标签合并
            self._merge_tags(target, entry.tags)
            self.store.update(
                target.id,
                source_ids=target.source_ids,
                confidence=target.confidence,
                tags=target.tags,
            )
            return target.id

        if decision.action == DeduplicationResult.MERGE:
            if not decision.target_id:
                return None
            target = self.store.get(decision.target_id)
            if target is None:
                return None
            merged_content = (
                decision.merged_content
                or self._merge_content(target.content, entry.content)
            )
            # 合并来源与标签
            existing_sources = set(target.source_ids)
            for sid in entry.source_ids:
                if sid not in existing_sources:
                    target.source_ids.append(sid)
                    existing_sources.add(sid)
            self._merge_tags(target, entry.tags)
            # 合并后置信度取两者较高值并略微提升
            new_confidence = min(1.0, max(target.confidence, entry.confidence) + 0.03)
            self.store.update(
                target.id,
                content=merged_content,
                source_ids=target.source_ids,
                tags=target.tags,
                confidence=new_confidence,
            )
            return target.id

        # APPEND
        return self.store.add(entry)

    # ── 内部方法 ──────────────────────────────────────────

    def _merge_content(self, existing: str, new: str) -> str:
        """合并两段内容：优先用 LLM，否则纯规则拼接."""
        if self.llm_fn is not None:
            try:
                return self.llm_fn(existing, new)
            except Exception:
                # LLM 失败时回退到规则拼接
                pass
        existing = existing.strip()
        new = new.strip()
        if new in existing:
            return existing
        if existing in new:
            return new
        return f"{existing}\n（补充）{new}"

    @staticmethod
    def _merge_tags(target: KnowledgeEntry, new_tags: List[str]) -> None:
        """将新标签合并进目标条目（原地修改，去重）."""
        existing = set(target.tags)
        for tag in new_tags:
            if tag not in existing:
                target.tags.append(tag)
                existing.add(tag)
