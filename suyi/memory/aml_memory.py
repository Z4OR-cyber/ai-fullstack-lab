"""AML 专用记忆管理器 — 多用户/多会话记忆存储与路由。

本模块实现 :class:`AMLMemoryStore`，为 AML（Agent Memory Leaderboard）
评测提供多租户记忆管理能力：

- **多用户多会话隔离**：以 ``(user_id, session_id)`` 为分区键。
- **三层记忆路由**：working（当前会话最近 N 条）、episodic（跨会话历史）、
  semantic（从对话中提取的关键词/事实/规则/偏好）。
- **混合检索**：基于 :class:`~suyi.memory.hybrid_retriever.HybridRetriever`
  的 BM25 + Dense RRF 融合，跨层检索后统一排序。
- **内容去重**：基于 SHA-256 内容哈希，避免重复存储同一条记忆。
- **TTL 与容量管理**：支持记忆条目过期和每层容量上限。
- **JSON 持久化**：默认存储到 ``~/.suyi/aml_memory/``。

注意：semantic 层的"事实/规则/偏好提取"采用简单的关键词和句式规则，
**不调用任何外部 LLM**，符合 AML 评测约束。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple

from .hybrid_retriever import AMLHybridRetriever as HybridRetriever, RetrievalResult

# v1.10.0: MemRL utility 重排器（可选，延迟导入以避免循环依赖）
from .utility_reranker import UtilityReranker, RerankCandidate


# ----------------------------------------------------------------------
#  常量
# ----------------------------------------------------------------------

# 三层记忆名称
LAYER_WORKING = "working"
LAYER_EPISODIC = "episodic"
LAYER_SEMANTIC = "semantic"

# 各层默认容量（条目数）
DEFAULT_WORKING_CAPACITY = 50
DEFAULT_EPISODIC_CAPACITY = 5000
DEFAULT_SEMANTIC_CAPACITY = 2000

# 默认 TTL（秒），0 表示永不过期
DEFAULT_WORKING_TTL = 24 * 3600          # 1 天
DEFAULT_EPISODIC_TTL = 30 * 24 * 3600    # 30 天
DEFAULT_SEMANTIC_TTL = 90 * 24 * 3600    # 90 天

# 用于提取 semantic 事实的关键词模式
_FACT_KEYWORDS = [
    "my name is", "i am", "i'm", "i like", "i prefer", "i love",
    "i hate", "i live", "i work", "my favorite", "my favourite",
    "remember that", "don't forget", "note that", "the rule is",
    "always", "never",
]

_PREFERENCE_PATTERNS = [
    re.compile(r"i (?:like|love|prefer|enjoy)\s+(.+)", re.IGNORECASE),
    re.compile(r"my (?:favorite|favourite) .+? is\s+(.+)", re.IGNORECASE),
    re.compile(r"i (?:hate|dislike)\s+(.+)", re.IGNORECASE),
    re.compile(r"my name is\s+(.+)", re.IGNORECASE),
    re.compile(r"i(?:'m| am)\s+(.+)", re.IGNORECASE),
    re.compile(r"i (?:live|work) (?:in|at)\s+(.+)", re.IGNORECASE),
]

_RULE_PATTERNS = [
    re.compile(r"(?:remember that|note that|don'?t forget)\s+(.+)",
               re.IGNORECASE),
    re.compile(r"(?:always|never)\s+(.+)", re.IGNORECASE),
    re.compile(r"the rule is\s+(.+)", re.IGNORECASE),
]


# ----------------------------------------------------------------------
#  记忆条目
# ----------------------------------------------------------------------

@dataclass
class MemoryRecord:
    """单条记忆条目。

    Attributes:
        id: 内容哈希生成的唯一 ID。
        user_id: 用户 ID。
        session_id: 会话 ID。
        layer: 记忆层（working / episodic / semantic）。
        role: 消息角色（user / assistant / system）。
        content: 文本内容。
        timestamp: 消息原始时间戳（Unix 秒）。
        added_at: 入库时间戳。
        ttl: 过期时间（秒），0 表示永不过期。
        metadata: 附加元数据。
        score: 检索得分（检索时填充，不持久化）。
    """

    id: str
    user_id: str
    session_id: str
    layer: str
    role: str
    content: str
    timestamp: float
    added_at: float = field(default_factory=time.time)
    ttl: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    # v1.10.0: MemRL utility 重排器使用的访问计数，每次 search 命中 +1
    access_count: int = 0
    last_accessed_at: float = 0.0

    @property
    def is_expired(self) -> bool:
        """是否已过期。"""
        if self.ttl <= 0:
            return False
        return (time.time() - self.added_at) > self.ttl

    def content_hash(self) -> str:
        """计算内容哈希（不含 score 等运行时字段）。"""
        payload = f"{self.user_id}|{self.session_id}|{self.role}|{self.content}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 友好的字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryRecord":
        """从字典反序列化。"""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            session_id=data["session_id"],
            layer=data["layer"],
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", time.time()),
            added_at=data.get("added_at", time.time()),
            ttl=data.get("ttl", 0.0),
            metadata=data.get("metadata", {}),
            score=0.0,
            access_count=int(data.get("access_count", 0)),
            last_accessed_at=float(data.get("last_accessed_at", 0.0)),
        )


# ----------------------------------------------------------------------
#  语义提取（纯规则，不调 LLM）
# ----------------------------------------------------------------------

def extract_semantic_facts(content: str, role: str) -> List[str]:
    """从一条消息中提取可能的 semantic 记忆（事实/规则/偏好）。

    采用简单的关键词和正则模式匹配，不依赖任何外部模型。
    仅对 user 消息进行提取（assistant 的回复通常不需要作为事实记忆）。

    Args:
        content: 消息文本。
        role: 消息角色。

    Returns:
        提取到的事实/规则/偏好文本列表（可能为空）。
    """
    if role != "user" or not content:
        return []

    text = content.strip()
    if len(text) < 3:
        return []

    facts: List[str] = []
    text_lower = text.lower()

    # 关键词触发：包含特定短语时整句作为事实
    for kw in _FACT_KEYWORDS:
        if kw in text_lower:
            facts.append(text)
            break

    # 正则模式提取
    for pattern in _PREFERENCE_PATTERNS + _RULE_PATTERNS:
        match = pattern.search(text)
        if match:
            extracted = match.group(0).strip()
            if extracted and extracted not in facts:
                facts.append(extracted)

    # 去重并限制长度
    seen: Set[str] = set()
    unique: List[str] = []
    for f in facts:
        f_norm = f.lower()
        if f_norm not in seen and len(f) <= 500:
            seen.add(f_norm)
            unique.append(f)

    return unique


# ----------------------------------------------------------------------
#  AMLMemoryStore
# ----------------------------------------------------------------------

class AMLMemoryStore:
    """AML 评测专用的多租户记忆存储器。

    为每个 ``(user_id, session_id)`` 维护独立的三层记忆，并提供统一的
    混合检索接口。内部使用 :class:`HybridRetriever` 进行 BM25 + Dense
    RRF 检索。

    架构概览::

        ┌─────────────────────────────────────────┐
        │              AMLMemoryStore              │
        │  ┌───────────────────────────────────┐  │
        │  │  records: Dict[record_id, Record]  │  │
        │  │  (跨所有用户/会话统一存储)           │  │
        │  └───────────────────────────────────┘  │
        │  ┌───────────────────────────────────┐  │
        │  │  index: HybridRetriever (共享)     │  │
        │  │  doc_id -> record_id 映射          │  │
        │  └───────────────────────────────────┘  │
        │  ┌───────────────────────────────────┐  │
        │  │  会话分区:                          │  │
        │  │  user_sessions[user][session] =    │  │
        │  │    {working:[ids], episodic:[ids]} │  │
        │  └───────────────────────────────────┘  │
        └─────────────────────────────────────────┘

    Attributes:
        storage_dir: 持久化目录路径。
        working_capacity: working 层每会话容量上限。
        episodic_capacity: episodic 层每会话容量上限。
        semantic_capacity: semantic 层每用户容量上限。
        working_ttl: working 层 TTL（秒）。
        episodic_ttl: episodic 层 TTL。
        semantic_ttl: semantic 层 TTL。
    """

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        working_capacity: int = DEFAULT_WORKING_CAPACITY,
        episodic_capacity: int = DEFAULT_EPISODIC_CAPACITY,
        semantic_capacity: int = DEFAULT_SEMANTIC_CAPACITY,
        working_ttl: float = DEFAULT_WORKING_TTL,
        episodic_ttl: float = DEFAULT_EPISODIC_TTL,
        semantic_ttl: float = DEFAULT_SEMANTIC_TTL,
        bm25_weight: float = 1.0,
        dense_weight: float = 1.0,
        rrf_k: int = 60,
        time_decay_half_life: float = 7 * 24 * 3600,  # 7 天
        reranker: Any = None,
    ) -> None:
        """初始化 AML 记忆存储。

        Args:
            storage_dir: JSON 持久化目录。若为 None，则使用
                ``~/.suyi/aml_memory/``。
            working_capacity: working 层每会话最大条目数。
            episodic_capacity: episodic 层每会话最大条目数。
            semantic_capacity: semantic 层每用户最大条目数。
            working_ttl: working 层条目 TTL（秒），0 表示不过期。
            episodic_ttl: episodic 层条目 TTL。
            semantic_ttl: semantic 层条目 TTL。
            bm25_weight: BM25 路在 RRF 融合中的权重。
            dense_weight: Dense 路在 RRF 融合中的权重。
            rrf_k: RRF 常数。
            time_decay_half_life: 检索时间衰减半衰期（秒）。
            reranker: v1.10.0 新增，可选的 utility 重排器配置：

                - ``None``（默认）：按环境变量 ``AML_RERANK_ENABLED``
                  自动决定（默认开启，仅当值为 ``false/0/no/off`` 时
                  关闭）；
                - ``False``：显式关闭重排；
                - :class:`~suyi.memory.utility_reranker.UtilityReranker`
                  实例：直接复用外部实例（便于共享权重）。
        """
        if storage_dir is None:
            storage_dir = os.path.join(
                os.path.expanduser("~"), ".suyi", "aml_memory"
            )
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

        self.working_capacity = working_capacity
        self.episodic_capacity = episodic_capacity
        self.semantic_capacity = semantic_capacity
        self.working_ttl = working_ttl
        self.episodic_ttl = episodic_ttl
        self.semantic_ttl = semantic_ttl

        # 核心存储
        self._records: Dict[str, MemoryRecord] = {}
        # doc_id (HybridRetriever) -> record_id
        self._doc_to_record: Dict[int, str] = {}
        # record_id -> doc_id
        self._record_to_doc: Dict[str, int] = {}

        # 会话分区索引
        # user_id -> session_id -> {layer: [record_ids]}
        self._partitions: Dict[str, Dict[str, Dict[str, List[str]]]] = {}
        # user_id -> [semantic record_ids]
        self._user_semantic: Dict[str, List[str]] = {}

        # 去重集合: (user_id, content_hash) -> record_id
        self._dedup_index: Dict[Tuple[str, str], str] = {}

        # 混合检索器
        self._retriever = HybridRetriever(
            rrf_k=rrf_k,
            bm25_weight=bm25_weight,
            dense_weight=dense_weight,
            time_decay_half_life=time_decay_half_life,
        )

        # v1.10.0: MemRL utility 重排器（可选，默认开启）
        # 通过环境变量 AML_RERANK_ENABLED=false 可关闭；显式传入
        # reranker=False 也可关闭；显式传入 UtilityReranker 实例则复用。
        self._reranker: Optional[UtilityReranker] = self._init_reranker(
            reranker=reranker,
        )

        # 线程锁（HTTP 服务器可能多线程访问）
        self._lock = threading.RLock()

        # 加载持久化数据
        self._load()

    @staticmethod
    def _init_reranker(
        reranker: Any,
    ) -> Optional[UtilityReranker]:
        """根据构造参数初始化 utility 重排器。

        Args:
            reranker: 支持三种取值：

                - ``None``（默认）：根据环境变量
                  ``AML_RERANK_ENABLED`` 决定是否创建（默认开启，
                  仅当值为 ``"false"`` / ``"0"`` / ``"no"`` 时关闭）。
                - ``False``：显式关闭。
                - :class:`UtilityReranker` 实例：直接复用。

        Returns:
            ``UtilityReranker`` 实例或 ``None``。
        """
        if reranker is False:
            return None
        if isinstance(reranker, UtilityReranker):
            return reranker
        if reranker is None:
            flag = os.environ.get("AML_RERANK_ENABLED", "true").strip().lower()
            if flag in ("false", "0", "no", "off"):
                return None
        # v1.10.0：默认重排器使用与检索器一致的 7 天半衰期。
        # 权重文件路径独立于 storage_dir，避免多 store 实例互相覆盖。
        return UtilityReranker(
            time_decay_half_life=7 * 24 * 3600.0,
            auto_load=True,
        )

    @property
    def reranker(self) -> Optional[UtilityReranker]:
        """当前使用的 utility 重排器（可能为 None）。"""
        return self._reranker

    # ------------------------------------------------------------------
    #  添加消息
    # ------------------------------------------------------------------

    def add_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryRecord]:
        """添加一条对话消息到记忆系统。

        路由逻辑：

        1. **Working memory**：所有消息都会进入当前会话的 working 层，
           保留最近 N 条。
        2. **Episodic memory**：消息同时进入 episodic 层（跨会话历史）。
        3. **Semantic memory**：如果是 user 消息且包含事实/规则/偏好
           关键词，提取后存入 semantic 层。

        内容去重基于 ``(user_id, role, content)`` 的 SHA-256 哈希；
        重复内容不会重复入库，但会更新时间戳。

        Args:
            user_id: 用户 ID。
            session_id: 会话 ID。
            role: 消息角色（user / assistant / system）。
            content: 消息文本。
            timestamp: 消息原始时间戳（Unix 秒），为 None 则使用当前时间。
            metadata: 附加元数据。

        Returns:
            本次创建的 :class:`MemoryRecord` 列表（working + episodic +
            可能的 semantic 条目）。若内容被去重，返回已有记录。
        """
        if not user_id or not session_id:
            raise ValueError("user_id and session_id must not be empty")
        if not content:
            return []

        if timestamp is None:
            timestamp = time.time()

        meta = dict(metadata or {})
        created_records: List[MemoryRecord] = []

        with self._lock:
            # --- 1. Working memory ---
            working_rec = self._store_record(
                layer=LAYER_WORKING,
                user_id=user_id,
                session_id=session_id,
                role=role,
                content=content,
                timestamp=timestamp,
                ttl=self.working_ttl,
                metadata=meta,
            )
            if working_rec is not None:
                created_records.append(working_rec)
                self._enforce_capacity(
                    user_id, session_id, LAYER_WORKING, self.working_capacity
                )

            # --- 2. Episodic memory ---
            episodic_rec = self._store_record(
                layer=LAYER_EPISODIC,
                user_id=user_id,
                session_id=session_id,
                role=role,
                content=content,
                timestamp=timestamp,
                ttl=self.episodic_ttl,
                metadata=meta,
            )
            if episodic_rec is not None:
                created_records.append(episodic_rec)
                self._enforce_capacity(
                    user_id, session_id, LAYER_EPISODIC,
                    self.episodic_capacity,
                )

            # --- 3. Semantic memory (仅 user 消息，规则提取) ---
            facts = extract_semantic_facts(content, role)
            for fact in facts:
                sem_meta = dict(meta)
                sem_meta["extracted_from"] = content[:200]
                sem_meta["fact_type"] = self._classify_fact(fact)
                sem_rec = self._store_record(
                    layer=LAYER_SEMANTIC,
                    user_id=user_id,
                    session_id=session_id,
                    role=role,
                    content=fact,
                    timestamp=timestamp,
                    ttl=self.semantic_ttl,
                    metadata=sem_meta,
                    dedup_scope="user",  # semantic 按用户去重
                )
                if sem_rec is not None:
                    created_records.append(sem_rec)

            # semantic 层按用户容量管理
            self._enforce_user_semantic_capacity(
                user_id, self.semantic_capacity
            )

            # 持久化
            self._save()

        return created_records

    def add_messages_batch(
        self,
        user_id: str,
        session_id: str,
        messages: List[Dict[str, Any]],
    ) -> int:
        """批量添加消息（AML /add 接口可能一次传多条）。

        Args:
            user_id: 用户 ID。
            session_id: 会话 ID。
            messages: 消息字典列表，每个字典包含 role、content、timestamp、
                metadata 字段。

        Returns:
            创建的记忆条目总数。
        """
        total = 0
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            ts = msg.get("timestamp")
            if isinstance(ts, str):
                try:
                    # 解析 ISO8601
                    from datetime import datetime
                    ts = datetime.fromisoformat(
                        ts.replace("Z", "+00:00")
                    ).timestamp()
                except (ValueError, AttributeError):
                    ts = None
            meta = msg.get("metadata", {})

            records = self.add_message(
                user_id=user_id,
                session_id=session_id,
                role=role,
                content=content,
                timestamp=ts,
                metadata=meta,
            )
            total += len(records)
        return total

    # ------------------------------------------------------------------
    #  内部存储
    # ------------------------------------------------------------------

    def _store_record(
        self,
        layer: str,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        timestamp: float,
        ttl: float,
        metadata: Dict[str, Any],
        dedup_scope: str = "session",
    ) -> Optional[MemoryRecord]:
        """存储一条记忆记录（内部方法，调用方需持有锁）。

        Args:
            layer: 记忆层。
            user_id: 用户 ID。
            session_id: 会话 ID。
            role: 角色。
            content: 内容。
            timestamp: 时间戳。
            ttl: 过期时间。
            metadata: 元数据。
            dedup_scope: 去重范围，``"session"`` 表示同会话同内容去重，
                ``"user"`` 表示同用户跨会话去重。

        Returns:
            创建的 MemoryRecord，若被去重则返回 None。
        """
        # 计算内容哈希
        content_hash = hashlib.sha256(
            f"{role}|{content}".encode("utf-8")
        ).hexdigest()[:16]

        if dedup_scope == "user":
            dedup_key = (user_id, f"{layer}:{content_hash}")
        else:
            dedup_key = (user_id, f"{layer}:{session_id}:{content_hash}")

        # 去重检查
        existing_id = self._dedup_index.get(dedup_key)
        if existing_id and existing_id in self._records:
            existing = self._records[existing_id]
            # 更新时间戳（让已有记忆"刷新"）
            existing.timestamp = timestamp
            existing.added_at = time.time()
            return None

        # 创建记录
        record_id = hashlib.sha256(
            f"{layer}|{user_id}|{session_id}|{role}|{content}|{time.time_ns()}"
            .encode("utf-8")
        ).hexdigest()[:16]

        record = MemoryRecord(
            id=record_id,
            user_id=user_id,
            session_id=session_id,
            layer=layer,
            role=role,
            content=content,
            timestamp=timestamp,
            ttl=ttl,
            metadata=dict(metadata),
        )

        # 添加到检索器
        doc_meta = {
            "record_id": record_id,
            "user_id": user_id,
            "session_id": session_id,
            "layer": layer,
            "role": role,
            "timestamp": timestamp,
        }
        doc_id = self._retriever.add_document(content, metadata=doc_meta)

        # 更新映射
        self._records[record_id] = record
        self._doc_to_record[doc_id] = record_id
        self._record_to_doc[record_id] = doc_id
        self._dedup_index[dedup_key] = record_id

        # 更新分区索引
        if layer == LAYER_SEMANTIC:
            self._user_semantic.setdefault(user_id, []).append(record_id)
        else:
            user_parts = self._partitions.setdefault(user_id, {})
            session_parts = user_parts.setdefault(session_id, {})
            session_parts.setdefault(layer, []).append(record_id)

        return record

    def _enforce_capacity(
        self,
        user_id: str,
        session_id: str,
        layer: str,
        capacity: int,
    ) -> None:
        """强制执行层容量上限，超出时删除最旧条目。"""
        if capacity <= 0:
            return

        session_parts = self._partitions.get(user_id, {}).get(session_id, {})
        id_list = session_parts.get(layer, [])
        if len(id_list) <= capacity:
            return

        # 按时间戳排序，删除最旧的
        records = [
            self._records[rid] for rid in id_list if rid in self._records
        ]
        records.sort(key=lambda r: r.timestamp)

        excess = len(records) - capacity
        to_remove = records[:excess]
        for rec in to_remove:
            self._remove_record(rec.id)

    def _enforce_user_semantic_capacity(
        self, user_id: str, capacity: int
    ) -> None:
        """强制执行每个用户的 semantic 层容量上限。"""
        if capacity <= 0:
            return
        id_list = self._user_semantic.get(user_id, [])
        if len(id_list) <= capacity:
            return

        records = [
            self._records[rid] for rid in id_list if rid in self._records
        ]
        records.sort(key=lambda r: r.timestamp)

        excess = len(records) - capacity
        for rec in records[:excess]:
            self._remove_record(rec.id)

    def _remove_record(self, record_id: str) -> None:
        """从所有索引中移除一条记录（调用方需持有锁）。"""
        record = self._records.pop(record_id, None)
        if record is None:
            return

        # 从检索器映射中移除（注意：HybridRetriever 不支持物理删除文档，
        # 但我们在检索后会过滤掉已删除的 record_id）
        self._record_to_doc.pop(record_id, None)
        # 反向映射中保留 doc_id -> None 标记，或直接删除
        # 为了安全，我们保留 doc_id 但在检索时检查 record 是否存在
        if record_id in self._record_to_doc.values():
            pass  # 已在上面 pop

        # 从分区索引中移除
        if record.layer == LAYER_SEMANTIC:
            sem_list = self._user_semantic.get(record.user_id, [])
            if record_id in sem_list:
                sem_list.remove(record_id)
        else:
            user_parts = self._partitions.get(record.user_id, {})
            session_parts = user_parts.get(record.session_id, {})
            id_list = session_parts.get(record.layer, [])
            if record_id in id_list:
                id_list.remove(record_id)

        # 从去重索引中移除
        keys_to_remove = [
            k for k, v in self._dedup_index.items() if v == record_id
        ]
        for k in keys_to_remove:
            del self._dedup_index[k]

    # ------------------------------------------------------------------
    #  检索
    # ------------------------------------------------------------------

    def search(
        self,
        user_id: str,
        session_id: str,
        query: str,
        top_k: int = 5,
        layers: Optional[List[str]] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        include_expired: bool = False,
    ) -> List[Dict[str, Any]]:
        """跨层检索相关记忆。

        检索范围：

        - 当前会话的 working memory
        - 当前会话的 episodic memory
        - 该用户所有会话的 semantic memory
        - 该用户其他会话的 episodic memory（跨会话历史）

        使用 HybridRetriever 的 BM25 + Dense RRF 融合排序，working 层
        结果因时间衰减自然获得更高权重。

        Args:
            user_id: 用户 ID。
            session_id: 当前会话 ID。
            query: 查询文本。
            top_k: 返回结果数上限。
            layers: 指定检索的层，None 表示全部三层。
            metadata_filter: 元数据过滤条件（精确匹配）。
            include_expired: 是否包含已过期条目。

        Returns:
            结果字典列表，每个字典包含 ``content``、``score``、
            ``metadata``、``layer``、``role``、``timestamp`` 字段。
        """
        if not query or top_k <= 0:
            return []

        target_layers = set(layers) if layers else {
            LAYER_WORKING, LAYER_EPISODIC, LAYER_SEMANTIC
        }

        with self._lock:
            # 收集候选 doc_ids
            candidate_doc_ids: List[int] = []

            # 当前会话的 working + episodic
            user_parts = self._partitions.get(user_id, {})
            session_parts = user_parts.get(session_id, {})
            for layer in (LAYER_WORKING, LAYER_EPISODIC):
                if layer in target_layers:
                    for rid in session_parts.get(layer, []):
                        doc_id = self._record_to_doc.get(rid)
                        if doc_id is not None:
                            candidate_doc_ids.append(doc_id)

            # 该用户其他会话的 episodic（跨会话）
            if LAYER_EPISODIC in target_layers:
                for other_sid, other_parts in user_parts.items():
                    if other_sid == session_id:
                        continue
                    for rid in other_parts.get(LAYER_EPISODIC, []):
                        doc_id = self._record_to_doc.get(rid)
                        if doc_id is not None:
                            candidate_doc_ids.append(doc_id)

            # 该用户的 semantic
            if LAYER_SEMANTIC in target_layers:
                for rid in self._user_semantic.get(user_id, []):
                    doc_id = self._record_to_doc.get(rid)
                    if doc_id is not None:
                        candidate_doc_ids.append(doc_id)

            if not candidate_doc_ids:
                return []

            # 去重候选
            candidate_doc_ids = list(set(candidate_doc_ids))

            # v1.10.0：RRF 第一阶段召回 top_k*3 候选。
            # 若配置了 UtilityReranker，则对这些候选做第二阶段重排，
            # 最终取 top_k。整个过程不改变返回结构（仍返回
            # content/score/metadata 等字段），仅在 metadata 中附加
            # 可选的 utility 分。
            fetch_k = min(top_k * 3, len(candidate_doc_ids))
            raw_results = self._retriever.search(
                query, top_k=fetch_k, candidate_ids=candidate_doc_ids,
            )

            # 后处理：过滤过期 / 元数据条件，并构建结果列表
            pre_results: List[Dict[str, Any]] = []
            for r in raw_results:
                record_id = self._doc_to_record.get(r.doc_id)
                if record_id is None:
                    continue
                record = self._records.get(record_id)
                if record is None:
                    continue

                # 过期检查
                if not include_expired and record.is_expired:
                    continue

                # 元数据过滤
                if metadata_filter:
                    if not self._match_metadata(
                        record.metadata, metadata_filter
                    ):
                        continue

                pre_results.append({
                    "doc_id": r.doc_id,
                    "record_id": record_id,
                    "content": record.content,
                    "score": float(r.score),
                    "layer": record.layer,
                    "role": record.role,
                    "session_id": record.session_id,
                    "timestamp": record.timestamp,
                    "record": record,
                })

            if not pre_results:
                return []

            if self._reranker is not None and len(pre_results) > 1:
                results = self._rerank_candidates(
                    query=query,
                    pre_results=pre_results,
                    top_k=top_k,
                    candidate_doc_ids=candidate_doc_ids,
                )
            else:
                # 无重排器或候选数 <=1：直接按原 RRF 分数排序
                pre_results.sort(key=lambda x: x["score"], reverse=True)
                results = self._format_results(pre_results[:top_k])

            return results[:top_k]

    def _build_rerank_candidate(
        self,
        doc_id: int,
        route_scores: Dict[str, float],
        record: MemoryRecord,
    ) -> RerankCandidate:
        """根据 doc_id 和单路得分构建一个 :class:`RerankCandidate`。"""
        return RerankCandidate(
            doc_id=doc_id,
            content=record.content,
            bm25_score=float(route_scores.get("bm25", 0.0)),
            dense_score=float(route_scores.get("dense", 0.0)),
            rrf_score=float(route_scores.get("fused", 0.0)),
            layer=record.layer,
            timestamp=record.timestamp,
            access_count=int(getattr(record, "access_count", 0)),
            metadata={
                "record_id": record.id,
                "role": record.role,
                "session_id": record.session_id,
                **record.metadata,
            },
        )

    def _rerank_candidates(
        self,
        query: str,
        pre_results: List[Dict[str, Any]],
        top_k: int,
        candidate_doc_ids: List[int],
    ) -> List[Dict[str, Any]]:
        """使用 UtilityReranker 对候选做第二阶段重排（内部方法）。

        调用方必须持有 ``self._lock``。
        """
        assert self._reranker is not None

        # 为所有召回候选取一次单路分数（特征需要）
        route_map = self._retriever.score_candidates(
            query, [p["doc_id"] for p in pre_results]
        )

        candidates: List[RerankCandidate] = []
        for p in pre_results:
            doc_id = p["doc_id"]
            record: MemoryRecord = p["record"]
            cands = self._build_rerank_candidate(
                doc_id, route_map.get(doc_id, {}), record
            )
            candidates.append(cands)

        ranked = self._reranker.rerank(
            query, candidates, top_k=len(candidates)
        )

        now_ts = time.time()
        ordered: List[Dict[str, Any]] = []
        for rr in ranked[:top_k]:
            c = rr.candidate
            rec_id = c.metadata.get("record_id")
            record = self._records.get(rec_id) if rec_id else None
            if record is None:
                continue
            # 更新访问计数（utility 特征的反馈信号之一）
            record.access_count = int(getattr(record, "access_count", 0)) + 1
            record.last_accessed_at = now_ts

            # 找到原始 RRF 分数（用于返回字段 score，保持与 v1.9 兼容）
            original_score = 0.0
            for p in pre_results:
                if p["doc_id"] == c.doc_id:
                    original_score = p["score"]
                    break

            ordered.append({
                "doc_id": c.doc_id,
                "record_id": rec_id,
                "content": c.content,
                "score": original_score,
                "utility_score": rr.utility,
                "layer": c.layer,
                "role": c.metadata.get("role", record.role),
                "session_id": c.metadata.get(
                    "session_id", record.session_id
                ),
                "timestamp": c.timestamp,
                "record": record,
            })

        return self._format_results(ordered)

    @staticmethod
    def _format_results(
        items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """把内部 dict 列表格式化为 search 返回的公开结构。"""
        out: List[Dict[str, Any]] = []
        for item in items:
            record: MemoryRecord = item["record"]
            metadata = {
                **record.metadata,
                "layer": item.get("layer", record.layer),
                "role": item.get("role", record.role),
                "session_id": item.get(
                    "session_id", record.session_id
                ),
                "timestamp": item.get("timestamp", record.timestamp),
                "record_id": item.get("record_id", record.id),
            }
            utility = item.get("utility_score")
            if utility is not None:
                metadata["utility_score"] = round(float(utility), 6)
            out.append({
                "content": item["content"],
                "score": round(float(item["score"]), 6),
                "metadata": metadata,
            })
        return out

    @staticmethod
    def _match_metadata(
        record_meta: Dict[str, Any], filter_meta: Dict[str, Any]
    ) -> bool:
        """检查记录元数据是否满足过滤条件（精确匹配）。"""
        for key, value in filter_meta.items():
            if record_meta.get(key) != value:
                return False
        return True

    @staticmethod
    def _classify_fact(text: str) -> str:
        """简单分类事实类型（preference / rule / identity / fact）。"""
        text_lower = text.lower()
        if any(p.search(text) for p in _PREFERENCE_PATTERNS):
            return "preference"
        if any(p.search(text) for p in _RULE_PATTERNS):
            return "rule"
        if "name" in text_lower or "i am" in text_lower or "i'm" in text_lower:
            return "identity"
        return "fact"

    # ------------------------------------------------------------------
    #  清理与维护
    # ------------------------------------------------------------------

    def cleanup_expired(self) -> int:
        """清理所有已过期的记忆条目。

        Returns:
            被清理的条目数。
        """
        removed = 0
        with self._lock:
            expired_ids = [
                rid for rid, rec in self._records.items()
                if rec.is_expired
            ]
            for rid in expired_ids:
                self._remove_record(rid)
                removed += 1
            if removed > 0:
                self._save()
        return removed

    def clear_user(self, user_id: str) -> int:
        """清除指定用户的所有记忆。

        Args:
            user_id: 用户 ID。

        Returns:
            被清除的条目数。
        """
        with self._lock:
            ids_to_remove = [
                rid for rid, rec in self._records.items()
                if rec.user_id == user_id
            ]
            for rid in ids_to_remove:
                self._remove_record(rid)
            self._save()
            return len(ids_to_remove)

    def clear_session(self, user_id: str, session_id: str) -> int:
        """清除指定会话的所有记忆。

        Args:
            user_id: 用户 ID。
            session_id: 会话 ID。

        Returns:
            被清除的条目数。
        """
        with self._lock:
            ids_to_remove = [
                rid for rid, rec in self._records.items()
                if rec.user_id == user_id
                and rec.session_id == session_id
                and rec.layer != LAYER_SEMANTIC
            ]
            for rid in ids_to_remove:
                self._remove_record(rid)
            self._save()
            return len(ids_to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息。"""
        with self._lock:
            layer_counts: Dict[str, int] = {
                LAYER_WORKING: 0,
                LAYER_EPISODIC: 0,
                LAYER_SEMANTIC: 0,
            }
            for rec in self._records.values():
                layer_counts[rec.layer] = (
                    layer_counts.get(rec.layer, 0) + 1
                )

            all_users = set(self._partitions.keys()) | set(
                self._user_semantic.keys()
            )
            return {
                "total_records": len(self._records),
                "total_users": len(all_users),
                "total_sessions": sum(
                    len(sessions) for sessions in self._partitions.values()
                ),
                "by_layer": layer_counts,
                "indexed_docs": self._retriever.n_docs,
                "storage_dir": self.storage_dir,
            }

    # ------------------------------------------------------------------
    #  持久化
    # ------------------------------------------------------------------

    def _get_storage_path(self) -> str:
        """获取持久化文件路径。"""
        return os.path.join(self.storage_dir, "aml_memory.json")

    def _save(self) -> None:
        """将所有记忆持久化到 JSON 文件。"""
        try:
            data = {
                "records": [
                    rec.to_dict() for rec in self._records.values()
                ],
                "doc_to_record": {
                    str(k): v for k, v in self._doc_to_record.items()
                },
                "partitions": self._partitions,
                "user_semantic": self._user_semantic,
                "dedup_index": [
                    {"key": list(k), "value": v}
                    for k, v in self._dedup_index.items()
                ],
                "saved_at": time.time(),
            }
            path = self._get_storage_path()
            tmp_path = path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp_path, path)
        except OSError as e:
            # 持久化失败不应中断服务
            print(f"[AMLMemoryStore] 持久化失败: {e}")

    def _load(self) -> None:
        """从 JSON 文件加载记忆数据。"""
        path = self._get_storage_path()
        if not os.path.exists(path):
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            records_data = data.get("records", [])
            for rd in records_data:
                record = MemoryRecord.from_dict(rd)
                self._records[record.id] = record

            # 重建检索索引
            # 需要按时间顺序添加以保持 doc_id 一致性
            sorted_records = sorted(
                self._records.values(), key=lambda r: r.added_at
            )
            for record in sorted_records:
                doc_meta = {
                    "record_id": record.id,
                    "user_id": record.user_id,
                    "session_id": record.session_id,
                    "layer": record.layer,
                    "role": record.role,
                    "timestamp": record.timestamp,
                }
                doc_id = self._retriever.add_document(
                    record.content, metadata=doc_meta
                )
                self._doc_to_record[doc_id] = record.id
                self._record_to_doc[record.id] = doc_id

            # 恢复分区索引
            self._partitions = data.get("partitions", {})
            self._user_semantic = data.get("user_semantic", {})

            # 恢复去重索引
            for entry in data.get("dedup_index", []):
                key = tuple(entry["key"])
                self._dedup_index[key] = entry["value"]

        except (json.JSONDecodeError, KeyError, OSError) as e:
            print(f"[AMLMemoryStore] 加载持久化数据失败: {e}")
            # 启动时加载失败则清空内存，以干净状态启动
            self._records.clear()
            self._doc_to_record.clear()
            self._record_to_doc.clear()
            self._partitions.clear()
            self._user_semantic.clear()
            self._dedup_index.clear()

    def reload(self) -> None:
        """重新从磁盘加载数据（丢弃内存中的未保存更改）。"""
        with self._lock:
            self._records.clear()
            self._doc_to_record.clear()
            self._record_to_doc.clear()
            self._partitions.clear()
            self._user_semantic.clear()
            self._dedup_index.clear()
            # 重建检索器
            self._retriever = HybridRetriever(
                rrf_k=self._retriever.rrf_k,
                bm25_weight=self._retriever.bm25_weight,
                dense_weight=self._retriever.dense_weight,
                time_decay_half_life=(
                    self._retriever.time_decay_half_life
                ),
            )
            self._load()

    # ------------------------------------------------------------------
    #  便捷方法
    # ------------------------------------------------------------------

    def get_record(self, record_id: str) -> Optional[MemoryRecord]:
        """根据 ID 获取记忆记录。"""
        with self._lock:
            return self._records.get(record_id)

    def get_user_records(
        self, user_id: str, layer: Optional[str] = None
    ) -> List[MemoryRecord]:
        """获取指定用户的所有记忆记录。"""
        with self._lock:
            return [
                rec for rec in self._records.values()
                if rec.user_id == user_id
                and (layer is None or rec.layer == layer)
            ]

    def get_session_records(
        self, user_id: str, session_id: str, layer: Optional[str] = None
    ) -> List[MemoryRecord]:
        """获取指定会话的所有记忆记录。"""
        with self._lock:
            return [
                rec for rec in self._records.values()
                if rec.user_id == user_id
                and rec.session_id == session_id
                and (layer is None or rec.layer == layer)
            ]

    @property
    def total_records(self) -> int:
        """总记忆条目数。"""
        return len(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"AMLMemoryStore("
            f"records={stats['total_records']}, "
            f"users={stats['total_users']}, "
            f"sessions={stats['total_sessions']})"
        )
