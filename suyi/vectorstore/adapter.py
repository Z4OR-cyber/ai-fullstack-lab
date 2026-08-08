"""Vector store adapter — bridges vector store with memory module's RetrievalChain.

The adapter wraps a :class:`~.base.VectorStoreBase` instance as a
:class:`~suyi.memory.retrieval_chain.BaseRetriever`, allowing the vector store
to be used as one link in the four-level fallback retrieval chain.

Usage::

    from suyi.vectorstore import InMemoryVectorStore, VectorStoreRetrieverAdapter
    from suyi.memory import RetrievalChain

    store = InMemoryVectorStore(dim=64)
    # ... add vectors ...

    adapter = VectorStoreRetrieverAdapter(store, embed_fn=my_embed_fn)
    chain = RetrievalChain([adapter, ...])
    results = chain.retrieve("query text", top_k=5)
"""

from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from .base import SearchResult, VectorRecord, VectorStoreBase
from .memory_store import InMemoryVectorStore


# Lazy import to avoid circular dependency at module load time
def _import_memory_items():
    """Import MemoryItem and BaseRetriever from suyi.memory.retrieval_chain."""
    from suyi.memory.retrieval_chain import MemoryItem, BaseRetriever
    return MemoryItem, BaseRetriever


# Type alias for an embedding function: str → np.ndarray
EmbedFn = Callable[[str], np.ndarray]


class VectorStoreRetrieverAdapter:
    """Adapter that makes a VectorStoreBase usable as a memory BaseRetriever.

    Wraps a vector store and an optional embedding function.  When
    :meth:`retrieve` is called with a text query, the embedding function
    converts the query to a vector, then the vector store's ``search`` method
    is called.

    The returned results are converted to :class:`MemoryItem` objects so they
    can be used interchangeably with other retrievers in a RetrievalChain.
    """

    def __init__(
        self,
        store: VectorStoreBase,
        embed_fn: Optional[EmbedFn] = None,
        name: str = "vector_store",
        layer: str = "semantic",
    ) -> None:
        self.store = store
        self.embed_fn = embed_fn
        self.name = name
        self.layer = layer

    def _ensure_retriever(self):
        """Lazily import and return a BaseRetriever subclass instance."""
        MemoryItem, BaseRetriever = _import_memory_items()

        adapter_self = self

        class _RetrieverAdapter(BaseRetriever):
            """Concrete retriever backed by a vector store."""

            def retrieve(self, query: str, top_k: int = 5) -> List[MemoryItem]:
                return adapter_self.retrieve(query, top_k)

        retriever = _RetrieverAdapter()
        retriever.name = self.name
        return retriever

    def retrieve(self, query: str, top_k: int = 5) -> List[Any]:
        """Retrieve results for *query*.

        Returns a list of :class:`MemoryItem` objects (imported lazily from
        the memory module).
        """
        MemoryItem, _ = _import_memory_items()

        # Convert query to vector
        if self.embed_fn is not None:
            query_vec = self.embed_fn(query)
        else:
            # Fallback: simple hash-based pseudo-embedding
            query_vec = _default_embed(query, self.store.dim if self.store.dim > 0 else 64)

        # Search
        results = self.store.search(query_vec, top_k=top_k)
        if not results:
            return []

        # Convert to MemoryItem
        items: List[MemoryItem] = []
        for sr in results:
            item = MemoryItem(
                content=sr.record.content,
                id=sr.record.id,
                score=sr.score,
                layer=self.layer,
                source=self.name,
                metadata={
                    **sr.record.metadata,
                    "vector_dim": len(sr.record.vector),
                },
            )
            items.append(item)

        return items

    def as_retriever(self):
        """Return a BaseRetriever instance compatible with RetrievalChain."""
        return self._ensure_retriever()


def _default_embed(text: str, dim: int = 64) -> np.ndarray:
    """Default fallback embedding — deterministic hash-based pseudo-embedding.

    This is NOT a real embedding model; it produces a fixed-dimension vector
    that is consistent for the same input text.  Used only when no real
    embedding function is provided.
    """
    vec = np.zeros(dim, dtype=np.float32)
    # Simple character-level hash
    for i, ch in enumerate(text):
        idx = (ord(ch) + i * 31) % dim
        vec[idx] += 1.0
    # Normalize
    norm = np.linalg.norm(vec)
    if norm > 1e-12:
        vec = vec / norm
    return vec


class RAGVectorStoreAdapter:
    """Adapter that bridges vector store with the RAG pipeline.

    Provides a simple interface for adding documents and searching,
    compatible with :class:`~suyi.rag.pipeline.RAGPipeline` expectations.
    """

    def __init__(
        self,
        store: Optional[VectorStoreBase] = None,
        embed_fn: Optional[EmbedFn] = None,
    ) -> None:
        self.store = store or InMemoryVectorStore()
        self.embed_fn = embed_fn

    def add_documents(
        self,
        documents: List[str],
        ids: Optional[List[str]] = None,
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Add text documents to the vector store.

        Each document is embedded (if an embedding function is available)
        before being stored.
        """
        vectors = []
        for doc in documents:
            if self.embed_fn is not None:
                vectors.append(self.embed_fn(doc))
            else:
                dim = self.store.dim if self.store.dim > 0 else 64
                vectors.append(_default_embed(doc, dim))

        return self.store.add(
            vectors=vectors,
            ids=ids,
            contents=documents,
            metadata=metadata,
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search and return results as plain dicts (RAG-compatible)."""
        if self.embed_fn is not None:
            query_vec = self.embed_fn(query)
        else:
            dim = self.store.dim if self.store.dim > 0 else 64
            query_vec = _default_embed(query, dim)

        results = self.store.search(query_vec, top_k=top_k)
        return [r.to_dict() for r in results]

    def clear(self) -> None:
        """Clear all stored documents."""
        self.store.clear()

    def count(self) -> int:
        """Return number of stored documents."""
        return self.store.count()
