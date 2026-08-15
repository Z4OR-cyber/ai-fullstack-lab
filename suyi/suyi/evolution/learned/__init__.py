"""旁路知识层（Bypass Knowledge Layer）— v1.6.0.

核心思想（来自双循环架构图）：
    主干 skill（代码）稳定不动，所有进化发生在旁路知识（数据），
    通过检索反哺内循环。**代码与数据分离，稳定与进化分离。**

子模块：
    - :mod:`store` — 旁路知识存储（KnowledgeEntry / LearnedKnowledgeStore）.
    - :mod:`retriever` — TF-IDF 语义检索器，兼容 MemoryBackend Protocol.
    - :mod:`dedup` — 入库前三策略去重（skip/merge/append）.
    - :mod:`distiller` — 正样本蒸馏器 / 失败教训提取.
    - :mod:`weak_signals` — 弱信号积累器（达阈值触发外循环蒸馏）.
    - :mod:`knowledge_assembler` — 三级知识注入器（原则/案例/专项）.

典型用法::

    from suyi.evolution.learned import (
        LearnedKnowledgeStore, KnowledgeRetriever,
        SemanticDeduplicator, SuccessDistiller,
        WeakSignalCollector, ThreeTierKnowledgeInjector,
    )
    from suyi.core import ContextAssembler

    store = LearnedKnowledgeStore(storage_dir="data/learned")
    retriever = KnowledgeRetriever(store)
    dedup = SemanticDeduplicator(store)
    distiller = SuccessDistiller(store, dedup)
    weak = WeakSignalCollector(storage_dir="data/learned")
    injector = ThreeTierKnowledgeInjector(store, retriever)

    # 外循环：从交互记录蒸馏
    distiller.distill_batch(records)

    # 内循环：作为 MemoryBackend 直接插入 ContextAssembler
    assembler = ContextAssembler(memory_backend=injector)
"""

from .store import (
    KnowledgeEntry,
    LearnedKnowledgeStore,
    VALID_CATEGORIES,
)
from .retriever import (
    KnowledgeRetriever,
    KnowledgeBackend,
    tokenize,
)
from .dedup import (
    SemanticDeduplicator,
    DeduplicationResult,
    DedupDecision,
)
from .distiller import (
    SuccessDistiller,
    DistillationResult,
)
from .weak_signals import (
    WeakSignal,
    WeakSignalCollector,
    SIGNAL_REWRITE,
    SIGNAL_THUMBS_DOWN,
    SIGNAL_CORRECTION,
    SIGNAL_RETRY,
    SIGNAL_USER_COMMENT,
    VALID_SIGNAL_TYPES,
)
from .knowledge_assembler import (
    ThreeTierKnowledgeInjector,
    KnowledgeTier,
)

__all__ = [
    # store
    "KnowledgeEntry",
    "LearnedKnowledgeStore",
    "VALID_CATEGORIES",
    # retriever
    "KnowledgeRetriever",
    "KnowledgeBackend",
    "tokenize",
    # dedup
    "SemanticDeduplicator",
    "DeduplicationResult",
    "DedupDecision",
    # distiller
    "SuccessDistiller",
    "DistillationResult",
    # weak signals
    "WeakSignal",
    "WeakSignalCollector",
    "SIGNAL_REWRITE",
    "SIGNAL_THUMBS_DOWN",
    "SIGNAL_CORRECTION",
    "SIGNAL_RETRY",
    "SIGNAL_USER_COMMENT",
    "VALID_SIGNAL_TYPES",
    # assembler
    "ThreeTierKnowledgeInjector",
    "KnowledgeTier",
]
