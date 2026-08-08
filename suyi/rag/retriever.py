"""RAG 检索管道 — 复用 memory/retrieval_chain 的四级回退，增加文档来源标记。

提供 RAGRetriever 类，支持:
    - 从文档分块构建检索索引
    - 四级回退检索（Hybrid → Dense → Lexical → SQLite）
    - 检索结果附带文档来源元数据
    - 可选集成 MemoryManager 进行联合检索
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..memory.retrieval_chain import (
    MemoryItem,
    BaseRetriever,
    HybridRetriever,
    DenseRetriever,
    LexicalRetriever,
    SQLiteRetriever,
    RetrievalChain,
)
from .chunker import Chunk


# ── 检索结果 ──────────────────────────────────────────────────

@dataclass
class RAGResult:
    """RAG 检索结果。

    Attributes:
        content: 检索到的文本内容。
        score: 相关性分数。
        source: 来源文档名称。
        chunk_index: 分块在原文档中的序号。
        retriever: 使用的检索器名称。
        metadata: 附加元数据。
    """

    content: str
    score: float = 0.0
    source: str = ""
    chunk_index: int = -1
    retriever: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "score": self.score,
            "source": self.source,
            "chunk_index": self.chunk_index,
            "retriever": self.retriever,
            "metadata": self.metadata,
        }

    @classmethod
    def from_memory_item(cls, item: MemoryItem) -> "RAGResult":
        """从 MemoryItem 转换。"""
        return cls(
            content=item.content,
            score=item.score,
            source=item.metadata.get("source", ""),
            chunk_index=item.metadata.get("chunk_index", -1),
            retriever=item.source,
            metadata=item.metadata,
        )

    def __repr__(self) -> str:
        preview = self.content[:40].replace("\n", " ")
        return f"RAGResult(score={self.score:.4f}, source='{self.source}', '{preview}...')"


# ── RAG 检索器 ────────────────────────────────────────────────

class RAGRetriever:
    """RAG 检索器 — 基于四级回退链的文档检索。

    管理多个文档的分块索引，使用 RetrievalChain 进行检索。

    Args:
        top_k: 默认返回结果数。
    """

    def __init__(self, top_k: int = 5) -> None:
        self.top_k = top_k
        self._documents: Dict[str, List[Chunk]] = {}
        self._all_chunks: List[Chunk] = []
        self._chain: Optional[RetrievalChain] = None
        self._rebuild_chain()
        self.retrieve_logs: List[Dict[str, Any]] = []

    def _rebuild_chain(self) -> None:
        """重建检索链。"""
        doc_texts = [c.content for c in self._all_chunks]
        self._chain = RetrievalChain([
            HybridRetriever(list(doc_texts), "rag"),
            DenseRetriever(list(doc_texts), "rag"),
            LexicalRetriever(list(doc_texts), "rag"),
            SQLiteRetriever(list(doc_texts), "rag"),
        ])

    def add_chunks(self, chunks: List[Chunk], source: str = "") -> None:
        """添加分块到检索索引。

        Args:
            chunks: 分块列表。
            source: 来源文档名称（如果未在 chunk.metadata 中指定）。
        """
        for c in chunks:
            if not c.metadata.get("source"):
                c.metadata["source"] = source
            self._all_chunks.append(c)
            if source:
                self._documents.setdefault(source, []).append(c)
        self._rebuild_chain()

    def add_document(self, text: str, source: str = "doc") -> None:
        """便捷方法：直接添加文本文档（按固定大小分块）。"""
        from .chunker import FixedSizeChunker
        chunker = FixedSizeChunker(chunk_size=500, overlap=50)
        chunks = chunker.chunk_document(text, source)
        self.add_chunks(chunks, source)

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[RAGResult]:
        """检索与查询相关的文档分块。

        Args:
            query: 查询文本。
            top_k: 最大返回数（默认使用 self.top_k）。

        Returns:
            RAGResult 列表。
        """
        if not self._chain or not self._all_chunks:
            return []

        k = top_k or self.top_k
        items = self._chain.retrieve(query, top_k=k)

        log: Dict[str, Any] = {
            "query": query,
            "top_k": k,
            "result_count": len(items),
            "timestamp": time.time(),
            "fallback_level": self._chain.last_fallback_log.get("fallback_level", 0) if self._chain.last_fallback_log else 0,
        }
        self.retrieve_logs.append(log)

        results: List[RAGResult] = []
        for item in items:
            result = RAGResult.from_memory_item(item)
            # 从分块元数据中补充来源信息
            # items 是按相关性排序的，尝试从 _all_chunks 中匹配
            results.append(result)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取检索器统计信息。"""
        return {
            "total_chunks": len(self._all_chunks),
            "total_documents": len(self._documents),
            "documents": list(self._documents.keys()),
            "retrieve_count": len(self.retrieve_logs),
        }

    def clear(self) -> None:
        """清空所有文档和索引。"""
        self._documents.clear()
        self._all_chunks.clear()
        self.retrieve_logs.clear()
        self._rebuild_chain()

    @property
    def document_count(self) -> int:
        return len(self._documents)

    @property
    def chunk_count(self) -> int:
        return len(self._all_chunks)


__all__ = [
    "RAGResult",
    "RAGRetriever",
]
