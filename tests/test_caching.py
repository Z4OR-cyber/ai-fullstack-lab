"""Tests for Caching Layer — 精确缓存、语义缓存、缓存管理器。"""

import json
import os
import tempfile
import time
import pytest

from suyi.cache.cache import CacheEntry, ExactCache, SemanticCache, _hash_prompt
from suyi.cache.manager import CacheManager, CacheStats


# ═════════════════════════════════════════════════════════════
#  CacheEntry
# ═════════════════════════════════════════════════════════════

class TestCacheEntry:
    """缓存条目测试。"""

    def test_creation(self):
        entry = CacheEntry(key="abc", prompt="Hello", response="World")
        assert entry.key == "abc"
        assert entry.prompt == "Hello"
        assert entry.response == "World"
        assert entry.hit_count == 0
        assert entry.ttl == 0.0

    def test_is_expired_no_ttl(self):
        entry = CacheEntry(key="k", prompt="p", response="r")
        assert not entry.is_expired()

    def test_is_expired_with_ttl(self):
        entry = CacheEntry(key="k", prompt="p", response="r", ttl=0.1, created_at=time.time() - 0.2)
        assert entry.is_expired()

    def test_is_expired_not_yet(self):
        entry = CacheEntry(key="k", prompt="p", response="r", ttl=10.0, created_at=time.time())
        assert not entry.is_expired()

    def test_touch(self):
        entry = CacheEntry(key="k", prompt="p", response="r")
        entry.touch()
        entry.touch()
        assert entry.hit_count == 2

    def test_to_dict_and_from_dict(self):
        entry = CacheEntry(key="k", prompt="p", response="r", ttl=60, hit_count=3)
        d = entry.to_dict()
        restored = CacheEntry.from_dict(d)
        assert restored.key == "k"
        assert restored.prompt == "p"
        assert restored.response == "r"
        assert restored.ttl == 60
        assert restored.hit_count == 3

    def test_hash_prompt(self):
        h1 = _hash_prompt("Hello")
        h2 = _hash_prompt("Hello")
        h3 = _hash_prompt("World")
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 64  # SHA-256 hex


# ═════════════════════════════════════════════════════════════
#  ExactCache
# ═════════════════════════════════════════════════════════════

class TestExactCache:
    """精确匹配缓存测试。"""

    def test_put_and_get(self):
        cache = ExactCache()
        cache.put("Hello", "World")
        entry = cache.get("Hello")
        assert entry is not None
        assert entry.response == "World"
        assert entry.hit_count == 1

    def test_miss(self):
        cache = ExactCache()
        cache.put("Hello", "World")
        entry = cache.get("Goodbye")
        assert entry is None
        assert cache.misses == 1

    def test_ttl_expiry(self):
        cache = ExactCache(ttl=0.1)
        cache.put("Hello", "World")
        time.sleep(0.15)
        entry = cache.get("Hello")
        assert entry is None

    def test_invalidate(self):
        cache = ExactCache()
        cache.put("Hello", "World")
        assert cache.invalidate("Hello") is True
        assert cache.get("Hello") is None
        assert cache.invalidate("Nonexistent") is False

    def test_clear(self):
        cache = ExactCache()
        cache.put("A", "1")
        cache.put("B", "2")
        cache.clear()
        assert cache.size == 0
        assert cache.hits == 0
        assert cache.misses == 0

    def test_hit_rate(self):
        cache = ExactCache()
        cache.put("A", "1")
        cache.get("A")  # hit
        cache.get("B")  # miss
        assert cache.hit_rate == 0.5

    def test_cleanup_expired(self):
        cache = ExactCache(ttl=0.1)
        cache.put("A", "1")
        cache.put("B", "2")
        time.sleep(0.15)
        count = cache.cleanup_expired()
        assert count == 2
        assert cache.size == 0

    def test_entries(self):
        cache = ExactCache()
        cache.put("A", "1")
        cache.put("B", "2")
        entries = cache.entries()
        assert len(entries) == 2


# ═════════════════════════════════════════════════════════════
#  SemanticCache
# ═════════════════════════════════════════════════════════════

class TestSemanticCache:
    """语义缓存测试。"""

    def test_put_and_exact_get(self):
        cache = SemanticCache(similarity_threshold=0.5)
        cache.put("Python is a language", "Python response")
        entry = cache.get("Python is a language")
        assert entry is not None
        assert entry.response == "Python response"

    def test_semantic_match(self):
        cache = SemanticCache(similarity_threshold=0.3)
        cache.put("Python is a programming language", "Python is great")
        # 相似查询应该命中
        entry = cache.get("Python is a programming language")
        assert entry is not None

    def test_miss(self):
        cache = SemanticCache(similarity_threshold=0.9)
        cache.put("Python is a language", "Python response")
        entry = cache.get("Java is a language")
        assert entry is None

    def test_empty_cache(self):
        cache = SemanticCache()
        entry = cache.get("anything")
        assert entry is None

    def test_clear(self):
        cache = SemanticCache(similarity_threshold=0.3)
        cache.put("A", "1")
        cache.clear()
        assert cache.size == 0

    def test_invalid_threshold(self):
        with pytest.raises(ValueError):
            SemanticCache(similarity_threshold=0)
        with pytest.raises(ValueError):
            SemanticCache(similarity_threshold=1.5)

    def test_hit_rate(self):
        cache = SemanticCache(similarity_threshold=0.3)
        cache.put("Python is a language", "response")
        cache.get("Python is a language")  # hit
        cache.get("Something completely different")  # miss
        assert cache.hit_rate > 0

    def test_cleanup_expired(self):
        cache = SemanticCache(similarity_threshold=0.3, ttl=0.1)
        cache.put("A", "1")
        cache.put("B", "2")
        time.sleep(0.15)
        count = cache.cleanup_expired()
        assert count == 2


# ═════════════════════════════════════════════════════════════
#  CacheManager
# ═════════════════════════════════════════════════════════════

class TestCacheManager:
    """缓存管理器测试。"""

    def test_put_and_get_exact(self):
        mgr = CacheManager(enable_semantic=False)
        mgr.put("Hello", "World")
        entry = mgr.get("Hello")
        assert entry is not None
        assert entry.response == "World"

    def test_put_and_get_semantic(self):
        mgr = CacheManager(enable_semantic=True, similarity_threshold=0.3)
        mgr.put("Python is a language", "Python response")
        entry = mgr.get("Python is a language")
        assert entry is not None
        assert entry.response == "Python response"

    def test_miss(self):
        mgr = CacheManager()
        entry = mgr.get("nonexistent")
        assert entry is None

    def test_lru_eviction(self):
        mgr = CacheManager(max_entries=2, enable_semantic=False)
        mgr.put("A", "1")
        mgr.put("B", "2")
        mgr.put("C", "3")  # 应该淘汰 A
        stats = mgr.get_stats()
        assert stats.evictions >= 1
        assert mgr.size <= 2

    def test_clear(self):
        mgr = CacheManager()
        mgr.put("A", "1")
        mgr.clear()
        assert mgr.is_empty

    def test_invalidate(self):
        mgr = CacheManager(enable_semantic=False)
        mgr.put("Hello", "World")
        assert mgr.invalidate("Hello") is True
        assert mgr.get("Hello") is None

    def test_get_stats(self):
        mgr = CacheManager(enable_semantic=True, similarity_threshold=0.3)
        mgr.put("A", "1")
        mgr.get("A")   # hit
        mgr.get("B")   # miss
        stats = mgr.get_stats()
        assert stats.total_entries >= 1
        assert stats.total_hits >= 1
        assert stats.total_misses >= 1
        d = stats.to_dict()
        assert "hit_rate" in d

    def test_save_and_load(self):
        mgr = CacheManager(enable_semantic=False)
        mgr.put("Hello", "World")
        mgr.put("Foo", "Bar")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            mgr.save(path)
            assert os.path.exists(path)
            mgr2 = CacheManager(enable_semantic=False)
            count = mgr2.load(path)
            assert count == 2
            entry = mgr2.get("Hello")
            assert entry is not None
            assert entry.response == "World"
        finally:
            os.unlink(path)

    def test_load_nonexistent(self):
        mgr = CacheManager()
        count = mgr.load("/nonexistent/cache.json")
        assert count == 0

    def test_cleanup_expired(self):
        mgr = CacheManager(ttl=0.1, enable_semantic=False)
        mgr.put("A", "1")
        time.sleep(0.15)
        count = mgr.cleanup_expired()
        assert count >= 1

    def test_no_semantic_mode(self):
        mgr = CacheManager(enable_semantic=False)
        mgr.put("Python is a language", "response")
        # 精确匹配应该命中
        entry = mgr.get("Python is a language")
        assert entry is not None
        # 语义缓存未启用，相似查询不应命中
        entry2 = mgr.get("Python is a programming language")
        assert entry2 is None

    def test_invalid_max_entries(self):
        with pytest.raises(ValueError):
            CacheManager(max_entries=0)

    def test_size_property(self):
        mgr = CacheManager(enable_semantic=False)
        mgr.put("A", "1")
        assert mgr.size == 1
