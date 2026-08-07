"""Semantic Memory — cross-session knowledge base with TF-IDF retrieval.

Semantic memory stores durable *knowledge entries* that persist across
sessions.  Retrieval uses a pure-numpy TF-IDF vector space model combined
with a keyword inverted index for fast lookups.

No external vector database or embedding model is required — everything
is computed from scratch with numpy.

Memory entry fields
-------------------

Each entry contains:

================  ============  ========================================
Field             Type          Description
================  ============  ========================================
``content``       str           The knowledge text.
``tags``          list[str]     Categorisation tags.
``confidence``    float         Belief score in [0, 1].
``success_count`` int           Times this knowledge was useful.
``fail_count``    int           Times this knowledge was misleading.
``created_at``    float         Unix timestamp.
``last_accessed`` float         Unix timestamp of last retrieval.
================  ============  ========================================

TF-IDF implementation
---------------------

1.  **Tokenise** — split on whitespace/punctuation; CJK characters are
    treated as individual tokens (bigrams are also extracted for better
    matching).
2.  **Vocabulary** — map every unique token to a column index.
3.  **TF** — normalised term frequency per document.
4.  **IDF** — ``log((1 + N) / (1 + df)) + 1`` (smoothed).
5.  **Cosine similarity** — query vector vs. every document vector.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ----------------------------------------------------------------------
#  Tokeniser
# ----------------------------------------------------------------------
# Matches CJK characters, alphanumeric words, and standalone symbols.
_TOKEN_RE = re.compile(
    r'[\u4e00-\u9fff\u3400-\u4dbf]'   # individual CJK chars
    r'|[a-zA-Z][a-zA-Z0-9_]*'          # English words
    r'|\d+(?:\.\d+)?'                  # numbers
)


def _tokenize(text: str) -> List[str]:
    """Tokenise text into a list of lowercased tokens.

    - CJK characters → individual tokens (also generates bigrams).
    - English words → whole-word tokens.
    - Numbers → preserved as tokens.

    Args:
        text: Input text.

    Returns:
        List of tokens (lowercased).
    """
    if not text:
        return []

    raw = _TOKEN_RE.findall(text)

    # Normalise to lowercase
    tokens = [t.lower() for t in raw]

    # Generate CJK bigrams for better matching
    cjk_bigrams: List[str] = []
    for i in range(len(tokens) - 1):
        if len(tokens[i]) == 1 and len(tokens[i + 1]) == 1:
            # Both are single CJK chars → form a bigram
            if '\u4e00' <= tokens[i][0] <= '\u9fff' and \
               '\u4e00' <= tokens[i + 1][0] <= '\u9fff':
                cjk_bigrams.append(tokens[i] + tokens[i + 1])

    tokens.extend(cjk_bigrams)
    return tokens


# ----------------------------------------------------------------------
#  Memory Entry
# ----------------------------------------------------------------------
class MemoryEntry:
    """A single knowledge entry in semantic memory.

    Attributes:
        id: Unique identifier.
        content: The knowledge text.
        tags: Categorisation tags.
        confidence: Belief score in [0, 1].
        success_count: Times this entry was useful (retrieved and helped).
        fail_count: Times this entry was misleading or unhelpful.
        created_at: Unix timestamp of creation.
        last_accessed: Unix timestamp of last retrieval.
        source: Where this entry originated (``'episodic'``, ``'manual'``,
            ``'consolidated'``, etc.).
    """

    def __init__(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        confidence: float = 0.5,
        success_count: int = 0,
        fail_count: int = 0,
        created_at: Optional[float] = None,
        last_accessed: Optional[float] = None,
        source: str = "manual",
        entry_id: Optional[str] = None,
    ) -> None:
        self.id: str = entry_id or str(uuid.uuid4())
        self.content: str = content
        self.tags: List[str] = tags or []
        self.confidence: float = max(0.0, min(1.0, confidence))
        self.success_count: int = success_count
        self.fail_count: int = fail_count
        self.created_at: float = created_at or time.time()
        self.last_accessed: float = last_accessed or self.created_at
        self.source: str = source

    # ------------------------------------------------------------------
    def touch(self) -> None:
        """Update ``last_accessed`` to now."""
        self.last_accessed = time.time()

    def record_success(self) -> None:
        """Increment the success counter."""
        self.success_count += 1

    def record_failure(self) -> None:
        """Increment the failure counter."""
        self.fail_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            'id': self.id,
            'content': self.content,
            'tags': self.tags,
            'confidence': self.confidence,
            'success_count': self.success_count,
            'fail_count': self.fail_count,
            'created_at': self.created_at,
            'last_accessed': self.last_accessed,
            'source': self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Reconstruct from a dict."""
        return cls(
            content=data['content'],
            tags=data.get('tags'),
            confidence=data.get('confidence', 0.5),
            success_count=data.get('success_count', 0),
            fail_count=data.get('fail_count', 0),
            created_at=data.get('created_at'),
            last_accessed=data.get('last_accessed'),
            source=data.get('source', 'manual'),
            entry_id=data.get('id'),
        )

    def __repr__(self) -> str:
        return (
            f"MemoryEntry(id={self.id[:8]}, "
            f"confidence={self.confidence:.2f}, "
            f"tags={self.tags})"
        )


# ----------------------------------------------------------------------
#  TF-IDF Index
# ----------------------------------------------------------------------
class TFIDFIndex:
    """A pure-numpy TF-IDF vector space model.

    Supports incremental add / delete of documents and cosine-similarity
    retrieval.  The vocabulary and IDF weights are recomputed on every
    structural change (add/delete), which is efficient enough for
    hundreds to low-thousands of entries.

    Attributes:
        vocabulary: Mapping ``token → column index``.
        idf: 1-D numpy array of IDF weights (length = vocab size).
        tfidf_matrix: 2-D numpy array (n_docs × vocab_size), L2-normalised
            rows for fast cosine similarity via dot product.
    """

    def __init__(self) -> None:
        self.vocabulary: Dict[str, int] = {}
        self.idf: Optional[np.ndarray] = None
        self.tfidf_matrix: Optional[np.ndarray] = None
        # Document tokens cache (for re-indexing)
        self._doc_tokens: List[List[str]] = []

    # ------------------------------------------------------------------
    #  Building
    # ------------------------------------------------------------------
    def build(self, documents: List[List[str]]) -> None:
        """(Re)build the entire index from a list of token lists.

        Args:
            documents: Each element is a list of tokens for one document.
        """
        self._doc_tokens = [list(tokens) for tokens in documents]
        self._rebuild()

    def _rebuild(self) -> None:
        """Recompute vocabulary, IDF, and TF-IDF matrix."""
        n_docs = len(self._doc_tokens)
        if n_docs == 0:
            self.vocabulary = {}
            self.idf = None
            self.tfidf_matrix = None
            return

        # --- Build vocabulary ---
        vocab: Dict[str, int] = {}
        doc_freq: Dict[str, int] = {}  # document frequency per term

        for tokens in self._doc_tokens:
            seen = set()
            for tok in tokens:
                if tok not in vocab:
                    vocab[tok] = len(vocab)
                    doc_freq[tok] = 0
                if tok not in seen:
                    doc_freq[tok] += 1
                    seen.add(tok)

        self.vocabulary = vocab
        vocab_size = len(vocab)
        if vocab_size == 0:
            self.idf = None
            self.tfidf_matrix = None
            return

        # --- IDF (smoothed) ---
        self.idf = np.zeros(vocab_size, dtype=np.float64)
        for tok, idx in vocab.items():
            df = doc_freq[tok]
            # Smoothed IDF: log((1 + N) / (1 + df)) + 1
            self.idf[idx] = math.log((1 + n_docs) / (1 + df)) + 1.0

        # --- TF-IDF matrix ---
        self.tfidf_matrix = np.zeros((n_docs, vocab_size), dtype=np.float64)
        for i, tokens in enumerate(self._doc_tokens):
            if not tokens:
                continue
            # Term frequency (raw count normalised by document length)
            tf_counts: Dict[int, int] = {}
            for tok in tokens:
                col = vocab.get(tok)
                if col is not None:
                    tf_counts[col] = tf_counts.get(col, 0) + 1
            doc_len = len(tokens)
            for col, count in tf_counts.items():
                self.tfidf_matrix[i, col] = (count / doc_len) * self.idf[col]

        # --- L2-normalise rows (so dot product = cosine similarity) ---
        norms = np.linalg.norm(self.tfidf_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.tfidf_matrix = self.tfidf_matrix / norms

    # ------------------------------------------------------------------
    #  Retrieval
    # ------------------------------------------------------------------
    def search(
        self,
        query_tokens: List[str],
        top_k: int = 5,
    ) -> List[Tuple[int, float]]:
        """Find the most similar documents to a query.

        Args:
            query_tokens: Pre-tokenised query.
            top_k: Maximum number of results.

        Returns:
            List of ``(doc_index, similarity_score)`` tuples, sorted by
            score descending.
        """
        if self.tfidf_matrix is None or self.idf is None or not query_tokens:
            return []

        # Build query TF-IDF vector
        vocab_size = len(self.vocabulary)
        query_vec = np.zeros(vocab_size, dtype=np.float64)

        tf_counts: Dict[int, int] = {}
        for tok in query_tokens:
            col = self.vocabulary.get(tok)
            if col is not None:
                tf_counts[col] = tf_counts.get(col, 0) + 1

        if not tf_counts:
            return []

        doc_len = len(query_tokens)
        for col, count in tf_counts.items():
            query_vec[col] = (count / doc_len) * self.idf[col]

        # Normalise query vector
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            query_vec /= norm

        # Cosine similarity = dot product (rows are already normalised)
        similarities = self.tfidf_matrix @ query_vec

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = [
            (int(idx), float(similarities[idx]))
            for idx in top_indices
            if similarities[idx] > 0
        ]
        return results


# ----------------------------------------------------------------------
#  Inverted Index
# ----------------------------------------------------------------------
class InvertedIndex:
    """A simple keyword → document-indices inverted index.

    Allows O(1) lookup of all entries containing a given keyword.
    """

    def __init__(self) -> None:
        self._index: Dict[str, set] = {}

    def build(self, doc_tokens: List[List[str]]) -> None:
        """Build the index from a list of token lists."""
        self._index.clear()
        for i, tokens in enumerate(doc_tokens):
            for tok in set(tokens):
                if tok not in self._index:
                    self._index[tok] = set()
                self._index[tok].add(i)

    def lookup(self, keyword: str) -> set:
        """Return the set of document indices containing *keyword*."""
        return self._index.get(keyword.lower(), set())

    def lookup_any(self, keywords: List[str]) -> set:
        """Return document indices containing *any* of the keywords."""
        result: set = set()
        for kw in keywords:
            result |= self.lookup(kw)
        return result

    def lookup_all(self, keywords: List[str]) -> set:
        """Return document indices containing *all* keywords."""
        if not keywords:
            return set()
        result = self.lookup(keywords[0])
        for kw in keywords[1:]:
            result &= self.lookup(kw)
        return result


# ----------------------------------------------------------------------
#  SemanticMemory
# ----------------------------------------------------------------------
class SemanticMemory:
    """Semantic Memory — cross-session knowledge base with TF-IDF retrieval.

    Combines a :class:`TFIDFIndex` for semantic similarity search with an
    :class:`InvertedIndex` for exact keyword matching.  Supports CRUD
    operations and JSON persistence.

    Attributes:
        storage_path: Path to the JSON persistence file.
        entries: List of :class:`MemoryEntry` objects.
        tfidf: The TF-IDF vector space index.
        inverted: The keyword inverted index.
    """

    def __init__(
        self,
        storage_path: Optional[str] = None,
        max_entries: int = 2000,
    ) -> None:
        self.storage_path = storage_path
        self.max_entries = max_entries
        self.entries: List[MemoryEntry] = []
        self.tfidf = TFIDFIndex()
        self.inverted = InvertedIndex()

        if storage_path:
            self._load()
        self._rebuild_indices()

    # ------------------------------------------------------------------
    #  CRUD — Create
    # ------------------------------------------------------------------
    def add(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        confidence: float = 0.5,
        source: str = "manual",
        **kwargs: Any,
    ) -> MemoryEntry:
        """Add a new knowledge entry.

        Args:
            content: The knowledge text.
            tags: Optional categorisation tags.
            confidence: Initial confidence score [0, 1].
            source: Origin label (``'manual'``, ``'episodic'``,
                ``'consolidated'``, etc.).
            **kwargs: Additional fields (``success_count``,
                ``fail_count``, etc.).

        Returns:
            The created :class:`MemoryEntry`.
        """
        entry = MemoryEntry(
            content=content,
            tags=tags,
            confidence=confidence,
            source=source,
            **kwargs,
        )
        self.entries.append(entry)

        # Enforce capacity
        if len(self.entries) > self.max_entries:
            self._evict()

        self._rebuild_indices()
        self._save()
        return entry

    # ------------------------------------------------------------------
    #  CRUD — Retrieve
    # ------------------------------------------------------------------
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_confidence: float = 0.0,
        tag_filter: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve the most relevant entries for a query.

        Combines TF-IDF cosine similarity with inverted-index keyword
        matching.  Results are ranked by a blended score and filtered by
        confidence and tags.

        Args:
            query: Natural-language query string.
            top_k: Maximum number of results.
            min_confidence: Exclude entries below this confidence.
            tag_filter: If provided, only return entries with at least
                one matching tag.

        Returns:
            List of entry dicts (with an added ``score`` field), sorted
            by relevance descending.
        """
        if not self.entries:
            return []

        query_tokens = _tokenize(query)

        # --- TF-IDF search ---
        tfidf_results = self.tfidf.search(query_tokens, top_k=top_k * 2)
        tfidf_scores: Dict[int, float] = {
            idx: score for idx, score in tfidf_results
        }

        # --- Inverted index boost ---
        keyword_hits = self.inverted.lookup_any(query_tokens)

        # --- Blend and rank ---
        scored: List[Tuple[float, int]] = []
        for i, entry in enumerate(self.entries):
            # Filter by confidence
            if entry.confidence < min_confidence:
                continue
            # Filter by tags
            if tag_filter:
                if not any(t in entry.tags for t in tag_filter):
                    continue

            tfidf_score = tfidf_scores.get(i, 0.0)
            keyword_boost = 0.15 if i in keyword_hits else 0.0
            # Blend: 70 % TF-IDF + 15 % keyword + 15 % confidence
            final_score = (
                tfidf_score * 0.70
                + keyword_boost
                + entry.confidence * 0.15
            )
            if final_score > 0:
                scored.append((final_score, i))

        scored.sort(key=lambda x: x[0], reverse=True)

        results: List[Dict[str, Any]] = []
        for score, idx in scored[:top_k]:
            entry = self.entries[idx]
            entry.touch()  # Update last_accessed
            d = entry.to_dict()
            d['score'] = round(score, 4)
            results.append(d)

        # Persist the updated last_accessed timestamps
        if results:
            self._save()

        return results

    def get_by_id(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieve a single entry by ID."""
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    # ------------------------------------------------------------------
    #  CRUD — Update
    # ------------------------------------------------------------------
    def record_success(self, entry_id: str) -> None:
        """Mark an entry as useful (increment success_count)."""
        entry = self.get_by_id(entry_id)
        if entry:
            entry.record_success()
            self._save()

    def record_failure(self, entry_id: str) -> None:
        """Mark an entry as unhelpful (increment fail_count)."""
        entry = self.get_by_id(entry_id)
        if entry:
            entry.record_failure()
            self._save()

    def update_confidence(self, entry_id: str, confidence: float) -> None:
        """Directly set an entry's confidence."""
        entry = self.get_by_id(entry_id)
        if entry:
            entry.confidence = max(0.0, min(1.0, confidence))
            self._save()

    # ------------------------------------------------------------------
    #  CRUD — Delete
    # ------------------------------------------------------------------
    def delete(self, entry_id: str) -> bool:
        """Delete an entry by ID.

        Args:
            entry_id: The ID of the entry to remove.

        Returns:
            ``True`` if the entry was found and deleted, ``False`` otherwise.
        """
        for i, entry in enumerate(self.entries):
            if entry.id == entry_id:
                self.entries.pop(i)
                self._rebuild_indices()
                self._save()
                return True
        return False

    def delete_by_tag(self, tag: str) -> int:
        """Delete all entries with a given tag.

        Returns:
            Number of entries deleted.
        """
        before = len(self.entries)
        self.entries = [e for e in self.entries if tag not in e.tags]
        deleted = before - len(self.entries)
        if deleted > 0:
            self._rebuild_indices()
            self._save()
        return deleted

    # ------------------------------------------------------------------
    #  Index management
    # ------------------------------------------------------------------
    def _rebuild_indices(self) -> None:
        """Rebuild the TF-IDF and inverted indices from current entries."""
        doc_tokens = [_tokenize(e.content) for e in self.entries]
        self.tfidf.build(doc_tokens)
        self.inverted.build(doc_tokens)

    def _evict(self) -> None:
        """Remove lowest-confidence entries to stay within capacity."""
        excess = len(self.entries) - self.max_entries
        if excess <= 0:
            return
        # Sort by confidence ascending, remove the lowest
        self.entries.sort(key=lambda e: e.confidence)
        self.entries = self.entries[excess:]

    # ------------------------------------------------------------------
    #  Persistence
    # ------------------------------------------------------------------
    def _save(self) -> None:
        """Persist entries to the JSON storage file."""
        if not self.storage_path:
            return
        os.makedirs(os.path.dirname(self.storage_path) or '.', exist_ok=True)
        data = {
            'entries': [e.to_dict() for e in self.entries],
        }
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        """Load entries from the JSON storage file."""
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.entries = [
                MemoryEntry.from_dict(d) for d in data.get('entries', [])
            ]
        except (json.JSONDecodeError, KeyError):
            self.entries = []

    def save(self) -> None:
        """Public save method."""
        self._save()

    # ------------------------------------------------------------------
    #  Utilities
    # ------------------------------------------------------------------
    def get_all_entries(self) -> List[MemoryEntry]:
        """Return a copy of all entries."""
        return list(self.entries)

    def get_entries_by_tag(self, tag: str) -> List[MemoryEntry]:
        """Return all entries with the given tag."""
        return [e for e in self.entries if tag in e.tags]

    def get_vocabulary_size(self) -> int:
        """Return the number of unique tokens in the index."""
        return len(self.vocabulary) if hasattr(self, 'vocabulary') else len(self.tfidf.vocabulary)

    def __len__(self) -> int:
        return len(self.entries)

    def __repr__(self) -> str:
        return (
            f"SemanticMemory(entries={len(self.entries)}, "
            f"vocab={len(self.tfidf.vocabulary)})"
        )
