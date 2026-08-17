"""MemRL 轻量 Utility 重排器 — v1.10.0 P1 改造。

本模块实现 :class:`UtilityReranker`，在 v1.9.0 已有的 BM25 + Dense RRF
混合检索（参见 :mod:`suyi.memory.hybrid_retriever`）基础上，对 RRF 召回
的候选记忆做"第二阶段"utility 重排。

设计灵感来自 MemRL（Zhang, Wang et al., 2026, arXiv:2601.03192）：
给每条候选记忆基于多维度特征计算一个 utility 分数，用于对结果重排序；
并通过在线监督信号（某条记忆是否被真正使用）增量更新线性模型权重。
所有实现均为纯 Python + numpy，不修改任何基础模型权重，不调用 LLM。

特征向量（共 :data:`N_FEATURES` = 10 维）
----------------------------------------

1. ``bm25_score``      — 候选在 BM25 路的得分（候选集内 min-max 归一化）。
2. ``dense_score``     — 候选在 Dense 路的余弦相似度（候选集内归一化）。
3. ``rrf_score``       — RRF 融合分数（候选集内归一化）。
4. ``time_decay``      — 时间衰减因子，越新越大，范围 [0.5, 1.0]。
5. ``layer_working``   — one-hot：是否来自 working 层。
6. ``layer_episodic``  — one-hot：是否来自 episodic 层。
7. ``layer_semantic``  — one-hot：是否来自 semantic 层。
8. ``access_count``    — 访问频次归一化（log1p 后除以候选集最大值）。
9. ``content_length``  — 内容 token 长度归一化（除以候选集最大长度）。
10. ``query_overlap``  — 查询与候选 token 集合的 Jaccard 重叠率。

Utility 模型
------------

一个简单的线性模型 + sigmoid 概率::

    p(useful) = sigmoid(w · x + b)

权重通过在线 logistic 回归（SGD + L2 正则）增量更新，相当于 LinUCB /
contextual bandit 的简化版本：

- ``fit_partial(features, labels)`` 传入一组特征和标签（1=被使用，
  0=未使用），用一步梯度下降更新权重。
- 冷启动时加载合理默认权重：相关性（RRF/BM25/Dense/重叠率）和 recency
  权重较高，semantic 层略高于 working/episodic（因为 semantic 存的是
  已提炼的事实/规则/偏好）。

持久化
------

权重保存到 ``~/.suyi/aml_memory/utility_weights.json``（路径可配置），
保存结构为 ``{"weights": [...], "bias": float, "updated_at": ...,
"n_updates": int}``。文件不存在或损坏时使用冷启动默认权重。

训练数据记录
------------

调用方可在每次 search 后调用 :meth:`record_search`，将
``(query, candidate_ids, clicked_ids)`` 追加到
``~/.suyi/aml_memory/utility_training_log.jsonl``。该方法只做追加写入，
不直接更新权重；权重更新由调用方选择时机批量执行
:meth:`ingest_log` 或直接 :meth:`fit_partial`。这样设计的目的是让
"记录"和"训练"解耦，避免在 HTTP 请求热路径里做模型更新。
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from .hybrid_retriever import tokenize


# ----------------------------------------------------------------------
#  常量
# ----------------------------------------------------------------------

#: 特征向量维度。修改特征时务必同步更新 :data:`FEATURE_NAMES` 和
#: :meth:`UtilityReranker._default_weights`。
N_FEATURES: int = 10

#: 特征名称，按向量索引顺序排列。主要用于调试、导出和权重可解释性。
FEATURE_NAMES: Tuple[str, ...] = (
    "bm25_score",
    "dense_score",
    "rrf_score",
    "time_decay",
    "layer_working",
    "layer_episodic",
    "layer_semantic",
    "access_count",
    "content_length",
    "query_overlap",
)

#: 默认权重持久化路径（相对用户 home 目录）。
DEFAULT_WEIGHTS_RELPATH: str = os.path.join(".suyi", "aml_memory",
                                            "utility_weights.json")

#: 默认训练日志路径。
DEFAULT_TRAIN_LOG_RELPATH: str = os.path.join(".suyi", "aml_memory",
                                              "utility_training_log.jsonl")

# 三层记忆名称（与 :mod:`suyi.memory.aml_memory` 保持一致，此处独立
# 定义以避免循环导入；只在内部做 one-hot 编码使用）。
_LAYER_WORKING = "working"
_LAYER_EPISODIC = "episodic"
_LAYER_SEMANTIC = "semantic"
_ALL_LAYERS = (_LAYER_WORKING, _LAYER_EPISODIC, _LAYER_SEMANTIC)


# ----------------------------------------------------------------------
#  候选数据类
# ----------------------------------------------------------------------

@dataclass
class RerankCandidate:
    """重排器输入候选。

    Attributes:
        doc_id: 在 :class:`~suyi.memory.hybrid_retriever.AMLHybridRetriever`
            中的文档 ID。
        content: 候选记忆文本。
        bm25_score: BM25 单路得分（无则 0）。
        dense_score: Dense 单路余弦相似度（无则 0）。
        rrf_score: RRF 融合得分（无则 0）。
        layer: 记忆层名（``working`` / ``episodic`` / ``semantic``）。
        timestamp: 记忆时间戳（Unix 秒），用于时间衰减。
        access_count: 历史访问次数，用于访问频次特征。
        metadata: 其它元数据，保留以便扩展。
    """

    doc_id: int
    content: str
    bm25_score: float = 0.0
    dense_score: float = 0.0
    rrf_score: float = 0.0
    layer: str = _LAYER_EPISODIC
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RerankResult:
    """重排结果。

    Attributes:
        candidate: 对应的候选对象。
        utility: sigmoid 后的 utility 概率，范围 [0, 1]。
        features: 用于打分的特征向量（调试/可解释性用）。
    """

    candidate: RerankCandidate
    utility: float
    features: np.ndarray


# ----------------------------------------------------------------------
#  特征提取
# ----------------------------------------------------------------------

def _minmax(values: Sequence[float]) -> List[float]:
    """对一组数值做 min-max 归一化。

    - 全部相等或只有一个值时，全部返回 1.0（让该维度对排序保持中性，
      不引入噪声）。
    - 若最大值与最小值相等，返回全 1.0。

    Args:
        values: 原始数值序列。

    Returns:
        归一化后的列表，长度与 ``values`` 相同，范围 [0, 1]。
    """
    if not values:
        return []
    arr = np.asarray(values, dtype=np.float64)
    lo = float(arr.min())
    hi = float(arr.max())
    if hi - lo < 1e-12:
        return [1.0 for _ in values]
    return ((arr - lo) / (hi - lo)).tolist()


def _time_decay(
    timestamp: Optional[float],
    half_life: float,
    now: Optional[float] = None,
) -> float:
    """计算时间衰减因子，范围 [0.5, 1.0]。

    公式与 :meth:`AMLHybridRetriever._time_decay_factor` 保持一致::

        decay = 0.5 + 0.5 * exp(-ln(2) * age_seconds / half_life)

    这样设计有两点考虑：

    - 半衰期时衰减因子为 0.75，对排序仍有贡献；
    - 无穷久时最低 0.5，老记忆不会完全被归零。

    Args:
        timestamp: 记忆的 Unix 秒时间戳。
        half_life: 半衰期（秒），<=0 时禁用衰减（返回 1.0）。
        now: 当前时间，主要用于测试注入；None 时取 :func:`time.time`。

    Returns:
        衰减因子。
    """
    if half_life <= 0 or timestamp is None:
        return 1.0
    if now is None:
        now = time.time()
    age = max(0.0, float(now) - float(timestamp))
    return 0.5 + 0.5 * math.exp(-math.log(2.0) * age / float(half_life))


def extract_features(
    query: str,
    candidate: RerankCandidate,
    *,
    bm25_norm: float = 0.0,
    dense_norm: float = 0.0,
    rrf_norm: float = 0.0,
    access_norm: float = 0.0,
    length_norm: float = 0.0,
    time_decay_half_life: float = 7 * 24 * 3600.0,
    now: Optional[float] = None,
) -> np.ndarray:
    """为单个候选构造 10 维特征向量。

    跨候选的归一化（min-max 等）必须由调用方先在整个候选集上算好，再
    通过 ``*_norm`` 参数传入；本函数只负责构造单条向量。这样做是为了
    让每个特征的"上下文"一致，同时避免在循环中重复扫描候选集。

    Args:
        query: 查询文本。
        candidate: 候选记忆对象。
        bm25_norm: BM25 分数在候选集内 min-max 归一化后的值，[0, 1]。
        dense_norm: Dense 分数归一化后的值，[0, 1]。
        rrf_norm: RRF 分数归一化后的值，[0, 1]。
        access_norm: 访问频次 log1p 归一化后的值，[0, 1]。
        length_norm: 内容 token 长度归一化后的值，[0, 1]。
        time_decay_half_life: 时间衰减半衰期（秒）。
        now: 当前时间戳，测试可注入。

    Returns:
        ``shape=(N_FEATURES,)`` 的 ``numpy.float64`` 向量。
    """
    query_tokens = set(tokenize(query))
    cand_tokens = set(tokenize(candidate.content))
    if query_tokens or cand_tokens:
        overlap = (
            len(query_tokens & cand_tokens)
            / max(1, len(query_tokens | cand_tokens))
        )
    else:
        overlap = 0.0

    decay = _time_decay(
        candidate.timestamp, time_decay_half_life, now=now
    )

    layer = (candidate.layer or "").lower()
    one_hot = [
        1.0 if layer == _LAYER_WORKING else 0.0,
        1.0 if layer == _LAYER_EPISODIC else 0.0,
        1.0 if layer == _LAYER_SEMANTIC else 0.0,
    ]

    vec = np.array(
        [
            float(bm25_norm),
            float(dense_norm),
            float(rrf_norm),
            float(decay),
            one_hot[0],
            one_hot[1],
            one_hot[2],
            float(access_norm),
            float(length_norm),
            float(overlap),
        ],
        dtype=np.float64,
    )
    return vec


# ----------------------------------------------------------------------
#  UtilityReranker
# ----------------------------------------------------------------------

class UtilityReranker:
    """MemRL 风格的线性 utility 重排器。

    使用一个 logistic 线性模型为每条候选记忆打分::

        p = sigmoid(w · x + b)

    其中 ``x`` 是 :func:`extract_features` 构造的 10 维特征。权重可
    通过 :meth:`fit_partial` 在线增量学习，也可从磁盘加载/持久化。

    该类是**线程安全**的：所有权重读写都在内部 ``RLock`` 保护下完成，
    可被多线程 HTTP 服务器（:class:`AMLMemoryServer`）共享使用。

    Attributes:
        learning_rate: SGD 学习率，默认 0.01。
        l2_lambda: L2 正则系数，默认 0.001。
        time_decay_half_life: 特征中时间衰减的半衰期（秒）。
        weights_path: 权重持久化文件路径。
        training_log_path: 训练日志 JSONL 路径。
    """

    def __init__(
        self,
        *,
        learning_rate: float = 0.01,
        l2_lambda: float = 0.001,
        time_decay_half_life: float = 7 * 24 * 3600.0,
        weights_path: Optional[str] = None,
        training_log_path: Optional[str] = None,
        auto_load: bool = True,
    ) -> None:
        """初始化 utility 重排器。

        Args:
            learning_rate: SGD 学习率。必须 > 0。
            l2_lambda: L2 正则系数，>=0。越大权重越被推向 0，过拟合
                风险越低；设为 0 则关闭正则。
            time_decay_half_life: 时间衰减半衰期（秒）。<=0 禁用。
            weights_path: 权重 JSON 路径。None 时使用
                ``~/.suyi/aml_memory/utility_weights.json``。
            training_log_path: 训练日志 JSONL 路径。None 时使用
                ``~/.suyi/aml_memory/utility_training_log.jsonl``。
            auto_load: 是否在初始化时自动从磁盘加载已持久化权重。
        """
        if learning_rate <= 0:
            raise ValueError("learning_rate must be > 0")
        if l2_lambda < 0:
            raise ValueError("l2_lambda must be >= 0")

        self.learning_rate = float(learning_rate)
        self.l2_lambda = float(l2_lambda)
        self.time_decay_half_life = float(time_decay_half_life)

        home = os.path.expanduser("~")
        self.weights_path = (
            weights_path
            if weights_path is not None
            else os.path.join(home, DEFAULT_WEIGHTS_RELPATH)
        )
        self.training_log_path = (
            training_log_path
            if training_log_path is not None
            else os.path.join(home, DEFAULT_TRAIN_LOG_RELPATH)
        )

        # 权重和偏置
        self._weights: np.ndarray
        self._bias: float
        self._n_updates: int = 0

        # 并发保护
        self._lock = threading.RLock()

        # 先设置默认值，再尝试加载（加载失败保留默认值）
        self._reset_to_defaults()
        if auto_load:
            self.load_weights()

    # ------------------------------------------------------------------
    #  默认权重 / 持久化
    # ------------------------------------------------------------------

    def _reset_to_defaults(self) -> None:
        """重置为冷启动默认权重。

        默认权重偏向相关性（RRF/BM25/Dense/query overlap）和 recency；
        semantic 层略受偏好（已提炼的事实/规则/偏好通常质量更高），
        episodic 次之，working 因为上下文最新也有一定权重；内容长度
        设为 0，不偏向长或短。

        权重数值在 [-2, 2] 范围内，避免 sigmoid 饱和，保留学习空间。
        """
        defaults = {
            "bm25_score": 1.20,
            "dense_score": 1.00,
            "rrf_score": 1.80,
            "time_decay": 1.20,
            "layer_working": 0.20,
            "layer_episodic": 0.10,
            "layer_semantic": 0.50,
            "access_count": 0.40,
            "content_length": 0.00,
            "query_overlap": 1.00,
        }
        self._weights = np.array(
            [defaults[name] for name in FEATURE_NAMES],
            dtype=np.float64,
        )
        self._bias = -0.20
        self._n_updates = 0

    def reset_defaults(self) -> None:
        """对外公开的重置接口：清空学习成果，恢复冷启动默认权重。

        注意：该方法**只修改内存**，不会删除磁盘上的权重文件。若需
        同时重置磁盘文件，请随后调用 :meth:`save_weights`。
        """
        with self._lock:
            self._reset_to_defaults()

    def save_weights(self) -> bool:
        """把当前权重持久化到 JSON 文件。

        采用"先写临时文件再原子替换"策略，避免写一半进程崩溃导致
        文件损坏。

        Returns:
            保存成功返回 True，IO 失败返回 False（仅记录，不抛异常，
            因为权重保存失败不应中断线上检索）。
        """
        with self._lock:
            payload = {
                "version": 1,
                "feature_names": list(FEATURE_NAMES),
                "weights": self._weights.tolist(),
                "bias": float(self._bias),
                "n_updates": int(self._n_updates),
                "updated_at": time.time(),
                "learning_rate": self.learning_rate,
                "l2_lambda": self.l2_lambda,
            }
            try:
                os.makedirs(
                    os.path.dirname(self.weights_path) or ".",
                    exist_ok=True,
                )
                tmp = self.weights_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                os.replace(tmp, self.weights_path)
                return True
            except OSError as exc:
                # 持久化失败不应影响运行
                print(f"[UtilityReranker] 保存权重失败: {exc}")
                return False

    def load_weights(self) -> bool:
        """从 JSON 文件加载权重。

        - 文件不存在：静默返回 False，保留当前内存权重（通常是默认值）。
        - 文件损坏或维度不匹配：打印警告，保留当前权重，返回 False。
        - 成功加载：覆盖内存权重，返回 True。

        Returns:
            是否成功加载。
        """
        if not os.path.exists(self.weights_path):
            return False
        try:
            with open(self.weights_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            w = np.asarray(data.get("weights", []), dtype=np.float64)
            if w.shape != (N_FEATURES,):
                print(
                    "[UtilityReranker] 权重维度不匹配，期望 "
                    f"{N_FEATURES} 实际 {w.shape}，忽略已保存权重。"
                )
                return False
            bias = float(data.get("bias", 0.0))
            with self._lock:
                self._weights = w
                self._bias = bias
                self._n_updates = int(data.get("n_updates", 0))
            return True
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            print(f"[UtilityReranker] 加载权重失败: {exc}")
            return False

    @property
    def weights(self) -> np.ndarray:
        """当前权重向量的只读副本。"""
        with self._lock:
            return self._weights.copy()

    @property
    def bias(self) -> float:
        """当前偏置。"""
        with self._lock:
            return float(self._bias)

    @property
    def n_updates(self) -> int:
        """累计执行的梯度更新步数。"""
        with self._lock:
            return int(self._n_updates)

    def get_weight_dict(self) -> Dict[str, float]:
        """返回 ``{feature_name: weight}`` 映射，便于调试/可解释性。"""
        with self._lock:
            return {
                name: float(self._weights[i])
                for i, name in enumerate(FEATURE_NAMES)
            }

    # ------------------------------------------------------------------
    #  特征批处理
    # ------------------------------------------------------------------

    def _build_feature_matrix(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        now: Optional[float] = None,
    ) -> np.ndarray:
        """为一组候选批量构造特征矩阵，并在候选集内做归一化。

        Args:
            query: 查询文本。
            candidates: 候选列表。
            now: 当前时间戳，测试可注入。

        Returns:
            ``shape=(len(candidates), N_FEATURES)`` 的特征矩阵。
        """
        if not candidates:
            return np.zeros((0, N_FEATURES), dtype=np.float64)

        bm25_n = _minmax([c.bm25_score for c in candidates])
        dense_n = _minmax([c.dense_score for c in candidates])
        rrf_n = _minmax([c.rrf_score for c in candidates])
        access_raw = [
            math.log1p(max(0, c.access_count)) for c in candidates
        ]
        access_n = _minmax(access_raw)
        length_raw = [max(1, len(tokenize(c.content))) for c in candidates]
        max_len = max(length_raw) if length_raw else 1
        length_n = [l / max_len for l in length_raw]

        rows = [
            extract_features(
                query,
                cand,
                bm25_norm=bm25_n[i],
                dense_norm=dense_n[i],
                rrf_norm=rrf_n[i],
                access_norm=access_n[i],
                length_norm=length_n[i],
                time_decay_half_life=self.time_decay_half_life,
                now=now,
            )
            for i, cand in enumerate(candidates)
        ]
        return np.vstack(rows)

    # ------------------------------------------------------------------
    #  打分 / 重排
    # ------------------------------------------------------------------

    @staticmethod
    def _sigmoid(z: np.ndarray) -> np.ndarray:
        """数值稳定的 sigmoid。"""
        # 对大负数和大正数分别截断，避免 exp 溢出
        out = np.empty_like(z, dtype=np.float64)
        pos = z >= 0
        out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
        exp_z = np.exp(z[~pos])
        out[~pos] = exp_z / (1.0 + exp_z)
        return out

    def score(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        *,
        return_features: bool = False,
        now: Optional[float] = None,
    ) -> List[RerankResult]:
        """对候选列表计算 utility 分数（保持原顺序，不做排序）。

        Args:
            query: 查询文本。
            candidates: 候选列表。
            return_features: 是否在结果中返回特征向量。
            now: 注入当前时间，测试用。

        Returns:
            :class:`RerankResult` 列表，顺序与输入一致。
        """
        if not candidates:
            return []

        feats = self._build_feature_matrix(query, candidates, now=now)
        with self._lock:
            w = self._weights
            b = self._bias
        z = feats @ w + b
        probs = self._sigmoid(z)

        results: List[RerankResult] = []
        for i, cand in enumerate(candidates):
            results.append(
                RerankResult(
                    candidate=cand,
                    utility=float(probs[i]),
                    features=feats[i] if return_features else np.array([]),
                )
            )
        return results

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        top_k: int = 5,
        *,
        return_features: bool = False,
        now: Optional[float] = None,
    ) -> List[RerankResult]:
        """对候选列表重排并取 top_k。

        Args:
            query: 查询文本。
            candidates: RRF 召回的候选列表（可多于 top_k）。
            top_k: 返回结果数量上限。若 <=0 返回空列表。
            return_features: 是否附带特征向量。
            now: 注入当前时间。

        Returns:
            按 utility 降序排列的 :class:`RerankResult`，至多 ``top_k`` 条。
            分数相同的候选保持其在输入中的相对顺序（稳定排序）。
        """
        if top_k <= 0 or not candidates:
            return []

        scored = self.score(
            query, candidates, return_features=return_features, now=now
        )
        # 稳定排序：按 utility 降序
        order = sorted(
            range(len(scored)),
            key=lambda i: scored[i].utility,
            reverse=True,
        )
        return [scored[i] for i in order[:top_k]]

    # ------------------------------------------------------------------
    #  在线学习
    # ------------------------------------------------------------------

    def fit_partial(
        self,
        features: np.ndarray,
        labels: np.ndarray,
        *,
        persist: bool = False,
    ) -> Dict[str, float]:
        """用一批 (features, labels) 做一步 SGD 更新。

        logistic 损失对单个样本的梯度::

            dw = (p - y) * x + 2 * lambda * w
            db = (p - y)

        其中 ``p = sigmoid(w·x + b)``。批量更新时对 batch 内的梯度
        取平均。

        Args:
            features: ``shape=(n_samples, N_FEATURES)`` 的特征矩阵。
            labels: ``shape=(n_samples,)`` 的标签数组，1 表示该记忆被
                成功使用，0 表示未使用。其它值会被 clip 到 [0, 1]。
            persist: 更新后是否立即保存权重到磁盘。

        Returns:
            字典，包含本次更新前在该 batch 上的平均 ``loss``（二元
            交叉熵）、``accuracy`` 和 ``batch_size``，便于监控。
        """
        X = np.asarray(features, dtype=np.float64)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        if X.shape[0] == 0:
            return {"loss": 0.0, "accuracy": 0.0, "batch_size": 0}
        if X.shape[1] != N_FEATURES:
            raise ValueError(
                f"features 第二维必须为 {N_FEATURES}，实际 {X.shape[1]}"
            )

        y = np.asarray(labels, dtype=np.float64).reshape(-1)
        if y.shape[0] != X.shape[0]:
            raise ValueError(
                "features 和 labels 的样本数不一致："
                f"{X.shape[0]} vs {y.shape[0]}"
            )
        # clip 标签，容忍噪声
        y = np.clip(y, 0.0, 1.0)

        with self._lock:
            w = self._weights
            b = self._bias
            z = X @ w + b
            p = self._sigmoid(z)
            error = p - y  # shape=(n,)
            n = X.shape[0]

            # 交叉熵损失（含 L2），用于监控；裁剪概率避免 log(0)
            eps = 1e-9
            loss = float(
                -np.mean(
                    y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)
                )
                + self.l2_lambda * float(w @ w)
            )
            preds = (p >= 0.5).astype(np.float64)
            accuracy = float(np.mean(preds == y))

            # 梯度
            grad_w = (X.T @ error) / n + 2.0 * self.l2_lambda * w
            grad_b = float(np.mean(error))

            # SGD 更新
            self._weights = w - self.learning_rate * grad_w
            self._bias = b - self.learning_rate * grad_b
            self._n_updates += 1

        if persist:
            self.save_weights()

        return {
            "loss": loss,
            "accuracy": accuracy,
            "batch_size": int(n),
        }

    def train_on_candidates(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        used_doc_ids: Iterable[int],
        *,
        persist: bool = False,
        now: Optional[float] = None,
    ) -> Dict[str, float]:
        """便捷方法：基于"哪些候选被使用"直接做一步训练。

        为所有候选构造特征，正样本为 ``used_doc_ids`` 中出现的候选，
        其它为负样本。这正好对应报告里"被 Answer 引用的记忆 +1，
        未被引用的 -0.1"思想的标签化实现。

        Args:
            query: 查询文本。
            candidates: 参与此次检索的候选列表（建议用 rerank 之前的
                完整候选集，以获得更丰富的负样本）。
            used_doc_ids: 被实际使用的 doc_id 集合。
            persist: 是否立即持久化权重。
            now: 当前时间注入。

        Returns:
            透传 :meth:`fit_partial` 的训练统计。
        """
        if not candidates:
            return {"loss": 0.0, "accuracy": 0.0, "batch_size": 0}
        used_set = {int(x) for x in used_doc_ids}
        X = self._build_feature_matrix(query, candidates, now=now)
        y = np.array(
            [1.0 if c.doc_id in used_set else 0.0 for c in candidates],
            dtype=np.float64,
        )
        return self.fit_partial(X, y, persist=persist)

    # ------------------------------------------------------------------
    #  训练日志（记录 -> 批量训练）
    # ------------------------------------------------------------------

    def record_search(
        self,
        query: str,
        candidate_ids: Sequence[int],
        used_doc_ids: Iterable[int],
        *,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录一次 search 的训练样本到 JSONL 日志（追加写）。

        本方法**不更新权重**，只做磁盘追加，便于把"记录"和"训练"
        解耦：HTTP 请求热路径里调用 ``record_search`` 几乎无成本（一次
        append 写），权重训练可由后台线程或运维任务批量触发
        :meth:`ingest_log`。

        Args:
            query: 本次查询文本。
            candidate_ids: 本次展示给下游的候选 doc_id 列表（顺序即
                展示顺序）。
            used_doc_ids: 实际被使用/点击的 doc_id 集合。
            extra: 可选元数据，例如 user_id、session_id、延迟等。
        """
        entry = {
            "ts": time.time(),
            "query": query,
            "candidates": [int(x) for x in candidate_ids],
            "used": [int(x) for x in used_doc_ids],
        }
        if extra:
            entry["extra"] = extra
        try:
            os.makedirs(
                os.path.dirname(self.training_log_path) or ".",
                exist_ok=True,
            )
            with open(self.training_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            print(f"[UtilityReranker] 写入训练日志失败: {exc}")

    def ingest_log(
        self,
        candidate_lookup,
        *,
        max_entries: Optional[int] = None,
        clear_after: bool = True,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """读取训练日志并批量训练。

        日志中的每条记录需要把 ``candidate_ids`` 反序列化成
        :class:`RerankCandidate`，因此调用方需传入 ``candidate_lookup``
        回调：``lookup(doc_id) -> Optional[RerankCandidate]``。这通常
        由持有 :class:`~suyi.memory.aml_memory.AMLMemoryStore` 的上层
        提供（根据 doc_id 从存储中重建候选）。

        找不到候选的 doc_id 会被静默跳过（可能是因为记忆已被 TTL
        淘汰）。所有日志条目按其查询分别构造 batch（因为 query 影响
        query_overlap 特征），但更新是连续执行的 SGD。

        Args:
            candidate_lookup: ``Callable[[int], Optional[RerankCandidate]]``。
            max_entries: 最多处理多少条日志，None 表示全部。
            clear_after: 训练成功后是否清空日志文件。
            persist: 训练完成后是否保存权重。

        Returns:
            汇总统计：``processed_entries``、``skipped_entries``、
            ``total_samples``、``last_metrics``。
        """
        if not os.path.exists(self.training_log_path):
            return {
                "processed_entries": 0,
                "skipped_entries": 0,
                "total_samples": 0,
                "last_metrics": None,
            }

        processed = 0
        skipped = 0
        total_samples = 0
        last_metrics: Optional[Dict[str, float]] = None

        remaining_lines: List[str] = []
        try:
            with open(self.training_log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as exc:
            print(f"[UtilityReranker] 读取训练日志失败: {exc}")
            return {
                "processed_entries": 0,
                "skipped_entries": 0,
                "total_samples": 0,
                "last_metrics": None,
            }

        for idx, line in enumerate(lines):
            if max_entries is not None and processed >= max_entries:
                remaining_lines = lines[idx:]
                break
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            query = entry.get("query", "")
            cand_ids = entry.get("candidates", [])
            used = set(int(x) for x in entry.get("used", []))

            cands: List[RerankCandidate] = []
            labels: List[float] = []
            for cid in cand_ids:
                cand = candidate_lookup(int(cid))
                if cand is None:
                    continue
                cands.append(cand)
                labels.append(1.0 if int(cid) in used else 0.0)

            if not cands:
                skipped += 1
                continue

            X = self._build_feature_matrix(query, cands)
            y = np.asarray(labels, dtype=np.float64)
            last_metrics = self.fit_partial(X, y, persist=False)
            total_samples += len(cands)
            processed += 1

        if clear_after:
            try:
                # 写回未处理的日志条目；全部处理完则清空文件
                with open(
                    self.training_log_path, "w", encoding="utf-8"
                ) as f:
                    for leftover in remaining_lines:
                        f.write(leftover if leftover.endswith("\n")
                                else leftover + "\n")
            except OSError as exc:
                print(f"[UtilityReranker] 清理训练日志失败: {exc}")

        if persist and processed > 0:
            self.save_weights()

        return {
            "processed_entries": processed,
            "skipped_entries": skipped,
            "total_samples": total_samples,
            "last_metrics": last_metrics,
        }

    # ------------------------------------------------------------------
    #  工具
    # ------------------------------------------------------------------

    def explain(self, query: str, candidate: RerankCandidate,
                *, now: Optional[float] = None) -> Dict[str, Any]:
        """对单个候选的 utility 做可解释性分解。

        返回每项特征的名称、原始值和对 logit 的贡献（weight * value），
        以及最终的 sigmoid 概率。主要用于调试和测试断言。

        Args:
            query: 查询文本。
            candidate: 候选。
            now: 时间注入。

        Returns:
            字典，包含 ``features``、``contributions``、``bias``、
            ``logit``、``utility``。
        """
        # 单独一条时，归一化值全为 1.0（与 _minmax 一致）
        vec = extract_features(
            query,
            candidate,
            bm25_norm=1.0,
            dense_norm=1.0,
            rrf_norm=1.0,
            access_norm=1.0,
            length_norm=1.0,
            time_decay_half_life=self.time_decay_half_life,
            now=now,
        )
        with self._lock:
            w = self._weights
            b = self._bias
        contributions = {
            name: float(w[i] * vec[i])
            for i, name in enumerate(FEATURE_NAMES)
        }
        logit = float(w @ vec + b)
        utility = float(self._sigmoid(np.array([logit]))[0])
        return {
            "features": {
                name: float(vec[i])
                for i, name in enumerate(FEATURE_NAMES)
            },
            "contributions": contributions,
            "weights": self.get_weight_dict(),
            "bias": float(b),
            "logit": logit,
            "utility": utility,
        }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"UtilityReranker(n_features={N_FEATURES}, "
                f"lr={self.learning_rate}, l2={self.l2_lambda}, "
                f"updates={self._n_updates})"
            )
