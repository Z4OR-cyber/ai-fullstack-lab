"""Tests for Vector Store (Phase 11)."""

from __future__ import annotations

import numpy as np
import pytest

from suyi.vectorstore import (
    VectorStoreBase,
    InMemoryVectorStore,
    VectorRecord,
    SearchResult,
    VectorStoreRetrieverAdapter,
    RAGVectorStoreAdapter,
    default_embed,
)


# ── VectorRecord tests ────────────────────────────────────────

class TestVectorRecord:
    def test_creation(self):
        v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        rec = VectorRecord(id="r1", vector=v, content="hello")
        assert rec.id == "r1"
        assert rec.vector.shape == (3,)
        assert rec.content == "hello"

    def test_auto_convert_list(self):
        rec = VectorRecord(id="r1", vector=[1.0, 2.0])
        assert isinstance(rec.vector, np.ndarray)
        assert rec.vector.dtype == np.float32

    def test_to_dict(self):
        rec = VectorRecord(id="r1", vector=[1.0, 2.0], content="hi", metadata={"k": "v"})
        d = rec.to_dict()
        assert d["id"] == "r1"
        assert d["content"] == "hi"
        assert d["vector"] == [1.0, 2.0]
        assert d["metadata"] == {"k": "v"}

    def test_from_dict(self):
        d = {"id": "r1", "vector": [1.0, 2.0], "content": "hi", "metadata": {"k": "v"}}
        rec = VectorRecord.from_dict(d)
        assert rec.id == "r1"
        assert np.array_equal(rec.vector, [1.0, 2.0])
        assert rec.content == "hi"

    def test_repr(self):
        rec = VectorRecord(id="r1", vector=[1.0, 2.0], content="hello world")
        r = repr(rec)
        assert "r1" in r
        assert "hello" in r


# ── SearchResult tests ────────────────────────────────────────

class TestSearchResult:
    def test_creation(self):
        rec = VectorRecord(id="r1", vector=[1.0, 2.0])
        sr = SearchResult(record=rec, score=0.95)
        assert sr.record.id == "r1"
        assert sr.score == 0.95

    def test_to_dict(self):
        rec = VectorRecord(id="r1", vector=[1.0, 2.0], content="hi")
        sr = SearchResult(record=rec, score=0.8)
        d = sr.to_dict()
        assert d["id"] == "r1"
        assert d["score"] == 0.8
        assert d["content"] == "hi"

    def test_repr(self):
        rec = VectorRecord(id="r1", vector=[1.0])
        sr = SearchResult(record=rec, score=0.123)
        r = repr(sr)
        assert "r1" in r
        assert "0.123" in r


# ── InMemoryVectorStore tests ─────────────────────────────────

class TestInMemoryVectorStore:
    def test_init_defaults(self):
        store = InMemoryVectorStore()
        assert store.dim == 0
        assert store.metric == "cosine"
        assert store.count() == 0
        assert len(store) == 0

    def test_init_with_dim(self):
        store = InMemoryVectorStore(dim=64)
        assert store.dim == 64

    def test_init_invalid_metric(self):
        with pytest.raises(ValueError):
            InMemoryVectorStore(metric="invalid")

    def test_add_single_vector(self):
        store = InMemoryVectorStore(dim=3)
        ids = store.add(np.array([1.0, 0.0, 0.0]))
        assert len(ids) == 1
        assert store.count() == 1

    def test_add_batch_vectors(self):
        store = InMemoryVectorStore(dim=3)
        vecs = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
        ids = store.add(vecs)
        assert len(ids) == 3
        assert store.count() == 3

    def test_add_list_of_vectors(self):
        store = InMemoryVectorStore(dim=3)
        vecs = [np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])]
        ids = store.add(vecs)
        assert len(ids) == 2

    def test_add_with_ids(self):
        store = InMemoryVectorStore(dim=3)
        ids = store.add(
            np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
            ids=["a", "b"],
        )
        assert ids == ["a", "b"]

    def test_add_with_contents(self):
        store = InMemoryVectorStore(dim=3)
        store.add(
            np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
            ids=["a", "b"],
            contents=["doc A", "doc B"],
        )
        assert store.get("a").content == "doc A"
        assert store.get("b").content == "doc B"

    def test_add_with_metadata(self):
        store = InMemoryVectorStore(dim=3)
        store.add(
            np.array([1.0, 0.0, 0.0]),
            ids=["a"],
            metadata=[{"source": "test"}],
        )
        assert store.get("a").metadata["source"] == "test"

    def test_add_duplicate_id_raises(self):
        store = InMemoryVectorStore(dim=3)
        store.add(np.array([1.0, 0.0, 0.0]), ids=["a"])
        with pytest.raises(ValueError, match="Duplicate id"):
            store.add(np.array([0.0, 1.0, 0.0]), ids=["a"])

    def test_add_dimension_mismatch(self):
        store = InMemoryVectorStore(dim=3)
        with pytest.raises(ValueError, match="dimension mismatch"):
            store.add(np.array([1.0, 0.0]))

    def test_add_auto_dim_detection(self):
        store = InMemoryVectorStore()
        store.add(np.array([1.0, 2.0, 3.0, 4.0]))
        assert store.dim == 4

    def test_add_length_mismatch_ids(self):
        store = InMemoryVectorStore(dim=3)
        with pytest.raises(ValueError, match="Length mismatch"):
            store.add(np.array([[1.0, 0.0, 0.0]]), ids=["a", "b"])

    def test_add_wrong_ndim(self):
        store = InMemoryVectorStore(dim=3)
        with pytest.raises(ValueError, match="Expected 1-D or 2-D"):
            store.add(np.zeros((2, 2, 2)))

    def test_search_empty_store(self):
        store = InMemoryVectorStore(dim=3)
        results = store.search(np.array([1.0, 0.0, 0.0]))
        assert results == []

    def test_search_cosine_exact_match(self):
        store = InMemoryVectorStore(dim=3)
        store.add(
            np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
            ids=["a", "b", "c"],
        )
        results = store.search(np.array([1.0, 0.0, 0.0]), top_k=1)
        assert len(results) == 1
        assert results[0].record.id == "a"
        assert results[0].score == pytest.approx(1.0, abs=1e-5)

    def test_search_cosine_partial_match(self):
        store = InMemoryVectorStore(dim=2)
        store.add(
            np.array([[1.0, 0.0], [1.0, 1.0]]),
            ids=["a", "b"],
        )
        results = store.search(np.array([1.0, 0.0]), top_k=2)
        assert results[0].record.id == "a"
        assert results[0].score > results[1].score

    def test_search_top_k(self):
        store = InMemoryVectorStore(dim=3)
        store.add(
            np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
            ids=["a", "b", "c"],
        )
        results = store.search(np.array([1.0, 0.0, 0.0]), top_k=2)
        assert len(results) == 2

    def test_search_top_k_more_than_count(self):
        store = InMemoryVectorStore(dim=3)
        store.add(np.array([1.0, 0.0, 0.0]), ids=["a"])
        results = store.search(np.array([1.0, 0.0, 0.0]), top_k=10)
        assert len(results) == 1

    def test_search_sorted_descending(self):
        store = InMemoryVectorStore(dim=3)
        store.add(
            np.array([[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.0, 0.0, 1.0]]),
            ids=["a", "b", "c"],
        )
        results = store.search(np.array([1.0, 0.0, 0.0]), top_k=3)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_with_filter(self):
        store = InMemoryVectorStore(dim=3)
        store.add(
            np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
            ids=["a", "b"],
            metadata=[{"keep": True}, {"keep": False}],
        )
        results = store.search(
            np.array([1.0, 0.0, 0.0]),
            top_k=5,
            filter_fn=lambda rec: rec.metadata.get("keep", False),
        )
        assert len(results) == 1
        assert results[0].record.id == "a"

    def test_search_l2_metric(self):
        store = InMemoryVectorStore(dim=2, metric="l2")
        store.add(
            np.array([[1.0, 0.0], [5.0, 5.0]]),
            ids=["close", "far"],
        )
        results = store.search(np.array([1.0, 0.0]), top_k=2)
        assert results[0].record.id == "close"
        assert results[0].score > results[1].score

    def test_search_dimension_mismatch(self):
        store = InMemoryVectorStore(dim=3)
        store.add(np.array([1.0, 0.0, 0.0]))
        with pytest.raises(ValueError, match="Query dimension"):
            store.search(np.array([1.0, 0.0]))

    def test_delete_single(self):
        store = InMemoryVectorStore(dim=3)
        store.add(
            np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
            ids=["a", "b"],
        )
        deleted = store.delete("a")
        assert deleted == 1
        assert store.count() == 1
        assert store.get("a") is None

    def test_delete_multiple(self):
        store = InMemoryVectorStore(dim=3)
        store.add(
            np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
            ids=["a", "b", "c"],
        )
        deleted = store.delete(["a", "b"])
        assert deleted == 2
        assert store.count() == 1

    def test_delete_nonexistent(self):
        store = InMemoryVectorStore(dim=3)
        store.add(np.array([1.0, 0.0, 0.0]), ids=["a"])
        deleted = store.delete("nonexistent")
        assert deleted == 0

    def test_clear(self):
        store = InMemoryVectorStore(dim=3)
        store.add(
            np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
            ids=["a", "b"],
        )
        store.clear()
        assert store.count() == 0
        assert store.get("a") is None

    def test_get(self):
        store = InMemoryVectorStore(dim=3)
        store.add(np.array([1.0, 0.0, 0.0]), ids=["a"], contents=["hello"])
        rec = store.get("a")
        assert rec is not None
        assert rec.content == "hello"

    def test_get_nonexistent(self):
        store = InMemoryVectorStore(dim=3)
        assert store.get("nonexistent") is None

    def test_get_all(self):
        store = InMemoryVectorStore(dim=3)
        store.add(
            np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
            ids=["a", "b"],
        )
        all_records = store.get_all()
        assert len(all_records) == 2

    def test_contains(self):
        store = InMemoryVectorStore(dim=3)
        store.add(np.array([1.0, 0.0, 0.0]), ids=["a"])
        assert "a" in store
        assert "b" not in store

    def test_stats(self):
        store = InMemoryVectorStore(dim=64, metric="cosine")
        store.add(np.random.randn(10, 64).astype(np.float32))
        s = store.stats()
        assert s["dim"] == 64
        assert s["metric"] == "cosine"
        assert s["count"] == 10
        assert s["matrix_bytes"] > 0

    def test_search_after_delete_rebuilds(self):
        store = InMemoryVectorStore(dim=3)
        store.add(
            np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
            ids=["a", "b", "c"],
        )
        store.delete("a")
        results = store.search(np.array([1.0, 0.0, 0.0]), top_k=5)
        # Should only find b and c
        ids = [r.record.id for r in results]
        assert "a" not in ids

    def test_top_k_zero(self):
        store = InMemoryVectorStore(dim=3)
        store.add(np.array([1.0, 0.0, 0.0]))
        results = store.search(np.array([1.0, 0.0, 0.0]), top_k=0)
        assert results == []

    def test_large_batch(self):
        store = InMemoryVectorStore(dim=128)
        vecs = np.random.randn(100, 128).astype(np.float32)
        ids = store.add(vecs)
        assert store.count() == 100

        query = vecs[0]
        results = store.search(query, top_k=5)
        assert len(results) == 5
        # The first result should be the exact match
        assert results[0].record.id == ids[0]
        assert results[0].score == pytest.approx(1.0, abs=1e-5)

    def test_add_update_via_delete_and_readd(self):
        store = InMemoryVectorStore(dim=3)
        store.add(np.array([1.0, 0.0, 0.0]), ids=["a"])
        store.delete("a")
        store.add(np.array([0.0, 1.0, 0.0]), ids=["a"])
        assert store.get("a").vector[1] == 1.0


# ── Adapter tests ─────────────────────────────────────────────

class TestVectorStoreRetrieverAdapter:
    def test_retrieve_returns_memory_items(self):
        store = InMemoryVectorStore(dim=4)
        store.add(
            np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]),
            ids=["a", "b"],
            contents=["doc A", "doc B"],
        )
        adapter = VectorStoreRetrieverAdapter(store, name="test")
        results = adapter.retrieve("doc A", top_k=2)

        from suyi.memory import MemoryItem
        assert len(results) > 0
        assert all(isinstance(r, MemoryItem) for r in results)
        assert results[0].source == "test"
        assert results[0].layer == "semantic"

    def test_retrieve_empty_store(self):
        store = InMemoryVectorStore(dim=4)
        adapter = VectorStoreRetrieverAdapter(store)
        results = adapter.retrieve("query", top_k=5)
        assert results == []

    def test_retrieve_with_embed_fn(self):
        store = InMemoryVectorStore(dim=4)
        store.add(
            np.array([[1.0, 0.0, 0.0, 0.0]]),
            ids=["a"],
            contents=["hello"],
        )

        def embed_fn(text: str) -> np.ndarray:
            return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)

        adapter = VectorStoreRetrieverAdapter(store, embed_fn=embed_fn)
        results = adapter.retrieve("hello", top_k=1)
        assert len(results) == 1
        assert results[0].content == "hello"

    def test_as_retriever(self):
        store = InMemoryVectorStore(dim=4)
        store.add(np.array([1.0, 0.0, 0.0, 0.0]), ids=["a"], contents=["doc"])
        adapter = VectorStoreRetrieverAdapter(store)
        retriever = adapter.as_retriever()

        from suyi.memory import BaseRetriever
        assert isinstance(retriever, BaseRetriever)

        results = retriever.retrieve("doc", top_k=1)
        assert len(results) == 1

    def test_retrieve_with_retrieval_chain(self):
        store = InMemoryVectorStore(dim=4)
        store.add(
            np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]),
            ids=["a", "b"],
            contents=["Python tutorial", "Java tutorial"],
        )
        adapter = VectorStoreRetrieverAdapter(store, name="vector")

        from suyi.memory import RetrievalChain
        chain = RetrievalChain([adapter.as_retriever()])
        results = chain.retrieve("Python tutorial", top_k=2)
        assert len(results) > 0
        assert chain.last_fallback_log["retriever"] == "vector"


class TestRAGVectorStoreAdapter:
    def test_add_documents(self):
        adapter = RAGVectorStoreAdapter()
        docs = ["hello world", "foo bar"]
        ids = adapter.add_documents(docs)
        assert len(ids) == 2
        assert adapter.count() == 2

    def test_add_documents_with_ids(self):
        adapter = RAGVectorStoreAdapter()
        ids = adapter.add_documents(["doc1", "doc2"], ids=["x", "y"])
        assert ids == ["x", "y"]

    def test_search(self):
        adapter = RAGVectorStoreAdapter()

        def embed(text: str) -> np.ndarray:
            v = np.zeros(4, dtype=np.float32)
            for i, c in enumerate(text):
                v[i % 4] += ord(c)
            n = np.linalg.norm(v)
            return v / n if n > 0 else v

        adapter.embed_fn = embed
        adapter.add_documents(["Python is great", "Java is okay"], ids=["a", "b"])
        results = adapter.search("Python is great", top_k=2)
        assert len(results) > 0
        assert results[0]["id"] in ("a", "b")

    def test_search_with_embed_fn(self):
        store = InMemoryVectorStore(dim=3)
        adapter = RAGVectorStoreAdapter(store=store)
        adapter.embed_fn = lambda t: np.array([1.0, 0.0, 0.0], dtype=np.float32)
        adapter.add_documents(["test doc"], ids=["x"])
        results = adapter.search("query", top_k=1)
        assert len(results) == 1
        assert results[0]["id"] == "x"

    def test_clear(self):
        adapter = RAGVectorStoreAdapter()
        adapter.add_documents(["a", "b"])
        adapter.clear()
        assert adapter.count() == 0

    def test_count(self):
        adapter = RAGVectorStoreAdapter()
        adapter.add_documents(["a", "b", "c"])
        assert adapter.count() == 3

    def test_add_with_metadata(self):
        adapter = RAGVectorStoreAdapter()
        adapter.add_documents(
            ["doc1", "doc2"],
            metadata=[{"page": 1}, {"page": 2}],
        )
        assert adapter.count() == 2


class TestDefaultEmbed:
    def test_deterministic(self):
        from suyi.vectorstore.adapter import _default_embed
        v1 = _default_embed("hello", dim=32)
        v2 = _default_embed("hello", dim=32)
        assert np.array_equal(v1, v2)

    def test_different_inputs_different_vectors(self):
        from suyi.vectorstore.adapter import _default_embed
        v1 = _default_embed("hello", dim=32)
        v2 = _default_embed("world", dim=32)
        assert not np.array_equal(v1, v2)

    def test_normalized(self):
        from suyi.vectorstore.adapter import _default_embed
        v = _default_embed("test text", dim=32)
        norm = np.linalg.norm(v)
        assert norm == pytest.approx(1.0, abs=1e-5)

    def test_module_level_default_embed(self):
        v = default_embed("hello", dim=32)
        assert v.shape == (32,)


class TestVectorStoreBase:
    def test_is_abstract(self):
        with pytest.raises(TypeError):
            VectorStoreBase()
