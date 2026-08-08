"""RAG 完整管道 — ingest → chunk → embed → store → retrieve → augment。

RAGPipeline 整合分块器、检索器和增强 prompt 生成:
    1. ingest:  加载文档文本（字符串或文件路径）
    2. chunk:   使用指定分块策略切分文档
    3. embed:   TF-IDF 向量化（由 retriever_chain 自动完成）
    4. store:   存储分块到检索索引
    5. retrieve: 根据查询检索相关分块
    6. augment:  将检索结果注入 prompt，生成增强上下文

Usage::

    pipeline = RAGPipeline(chunker="semantic")
    pipeline.ingest("# Title\\n\\nContent...", source="readme.md")
    results = pipeline.retrieve("What is this about?")
    prompt = pipeline.augment("What is this about?", results)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .chunker import (
    Chunk,
    BaseChunker,
    FixedSizeChunker,
    SentenceChunker,
    SemanticChunker,
)
from .retriever import RAGResult, RAGRetriever


# ── 分块器工厂 ────────────────────────────────────────────────

_CHUNKER_REGISTRY: Dict[str, type[BaseChunker]] = {
    "fixed": FixedSizeChunker,
    "sentence": SentenceChunker,
    "semantic": SemanticChunker,
}


def get_chunker(name: str, **kwargs: Any) -> BaseChunker:
    """获取分块器实例。

    Args:
        name: 分块策略名称 ("fixed", "sentence", "semantic")。
        **kwargs: 传递给分块器构造函数的参数。

    Returns:
        分块器实例。
    """
    name_lower = name.lower()
    if name_lower not in _CHUNKER_REGISTRY:
        raise ValueError(
            f"Unknown chunker '{name}'. Available: {list(_CHUNKER_REGISTRY.keys())}"
        )
    return _CHUNKER_REGISTRY[name_lower](**kwargs)


# ── RAG 管道 ──────────────────────────────────────────────────

class RAGPipeline:
    """RAG 完整管道。

    Args:
        chunker: 分块策略名称或 BaseChunker 实例。
        chunk_size: 分块大小（传递给分块器）。
        top_k: 默认检索结果数。
        retriever: 可选的自定义 RAGRetriever 实例。
    """

    def __init__(
        self,
        chunker: str | BaseChunker = "semantic",
        chunk_size: int = 500,
        top_k: int = 5,
        retriever: Optional[RAGRetriever] = None,
    ) -> None:
        if isinstance(chunker, BaseChunker):
            self.chunker = chunker
        else:
            # 根据策略选择合适的参数
            if chunker == "semantic":
                self.chunker = SemanticChunker(max_chunk_size=chunk_size)
            elif chunker == "sentence":
                self.chunker = SentenceChunker(target_size=chunk_size)
            else:
                self.chunker = FixedSizeChunker(chunk_size=chunk_size)

        self.retriever = retriever or RAGRetriever(top_k=top_k)
        self._documents: Dict[str, str] = {}

    # ── 1. Ingest ─────────────────────────────────────────────

    def ingest(self, text: str, source: str = "document") -> List[Chunk]:
        """加载文档文本并进行分块和存储。

        Args:
            text: 文档文本内容。
            source: 来源标识（如文件名）。

        Returns:
            分块列表。
        """
        self._documents[source] = text
        chunks = self.chunker.chunk_document(text, source)
        self.retriever.add_chunks(chunks, source)
        return chunks

    def ingest_file(self, file_path: str, encoding: str = "utf-8") -> List[Chunk]:
        """从文件加载文档。

        Args:
            file_path: 文件路径。
            encoding: 文件编码。

        Returns:
            分块列表。
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(file_path, "r", encoding=encoding) as f:
            text = f.read()
        source = os.path.basename(file_path)
        return self.ingest(text, source)

    # ── 2. Chunk (exposed) ────────────────────────────────────

    def chunk(self, text: str, source: str = "") -> List[Chunk]:
        """仅执行分块（不存储）。"""
        return self.chunker.chunk_document(text, source)

    # ── 3. Embed & 4. Store ───────────────────────────────────
    # embed 和 store 由 retriever 在 add_chunks 时自动完成

    def embed_and_store(self, chunks: List[Chunk], source: str = "") -> None:
        """将分块嵌入并存储到检索索引。"""
        self.retriever.add_chunks(chunks, source)

    # ── 5. Retrieve ───────────────────────────────────────────

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[RAGResult]:
        """检索与查询相关的文档分块。"""
        return self.retriever.retrieve(query, top_k=top_k)

    # ── 6. Augment ────────────────────────────────────────────

    def augment(
        self,
        query: str,
        results: Optional[List[RAGResult]] = None,
        system_prompt: str = "",
    ) -> str:
        """将检索结果注入 prompt，生成增强上下文。

        Args:
            query: 用户查询。
            results: 检索结果（如未提供则自动检索）。
            system_prompt: 原始系统 prompt（可选）。

        Returns:
            增强后的 prompt 字符串。
        """
        if results is None:
            results = self.retrieve(query)

        if not results:
            return system_prompt

        # 构建上下文片段
        context_parts: List[str] = []
        for i, r in enumerate(results):
            source_tag = f"[{r.source}]" if r.source else ""
            context_parts.append(f"[{i + 1}]{source_tag} {r.content}")

        context_block = "\n\n".join(context_parts)

        # 组装增强 prompt
        augmented = f"{system_prompt}\n\n## Retrieved Context\n\n{context_block}\n\n## Query\n{query}" if system_prompt else \
                    f"## Retrieved Context\n\n{context_block}\n\n## Query\n{query}"

        return augmented

    def query(self, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        """一步完成检索 + 增强，返回完整结果。

        Args:
            query: 用户查询。
            top_k: 最大检索结果数。

        Returns:
            包含 query, results, augmented_prompt 的字典。
        """
        results = self.retrieve(query, top_k=top_k)
        augmented = self.augment(query, results)
        return {
            "query": query,
            "results": results,
            "augmented_prompt": augmented,
            "result_count": len(results),
        }

    # ── 工具方法 ──────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """获取管道统计信息。"""
        return {
            "chunker": self.chunker.__class__.__name__,
            "document_count": len(self._documents),
            **self.retriever.get_stats(),
        }

    def clear(self) -> None:
        """清空所有文档和索引。"""
        self._documents.clear()
        self.retriever.clear()

    @property
    def document_count(self) -> int:
        return len(self._documents)


__all__ = [
    "RAGPipeline",
    "get_chunker",
    "RAGResult",
    "RAGRetriever",
    "Chunk",
    "BaseChunker",
    "FixedSizeChunker",
    "SentenceChunker",
    "SemanticChunker",
]
