"""Ground Truth Layer — 最高优先级记忆，覆盖其他层冲突。

Ground Truth 层存储用户明确确认或系统设定的权威信息。
当其他记忆层的内容与 Ground Truth 冲突时，Ground Truth 优先。

每条 Ground Truth 条目包含:
    - content: 内容文本
    - category: 分类（如 "user_profile", "system_config", "verified_fact"）
    - priority: 优先级（用于 Ground Truth 内部排序）
    - verified: 是否已验证
    - timestamp: 创建时间
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .semantic import _tokenize
import numpy as np


@dataclass
class GroundTruthEntry:
    """单条 Ground Truth 条目。

    Attributes:
        id: 唯一标识符。
        content: 权威内容文本。
        category: 分类标签。
        priority: 优先级（数字越大优先级越高）。
        verified: 是否已验证。
        timestamp: 创建时间戳。
        source: 来源标签。
        metadata: 附加元数据。
    """

    content: str
    category: str = "general"
    priority: int = 100
    verified: bool = True
    timestamp: float = field(default_factory=time.time)
    source: str = "user"
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "priority": self.priority,
            "verified": self.verified,
            "timestamp": self.timestamp,
            "source": self.source,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GroundTruthEntry":
        """从字典重建。"""
        return cls(
            content=data["content"],
            category=data.get("category", "general"),
            priority=data.get("priority", 100),
            verified=data.get("verified", True),
            timestamp=data.get("timestamp", time.time()),
            source=data.get("source", "user"),
            metadata=data.get("metadata", {}),
            id=data.get("id", str(uuid.uuid4())),
        )

    def __repr__(self) -> str:
        return (
            f"GroundTruthEntry(id={self.id[:8]}, "
            f"category={self.category!r}, "
            f"priority={self.priority})"
        )


class GroundTruthStore:
    """Ground Truth 存储层 — 最高优先级记忆。

    提供权威信息的存储和检索。当与其他层冲突时，Ground Truth 优先。

    Attributes:
        storage_path: JSON 持久化文件路径。
        entries: 存储的 GroundTruthEntry 列表。
    """

    def __init__(self, storage_path: Optional[str] = None) -> None:
        self.storage_path = storage_path
        self.entries: List[GroundTruthEntry] = []
        if storage_path:
            self._load()

    # ── CRUD ──────────────────────────────────────────────────

    def add(
        self,
        content: str,
        category: str = "general",
        priority: int = 100,
        verified: bool = True,
        source: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GroundTruthEntry:
        """添加一条 Ground Truth。"""
        entry = GroundTruthEntry(
            content=content,
            category=category,
            priority=priority,
            verified=verified,
            source=source,
            metadata=metadata or {},
        )
        self.entries.append(entry)
        self._save()
        return entry

    def add_entry(self, entry: GroundTruthEntry) -> GroundTruthEntry:
        """添加预构造的条目。"""
        self.entries.append(entry)
        self._save()
        return entry

    def get_by_id(self, entry_id: str) -> Optional[GroundTruthEntry]:
        """按 ID 获取。"""
        for e in self.entries:
            if e.id == entry_id:
                return e
        return None

    def get_by_category(self, category: str) -> List[GroundTruthEntry]:
        """按分类获取。"""
        return [e for e in self.entries if e.category == category]

    def delete(self, entry_id: str) -> bool:
        """删除一条条目。"""
        for i, e in enumerate(self.entries):
            if e.id == entry_id:
                self.entries.pop(i)
                self._save()
                return True
        return False

    def update(
        self,
        entry_id: str,
        content: Optional[str] = None,
        priority: Optional[int] = None,
        verified: Optional[bool] = None,
    ) -> bool:
        """更新条目。"""
        e = self.get_by_id(entry_id)
        if not e:
            return False
        if content is not None:
            e.content = content
        if priority is not None:
            e.priority = priority
        if verified is not None:
            e.verified = verified
        self._save()
        return True

    # ── 检索 ──────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """语义检索 Ground Truth 条目。

        Ground Truth 条目的 score 固定为 1.0（最高优先级），
        但仍按相关性排序。

        Args:
            query: 查询文本。
            top_k: 最大返回数。
            category: 可选分类过滤。

        Returns:
            条目字典列表，附带 score 和 layer 字段。
        """
        if not self.entries:
            return []

        # 过滤分类
        candidates = self.entries
        if category:
            candidates = [e for e in self.entries if e.category == category]

        if not candidates:
            return []

        # TF-IDF 检索
        docs = [_tokenize(e.content) for e in candidates]
        matrix, vocab = self._build_tfidf(docs)
        if matrix is None or len(vocab) == 0:
            # 无法计算相似度，返回所有（按优先级排序）
            sorted_entries = sorted(
                candidates, key=lambda e: e.priority, reverse=True
            )
            results = []
            for e in sorted_entries[:top_k]:
                d = e.to_dict()
                d["score"] = 1.0
                d["relevance_score"] = 0.0
                d["layer"] = "ground_truth"
                results.append(d)
            return results

        query_tokens = _tokenize(query)
        query_vec = self._vectorize(query_tokens, vocab)
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 0:
            query_vec /= q_norm

        similarities = matrix @ query_vec

        scored: List[Tuple[float, int]] = []
        for i, entry in enumerate(candidates):
            sim = float(similarities[i])
            # Ground Truth 分数 = 相关性 * (1.0 + 优先级加权)
            score = sim if sim > 0 else 0.0
            if score > 0 or entry.priority >= 100:
                scored.append((score, i))

        scored.sort(key=lambda x: x[0], reverse=True)

        results: List[Dict[str, Any]] = []
        for score, idx in scored[:top_k]:
            d = candidates[idx].to_dict()
            d["score"] = round(score, 4) if score > 0 else 1.0
            d["relevance_score"] = round(float(similarities[idx]), 4)
            d["layer"] = "ground_truth"
            results.append(d)

        return results

    def get_all(self) -> List[GroundTruthEntry]:
        """返回所有条目。"""
        return list(self.entries)

    # ── 冲突裁决 ──────────────────────────────────────────────

    def check_conflict(self, content: str, threshold: float = 0.8) -> List[GroundTruthEntry]:
        """检查给定内容是否与现有 Ground Truth 冲突。

        Args:
            content: 要检查的内容。
            threshold: 相似度阈值，超过则认为可能冲突。

        Returns:
            可能冲突的 GroundTruthEntry 列表。
        """
        if not self.entries:
            return []

        docs = [_tokenize(e.content) for e in self.entries]
        matrix, vocab = self._build_tfidf(docs)
        if matrix is None or len(vocab) == 0:
            return []

        query_tokens = _tokenize(content)
        query_vec = self._vectorize(query_tokens, vocab)
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 0:
            query_vec /= q_norm

        similarities = matrix @ query_vec

        conflicts: List[GroundTruthEntry] = []
        for i, entry in enumerate(self.entries):
            if float(similarities[i]) >= threshold:
                conflicts.append(entry)

        return conflicts

    # ── TF-IDF 内部方法 ───────────────────────────────────────

    @staticmethod
    def _build_tfidf(
        docs: List[List[str]],
    ) -> Tuple[Optional[np.ndarray], Dict[str, int]]:
        """构建 TF-IDF 矩阵。"""
        n_docs = len(docs)
        if n_docs == 0:
            return None, {}

        vocab: Dict[str, int] = {}
        for tokens in docs:
            for t in set(tokens):
                if t not in vocab:
                    vocab[t] = len(vocab)

        if len(vocab) == 0:
            return None, vocab

        df = np.zeros(len(vocab))
        for tokens in docs:
            for t in set(tokens):
                df[vocab[t]] += 1

        idf = np.log((1 + n_docs) / (1 + df)) + 1

        matrix = np.zeros((n_docs, len(vocab)))
        for i, tokens in enumerate(docs):
            counts: Dict[str, int] = {}
            for t in tokens:
                counts[t] = counts.get(t, 0) + 1
            total = len(tokens) if tokens else 1
            for t, c in counts.items():
                matrix[i, vocab[t]] = (c / total) * idf[vocab[t]]

        for i in range(n_docs):
            norm = np.linalg.norm(matrix[i])
            if norm > 0:
                matrix[i] /= norm

        return matrix, vocab

    @staticmethod
    def _vectorize(tokens: List[str], vocab: Dict[str, int]) -> np.ndarray:
        """将 tokens 转换为向量。"""
        vec = np.zeros(len(vocab))
        if not tokens:
            return vec
        counts: Dict[str, int] = {}
        for t in tokens:
            counts[t] = counts.get(t, 0) + 1
        total = len(tokens)
        for t, c in counts.items():
            if t in vocab:
                vec[vocab[t]] = c / total
        return vec

    # ── 持久化 ────────────────────────────────────────────────

    def _save(self) -> None:
        if not self.storage_path:
            return
        os.makedirs(os.path.dirname(self.storage_path) or ".", exist_ok=True)
        data = {"entries": [e.to_dict() for e in self.entries]}
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.entries = [
                GroundTruthEntry.from_dict(d) for d in data.get("entries", [])
            ]
        except (json.JSONDecodeError, KeyError):
            self.entries = []

    def save(self) -> None:
        """公开保存方法。"""
        self._save()

    def __len__(self) -> int:
        return len(self.entries)

    def __repr__(self) -> str:
        return f"GroundTruthStore(entries={len(self.entries)})"


__all__ = [
    "GroundTruthEntry",
    "GroundTruthStore",
]
