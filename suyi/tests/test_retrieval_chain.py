"""Tests for Retrieval Chain — 四级回退检索器链。"""

import pytest

from suyi.memory.retrieval_chain import (
    MemoryItem,
    BaseRetriever,
    HybridRetriever,
    DenseRetriever,
    LexicalRetriever,
    SQLiteRetriever,
    RetrievalChain,
)


class TestMemoryItem:
    """MemoryItem 数据结构测试。"""

    def test_creation(self):
        item = MemoryItem(
            content="Test content",
            score=0.95,
            layer="semantic",
            source="hybrid",
        )
        assert item.content == "Test content"
        assert item.score == 0.95
        assert item.id  # 自动生成 ID

    def test_to_dict(self):
        item = MemoryItem(content="Test", score=0.5)
        d = item.to_dict()
        assert d["content"] == "Test"
        assert d["score"] == 0.5


class TestHybridRetriever:
    """HybridRetriever 混合检索器测试。"""

    def test_retrieve(self):
        docs = [
            "Python is a programming language",
            "Rust focuses on memory safety",
            "JavaScript is dynamic typing",
        ]
        retriever = HybridRetriever(documents=docs, layer="semantic")
        results = retriever.retrieve("Python programming", top_k=2)
        assert len(results) > 0
        assert results[0].source == "hybrid"
        assert results[0].layer == "semantic"
        assert results[0].score > 0

    def test_add_document(self):
        retriever = HybridRetriever(layer="semantic")
        retriever.add_document("Python is great")
        retriever.add_document("Rust is safe")
        results = retriever.retrieve("Python")
        assert len(results) > 0

    def test_empty_retrieve(self):
        retriever = HybridRetriever()
        assert retriever.retrieve("anything") == []


class TestDenseRetriever:
    """DenseRetriever 密集检索器测试。"""

    def test_retrieve(self):
        docs = [
            "Python programming language tutorial",
            "Rust memory safety guide",
        ]
        retriever = DenseRetriever(documents=docs, layer="semantic")
        results = retriever.retrieve("Python programming", top_k=2)
        assert len(results) > 0
        assert results[0].source == "dense"

    def test_empty_retrieve(self):
        retriever = DenseRetriever()
        assert retriever.retrieve("anything") == []


class TestLexicalRetriever:
    """LexicalRetriever 词汇检索器测试。"""

    def test_retrieve(self):
        docs = [
            "Python is a programming language",
            "Rust focuses on memory safety",
        ]
        retriever = LexicalRetriever(documents=docs, layer="episodic")
        results = retriever.retrieve("Python programming", top_k=2)
        assert len(results) > 0
        assert results[0].source == "lexical"

    def test_empty_retrieve(self):
        retriever = LexicalRetriever()
        assert retriever.retrieve("anything") == []


class TestSQLiteRetriever:
    """SQLiteRetriever 基础检索器测试。"""

    def test_retrieve(self):
        docs = [
            "Python is a programming language",
            "Rust focuses on memory safety",
        ]
        retriever = SQLiteRetriever(documents=docs, layer="episodic")
        results = retriever.retrieve("Python programming", top_k=2)
        assert len(results) > 0
        assert results[0].source == "sqlite"

    def test_empty_retrieve(self):
        retriever = SQLiteRetriever()
        assert retriever.retrieve("anything") == []


class TestRetrievalChain:
    """RetrievalChain 回退检索链测试。"""

    def test_first_retriever_returns(self):
        """第一个检索器返回非空即返回。"""
        docs = ["Python programming language"]
        chain = RetrievalChain([
            HybridRetriever(docs, "semantic"),
            DenseRetriever(docs, "semantic"),
            LexicalRetriever(docs, "episodic"),
            SQLiteRetriever(docs, "episodic"),
        ])
        results = chain.retrieve("Python programming")
        assert len(results) > 0
        assert chain.last_fallback_log["fallback_level"] == 0
        assert chain.last_fallback_log["retriever"] == "hybrid"

    def test_fallback_to_second(self):
        """第一个检索器为空时回退到第二个。"""
        chain = RetrievalChain([
            HybridRetriever([], "semantic"),  # 空文档
            LexicalRetriever(["Python programming"], "episodic"),
        ])
        results = chain.retrieve("Python")
        assert len(results) > 0
        assert chain.last_fallback_log["fallback_level"] == 1
        assert chain.last_fallback_log["retriever"] == "lexical"

    def test_all_empty(self):
        """所有检索器都返回空。"""
        chain = RetrievalChain([
            HybridRetriever([], "semantic"),
            LexicalRetriever([], "episodic"),
        ])
        results = chain.retrieve("anything")
        assert results == []
        assert chain.last_fallback_log["fallback_level"] == -1
        assert chain.last_fallback_log["retriever"] == "none"

    def test_fallback_log(self):
        """回退日志记录。"""
        docs = ["Python is great"]
        chain = RetrievalChain([
            HybridRetriever(docs, "semantic"),
            LexicalRetriever(docs, "episodic"),
        ])
        chain.retrieve("Python")
        log = chain.last_fallback_log
        assert log is not None
        assert "query" in log
        assert "fallback_level" in log
        assert "result_count" in log
        assert "attempts" in log

    def test_get_logs(self):
        """获取历史日志。"""
        chain = RetrievalChain([
            LexicalRetriever(["Python"], "episodic"),
        ])
        chain.retrieve("Python")
        chain.retrieve("Rust")
        logs = chain.get_logs()
        assert len(logs) == 2

    def test_clear_logs(self):
        """清除日志。"""
        chain = RetrievalChain([
            LexicalRetriever(["test"], "episodic"),
        ])
        chain.retrieve("test")
        chain.clear_logs()
        assert len(chain.fallback_logs) == 0
        assert chain.last_fallback_log is None

    def test_add_retriever(self):
        """添加检索器。"""
        chain = RetrievalChain([
            LexicalRetriever(["test"], "episodic"),
        ])
        chain.add_retriever(SQLiteRetriever(["test2"], "episodic"))
        assert len(chain.retrievers) == 2

    def test_empty_chain_raises(self):
        """空链抛出异常。"""
        with pytest.raises(ValueError):
            RetrievalChain([])

    def test_repr(self):
        """repr 方法。"""
        chain = RetrievalChain([
            HybridRetriever(["test"], "semantic"),
        ])
        assert "RetrievalChain" in repr(chain)
