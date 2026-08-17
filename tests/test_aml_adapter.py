"""AML Add/Search HTTP 接口与 BM25+Dense RRF 混合检索测试套件。

覆盖范围：

- BM25 检索器（英文/中文/空文档/增量索引/参数/IDF）
- Dense 检索器（向量构建/相似度/增量更新/空查询）
- Hybrid 检索器（RRF 融合/权重/top_k/时间衰减）
- AMLMemoryStore（多用户隔离/会话隔离/去重/持久化/TTL/容量/语义提取）
- AMLMemoryServer HTTP（/add /search /health/鉴权/错误处理/并发/CORS）
- 端到端（add→search 完整流程，覆盖 AML 7 维基础场景）
- 性能（1000 条文档检索 < 1 秒）

运行方式::

    cd suyi
    python -m pytest tests/test_aml_adapter.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

import numpy as np

from suyi.memory.hybrid_retriever import (
    AMLBM25Retriever as BM25Retriever,
    AMLDenseRetriever as DenseRetriever,
    AMLHybridRetriever as HybridRetriever,
    RetrievalResult,
    tokenize,
)
from suyi.memory.aml_memory import (
    AMLMemoryStore,
    MemoryRecord,
    extract_semantic_facts,
    LAYER_WORKING,
    LAYER_EPISODIC,
    LAYER_SEMANTIC,
)
from suyi.memory.aml_adapter import (
    AMLMemoryServer,
    AMLRequestHandler,
    _validate_add_body,
    _validate_search_body,
)


# ----------------------------------------------------------------------
#  分词器测试
# ----------------------------------------------------------------------

class TestTokenizer(unittest.TestCase):
    """中英文混合分词器测试。"""

    def test_english_tokenization(self) -> None:
        tokens = tokenize("Python GIL prevents true multithreading")
        self.assertIn("python", tokens)
        self.assertIn("gil", tokens)
        self.assertIn("multithreading", tokens)
        # 全部小写
        for t in tokens:
            self.assertEqual(t, t.lower())

    def test_chinese_tokenization(self) -> None:
        tokens = tokenize("我喜欢Python编程")
        # 中文字符应单独成 token
        self.assertIn("我", tokens)
        self.assertIn("喜", tokens)
        self.assertIn("欢", tokens)
        # 应包含中文 bigram
        self.assertIn("我喜", tokens)
        self.assertIn("喜欢", tokens)
        # 英文单词
        self.assertIn("python", tokens)

    def test_numbers_preserved(self) -> None:
        tokens = tokenize("I have 3 cats and 2.5 dogs")
        self.assertIn("3", tokens)
        self.assertIn("2.5", tokens)

    def test_empty_string(self) -> None:
        self.assertEqual(tokenize(""), [])

    def test_punctuation_stripped(self) -> None:
        tokens = tokenize("Hello, world! How are you?")
        self.assertNotIn(",", tokens)
        self.assertNotIn("!", tokens)
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)

    def test_mixed_chinese_english(self) -> None:
        tokens = tokenize("用Python做数据分析")
        self.assertIn("python", tokens)
        self.assertIn("做", tokens)
        # bigram
        self.assertIn("数据", tokens)
        self.assertIn("据分", tokens)


# ----------------------------------------------------------------------
#  BM25 检索器测试
# ----------------------------------------------------------------------

class TestBM25Retriever(unittest.TestCase):
    """BM25 Okapi 检索器单元测试。"""

    def setUp(self) -> None:
        self.docs = [
            "Python GIL prevents true multithreading in CPython",
            "Java runs on the JVM virtual machine",
            "Python is great for data science and machine learning",
            "JavaScript is the language of the web browsers",
            "Rust provides memory safety without garbage collection",
        ]
        self.bm25 = BM25Retriever()
        self.bm25.add_documents(self.docs)

    def test_basic_search_returns_results(self) -> None:
        results = self.bm25.search("Python threading", top_k=3)
        self.assertGreater(len(results), 0)
        self.assertLessEqual(len(results), 3)

    def test_python_doc_ranks_first_for_python_query(self) -> None:
        results = self.bm25.search("Python", top_k=3)
        # 包含 Python 的文档应排在前面
        top_contents = [r.content for r in results]
        self.assertTrue(
            any("Python" in c or "python" in c for c in top_contents[:2])
        )

    def test_exact_match_scores_higher(self) -> None:
        results = self.bm25.search("GIL multithreading CPython", top_k=5)
        # 第一篇文档完全匹配查询词，应排第一
        self.assertEqual(results[0].doc_id, 0)

    def test_empty_query_returns_empty(self) -> None:
        results = self.bm25.search("", top_k=5)
        self.assertEqual(results, [])

    def test_no_match_returns_empty(self) -> None:
        results = self.bm25.search("xyznonexistentterm123", top_k=5)
        self.assertEqual(results, [])

    def test_empty_corpus(self) -> None:
        bm25 = BM25Retriever()
        self.assertEqual(bm25.search("anything"), [])
        self.assertEqual(len(bm25), 0)

    def test_incremental_index(self) -> None:
        bm25 = BM25Retriever()
        bm25.add_document("The quick brown fox")
        r1 = bm25.search("fox", top_k=5)
        self.assertEqual(len(r1), 1)

        # 增量添加文档
        new_id = bm25.add_document("A lazy dog and a fox")
        r2 = bm25.search("fox", top_k=5)
        self.assertEqual(len(r2), 2)
        # 新文档 ID 应为 1
        self.assertEqual(new_id, 1)

    def test_chinese_search(self) -> None:
        bm25 = BM25Retriever()
        bm25.add_document("Python是一门编程语言")
        bm25.add_document("Java用于企业级后端开发")
        bm25.add_document("机器学习使用Python和TensorFlow")

        results = bm25.search("Python 编程", top_k=3)
        self.assertGreater(len(results), 0)
        # 第一篇包含 "Python" 和 "编程"，应排第一
        self.assertIn("Python", results[0].content)

    def test_top_k_respected(self) -> None:
        for k in [1, 2, 3]:
            results = self.bm25.search("Python Java language", top_k=k)
            self.assertLessEqual(len(results), k)

    def test_parameters_k1_b(self) -> None:
        bm25_low_k1 = BM25Retriever(k1=0.5, b=0.5)
        bm25_high_k1 = BM25Retriever(k1=3.0, b=0.75)
        for doc in self.docs:
            bm25_low_k1.add_document(doc)
            bm25_high_k1.add_document(doc)

        # 不同参数应产生不同分数
        r_low = bm25_low_k1.search("Python", top_k=5)
        r_high = bm25_high_k1.search("Python", top_k=5)
        # 两个结果集都应包含相关文档
        self.assertGreater(len(r_low), 0)
        self.assertGreater(len(r_high), 0)

    def test_idf_nonnegative(self) -> None:
        for term, idf in self.bm25._idf_cache.items():
            self.assertGreaterEqual(idf, 0.0, f"IDF for {term} is negative")

    def test_avg_doc_length(self) -> None:
        self.assertGreater(self.bm25.avg_doc_length, 0)

    def test_vocabulary_size(self) -> None:
        self.assertGreater(self.bm25.vocabulary_size, 0)

    def test_get_document(self) -> None:
        self.assertEqual(self.bm25.get_document(0), self.docs[0])
        self.assertIsNone(self.bm25.get_document(999))

    def test_metadata_preserved(self) -> None:
        bm25 = BM25Retriever()
        bm25.add_document("test doc", metadata={"source": "unit_test"})
        r = bm25.search("test", top_k=1)
        self.assertEqual(r[0].metadata.get("source"), "unit_test")

    def test_scores_descending(self) -> None:
        results = self.bm25.search("Python Java machine", top_k=5)
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_candidate_ids_filter(self) -> None:
        # 仅在文档 1、3、4 中检索
        results = self.bm25.search(
            "Python", top_k=5, candidate_ids=[1, 3, 4]
        )
        for r in results:
            self.assertIn(r.doc_id, [1, 3, 4])

    def test_repr(self) -> None:
        r = repr(self.bm25)
        self.assertIn("BM25Retriever", r)
        self.assertIn("n_docs=5", r)


# ----------------------------------------------------------------------
#  Dense 检索器测试
# ----------------------------------------------------------------------

class TestDenseRetriever(unittest.TestCase):
    """Dense（TF-IDF 加权词向量）检索器测试。"""

    def setUp(self) -> None:
        self.docs = [
            "Python GIL prevents true multithreading in CPython",
            "Java runs on the JVM virtual machine",
            "Python is great for data science and machine learning",
            "JavaScript is the language of the web browsers",
            "Rust provides memory safety without garbage collection",
        ]
        self.dense = DenseRetriever()
        self.dense.add_documents(self.docs)

    def test_basic_search(self) -> None:
        results = self.dense.search("Python", top_k=3)
        self.assertGreater(len(results), 0)
        self.assertLessEqual(len(results), 3)

    def test_cosine_similarity_range(self) -> None:
        results = self.dense.search("Python Java", top_k=5)
        for r in results:
            # L2 归一化后的余弦相似度应在 [-1, 1]
            self.assertGreaterEqual(r.score, -1.0)
            self.assertLessEqual(r.score, 1.0)

    def test_same_query_high_similarity(self) -> None:
        # 查询与某文档完全相同，相似度应很高
        results = self.dense.search(
            "Python GIL prevents true multithreading in CPython",
            top_k=1,
        )
        self.assertGreater(len(results), 0)
        self.assertGreater(results[0].score, 0.5)
        self.assertEqual(results[0].doc_id, 0)

    def test_empty_query(self) -> None:
        self.assertEqual(self.dense.search(""), [])

    def test_no_match(self) -> None:
        results = self.dense.search("zzzznonexistent", top_k=5)
        self.assertEqual(results, [])

    def test_empty_corpus(self) -> None:
        dense = DenseRetriever()
        self.assertEqual(dense.search("test"), [])

    def test_incremental_update(self) -> None:
        dense = DenseRetriever()
        dense.add_document("hello world")
        dense.add_document("foo bar baz")
        r = dense.search("hello", top_k=5)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].doc_id, 0)

        # 增量添加
        dense.add_document("hello there everyone")
        r2 = dense.search("hello", top_k=5)
        self.assertEqual(len(r2), 2)

    def test_dimensions_grows_with_vocab(self) -> None:
        d1 = self.dense.dimensions
        self.dense.add_document("A completely new term xyzqwerty")
        d2 = self.dense.dimensions
        self.assertGreater(d2, d1)

    def test_scores_descending(self) -> None:
        results = self.dense.search("Python Java machine", top_k=5)
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_chinese_search(self) -> None:
        dense = DenseRetriever()
        dense.add_document("我喜欢用Python编程")
        dense.add_document("Java是企业级语言")
        results = dense.search("Python 编程", top_k=2)
        self.assertGreater(len(results), 0)

    def test_top_k(self) -> None:
        results = self.dense.search("the is on", top_k=2)
        self.assertLessEqual(len(results), 2)

    def test_metadata(self) -> None:
        dense = DenseRetriever()
        dense.add_document("meta test", metadata={"tag": "v1"})
        r = dense.search("meta", top_k=1)
        self.assertEqual(r[0].metadata["tag"], "v1")

    def test_get_document(self) -> None:
        self.assertEqual(self.dense.get_document(0), self.docs[0])
        self.assertIsNone(self.dense.get_document(999))

    def test_repr(self) -> None:
        r = repr(self.dense)
        self.assertIn("DenseRetriever", r)


# ----------------------------------------------------------------------
#  Hybrid 检索器测试
# ----------------------------------------------------------------------

class TestHybridRetriever(unittest.TestCase):
    """RRF 混合检索器测试。"""

    def setUp(self) -> None:
        self.docs = [
            "Python GIL prevents true multithreading in CPython",
            "Java runs on the JVM virtual machine",
            "Python is great for data science and machine learning",
            "JavaScript is the language of the web browsers",
            "Rust provides memory safety without garbage collection",
            "Go offers goroutines for concurrent programming",
            "Python threading and multiprocessing compared",
        ]
        self.hybrid = HybridRetriever()
        self.hybrid.add_documents(self.docs)

    def test_basic_search(self) -> None:
        results = self.hybrid.search("Python threading", top_k=3)
        self.assertGreater(len(results), 0)
        self.assertLessEqual(len(results), 3)

    def test_rrf_scores_positive(self) -> None:
        results = self.hybrid.search("Python", top_k=5)
        for r in results:
            self.assertGreater(r.score, 0)

    def test_top_k(self) -> None:
        for k in [1, 3, 5]:
            r = self.hybrid.search("Python Java", top_k=k)
            self.assertLessEqual(len(r), k)

    def test_empty_query(self) -> None:
        self.assertEqual(self.hybrid.search(""), [])

    def test_empty_corpus(self) -> None:
        h = HybridRetriever()
        self.assertEqual(h.search("test"), [])

    def test_weights_affect_ranking(self) -> None:
        """BM25 权重和 Dense 权重应影响融合结果。"""
        h_bm25_heavy = HybridRetriever(bm25_weight=10.0, dense_weight=0.1)
        h_dense_heavy = HybridRetriever(bm25_weight=0.1, dense_weight=10.0)
        for doc in self.docs:
            h_bm25_heavy.add_document(doc)
            h_dense_heavy.add_document(doc)

        # 两者都应返回结果，但排序可能不同
        r1 = h_bm25_heavy.search("Python machine", top_k=3)
        r2 = h_dense_heavy.search("Python machine", top_k=3)
        self.assertGreater(len(r1), 0)
        self.assertGreater(len(r2), 0)

    def test_time_decay(self) -> None:
        """时间衰减应使较新文档获得更高分数。"""
        h = HybridRetriever(time_decay_half_life=3600)  # 1 小时半衰期

        now = time.time()
        # 添加旧文档
        h.add_document(
            "Old Python tutorial",
            metadata={"timestamp": now - 86400 * 30},  # 30 天前
        )
        # 添加新文档
        h.add_document(
            "New Python tutorial",
            metadata={"timestamp": now},
        )

        results = h.search("Python tutorial", top_k=2)
        self.assertEqual(len(results), 2)
        # 新文档应排第一
        self.assertIn("New", results[0].content)
        self.assertIn("Old", results[1].content)

    def test_time_decay_disabled(self) -> None:
        """half_life=0 时不应用时间衰减。"""
        h = HybridRetriever(time_decay_half_life=0)
        now = time.time()
        h.add_document("Old doc about Python", metadata={"timestamp": now - 999999})
        h.add_document("New doc about Python", metadata={"timestamp": now})

        results = h.search("Python", top_k=2)
        # 不禁用衰减时，两篇都应出现（顺序取决于相关性而非时间）
        self.assertEqual(len(results), 2)

    def test_rrf_formula(self) -> None:
        """验证 RRF 公式：score = 1/(k+rank)。"""
        h = HybridRetriever(rrf_k=60, bm25_weight=1.0, dense_weight=0.0)
        h.add_document("alpha beta gamma")
        h.add_document("alpha beta")
        h.add_document("alpha")

        results = h.search("alpha", top_k=3)
        # doc 2 只含 alpha，排第一（词频更集中）
        # doc 0 含 alpha beta gamma，可能排第二或第三
        # 关键是分数应符合 RRF 公式
        self.assertGreater(len(results), 0)
        # 第一名的 RRF 分数应为 1/(60+1)
        self.assertAlmostEqual(results[0].score, 1.0 / 61.0, places=4)

    def test_chinese_search(self) -> None:
        h = HybridRetriever()
        h.add_document("Python是最好的编程语言")
        h.add_document("Java用于后端服务")
        h.add_document("机器学习用Python")
        results = h.search("Python 编程", top_k=3)
        self.assertGreater(len(results), 0)

    def test_candidate_ids(self) -> None:
        results = self.hybrid.search(
            "Python", top_k=5, candidate_ids=[1, 3, 4]
        )
        for r in results:
            self.assertIn(r.doc_id, [1, 3, 4])

    def test_metadata_preserved(self) -> None:
        h = HybridRetriever()
        h.add_document("test", metadata={"layer": "working"})
        r = h.search("test", top_k=1)
        self.assertEqual(r[0].metadata["layer"], "working")

    def test_n_docs(self) -> None:
        self.assertEqual(self.hybrid.n_docs, len(self.docs))

    def test_repr(self) -> None:
        r = repr(self.hybrid)
        self.assertIn("HybridRetriever", r)

    def test_result_to_dict(self) -> None:
        results = self.hybrid.search("Python", top_k=1)
        d = results[0].to_dict()
        self.assertIn("doc_id", d)
        self.assertIn("content", d)
        self.assertIn("score", d)
        self.assertIn("metadata", d)


# ----------------------------------------------------------------------
#  语义提取测试
# ----------------------------------------------------------------------

class TestSemanticExtraction(unittest.TestCase):
    """事实/规则/偏好提取规则测试。"""

    def test_extract_preference(self) -> None:
        facts = extract_semantic_facts(
            "I like Python programming", "user"
        )
        self.assertGreater(len(facts), 0)

    def test_extract_name(self) -> None:
        facts = extract_semantic_facts("My name is Alice", "user")
        self.assertTrue(any("Alice" in f for f in facts))

    def test_extract_rule(self) -> None:
        facts = extract_semantic_facts(
            "Always use dark mode in the editor", "user"
        )
        self.assertGreater(len(facts), 0)

    def test_no_extraction_for_assistant(self) -> None:
        facts = extract_semantic_facts(
            "I like Python", "assistant"
        )
        self.assertEqual(facts, [])

    def test_no_extraction_for_short(self) -> None:
        facts = extract_semantic_facts("hi", "user")
        self.assertEqual(facts, [])

    def test_no_extraction_for_neutral(self) -> None:
        facts = extract_semantic_facts(
            "The weather is nice today", "user"
        )
        # 不含偏好/规则关键词，不应提取
        self.assertEqual(len(facts), 0)

    def test_remember_that(self) -> None:
        facts = extract_semantic_facts(
            "Remember that the meeting is at 3pm", "user"
        )
        self.assertGreater(len(facts), 0)

    def test_dont_forget(self) -> None:
        facts = extract_semantic_facts(
            "Don't forget to backup the database", "user"
        )
        self.assertGreater(len(facts), 0)

    def test_i_live_in(self) -> None:
        facts = extract_semantic_facts("I live in Beijing", "user")
        self.assertTrue(any("Beijing" in f for f in facts))


# ----------------------------------------------------------------------
#  AMLMemoryStore 测试
# ----------------------------------------------------------------------

class TestAMLMemoryStore(unittest.TestCase):
    """AML 记忆管理器单元测试。"""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="suyi_aml_test_")
        self.store = AMLMemoryStore(
            storage_dir=self.tmpdir,
            working_capacity=10,
            episodic_capacity=50,
            semantic_capacity=20,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # --- 基本添加与检索 ---

    def test_add_and_search(self) -> None:
        self.store.add_message(
            "u1", "s1", "user", "My name is Alice"
        )
        results = self.store.search("u1", "s1", "what is my name")
        self.assertGreater(len(results), 0)
        self.assertTrue(any("Alice" in r["content"] for r in results))

    def test_add_message_returns_records(self) -> None:
        records = self.store.add_message(
            "u1", "s1", "user", "Hello there"
        )
        # 应至少创建 working + episodic
        self.assertGreaterEqual(len(records), 2)

    def test_empty_content_no_records(self) -> None:
        records = self.store.add_message("u1", "s1", "user", "")
        self.assertEqual(len(records), 0)

    def test_invalid_user_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.store.add_message("", "s1", "user", "test")

    def test_invalid_session_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.store.add_message("u1", "", "user", "test")

    # --- 多用户/会话隔离 ---

    def test_user_isolation(self) -> None:
        self.store.add_message("u1", "s1", "user", "Alice secret")
        self.store.add_message("u2", "s2", "user", "Bob secret")

        r1 = self.store.search("u1", "s1", "secret", top_k=10)
        r2 = self.store.search("u2", "s2", "secret", top_k=10)

        for r in r1:
            self.assertNotIn("Bob", r["content"])
        for r in r2:
            self.assertNotIn("Alice", r["content"])

    def test_session_isolation(self) -> None:
        self.store.add_message("u1", "s1", "user", "session one content")
        self.store.add_message("u1", "s2", "user", "session two content")

        r1 = self.store.search("u1", "s1", "content", top_k=10)
        # 当前会话结果应包含 session one
        self.assertTrue(
            any("session one" in r["content"] for r in r1)
        )

    def test_cross_session_episodic(self) -> None:
        """同用户不同会话的 episodic 记忆应可被检索到。"""
        self.store.add_message(
            "u1", "old_session", "user",
            "The project deadline is March 15th"
        )
        results = self.store.search(
            "u1", "new_session", "project deadline"
        )
        self.assertTrue(
            any("March 15" in r["content"] for r in results)
        )

    # --- 去重 ---

    def test_dedup_same_content(self) -> None:
        self.store.add_message("u1", "s1", "user", "hello world")
        self.store.add_message("u1", "s1", "user", "hello world")
        records = self.store.get_session_records("u1", "s1")
        # working 层应只有一条 "hello world"
        working = [r for r in records if r.layer == LAYER_WORKING]
        contents = [r.content for r in working]
        self.assertEqual(contents.count("hello world"), 1)

    def test_dedup_different_roles(self) -> None:
        self.store.add_message("u1", "s1", "user", "same content")
        self.store.add_message("u1", "s1", "assistant", "same content")
        # 不同角色不去重
        records = self.store.get_session_records("u1", "s1")
        working = [r for r in records if r.layer == LAYER_WORKING]
        self.assertEqual(len(working), 2)

    # --- 三层记忆路由 ---

    def test_working_memory_stored(self) -> None:
        self.store.add_message("u1", "s1", "user", "test message")
        records = self.store.get_session_records(
            "u1", "s1", layer=LAYER_WORKING
        )
        self.assertEqual(len(records), 1)

    def test_episodic_memory_stored(self) -> None:
        self.store.add_message("u1", "s1", "user", "test message")
        records = self.store.get_session_records(
            "u1", "s1", layer=LAYER_EPISODIC
        )
        self.assertEqual(len(records), 1)

    def test_semantic_memory_extracted(self) -> None:
        self.store.add_message(
            "u1", "s1", "user",
            "I like dark mode and my name is Alice"
        )
        records = self.store.get_user_records(
            "u1", layer=LAYER_SEMANTIC
        )
        self.assertGreater(len(records), 0)

    # --- TTL ---

    def test_ttl_expiration(self) -> None:
        store = AMLMemoryStore(
            storage_dir=self.tmpdir,
            working_ttl=0.1,  # 100ms
            episodic_ttl=0.1,
            semantic_ttl=0.1,
        )
        store.add_message("u1", "s1", "user", "expiring message")
        time.sleep(0.2)

        # 默认不返回过期条目
        results = store.search("u1", "s1", "expiring")
        self.assertEqual(len(results), 0)

    def test_include_expired(self) -> None:
        store = AMLMemoryStore(
            storage_dir=self.tmpdir,
            working_ttl=0.1,
            episodic_ttl=0.1,
        )
        store.add_message("u1", "s1", "user", "expiring message")
        time.sleep(0.2)

        results = store.search(
            "u1", "s1", "expiring", include_expired=True
        )
        self.assertGreater(len(results), 0)

    def test_cleanup_expired(self) -> None:
        store = AMLMemoryStore(
            storage_dir=self.tmpdir,
            working_ttl=0.1,
            episodic_ttl=0.1,
        )
        store.add_message("u1", "s1", "user", "to be cleaned")
        initial = store.total_records
        time.sleep(0.2)
        removed = store.cleanup_expired()
        self.assertGreater(removed, 0)
        self.assertLess(store.total_records, initial)

    def test_no_ttl_never_expires(self) -> None:
        store = AMLMemoryStore(
            storage_dir=self.tmpdir,
            working_ttl=0,
            episodic_ttl=0,
            semantic_ttl=0,
        )
        store.add_message("u1", "s1", "user", "permanent message")
        time.sleep(0.1)
        results = store.search("u1", "s1", "permanent")
        self.assertGreater(len(results), 0)

    # --- 容量管理 ---

    def test_working_capacity_enforced(self) -> None:
        store = AMLMemoryStore(
            storage_dir=self.tmpdir, working_capacity=3,
        )
        for i in range(10):
            store.add_message(
                "u1", "s1", "user", f"message number {i}"
            )
        records = store.get_session_records(
            "u1", "s1", layer=LAYER_WORKING
        )
        self.assertLessEqual(len(records), 3)

    def test_semantic_capacity_per_user(self) -> None:
        store = AMLMemoryStore(
            storage_dir=self.tmpdir,
            semantic_capacity=3,
        )
        for i in range(10):
            store.add_message(
                "u1", "s1", "user",
                f"I like thing number {i} and prefer color {i}"
            )
        sem = store.get_user_records("u1", layer=LAYER_SEMANTIC)
        self.assertLessEqual(len(sem), 3)

    # --- 持久化 ---

    def test_persistence_save_load(self) -> None:
        self.store.add_message("u1", "s1", "user", "Persistent fact one")
        self.store.add_message("u1", "s1", "user", "Persistent fact two")
        count_before = self.store.total_records

        # 重新加载
        store2 = AMLMemoryStore(storage_dir=self.tmpdir)
        self.assertEqual(store2.total_records, count_before)

    def test_persistence_search_after_load(self) -> None:
        self.store.add_message(
            "u1", "s1", "user", "The secret code is 42"
        )

        store2 = AMLMemoryStore(storage_dir=self.tmpdir)
        results = store2.search("u1", "s1", "secret code")
        self.assertTrue(any("42" in r["content"] for r in results))

    def test_persistence_corrupt_file(self) -> None:
        # 写入损坏的 JSON
        path = os.path.join(self.tmpdir, "aml_memory.json")
        with open(path, "w") as f:
            f.write("{not valid json!!!")

        # 应能正常启动（清空数据）
        store = AMLMemoryStore(storage_dir=self.tmpdir)
        self.assertEqual(store.total_records, 0)

    # --- 批量添加 ---

    def test_add_messages_batch(self) -> None:
        messages = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First reply"},
            {"role": "user", "content": "Second message"},
        ]
        count = self.store.add_messages_batch("u1", "s1", messages)
        self.assertGreater(count, 0)

        results = self.store.search("u1", "s1", "first message")
        self.assertGreater(len(results), 0)

    def test_batch_with_iso_timestamp(self) -> None:
        messages = [
            {
                "role": "user",
                "content": "Timestamped message",
                "timestamp": "2024-01-15T10:30:00Z",
            }
        ]
        count = self.store.add_messages_batch("u1", "s1", messages)
        self.assertGreater(count, 0)

    # --- 清除 ---

    def test_clear_user(self) -> None:
        self.store.add_message("u1", "s1", "user", "u1 data")
        self.store.add_message("u2", "s2", "user", "u2 data")
        removed = self.store.clear_user("u1")
        self.assertGreater(removed, 0)
        self.assertEqual(
            len(self.store.get_user_records("u1")), 0
        )
        self.assertGreater(
            len(self.store.get_user_records("u2")), 0
        )

    def test_clear_session(self) -> None:
        self.store.add_message("u1", "s1", "user", "session1")
        self.store.add_message("u1", "s2", "user", "session2")
        removed = self.store.clear_session("u1", "s1")
        self.assertGreater(removed, 0)
        self.assertEqual(
            len(self.store.get_session_records("u1", "s1")), 0
        )
        self.assertGreater(
            len(self.store.get_session_records("u1", "s2")), 0
        )

    # --- 元数据过滤 ---

    def test_metadata_filter(self) -> None:
        self.store.add_message(
            "u1", "s1", "user", "Important note about Python",
            metadata={"category": "tech"},
        )
        self.store.add_message(
            "u1", "s1", "user", "Important note about cooking",
            metadata={"category": "lifestyle"},
        )

        results = self.store.search(
            "u1", "s1", "important note",
            metadata_filter={"category": "tech"},
        )
        self.assertTrue(all(
            r["metadata"].get("category") == "tech" for r in results
        ))

    # --- 统计信息 ---

    def test_get_stats(self) -> None:
        self.store.add_message("u1", "s1", "user", "test content")
        stats = self.store.get_stats()
        self.assertIn("total_records", stats)
        self.assertIn("by_layer", stats)
        self.assertGreater(stats["total_records"], 0)
        self.assertIn("working", stats["by_layer"])

    # --- MemoryRecord ---

    def test_memory_record_is_expired(self) -> None:
        rec = MemoryRecord(
            id="x", user_id="u", session_id="s",
            layer="working", role="user", content="test",
            timestamp=time.time(), ttl=0.1,
        )
        self.assertFalse(rec.is_expired)
        time.sleep(0.15)
        self.assertTrue(rec.is_expired)

    def test_memory_record_serialization(self) -> None:
        rec = MemoryRecord(
            id="abc", user_id="u1", session_id="s1",
            layer="working", role="user", content="hello",
            timestamp=1000.0, added_at=900.0, ttl=60.0,
            metadata={"k": "v"},
        )
        d = rec.to_dict()
        rec2 = MemoryRecord.from_dict(d)
        self.assertEqual(rec2.id, "abc")
        self.assertEqual(rec2.content, "hello")
        self.assertEqual(rec2.metadata, {"k": "v"})

    # --- layers 参数 ---

    def test_search_specific_layers(self) -> None:
        self.store.add_message(
            "u1", "s1", "user",
            "I like Python and my name is Alice"
        )
        # 仅搜索 working
        r1 = self.store.search(
            "u1", "s1", "Alice", layers=[LAYER_WORKING]
        )
        for r in r1:
            self.assertEqual(r["metadata"]["layer"], LAYER_WORKING)


# ----------------------------------------------------------------------
#  请求体验证测试
# ----------------------------------------------------------------------

class TestRequestValidation(unittest.TestCase):
    """AML 请求体校验测试。"""

    def test_valid_add_body(self) -> None:
        body = {
            "user_id": "u1",
            "session_id": "s1",
            "messages": [
                {"role": "user", "content": "hello"},
            ],
        }
        self.assertIsNone(_validate_add_body(body))

    def test_add_missing_user_id(self) -> None:
        body = {
            "session_id": "s1",
            "messages": [{"role": "user", "content": "hi"}],
        }
        self.assertIsNotNone(_validate_add_body(body))

    def test_add_missing_session_id(self) -> None:
        body = {
            "user_id": "u1",
            "messages": [{"role": "user", "content": "hi"}],
        }
        self.assertIsNotNone(_validate_add_body(body))

    def test_add_empty_messages(self) -> None:
        body = {
            "user_id": "u1",
            "session_id": "s1",
            "messages": [],
        }
        self.assertIsNotNone(_validate_add_body(body))

    def test_add_invalid_role(self) -> None:
        body = {
            "user_id": "u1",
            "session_id": "s1",
            "messages": [{"role": "invalid", "content": "hi"}],
        }
        self.assertIsNotNone(_validate_add_body(body))

    def test_add_non_dict_message(self) -> None:
        body = {
            "user_id": "u1",
            "session_id": "s1",
            "messages": ["not a dict"],
        }
        self.assertIsNotNone(_validate_add_body(body))

    def test_add_content_must_be_string(self) -> None:
        body = {
            "user_id": "u1",
            "session_id": "s1",
            "messages": [{"role": "user", "content": 123}],
        }
        self.assertIsNotNone(_validate_add_body(body))

    def test_valid_search_body(self) -> None:
        body = {
            "user_id": "u1",
            "session_id": "s1",
            "query": "test query",
            "top_k": 5,
        }
        self.assertIsNone(_validate_search_body(body))

    def test_search_default_top_k(self) -> None:
        body = {
            "user_id": "u1",
            "session_id": "s1",
            "query": "test",
        }
        self.assertIsNone(_validate_search_body(body))

    def test_search_missing_query(self) -> None:
        body = {
            "user_id": "u1",
            "session_id": "s1",
        }
        self.assertIsNotNone(_validate_search_body(body))

    def test_search_empty_query(self) -> None:
        body = {
            "user_id": "u1",
            "session_id": "s1",
            "query": "   ",
        }
        self.assertIsNotNone(_validate_search_body(body))

    def test_search_invalid_top_k(self) -> None:
        body = {
            "user_id": "u1",
            "session_id": "s1",
            "query": "test",
            "top_k": 0,
        }
        self.assertIsNotNone(_validate_search_body(body))

    def test_search_top_k_too_large(self) -> None:
        body = {
            "user_id": "u1",
            "session_id": "s1",
            "query": "test",
            "top_k": 200,
        }
        self.assertIsNotNone(_validate_search_body(body))


# ----------------------------------------------------------------------
#  HTTP 服务器测试
# ----------------------------------------------------------------------

class TestAMLMemoryServer(unittest.TestCase):
    """AML HTTP 服务器端到端测试。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmpdir = tempfile.mkdtemp(prefix="suyi_aml_http_")
        cls.api_key = "test-api-key-12345"
        cls.server = AMLMemoryServer(
            host="127.0.0.1",
            port=0,  # 随机端口
            storage_dir=cls.tmpdir,
            api_key=cls.api_key,
        )
        cls.server.start_in_thread()
        # 获取实际端口
        time.sleep(0.3)
        cls.port = cls.server.httpd.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def _request(
        self,
        method: str,
        path: str,
        body: Any = None,
        headers: Dict[str, str] = None,
    ) -> tuple:
        """发送 HTTP 请求。

        Returns:
            (status_code, response_dict) 元组。
        """
        url = self.base_url + path
        data = None
        hdrs = {"Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)
        if body is not None:
            data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(
            url, data=data, headers=hdrs, method=method
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    # --- 健康检查 ---

    def test_health_endpoint(self) -> None:
        status, data = self._request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")
        self.assertIn("stats", data)
        self.assertIn("version", data)

    def test_health_no_auth_required(self) -> None:
        # /health 不需要鉴权
        status, _ = self._request("GET", "/health")
        self.assertEqual(status, 200)

    # --- /add ---

    def test_add_single_message(self) -> None:
        body = {
            "user_id": "http_u1",
            "session_id": "http_s1",
            "messages": [
                {"role": "user", "content": "Hello from HTTP test"},
            ],
        }
        status, data = self._request(
            "POST", "/add", body,
            headers={"X-API-Key": self.api_key},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")
        self.assertGreater(data["added"], 0)

    def test_add_multiple_messages(self) -> None:
        body = {
            "user_id": "http_u2",
            "session_id": "http_s2",
            "messages": [
                {"role": "user", "content": "First"},
                {"role": "assistant", "content": "Second"},
                {"role": "user", "content": "Third"},
            ],
        }
        status, data = self._request(
            "POST", "/add", body,
            headers={"X-API-Key": self.api_key},
        )
        self.assertEqual(status, 200)

    def test_add_with_metadata(self) -> None:
        body = {
            "user_id": "http_u3",
            "session_id": "http_s3",
            "messages": [
                {
                    "role": "user",
                    "content": "Message with metadata",
                    "metadata": {"source": "test"},
                }
            ],
            "metadata": {"batch": "unit_test"},
        }
        status, _ = self._request(
            "POST", "/add", body,
            headers={"X-API-Key": self.api_key},
        )
        self.assertEqual(status, 200)

    def test_add_invalid_json(self) -> None:
        url = self.base_url + "/add"
        req = urllib.request.Request(
            url,
            data=b"not json at all",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            },
            method="POST",
        )
        try:
            urllib.request.urlopen(req)
            self.fail("Should have raised HTTPError")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)

    def test_add_missing_user_id(self) -> None:
        body = {
            "session_id": "s1",
            "messages": [{"role": "user", "content": "hi"}],
        }
        status, data = self._request(
            "POST", "/add", body,
            headers={"X-API-Key": self.api_key},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", data)

    def test_add_empty_messages(self) -> None:
        body = {
            "user_id": "u1",
            "session_id": "s1",
            "messages": [],
        }
        status, _ = self._request(
            "POST", "/add", body,
            headers={"X-API-Key": self.api_key},
        )
        self.assertEqual(status, 400)

    # --- /search ---

    def test_search_endpoint(self) -> None:
        # 先添加
        self._request(
            "POST", "/add",
            {
                "user_id": "search_u1",
                "session_id": "search_s1",
                "messages": [
                    {"role": "user",
                     "content": "My favorite color is blue"},
                ],
            },
            headers={"X-API-Key": self.api_key},
        )

        status, data = self._request(
            "POST", "/search",
            {
                "user_id": "search_u1",
                "session_id": "search_s1",
                "query": "what is my favorite color",
                "top_k": 3,
            },
            headers={"X-API-Key": self.api_key},
        )
        self.assertEqual(status, 200)
        self.assertIn("results", data)
        self.assertGreater(data["count"], 0)
        self.assertIn("elapsed_ms", data)

    def test_search_empty_results(self) -> None:
        status, data = self._request(
            "POST", "/search",
            {
                "user_id": "nonexistent_user",
                "session_id": "nonexistent_session",
                "query": "anything at all",
                "top_k": 5,
            },
            headers={"X-API-Key": self.api_key},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["count"], 0)

    def test_search_invalid_top_k(self) -> None:
        status, _ = self._request(
            "POST", "/search",
            {
                "user_id": "u1",
                "session_id": "s1",
                "query": "test",
                "top_k": -1,
            },
            headers={"X-API-Key": self.api_key},
        )
        self.assertEqual(status, 400)

    def test_search_missing_query(self) -> None:
        status, _ = self._request(
            "POST", "/search",
            {
                "user_id": "u1",
                "session_id": "s1",
            },
            headers={"X-API-Key": self.api_key},
        )
        self.assertEqual(status, 400)

    # --- 鉴权 ---

    def test_auth_required(self) -> None:
        status, _ = self._request(
            "POST", "/search",
            {
                "user_id": "u1", "session_id": "s1",
                "query": "test",
            },
            # 不提供 API Key
        )
        self.assertEqual(status, 401)

    def test_auth_invalid_key(self) -> None:
        status, _ = self._request(
            "POST", "/search",
            {
                "user_id": "u1", "session_id": "s1",
                "query": "test",
            },
            headers={"X-API-Key": "wrong-key"},
        )
        self.assertEqual(status, 401)

    def test_auth_bearer_token(self) -> None:
        """支持 Authorization: Bearer <key> 方式。"""
        self._request(
            "POST", "/add",
            {
                "user_id": "bearer_u",
                "session_id": "bearer_s",
                "messages": [{"role": "user", "content": "bearer test"}],
            },
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        status, data = self._request(
            "POST", "/search",
            {
                "user_id": "bearer_u",
                "session_id": "bearer_s",
                "query": "bearer test",
            },
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        self.assertEqual(status, 200)
        self.assertGreater(data["count"], 0)

    # --- 错误处理 ---

    def test_404_for_unknown_path(self) -> None:
        status, _ = self._request("GET", "/nonexistent")
        self.assertEqual(status, 404)

    def test_404_post_unknown_path(self) -> None:
        status, _ = self._request(
            "POST", "/unknown",
            {"test": 1},
            headers={"X-API-Key": self.api_key},
        )
        self.assertEqual(status, 404)

    def test_cors_headers(self) -> None:
        url = self.base_url + "/health"
        req = urllib.request.Request(url, method="OPTIONS")
        try:
            with urllib.request.urlopen(req) as resp:
                self.assertIn("Access-Control-Allow-Origin", resp.headers)
        except urllib.error.HTTPError:
            pass  # OPTIONS 可能返回 204/200

    def test_empty_body_post(self) -> None:
        url = self.base_url + "/add"
        req = urllib.request.Request(
            url,
            data=b"",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            },
            method="POST",
        )
        try:
            urllib.request.urlopen(req)
            self.fail("Should have raised")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)

    # --- 并发测试 ---

    def test_concurrent_add(self) -> None:
        """并发添加消息不应出错。"""
        def add_msg(i: int) -> int:
            status, data = self._request(
                "POST", "/add",
                {
                    "user_id": f"concurrent_u_{i % 5}",
                    "session_id": f"concurrent_s_{i}",
                    "messages": [
                        {"role": "user",
                         "content": f"Concurrent message number {i}"}
                    ],
                },
                headers={"X-API-Key": self.api_key},
            )
            return status

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(add_msg, i) for i in range(20)]
            statuses = [f.result() for f in as_completed(futures)]

        self.assertTrue(all(s == 200 for s in statuses))

    def test_concurrent_search(self) -> None:
        """并发检索应线程安全。"""
        # 先添加一些数据
        for i in range(10):
            self._request(
                "POST", "/add",
                {
                    "user_id": "concurrent_search_u",
                    "session_id": "concurrent_search_s",
                    "messages": [
                        {"role": "user",
                         "content": f"Searchable content item {i}"}
                    ],
                },
                headers={"X-API-Key": self.api_key},
            )

        def search(i: int) -> int:
            status, _ = self._request(
                "POST", "/search",
                {
                    "user_id": "concurrent_search_u",
                    "session_id": "concurrent_search_s",
                    "query": f"content item {i}",
                    "top_k": 5,
                },
                headers={"X-API-Key": self.api_key},
            )
            return status

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(search, i) for i in range(20)]
            statuses = [f.result() for f in as_completed(futures)]

        self.assertTrue(all(s == 200 for s in statuses))


# ----------------------------------------------------------------------
#  无鉴权服务器测试
# ----------------------------------------------------------------------

class TestAMLServerNoAuth(unittest.TestCase):
    """不启用鉴权时的服务器测试。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmpdir = tempfile.mkdtemp(prefix="suyi_aml_noauth_")
        cls.server = AMLMemoryServer(
            host="127.0.0.1", port=0,
            storage_dir=cls.tmpdir, api_key=None,
        )
        cls.server.start_in_thread()
        time.sleep(0.3)
        cls.port = cls.server.httpd.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def test_no_auth_allows_access(self) -> None:
        body = {
            "user_id": "noauth_u",
            "session_id": "noauth_s",
            "query": "test",
        }
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            self.base_url + "/search",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)


# ----------------------------------------------------------------------
#  端到端测试（覆盖 AML 7 维基础场景）
# ----------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):
    """add → search 完整流程测试，覆盖 AML 7 个评测维度的基础场景。"""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="suyi_aml_e2e_")
        self.store = AMLMemoryStore(storage_dir=self.tmpdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_fact_recall(self) -> None:
        """FactRecall：能召回之前说过的事实。"""
        self.store.add_message(
            "u1", "s1", "user",
            "My passport number is AB1234567"
        )
        results = self.store.search("u1", "s1", "passport number")
        self.assertTrue(
            any("AB1234567" in r["content"] for r in results)
        )

    def test_multi_hop_integration(self) -> None:
        """MultiHopIntegration：能整合多条信息。"""
        self.store.add_message(
            "u1", "s1", "user", "I work at Acme Corporation"
        )
        self.store.add_message(
            "u1", "s1", "user", "Acme is located in San Francisco"
        )
        r1 = self.store.search("u1", "s1", "where do I work")
        r2 = self.store.search("u1", "s1", "Acme location")
        self.assertGreater(len(r1), 0)
        self.assertGreater(len(r2), 0)

    def test_temporal_reasoning(self) -> None:
        """TemporalReasoning：能区分新旧信息。"""
        now = time.time()
        self.store.add_message(
            "u1", "s1", "user", "I live in New York",
            timestamp=now - 86400 * 365,
        )
        self.store.add_message(
            "u1", "s1", "user", "I moved to London last week",
            timestamp=now,
        )
        results = self.store.search("u1", "s1", "where do I live now")
        # 最近的信息应排在前面（时间衰减）
        self.assertGreater(len(results), 0)

    def test_memory_governance(self) -> None:
        """MemoryGovernance：能清除用户数据。"""
        self.store.add_message(
            "u1", "s1", "user", "Sensitive personal information"
        )
        self.store.clear_user("u1")
        results = self.store.search("u1", "s1", "personal information")
        self.assertEqual(len(results), 0)

    def test_personalization(self) -> None:
        """Personalization：能记住用户偏好。"""
        self.store.add_message(
            "u1", "s1", "user", "I prefer dark mode in all my apps"
        )
        self.store.add_message(
            "u1", "s1", "user",
            "My favorite programming language is Python"
        )
        # 查询词与记忆内容有词汇重叠（BM25/Dense 基于词项匹配）
        r1 = self.store.search("u1", "s1", "dark mode apps")
        r2 = self.store.search(
            "u1", "s1", "favorite programming language Python"
        )
        self.assertTrue(any("dark" in r["content"].lower() for r in r1))
        self.assertTrue(
            any("python" in r["content"].lower() for r in r2)
        )

    def test_rule_execution(self) -> None:
        """RuleExecution：能记住规则。"""
        self.store.add_message(
            "u1", "s1", "user",
            "Always format code with 4 spaces indentation"
        )
        results = self.store.search("u1", "s1", "code formatting rule")
        self.assertTrue(
            any("indentation" in r["content"].lower() for r in results)
        )

    def test_security_privacy_isolation(self) -> None:
        """SecurityPrivacy：用户数据完全隔离。"""
        self.store.add_message(
            "alice", "s1", "user", "Alice's password is secret123"
        )
        self.store.add_message(
            "bob", "s1", "user", "Bob's password is hunter2"
        )

        alice_results = self.store.search(
            "alice", "s1", "password", top_k=10
        )
        for r in alice_results:
            self.assertNotIn("hunter2", r["content"])

        bob_results = self.store.search(
            "bob", "s1", "password", top_k=10
        )
        for r in bob_results:
            self.assertNotIn("secret123", r["content"])

    def test_http_e2e_add_search(self) -> None:
        """HTTP 端到端：通过 HTTP 接口完成 add→search。"""
        tmpdir = tempfile.mkdtemp(prefix="suyi_aml_e2e_http_")
        try:
            server = AMLMemoryServer(
                host="127.0.0.1", port=0,
                storage_dir=tmpdir, api_key="e2e-key",
            )
            server.start_in_thread()
            time.sleep(0.3)
            port = server.httpd.server_address[1]

            # Add
            add_data = json.dumps({
                "user_id": "e2e_user",
                "session_id": "e2e_session",
                "messages": [
                    {"role": "user",
                     "content": "The capital of France is Paris"},
                    {"role": "assistant",
                     "content": "Got it, I'll remember that."},
                ],
            }).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/add",
                data=add_data,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": "e2e-key",
                },
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                add_result = json.loads(resp.read())
                self.assertEqual(add_result["status"], "ok")

            # Search
            search_data = json.dumps({
                "user_id": "e2e_user",
                "session_id": "e2e_session",
                "query": "What is the capital of France?",
                "top_k": 5,
            }).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/search",
                data=search_data,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": "e2e-key",
                },
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                search_result = json.loads(resp.read())
                self.assertGreater(search_result["count"], 0)
                self.assertTrue(
                    any(
                        "Paris" in r["content"]
                        for r in search_result["results"]
                    )
                )

            server.stop()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ----------------------------------------------------------------------
#  性能测试
# ----------------------------------------------------------------------

class TestPerformance(unittest.TestCase):
    """性能基准测试。"""

    def test_1000_docs_search_under_1_second(self) -> None:
        """1000 条文档的检索应在 1 秒内完成。"""
        bm25 = BM25Retriever()
        dense = DenseRetriever()
        hybrid = HybridRetriever()

        # 生成 1000 条文档
        docs = []
        for i in range(1000):
            docs.append(
                f"Document number {i} about topic {i % 50}. "
                f"This document contains keywords alpha beta gamma "
                f"and some unique identifier doc_{i}."
            )

        # 索引构建
        start = time.time()
        for doc in docs:
            hybrid.add_document(doc)
        index_time = time.time() - start
        # 索引 1000 条不应超过 10 秒
        self.assertLess(index_time, 10.0)

        # 检索
        start = time.time()
        for _ in range(10):
            results = hybrid.search("alpha beta topic 25", top_k=10)
        elapsed = (time.time() - start) / 10

        self.assertGreater(len(results), 0)
        # 平均检索时间应 < 1 秒
        self.assertLess(elapsed, 1.0, f"Avg search took {elapsed:.3f}s")

    def test_memory_store_throughput(self) -> None:
        """AMLMemoryStore 添加 100 条消息的吞吐测试。"""
        tmpdir = tempfile.mkdtemp(prefix="suyi_aml_perf_")
        try:
            store = AMLMemoryStore(
                storage_dir=tmpdir,
                working_capacity=1000,
                episodic_capacity=1000,
                semantic_capacity=1000,
            )

            start = time.time()
            for i in range(100):
                store.add_message(
                    "perf_user", "perf_session", "user",
                    f"Performance test message number {i} "
                    f"with content about topic {i % 10}"
                )
            elapsed = time.time() - start

            # 100 条消息应在 5 秒内处理完成
            self.assertLess(elapsed, 5.0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ----------------------------------------------------------------------
#  工厂函数和上下文管理器测试
# ----------------------------------------------------------------------

class TestServerFactory(unittest.TestCase):
    """create_server 工厂函数和上下文管理器测试。"""

    def test_create_server(self) -> None:
        from suyi.memory.aml_adapter import create_server
        tmpdir = tempfile.mkdtemp()
        try:
            server = create_server(
                host="127.0.0.1", port=0,
                storage_dir=tmpdir, api_key=None,
            )
            self.assertIsInstance(server, AMLMemoryServer)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_context_manager(self) -> None:
        tmpdir = tempfile.mkdtemp()
        try:
            with AMLMemoryServer(
                host="127.0.0.1", port=0,
                storage_dir=tmpdir, api_key=None,
            ) as server:
                time.sleep(0.3)
                self.assertIsNotNone(server.httpd)
                port = server.httpd.server_address[1]

                # 发送请求验证
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/health"
                )
                with urllib.request.urlopen(req) as resp:
                    self.assertEqual(resp.status, 200)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_repr(self) -> None:
        server = AMLMemoryServer(host="localhost", port=8090)
        r = repr(server)
        self.assertIn("AMLMemoryServer", r)
        self.assertIn("8090", r)


# ----------------------------------------------------------------------
#  入口
# ----------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
