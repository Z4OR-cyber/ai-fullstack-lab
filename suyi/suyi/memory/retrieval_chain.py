"""Retrieval Chain — 四级回退检索器链。

实现四级检索器链，依次尝试:
    1. HybridRetriever  — 混合检索（TF-IDF + 关键词）
    2. DenseRetriever   — 密集检索（纯 TF-IDF 向量相似度）
    3. LexicalRetriever — 词汇检索（精确匹配 + 子串匹配）
    4. SQLiteRetriever  — 基础检索（简单遍历匹配）

每个 Retriever 实现统一接口: retrieve(query, top_k) -> List[MemoryItem]
RetrievalChain.retrieve() 依次尝试，第一个返回非空结果即返回。
记录回退日志: {query, fallback_level, result_count}
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from .semantic import _tokenize, TFIDFIndex, InvertedIndex


# ── 统一返回类型 ──────────────────────────────────────────────

@dataclass
class MemoryItem:
    """检索结果统一数据结构。

    Attributes:
        id: 记忆条目 ID。
        content: 内容文本。
        score: 检索相关性分数。
        layer: 来源记忆层。
        source: 检索器名称。
        metadata: 附加元数据。
    """

    content: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    score: float = 0.0
    layer: str = "unknown"
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "score": self.score,
            "layer": self.layer,
            "source": self.source,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"MemoryItem(id={self.id[:8]}, score={self.score:.4f}, "
            f"layer={self.layer!r}, source={self.source!r})"
        )


# ── 检索器基类 ────────────────────────────────────────────────

class BaseRetriever(ABC):
    """检索器抽象基类。

    所有检索器必须实现 retrieve 方法。
    """

    name: str = "base"

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        """检索与 query 相关的记忆。

        Args:
            query: 查询文本。
            top_k: 最大返回数。

        Returns:
            MemoryItem 列表（可能为空）。
        """
        ...


# ── 1. HybridRetriever ────────────────────────────────────────

class HybridRetriever(BaseRetriever):
    """混合检索器 — TF-IDF + 关键词倒排索引。

    结合语义相似度和关键词匹配，适用于大多数场景。

    Attributes:
        documents: 文档列表（字符串）。
        tfidf: TF-IDF 索引。
        inverted: 倒排索引。
        layer: 记忆层标签。
    """

    name = "hybrid"

    def __init__(
        self,
        documents: Optional[List[str]] = None,
        layer: str = "semantic",
    ) -> None:
        self.documents: List[str] = documents or []
        self.layer = layer
        self.tfidf = TFIDFIndex()
        self.inverted = InvertedIndex()
        self._rebuild()

    def add_document(self, doc: str) -> None:
        """添加文档。"""
        self.documents.append(doc)
        self._rebuild()

    def _rebuild(self) -> None:
        """重建索引。"""
        doc_tokens = [_tokenize(d) for d in self.documents]
        self.tfidf.build(doc_tokens)
        self.inverted.build(doc_tokens)

    def retrieve(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        """混合检索: TF-IDF + 关键词。"""
        if not self.documents:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        # TF-IDF 检索
        tfidf_results = self.tfidf.search(query_tokens, top_k=top_k * 2)
        tfidf_scores: Dict[int, float] = {
            idx: score for idx, score in tfidf_results
        }

        # 关键词命中
        keyword_hits = self.inverted.lookup_any(query_tokens)

        scored: List[tuple[float, int]] = []
        for i, doc in enumerate(self.documents):
            tfidf_score = tfidf_scores.get(i, 0.0)
            keyword_boost = 0.15 if i in keyword_hits else 0.0
            final = tfidf_score * 0.85 + keyword_boost
            if final > 0:
                scored.append((final, i))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            MemoryItem(
                content=self.documents[idx],
                score=round(score, 4),
                layer=self.layer,
                source=self.name,
                metadata={"method": "hybrid"},
            )
            for score, idx in scored[:top_k]
        ]


# ── 2. DenseRetriever ─────────────────────────────────────────

class DenseRetriever(BaseRetriever):
    """密集检索器 — 纯 TF-IDF 向量相似度。

    仅使用 TF-IDF 余弦相似度，不使用关键词增强。
    适用于需要纯语义匹配的场景。
    """

    name = "dense"

    def __init__(
        self,
        documents: Optional[List[str]] = None,
        layer: str = "semantic",
    ) -> None:
        self.documents: List[str] = documents or []
        self.layer = layer
        self.tfidf = TFIDFIndex()
        self._rebuild()

    def add_document(self, doc: str) -> None:
        """添加文档。"""
        self.documents.append(doc)
        self._rebuild()

    def _rebuild(self) -> None:
        doc_tokens = [_tokenize(d) for d in self.documents]
        self.tfidf.build(doc_tokens)

    def retrieve(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        """纯 TF-IDF 向量检索。"""
        if not self.documents:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        results = self.tfidf.search(query_tokens, top_k=top_k)

        return [
            MemoryItem(
                content=self.documents[idx],
                score=round(score, 4),
                layer=self.layer,
                source=self.name,
                metadata={"method": "dense"},
            )
            for idx, score in results
        ]


# ── 3. LexicalRetriever ───────────────────────────────────────

class LexicalRetriever(BaseRetriever):
    """词汇检索器 — 精确匹配 + 子串匹配。

    基于词频统计的检索，适用于精确关键词匹配场景。
    """

    name = "lexical"

    def __init__(
        self,
        documents: Optional[List[str]] = None,
        layer: str = "episodic",
    ) -> None:
        self.documents: List[str] = documents or []
        self.layer = layer

    def add_document(self, doc: str) -> None:
        """添加文档。"""
        self.documents.append(doc)

    def retrieve(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        """词汇匹配检索。"""
        if not self.documents:
            return []

        query_terms = [t.lower() for t in query.split() if t.strip()]
        if not query_terms:
            return []

        scored: List[tuple[float, int]] = []
        for i, doc in enumerate(self.documents):
            doc_lower = doc.lower()
            score = sum(1 for term in query_terms if term in doc_lower)
            if score > 0:
                # 归一化到 [0, 1]
                normalized = score / len(query_terms)
                scored.append((normalized, i))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            MemoryItem(
                content=self.documents[idx],
                score=round(score, 4),
                layer=self.layer,
                source=self.name,
                metadata={"method": "lexical"},
            )
            for score, idx in scored[:top_k]
        ]


# ── 4. SQLiteRetriever ────────────────────────────────────────

class SQLiteRetriever(BaseRetriever):
    """基础检索器 — 简单遍历匹配。

    最简单的检索方式，遍历所有文档进行子串匹配。
    作为回退链的最后一环。
    """

    name = "sqlite"

    def __init__(
        self,
        documents: Optional[List[str]] = None,
        layer: str = "episodic",
    ) -> None:
        self.documents: List[str] = documents or []
        self.layer = layer

    def add_document(self, doc: str) -> None:
        """添加文档。"""
        self.documents.append(doc)

    def retrieve(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        """简单子串匹配检索。"""
        if not self.documents:
            return []

        query_lower = query.lower()
        # 取查询的第一个有效词作为匹配词
        query_words = [w for w in query_lower.split() if len(w) >= 2]
        if not query_words:
            return []

        scored: List[tuple[float, int]] = []
        for i, doc in enumerate(self.documents):
            doc_lower = doc.lower()
            # 子串匹配
            matches = sum(1 for w in query_words if w in doc_lower)
            if matches > 0:
                score = matches / len(query_words) * 0.5  # 较低的分数
                scored.append((score, i))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            MemoryItem(
                content=self.documents[idx],
                score=round(score, 4),
                layer=self.layer,
                source=self.name,
                metadata={"method": "substring"},
            )
            for score, idx in scored[:top_k]
        ]


# ── 回退检索链 ────────────────────────────────────────────────

class RetrievalChain:
    """四级回退检索链。

    依次尝试每个检索器，第一个返回非空结果即返回。
    记录回退日志。

    Usage::

        chain = RetrievalChain([
            HybridRetriever(docs, "semantic"),
            DenseRetriever(docs, "semantic"),
            LexicalRetriever(docs, "episodic"),
            SQLiteRetriever(docs, "episodic"),
        ])
        results = chain.retrieve("Python asyncio", top_k=5)
        print(chain.last_fallback_log)
    """

    def __init__(self, retrievers: List[BaseRetriever]) -> None:
        if not retrievers:
            raise ValueError("RetrievalChain requires at least one retriever.")
        self.retrievers = retrievers
        self.fallback_logs: List[Dict[str, Any]] = []
        self.last_fallback_log: Optional[Dict[str, Any]] = None

    def retrieve(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        """依次尝试检索器，第一个返回非空结果即返回。

        Args:
            query: 查询文本。
            top_k: 最大返回数。

        Returns:
            MemoryItem 列表。
        """
        log: Dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "fallback_level": 0,
            "retriever": "",
            "result_count": 0,
            "timestamp": time.time(),
            "attempts": [],
        }

        for level, retriever in enumerate(self.retrievers):
            attempt_info: Dict[str, Any] = {
                "level": level,
                "retriever": retriever.name,
                "result_count": 0,
            }

            try:
                results = retriever.retrieve(query, top_k=top_k)
            except Exception as e:
                attempt_info["error"] = str(e)
                log["attempts"].append(attempt_info)
                continue

            attempt_info["result_count"] = len(results)
            log["attempts"].append(attempt_info)

            if results:
                log["fallback_level"] = level
                log["retriever"] = retriever.name
                log["result_count"] = len(results)
                self.last_fallback_log = log
                self.fallback_logs.append(log)
                return results

        # 所有检索器都返回空
        log["fallback_level"] = -1
        log["retriever"] = "none"
        self.last_fallback_log = log
        self.fallback_logs.append(log)
        return []

    def add_retriever(self, retriever: BaseRetriever) -> None:
        """添加检索器到链尾。"""
        self.retrievers.append(retriever)

    def get_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的回退日志。

        Args:
            limit: 最大返回数。

        Returns:
            日志字典列表。
        """
        return self.fallback_logs[-limit:]

    def clear_logs(self) -> None:
        """清除所有日志。"""
        self.fallback_logs.clear()
        self.last_fallback_log = None

    def __repr__(self) -> str:
        names = [r.name for r in self.retrievers]
        return f"RetrievalChain(retrievers={names})"


__all__ = [
    "MemoryItem",
    "BaseRetriever",
    "HybridRetriever",
    "DenseRetriever",
    "LexicalRetriever",
    "SQLiteRetriever",
    "RetrievalChain",
]
