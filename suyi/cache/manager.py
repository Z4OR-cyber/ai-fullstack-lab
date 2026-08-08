"""缓存管理器 — LRU 淘汰、大小限制、命中统计、JSON 持久化。

CacheManager 整合 ExactCache 和 SemanticCache，提供:
    - 统一的 get/put 接口（先精确匹配，再语义匹配）
    - LRU 淘汰策略（超过最大条目数时淘汰最久未访问的）
    - 大小限制
    - 命中统计
    - 持久化到 JSON 文件

Usage::

    mgr = CacheManager(max_entries=1000, enable_semantic=True)
    mgr.put("What is Python?", "Python is a programming language.")
    entry = mgr.get("What is Python?")  # 精确命中
    entry = mgr.get("What's Python?")    # 语义命中
    mgr.save("cache.json")
    mgr.load("cache.json")
"""

from __future__ import annotations

import json
import os
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .cache import CacheEntry, ExactCache, SemanticCache


@dataclass
class CacheStats:
    """缓存统计信息。"""

    total_entries: int = 0
    exact_entries: int = 0
    semantic_entries: int = 0
    exact_hits: int = 0
    exact_misses: int = 0
    semantic_hits: int = 0
    semantic_misses: int = 0
    total_hits: int = 0
    total_misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.total_hits + self.total_misses
        return self.total_hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_entries": self.total_entries,
            "exact_entries": self.exact_entries,
            "semantic_entries": self.semantic_entries,
            "exact_hits": self.exact_hits,
            "exact_misses": self.exact_misses,
            "semantic_hits": self.semantic_hits,
            "semantic_misses": self.semantic_misses,
            "total_hits": self.total_hits,
            "total_misses": self.total_misses,
            "evictions": self.evictions,
            "hit_rate": round(self.hit_rate, 4),
        }


class CacheManager:
    """缓存管理器 — 整合精确和语义缓存，提供 LRU 淘汰和持久化。

    Args:
        max_entries: 最大缓存条目数。
        ttl: 默认 TTL（秒），0 表示永不过期。
        enable_semantic: 是否启用语义缓存。
        similarity_threshold: 语义缓存相似度阈值。
    """

    def __init__(
        self,
        max_entries: int = 1000,
        ttl: float = 0.0,
        enable_semantic: bool = True,
        similarity_threshold: float = 0.85,
    ) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self.max_entries = max_entries
        self.ttl = ttl
        self.enable_semantic = enable_semantic

        self._exact_cache = ExactCache(ttl=ttl)
        self._semantic_cache: Optional[SemanticCache] = (
            SemanticCache(
                similarity_threshold=similarity_threshold,
                ttl=ttl,
            )
            if enable_semantic
            else None
        )

        # LRU 跟踪：key -> last_access_time
        self._lru: OrderedDict[str, float] = OrderedDict()
        self._evictions = 0

    def get(self, prompt: str) -> Optional[CacheEntry]:
        """查找缓存：先精确匹配，再语义匹配。"""
        # 1. 精确匹配
        entry = self._exact_cache.get(prompt)
        if entry is not None:
            self._touch_lru(entry.key)
            return entry

        # 2. 语义匹配
        if self._semantic_cache is not None:
            entry = self._semantic_cache.get(prompt)
            if entry is not None:
                self._touch_lru(entry.key)
                return entry

        return None

    def put(
        self,
        prompt: str,
        response: str,
        ttl: Optional[float] = None,
    ) -> CacheEntry:
        """存入缓存。"""
        effective_ttl = ttl if ttl is not None else self.ttl
        entry = self._exact_cache.put(prompt, response, ttl=effective_ttl)
        self._touch_lru(entry.key)

        if self._semantic_cache is not None:
            self._semantic_cache.put(prompt, response, ttl=effective_ttl)

        # LRU 淘汰
        self._evict_if_needed()
        return entry

    def invalidate(self, prompt: str) -> bool:
        """使指定 prompt 的缓存失效。"""
        ok1 = self._exact_cache.invalidate(prompt)
        ok2 = False
        if self._semantic_cache is not None:
            ok2 = self._semantic_cache.invalidate(prompt)
        if ok1 or ok2:
            key = self._exact_cache._store  # 内部访问以获取 key
            # 从 LRU 中移除
            # 使用 hash 来匹配
            from .cache import _hash_prompt
            h = _hash_prompt(prompt)
            self._lru.pop(h, None)
            return True
        return False

    def clear(self) -> None:
        """清空所有缓存。"""
        self._exact_cache.clear()
        if self._semantic_cache is not None:
            self._semantic_cache.clear()
        self._lru.clear()
        self._evictions = 0

    def cleanup_expired(self) -> int:
        """清理所有过期条目。"""
        count = self._exact_cache.cleanup_expired()
        if self._semantic_cache is not None:
            count += self._semantic_cache.cleanup_expired()
        # 同步 LRU
        self._rebuild_lru()
        return count

    def get_stats(self) -> CacheStats:
        """获取缓存统计信息。"""
        exact_entries = self._exact_cache.size
        semantic_entries = self._semantic_cache.size if self._semantic_cache else 0
        exact_hits = self._exact_cache.hits
        exact_misses = self._exact_cache.misses
        semantic_hits = self._semantic_cache.hits if self._semantic_cache else 0
        semantic_misses = self._semantic_cache.misses if self._semantic_cache else 0

        return CacheStats(
            total_entries=exact_entries,
            exact_entries=exact_entries,
            semantic_entries=semantic_entries,
            exact_hits=exact_hits,
            exact_misses=exact_misses,
            semantic_hits=semantic_hits,
            semantic_misses=semantic_misses,
            total_hits=exact_hits + semantic_hits,
            total_misses=exact_misses + semantic_misses,
            evictions=self._evictions,
        )

    # ── LRU 管理 ──────────────────────────────────────────────

    def _touch_lru(self, key: str) -> None:
        """更新 LRU 访问时间。"""
        self._lru.pop(key, None)
        self._lru[key] = time.time()

    def _evict_if_needed(self) -> None:
        """如果超过最大条目数，淘汰最久未访问的。"""
        while len(self._lru) > self.max_entries:
            oldest_key, _ = self._lru.popitem(last=False)
            self._exact_cache._store.pop(oldest_key, None)
            if self._semantic_cache is not None:
                # 从语义缓存中移除对应条目
                self._semantic_cache._entries = [
                    e for e in self._semantic_cache._entries if e.key != oldest_key
                ]
                self._semantic_cache._prompts = [
                    p for e, p in zip(self._semantic_cache._entries, self._semantic_cache._prompts)
                    if e.key != oldest_key
                ] if self._semantic_cache._entries else []
                self._semantic_cache._rebuild_index()
            self._evictions += 1

    def _rebuild_lru(self) -> None:
        """从精确缓存重建 LRU。"""
        self._lru.clear()
        for entry in self._exact_cache.entries():
            self._lru[entry.key] = entry.created_at

    # ── 持久化 ────────────────────────────────────────────────

    def save(self, file_path: str) -> None:
        """保存缓存到 JSON 文件。"""
        data = {
            "version": "1.0",
            "max_entries": self.max_entries,
            "ttl": self.ttl,
            "enable_semantic": self.enable_semantic,
            "evictions": self._evictions,
            "entries": [e.to_dict() for e in self._exact_cache.entries()],
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, file_path: str) -> int:
        """从 JSON 文件加载缓存，返回加载的条目数。"""
        if not os.path.exists(file_path):
            return 0
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.clear()
        self.max_entries = data.get("max_entries", self.max_entries)
        self._evictions = data.get("evictions", 0)

        count = 0
        for entry_dict in data.get("entries", []):
            entry = CacheEntry.from_dict(entry_dict)
            self._exact_cache._store[entry.key] = entry
            self._touch_lru(entry.key)
            if self._semantic_cache is not None:
                self._semantic_cache.put(entry.prompt, entry.response, ttl=entry.ttl)
            count += 1

        return count

    @property
    def size(self) -> int:
        return self._exact_cache.size

    @property
    def is_empty(self) -> bool:
        return self.size == 0


__all__ = [
    "CacheManager",
    "CacheStats",
    "CacheEntry",
    "ExactCache",
    "SemanticCache",
]
