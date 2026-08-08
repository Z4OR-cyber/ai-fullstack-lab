"""Structured Facts Layer — entity-attribute-value triples with trust scoring.

存储实体-属性-值三元组，每条事实附带 trust_score (0-1)。
信任度规则:
    - 用户明确陈述: 0.95
    - Agent 推断: 0.6
    - 推测: 0.3

提供 trust_decay()（每月 -0.05，下限 0.1）和 trust_boost()（被确认 +0.1，上限 1.0）。
检索时按 (relevance_score * trust_score) 综合排序。
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .semantic import _tokenize


# ── 事实来源标签 ──────────────────────────────────────────────

class FactSource(str, Enum):
    """事实来源类型，决定初始 trust_score."""

    USER_STATEMENT = "user_statement"   # 用户明确陈述
    AGENT_INFERENCE = "agent_inference"  # Agent 推断
    SPECULATION = "speculation"          # 推测
    EXTERNAL = "external"                # 外部来源（工具结果等）


# ── 来源 → 默认信任度映射 ────────────────────────────────────

_DEFAULT_TRUST: Dict[str, float] = {
    FactSource.USER_STATEMENT.value: 0.95,
    FactSource.AGENT_INFERENCE.value: 0.6,
    FactSource.SPECULATION.value: 0.3,
    FactSource.EXTERNAL.value: 0.5,
}


@dataclass
class StructuredFact:
    """单条结构化事实: 实体-属性-值三元组。

    Attributes:
        id: 唯一标识符。
        entity: 实体名称（如 "Python"）。
        attribute: 属性名称（如 "typing_system"）。
        value: 属性值（如 "gradual"）。
        trust_score: 信任度 [0, 1]。
        source: 事实来源类型。
        timestamp: 创建时间戳。
        confirmed_count: 被确认次数。
        last_confirmed: 最后确认时间戳。
        metadata: 附加元数据。
    """

    entity: str
    attribute: str
    value: str
    trust_score: float = 0.5
    source: str = FactSource.EXTERNAL.value
    timestamp: float = field(default_factory=time.time)
    confirmed_count: int = 0
    last_confirmed: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        # 根据来源设置默认 trust_score
        if self.source in _DEFAULT_TRUST and self.trust_score == 0.5:
            self.trust_score = _DEFAULT_TRUST[self.source]
        # 确保在 [0, 1] 范围内
        self.trust_score = max(0.0, min(1.0, self.trust_score))
        # last_confirmed 默认为创建时间
        if self.last_confirmed == 0.0:
            self.last_confirmed = self.timestamp

    # ── 序列化 ────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """转换为 JSON 可序列化的字典。"""
        return {
            "id": self.id,
            "entity": self.entity,
            "attribute": self.attribute,
            "value": self.value,
            "trust_score": self.trust_score,
            "source": self.source,
            "timestamp": self.timestamp,
            "confirmed_count": self.confirmed_count,
            "last_confirmed": self.last_confirmed,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuredFact":
        """从字典重建 StructuredFact。"""
        return cls(
            entity=data["entity"],
            attribute=data["attribute"],
            value=data["value"],
            trust_score=data.get("trust_score", 0.5),
            source=data.get("source", FactSource.EXTERNAL.value),
            timestamp=data.get("timestamp", time.time()),
            confirmed_count=data.get("confirmed_count", 0),
            last_confirmed=data.get("last_confirmed", 0.0),
            metadata=data.get("metadata", {}),
            id=data.get("id", str(uuid.uuid4())),
        )

    # ── 信任度操作 ────────────────────────────────────────────

    def trust_decay(self, months: float = 1.0) -> float:
        """信任度衰减: 每月 -0.05，下限 0.1。

        Args:
            months: 衰减月数（支持小数）。

        Returns:
            衰减后的信任度。
        """
        decay_per_month = 0.05
        min_trust = 0.1
        self.trust_score = max(min_trust, self.trust_score - decay_per_month * months)
        return self.trust_score

    def trust_boost(self, amount: float = 0.1) -> float:
        """信任度提升: 被确认时 +0.1，上限 1.0。

        Args:
            amount: 提升量（默认 0.1）。

        Returns:
            提升后的信任度。
        """
        self.trust_score = min(1.0, self.trust_score + amount)
        self.confirmed_count += 1
        self.last_confirmed = time.time()
        return self.trust_score

    def content_text(self) -> str:
        """返回事实的可读文本表示。"""
        return f"{self.entity}.{self.attribute} = {self.value}"

    def __repr__(self) -> str:
        return (
            f"StructuredFact(entity={self.entity!r}, "
            f"attribute={self.attribute!r}, "
            f"value={self.value!r}, "
            f"trust={self.trust_score:.2f})"
        )


class StructuredFactsStore:
    """结构化事实存储层。

    管理实体-属性-值三元组的增删改查，支持:
        - 按实体/属性检索
        - 语义检索（TF-IDF 余弦相似度）
        - 信任度排序 (relevance_score * trust_score)
        - JSON 持久化

    Attributes:
        storage_path: JSON 持久化文件路径。
        facts: 存储的 StructuredFact 列表。
    """

    def __init__(self, storage_path: Optional[str] = None) -> None:
        self.storage_path = storage_path
        self.facts: List[StructuredFact] = []
        if storage_path:
            self._load()

    # ── CRUD ──────────────────────────────────────────────────

    def add(
        self,
        entity: str,
        attribute: str,
        value: str,
        source: str = FactSource.EXTERNAL.value,
        trust_score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StructuredFact:
        """添加一条结构化事实。

        Args:
            entity: 实体名称。
            attribute: 属性名称。
            value: 属性值。
            source: 事实来源。
            trust_score: 自定义信任度（None 时按 source 自动设置）。
            metadata: 附加元数据。

        Returns:
            创建的 StructuredFact。
        """
        if trust_score is None:
            trust_score = _DEFAULT_TRUST.get(source, 0.5)

        fact = StructuredFact(
            entity=entity,
            attribute=attribute,
            value=value,
            source=source,
            trust_score=trust_score,
            metadata=metadata or {},
        )
        self.facts.append(fact)
        self._save()
        return fact

    def add_fact(self, fact: StructuredFact) -> StructuredFact:
        """添加预构造的 StructuredFact 对象。"""
        self.facts.append(fact)
        self._save()
        return fact

    def get_by_id(self, fact_id: str) -> Optional[StructuredFact]:
        """按 ID 获取事实。"""
        for f in self.facts:
            if f.id == fact_id:
                return f
        return None

    def get_by_entity(self, entity: str) -> List[StructuredFact]:
        """获取某实体的所有事实。"""
        return [f for f in self.facts if f.entity == entity]

    def get_by_entity_attribute(
        self, entity: str, attribute: str
    ) -> Optional[StructuredFact]:
        """获取特定实体+属性的事实。"""
        for f in self.facts:
            if f.entity == entity and f.attribute == attribute:
                return f
        return None

    def delete(self, fact_id: str) -> bool:
        """删除一条事实。"""
        for i, f in enumerate(self.facts):
            if f.id == fact_id:
                self.facts.pop(i)
                self._save()
                return True
        return False

    # ── 语义检索 ──────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_trust: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """语义检索事实，按 (relevance_score * trust_score) 排序。

        使用 TF-IDF 余弦相似度计算 relevance_score，
        最终排序分数 = relevance_score * trust_score。

        Args:
            query: 查询文本。
            top_k: 最大返回数。
            min_trust: 最低信任度过滤。

        Returns:
            事实字典列表，附带 score 字段。
        """
        if not self.facts:
            return []

        # 构建文档列表
        docs = [_tokenize(f.content_text()) for f in self.facts]

        # 构建 TF-IDF
        tfidf_matrix, vocab = self._build_tfidf(docs)
        if tfidf_matrix is None or len(vocab) == 0:
            return []

        # 查询向量
        query_tokens = _tokenize(query)
        query_vec = self._vectorize(query_tokens, vocab)

        # 归一化
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 0:
            query_vec /= q_norm

        # 计算余弦相似度
        similarities = tfidf_matrix @ query_vec

        # 计算综合分数并排序
        scored: List[Tuple[float, int]] = []
        for i, fact in enumerate(self.facts):
            if fact.trust_score < min_trust:
                continue
            relevance = float(similarities[i]) if similarities[i] > 0 else 0.0
            if relevance > 0:
                combined = relevance * fact.trust_score
                scored.append((combined, i))

        scored.sort(key=lambda x: x[0], reverse=True)

        results: List[Dict[str, Any]] = []
        for score, idx in scored[:top_k]:
            d = self.facts[idx].to_dict()
            d["score"] = round(score, 4)
            d["relevance_score"] = round(float(similarities[idx]), 4)
            d["layer"] = "facts"
            results.append(d)

        return results

    # ── 批量信任度操作 ────────────────────────────────────────

    def apply_trust_decay(self, months: float = 1.0) -> int:
        """对所有事实应用信任度衰减。

        Args:
            months: 衰减月数。

        Returns:
            受影响的事实数量。
        """
        for f in self.facts:
            f.trust_decay(months)
        self._save()
        return len(self.facts)

    def confirm_fact(self, fact_id: str) -> bool:
        """确认一条事实（提升信任度）。"""
        f = self.get_by_id(fact_id)
        if f:
            f.trust_boost()
            self._save()
            return True
        return False

    # ── TF-IDF 内部方法 ───────────────────────────────────────

    @staticmethod
    def _build_tfidf(
        docs: List[List[str]],
    ) -> Tuple[Optional[np.ndarray], Dict[str, int]]:
        """构建 TF-IDF 矩阵。"""
        n_docs = len(docs)
        if n_docs == 0:
            return None, {}

        # 构建词表
        vocab: Dict[str, int] = {}
        for tokens in docs:
            for t in set(tokens):
                if t not in vocab:
                    vocab[t] = len(vocab)

        if len(vocab) == 0:
            return None, vocab

        # 文档频率
        df = np.zeros(len(vocab))
        for tokens in docs:
            for t in set(tokens):
                df[vocab[t]] += 1

        # IDF
        idf = np.log((1 + n_docs) / (1 + df)) + 1

        # TF-IDF 矩阵
        matrix = np.zeros((n_docs, len(vocab)))
        for i, tokens in enumerate(docs):
            counts: Dict[str, int] = {}
            for t in tokens:
                counts[t] = counts.get(t, 0) + 1
            total = len(tokens) if tokens else 1
            for t, c in counts.items():
                matrix[i, vocab[t]] = (c / total) * idf[vocab[t]]

        # L2 归一化
        for i in range(n_docs):
            norm = np.linalg.norm(matrix[i])
            if norm > 0:
                matrix[i] /= norm

        return matrix, vocab

    @staticmethod
    def _vectorize(
        tokens: List[str], vocab: Dict[str, int]
    ) -> np.ndarray:
        """将 tokens 转换为 TF-IDF 向量。"""
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
        """保存到 JSON 文件。"""
        if not self.storage_path:
            return
        os.makedirs(os.path.dirname(self.storage_path) or ".", exist_ok=True)
        data = {"facts": [f.to_dict() for f in self.facts]}
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        """从 JSON 文件加载。"""
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.facts = [
                StructuredFact.from_dict(d) for d in data.get("facts", [])
            ]
        except (json.JSONDecodeError, KeyError):
            self.facts = []

    def save(self) -> None:
        """公开保存方法。"""
        self._save()

    # ── 工具方法 ──────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self.facts)

    def __repr__(self) -> str:
        return f"StructuredFactsStore(facts={len(self.facts)})"


__all__ = [
    "StructuredFact",
    "StructuredFactsStore",
    "FactSource",
]
