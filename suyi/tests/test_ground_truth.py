"""Tests for Ground Truth Layer — 最高优先级记忆。"""

import os
import tempfile

import pytest

from suyi.memory.ground_truth import GroundTruthEntry, GroundTruthStore


class TestGroundTruthEntry:
    """GroundTruthEntry 模型测试。"""

    def test_creation(self):
        """基本创建。"""
        entry = GroundTruthEntry(
            content="用户偏好使用 Python 3.12",
            category="user_profile",
            priority=100,
        )
        assert entry.content == "用户偏好使用 Python 3.12"
        assert entry.category == "user_profile"
        assert entry.priority == 100
        assert entry.verified is True
        assert entry.id

    def test_serialization(self):
        """序列化和反序列化。"""
        entry = GroundTruthEntry(
            content="Test content",
            category="system_config",
            priority=50,
            verified=False,
        )
        d = entry.to_dict()
        assert d["content"] == "Test content"

        restored = GroundTruthEntry.from_dict(d)
        assert restored.content == entry.content
        assert restored.priority == entry.priority
        assert restored.verified == entry.verified
        assert restored.id == entry.id


class TestGroundTruthStore:
    """GroundTruthStore 存储层测试。"""

    def test_add_and_get(self):
        """添加和获取。"""
        store = GroundTruthStore()
        entry = store.add(
            content="用户名是张三",
            category="user_profile",
            priority=100,
        )
        assert len(store) == 1
        assert store.get_by_id(entry.id) is not None

    def test_get_by_category(self):
        """按分类获取。"""
        store = GroundTruthStore()
        store.add("内容1", category="user_profile")
        store.add("内容2", category="system_config")
        store.add("内容3", category="user_profile")

        user_entries = store.get_by_category("user_profile")
        assert len(user_entries) == 2

    def test_delete(self):
        """删除。"""
        store = GroundTruthStore()
        entry = store.add("Test")
        assert store.delete(entry.id) is True
        assert len(store) == 0
        assert store.delete("nonexistent") is False

    def test_update(self):
        """更新条目。"""
        store = GroundTruthStore()
        entry = store.add("Original", priority=50)
        assert store.update(entry.id, content="Updated", priority=100, verified=False)
        updated = store.get_by_id(entry.id)
        assert updated.content == "Updated"
        assert updated.priority == 100
        assert updated.verified is False

    def test_retrieve(self):
        """语义检索。"""
        store = GroundTruthStore()
        store.add("Python 是一门编程语言", category="fact")
        store.add("Rust 关注内存安全", category="fact")
        store.add("系统配置: 端口 8080", category="config")

        results = store.retrieve("Python programming")
        assert len(results) > 0
        assert results[0]["layer"] == "ground_truth"
        assert "score" in results[0]

    def test_retrieve_with_category_filter(self):
        """分类过滤检索。"""
        store = GroundTruthStore()
        store.add("Python fact", category="fact")
        store.add("Config value", category="config")

        results = store.retrieve("Python", category="config")
        # 不应该匹配到 fact 类别的结果
        for r in results:
            assert r["category"] == "config"

    def test_check_conflict(self):
        """冲突检测。"""
        store = GroundTruthStore()
        store.add("用户偏好使用 Python 3.12")

        conflicts = store.check_conflict("用户偏好使用 Python 3.12", threshold=0.5)
        assert len(conflicts) > 0

        no_conflicts = store.check_conflict("完全不同的内容", threshold=0.5)
        assert len(no_conflicts) == 0

    def test_persistence(self):
        """JSON 持久化。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "gt.json")
            store = GroundTruthStore(storage_path=path)
            store.add("Ground truth content")

            store2 = GroundTruthStore(storage_path=path)
            assert len(store2) == 1

    def test_empty_retrieve(self):
        """空存储检索。"""
        store = GroundTruthStore()
        assert store.retrieve("anything") == []

    def test_get_all(self):
        """获取所有条目。"""
        store = GroundTruthStore()
        store.add("Entry 1")
        store.add("Entry 2")
        assert len(store.get_all()) == 2

    def test_repr(self):
        """repr 方法。"""
        store = GroundTruthStore()
        store.add("Test")
        assert "GroundTruthStore" in repr(store)
