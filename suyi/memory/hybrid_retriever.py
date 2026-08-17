"""BM25 + Dense RRF 混合检索器 — AML 评测专用。

本模块提供三种纯 numpy 实现的检索组件：

- :class:`AMLBM25Retriever`：BM25 Okapi 算法，支持中英文混合分词。
- :class:`AMLDenseRetriever`：基于 TF-IDF 加权词向量的稠密检索（无需 embedding 模型）。
- :class:`AMLHybridRetriever`：使用 RRF（Reciprocal Rank Fusion）融合 BM25 和 Dense
  两路排序结果，支持时间衰减加权。

设计约束
--------
- 纯 Python + numpy，不引入 sklearn / jieba / rank_bm25 等外部依赖。
- 支持增量索引（add_document），无需全量重建。
- 分词方案：英文按空格+标点切分并小写化；中文按字符 bigram 切分。

典型用法::

    retriever = AMLHybridRetriever()
    retriever.add_document("Python GIL prevents true multithreading")
    retriever.add_document("用 Java 做后端开发")
    results = retriever.search("Python threading", top_k=2)
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


# ----------------------------------------------------------------------
#  分词器
# ----------------------------------------------------------------------

# 匹配英文单词、数字、以及单个 CJK 字符
_TOKEN_RE = re.compile(
    r'[a-zA-Z][a-zA-Z0-9_]*'   # 英文单词
    r'|\d+(?:\.\d+)?'           # 数字
    r'|[\u4e00-\u9fff\u3400-\u4dbf]'  # 单个 CJK 字符
)


def tokenize(text: str) -> List[str]:
    """中英文混合分词。

    分词策略：

    - 英文/数字：按正则提取整个单词，转小写。
    - 中文：先提取单字，再对相邻中文字符生成 bigram，提升召回。

    Args:
        text: 待分词文本。

    Returns:
        小写化的 token 列表。空文本返回空列表。
    """
    if not text:
        return []

    raw_tokens: List[str] = _TOKEN_RE.findall(text)
    tokens: List[str] = [t.lower() for t in raw_tokens]

    # 为连续中文字符生成 bigram
    cjk_bigrams: List[str] = []
    for i in range(len(tokens) - 1):
        cur, nxt = tokens[i], tokens[i + 1]
        if (
            len(cur) == 1
            and len(nxt) == 1
            and '\u4e00' <= cur[0] <= '\u9fff'
            and '\u4e00' <= nxt[0] <= '\u9fff'
        ):
            cjk_bigrams.append(cur + nxt)

    tokens.extend(cjk_bigrams)
    return tokens


# ----------------------------------------------------------------------
#  检索结果数据类
# ----------------------------------------------------------------------

@dataclass
class RetrievalResult:
    """单条检索结果。

    Attributes:
        doc_id: 文档在索引中的唯一编号。
        content: 文档原文。
        score: 检索得分（不同检索器的得分口径不同，仅在同一检索器内可比）。
        metadata: 附加元数据（来源、时间戳等）。
    """

    doc_id: int
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典，便于 JSON 响应。"""
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "score": round(self.score, 6),
            "metadata": self.metadata,
        }


# ----------------------------------------------------------------------
#  BM25 Okapi 检索器
# ----------------------------------------------------------------------

class AMLBM25Retriever:
    """BM25 Okapi 检索器（纯 numpy 实现）。

    BM25 是经典的词频-文档频率排序函数，在短文本检索场景表现稳定。
    公式::

        score(D, Q) = Σ IDF(q_i) · [ f(q_i, D) · (k1 + 1) ]
                      / [ f(q_i, D) + k1 · (1 - b + b · |D| / avgdl) ]

        IDF(q_i) = log(1 + (N - n(q_i) + 0.5) / (n(q_i) + 0.5))

    Attributes:
        k1: 词频饱和参数，默认 1.5。
        b: 文档长度归一化参数，默认 0.75。
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        """初始化 BM25 检索器。

        Args:
            k1: 词频饱和参数，越大则词频影响越显著，通常取 1.2–2.0。
            b: 文档长度归一化强度，0 表示不归一化，1 表示完全归一化，
                默认 0.75。
        """
        self.k1 = float(k1)
        self.b = float(b)

        # 文档存储
        self._documents: List[str] = []
        self._doc_tokens: List[List[str]] = []
        self._doc_lengths: List[int] = []
        self._doc_metadata: List[Dict[str, Any]] = []

        # 词频统计: term -> {doc_id: freq}
        self._term_freqs: Dict[str, Dict[int, int]] = {}
        # 文档频率: term -> 包含该词的文档数
        self._doc_freq: Dict[str, int] = {}
        # 文档总数
        self._n_docs: int = 0
        # 平均文档长度
        self._avgdl: float = 0.0
        # IDF 缓存
        self._idf_cache: Dict[str, float] = {}
        # 是否需要重算 IDF
        self._dirty: bool = True

    # ------------------------------------------------------------------
    #  索引管理
    # ------------------------------------------------------------------

    def add_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """添加一篇文档到索引。

        增量更新内部统计量，无需全量重建。

        Args:
            content: 文档文本。
            metadata: 可选的文档元数据。

        Returns:
            新分配的文档 ID（从 0 开始递增）。
        """
        doc_id = self._n_docs
        tokens = tokenize(content)

        self._documents.append(content)
        self._doc_tokens.append(tokens)
        self._doc_lengths.append(len(tokens))
        self._doc_metadata.append(metadata or {})

        # 更新词频和文档频率
        seen_terms: set = set()
        for tok in tokens:
            self._term_freqs.setdefault(tok, {})
            self._term_freqs[tok][doc_id] = (
                self._term_freqs[tok].get(doc_id, 0) + 1
            )
            if tok not in seen_terms:
                seen_terms.add(tok)
                self._doc_freq[tok] = self._doc_freq.get(tok, 0) + 1

        self._n_docs += 1
        self._dirty = True
        self._recompute_stats()
        return doc_id

    def add_documents(
        self,
        documents: Sequence[str],
        metadatas: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> List[int]:
        """批量添加文档。

        Args:
            documents: 文档文本列表。
            metadatas: 可选的元数据列表，长度需与 documents 一致。

        Returns:
            新分配的文档 ID 列表。
        """
        ids: List[int] = []
        for idx, content in enumerate(documents):
            meta = metadatas[idx] if metadatas else None
            ids.append(self.add_document(content, metadata=meta))
        return ids

    def _recompute_stats(self) -> None:
        """重算平均文档长度和 IDF 缓存。"""
        if not self._dirty:
            return

        if self._n_docs > 0:
            self._avgdl = sum(self._doc_lengths) / self._n_docs
        else:
            self._avgdl = 0.0

        # 重算 IDF
        self._idf_cache.clear()
        n = self._n_docs
        for term, df in self._doc_freq.items():
            # BM25+ 风格的平滑 IDF，保证非负
            self._idf_cache[term] = math.log(
                1.0 + (n - df + 0.5) / (df + 0.5)
            )

        self._dirty = False

    # ------------------------------------------------------------------
    #  检索
    # ------------------------------------------------------------------

    def _score_query(self, query_tokens: List[str]) -> np.ndarray:
        """计算查询对所有文档的 BM25 分数。

        Args:
            query_tokens: 已分词的查询 token 列表。

        Returns:
            numpy 数组，shape=(n_docs,)，每个元素为对应文档的 BM25 分数。
        """
        if self._n_docs == 0:
            return np.array([], dtype=np.float64)

        scores = np.zeros(self._n_docs, dtype=np.float64)
        avgdl = self._avgdl if self._avgdl > 0 else 1.0
        k1 = self.k1
        b = self.b

        doc_lengths = np.array(self._doc_lengths, dtype=np.float64)
        length_norm = 1.0 - b + b * doc_lengths / avgdl

        for qt in query_tokens:
            idf = self._idf_cache.get(qt)
            if idf is None:
                continue
            tf_map = self._term_freqs.get(qt, {})
            if not tf_map:
                continue
            # 仅对包含该词的文档计分
            for doc_id, freq in tf_map.items():
                tf = float(freq)
                denom = tf + k1 * length_norm[doc_id]
                scores[doc_id] += idf * (tf * (k1 + 1.0)) / denom

        return scores

    def search(
        self,
        query: str,
        top_k: int = 5,
        candidate_ids: Optional[Sequence[int]] = None,
    ) -> List[RetrievalResult]:
        """检索与查询最相关的 top_k 篇文档。

        Args:
            query: 查询文本。
            top_k: 返回结果数量上限。
            candidate_ids: 可选的候选文档 ID 子集，用于在检索前缩小范围
                （例如会话隔离）。若为 None 则检索全部文档。

        Returns:
            :class:`RetrievalResult` 列表，按分数降序排列。
        """
        if self._n_docs == 0 or top_k <= 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores = self._score_query(query_tokens)

        # 候选过滤
        if candidate_ids is not None:
            mask = np.full_like(scores, -np.inf)
            for cid in candidate_ids:
                if 0 <= cid < self._n_docs:
                    mask[cid] = scores[cid]
            scores = mask

        # 取 top_k
        top_k = min(top_k, self._n_docs)
        # argpartition 比 argsort 快，但需要再排序保证顺序
        if top_k >= self._n_docs:
            top_indices = np.argsort(-scores)[:top_k]
        else:
            partition_idx = np.argpartition(-scores, top_k - 1)[:top_k]
            top_indices = partition_idx[np.argsort(-scores[partition_idx])]

        results: List[RetrievalResult] = []
        for idx in top_indices:
            score = float(scores[idx])
            if score <= 0:
                continue
            results.append(
                RetrievalResult(
                    doc_id=int(idx),
                    content=self._documents[idx],
                    score=score,
                    metadata=dict(self._doc_metadata[idx]),
                )
            )
        return results

    # ------------------------------------------------------------------
    #  属性访问
    # ------------------------------------------------------------------

    @property
    def n_docs(self) -> int:
        """当前索引中的文档总数。"""
        return self._n_docs

    @property
    def vocabulary_size(self) -> int:
        """词汇表大小。"""
        return len(self._doc_freq)

    @property
    def avg_doc_length(self) -> float:
        """平均文档长度（token 数）。"""
        return self._avgdl

    def get_document(self, doc_id: int) -> Optional[str]:
        """根据 ID 获取文档原文。"""
        if 0 <= doc_id < self._n_docs:
            return self._documents[doc_id]
        return None

    def get_metadata(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取文档元数据。"""
        if 0 <= doc_id < self._n_docs:
            return dict(self._doc_metadata[doc_id])
        return None

    def get_all_doc_ids(self) -> List[int]:
        """返回所有文档 ID。"""
        return list(range(self._n_docs))

    def __len__(self) -> int:
        return self._n_docs

    def __repr__(self) -> str:
        return (
            f"AMLBM25Retriever(n_docs={self._n_docs}, "
            f"vocab={self.vocabulary_size}, k1={self.k1}, b={self.b})"
        )


# ----------------------------------------------------------------------
#  Dense 检索器（TF-IDF 加权词向量 + 余弦相似度）
# ----------------------------------------------------------------------

class AMLDenseRetriever:
    """轻量稠密向量检索器。

    不依赖任何预训练 embedding 模型，而是将每篇文档表示为 TF-IDF 加权
    的词袋向量，再通过余弦相似度进行检索。本质上是一个高维稀疏向量空间
    模型，但由于使用 numpy 矩阵运算，检索效率接近稠密向量检索。

    实现细节：

    1. 构建词汇表，每个词映射到一个维度。
    2. 计算每个词的 IDF（与 BM25 使用相同的平滑公式）。
    3. 文档向量 = TF × IDF，做 L2 归一化。
    4. 查询向量同理，与所有文档向量做点积得到余弦相似度。

    Attributes:
        dimensions: 词汇表维度（即向量长度）。
    """

    def __init__(self) -> None:
        """初始化 Dense 检索器。"""
        self._documents: List[str] = []
        self._doc_tokens: List[List[str]] = []
        self._doc_metadata: List[Dict[str, Any]] = []

        # 词汇表: term -> column index
        self._vocabulary: Dict[str, int] = {}
        # IDF 数组
        self._idf: np.ndarray = np.array([], dtype=np.float64)
        # 文档向量矩阵 (n_docs, vocab_size)，已 L2 归一化
        self._doc_vectors: np.ndarray = np.array([], dtype=np.float64)
        # 词频矩阵 (n_docs, vocab_size)，用于增量更新
        self._tf_matrix: np.ndarray = np.array([], dtype=np.float64)
        # 文档长度（token 数）
        self._doc_lengths: List[int] = []

        self._n_docs: int = 0

    # ------------------------------------------------------------------
    #  索引管理
    # ------------------------------------------------------------------

    def add_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """添加一篇文档并增量更新向量矩阵。

        Args:
            content: 文档文本。
            metadata: 可选元数据。

        Returns:
            文档 ID。
        """
        doc_id = self._n_docs
        tokens = tokenize(content)

        self._documents.append(content)
        self._doc_tokens.append(tokens)
        self._doc_metadata.append(metadata or {})
        self._doc_lengths.append(len(tokens))
        self._n_docs += 1

        # 发现新词，扩展词汇表和矩阵
        new_terms = [t for t in set(tokens) if t not in self._vocabulary]
        if new_terms:
            start_idx = len(self._vocabulary)
            for i, term in enumerate(new_terms):
                self._vocabulary[term] = start_idx + i

        # 重建矩阵（增量扩展列更复杂且词表通常不大，全量重建更可靠）
        self._build_vectors()
        return doc_id

    def add_documents(
        self,
        documents: Sequence[str],
        metadatas: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> List[int]:
        """批量添加文档。"""
        ids: List[int] = []
        for idx, content in enumerate(documents):
            meta = metadatas[idx] if metadatas else None
            ids.append(self.add_document(content, metadata=meta))
        return ids

    def _build_vectors(self) -> None:
        """根据当前全部文档构建 TF-IDF 向量矩阵。"""
        vocab_size = len(self._vocabulary)
        n_docs = self._n_docs

        if n_docs == 0 or vocab_size == 0:
            self._tf_matrix = np.zeros((0, 0), dtype=np.float64)
            self._idf = np.zeros(0, dtype=np.float64)
            self._doc_vectors = np.zeros((0, 0), dtype=np.float64)
            return

        # 构建 TF 矩阵
        tf = np.zeros((n_docs, vocab_size), dtype=np.float64)
        for doc_id, tokens in enumerate(self._doc_tokens):
            for tok in tokens:
                col = self._vocabulary.get(tok)
                if col is not None:
                    tf[doc_id, col] += 1.0

        # 计算文档频率 DF
        df = np.count_nonzero(tf > 0, axis=0).astype(np.float64)
        # 平滑 IDF: log(1 + (N - df + 0.5) / (df + 0.5))
        idf = np.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))

        # TF-IDF
        tfidf = tf * idf[np.newaxis, :]

        # L2 归一化
        norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
        norms[norms == 0] = 1.0  # 避免除零
        normalized = tfidf / norms

        self._tf_matrix = tf
        self._idf = idf
        self._doc_vectors = normalized

    # ------------------------------------------------------------------
    #  检索
    # ------------------------------------------------------------------

    def _encode_query(self, query_tokens: List[str]) -> np.ndarray:
        """将查询编码为 TF-IDF 向量并 L2 归一化。

        Args:
            query_tokens: 查询 token 列表。

        Returns:
            shape=(vocab_size,) 的 numpy 向量。
        """
        vocab_size = len(self._vocabulary)
        if vocab_size == 0:
            return np.zeros(0, dtype=np.float64)

        vec = np.zeros(vocab_size, dtype=np.float64)
        for tok in query_tokens:
            col = self._vocabulary.get(tok)
            if col is not None:
                vec[col] += 1.0

        # TF-IDF 加权
        vec = vec * self._idf

        # L2 归一化
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def search(
        self,
        query: str,
        top_k: int = 5,
        candidate_ids: Optional[Sequence[int]] = None,
    ) -> List[RetrievalResult]:
        """基于余弦相似度检索文档。

        Args:
            query: 查询文本。
            top_k: 返回结果数上限。
            candidate_ids: 可选的候选文档 ID 子集。

        Returns:
            :class:`RetrievalResult` 列表，按相似度降序。
        """
        if self._n_docs == 0 or top_k <= 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        qvec = self._encode_query(query_tokens)
        if qvec.size == 0 or np.linalg.norm(qvec) == 0:
            return []

        # 全量余弦相似度（点积即余弦，因为已归一化）
        all_scores = self._doc_vectors @ qvec  # shape=(n_docs,)

        if candidate_ids is not None:
            mask = np.full_like(all_scores, -np.inf)
            for cid in candidate_ids:
                if 0 <= cid < self._n_docs:
                    mask[cid] = all_scores[cid]
            all_scores = mask

        top_k = min(top_k, self._n_docs)
        if top_k >= self._n_docs:
            top_indices = np.argsort(-all_scores)[:top_k]
        else:
            partition_idx = np.argpartition(-all_scores, top_k - 1)[:top_k]
            top_indices = partition_idx[
                np.argsort(-all_scores[partition_idx])
            ]

        results: List[RetrievalResult] = []
        for idx in top_indices:
            score = float(all_scores[idx])
            if score <= 0:
                continue
            results.append(
                RetrievalResult(
                    doc_id=int(idx),
                    content=self._documents[idx],
                    score=score,
                    metadata=dict(self._doc_metadata[idx]),
                )
            )
        return results

    # ------------------------------------------------------------------
    #  属性
    # ------------------------------------------------------------------

    @property
    def n_docs(self) -> int:
        """文档总数。"""
        return self._n_docs

    @property
    def dimensions(self) -> int:
        """向量维度（词汇表大小）。"""
        return len(self._vocabulary)

    def get_document(self, doc_id: int) -> Optional[str]:
        """根据 ID 获取文档原文。"""
        if 0 <= doc_id < self._n_docs:
            return self._documents[doc_id]
        return None

    def get_metadata(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取文档元数据。"""
        if 0 <= doc_id < self._n_docs:
            return dict(self._doc_metadata[doc_id])
        return None

    def __len__(self) -> int:
        return self._n_docs

    def __repr__(self) -> str:
        return (
            f"AMLDenseRetriever(n_docs={self._n_docs}, "
            f"dimensions={self.dimensions})"
        )


# ----------------------------------------------------------------------
#  Hybrid 检索器（RRF 融合 + 时间衰减）
# ----------------------------------------------------------------------

class AMLHybridRetriever:
    """BM25 + Dense RRF 混合检索器。

    使用 Reciprocal Rank Fusion（RRF）将两路检索结果的排名融合：

    .. math::

        score(d) = w_{bm25} \\cdot \\sum_{r \\in R_{bm25}}
                   \\frac{1}{k + rank_r(d)}
                 + w_{dense} \\cdot \\sum_{r \\in R_{dense}}
                   \\frac{1}{k + rank_r(d)}

    其中 ``k=60`` 是 RRF 常数，``rank`` 从 1 开始。RRF 的优势在于
    不依赖各路分数的绝对值，仅利用排名信息，对分数尺度差异鲁棒。

    此外支持**时间衰减因子**：文档元数据中包含 ``timestamp`` 时，
    越新的文档获得越高的权重加成。

    Attributes:
        bm25: 内部 BM25 检索器实例。
        dense: 内部 Dense 检索器实例。
        rrf_k: RRF 常数，默认 60。
        bm25_weight: BM25 路权重，默认 1.0。
        dense_weight: Dense 路权重，默认 1.0。
        time_decay_half_life: 时间衰减半衰期（秒），0 表示不衰减。
    """

    def __init__(
        self,
        bm25_k1: float = 1.5,
        bm25_b: float = 0.75,
        rrf_k: int = 60,
        bm25_weight: float = 1.0,
        dense_weight: float = 1.0,
        time_decay_half_life: float = 0.0,
    ) -> None:
        """初始化混合检索器。

        Args:
            bm25_k1: BM25 的 k1 参数。
            bm25_b: BM25 的 b 参数。
            rrf_k: RRF 融合常数，通常取 60。
            bm25_weight: BM25 路的融合权重。
            dense_weight: Dense 路的融合权重。
            time_decay_half_life: 时间衰减半衰期（秒）。设为 0 则禁用
                时间衰减；设为正数时，文档的 RRF 分数会乘以
                ``0.5 ^ (age_seconds / half_life)`` 的补数加权。
        """
        self.bm25 = AMLBM25Retriever(k1=bm25_k1, b=bm25_b)
        self.dense = AMLDenseRetriever()

        self.rrf_k = int(rrf_k)
        self.bm25_weight = float(bm25_weight)
        self.dense_weight = float(dense_weight)
        self.time_decay_half_life = float(time_decay_half_life)

        # 统一文档存储（两个子检索器共享文档 ID）
        self._documents: List[str] = []
        self._doc_metadata: List[Dict[str, Any]] = []
        self._n_docs: int = 0

    # ------------------------------------------------------------------
    #  文档管理
    # ------------------------------------------------------------------

    def add_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """添加文档到 BM25 和 Dense 两路索引。

        Args:
            content: 文档文本。
            metadata: 文档元数据，可包含 ``timestamp``（Unix 时间戳）
                用于时间衰减，以及 ``layer`` 等自定义字段。

        Returns:
            文档 ID。
        """
        doc_id = self._n_docs
        meta = dict(metadata) if metadata else {}

        # 自动补充添加时间
        meta.setdefault("added_at", time.time())

        self._documents.append(content)
        self._doc_metadata.append(meta)
        self._n_docs += 1

        self.bm25.add_document(content, metadata=meta)
        self.dense.add_document(content, metadata=meta)

        return doc_id

    def add_documents(
        self,
        documents: Sequence[str],
        metadatas: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> List[int]:
        """批量添加文档。"""
        ids: List[int] = []
        for idx, content in enumerate(documents):
            meta = metadatas[idx] if metadatas else None
            ids.append(self.add_document(content, metadata=meta))
        return ids

    # ------------------------------------------------------------------
    #  RRF 融合
    # ------------------------------------------------------------------

    @staticmethod
    def _rrf_scores(
        ranked_ids: Sequence[int],
        rrf_k: int,
        weight: float = 1.0,
    ) -> Dict[int, float]:
        """计算一路检索结果的 RRF 贡献分。

        Args:
            ranked_ids: 按相关性降序排列的文档 ID 列表。
            rrf_k: RRF 常数。
            weight: 该路权重。

        Returns:
            文档 ID -> RRF 分数的映射。
        """
        scores: Dict[int, float] = {}
        for rank, doc_id in enumerate(ranked_ids, start=1):
            scores[doc_id] = weight / (rrf_k + rank)
        return scores

    def _time_decay_factor(self, metadata: Dict[str, Any]) -> float:
        """计算时间衰减因子。

        衰减公式::

            factor = 0.5 + 0.5 * exp(-ln(2) * age / half_life)

        即半衰期时因子降为 0.75，无穷久时趋近 0.5（不至于完全消失）。

        Args:
            metadata: 文档元数据，需包含 ``timestamp`` 或 ``added_at``。

        Returns:
            衰减因子，范围 [0.5, 1.0]。若未配置半衰期或缺少时间戳，
            返回 1.0（不衰减）。
        """
        if self.time_decay_half_life <= 0:
            return 1.0

        ts = metadata.get("timestamp") or metadata.get("added_at")
        if ts is None:
            return 1.0

        age = max(0.0, time.time() - float(ts))
        # 指数衰减: exp(-ln2 * age / half_life)
        decay = math.exp(-math.log(2.0) * age / self.time_decay_half_life)
        # 将衰减映射到 [0.5, 1.0]，老记忆不会完全归零
        return 0.5 + 0.5 * decay

    def search(
        self,
        query: str,
        top_k: int = 5,
        candidate_ids: Optional[Sequence[int]] = None,
    ) -> List[RetrievalResult]:
        """执行 BM25 + Dense 混合检索。

        流程：

        1. 分别从 BM25 和 Dense 检索 top_k × 2 的候选。
        2. 用 RRF 融合两路排名。
        3. 应用时间衰减因子。
        4. 返回融合后 top_k 结果。

        Args:
            query: 查询文本。
            top_k: 返回结果数上限。
            candidate_ids: 可选的候选文档 ID 子集。

        Returns:
            :class:`RetrievalResult` 列表，按融合分数降序。
        """
        if self._n_docs == 0 or top_k <= 0:
            return []

        # 每路取更多候选以提升融合质量
        fetch_k = min(top_k * 3, self._n_docs)

        bm25_results = self.bm25.search(
            query, top_k=fetch_k, candidate_ids=candidate_ids
        )
        dense_results = self.dense.search(
            query, top_k=fetch_k, candidate_ids=candidate_ids
        )

        # 计算 RRF 分数
        bm25_ranked = [r.doc_id for r in bm25_results]
        dense_ranked = [r.doc_id for r in dense_results]

        bm25_scores = self._rrf_scores(
            bm25_ranked, self.rrf_k, self.bm25_weight
        )
        dense_scores = self._rrf_scores(
            dense_ranked, self.rrf_k, self.dense_weight
        )

        # 合并所有出现在任一路结果中的文档
        all_doc_ids: set = set(bm25_scores.keys()) | set(dense_scores.keys())

        fused: List[Tuple[float, int]] = []
        for doc_id in all_doc_ids:
            rrf = bm25_scores.get(doc_id, 0.0) + dense_scores.get(doc_id, 0.0)

            # 时间衰减
            meta = self._doc_metadata[doc_id] if doc_id < len(
                self._doc_metadata
            ) else {}
            decay = self._time_decay_factor(meta)
            final_score = rrf * decay

            fused.append((final_score, doc_id))

        fused.sort(key=lambda x: x[0], reverse=True)

        results: List[RetrievalResult] = []
        for score, doc_id in fused[:top_k]:
            results.append(
                RetrievalResult(
                    doc_id=doc_id,
                    content=self._documents[doc_id],
                    score=score,
                    metadata=dict(self._doc_metadata[doc_id]),
                )
            )
        return results

    # ------------------------------------------------------------------
    #  属性
    # ------------------------------------------------------------------

    @property
    def n_docs(self) -> int:
        """文档总数。"""
        return self._n_docs

    def get_document(self, doc_id: int) -> Optional[str]:
        """根据 ID 获取文档原文。"""
        if 0 <= doc_id < self._n_docs:
            return self._documents[doc_id]
        return None

    def get_metadata(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取文档元数据。"""
        if 0 <= doc_id < self._n_docs:
            return dict(self._doc_metadata[doc_id])
        return None

    def __len__(self) -> int:
        return self._n_docs

    def __repr__(self) -> str:
        return (
            f"AMLHybridRetriever(n_docs={self._n_docs}, "
            f"rrf_k={self.rrf_k}, "
            f"weights=({self.bm25_weight}, {self.dense_weight}), "
            f"time_decay={self.time_decay_half_life})"
        )
