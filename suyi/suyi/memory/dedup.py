"""Semantic Deduplication — 写入前语义去重。

使用 Cosine 相似度比对新记忆与现有记忆:
    - 相似度超阈值（默认 0.95）的合并为一条
    - 合并策略: 信息并集，时间戳取较新值，trust_score 取较高值
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .semantic import _tokenize


class SemanticDeduplicator:
    """语义去重器 — 写入前检查重复并合并。

    Attributes:
        threshold: 相似度阈值，超过则认为重复（默认 0.95）。
    """

    def __init__(self, threshold: float = 0.95) -> None:
        self.threshold = threshold

    @staticmethod
    def cosine_similarity(text_a: str, text_b: str) -> float:
        """计算两段文本的余弦相似度。

        基于 TF-IDF 向量的余弦相似度。

        Args:
            text_a: 第一段文本。
            text_b: 第二段文本。

        Returns:
            相似度分数 [0, 1]。
        """
        tokens_a = _tokenize(text_a)
        tokens_b = _tokenize(text_b)

        if not tokens_a or not tokens_b:
            return 0.0

        # 构建词表
        vocab: Dict[str, int] = {}
        for t in set(tokens_a) | set(tokens_b):
            if t not in vocab:
                vocab[t] = len(vocab)

        # TF 向量
        def _to_tf_vector(tokens: List[str]) -> np.ndarray:
            vec = np.zeros(len(vocab))
            counts: Dict[str, int] = {}
            for t in tokens:
                counts[t] = counts.get(t, 0) + 1
            total = len(tokens) if tokens else 1
            for t, c in counts.items():
                if t in vocab:
                    vec[vocab[t]] = c / total
            return vec

        vec_a = _to_tf_vector(tokens_a)
        vec_b = _to_tf_vector(tokens_b)

        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

    def find_duplicate(
        self,
        new_content: str,
        existing_items: List[Dict[str, Any]],
        content_key: str = "content",
    ) -> Optional[Tuple[int, float]]:
        """在现有条目中查找与新内容重复的条目。

        Args:
            new_content: 新记忆内容。
            existing_items: 现有条目列表。
            content_key: 条目中内容字段的键名。

        Returns:
            (重复条目索引, 相似度分数) 或 None（无重复）。
        """
        for i, item in enumerate(existing_items):
            existing_content = item.get(content_key, "")
            if not existing_content:
                continue
            sim = self.cosine_similarity(new_content, existing_content)
            if sim >= self.threshold:
                return (i, sim)
        return None

    def merge(
        self,
        new_item: Dict[str, Any],
        existing_item: Dict[str, Any],
        content_key: str = "content",
    ) -> Dict[str, Any]:
        """合并两条重复的记忆。

        合并策略:
            - 内容: 取信息更完整的版本（较长的）
            - 时间戳: 取较新值
            - trust_score: 取较高值
            - tags: 并集
            - 其他字段: 保留新条目的值

        Args:
            new_item: 新记忆条目。
            existing_item: 现有记忆条目。
            content_key: 内容字段键名。

        Returns:
            合并后的条目。
        """
        merged = dict(existing_item)

        # 内容: 取信息更完整的版本
        new_content = new_item.get(content_key, "")
        existing_content = existing_item.get(content_key, "")
        if len(new_content) > len(existing_content):
            merged[content_key] = new_content
        else:
            merged[content_key] = existing_content

        # 时间戳: 取较新值
        new_ts = new_item.get("timestamp", 0)
        existing_ts = existing_item.get("timestamp", 0)
        merged["timestamp"] = max(new_ts, existing_ts)

        # trust_score: 取较高值
        new_trust = new_item.get("trust_score", 0.5)
        existing_trust = existing_item.get("trust_score", 0.5)
        merged["trust_score"] = max(new_trust, existing_trust)

        # tags: 并集
        new_tags = set(new_item.get("tags", []))
        existing_tags = set(existing_item.get("tags", []))
        merged["tags"] = list(new_tags | existing_tags)

        # confidence: 取较高值（如果存在）
        if "confidence" in new_item or "confidence" in existing_item:
            new_conf = new_item.get("confidence", 0.5)
            existing_conf = existing_item.get("confidence", 0.5)
            merged["confidence"] = max(new_conf, existing_conf)

        # 标记为已合并
        merged["_merged"] = True
        merged["_merged_at"] = time.time()

        return merged

    def deduplicate(
        self,
        new_item: Dict[str, Any],
        existing_items: List[Dict[str, Any]],
        content_key: str = "content",
    ) -> Tuple[Dict[str, Any], bool, Optional[int]]:
        """对新条目进行去重检查。

        如果发现重复，合并后返回合并后的条目。
        否则返回原条目。

        Args:
            new_item: 新记忆条目。
            existing_items: 现有条目列表。
            content_key: 内容字段键名。

        Returns:
            (处理后的条目, 是否被合并, 重复条目索引)。
        """
        new_content = new_item.get(content_key, "")
        if not new_content:
            return new_item, False, None

        dup = self.find_duplicate(new_content, existing_items, content_key)
        if dup is not None:
            idx, sim = dup
            merged = self.merge(new_item, existing_items[idx], content_key)
            merged["_dedup_similarity"] = round(sim, 4)
            return merged, True, idx

        return new_item, False, None

    def deduplicate_batch(
        self,
        items: List[Dict[str, Any]],
        content_key: str = "content",
    ) -> Tuple[List[Dict[str, Any]], int]:
        """对一批条目进行去重。

        依次检查每条条目是否与已保留的条目重复，
        重复则合并，不重复则添加到保留列表。

        Args:
            items: 待去重的条目列表。
            content_key: 内容字段键名。

        Returns:
            (去重后的条目列表, 被合并的数量)。
        """
        kept: List[Dict[str, Any]] = []
        merged_count = 0

        for item in items:
            processed, was_merged, dup_idx = self.deduplicate(
                item, kept, content_key
            )
            if was_merged and dup_idx is not None:
                # 替换已保留的条目
                kept[dup_idx] = processed
                merged_count += 1
            else:
                kept.append(processed)

        return kept, merged_count

    def __repr__(self) -> str:
        return f"SemanticDeduplicator(threshold={self.threshold})"


__all__ = ["SemanticDeduplicator"]
