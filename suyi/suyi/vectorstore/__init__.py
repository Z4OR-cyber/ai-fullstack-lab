"""Vector Store — pure numpy in-memory vector storage with cosine similarity.

Public API:
    - VectorStoreBase: abstract interface (add/search/delete/clear/count)
    - InMemoryVectorStore: numpy-backed implementation
    - VectorRecord: single vector record
    - SearchResult: search result with score
    - VectorStoreRetrieverAdapter: bridge to memory RetrievalChain
    - RAGVectorStoreAdapter: bridge to RAG pipeline
"""

from .base import VectorStoreBase, VectorRecord, SearchResult
from .memory_store import InMemoryVectorStore
from .adapter import (
    VectorStoreRetrieverAdapter,
    RAGVectorStoreAdapter,
    EmbedFn,
    _default_embed as default_embed,
)

__all__ = [
    "VectorStoreBase",
    "InMemoryVectorStore",
    "VectorRecord",
    "SearchResult",
    "VectorStoreRetrieverAdapter",
    "RAGVectorStoreAdapter",
    "EmbedFn",
    "default_embed",
]
