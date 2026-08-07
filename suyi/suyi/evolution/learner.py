"""学习引擎 — 从交互记录中提取模式并更新行为策略.

设计原则：
- **频率统计优先**：通过 n-gram 频率统计识别高频工具序列，
  不依赖嵌入模型，保持纯 numpy/标准库依赖.
- **简单聚类**：使用 numpy 实现的 k-means 对交互特征向量聚类，
  发现隐含的行为模式群组.
- **成功率驱动**：策略更新基于成功率和频率的加权，
  高频高成功率模式被巩固为经验规则.
- **JSON 持久化**：所有数据存储在 JSON 文件中，
  便于调试和人类可读.

核心数据流::

    InteractionRecord ──▶ extract_patterns() ──▶ Pattern[]
                                                │
                    update_policy() ◀──────────┘
                           │
                    consolidate_rules() ──▶ experience rules (JSON)
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ═══════════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════════


@dataclass
class InteractionRecord:
    """单次 Agent 交互的完整记录.

    Attributes:
        id: 交互唯一标识符.
        task: 用户任务描述.
        tool_calls: 工具调用序列，每项为
            ``{"name": str, "arguments": dict, "success": bool, "output_summary": str}``.
        success: 任务是否成功完成.
        duration: 执行耗时（秒）.
        tokens_used: 总 token 消耗.
        timestamp: Unix 时间戳.
        version: 策略版本标签（用于 A/B 评估）.
        feedback: 关联的反馈信息字典.
        tags: 上下文标签（如任务类型）.
    """

    id: str = ""
    task: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = False
    duration: float = 0.0
    tokens_used: int = 0
    timestamp: float = 0.0
    version: str = "default"
    feedback: Optional[Dict[str, Any]] = None
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = f"int_{uuid.uuid4().hex[:12]}"
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def tool_sequence(self) -> List[str]:
        """返回工具名称序列（按调用顺序）."""
        return [tc.get("name", "unknown") for tc in self.tool_calls]

    @property
    def tool_success_rate(self) -> float:
        """单个工具调用的成功率."""
        if not self.tool_calls:
            return 0.0
        successes = sum(1 for tc in self.tool_calls if tc.get("success", False))
        return successes / len(self.tool_calls)

    def to_dict(self) -> dict:
        """转换为字典（用于 JSON 序列化）."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "InteractionRecord":
        """从字典创建实例."""
        return cls(**d)


@dataclass
class Pattern:
    """从交互记录中提取的行为模式.

    Attributes:
        id: 模式唯一标识符.
        tool_sequence: 工具名称序列.
        context_tags: 上下文标签.
        frequency: 出现频率（在多少次交互中出现）.
        success_rate: 成功率（0.0–1.0）.
        avg_duration: 平均耗时（秒）.
        avg_tokens: 平均 token 消耗.
        example_tasks: 示例任务描述列表.
        confidence: 统计置信度（0.0–1.0），基于频率和样本量.
        pattern_type: 模式类型 — ``'success'`` / ``'failure'`` / ``'neutral'``.
    """

    id: str = ""
    tool_sequence: List[str] = field(default_factory=list)
    context_tags: List[str] = field(default_factory=list)
    frequency: int = 0
    success_rate: float = 0.0
    avg_duration: float = 0.0
    avg_tokens: int = 0
    example_tasks: List[str] = field(default_factory=list)
    confidence: float = 0.0
    pattern_type: str = "neutral"

    def __post_init__(self):
        if not self.id:
            self.id = f"pat_{uuid.uuid4().hex[:12]}"

    @property
    def is_high_value(self) -> bool:
        """是否为高价值模式（高频 + 高成功率）."""
        return self.frequency >= 3 and self.success_rate >= 0.7

    def to_dict(self) -> dict:
        """转换为字典."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Pattern":
        """从字典创建实例."""
        return cls(**d)


@dataclass
class BehaviorPolicy:
    """从学习结果导出的行为策略.

    Attributes:
        version: 策略版本号.
        tool_preferences: 工具偏好分数（工具名 → 0.0–1.0）.
        preferred_sequences: 推荐的工具序列列表.
        avoidance_sequences: 应避免的工具序列列表.
        parameters: 可调参数（如默认重试次数等）.
        experience_rules: 已巩固的经验规则列表.
        updated_at: 最后更新时间戳.
        stats: 统计信息（总交互数、成功率等）.
    """

    version: str = "v1"
    tool_preferences: Dict[str, float] = field(default_factory=dict)
    preferred_sequences: List[Dict[str, Any]] = field(default_factory=list)
    avoidance_sequences: List[Dict[str, Any]] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    experience_rules: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: float = 0.0
    stats: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.updated_at == 0.0:
            self.updated_at = time.time()

    def get_tool_preference(self, tool_name: str) -> float:
        """获取工具偏好分数，默认 0.5."""
        return self.tool_preferences.get(tool_name, 0.5)

    def to_dict(self) -> dict:
        """转换为字典."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BehaviorPolicy":
        """从字典创建实例."""
        return cls(**d)


# ═══════════════════════════════════════════════════════════════
#  Learning Engine
# ═══════════════════════════════════════════════════════════════


class LearningEngine:
    """学习引擎 — 模式提取、策略更新、规则巩固.

    从交互记录中提取成功路径、失败模式和工具使用偏好，
    基于成功率和频率更新行为策略，
    将高频成功模式自动巩固为经验规则.

    模式提取方法：
        1. **N-gram 频率统计**：提取工具序列的 n-gram（n=1,2,3），
           统计频率和成功率.
        2. **K-means 聚类**：将交互向量化后用 numpy k-means 聚类，
           发现隐含的行为群组.

    Usage::

        engine = LearningEngine(storage_dir="data/evolution")
        engine.record_interaction(record)
        patterns = engine.extract_patterns()
        engine.update_policy()
        rules = engine.consolidate_rules()
    """

    # 默认 n-gram 长度范围
    DEFAULT_NGRAM_RANGE: Tuple[int, int] = (1, 3)

    # 巩固为经验规则的阈值
    CONSOLIDATE_MIN_FREQUENCY: int = 3
    CONSOLIDATE_MIN_SUCCESS_RATE: float = 0.7

    # 默认 k-means 聚类数
    DEFAULT_K: int = 3

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        ngram_range: Optional[Tuple[int, int]] = None,
    ):
        """
        Args:
            storage_dir: 数据持久化目录. 默认为 ``suyi/data/evolution/``.
            ngram_range: n-gram 长度范围（min_n, max_n）.
        """
        if storage_dir is None:
            # 相对于本文件向上找到 suyi 包根目录
            pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            storage_dir = os.path.join(pkg_root, "data", "evolution")

        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

        self.ngram_range = ngram_range or self.DEFAULT_NGRAM_RANGE

        # 内部状态
        self._interactions: List[InteractionRecord] = []
        self._patterns: List[Pattern] = []
        self._policy: BehaviorPolicy = BehaviorPolicy()

        # 工具名 → 全局统计
        self._tool_stats: Dict[str, Dict[str, Any]] = {}

        # 尝试加载已有数据
        self._load()

    # ── 交互记录管理 ──────────────────────────────────────

    def record_interaction(self, record: InteractionRecord) -> None:
        """记录一次交互.

        Args:
            record: 交互记录实例.
        """
        self._interactions.append(record)
        self._update_tool_stats(record)

    def record_interactions(self, records: List[InteractionRecord]) -> None:
        """批量记录交互.

        Args:
            records: 交互记录列表.
        """
        for record in records:
            self.record_interaction(record)

    def get_interactions(self) -> List[InteractionRecord]:
        """返回所有交互记录."""
        return list(self._interactions)

    def get_interaction_count(self) -> int:
        """返回交互记录总数."""
        return len(self._interactions)

    # ── 模式提取 ──────────────────────────────────────────

    def extract_patterns(self) -> List[Pattern]:
        """从交互记录中提取行为模式.

        执行三步：
        1. N-gram 频率统计：提取工具序列的 n-gram，
           统计频率和成功率.
        2. K-means 聚类：将交互向量化后聚类，
           发现行为群组.
        3. 合并去重：合并 n-gram 和聚类结果.

        Returns:
            Pattern 列表，按频率降序排列.
        """
        if not self._interactions:
            self._patterns = []
            return []

        # Step 1: N-gram 频率统计
        ngram_patterns = self._extract_ngram_patterns()

        # Step 2: K-means 聚类
        cluster_patterns = self._extract_cluster_patterns()

        # Step 3: 合并
        all_patterns = ngram_patterns + cluster_patterns
        all_patterns = self._merge_patterns(all_patterns)

        # 按 frequency 降序排列
        all_patterns.sort(key=lambda p: p.frequency, reverse=True)

        self._patterns = all_patterns
        return all_patterns

    def get_patterns(self) -> List[Pattern]:
        """返回最近一次提取的模式列表."""
        return list(self._patterns)

    def get_success_patterns(self) -> List[Pattern]:
        """返回成功模式（success_rate >= 0.7）."""
        return [p for p in self._patterns if p.success_rate >= 0.7]

    def get_failure_patterns(self) -> List[Pattern]:
        """返回失败模式（success_rate < 0.3）."""
        return [p for p in self._patterns if p.success_rate < 0.3]

    # ── 策略更新 ──────────────────────────────────────────

    def update_policy(self) -> BehaviorPolicy:
        """基于提取的模式更新行为策略.

        策略更新规则：
        1. **工具偏好**：按工具成功率加权更新偏好分数.
        2. **推荐序列**：高频高成功率模式加入推荐序列.
        3. **避免序列**：高频低成功率模式加入避免序列.
        4. **参数调优**：根据统计调整默认参数.

        Returns:
            更新后的 BehaviorPolicy.
        """
        if not self._patterns:
            self.extract_patterns()

        # 计算工具偏好
        tool_prefs = self._compute_tool_preferences()

        # 推荐序列
        preferred = [
            {
                "sequence": p.tool_sequence,
                "success_rate": round(p.success_rate, 3),
                "frequency": p.frequency,
                "reason": f"High success rate ({p.success_rate:.0%}) "
                f"across {p.frequency} interactions",
            }
            for p in self._patterns
            if p.is_high_value
        ]

        # 避免序列
        avoidance = [
            {
                "sequence": p.tool_sequence,
                "failure_rate": round(1 - p.success_rate, 3),
                "frequency": p.frequency,
                "reason": f"Low success rate ({p.success_rate:.0%}) "
                f"across {p.frequency} interactions",
            }
            for p in self._patterns
            if p.frequency >= 2 and p.success_rate < 0.3
        ]

        # 参数调优
        params = self._compute_parameters()

        # 统计信息
        stats = self._compute_stats()

        # 版本号递增
        version = self._next_version()

        self._policy = BehaviorPolicy(
            version=version,
            tool_preferences=tool_prefs,
            preferred_sequences=preferred,
            avoidance_sequences=avoidance,
            parameters=params,
            experience_rules=self._policy.experience_rules,
            updated_at=time.time(),
            stats=stats,
        )

        return self._policy

    def get_policy(self) -> BehaviorPolicy:
        """返回当前行为策略."""
        return self._policy

    # ── 经验规则巩固 ──────────────────────────────────────

    def consolidate_rules(self) -> List[Dict[str, Any]]:
        """将高频成功模式巩固为经验规则.

        巩固条件：
        - frequency >= CONSOLIDATE_MIN_FREQUENCY
        - success_rate >= CONSOLIDATE_MIN_SUCCESS_RATE

        每条经验规则包含：
        - rule_id, condition, action, confidence, source_pattern

        Returns:
            经验规则列表.
        """
        if not self._patterns:
            self.extract_patterns()

        new_rules: List[Dict[str, Any]] = []

        for pattern in self._patterns:
            if (
                pattern.frequency >= self.CONSOLIDATE_MIN_FREQUENCY
                and pattern.success_rate >= self.CONSOLIDATE_MIN_SUCCESS_RATE
            ):
                # 检查是否已存在相同规则
                exists = any(
                    r.get("source_pattern") == pattern.id
                    for r in self._policy.experience_rules
                )
                if exists:
                    continue

                rule = {
                    "rule_id": f"rule_{uuid.uuid4().hex[:8]}",
                    "condition": {
                        "task_tags": pattern.context_tags,
                        "tool_sequence": pattern.tool_sequence,
                    },
                    "action": {
                        "recommended_tools": pattern.tool_sequence,
                        "expected_success_rate": round(pattern.success_rate, 3),
                        "expected_duration": round(pattern.avg_duration, 1),
                    },
                    "confidence": round(pattern.confidence, 3),
                    "source_pattern": pattern.id,
                    "created_at": time.time(),
                }
                new_rules.append(rule)
                self._policy.experience_rules.append(rule)

        return new_rules

    def get_experience_rules(self) -> List[Dict[str, Any]]:
        """返回所有经验规则."""
        return list(self._policy.experience_rules)

    # ── 持久化 ────────────────────────────────────────────

    def save(self) -> None:
        """将所有状态持久化到 JSON 文件."""
        # 保存交互记录
        interactions_path = os.path.join(self.storage_dir, "interactions.json")
        with open(interactions_path, "w", encoding="utf-8") as f:
            json.dump(
                [r.to_dict() for r in self._interactions],
                f, ensure_ascii=False, indent=2,
            )

        # 保存模式
        patterns_path = os.path.join(self.storage_dir, "patterns.json")
        with open(patterns_path, "w", encoding="utf-8") as f:
            json.dump(
                [p.to_dict() for p in self._patterns],
                f, ensure_ascii=False, indent=2,
            )

        # 保存策略
        policy_path = os.path.join(self.storage_dir, "policy.json")
        with open(policy_path, "w", encoding="utf-8") as f:
            json.dump(
                self._policy.to_dict(),
                f, ensure_ascii=False, indent=2,
            )

    def _load(self) -> None:
        """从 JSON 文件加载状态."""
        interactions_path = os.path.join(self.storage_dir, "interactions.json")
        if os.path.isfile(interactions_path):
            try:
                with open(interactions_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._interactions = [
                    InteractionRecord.from_dict(d) for d in data
                ]
                for record in self._interactions:
                    self._update_tool_stats(record)
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        patterns_path = os.path.join(self.storage_dir, "patterns.json")
        if os.path.isfile(patterns_path):
            try:
                with open(patterns_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._patterns = [Pattern.from_dict(d) for d in data]
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        policy_path = os.path.join(self.storage_dir, "policy.json")
        if os.path.isfile(policy_path):
            try:
                with open(policy_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._policy = BehaviorPolicy.from_dict(data)
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

    # ── 内部方法：N-gram 模式提取 ────────────────────────

    def _extract_ngram_patterns(self) -> List[Pattern]:
        """通过 n-gram 频率统计提取模式.

        对每个交互记录的工具序列提取 n-gram（n 从 ngram_range[0]
        到 ngram_range[1]），统计每个 n-gram 的频率和成功率.

        Returns:
            Pattern 列表.
        """
        min_n, max_n = self.ngram_range
        # ngram_key → list of (interaction_index, success, duration, tokens, task, tags)
        ngram_data: Dict[str, List[Tuple[int, bool, float, int, str, List[str]]]] = {}

        for idx, record in enumerate(self._interactions):
            seq = record.tool_sequence
            tags = record.tags

            for n in range(min_n, max_n + 1):
                if len(seq) < n:
                    continue
                for i in range(len(seq) - n + 1):
                    ngram = tuple(seq[i:i + n])
                    key = " → ".join(ngram)
                    if key not in ngram_data:
                        ngram_data[key] = []
                    ngram_data[key].append((
                        idx, record.success, record.duration,
                        record.tokens_used, record.task, tags,
                    ))

        patterns: List[Pattern] = []
        for key, entries in ngram_data.items():
            if len(entries) < 1:
                continue

            successes = sum(1 for _, s, _, _, _, _ in entries if s)
            total = len(entries)
            success_rate = successes / total if total > 0 else 0.0

            durations = [d for _, _, d, _, _, _ in entries]
            tokens_list = [t for _, _, _, t, _, _ in entries]
            tasks = [task for _, _, _, _, task, _ in entries]

            # 收集所有 tags
            all_tags: List[str] = []
            for _, _, _, _, _, tags in entries:
                all_tags.extend(tags)
            # 取最常出现的 tags（top 3）
            from collections import Counter
            tag_counts = Counter(all_tags)
            top_tags = [tag for tag, _ in tag_counts.most_common(3)]

            # 置信度：基于样本量（Wilson score 下界的简化版）
            confidence = self._wilson_lower(successes, total)

            # 模式类型
            if success_rate >= 0.7:
                pattern_type = "success"
            elif success_rate < 0.3:
                pattern_type = "failure"
            else:
                pattern_type = "neutral"

            patterns.append(Pattern(
                tool_sequence=key.split(" → "),
                context_tags=top_tags,
                frequency=total,
                success_rate=round(success_rate, 4),
                avg_duration=round(np.mean(durations), 2),
                avg_tokens=int(np.mean(tokens_list)),
                example_tasks=tasks[:5],
                confidence=round(confidence, 4),
                pattern_type=pattern_type,
            ))

        return patterns

    # ── 内部方法：K-means 聚类 ────────────────────────────

    def _extract_cluster_patterns(self) -> List[Pattern]:
        """使用 numpy k-means 对交互进行聚类，提取行为群组模式.

        将每个交互向量化为特征向量：
        - 工具使用频率（one-hot 编码的子集）
        - 成功/失败标志
        - 归一化耗时
        - 归一化 token 使用

        然后用 k-means 聚类，每个簇形成一个 Pattern.

        Returns:
            Pattern 列表.
        """
        if len(self._interactions) < 2:
            return []

        # 收集所有工具名
        all_tools: set = set()
        for record in self._interactions:
            all_tools.update(record.tool_sequence)
        tool_list = sorted(all_tools)

        if not tool_list:
            return []

        # 构建特征矩阵
        n_interactions = len(self._interactions)
        n_features = len(tool_list) + 3  # tools + success + duration + tokens

        features = np.zeros((n_interactions, n_features), dtype=np.float64)

        # 工具索引
        tool_index = {name: i for i, name in enumerate(tool_list)}

        # 填充特征矩阵
        durations = np.array([r.duration for r in self._interactions], dtype=np.float64)
        tokens = np.array([r.tokens_used for r in self._interactions], dtype=np.float64)

        # 归一化（避免除零）
        max_duration = durations.max() if durations.max() > 0 else 1.0
        max_tokens = tokens.max() if tokens.max() > 0 else 1.0

        for i, record in enumerate(self._interactions):
            # 工具使用频率（归一化）
            for tool_name in record.tool_sequence:
                if tool_name in tool_index:
                    features[i, tool_index[tool_name]] += 1
            # 归一化工具频率
            tool_count = len(record.tool_sequence)
            if tool_count > 0:
                features[i, :len(tool_list)] /= tool_count

            # 成功标志
            features[i, len(tool_list)] = 1.0 if record.success else 0.0
            # 归一化耗时
            features[i, len(tool_list) + 1] = durations[i] / max_duration
            # 归一化 token
            features[i, len(tool_list) + 2] = tokens[i] / max_tokens

        # 确定聚类数 K
        k = min(self.DEFAULT_K, n_interactions)
        if k < 1:
            return []

        # 运行 k-means
        labels, centroids = self._kmeans(features, k, max_iters=50)

        # 从每个簇提取模式
        patterns: List[Pattern] = []
        for cluster_id in range(k):
            mask = labels == cluster_id
            cluster_indices = np.where(mask)[0]
            if len(cluster_indices) == 0:
                continue

            cluster_records = [self._interactions[i] for i in cluster_indices]

            # 找到簇内最频繁的工具序列
            seq_counter: Dict[Tuple[str, ...], int] = {}
            for record in cluster_records:
                seq = tuple(record.tool_sequence)
                seq_counter[seq] = seq_counter.get(seq, 0) + 1

            if not seq_counter:
                continue

            best_seq = max(seq_counter, key=seq_counter.get)
            if not best_seq:
                continue

            successes = sum(1 for r in cluster_records if r.success)
            total = len(cluster_records)
            success_rate = successes / total

            durations_cluster = [r.duration for r in cluster_records]
            tokens_cluster = [r.tokens_used for r in cluster_records]
            tasks_cluster = [r.task for r in cluster_records]

            # 收集 tags
            from collections import Counter
            all_tags: List[str] = []
            for r in cluster_records:
                all_tags.extend(r.tags)
            tag_counts = Counter(all_tags)
            top_tags = [tag for tag, _ in tag_counts.most_common(3)]

            confidence = self._wilson_lower(successes, total)

            if success_rate >= 0.7:
                pattern_type = "success"
            elif success_rate < 0.3:
                pattern_type = "failure"
            else:
                pattern_type = "neutral"

            patterns.append(Pattern(
                tool_sequence=list(best_seq),
                context_tags=top_tags,
                frequency=total,
                success_rate=round(success_rate, 4),
                avg_duration=round(float(np.mean(durations_cluster)), 2),
                avg_tokens=int(np.mean(tokens_cluster)),
                example_tasks=tasks_cluster[:5],
                confidence=round(confidence, 4),
                pattern_type=pattern_type,
            ))

        return patterns

    @staticmethod
    def _kmeans(
        data: np.ndarray, k: int, max_iters: int = 50
    ) -> Tuple[np.ndarray, np.ndarray]:
        """简单的 numpy k-means 实现.

        Args:
            data: (n_samples, n_features) 特征矩阵.
            k: 聚类数.
            max_iters: 最大迭代次数.

        Returns:
            (labels, centroids) — 每个样本的簇标签和簇中心.
        """
        n_samples = data.shape[0]

        # 随机初始化中心点（从数据中选取）
        rng = np.random.RandomState(42)
        indices = rng.choice(n_samples, size=min(k, n_samples), replace=False)
        centroids = data[indices].copy()

        labels = np.zeros(n_samples, dtype=int)

        for _ in range(max_iters):
            # 计算每个样本到每个中心的距离
            distances = np.zeros((n_samples, k))
            for j in range(k):
                diff = data - centroids[j]
                distances[:, j] = np.sum(diff ** 2, axis=1)

            # 分配到最近的中心
            new_labels = np.argmin(distances, axis=1)

            # 检查收敛
            if np.array_equal(new_labels, labels):
                break
            labels = new_labels

            # 更新中心
            for j in range(k):
                mask = labels == j
                if np.any(mask):
                    centroids[j] = np.mean(data[mask], axis=0)

        return labels, centroids

    # ── 内部方法：工具统计 ────────────────────────────────

    def _update_tool_stats(self, record: InteractionRecord) -> None:
        """更新全局工具统计."""
        for tc in record.tool_calls:
            name = tc.get("name", "unknown")
            success = tc.get("success", False)
            if name not in self._tool_stats:
                self._tool_stats[name] = {
                    "total_uses": 0,
                    "successes": 0,
                    "failures": 0,
                }
            self._tool_stats[name]["total_uses"] += 1
            if success:
                self._tool_stats[name]["successes"] += 1
            else:
                self._tool_stats[name]["failures"] += 1

    def _compute_tool_preferences(self) -> Dict[str, float]:
        """计算工具偏好分数.

        偏好分数 = 工具成功率（加权 by 使用频率的平方根）.
        """
        prefs: Dict[str, float] = {}
        for name, stats in self._tool_stats.items():
            total = stats["total_uses"]
            if total == 0:
                prefs[name] = 0.5
                continue
            success_rate = stats["successes"] / total
            # Wilson 下界作为偏好分数
            prefs[name] = round(
                self._wilson_lower(stats["successes"], total), 4
            )
        return prefs

    def _compute_parameters(self) -> Dict[str, Any]:
        """根据统计信息计算可调参数."""
        if not self._interactions:
            return {}

        durations = [r.duration for r in self._interactions]
        tokens = [r.tokens_used for r in self._interactions]
        successes = sum(1 for r in self._interactions if r.success)
        total = len(self._interactions)

        return {
            "avg_duration": round(float(np.mean(durations)), 2),
            "median_duration": round(float(np.median(durations)), 2),
            "avg_tokens": int(np.mean(tokens)),
            "overall_success_rate": round(successes / total, 4) if total else 0.0,
            "total_interactions": total,
            "recommended_max_turns": max(
                5, int(np.percentile(
                    [len(r.tool_calls) for r in self._interactions], 75
                )) + 2
            ) if self._interactions else 10,
        }

    def _compute_stats(self) -> Dict[str, Any]:
        """计算统计摘要."""
        if not self._interactions:
            return {"total": 0}

        successes = sum(1 for r in self._interactions if r.success)
        total = len(self._interactions)

        return {
            "total_interactions": total,
            "overall_success_rate": round(successes / total, 4),
            "total_patterns": len(self._patterns),
            "success_patterns": len(self.get_success_patterns()),
            "failure_patterns": len(self.get_failure_patterns()),
            "experience_rules": len(self._policy.experience_rules),
            "unique_tools": len(self._tool_stats),
        }

    def _next_version(self) -> str:
        """生成下一个版本号."""
        current = self._policy.version
        if current.startswith("v"):
            try:
                num = int(current[1:])
                return f"v{num + 1}"
            except ValueError:
                pass
        return "v1"

    @staticmethod
    def _wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
        """Wilson score 下界 — 小样本下的成功率置信下界.

        Args:
            successes: 成功次数.
            total: 总次数.
            z: z 值（1.96 对应 95% 置信度）.

        Returns:
            置信下界 (0.0–1.0).
        """
        if total == 0:
            return 0.0
        p = successes / total
        denominator = 1 + z ** 2 / total
        centre = p + z ** 2 / (2 * total)
        spread = z * np.sqrt(p * (1 - p) / total + z ** 2 / (4 * total ** 2))
        lower = (centre - spread) / denominator
        return float(max(0.0, min(1.0, lower)))

    @staticmethod
    def _merge_patterns(patterns: List[Pattern]) -> List[Pattern]:
        """合并相同工具序列的模式.

        如果两个模式的 tool_sequence 相同，合并其统计数据.
        """
        merged: Dict[str, Pattern] = {}
        for p in patterns:
            key = " → ".join(p.tool_sequence)
            if key in merged:
                existing = merged[key]
                # 合并频率
                total_freq = existing.frequency + p.frequency
                # 加权平均成功率
                existing.success_rate = round(
                    (existing.success_rate * existing.frequency
                     + p.success_rate * p.frequency) / total_freq,
                    4,
                )
                existing.frequency = total_freq
                existing.avg_duration = round(
                    (existing.avg_duration * existing.frequency
                     + p.avg_duration * p.frequency) / total_freq,
                    2,
                )
                # 更新置信度
                existing.confidence = round(
                    max(existing.confidence, p.confidence), 4
                )
                # 合并示例任务
                existing.example_tasks = list(
                    dict.fromkeys(existing.example_tasks + p.example_tasks)
                )[:10]
                # 合并 tags
                existing.context_tags = list(
                    dict.fromkeys(existing.context_tags + p.context_tags)
                )[:5]
                # 更新类型
                if existing.success_rate >= 0.7:
                    existing.pattern_type = "success"
                elif existing.success_rate < 0.3:
                    existing.pattern_type = "failure"
                else:
                    existing.pattern_type = "neutral"
            else:
                merged[key] = p
        return list(merged.values())
