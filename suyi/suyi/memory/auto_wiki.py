"""Auto Wiki Layer — 自动知识整理，从会话和事实中提取概念/实体关系。

从会话历史和结构化事实中提取概念、实体及其关系，
整理为结构化 Wiki 页面。Wiki 页面可以用于:
    - 快速知识回顾
    - 跨会话知识迁移
    - 为 LLM 提供结构化背景知识

Wiki 结构:
    - WikiPage: 单个主题页面，包含标题、摘要、相关实体、详细内容
    - AutoWiki: 管理多个 WikiPage 的管理器
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .semantic import _tokenize


# ── 简单停用词表 ──────────────────────────────────────────────

_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "to", "of", "in",
    "on", "at", "by", "for", "with", "about", "as", "and", "but", "or",
    "so", "if", "because", "when", "while", "i", "you", "he", "she",
    "it", "we", "they", "this", "that", "these", "those", "what",
    "which", "who", "how", "why", "where", "there", "here", "not", "no",
    "yes", "的", "了", "是", "在", "我", "你", "他", "她", "它",
    "们", "和", "与", "或", "但", "也", "都", "就", "还", "又",
    "这", "那", "些", "个", "中", "上", "下", "吗", "呢", "吧",
    "啊", "哦", "嗯",
})


@dataclass
class WikiPage:
    """单个 Wiki 页面。

    Attributes:
        id: 唯一标识符。
        title: 页面标题（通常是概念或实体名）。
        summary: 页面摘要。
        content: 详细内容。
        related_entities: 相关实体列表。
        tags: 标签列表。
        created_at: 创建时间。
        updated_at: 更新时间。
        source_facts: 来源事实 ID 列表。
    """

    title: str
    summary: str = ""
    content: str = ""
    related_entities: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    source_facts: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "related_entities": self.related_entities,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_facts": self.source_facts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WikiPage":
        """从字典重建。"""
        return cls(
            title=data["title"],
            summary=data.get("summary", ""),
            content=data.get("content", ""),
            related_entities=data.get("related_entities", []),
            tags=data.get("tags", []),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            source_facts=data.get("source_facts", []),
            id=data.get("id", str(uuid.uuid4())),
        )

    def __repr__(self) -> str:
        return f"WikiPage(title={self.title!r}, tags={self.tags})"


class AutoWiki:
    """自动知识整理器 — 从会话和事实中提取结构化 Wiki。

    工作流程:
        1. 收集会话消息和结构化事实
        2. 提取概念和实体（基于词频和共现）
        3. 将相关事实聚类为 Wiki 页面
        4. 生成页面摘要和关系链接

    Attributes:
        storage_path: JSON 持久化文件路径。
        pages: 存储的 WikiPage 列表。
    """

    def __init__(self, storage_path: Optional[str] = None) -> None:
        self.storage_path = storage_path
        self.pages: List[WikiPage] = []
        # 内部缓存: 概念频率统计
        self._concept_freq: Dict[str, int] = {}
        # 内部缓存: 实体共现统计
        self._co_occurrence: Dict[str, Dict[str, int]] = {}
        if storage_path:
            self._load()

    # ── 知识输入 ──────────────────────────────────────────────

    def add_session(
        self,
        messages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """从会话消息中提取概念和关系。

        Args:
            messages: 会话消息列表。

        Returns:
            提取统计信息。
        """
        stats: Dict[str, Any] = {
            "messages_processed": 0,
            "concepts_extracted": 0,
            "relations_found": 0,
        }

        for msg in messages:
            content = msg.get("content", "")
            if not content or len(content) < 5:
                continue

            stats["messages_processed"] += 1
            tokens = _tokenize(content)
            keywords = [
                t for t in tokens
                if t not in _STOP_WORDS and len(t) >= 2
            ]

            # 更新概念频率
            seen: Set[str] = set()
            for kw in keywords:
                if kw not in seen:
                    self._concept_freq[kw] = self._concept_freq.get(kw, 0) + 1
                    seen.add(kw)
                    stats["concepts_extracted"] += 1

            # 更新共现统计
            unique_kws = list(seen)
            for i in range(len(unique_kws)):
                for j in range(i + 1, len(unique_kws)):
                    a, b = unique_kws[i], unique_kws[j]
                    if a not in self._co_occurrence:
                        self._co_occurrence[a] = {}
                    if b not in self._co_occurrence:
                        self._co_occurrence[b] = {}
                    self._co_occurrence[a][b] = self._co_occurrence[a].get(b, 0) + 1
                    self._co_occurrence[b][a] = self._co_occurrence[b].get(a, 0) + 1
                    stats["relations_found"] += 1

        return stats

    def add_facts(
        self,
        facts: List[Any],
    ) -> Dict[str, Any]:
        """从结构化事实中构建 Wiki 页面。

        Args:
            facts: StructuredFact 对象列表。

        Returns:
            构建统计信息。
        """
        stats: Dict[str, Any] = {
            "facts_processed": 0,
            "pages_created": 0,
            "pages_updated": 0,
        }

        # 按实体分组
        entity_facts: Dict[str, List[Any]] = {}
        for fact in facts:
            entity = getattr(fact, "entity", None) or str(fact)
            if entity not in entity_facts:
                entity_facts[entity] = []
            entity_facts[entity].append(fact)
            stats["facts_processed"] += 1

        # 为每个实体创建/更新 Wiki 页面
        for entity, entity_fact_list in entity_facts.items():
            existing = self._find_page(entity)

            # 构建内容
            content_lines: List[str] = []
            related: Set[str] = set()
            source_ids: List[str] = []

            for f in entity_fact_list:
                attr = getattr(f, "attribute", "unknown")
                val = getattr(f, "value", "")
                fid = getattr(f, "id", "")
                trust = getattr(f, "trust_score", 0.5)

                content_lines.append(f"- {attr}: {val} (trust={trust:.2f})")
                if fid:
                    source_ids.append(fid)
                # 提取值中的相关实体
                val_tokens = _tokenize(str(val))
                for t in val_tokens:
                    if t != entity.lower() and len(t) >= 2 and t not in _STOP_WORDS:
                        related.add(t)

            content = "\n".join(content_lines)
            summary = f"{entity} has {len(entity_fact_list)} known attributes."

            if existing:
                # 更新现有页面
                existing.content = content
                existing.summary = summary
                existing.related_entities = list(
                    set(existing.related_entities) | related
                )
                existing.source_facts = list(
                    set(existing.source_facts) | set(source_ids)
                )
                existing.updated_at = time.time()
                stats["pages_updated"] += 1
            else:
                # 创建新页面
                page = WikiPage(
                    title=entity,
                    summary=summary,
                    content=content,
                    related_entities=list(related),
                    tags=["auto_generated"],
                    source_facts=source_ids,
                )
                self.pages.append(page)
                stats["pages_created"] += 1

        self._save()
        return stats

    # ── Wiki 查询 ─────────────────────────────────────────────

    def get_page(self, title: str) -> Optional[WikiPage]:
        """按标题获取页面。"""
        for p in self.pages:
            if p.title == title:
                return p
        return None

    def get_page_by_id(self, page_id: str) -> Optional[WikiPage]:
        """按 ID 获取页面。"""
        for p in self.pages:
            if p.id == page_id:
                return p
        return None

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """检索相关 Wiki 页面。

        使用关键词匹配进行检索。

        Args:
            query: 查询文本。
            top_k: 最大返回数。

        Returns:
            页面字典列表，附带 score 和 layer 字段。
        """
        if not self.pages:
            return []

        query_tokens = set(
            t for t in _tokenize(query)
            if t not in _STOP_WORDS and len(t) >= 2
        )

        if not query_tokens:
            return []

        scored: List[tuple[float, WikiPage]] = []
        for page in self.pages:
            # 标题匹配权重高
            title_tokens = set(_tokenize(page.title))
            content_tokens = set(_tokenize(page.content))
            related_tokens = set(
                t for ent in page.related_entities for t in _tokenize(ent)
            )

            title_hits = len(query_tokens & title_tokens)
            content_hits = len(query_tokens & content_tokens)
            related_hits = len(query_tokens & related_tokens)

            score = title_hits * 3.0 + content_hits * 1.0 + related_hits * 0.5
            if score > 0:
                scored.append((score, page))

        scored.sort(key=lambda x: x[0], reverse=True)

        results: List[Dict[str, Any]] = []
        for score, page in scored[:top_k]:
            d = page.to_dict()
            d["score"] = round(score, 4)
            d["layer"] = "wiki"
            results.append(d)

        return results

    def build_wiki(self) -> Dict[str, Any]:
        """构建/重建整个 Wiki，返回统计信息。

        基于已收集的概念频率和共现统计，
        为高频概念创建 Wiki 页面。

        Returns:
            构建统计信息。
        """
        stats: Dict[str, Any] = {
            "pages_before": len(self.pages),
            "pages_created": 0,
            "top_concepts": [],
        }

        # 按频率排序概念
        sorted_concepts = sorted(
            self._concept_freq.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        stats["top_concepts"] = [
            {"concept": c, "frequency": f}
            for c, f in sorted_concepts[:10]
        ]

        # 为高频概念创建页面（频率 >= 3）
        for concept, freq in sorted_concepts:
            if freq < 3:
                break
            if self._find_page(concept):
                continue

            # 获取共现实体
            related = sorted(
                self._co_occurrence.get(concept, {}).items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]

            related_names = [r[0] for r in related]

            page = WikiPage(
                title=concept,
                summary=f"概念 '{concept}' 在会话中出现 {freq} 次。",
                content=f"概念: {concept}\n出现频率: {freq}\n相关概念: {', '.join(related_names)}",
                related_entities=related_names,
                tags=["auto_generated", "concept"],
            )
            self.pages.append(page)
            stats["pages_created"] += 1

        stats["pages_after"] = len(self.pages)
        self._save()
        return stats

    # ── 页面管理 ──────────────────────────────────────────────

    def delete_page(self, page_id: str) -> bool:
        """删除页面。"""
        for i, p in enumerate(self.pages):
            if p.id == page_id:
                self.pages.pop(i)
                self._save()
                return True
        return False

    def get_all_pages(self) -> List[WikiPage]:
        """返回所有页面。"""
        return list(self.pages)

    def _find_page(self, title: str) -> Optional[WikiPage]:
        """查找指定标题的页面（大小写不敏感）。"""
        title_lower = title.lower()
        for p in self.pages:
            if p.title.lower() == title_lower:
                return p
        return None

    # ── 持久化 ────────────────────────────────────────────────

    def _save(self) -> None:
        if not self.storage_path:
            return
        os.makedirs(os.path.dirname(self.storage_path) or ".", exist_ok=True)
        data = {
            "pages": [p.to_dict() for p in self.pages],
            "concept_freq": self._concept_freq,
            "co_occurrence": self._co_occurrence,
        }
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.pages = [
                WikiPage.from_dict(d) for d in data.get("pages", [])
            ]
            self._concept_freq = data.get("concept_freq", {})
            self._co_occurrence = data.get("co_occurrence", {})
        except (json.JSONDecodeError, KeyError):
            self.pages = []

    def save(self) -> None:
        """公开保存方法。"""
        self._save()

    def __len__(self) -> int:
        return len(self.pages)

    def __repr__(self) -> str:
        return f"AutoWiki(pages={len(self.pages)})"


__all__ = [
    "WikiPage",
    "AutoWiki",
]
