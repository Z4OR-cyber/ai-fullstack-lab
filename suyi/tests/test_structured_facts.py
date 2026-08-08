"""Tests for Structured Facts Layer — 实体-属性-值三元组与信任度。"""

import os
import tempfile
import time

import pytest

from suyi.memory.structured_facts import (
    StructuredFact,
    StructuredFactsStore,
    FactSource,
)


class TestStructuredFact:
    """StructuredFact 模型测试。"""

    def test_creation_basic(self):
        """基本创建。"""
        fact = StructuredFact(
            entity="Python",
            attribute="typing_system",
            value="gradual",
        )
        assert fact.entity == "Python"
        assert fact.attribute == "typing_system"
        assert fact.value == "gradual"
        assert fact.id  # 自动生成 ID
        assert fact.timestamp > 0

    def test_default_trust_by_source(self):
        """根据来源设置默认 trust_score。"""
        user_fact = StructuredFact(
            entity="X", attribute="a", value="1",
            source=FactSource.USER_STATEMENT.value,
        )
        assert user_fact.trust_score == 0.95

        agent_fact = StructuredFact(
            entity="X", attribute="a", value="1",
            source=FactSource.AGENT_INFERENCE.value,
        )
        assert agent_fact.trust_score == 0.6

        speculation_fact = StructuredFact(
            entity="X", attribute="a", value="1",
            source=FactSource.SPECULATION.value,
        )
        assert speculation_fact.trust_score == 0.3

    def test_custom_trust_score(self):
        """自定义 trust_score。"""
        # 使用非 0.5 的值以避免被 __post_init__ 覆盖
        fact = StructuredFact(
            entity="X", attribute="a", value="1",
            source=FactSource.USER_STATEMENT.value,
            trust_score=0.7,
        )
        assert fact.trust_score == 0.7

    def test_trust_score_clamping(self):
        """trust_score 被限制在 [0, 1]。"""
        fact = StructuredFact(
            entity="X", attribute="a", value="1",
            trust_score=1.5,
        )
        assert fact.trust_score == 1.0

        fact2 = StructuredFact(
            entity="X", attribute="a", value="1",
            trust_score=-0.5,
        )
        assert fact2.trust_score == 0.0

    def test_trust_decay(self):
        """信任度衰减: 每月 -0.05，下限 0.1。"""
        fact = StructuredFact(
            entity="X", attribute="a", value="1",
            trust_score=0.5,
        )
        # 衰减 1 个月
        fact.trust_decay(months=1)
        assert fact.trust_score == pytest.approx(0.45)

        # 衰减多个月
        fact.trust_decay(months=3)
        assert fact.trust_score == pytest.approx(0.30)

        # 衰减到下限
        fact.trust_decay(months=100)
        assert fact.trust_score == 0.1

    def test_trust_boost(self):
        """信任度提升: 被确认 +0.1，上限 1.0。"""
        fact = StructuredFact(
            entity="X", attribute="a", value="1",
            trust_score=0.5,
        )
        fact.trust_boost()
        assert fact.trust_score == pytest.approx(0.6)
        assert fact.confirmed_count == 1

        fact.trust_boost()
        assert fact.trust_score == pytest.approx(0.7)
        assert fact.confirmed_count == 2

        # 上限 1.0
        fact.trust_boost(amount=0.5)
        assert fact.trust_score == 1.0

    def test_serialization(self):
        """序列化和反序列化。"""
        fact = StructuredFact(
            entity="Python",
            attribute="creator",
            value="Guido van Rossum",
            source=FactSource.USER_STATEMENT.value,
            trust_score=0.95,
        )
        d = fact.to_dict()
        assert d["entity"] == "Python"
        assert d["trust_score"] == 0.95

        restored = StructuredFact.from_dict(d)
        assert restored.entity == fact.entity
        assert restored.attribute == fact.attribute
        assert restored.value == fact.value
        assert restored.trust_score == fact.trust_score
        assert restored.id == fact.id

    def test_content_text(self):
        """内容文本表示。"""
        fact = StructuredFact(
            entity="Python", attribute="version", value="3.12",
        )
        assert fact.content_text() == "Python.version = 3.12"


class TestStructuredFactsStore:
    """StructuredFactsStore 存储层测试。"""

    def test_add_and_retrieve(self):
        """添加和检索。"""
        store = StructuredFactsStore()
        store.add(
            entity="Python",
            attribute="typing_system",
            value="gradual",
            source=FactSource.USER_STATEMENT.value,
        )
        store.add(
            entity="Python",
            attribute="creator",
            value="Guido van Rossum",
            source=FactSource.USER_STATEMENT.value,
        )

        assert len(store) == 2

        # 按实体检索
        python_facts = store.get_by_entity("Python")
        assert len(python_facts) == 2

        # 按实体+属性检索
        fact = store.get_by_entity_attribute("Python", "creator")
        assert fact is not None
        assert fact.value == "Guido van Rossum"

    def test_add_fact_object(self):
        """添加预构造的 StructuredFact。"""
        store = StructuredFactsStore()
        fact = StructuredFact(
            entity="Rust", attribute="memory_safety", value="ownership",
        )
        store.add_fact(fact)
        assert len(store) == 1
        assert store.get_by_id(fact.id) is not None

    def test_delete(self):
        """删除事实。"""
        store = StructuredFactsStore()
        fact = store.add("X", "a", "1")
        assert len(store) == 1
        assert store.delete(fact.id) is True
        assert len(store) == 0
        assert store.delete("nonexistent") is False

    def test_retrieve_semantic(self):
        """语义检索。"""
        store = StructuredFactsStore()
        store.add("Python", "typing", "gradual", source=FactSource.USER_STATEMENT.value)
        store.add("Rust", "typing", "static", source=FactSource.USER_STATEMENT.value)
        store.add("JavaScript", "typing", "dynamic", source=FactSource.USER_STATEMENT.value)

        results = store.retrieve("Python typing")
        assert len(results) > 0
        assert results[0]["entity"] == "Python"
        assert results[0]["layer"] == "facts"
        assert "score" in results[0]
        assert "relevance_score" in results[0]

    def test_retrieve_with_min_trust(self):
        """按最低信任度过滤。"""
        store = StructuredFactsStore()
        store.add("A", "x", "1", source=FactSource.SPECULATION.value)  # trust=0.3
        store.add("B", "x", "1", source=FactSource.USER_STATEMENT.value)  # trust=0.95

        results = store.retrieve("x", min_trust=0.5)
        assert len(results) > 0
        for r in results:
            assert r["trust_score"] >= 0.5

    def test_retrieve_combined_score(self):
        """综合分数 = relevance_score * trust_score。"""
        store = StructuredFactsStore()
        # 高 trust 但低相关性
        store.add("Python", "version", "3.12", source=FactSource.USER_STATEMENT.value)
        # 低 trust 但高相关性
        store.add("Python", "version_info", "3.12.0", source=FactSource.SPECULATION.value)

        results = store.retrieve("Python version")
        assert len(results) > 0
        # 验证综合分数排序
        if len(results) >= 2:
            assert results[0]["score"] >= results[1]["score"]

    def test_apply_trust_decay(self):
        """批量信任度衰减。"""
        store = StructuredFactsStore()
        store.add("A", "x", "1", source=FactSource.USER_STATEMENT.value)
        store.add("B", "x", "2", source=FactSource.AGENT_INFERENCE.value)

        count = store.apply_trust_decay(months=2)
        assert count == 2
        for f in store.facts:
            assert f.trust_score <= 0.95 - 0.10  # 衰减 2 个月

    def test_confirm_fact(self):
        """确认事实。"""
        store = StructuredFactsStore()
        fact = store.add("A", "x", "1", source=FactSource.AGENT_INFERENCE.value)
        original_trust = fact.trust_score

        assert store.confirm_fact(fact.id) is True
        updated = store.get_by_id(fact.id)
        assert updated.trust_score > original_trust
        assert updated.confirmed_count == 1

        assert store.confirm_fact("nonexistent") is False

    def test_persistence(self):
        """JSON 持久化。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "facts.json")
            store = StructuredFactsStore(storage_path=path)
            store.add("Python", "typing", "gradual")

            # 创建新实例加载
            store2 = StructuredFactsStore(storage_path=path)
            assert len(store2) == 1
            assert store2.get_by_entity("Python") is not None

    def test_empty_retrieve(self):
        """空存储检索。"""
        store = StructuredFactsStore()
        assert store.retrieve("anything") == []

    def test_repr(self):
        """repr 方法。"""
        store = StructuredFactsStore()
        store.add("A", "x", "1")
        assert "StructuredFactsStore" in repr(store)
        assert "facts=1" in repr(store)
