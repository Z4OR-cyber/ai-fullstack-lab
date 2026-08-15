"""旁路知识存储层 — LearnedKnowledgeStore.

旁路知识层（Bypass Knowledge Layer）的核心存储。每条知识是一条
"可复用规则"，以自然语言形式存在，可直接注入 prompt。

设计原则（来自双循环架构图）：
- **代码与数据分离**：主干 skill（代码）稳定不动，所有进化发生在
  旁路知识（数据），通过检索反哺内循环。
- **稳定与进化分离**：策略代码不被频繁改写，易变的经验沉淀为数据。
- **纯 JSON 持久化**：便于人工 review 与版本管理，与现有
  learner / feedback 模块保持一致。

条目类别（category）：
    - ``success_pattern``: 成功模式（正样本蒸馏）
    - ``failure_lesson``: 失败教训（负样本提取）
    - ``guideline``: 通用原则/准则（稳定，每次注入）
    - ``style``: 风格/专项技能（按任务类型路由）

Usage::

    from suyi.evolution.learned import LearnedKnowledgeStore, KnowledgeEntry

    store = LearnedKnowledgeStore()
    entry_id = store.add(KnowledgeEntry(
        bureau="default",
        category="success_pattern",
        title="文件读取成功模式",
        content="读取文件时优先使用 read_file 工具...",
        source_ids=["int_abc"],
        confidence=0.6,
        tags=["file", "read"],
    ))
    store.save("data/learned/knowledge.json")
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# 允许的知识类别
VALID_CATEGORIES = frozenset({
    "success_pattern",
    "failure_lesson",
    "guideline",
    "style",
})


@dataclass
class KnowledgeEntry:
    """一条可复用的旁路知识条目.

    Attributes:
        id: 唯一标识符（``kn_xxx``，自动生成）.
        bureau: 业务域/租户，默认 ``"default"``，用于多租户隔离.
        category: 知识类别，见 :data:`VALID_CATEGORIES`.
        title: 简短标题.
        content: 规则正文（可直接注入 prompt 的自然语言）.
        source_ids: 来源样本 ID 列表（哪些交互案例蒸馏出这条）.
        confidence: 置信度 0-1，基于来源数量和质量.
        usage_count: 被检索召回的次数.
        success_count: 召回后任务成功的次数.
        created_at: 创建时间戳.
        updated_at: 最后更新时间戳.
        tags: 标签列表，用于按标签过滤/路由.
        embedding: TF-IDF 向量缓存（可选，不参与 JSON 往返时也可保留）.
    """

    id: str = ""
    bureau: str = "default"
    category: str = "guideline"
    title: str = ""
    content: str = ""
    source_ids: List[str] = field(default_factory=list)
    confidence: float = 0.5
    usage_count: int = 0
    success_count: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0
    tags: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = f"kn_{uuid.uuid4().hex[:12]}"
        now = time.time()
        if self.created_at == 0.0:
            self.created_at = now
        if self.updated_at == 0.0:
            self.updated_at = now
        # 置信度钳制到 [0, 1]
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    @property
    def success_rate(self) -> float:
        """召回后任务成功率（无召回记录时返回 0.0）."""
        if self.usage_count <= 0:
            return 0.0
        return self.success_count / self.usage_count

    def to_dict(self) -> dict:
        """转换为字典（用于 JSON 序列化）."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KnowledgeEntry":
        """从字典创建实例，容忍缺失/多余字段."""
        # 只取构造器已知字段，向前兼容旧数据
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in d.items() if k in known}
        return cls(**filtered)

    def __repr__(self) -> str:
        return (
            f"KnowledgeEntry(id={self.id!r}, category={self.category!r}, "
            f"title={self.title!r}, confidence={self.confidence:.2f})"
        )


class LearnedKnowledgeStore:
    """旁路知识存储 — 内存 dict + JSON 文件持久化.

    支持两种使用模式：
        1. 纯内存模式（测试用）：``store = LearnedKnowledgeStore()``
        2. 文件持久化模式：``store = LearnedKnowledgeStore("path/to/dir")``
           或显式调用 :meth:`save` / :meth:`load`.

    数据结构为 ``dict[entry_id, KnowledgeEntry]``，所有查询操作
    返回条目副本或列表副本，避免外部直接修改内部状态。
    """

    def __init__(self, storage_dir: Optional[str] = None) -> None:
        """
        Args:
            storage_dir: 可选的持久化目录。若提供，store 会在该目录下
                维护 ``learned_knowledge.json``，并在初始化时自动加载。
        """
        self.storage_dir = storage_dir
        self._entries: Dict[str, KnowledgeEntry] = {}
        self._storage_file = "learned_knowledge.json"

        if storage_dir is not None:
            os.makedirs(storage_dir, exist_ok=True)
            self.load()

    # ── 增删改查 ──────────────────────────────────────────

    def add(self, entry: KnowledgeEntry) -> str:
        """添加一条知识条目.

        若条目未设置 ID/时间戳，会自动生成。若 ID 已存在则覆盖。

        Args:
            entry: 知识条目.

        Returns:
            条目的 ID.
        """
        # 确保 ID 存在（触发 __post_init__）
        if not entry.id:
            entry.__post_init__()
        entry.updated_at = time.time()
        self._entries[entry.id] = entry
        self._maybe_save()
        return entry.id

    def get(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """根据 ID 获取条目（不存在返回 None）."""
        return self._entries.get(entry_id)

    def update(self, entry_id: str, **fields: Any) -> Optional[KnowledgeEntry]:
        """更新指定条目的字段.

        Args:
            entry_id: 条目 ID.
            **fields: 要更新的字段名和值（如 ``confidence=0.8``）.

        Returns:
            更新后的条目；条目不存在时返回 None.
        """
        entry = self._entries.get(entry_id)
        if entry is None:
            return None
        for key, value in fields.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        entry.updated_at = time.time()
        # 置信度钳制
        entry.confidence = max(0.0, min(1.0, float(entry.confidence)))
        self._maybe_save()
        return entry

    def delete(self, entry_id: str) -> bool:
        """删除一条知识.

        Args:
            entry_id: 条目 ID.

        Returns:
            是否删除成功（条目存在并被删除）.
        """
        if entry_id in self._entries:
            del self._entries[entry_id]
            self._maybe_save()
            return True
        return False

    def list(
        self,
        bureau: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[KnowledgeEntry]:
        """按条件过滤列出知识条目.

        Args:
            bureau: 仅返回该业务域的条目（None 表示不过滤）.
            category: 仅返回该类别的条目.
            tags: 仅返回 **包含全部** 指定标签的条目.

        Returns:
            匹配的条目列表（按创建时间升序）.
        """
        result: List[KnowledgeEntry] = []
        tag_set = set(tags) if tags else None
        for entry in self._entries.values():
            if bureau is not None and entry.bureau != bureau:
                continue
            if category is not None and entry.category != category:
                continue
            if tag_set is not None and not tag_set.issubset(set(entry.tags)):
                continue
            result.append(entry)
        result.sort(key=lambda e: e.created_at)
        return result

    def all(self) -> List[KnowledgeEntry]:
        """返回全部条目（按创建时间升序）."""
        return self.list()

    def count(self) -> int:
        """返回条目总数."""
        return len(self._entries)

    def increment_usage(self, entry_id: str, success: bool = False) -> None:
        """召回后更新使用统计.

        Args:
            entry_id: 被召回的条目 ID.
            success: 本次召回后任务是否成功.
        """
        entry = self._entries.get(entry_id)
        if entry is None:
            return
        entry.usage_count += 1
        if success:
            entry.success_count += 1
        entry.updated_at = time.time()
        self._maybe_save()

    def clear(self) -> None:
        """清空全部条目（主要用于测试）."""
        self._entries.clear()
        self._maybe_save()

    # ── 持久化 ────────────────────────────────────────────

    @property
    def storage_path(self) -> Optional[str]:
        """当前持久化文件的完整路径（未配置目录时返回 None）."""
        if self.storage_dir is None:
            return None
        return os.path.join(self.storage_dir, self._storage_file)

    def save(self, path: Optional[str] = None) -> str:
        """保存全部知识到 JSON 文件.

        Args:
            path: 目标文件路径。为 None 时使用
                ``storage_dir/learned_knowledge.json``.

        Returns:
            实际写入的文件路径.
        """
        if path is None:
            if self.storage_dir is None:
                raise ValueError(
                    "未配置 storage_dir，必须显式传入 path 参数"
                )
            path = os.path.join(self.storage_dir, self._storage_file)

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        data = {
            "version": 1,
            "entries": [e.to_dict() for e in self._entries.values()],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def load(self, path: Optional[str] = None) -> int:
        """从 JSON 文件加载知识（合并到当前存储，不覆盖已有 ID）.

        Args:
            path: 源文件路径。为 None 时使用
                ``storage_dir/learned_knowledge.json``.

        Returns:
            加载的条目数量.
        """
        if path is None:
            if self.storage_dir is None:
                return 0
            path = os.path.join(self.storage_dir, self._storage_file)

        if not os.path.isfile(path):
            return 0

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return 0

        entries_data = data.get("entries", data) if isinstance(data, dict) else data
        loaded = 0
        for item in entries_data:
            try:
                entry = KnowledgeEntry.from_dict(item)
            except (TypeError, ValueError):
                continue
            # 已存在的 ID 不覆盖（以内存最新状态为准）
            if entry.id not in self._entries:
                self._entries[entry.id] = entry
                loaded += 1
        return loaded

    # ── 内部方法 ──────────────────────────────────────────

    def _maybe_save(self) -> None:
        """配置了持久化目录时自动保存."""
        if self.storage_dir is not None:
            try:
                self.save()
            except OSError:
                # 持久化失败不应中断内存操作
                pass
