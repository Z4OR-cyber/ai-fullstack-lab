"""LLM 响应缓存 — 精确匹配 + 语义缓存 + TTL 过期。

缓存策略:
    1. ExactCache — 基于 prompt hash 的精确匹配缓存
    2. SemanticCache — 基于 TF-IDF 相似度的语义缓存
    3. CacheEntry — 统一缓存条目数据结构

两种缓存都支持 TTL 过期策略。
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ..memory.semantic import _tokenize, TFIDFIndex


# ── 缓存条目 ──────────────────────────────────────────────────

@dataclass
class CacheEntry:
    """缓存条目。

    Attributes:
        key: 缓存键（prompt hash 或语义键）。
        prompt: 原始 prompt 文本。
        response: 缓存的响应内容。
        created_at: 创建时间戳。
        ttl: 生存时间（秒），0 表示永不过期。
        hit_count: 命中次数。
        metadata: 附加元数据。
    """

    key: str
    prompt: str
    response: str
    created_at: float = field(default_factory=time.time)
    ttl: float = 0.0
    hit_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self, now: Optional[float] = None) -> bool:
        """检查是否已过期。"""
        if self.ttl <= 0:
            return False
        current = now or time.time()
        return (current - self.created_at) > self.ttl

    def touch(self) -> None:
        """增加命中次数。"""
        self.hit_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "prompt": self.prompt,
            "response": self.response,
            "created_at": self.created_at,
            "ttl": self.ttl,
            "hit_count": self.hit_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CacheEntry":
        return cls(
            key=d["key"],
            prompt=d.get("prompt", ""),
            response=d.get("response", ""),
            created_at=d.get("created_at", time.time()),
            ttl=d.get("ttl", 0.0),
            hit_count=d.get("hit_count", 0),
            metadata=d.get("metadata", {}),
        )


# ── 辅助函数 ──────────────────────────────────────────────────

def _hash_prompt(prompt: str) -> str:
    """计算 prompt 的 SHA-256 哈希。"""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


# ── 1. 精确匹配缓存 ──────────────────────────────────────────

class ExactCache:
    """精确匹配缓存 — 基于 prompt hash。

    Args:
        ttl: 默认 TTL（秒），0 表示永不过期。
    """

    def __init__(self, ttl: float = 0.0) -> None:
        self.ttl = ttl
        self._store: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0

    def get(self, prompt: str) -> Optional[CacheEntry]:
        """精确查找缓存。"""
        key = _hash_prompt(prompt)
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.is_expired():
            del self._store[key]
            self._misses += 1
            return None
        entry.touch()
        self._hits += 1
        return entry

    def put(self, prompt: str, response: str, ttl: Optional[float] = None) -> CacheEntry:
        """存入缓存。"""
        key = _hash_prompt(prompt)
        entry = CacheEntry(
            key=key,
            prompt=prompt,
            response=response,
            ttl=ttl if ttl is not None else self.ttl,
        )
        self._store[key] = entry
        return entry

    def invalidate(self, prompt: str) -> bool:
        """使指定 prompt 的缓存失效。"""
        key = _hash_prompt(prompt)
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        """清空缓存。"""
        self._store.clear()
        self._hits = 0
        self._misses = 0

    def cleanup_expired(self) -> int:
        """清理过期条目，返回清理数量。"""
        expired_keys = [
            k for k, v in self._store.items() if v.is_expired()
        ]
        for k in expired_keys:
            del self._store[k]
        return len(expired_keys)

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def entries(self) -> List[CacheEntry]:
        """返回所有缓存条目。"""
        return list(self._store.values())


# ── 2. 语义缓存 ──────────────────────────────────────────────

class SemanticCache:
    """语义缓存 — 基于 TF-IDF 相似度匹配。

    对于相似的 prompt，返回之前缓存的响应。

    Args:
        similarity_threshold: 相似度阈值（0~1），高于此值视为命中。
        ttl: 默认 TTL（秒）。
    """

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        ttl: float = 0.0,
    ) -> None:
        if not 0 < similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be in (0, 1]")
        self.similarity_threshold = similarity_threshold
        self.ttl = ttl
        self._entries: List[CacheEntry] = []
        self._tfidf = TFIDFIndex()
        self._prompts: List[str] = []
        self._hits = 0
        self._misses = 0

    def _rebuild_index(self) -> None:
        """重建 TF-IDF 索引。"""
        token_lists = [_tokenize(p) for p in self._prompts]
        self._tfidf.build(token_lists)

    def _compute_similarity(self, query: str) -> List[tuple[int, float]]:
        """计算查询与所有缓存 prompt 的相似度。"""
        if not self._prompts:
            return []
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        results = self._tfidf.search(query_tokens, top_k=len(self._prompts))
        return results

    def get(self, prompt: str) -> Optional[CacheEntry]:
        """语义查找缓存。"""
        if not self._entries:
            self._misses += 1
            return None

        similarities = self._compute_similarity(prompt)
        for idx, score in similarities:
            if idx >= len(self._entries):
                continue
            entry = self._entries[idx]
            if entry.is_expired():
                continue
            if score >= self.similarity_threshold:
                entry.touch()
                self._hits += 1
                return entry

        self._misses += 1
        return None

    def put(self, prompt: str, response: str, ttl: Optional[float] = None) -> CacheEntry:
        """存入缓存。"""
        entry = CacheEntry(
            key=_hash_prompt(prompt),
            prompt=prompt,
            response=response,
            ttl=ttl if ttl is not None else self.ttl,
        )
        self._entries.append(entry)
        self._prompts.append(prompt)
        self._rebuild_index()
        return entry

    def invalidate(self, prompt: str) -> bool:
        """使最相似的缓存条目失效。"""
        similarities = self._compute_similarity(prompt)
        for idx, score in similarities:
            if score >= self.similarity_threshold:
                self._entries.pop(idx)
                self._prompts.pop(idx)
                self._rebuild_index()
                return True
        return False

    def clear(self) -> None:
        """清空缓存。"""
        self._entries.clear()
        self._prompts.clear()
        self._tfidf = TFIDFIndex()
        self._hits = 0
        self._misses = 0

    def cleanup_expired(self) -> int:
        """清理过期条目。"""
        original_len = len(self._entries)
        now = time.time()
        keep = [(e, p) for e, p in zip(self._entries, self._prompts) if not e.is_expired(now)]
        if keep:
            self._entries, self._prompts = zip(*keep)
            self._entries = list(self._entries)
            self._prompts = list(self._prompts)
        else:
            self._entries = []
            self._prompts = []
        self._rebuild_index()
        return original_len - len(self._entries)

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def entries(self) -> List[CacheEntry]:
        return list(self._entries)


__all__ = [
    "CacheEntry",
    "ExactCache",
    "SemanticCache",
]
