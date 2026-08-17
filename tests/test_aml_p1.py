"""AML P1 改造（v1.10.0）测试套件。

覆盖范围：

- :class:`~suyi.memory.utility_reranker.UtilityReranker`：特征提取、
  冷启动排序、在线学习、权重持久化、L2 正则、与 AMLMemoryStore 集成。
- :class:`~suyi.memory.aml_evaluator.AMLEvaluator`：7 个维度各自的
  评分正确性、run_all 聚合、JSON 报告、边界情况。
- 端到端：带 reranking 的完整 add/search HTTP 流程。

运行方式::

    cd suyi
    python -m pytest tests/test_aml_p1.py -v
"""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

import numpy as np

from suyi.memory.utility_reranker import (
    UtilityReranker,
    RerankCandidate,
    RerankResult,
    FEATURE_NAMES,
    N_FEATURES,
    extract_features,
    _time_decay,
    _minmax,
)
from suyi.memory.aml_memory import AMLMemoryStore
from suyi.memory.aml_adapter import AMLMemoryServer
from suyi.memory.aml_evaluator import (
    AMLEvaluator,
    EvalReport,
    DimensionResult,
    CaseResult,
)
from suyi.memory.hybrid_retriever import AMLHybridRetriever
import suyi


# ----------------------------------------------------------------------
#  辅助
# ----------------------------------------------------------------------

def _candidate(
    doc_id: int,
    content: str,
    *,
    bm25: float = 0.0,
    dense: float = 0.0,
    rrf: float = 0.0,
    layer: str = "episodic",
    timestamp: Optional[float] = None,
    access: int = 0,
) -> RerankCandidate:
    """快速构造一个 :class:`RerankCandidate`。"""
    return RerankCandidate(
        doc_id=doc_id,
        content=content,
        bm25_score=bm25,
        dense_score=dense,
        rrf_score=rrf,
        layer=layer,
        timestamp=timestamp if timestamp is not None else time.time(),
        access_count=access,
    )


class _TempDirTestCase(unittest.TestCase):
    """每个测试用例创建独立临时目录。"""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="aml_p1_test_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)


# ----------------------------------------------------------------------
#  1. 特征提取（8 个）
# ----------------------------------------------------------------------

class TestFeatureExtraction(unittest.TestCase):
    """特征向量单元测试。"""

    def test_n_features_constant(self) -> None:
        """N_FEATURES 必须等于 FEATURE_NAMES 长度。"""
        self.assertEqual(N_FEATURES, len(FEATURE_NAMES))

    def test_feature_vector_shape(self) -> None:
        """单条特征向量 shape 正确。"""
        cand = _candidate(0, "Python GIL prevents threading")
        vec = extract_features("Python GIL", cand)
        self.assertEqual(vec.shape, (N_FEATURES,))
        self.assertEqual(vec.dtype, np.float64)

    def test_bm25_dense_rrf_passed_through(self) -> None:
        """传入的归一化分数应被原样放到对应维度。"""
        cand = _candidate(0, "hello world")
        vec = extract_features(
            "hello", cand,
            bm25_norm=0.3, dense_norm=0.4, rrf_norm=0.5,
        )
        self.assertAlmostEqual(vec[0], 0.3)
        self.assertAlmostEqual(vec[1], 0.4)
        self.assertAlmostEqual(vec[2], 0.5)

    def test_layer_one_hot_working(self) -> None:
        cand = _candidate(0, "c", layer="working")
        vec = extract_features("q", cand)
        self.assertEqual(vec[4], 1.0)
        self.assertEqual(vec[5], 0.0)
        self.assertEqual(vec[6], 0.0)

    def test_layer_one_hot_episodic(self) -> None:
        cand = _candidate(0, "c", layer="episodic")
        vec = extract_features("q", cand)
        self.assertEqual(vec[4], 0.0)
        self.assertEqual(vec[5], 1.0)
        self.assertEqual(vec[6], 0.0)

    def test_layer_one_hot_semantic(self) -> None:
        cand = _candidate(0, "c", layer="semantic")
        vec = extract_features("q", cand)
        self.assertEqual(vec[4], 0.0)
        self.assertEqual(vec[5], 0.0)
        self.assertEqual(vec[6], 1.0)

    def test_query_overlap_jaccard(self) -> None:
        """query_overlap 应是 token 集合的 Jaccard 相似度。"""
        cand = _candidate(0, "Python GIL threading concurrency")
        vec = extract_features("Python GIL", cand)
        # overlap 维 = 第 9 维（索引 9）
        # tokens(query) = {python, gil}
        # tokens(cand)  = {python, gil, threading, concurrency,
        #                  以及中文 bigram 这里不影响}
        # 交集 = 2，并集 = 4
        self.assertAlmostEqual(vec[9], 2.0 / 4.0, places=4)

    def test_time_decay_recent_is_higher(self) -> None:
        """越新的记忆，time_decay 维度值越高。"""
        now = 1_000_000.0
        old = _candidate(0, "old", timestamp=now - 10 * 365 * 24 * 3600)
        new = _candidate(1, "new", timestamp=now - 10)
        vec_old = extract_features("q", old, now=now,
                                   time_decay_half_life=7 * 24 * 3600)
        vec_new = extract_features("q", new, now=now,
                                   time_decay_half_life=7 * 24 * 3600)
        self.assertGreater(vec_new[3], vec_old[3])
        self.assertGreaterEqual(vec_old[3], 0.5)
        self.assertLessEqual(vec_new[3], 1.0)

    def test_time_decay_disabled(self) -> None:
        """half_life <= 0 时 time_decay 维度恒为 1.0。"""
        cand = _candidate(0, "old", timestamp=0.0)
        vec = extract_features("q", cand, time_decay_half_life=0.0,
                               now=1e12)
        self.assertAlmostEqual(vec[3], 1.0)


# ----------------------------------------------------------------------
#  2. 冷启动排序（5 个）
# ----------------------------------------------------------------------

class TestColdStartRanking(unittest.TestCase):
    """冷启动默认权重下的重排序行为。"""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="rerank_cold_")
        self.reranker = UtilityReranker(
            weights_path=os.path.join(self.tmp, "w.json"),
            training_log_path=os.path.join(self.tmp, "log.jsonl"),
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_more_relevant_ranks_higher(self) -> None:
        """BM25/Dense/RRF 分更高的候选应排在前面。"""
        cands = [
            _candidate(0, "Random unrelated text about cooking pasta",
                       bm25=0.0, dense=0.0, rrf=0.001),
            _candidate(1, "Python GIL prevents true multithreading",
                       bm25=2.5, dense=0.8, rrf=0.04),
        ]
        ranked = self.reranker.rerank(
            "Python GIL multithreading", cands, top_k=2
        )
        self.assertEqual(ranked[0].candidate.doc_id, 1)

    def test_newer_ranks_higher_when_relevance_equal(self) -> None:
        """相关性相当时，越新越靠前。"""
        now = time.time()
        cands = [
            _candidate(0, "Same content about Python",
                       bm25=1.0, dense=0.5, rrf=0.03,
                       timestamp=now - 100 * 24 * 3600),
            _candidate(1, "Same content about Python",
                       bm25=1.0, dense=0.5, rrf=0.03,
                       timestamp=now - 10),
        ]
        ranked = self.reranker.rerank("Python", cands, top_k=2, now=now)
        self.assertEqual(ranked[0].candidate.doc_id, 1)

    def test_semantic_layer_preferred_when_other_features_equal(
        self,
    ) -> None:
        """默认权重对 semantic 层略有偏好。"""
        now = time.time()
        cands = [
            _candidate(0, "I prefer Python for backends",
                       bm25=1.0, dense=0.5, rrf=0.03, layer="episodic",
                       timestamp=now),
            _candidate(1, "I prefer Python for backends",
                       bm25=1.0, dense=0.5, rrf=0.03, layer="semantic",
                       timestamp=now),
        ]
        ranked = self.reranker.rerank("Python preference", cands,
                                      top_k=2, now=now)
        self.assertEqual(ranked[0].candidate.doc_id, 1)

    def test_returns_top_k(self) -> None:
        cands = [_candidate(i, f"document {i}", bm25=float(i),
                           dense=0.1 * i, rrf=0.01 * i)
                 for i in range(10)]
        ranked = self.reranker.rerank("query", cands, top_k=3)
        self.assertEqual(len(ranked), 3)

    def test_empty_input_returns_empty(self) -> None:
        ranked = self.reranker.rerank("q", [], top_k=5)
        self.assertEqual(ranked, [])
        scored = self.reranker.score("q", [])
        self.assertEqual(scored, [])

    def test_utility_in_zero_one(self) -> None:
        """utility 概率必须落在 [0, 1]。"""
        cands = [_candidate(i, f"doc {i}", bm25=float(i))
                 for i in range(5)]
        for r in self.reranker.rerank("q", cands, top_k=5):
            self.assertGreaterEqual(r.utility, 0.0)
            self.assertLessEqual(r.utility, 1.0)


# ----------------------------------------------------------------------
#  3. 在线学习更新（8 个）
# ----------------------------------------------------------------------

class TestOnlineLearning(unittest.TestCase):
    """fit_partial / train_on_candidates 的行为测试。"""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="rerank_learn_")
        self.reranker = UtilityReranker(
            weights_path=os.path.join(self.tmp, "w.json"),
            training_log_path=os.path.join(self.tmp, "log.jsonl"),
            learning_rate=0.1,
            l2_lambda=0.0,  # 测试纯梯度更新
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_fit_partial_changes_weights(self) -> None:
        w_before = self.reranker.weights.copy()
        X = np.random.RandomState(0).rand(20, N_FEATURES)
        y = (X[:, 0] + X[:, 2] > 1.0).astype(np.float64)
        self.reranker.fit_partial(X, y)
        self.assertFalse(np.allclose(w_before, self.reranker.weights))

    def test_n_updates_counter(self) -> None:
        self.assertEqual(self.reranker.n_updates, 0)
        X = np.ones((2, N_FEATURES))
        y = np.array([1.0, 0.0])
        self.reranker.fit_partial(X, y)
        self.assertEqual(self.reranker.n_updates, 1)
        self.reranker.fit_partial(X, y)
        self.assertEqual(self.reranker.n_updates, 2)

    def test_positive_gradient_increases_relevant_weight(self) -> None:
        """正样本时，正特征的权重应增加。"""
        w_bm25_before = self.reranker.weights[0]
        X = np.zeros((1, N_FEATURES))
        X[0, 0] = 1.0  # bm25
        X[0, 3] = 1.0  # time_decay
        y = np.array([1.0])
        # 初始 bias = -0.2，w*b 等加起来 sigmoid < 1
        # error = p - y 是负的，梯度 w -= lr * (error * x + 2*l2*w)
        # 所以权重会增大
        self.reranker.fit_partial(X, y)
        self.assertGreater(self.reranker.weights[0], w_bm25_before)

    def test_negative_gradient_decreases_weight(self) -> None:
        """负样本时，正特征的权重应减小。"""
        w_bm25_before = self.reranker.weights[0]
        X = np.zeros((1, N_FEATURES))
        X[0, 0] = 1.0
        y = np.array([0.0])
        # p>0 -> error = p-0 > 0 -> 权重减小
        self.reranker.fit_partial(X, y)
        self.assertLess(self.reranker.weights[0], w_bm25_before)

    def test_train_on_candidates(self) -> None:
        cands = [
            _candidate(0, "good", bm25=2.0, dense=0.9, rrf=0.05),
            _candidate(1, "bad", bm25=0.0, dense=0.0, rrf=0.001),
        ]
        before = self.reranker.weights.copy()
        metrics = self.reranker.train_on_candidates(
            "query", cands, used_doc_ids=[0]
        )
        self.assertEqual(metrics["batch_size"], 2)
        self.assertFalse(np.allclose(before, self.reranker.weights))

    def test_fit_partial_returns_metrics(self) -> None:
        X = np.ones((4, N_FEATURES))
        y = np.array([1.0, 1.0, 0.0, 0.0])
        m = self.reranker.fit_partial(X, y)
        self.assertIn("loss", m)
        self.assertIn("accuracy", m)
        self.assertEqual(m["batch_size"], 4)
        self.assertGreaterEqual(m["loss"], 0.0)
        self.assertGreaterEqual(m["accuracy"], 0.0)
        self.assertLessEqual(m["accuracy"], 1.0)

    def test_fit_partial_invalid_dim_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.reranker.fit_partial(
                np.zeros((3, N_FEATURES + 1)),
                np.zeros(3),
            )

    def test_fit_partial_label_sample_mismatch_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.reranker.fit_partial(
                np.zeros((3, N_FEATURES)),
                np.zeros(4),
            )

    def test_fit_partial_empty_batch_is_noop(self) -> None:
        before = self.reranker.weights.copy()
        m = self.reranker.fit_partial(
            np.zeros((0, N_FEATURES)), np.zeros(0)
        )
        self.assertEqual(m["batch_size"], 0)
        np.testing.assert_array_equal(before, self.reranker.weights)


# ----------------------------------------------------------------------
#  4. 权重持久化（4 个）
# ----------------------------------------------------------------------

class TestWeightPersistence(_TempDirTestCase):
    """权重保存/加载测试。"""

    def test_save_and_load_roundtrip(self) -> None:
        wp = os.path.join(self.tmpdir, "w.json")
        lp = os.path.join(self.tmpdir, "log.jsonl")
        r1 = UtilityReranker(weights_path=wp, training_log_path=lp)
        X = np.random.RandomState(1).rand(10, N_FEATURES)
        y = (X.sum(axis=1) > 5).astype(float)
        r1.fit_partial(X, y, persist=True)

        r2 = UtilityReranker(weights_path=wp, training_log_path=lp)
        np.testing.assert_allclose(r1.weights, r2.weights)
        self.assertAlmostEqual(r1.bias, r2.bias)
        self.assertEqual(r1.n_updates, r2.n_updates)

    def test_corrupt_file_falls_back_to_defaults(self) -> None:
        wp = os.path.join(self.tmpdir, "w.json")
        with open(wp, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        r = UtilityReranker(weights_path=wp,
                            training_log_path=os.path.join(self.tmpdir,
                                                           "log.jsonl"))
        # 默认权重仍然可用
        self.assertEqual(r.weights.shape, (N_FEATURES,))

    def test_missing_file_uses_defaults(self) -> None:
        wp = os.path.join(self.tmpdir, "nonexistent", "w.json")
        r = UtilityReranker(weights_path=wp,
                            training_log_path=os.path.join(self.tmpdir,
                                                           "log.jsonl"))
        self.assertEqual(r.weights.shape, (N_FEATURES,))
        # RRF 维度（索引 2）的默认权重应较高
        self.assertGreater(r.weights[2], 1.0)

    def test_get_weight_dict_has_correct_keys(self) -> None:
        r = UtilityReranker(
            weights_path=os.path.join(self.tmpdir, "w.json"),
            training_log_path=os.path.join(self.tmpdir, "log.jsonl"),
        )
        d = r.get_weight_dict()
        self.assertEqual(set(d.keys()), set(FEATURE_NAMES))
        for name in FEATURE_NAMES:
            self.assertIsInstance(d[name], float)

    def test_reset_defaults(self) -> None:
        wp = os.path.join(self.tmpdir, "w.json")
        r = UtilityReranker(weights_path=wp,
                            training_log_path=os.path.join(self.tmpdir,
                                                           "log.jsonl"))
        X = np.ones((5, N_FEATURES))
        y = np.array([1, 1, 0, 0, 1], dtype=float)
        r.fit_partial(X, y)
        self.assertGreater(r.n_updates, 0)
        r.reset_defaults()
        self.assertEqual(r.n_updates, 0)
        # 默认 rrf 权重约为 1.8
        self.assertAlmostEqual(r.weights[2], 1.8, places=4)


# ----------------------------------------------------------------------
#  5. L2 正则（2 个）
# ----------------------------------------------------------------------

class TestL2Regularization(unittest.TestCase):
    """L2 正则化测试。"""

    def test_l2_pulls_weights_toward_zero(self) -> None:
        tmp = tempfile.mkdtemp(prefix="l2_")
        try:
            r_no_reg = UtilityReranker(
                weights_path=os.path.join(tmp, "a.json"),
                training_log_path=os.path.join(tmp, "la.jsonl"),
                learning_rate=0.1, l2_lambda=0.0,
            )
            r_reg = UtilityReranker(
                weights_path=os.path.join(tmp, "b.json"),
                training_log_path=os.path.join(tmp, "lb.jsonl"),
                learning_rate=0.1, l2_lambda=0.5,
            )
            X = np.zeros((1, N_FEATURES))
            X[0, 0] = 1.0
            y = np.array([1.0])
            # 多步更新让 L2 的效果累积
            for _ in range(20):
                r_no_reg.fit_partial(X, y)
                r_reg.fit_partial(X, y)
            self.assertLess(
                abs(r_reg.weights[0]), abs(r_no_reg.weights[0])
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_invalid_lambda_raises(self) -> None:
        with self.assertRaises(ValueError):
            UtilityReranker(l2_lambda=-0.1)

    def test_invalid_learning_rate_raises(self) -> None:
        with self.assertRaises(ValueError):
            UtilityReranker(learning_rate=0.0)


# ----------------------------------------------------------------------
#  6. 与 AMLMemoryStore / RRF 集成（5 个）
# ----------------------------------------------------------------------

class TestRerankerStoreIntegration(_TempDirTestCase):
    """Reranker 与 AMLMemoryStore.search 的集成测试。"""

    def test_store_creates_reranker_by_default(self) -> None:
        """默认应启用 reranker（除非环境变量关闭）。"""
        os.environ.pop("AML_RERANK_ENABLED", None)
        store = AMLMemoryStore(storage_dir=os.path.join(self.tmpdir, "a"))
        self.assertIsNotNone(store.reranker)
        self.assertIsInstance(store.reranker, UtilityReranker)

    def test_store_reranker_disabled_via_flag(self) -> None:
        store = AMLMemoryStore(
            storage_dir=os.path.join(self.tmpdir, "b"),
            reranker=False,
        )
        self.assertIsNone(store.reranker)

    def test_store_reranker_disabled_via_env(self) -> None:
        os.environ["AML_RERANK_ENABLED"] = "false"
        try:
            store = AMLMemoryStore(
                storage_dir=os.path.join(self.tmpdir, "c")
            )
            self.assertIsNone(store.reranker)
        finally:
            os.environ.pop("AML_RERANK_ENABLED", None)

    def test_search_with_reranker_returns_utility_metadata(self) -> None:
        store = AMLMemoryStore(
            storage_dir=os.path.join(self.tmpdir, "d"),
        )
        store.add_message("u", "s", "user",
                          "Python GIL prevents true multithreading")
        store.add_message("u", "s", "user",
                          "Java runs on the JVM virtual machine")
        res = store.search("u", "s",
                           "Python threading GIL", top_k=2)
        self.assertGreaterEqual(len(res), 1)
        # metadata 应包含 utility_score
        self.assertIn("utility_score", res[0]["metadata"])
        self.assertGreater(res[0]["metadata"]["utility_score"], 0.0)

    def test_search_rerank_does_not_change_response_shape(self) -> None:
        """重排不能破坏 v1.9 的响应结构。"""
        store = AMLMemoryStore(
            storage_dir=os.path.join(self.tmpdir, "e"),
        )
        store.add_message("u", "s", "user", "Remember that the deploy window is 2-4pm.")
        res = store.search("u", "s", "deploy window", top_k=3)
        for r in res:
            self.assertIn("content", r)
            self.assertIn("score", r)
            self.assertIn("metadata", r)
            self.assertIsInstance(r["score"], float)
            self.assertIsInstance(r["metadata"], dict)
            self.assertIn("layer", r["metadata"])

    def test_reranker_respects_top_k(self) -> None:
        store = AMLMemoryStore(
            storage_dir=os.path.join(self.tmpdir, "f"),
        )
        for i in range(10):
            store.add_message("u", "s", "user",
                              f"Fact number {i} about Python and ML")
        res = store.search("u", "s", "Python ML", top_k=3)
        self.assertLessEqual(len(res), 3)


# ----------------------------------------------------------------------
#  7. score_candidates 新接口（3 个）
# ----------------------------------------------------------------------

class TestScoreCandidates(unittest.TestCase):
    """AMLHybridRetriever.score_candidates 的单元测试。"""

    def test_returns_scores_for_each_doc(self) -> None:
        r = AMLHybridRetriever()
        id0 = r.add_document("Python GIL prevents threading")
        id1 = r.add_document("Java runs on JVM")
        id2 = r.add_document("I love Python programming")
        scores = r.score_candidates("Python GIL", [id0, id1, id2])
        self.assertEqual(set(scores.keys()), {id0, id1, id2})
        for s in scores.values():
            self.assertIn("bm25", s)
            self.assertIn("dense", s)
            self.assertIn("rrf", s)
            self.assertIn("fused", s)

    def test_relevant_doc_has_higher_rrf(self) -> None:
        r = AMLHybridRetriever()
        id0 = r.add_document("Python GIL prevents threading in CPython")
        id1 = r.add_document("Banana bread recipe with chocolate")
        scores = r.score_candidates("Python GIL threading", [id0, id1])
        self.assertGreater(scores[id0]["rrf"], scores[id1]["rrf"])

    def test_empty_input_returns_empty(self) -> None:
        r = AMLHybridRetriever()
        self.assertEqual(r.score_candidates("q", []), {})


# ----------------------------------------------------------------------
#  8. AMLEvaluator 维度测试（7 维 + 聚合 + JSON + 边界）
# ----------------------------------------------------------------------

class TestAMLEvaluatorDimensions(unittest.TestCase):
    """对每个维度的独立 evaluate_* 方法做基本断言。"""

    def _eval(self, **kwargs: Any) -> AMLEvaluator:
        return AMLEvaluator(verbose=False, **kwargs)

    def test_fact_recall_dimension(self) -> None:
        report = self._eval().evaluate_fact_recall()
        self.assertIsInstance(report, DimensionResult)
        self.assertEqual(report.dimension, "fact_recall")
        self.assertEqual(report.total_cases, 6)
        self.assertEqual(report.passed_cases, 6,
                         msg=[c.detail for c in report.cases
                              if not c.passed])
        self.assertAlmostEqual(report.score, 100.0)

    def test_multi_hop_dimension(self) -> None:
        report = self._eval().evaluate_multi_hop()
        self.assertEqual(report.total_cases, 5)
        self.assertEqual(report.passed_cases, 5,
                         msg=[c.detail for c in report.cases
                              if not c.passed])

    def test_temporal_dimension(self) -> None:
        report = self._eval().evaluate_temporal()
        self.assertEqual(report.total_cases, 6)
        self.assertEqual(report.passed_cases, 6,
                         msg=[c.detail for c in report.cases
                              if not c.passed])

    def test_governance_dimension(self) -> None:
        report = self._eval().evaluate_governance()
        self.assertEqual(report.total_cases, 5)
        self.assertEqual(report.passed_cases, 5,
                         msg=[c.detail for c in report.cases
                              if not c.passed])

    def test_personalization_dimension(self) -> None:
        report = self._eval().evaluate_personalization()
        self.assertEqual(report.total_cases, 5)
        self.assertEqual(report.passed_cases, 5,
                         msg=[c.detail for c in report.cases
                              if not c.passed])

    def test_rule_execution_dimension(self) -> None:
        report = self._eval().evaluate_rule_execution()
        self.assertEqual(report.total_cases, 5)
        self.assertEqual(report.passed_cases, 5,
                         msg=[c.detail for c in report.cases
                              if not c.passed])

    def test_security_privacy_dimension(self) -> None:
        report = self._eval().evaluate_security_privacy()
        self.assertEqual(report.total_cases, 6)
        self.assertEqual(report.passed_cases, 6,
                         msg=[(c.name, c.detail) for c in report.cases
                              if not c.passed])


class TestAMLEvaluatorAggregation(unittest.TestCase):
    """run_all 聚合逻辑测试。"""

    def test_run_all_returns_eval_report(self) -> None:
        ev = AMLEvaluator()
        report = ev.run_all()
        self.assertIsInstance(report, EvalReport)
        self.assertEqual(set(report.details.keys()), {
            "fact_recall", "multi_hop", "temporal", "governance",
            "personalization", "rule_execution", "security_privacy",
        })
        self.assertEqual(report.total_cases,
                         sum(d.total_cases
                             for d in report.details.values()))
        self.assertEqual(report.passed_cases,
                         sum(d.passed_cases
                             for d in report.details.values()))

    def test_run_all_total_score_is_average(self) -> None:
        ev = AMLEvaluator()
        report = ev.run_all()
        expected = round(
            sum(report.dimension_scores.values())
            / len(report.dimension_scores),
            2,
        )
        self.assertAlmostEqual(report.total_score, expected)

    def test_run_all_perfect_score(self) -> None:
        ev = AMLEvaluator()
        report = ev.run_all()
        self.assertEqual(report.total_score, 100.0,
                         msg=report.summary())

    def test_run_all_with_subset(self) -> None:
        ev = AMLEvaluator()
        report = ev.run_all(dimensions=["fact_recall", "multi_hop"])
        self.assertEqual(set(report.details.keys()),
                         {"fact_recall", "multi_hop"})
        self.assertEqual(len(report.dimension_scores), 2)

    def test_run_all_records_elapsed(self) -> None:
        ev = AMLEvaluator()
        report = ev.run_all()
        self.assertGreater(report.finished_at, report.started_at)
        self.assertGreaterEqual(
            (report.finished_at - report.started_at), 0.0
        )


class TestAMLEvaluatorJSONReport(_TempDirTestCase):
    """JSON 报告输出测试。"""

    def test_to_json_roundtrip(self) -> None:
        ev = AMLEvaluator()
        report = ev.run_all()
        js = report.to_json()
        data = json.loads(js)
        self.assertEqual(data["version"], "1.10.0")
        self.assertEqual(data["total_score"], 100.0)
        self.assertIn("details", data)
        self.assertEqual(len(data["details"]), 7)

    def test_save_report_to_file(self) -> None:
        ev = AMLEvaluator()
        report = ev.run_all()
        out_dir = os.path.join(self.tmpdir, "out")
        os.makedirs(out_dir, exist_ok=True)
        path = ev.save_report(report, out_dir)
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["total_score"], 100.0)

    def test_summary_contains_all_dimensions(self) -> None:
        ev = AMLEvaluator()
        report = ev.run_all()
        s = report.summary()
        for name in ["事实召回", "多跳整合", "时序推理", "记忆治理",
                     "个性化", "规则执行", "安全隐私"]:
            self.assertIn(name, s)


class TestAMLEvaluatorEdgeCases(_TempDirTestCase):
    """边界情况测试。"""

    def test_keep_data_true_preserves_directory(self) -> None:
        path = os.path.join(self.tmpdir, "keep")
        ev = AMLEvaluator(base_dir=path, keep_data=True)
        ev.run_all()
        # run_all 不应删除目录
        self.assertTrue(os.path.exists(path))

    def test_case_result_dataclass_fields(self) -> None:
        c = CaseResult(name="x", passed=True, detail="ok",
                       expected=["a"], actual=["b"], elapsed_ms=1.2)
        d = c.to_dict()
        self.assertEqual(d["name"], "x")
        self.assertEqual(d["elapsed_ms"], 1.2)

    def test_dimension_result_score_zero_on_no_cases(self) -> None:
        ev = AMLEvaluator()
        dim = ev._aggregate("empty", [])
        self.assertEqual(dim.score, 0.0)
        self.assertEqual(dim.total_cases, 0)

    def test_minmax_constant_returns_ones(self) -> None:
        self.assertEqual(_minmax([3, 3, 3]), [1.0, 1.0, 1.0])
        self.assertEqual(_minmax([]), [])

    def test_time_decay_at_half_life(self) -> None:
        now = 1_000_000.0
        half = 7 * 24 * 3600
        val = _time_decay(now - half, half_life=half, now=now)
        # 0.5 + 0.5*0.5 = 0.75
        self.assertAlmostEqual(val, 0.75)


# ----------------------------------------------------------------------
#  9. 端到端 HTTP + reranking（5 个）
# ----------------------------------------------------------------------

class TestEndToEndWithReranking(unittest.TestCase):
    """启动真实 HTTP 服务器，验证 add/search + reranking 端到端。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.mkdtemp(prefix="e2e_p1_")
        cls.server = AMLMemoryServer(
            host="127.0.0.1",
            port=0,
            storage_dir=os.path.join(cls.tmp, "store"),
            api_key=None,
            version="test-1.10.0",
            reranker=None,  # 默认开启（环境变量未设置）
        )
        cls.server.start_in_thread()
        port = None
        for _ in range(50):
            if cls.server.httpd is not None:
                port = cls.server.httpd.server_address[1]
                break
            time.sleep(0.05)
        cls.port = port
        cls.base = f"http://127.0.0.1:{port}"

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.server.stop(timeout=5)
        finally:
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def _post(
        self, path: str, body: Dict[str, Any],
    ) -> Dict[str, Any]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.base + path, data=data, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_health_reports_v1_10(self) -> None:
        req = urllib.request.Request(self.base + "/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["version"], "test-1.10.0")

    def test_add_and_search_returns_results(self) -> None:
        self._post("/add", {
            "user_id": "e2e",
            "session_id": "s1",
            "messages": [
                {"role": "user",
                 "content": "The deploy window is Tuesdays 2-4pm."}
            ],
        })
        res = self._post("/search", {
            "user_id": "e2e",
            "session_id": "s1",
            "query": "deploy window",
            "top_k": 5,
        })
        self.assertIn("results", res)
        contents = [r["content"] for r in res["results"]]
        self.assertTrue(any("deploy" in c.lower() for c in contents))

    def test_search_response_contains_utility_metadata(self) -> None:
        """reranker 开启时，/search 返回结果的 metadata 中带 utility_score。"""
        self._post("/add", {
            "user_id": "e2e",
            "session_id": "s1",
            "messages": [
                {"role": "user",
                 "content": "Production database runs on PostgreSQL 16."}
            ],
        })
        res = self._post("/search", {
            "user_id": "e2e",
            "session_id": "s1",
            "query": "production database postgres",
            "top_k": 5,
        })
        self.assertGreaterEqual(len(res["results"]), 1)
        meta = res["results"][0].get("metadata", {})
        self.assertIn("utility_score", meta)
        self.assertIsInstance(meta["utility_score"], (int, float))

    def test_user_isolation_over_http(self) -> None:
        self._post("/add", {
            "user_id": "alice", "session_id": "s",
            "messages": [{"role": "user",
                          "content": "Alice secret project codename Orion."}],
        })
        self._post("/add", {
            "user_id": "bob", "session_id": "s",
            "messages": [{"role": "user",
                          "content": "Bob secret project codename Pegasus."}],
        })
        res_alice = self._post("/search", {
            "user_id": "alice", "session_id": "s",
            "query": "secret project codename", "top_k": 10,
        })
        res_bob = self._post("/search", {
            "user_id": "bob", "session_id": "s",
            "query": "secret project codename", "top_k": 10,
        })
        alice_contents = " ".join(
            r["content"] for r in res_alice["results"]
        ).lower()
        bob_contents = " ".join(
            r["content"] for r in res_bob["results"]
        ).lower()
        self.assertIn("orion", alice_contents)
        self.assertNotIn("pegasus", alice_contents)
        self.assertIn("pegasus", bob_contents)
        self.assertNotIn("orion", bob_contents)

    def test_top_k_limits_results(self) -> None:
        for i in range(8):
            self._post("/add", {
                "user_id": "tk", "session_id": "s",
                "messages": [{"role": "user",
                              "content": f"Unique fact about topic {i}."}],
            })
        res = self._post("/search", {
            "user_id": "tk", "session_id": "s",
            "query": "unique fact topic",
            "top_k": 2,
        })
        self.assertLessEqual(len(res["results"]), 2)


# ----------------------------------------------------------------------
#  10. 版本号与导出（2 个）
# ----------------------------------------------------------------------

class TestVersionAndExports(unittest.TestCase):
    """确认版本号升级与公开导出。"""

    def test_version_is_1_10(self) -> None:
        self.assertEqual(suyi.__version__, "1.10.0")

    def test_top_level_exports(self) -> None:
        for name in [
            "UtilityReranker", "RerankCandidate", "RerankResult",
            "AMLEvaluator", "EvalReport",
            "AMLDimensionResult", "AMLCaseResult",
        ]:
            self.assertTrue(hasattr(suyi, name),
                            f"suyi.{name} missing")


# ----------------------------------------------------------------------
#  11. 训练日志记录（3 个）
# ----------------------------------------------------------------------

class TestTrainingLog(_TempDirTestCase):
    """record_search / ingest_log 测试。"""

    def test_record_search_appends_jsonl(self) -> None:
        lp = os.path.join(self.tmpdir, "log.jsonl")
        r = UtilityReranker(
            weights_path=os.path.join(self.tmpdir, "w.json"),
            training_log_path=lp,
        )
        r.record_search("q1", [1, 2, 3], used_doc_ids=[2])
        r.record_search("q2", [4, 5], used_doc_ids=[4, 5])
        with open(lp, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0])
        self.assertEqual(first["query"], "q1")
        self.assertEqual(first["used"], [2])

    def test_ingest_log_trains_and_clears(self) -> None:
        lp = os.path.join(self.tmpdir, "log.jsonl")
        r = UtilityReranker(
            weights_path=os.path.join(self.tmpdir, "w.json"),
            training_log_path=lp,
            learning_rate=0.1,
            l2_lambda=0.0,
        )
        # 造几条日志
        r.record_search("python", [0, 1], used_doc_ids=[0])
        r.record_search("java", [2, 3], used_doc_ids=[3])

        candidates = {
            0: _candidate(0, "Python is great", bm25=2.0, rrf=0.05),
            1: _candidate(1, "Cooking pasta", bm25=0.0, rrf=0.001),
            2: _candidate(2, "Cooking pasta", bm25=0.0, rrf=0.001),
            3: _candidate(3, "Java runs on JVM", bm25=2.0, rrf=0.05),
        }

        before = r.n_updates
        stats = r.ingest_log(
            candidate_lookup=lambda doc_id: candidates.get(doc_id),
            persist=False,
        )
        self.assertEqual(stats["processed_entries"], 2)
        self.assertEqual(r.n_updates, before + 2)
        # 训练后日志应被清空
        with open(lp, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "")

    def test_ingest_log_skips_missing_candidates(self) -> None:
        lp = os.path.join(self.tmpdir, "log.jsonl")
        r = UtilityReranker(
            weights_path=os.path.join(self.tmpdir, "w.json"),
            training_log_path=lp,
        )
        r.record_search("q", [999], used_doc_ids=[999])
        stats = r.ingest_log(
            candidate_lookup=lambda doc_id: None,
            persist=False,
        )
        self.assertEqual(stats["processed_entries"], 0)
        self.assertEqual(stats["skipped_entries"], 1)


# ----------------------------------------------------------------------
#  12. explain 可解释性
# ----------------------------------------------------------------------

class TestExplain(unittest.TestCase):
    def test_explain_returns_contributions(self) -> None:
        r = UtilityReranker(auto_load=False)
        c = _candidate(0, "Python GIL prevents threading",
                       layer="semantic")
        e = r.explain("Python GIL", c)
        self.assertIn("features", e)
        self.assertIn("contributions", e)
        self.assertIn("utility", e)
        self.assertIn("bias", e)
        self.assertEqual(set(e["features"].keys()), set(FEATURE_NAMES))
        self.assertGreaterEqual(e["utility"], 0.0)
        self.assertLessEqual(e["utility"], 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
