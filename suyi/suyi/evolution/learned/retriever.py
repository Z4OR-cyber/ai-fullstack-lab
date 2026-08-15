"""知识检索器 — TF-IDF + 余弦相似度的"穷人版语义检索".

实现 :class:`~suyi.core.context.MemoryBackend` Protocol（async retrieve），
可直接插入现有 :class:`~suyi.core.context.ContextAssembler` 而无需
修改其公开接口。

技术选型（Suyi 既定原则：纯 numpy + 标准库）：
    - 分词：空白/标点切分，英文按词，中文按字符并生成 bigram。
    - 权重：TF-IDF（``log((1+N)/(1+df)) + 1`` 平滑 IDF）。
    - 相似度：L2 归一化后的向量点积 = 余弦相似度。
    - 缓存：首次检索构建 corpus TF-IDF 矩阵并缓存；store 发生
      新增/删除后自动失效（通过版本号比对）。

接口设计成可替换：检索逻辑基于 :class:`KnowledgeBackend` Protocol，
未来可替换为真正的 dense embedding（如 sentence-transformers），
只要实现相同的 ``retrieve`` 签名即可。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import numpy as np

from .store import KnowledgeEntry, LearnedKnowledgeStore


# 复用主记忆系统同款分词正则（保持行为一致）：
# CJK 单字、英文词、数字
_TOKEN_RE = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf]"   # 单个 CJK 字符
    r"|[a-zA-Z][a-zA-Z0-9_]*"          # 英文单词
    r"|\d+(?:\.\d+)?"                  # 数字
)


def tokenize(text: str) -> List[str]:
    """中英文混合分词.

    - 英文/数字 → 整词（小写）.
    - CJK 字符 → 单字，并生成相邻汉字 bigram 以提升中文匹配.

    Args:
        text: 输入文本.

    Returns:
        token 列表（小写）.
    """
    if not text:
        return []
    raw = _TOKEN_RE.findall(text)
    tokens = [t.lower() for t in raw]

    # 为相邻 CJK 单字生成 bigram
    cjk_bigrams: List[str] = []
    for i in range(len(tokens) - 1):
        a, b = tokens[i], tokens[i + 1]
        if (
            len(a) == 1
            and len(b) == 1
            and "\u4e00" <= a <= "\u9fff"
            and "\u4e00" <= b <= "\u9fff"
        ):
            cjk_bigrams.append(a + b)
    tokens.extend(cjk_bigrams)
    return tokens


# ── KnowledgeBackend Protocol（可替换检索后端） ────────────────


@runtime_checkable
class KnowledgeBackend(Protocol):
    """旁路知识检索后端协议.

    未来若要替换为向量模型，实现本协议即可：
        - ``retrieve`` 返回兼容 MemoryBackend 的 dict 列表
        - ``retrieve_entries`` 返回原始 KnowledgeEntry 列表
    """

    async def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """检索并返回 dict 列表（至少含 content 字段）."""
        ...

    def retrieve_entries(
        self, query: str, top_k: Optional[int] = None
    ) -> List[tuple[KnowledgeEntry, float]]:
        """检索并返回 (条目, 相似度) 列表."""
        ...


class KnowledgeRetriever:
    """基于 TF-IDF 的知识检索器，兼容 MemoryBackend Protocol.

    该类拥有 async ``retrieve`` 方法，因此是一个结构化的
    :class:`~suyi.core.context.MemoryBackend`，可直接传给
    :class:`~suyi.core.context.ContextAssembler`。

    Attributes:
        store: 旁路知识存储.
        top_k: 默认返回条目数.
        min_similarity: 最小相似度阈值，低于此值的结果被过滤.
    """

    def __init__(
        self,
        store: LearnedKnowledgeStore,
        top_k: int = 3,
        min_similarity: float = 0.1,
    ) -> None:
        """
        Args:
            store: 旁路知识存储实例.
            top_k: 默认返回的最相似条目数.
            min_similarity: 最小相似度阈值（0-1），默认 0.1.
        """
        self.store = store
        self.top_k = top_k
        self.min_similarity = min_similarity

        # 缓存的 TF-IDF 索引
        self._vocab: Dict[str, int] = {}
        self._idf: Optional[np.ndarray] = None
        self._matrix: Optional[np.ndarray] = None  # shape (n_docs, vocab)，已 L2 归一化
        self._doc_ids: List[str] = []
        self._store_version: int = -1  # 用于检测 store 变化

    # ── 公开检索接口 ──────────────────────────────────────

    async def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """异步检索 — 实现 MemoryBackend Protocol.

        Args:
            query: 查询文本（通常是最近一条用户消息）.
            top_k: 返回条目数上限.

        Returns:
            dict 列表，每项至少包含：
                - ``content``: 知识正文
                - ``source``: 固定为 ``"learned_knowledge"``
                - ``confidence``: 条目的置信度
            此外还附带 ``title`` / ``category`` / ``score`` / ``id`` 等元数据.
        """
        results = self.retrieve_entries(query, top_k=top_k)
        output: List[Dict[str, Any]] = []
        for entry, score in results:
            # 召回计数
            self.store.increment_usage(entry.id, success=False)
            output.append({
                "content": entry.content,
                "source": "learned_knowledge",
                "confidence": round(entry.confidence, 4),
                "id": entry.id,
                "title": entry.title,
                "category": entry.category,
                "bureau": entry.bureau,
                "score": round(float(score), 4),
                "tags": list(entry.tags),
            })
        return output

    def retrieve_entries(
        self, query: str, top_k: Optional[int] = None
    ) -> List[tuple[KnowledgeEntry, float]]:
        """同步检索，返回 (条目, 相似度) 列表.

        Args:
            query: 查询文本.
            top_k: 返回数量上限，None 时使用实例默认值.

        Returns:
            按相似度降序排列的 (KnowledgeEntry, score) 列表，
            已过滤低于 ``min_similarity`` 的结果.
        """
        k = self.top_k if top_k is None else top_k
        entries = self.store.all()
        if not entries or not query:
            return []

        self._ensure_index(entries)
        if self._matrix is None or self._idf is None or not self._vocab:
            return []

        # 构建查询向量
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        query_vec = self._build_query_vector(query_tokens)
        if query_vec is None:
            return []

        # 余弦相似度（矩阵行已 L2 归一化，点积即余弦）
        sims = self._matrix @ query_vec  # type: ignore[operator]

        # 按相似度降序
        order = np.argsort(-sims)
        results: List[tuple[KnowledgeEntry, float]] = []
        for idx in order:
            score = float(sims[idx])
            if score < self.min_similarity:
                continue
            entry_id = self._doc_ids[int(idx)]
            entry = self.store.get(entry_id)
            if entry is not None:
                results.append((entry, score))
            if len(results) >= k:
                break
        return results

    def retrieve_by_tags(
        self,
        tags: List[str],
        bureau: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> List[KnowledgeEntry]:
        """按标签过滤检索（不做语义相似度，纯标签匹配）.

        Args:
            tags: 需要匹配的标签列表，条目需包含全部标签.
            bureau: 可选业务域过滤.
            top_k: 返回数量上限.

        Returns:
            匹配的 KnowledgeEntry 列表（按置信度降序）.
        """
        entries = self.store.list(bureau=bureau, tags=tags)
        entries.sort(key=lambda e: e.confidence, reverse=True)
        if top_k is not None:
            entries = entries[:top_k]
        return entries

    # ── 索引构建与缓存 ────────────────────────────────────

    def invalidate_cache(self) -> None:
        """手动使缓存失效（下次检索时重建索引）."""
        self._vocab = {}
        self._idf = None
        self._matrix = None
        self._doc_ids = []
        self._store_version = -1

    def _ensure_index(self, entries: List[KnowledgeEntry]) -> None:
        """确保 TF-IDF 索引是最新的（基于条目数量与 ID 集合检测变化）."""
        current_version = self._compute_version(entries)
        if (
            self._matrix is not None
            and current_version == self._store_version
            and len(self._doc_ids) == len(entries)
        ):
            return
        self._build_index(entries)

    def _compute_version(self, entries: List[KnowledgeEntry]) -> int:
        """计算一个粗略的 store 版本号（条目数 + ID 哈希）."""
        ids = tuple(sorted(e.id for e in entries))
        return hash(ids) & 0xFFFFFFFF

    def _build_index(self, entries: List[KnowledgeEntry]) -> None:
        """构建 corpus TF-IDF 矩阵（L2 归一化）."""
        # 1. 分词所有文档
        doc_tokens: List[List[str]] = []
        doc_ids: List[str] = []
        for entry in entries:
            tokens = tokenize(f"{entry.title} {entry.content} {' '.join(entry.tags)}")
            if not tokens:
                # 空文档也保留一行（全零向量），保证索引与条目一一对应
                tokens = []
            doc_tokens.append(tokens)
            doc_ids.append(entry.id)

        # 2. 构建词表
        vocab: Dict[str, int] = {}
        for tokens in doc_tokens:
            for tok in tokens:
                if tok not in vocab:
                    vocab[tok] = len(vocab)

        n_docs = len(doc_tokens)
        vocab_size = len(vocab)

        if vocab_size == 0:
            self._vocab = {}
            self._idf = None
            self._matrix = None
            self._doc_ids = doc_ids
            self._store_version = self._compute_version(entries)
            return

        # 3. 计算文档频率 df
        df = np.zeros(vocab_size, dtype=np.float64)
        tf_rows: List[Dict[int, float]] = []
        for tokens in doc_tokens:
            counts: Dict[int, int] = {}
            for tok in tokens:
                col = vocab.get(tok)
                if col is not None:
                    counts[col] = counts.get(col, 0) + 1
            for col in counts:
                df[col] += 1.0
            doc_len = max(1, len(tokens))
            tf_rows.append({col: cnt / doc_len for col, cnt in counts.items()})

        # 4. 平滑 IDF: log((1+N)/(1+df)) + 1
        idf = np.log((1.0 + n_docs) / (1.0 + df)) + 1.0

        # 5. 填充 TF-IDF 矩阵并 L2 归一化
        matrix = np.zeros((n_docs, vocab_size), dtype=np.float64)
        for i, tf_map in enumerate(tf_rows):
            for col, tf_val in tf_map.items():
                matrix[i, col] = tf_val * idf[col]

        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0  # 避免除零
        matrix = matrix / norms

        self._vocab = vocab
        self._idf = idf
        self._matrix = matrix
        self._doc_ids = doc_ids
        self._store_version = self._compute_version(entries)

    def _build_query_vector(self, query_tokens: List[str]) -> Optional[np.ndarray]:
        """构建查询 TF-IDF 向量并 L2 归一化."""
        assert self._idf is not None and self._vocab
        vocab_size = len(self._vocab)
        vec = np.zeros(vocab_size, dtype=np.float64)

        counts: Dict[int, int] = {}
        for tok in query_tokens:
            col = self._vocab.get(tok)
            if col is not None:
                counts[col] = counts.get(col, 0) + 1

        if not counts:
            return None

        doc_len = max(1, len(query_tokens))
        for col, cnt in counts.items():
            vec[col] = (cnt / doc_len) * self._idf[col]

        norm = np.linalg.norm(vec)
        if norm == 0:
            return None
        return vec / norm
