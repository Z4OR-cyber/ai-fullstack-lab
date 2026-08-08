"""RAG Pipeline — 文档分块、检索与增强 prompt 生成。

公共 API:
    - RAGPipeline: 完整 RAG 管道
    - RAGRetriever: 检索器
    - RAGResult: 检索结果
    - Chunk: 分块数据结构
    - FixedSizeChunker / SentenceChunker / SemanticChunker: 分块器
    - get_chunker: 分块器工厂函数
"""

from .chunker import (
    Chunk,
    BaseChunker,
    FixedSizeChunker,
    SentenceChunker,
    SemanticChunker,
)
from .retriever import RAGResult, RAGRetriever
from .pipeline import RAGPipeline, get_chunker

__all__ = [
    "RAGPipeline",
    "RAGRetriever",
    "RAGResult",
    "Chunk",
    "BaseChunker",
    "FixedSizeChunker",
    "SentenceChunker",
    "SemanticChunker",
    "get_chunker",
]
