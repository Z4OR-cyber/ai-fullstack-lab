"""Tests for Semantic Deduplication — 语义去重。"""

import pytest

from suyi.memory.dedup import SemanticDeduplicator


class TestSemanticDeduplicator:
    """SemanticDeduplicator 语义去重测试。"""

    def test_cosine_similarity_identical(self):
        """相同文本相似度为 1.0。"""
        dedup = SemanticDeduplicator()
        sim = dedup.cosine_similarity("Python is great", "Python is great")
        assert sim == pytest.approx(1.0, abs=0.01)

    def test_cosine_similarity_different(self):
        """不同文本相似度较低。"""
        dedup = SemanticDeduplicator()
        sim = dedup.cosine_similarity("Python programming", "Rust memory safety")
        assert sim < 0.5

    def test_cosine_similarity_empty(self):
        """空文本相似度为 0。"""
        dedup = SemanticDeduplicator()
        assert dedup.cosine_similarity("", "test") == 0.0
        assert dedup.cosine_similarity("test", "") == 0.0
        assert dedup.cosine_similarity("", "") == 0.0

    def test_find_duplicate_found(self):
        """找到重复条目。"""
        dedup = SemanticDeduplicator(threshold=0.8)
        existing = [
            {"content": "Python is a programming language"},
            {"content": "Rust focuses on memory safety"},
        ]
        result = dedup.find_duplicate("Python is a programming language", existing)
        assert result is not None
        idx, sim = result
        assert idx == 0
        assert sim >= 0.8

    def test_find_duplicate_not_found(self):
        """未找到重复条目。"""
        dedup = SemanticDeduplicator(threshold=0.95)
        existing = [
            {"content": "Python is a programming language"},
        ]
        result = dedup.find_duplicate("Rust focuses on memory safety", existing)
        assert result is None

    def test_merge(self):
        """合并策略: 信息并集，时间戳取较新值，trust_score 取较高值。"""
        dedup = SemanticDeduplicator()
        new_item = {
            "content": "Python is a programming language with dynamic typing",
            "timestamp": 200,
            "trust_score": 0.8,
            "tags": ["python", "language"],
        }
        existing_item = {
            "content": "Python is a programming language",
            "timestamp": 100,
            "trust_score": 0.6,
            "tags": ["python"],
        }
        merged = dedup.merge(new_item, existing_item)

        # 内容取更长的
        assert len(merged["content"]) >= len(existing_item["content"])
        # 时间戳取较新的
        assert merged["timestamp"] == 200
        # trust_score 取较高的
        assert merged["trust_score"] == 0.8
        # tags 并集
        assert set(merged["tags"]) == {"python", "language"}
        # 标记为已合并
        assert merged["_merged"] is True

    def test_deduplicate_no_dup(self):
        """无重复时返回原条目。"""
        dedup = SemanticDeduplicator(threshold=0.95)
        new_item = {"content": "Completely new content about Rust"}
        existing = [{"content": "Python is a programming language"}]

        result, was_merged, dup_idx = dedup.deduplicate(new_item, existing)
        assert was_merged is False
        assert dup_idx is None
        assert result == new_item

    def test_deduplicate_with_dup(self):
        """有重复时合并。"""
        dedup = SemanticDeduplicator(threshold=0.5)
        new_item = {
            "content": "Python is a programming language",
            "timestamp": 200,
            "trust_score": 0.9,
        }
        existing = [
            {"content": "Python is a programming language", "timestamp": 100, "trust_score": 0.5}
        ]

        result, was_merged, dup_idx = dedup.deduplicate(new_item, existing)
        assert was_merged is True
        assert dup_idx == 0
        assert result["_merged"] is True
        assert result["trust_score"] == 0.9

    def test_deduplicate_batch(self):
        """批量去重。"""
        dedup = SemanticDeduplicator(threshold=0.7)
        items = [
            {"content": "Python is a programming language", "timestamp": 100, "trust_score": 0.5},
            {"content": "Python is a programming language", "timestamp": 200, "trust_score": 0.8},
            {"content": "Rust focuses on memory safety", "timestamp": 150, "trust_score": 0.6},
        ]
        kept, merged_count = dedup.deduplicate_batch(items)
        assert merged_count == 1
        assert len(kept) == 2  # Python merged + Rust

    def test_custom_threshold(self):
        """自定义阈值。"""
        dedup_low = SemanticDeduplicator(threshold=0.3)
        dedup_high = SemanticDeduplicator(threshold=0.99)

        existing = [{"content": "Python is a programming language"}]

        # 低阈值: 相似文本会被认为重复
        _, merged_low, _ = dedup_low.deduplicate(
            {"content": "Python is a programming"}, existing
        )
        assert merged_low is True

        # 高阈值: 相似但不完全相同的文本不会被认为重复
        _, merged_high, _ = dedup_high.deduplicate(
            {"content": "Python is a programming"}, existing
        )
        assert merged_high is False

    def test_repr(self):
        """repr 方法。"""
        dedup = SemanticDeduplicator(threshold=0.9)
        assert "SemanticDeduplicator" in repr(dedup)
        assert "0.9" in repr(dedup)
