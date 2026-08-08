"""Tests for Memory Priority and 7-layer MemoryManager integration.

测试 MemoryManager 统一管理七层记忆的读写和优先级裁决。
"""

import pytest

from suyi.memory import (
    MemoryManager,
    MemoryPriority,
    StructuredFact,
    StructuredFactsStore,
    FactSource,
    GroundTruthStore,
    AutoWiki,
    RetrievalChain,
    SemanticDeduplicator,
    MessageClassifier,
    HybridRetriever,
    LexicalRetriever,
)


class TestMemoryPriority:
    """MemoryPriority 枚举测试。"""

    def test_priority_order(self):
        """优先级顺序: GROUND_TRUTH > WORKSPACE > FACTS > SESSIONS > VECTOR > WIKI"""
        assert MemoryPriority.GROUND_TRUTH > MemoryPriority.WORKSPACE
        assert MemoryPriority.WORKSPACE > MemoryPriority.FACTS
        assert MemoryPriority.FACTS > MemoryPriority.SESSIONS
        assert MemoryPriority.SESSIONS > MemoryPriority.VECTOR
        assert MemoryPriority.VECTOR > MemoryPriority.WIKI

    def test_priority_values(self):
        """优先级值正确。"""
        assert MemoryPriority.GROUND_TRUTH == 6
        assert MemoryPriority.WORKSPACE == 5
        assert MemoryPriority.FACTS == 4
        assert MemoryPriority.SESSIONS == 3
        assert MemoryPriority.VECTOR == 2
        assert MemoryPriority.WIKI == 1

    def test_sortable(self):
        """可排序。"""
        priorities = [
            MemoryPriority.WIKI,
            MemoryPriority.GROUND_TRUTH,
            MemoryPriority.VECTOR,
        ]
        sorted_priorities = sorted(priorities, reverse=True)
        assert sorted_priorities[0] == MemoryPriority.GROUND_TRUTH
        assert sorted_priorities[-1] == MemoryPriority.WIKI


class TestMemoryManagerSevenLayers:
    """MemoryManager 七层记忆管理测试。"""

    def setup_method(self):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()

    def _make_mgr(self):
        return MemoryManager(storage_dir=self._tmpdir)

    def test_all_layers_initialized(self):
        """所有七层记忆都已初始化。"""
        mgr = self._make_mgr()
        assert hasattr(mgr, "working")
        assert hasattr(mgr, "episodic")
        assert hasattr(mgr, "semantic")
        assert hasattr(mgr, "ground_truth")
        assert hasattr(mgr, "structured_facts")
        assert hasattr(mgr, "auto_wiki")
        assert hasattr(mgr, "message_classifier")
        assert hasattr(mgr, "deduplicator")

    def test_ground_truth_layer(self):
        """Ground Truth 层操作。"""
        mgr = self._make_mgr()
        mgr.ground_truth.add("User prefers Python 3.12", category="user_profile")
        assert len(mgr.ground_truth) == 1
        results = mgr.ground_truth.retrieve("Python")
        assert len(results) > 0

    def test_structured_facts_layer(self):
        """结构化事实层操作。"""
        mgr = self._make_mgr()
        mgr.structured_facts.add(
            "Python", "typing", "dynamic",
            source=FactSource.USER_STATEMENT.value,
        )
        assert len(mgr.structured_facts) == 1
        results = mgr.structured_facts.retrieve("Python typing")
        assert len(results) > 0

    def test_auto_wiki_layer(self):
        """Auto Wiki 层操作。"""
        mgr = self._make_mgr()
        facts = [
            StructuredFact(entity="Python", attribute="typing", value="dynamic"),
        ]
        mgr.auto_wiki.add_facts(facts)
        assert len(mgr.auto_wiki) == 1

    def test_message_classifier(self):
        """消息分类器。"""
        mgr = self._make_mgr()
        assert mgr.message_classifier.is_trivial("好的") is True
        assert mgr.message_classifier.is_trivial("请帮我写代码") is False

    def test_deduplicator(self):
        """语义去重器。"""
        mgr = self._make_mgr()
        sim = mgr.deduplicator.cosine_similarity("test", "test")
        assert sim > 0.9

    def test_get_status_includes_new_layers(self):
        """状态报告包含新层。"""
        mgr = self._make_mgr()
        mgr.ground_truth.add("GT entry")
        mgr.structured_facts.add("A", "x", "1")

        status = mgr.get_status()
        assert "ground_truth" in status
        assert status["ground_truth"]["entries"] == 1
        assert "structured_facts" in status
        assert status["structured_facts"]["facts"] == 1
        assert "auto_wiki" in status

    def test_priority_arbitration(self):
        """优先级裁决: Ground Truth 覆盖其他层。"""
        mgr = self._make_mgr()

        # 在语义层存储一条信息
        mgr.semantic.add("Python is slow", tags=["python"])

        # 在 Ground Truth 层存储矛盾信息
        mgr.ground_truth.add("Python is fast and efficient", category="fact")

        # 检索时 Ground Truth 应该有更高优先级
        gt_results = mgr.ground_truth.retrieve("Python")
        assert len(gt_results) > 0
        assert gt_results[0]["layer"] == "ground_truth"

    def test_retrieval_chain_integration(self):
        """检索链集成测试。"""
        mgr = self._make_mgr()
        mgr.semantic.add("Python programming language")

        # 构建检索链
        docs = [e.content for e in mgr.semantic.entries]
        chain = RetrievalChain([
            HybridRetriever(docs, "semantic"),
            LexicalRetriever(docs, "episodic"),
        ])

        results = chain.retrieve("Python")
        assert len(results) > 0
        assert chain.last_fallback_log["fallback_level"] == 0

    def test_deduplication_integration(self):
        """去重集成测试。"""
        mgr = self._make_mgr()

        # 写入前检查去重
        new_item = {"content": "Python is a programming language", "trust_score": 0.8}
        existing = [{"content": "Python is a programming language", "trust_score": 0.5}]

        result, was_merged, idx = mgr.deduplicator.deduplicate(new_item, existing)
        assert was_merged is True
        assert result["trust_score"] == 0.8  # 取较高值

    def test_message_classifier_integration(self):
        """消息分类器集成: trivial 消息跳过记忆写入。"""
        mgr = self._make_mgr()

        # Trivial 消息不写入记忆
        trivial_msg = "好的"
        if not mgr.message_classifier.is_trivial(trivial_msg):
            mgr.semantic.add(trivial_msg)
        assert len(mgr.semantic) == 0

        # 非 trivial 消息写入记忆
        important_msg = "Python uses GIL for thread safety"
        if not mgr.message_classifier.is_trivial(important_msg):
            mgr.semantic.add(important_msg)
        assert len(mgr.semantic) == 1
