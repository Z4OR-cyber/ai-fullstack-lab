"""Vector store base — abstract interface for vector storage backends.

All vector store implementations must inherit from :class:`VectorStoreBase`
and implement ``add``, ``search``, ``delete``, and ``clear``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


@dataclass
class VectorRecord:
    """A single record in the vector store.

    Attributes:
        id: Unique identifier (string or auto-generated).
        vector: Embedding vector (1-D numpy array or list of floats).
        content: Original text or metadata payload.
        metadata: Additional key-value metadata.
    """

    id: str
    vector: np.ndarray
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.vector, np.ndarray):
            self.vector = np.asarray(self.vector, dtype=np.float32)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "vector": self.vector.tolist(),
            "content": self.content,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VectorRecord":
        return cls(
            id=d["id"],
            vector=np.asarray(d.get("vector", []), dtype=np.float32),
            content=d.get("content", ""),
            metadata=dict(d.get("metadata", {})),
        )

    def __repr__(self) -> str:
        return (
            f"VectorRecord(id={self.id!r}, dim={self.vector.shape[0]}, "
            f"content={self.content[:40]!r}...)"
        )


@dataclass
class SearchResult:
    """A single search result.

    Attributes:
        record: The matched :class:`VectorRecord`.
        score: Similarity score (higher = more similar).
    """

    record: VectorRecord
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.record.id,
            "score": self.score,
            "content": self.record.content,
            "metadata": dict(self.record.metadata),
        }

    def __repr__(self) -> str:
        return f"SearchResult(id={self.record.id!r}, score={self.score:.4f})"


class VectorStoreBase(ABC):
    """Abstract base class for all vector store implementations.

    Subclasses must implement:
      * ``add``     — insert one or more vectors
      * ``search``  — find top-k similar vectors
      * ``delete``  — remove by id
      * ``clear``   — remove everything
      * ``count``   — number of stored vectors
    """

    #: Store name for identification.
    name: str = "base"

    @abstractmethod
    def add(
        self,
        vectors: Sequence[np.ndarray] | np.ndarray,
        ids: Optional[Sequence[str]] = None,
        contents: Optional[Sequence[str]] = None,
        metadata: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Add one or more vectors.

        Args:
            vectors: Single vector or batch of vectors.
            ids: Optional IDs (auto-generated if None).
            contents: Optional text content for each vector.
            metadata: Optional metadata dicts.

        Returns:
            List of assigned IDs.
        """
        ...

    @abstractmethod
    def search(
        self,
        query: np.ndarray,
        top_k: int = 5,
        filter_fn: Optional[Any] = None,
    ) -> List[SearchResult]:
        """Search for the top-k most similar vectors.

        Args:
            query: Query vector.
            top_k: Maximum number of results.
            filter_fn: Optional callable(record) → bool to filter results.

        Returns:
            List of :class:`SearchResult`, sorted by descending score.
        """
        ...

    @abstractmethod
    def delete(self, ids: str | Sequence[str]) -> int:
        """Delete one or more records by ID.

        Returns:
            Number of records actually deleted.
        """
        ...

    @abstractmethod
    def clear(self) -> None:
        """Remove all records."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Return the number of stored records."""
        ...

    # ── convenience ───────────────────────────────────────────

    def get(self, id: str) -> Optional[VectorRecord]:
        """Retrieve a single record by ID.  Default implementation is O(n)."""
        results = self.search(np.zeros(1, dtype=np.float32), top_k=self.count())
        for r in results:
            if r.record.id == id:
                return r.record
        return None

    def __len__(self) -> int:
        return self.count()

    def __contains__(self, id: str) -> bool:
        return self.get(id) is not None
