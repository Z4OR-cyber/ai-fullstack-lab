"""In-memory vector store — pure numpy cosine similarity search.

No external vector database dependency.  Suitable for small-to-medium
collections that fit in RAM.

Usage::

    from suyi.vectorstore import InMemoryVectorStore

    store = InMemoryVectorStore(dim=128)
    ids = store.add([vec1, vec2, vec3], contents=["a", "b", "c"])
    results = store.search(query_vec, top_k=3)
    store.delete(ids[0])
"""

from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .base import SearchResult, VectorRecord, VectorStoreBase


class InMemoryVectorStore(VectorStoreBase):
    """In-memory vector store using numpy cosine similarity.

    Vectors are stored as a 2-D numpy matrix for efficient batch similarity
    computation.  Cosine similarity is used by default; the store also
    supports L2 (Euclidean) distance mode.

    Attributes:
        dim: Vector dimensionality.
        metric: Similarity metric — ``"cosine"`` or ``"l2"``.
    """

    name = "in_memory"

    def __init__(self, dim: int = 0, metric: str = "cosine") -> None:
        if metric not in ("cosine", "l2"):
            raise ValueError(f"Unknown metric: {metric!r}. Use 'cosine' or 'l2'.")
        self.dim = dim
        self.metric = metric
        self._records: Dict[str, VectorRecord] = {}
        self._matrix: Optional[np.ndarray] = None  # (N, dim)
        self._ids: List[str] = []  # ordered list matching matrix rows
        self._dirty = True  # whether matrix needs rebuild

    # ── internal ──────────────────────────────────────────────

    def _ensure_matrix(self) -> None:
        """Rebuild the internal numpy matrix if dirty."""
        if not self._dirty and self._matrix is not None:
            return
        if not self._ids:
            self._matrix = None
            self._dirty = False
            return
        vectors = [self._records[rid].vector for rid in self._ids]
        self._matrix = np.stack(vectors).astype(np.float32)
        self._dirty = False

    def _normalize(self, vec: np.ndarray) -> np.ndarray:
        """L2-normalize a vector (for cosine similarity)."""
        norm = np.linalg.norm(vec)
        if norm < 1e-12:
            return vec.astype(np.float32)
        return (vec / norm).astype(np.float32)

    # ── public API ─────────────────────────────────────────────

    def add(
        self,
        vectors: Sequence[np.ndarray] | np.ndarray,
        ids: Optional[Sequence[str]] = None,
        contents: Optional[Sequence[str]] = None,
        metadata: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Add one or more vectors.

        Args:
            vectors: Single vector (1-D array) or batch (2-D array / list of arrays).
            ids: Optional IDs. Auto-generated UUIDs if not provided.
            contents: Optional text for each vector.
            metadata: Optional metadata dicts.

        Returns:
            List of assigned IDs.
        """
        # Normalize input to list of 1-D arrays
        if isinstance(vectors, np.ndarray):
            if vectors.ndim == 1:
                vec_list = [vectors]
            elif vectors.ndim == 2:
                vec_list = [vectors[i] for i in range(vectors.shape[0])]
            else:
                raise ValueError(f"Expected 1-D or 2-D array, got {vectors.ndim}-D")
        else:
            vec_list = [np.asarray(v, dtype=np.float32) for v in vectors]

        n = len(vec_list)
        if ids is not None and len(ids) != n:
            raise ValueError(f"Length mismatch: {n} vectors vs {len(ids)} ids")
        if contents is not None and len(contents) != n:
            raise ValueError(f"Length mismatch: {n} vectors vs {len(contents)} contents")
        if metadata is not None and len(metadata) != n:
            raise ValueError(f"Length mismatch: {n} vectors vs {len(metadata)} metadata")

        assigned_ids: List[str] = []
        for i, vec in enumerate(vec_list):
            vec = np.asarray(vec, dtype=np.float32)
            if self.dim == 0:
                self.dim = vec.shape[0]
            elif vec.shape[0] != self.dim:
                raise ValueError(
                    f"Vector dimension mismatch: expected {self.dim}, got {vec.shape[0]}"
                )

            rid = ids[i] if ids else str(uuid.uuid4())
            if rid in self._records:
                raise ValueError(f"Duplicate id: {rid!r}")

            record = VectorRecord(
                id=rid,
                vector=vec,
                content=contents[i] if contents else "",
                metadata=dict(metadata[i]) if metadata else {},
            )
            self._records[rid] = record
            self._ids.append(rid)
            assigned_ids.append(rid)

        self._dirty = True
        return assigned_ids

    def search(
        self,
        query: np.ndarray,
        top_k: int = 5,
        filter_fn: Optional[Callable[[VectorRecord], bool]] = None,
    ) -> List[SearchResult]:
        """Search for top-k most similar vectors.

        Args:
            query: Query vector (1-D, same dimensionality as stored vectors).
            top_k: Maximum number of results.
            filter_fn: Optional filter function applied to each record.

        Returns:
            List of :class:`SearchResult` sorted by descending similarity.
        """
        if self.count() == 0:
            return []

        query = np.asarray(query, dtype=np.float32)
        if query.shape[0] != self.dim:
            raise ValueError(
                f"Query dimension mismatch: expected {self.dim}, got {query.shape[0]}"
            )

        self._ensure_matrix()
        assert self._matrix is not None

        # Compute similarities
        if self.metric == "cosine":
            q_norm = self._normalize(query)
            m_norm = self._normalize_matrix(self._matrix)
            scores = m_norm @ q_norm  # (N,) cosine similarities
        else:
            # L2 distance — convert to similarity (1 / (1 + distance))
            diff = self._matrix - query[np.newaxis, :]  # (N, dim)
            distances = np.linalg.norm(diff, axis=1)  # (N,)
            scores = 1.0 / (1.0 + distances)

        # Apply filter
        if filter_fn is not None:
            mask = np.array(
                [filter_fn(self._records[rid]) for rid in self._ids], dtype=bool
            )
            scores = scores * mask  # zero out non-matching
            # Track which indices were filtered out
            filtered_out = ~mask
        else:
            filtered_out = np.zeros(len(self._ids), dtype=bool)

        # Top-k
        k = min(top_k, len(self._ids))
        if k <= 0:
            return []

        # Get top-k indices
        top_indices = np.argpartition(scores, -k)[-k:]
        # Sort by descending score
        top_indices = top_indices[np.argsort(-scores[top_indices])]

        results: List[SearchResult] = []
        for idx in top_indices:
            # Skip results that were filtered out by filter_fn
            if filtered_out[idx]:
                continue
            score = float(scores[idx])
            rid = self._ids[idx]
            record = self._records[rid]
            results.append(SearchResult(record=record, score=score))

        return results[:top_k]

    def _normalize_matrix(self, matrix: np.ndarray) -> np.ndarray:
        """L2-normalize each row of *matrix*."""
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms < 1e-12, 1.0, norms)
        return (matrix / norms).astype(np.float32)

    def delete(self, ids: str | Sequence[str]) -> int:
        """Delete one or more records by ID.

        Returns:
            Number of records actually deleted.
        """
        if isinstance(ids, str):
            ids = [ids]

        deleted = 0
        for rid in ids:
            if rid in self._records:
                del self._records[rid]
                self._ids.remove(rid)
                deleted += 1

        if deleted > 0:
            self._dirty = True
        return deleted

    def clear(self) -> None:
        """Remove all records."""
        self._records.clear()
        self._ids.clear()
        self._matrix = None
        self._dirty = False

    def count(self) -> int:
        """Return the number of stored records."""
        return len(self._records)

    # ── extra methods ─────────────────────────────────────────

    def get(self, id: str) -> Optional[VectorRecord]:
        """Directly retrieve a record by ID."""
        return self._records.get(id)

    def get_all(self) -> List[VectorRecord]:
        """Return all records (no particular order guaranteed)."""
        return list(self._records.values())

    def stats(self) -> Dict[str, Any]:
        """Return store statistics."""
        self._ensure_matrix()
        total_bytes = 0
        if self._matrix is not None:
            total_bytes = self._matrix.nbytes
        return {
            "name": self.name,
            "dim": self.dim,
            "metric": self.metric,
            "count": self.count(),
            "matrix_bytes": total_bytes,
        }
