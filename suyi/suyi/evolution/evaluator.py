"""行为评估器 — 多维度评估 Agent 表现.

设计原则：
- **多维度评估**：从任务完成率、效率、质量、用户满意度
  四个维度综合评估，不依赖单一指标.
- **版本对比**：支持 A/B 评估，对比不同策略版本的效果.
- **统计严谨**：使用 Wilson 置信区间处理小样本，
  使用中位数和百分位数抵抗异常值.
- **JSON 报告**：评估报告以 JSON 格式输出，便于程序消费和持久化.

评估维度::

    ┌──────────────────────────────────────────────┐
    │  Completion Rate   — 任务是否成功完成          │
    │  Efficiency        — 耗时 / token 消耗         │
    │  Quality           — 工具成功率 / 轮次效率      │
    │  User Satisfaction — 显式 + 隐式反馈           │
    └──────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .learner import InteractionRecord


# ═══════════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════════


@dataclass
class EvaluationMetrics:
    """多维度评估指标.

    每个维度分数归一化到 0.0–1.0，1.0 表示最佳.

    Attributes:
        completion_rate: 任务完成率（0.0–1.0）.
        efficiency_score: 效率分数（0.0–1.0），基于耗时和 token 消耗.
        quality_score: 质量分数（0.0–1.0），基于工具成功率和轮次效率.
        user_satisfaction: 用户满意度（0.0–1.0），基于反馈信号.
        overall_score: 综合分数（加权平均）.
        details: 详细统计信息.
    """

    completion_rate: float = 0.0
    efficiency_score: float = 0.0
    quality_score: float = 0.0
    user_satisfaction: float = 0.5
    overall_score: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    # 维度权重
    WEIGHTS: Tuple[float, float, float, float] = (
        0.35,  # completion
        0.25,  # efficiency
        0.20,  # quality
        0.20,  # satisfaction
    )

    def compute_overall(self) -> float:
        """计算加权综合分数."""
        w = self.WEIGHTS
        self.overall_score = round(
            self.completion_rate * w[0]
            + self.efficiency_score * w[1]
            + self.quality_score * w[2]
            + self.user_satisfaction * w[3],
            4,
        )
        return self.overall_score

    def to_dict(self) -> dict:
        """转换为字典."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EvaluationMetrics":
        """从字典创建实例."""
        return cls(**d)

    def __repr__(self) -> str:
        return (
            f"EvaluationMetrics(overall={self.overall_score:.2f}, "
            f"completion={self.completion_rate:.2f}, "
            f"efficiency={self.efficiency_score:.2f}, "
            f"quality={self.quality_score:.2f}, "
            f"satisfaction={self.user_satisfaction:.2f})"
        )


@dataclass
class EvaluationReport:
    """完整评估报告.

    Attributes:
        id: 报告唯一标识符.
        version: 被评估的策略版本.
        metrics: 评估指标.
        comparison: 版本对比结果（如有）.
        timestamp: 评估时间戳.
        interaction_count: 评估涉及的交互数量.
        recommendations: 改进建议列表.
    """

    id: str = ""
    version: str = "default"
    metrics: EvaluationMetrics = field(default_factory=EvaluationMetrics)
    comparison: Optional[Dict[str, Any]] = None
    timestamp: float = 0.0
    interaction_count: int = 0
    recommendations: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = f"eval_{uuid.uuid4().hex[:12]}"
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "id": self.id,
            "version": self.version,
            "metrics": self.metrics.to_dict(),
            "comparison": self.comparison,
            "timestamp": self.timestamp,
            "interaction_count": self.interaction_count,
            "recommendations": self.recommendations,
        }

    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> "EvaluationReport":
        """从字典创建实例."""
        metrics = EvaluationMetrics.from_dict(d.pop("metrics", {}))
        return cls(metrics=metrics, **d)


# ═══════════════════════════════════════════════════════════════
#  Behavior Evaluator
# ═══════════════════════════════════════════════════════════════


class BehaviorEvaluator:
    """行为评估器 — 多维度评估 Agent 表现.

    支持单次评估、批量评估和版本对比（A/B 评估）.

    Usage::

        evaluator = BehaviorEvaluator(storage_dir="data/evolution")

        # 单次评估
        metrics = evaluator.evaluate_single(interaction)

        # 批量评估
        report = evaluator.evaluate_batch(interactions, version="v2")

        # A/B 对比
        comparison = evaluator.compare_versions(
            interactions_a, "v1",
            interactions_b, "v2",
        )
    """

    # 效率基准（用于归一化）
    DEFAULT_MAX_DURATION: float = 60.0  # 秒
    DEFAULT_MAX_TOKENS: int = 8192

    # 满意度从反馈信号提取的映射
    SATISFACTION_MAP = {
        "thumbs_up": 1.0,
        "thumbs_down": 0.0,
        "neutral": 0.5,
    }

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        max_duration: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        """
        Args:
            storage_dir: 评估报告持久化目录.
            max_duration: 效率归一化的最大耗时基准.
            max_tokens: 效率归一化的最大 token 基准.
        """
        if storage_dir is None:
            pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            storage_dir = os.path.join(pkg_root, "data", "evolution")

        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

        self.max_duration = max_duration or self.DEFAULT_MAX_DURATION
        self.max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS

        self._reports: List[EvaluationReport] = []

    # ── 单次评估 ──────────────────────────────────────────

    def evaluate_single(
        self, interaction: InteractionRecord
    ) -> EvaluationMetrics:
        """评估单次交互.

        Args:
            interaction: 交互记录.

        Returns:
            EvaluationMetrics 实例.
        """
        metrics = EvaluationMetrics()

        # 1. 完成率 — 单次交互只有 0 或 1
        metrics.completion_rate = 1.0 if interaction.success else 0.0

        # 2. 效率分数
        metrics.efficiency_score = self._compute_efficiency(interaction)

        # 3. 质量分数
        metrics.quality_score = self._compute_quality(interaction)

        # 4. 用户满意度
        metrics.user_satisfaction = self._compute_satisfaction(interaction)

        # 详细信息
        metrics.details = {
            "duration": interaction.duration,
            "tokens_used": interaction.tokens_used,
            "tool_calls": len(interaction.tool_calls),
            "tool_success_rate": interaction.tool_success_rate,
            "has_feedback": interaction.feedback is not None,
            "tags": interaction.tags,
        }

        metrics.compute_overall()
        return metrics

    # ── 批量评估 ──────────────────────────────────────────

    def evaluate_batch(
        self,
        interactions: List[InteractionRecord],
        version: str = "default",
    ) -> EvaluationReport:
        """批量评估一组交互.

        Args:
            interactions: 交互记录列表.
            version: 策略版本标签.

        Returns:
            EvaluationReport 实例.
        """
        if not interactions:
            return EvaluationReport(
                version=version,
                interaction_count=0,
                recommendations=["No interactions to evaluate."],
            )

        # 收集每条交互的指标
        per_interaction: List[EvaluationMetrics] = []
        for record in interactions:
            per_interaction.append(self.evaluate_single(record))

        # 聚合
        metrics = self._aggregate_metrics(per_interaction, interactions)

        # 生成改进建议
        recommendations = self._generate_recommendations(metrics, interactions)

        report = EvaluationReport(
            version=version,
            metrics=metrics,
            interaction_count=len(interactions),
            recommendations=recommendations,
        )

        self._reports.append(report)
        self._save_report(report)
        return report

    # ── 版本对比（A/B 评估）──────────────────────────────

    def compare_versions(
        self,
        interactions_a: List[InteractionRecord],
        version_a: str,
        interactions_b: List[InteractionRecord],
        version_b: str,
    ) -> Dict[str, Any]:
        """对比两个策略版本的效果（A/B 评估）.

        Args:
            interactions_a: 版本 A 的交互记录.
            version_a: 版本 A 标签.
            interactions_b: 版本 B 的交互记录.
            version_b: 版本 B 标签.

        Returns:
            对比结果字典，包含两个版本的指标和差异分析.
        """
        report_a = self.evaluate_batch(interactions_a, version_a)
        report_b = self.evaluate_batch(interactions_b, version_b)

        metrics_a = report_a.metrics
        metrics_b = report_b.metrics

        # 计算差异
        diff = {}
        for attr in (
            "completion_rate", "efficiency_score",
            "quality_score", "user_satisfaction", "overall_score",
        ):
            val_a = getattr(metrics_a, attr)
            val_b = getattr(metrics_b, attr)
            diff[attr] = {
                "a": val_a,
                "b": val_b,
                "delta": round(val_b - val_a, 4),
                "improvement": val_b > val_a,
            }

        # 判断哪个版本更好
        if metrics_b.overall_score > metrics_a.overall_score:
            winner = version_b
        elif metrics_a.overall_score > metrics_b.overall_score:
            winner = version_a
        else:
            winner = "tie"

        comparison = {
            "version_a": version_a,
            "version_b": version_b,
            "metrics_a": metrics_a.to_dict(),
            "metrics_b": metrics_b.to_dict(),
            "differences": diff,
            "winner": winner,
            "sample_size_a": len(interactions_a),
            "sample_size_b": len(interactions_b),
            "timestamp": time.time(),
        }

        return comparison

    # ── 报告管理 ──────────────────────────────────────────

    def get_reports(self) -> List[EvaluationReport]:
        """返回所有评估报告."""
        return list(self._reports)

    def get_report_by_id(self, report_id: str) -> Optional[EvaluationReport]:
        """按 ID 获取报告."""
        for r in self._reports:
            if r.id == report_id:
                return r
        return None

    def get_latest_report(self, version: Optional[str] = None) -> Optional[EvaluationReport]:
        """获取最新的评估报告.

        Args:
            version: 可选，按版本过滤.

        Returns:
            最新的 EvaluationReport，或 None.
        """
        filtered = self._reports
        if version:
            filtered = [r for r in filtered if r.version == version]
        if not filtered:
            return None
        return max(filtered, key=lambda r: r.timestamp)

    # ── 内部计算方法 ──────────────────────────────────────

    def _compute_efficiency(self, record: InteractionRecord) -> float:
        """计算效率分数.

        基于耗时和 token 消耗的归一化：
        - 耗时越短，分数越高
        - token 消耗越少，分数越高
        综合分数 = 0.5 * duration_score + 0.5 * token_score
        """
        # 耗时分数：线性归一化，截断到 [0, 1]
        duration_score = max(
            0.0, 1.0 - (record.duration / self.max_duration)
        )

        # token 分数：线性归一化
        token_score = max(
            0.0, 1.0 - (record.tokens_used / self.max_tokens)
        )

        return round(0.5 * duration_score + 0.5 * token_score, 4)

    def _compute_quality(self, record: InteractionRecord) -> float:
        """计算质量分数.

        基于：
        - 工具调用成功率（60% 权重）
        - 轮次效率：用更少的工具调用完成任务（40% 权重）
        """
        # 工具成功率
        tool_sr = record.tool_success_rate

        # 轮次效率：调用次数越少越好（对数衰减）
        n_calls = len(record.tool_calls)
        if n_calls == 0:
            turn_efficiency = 0.5  # 无工具调用，给中等分
        else:
            # 1 次调用 = 1.0, 5 次调用 ≈ 0.57, 10 次调用 ≈ 0.40
            turn_efficiency = 1.0 / (1.0 + 0.3 * (n_calls - 1)) if n_calls > 0 else 0.5
            turn_efficiency = max(0.0, min(1.0, turn_efficiency))

        return round(0.6 * tool_sr + 0.4 * turn_efficiency, 4)

    def _compute_satisfaction(self, record: InteractionRecord) -> float:
        """计算用户满意度.

        优先使用显式反馈，无显式反馈时用隐式信号推断.

        显式反馈：
        - thumbs_up → 1.0
        - thumbs_down → 0.0
        - neutral / 无评分 → 0.5

        隐式反馈（无显式时）：
        - 任务成功 + 无重试 → 0.8
        - 任务成功 + 有重试 → 0.5
        - 任务失败 → 0.2
        """
        if record.feedback:
            # 显式反馈
            rating = record.feedback.get("rating")
            if rating in self.SATISFACTION_MAP:
                return self.SATISFACTION_MAP[rating]

            # 数值评分（如 1-5 星）
            if isinstance(rating, (int, float)):
                normalized = max(0.0, min(1.0, rating / 5.0))
                return round(normalized, 4)

            # 默认中性
            return 0.5

        # 隐式反馈
        if record.success:
            # 检查是否有重试（工具调用中有失败的）
            has_failures = any(
                not tc.get("success", False) for tc in record.tool_calls
            )
            return 0.8 if not has_failures else 0.5
        else:
            return 0.2

    def _aggregate_metrics(
        self,
        per_interaction: List[EvaluationMetrics],
        interactions: List[InteractionRecord],
    ) -> EvaluationMetrics:
        """聚合一组交互的指标.

        Args:
            per_interaction: 每条交互的指标.
            interactions: 原始交互记录.

        Returns:
            聚合后的 EvaluationMetrics.
        """
        n = len(per_interaction)

        # 完成率：成功的比例
        completion = sum(1 for r in interactions if r.success) / n

        # 效率：平均效率分数
        efficiency = float(np.mean([m.efficiency_score for m in per_interaction]))

        # 质量：平均质量分数
        quality = float(np.mean([m.quality_score for m in per_interaction]))

        # 满意度：平均满意度
        satisfaction = float(np.mean([m.user_satisfaction for m in per_interaction]))

        metrics = EvaluationMetrics(
            completion_rate=round(completion, 4),
            efficiency_score=round(efficiency, 4),
            quality_score=round(quality, 4),
            user_satisfaction=round(satisfaction, 4),
        )

        # 详细统计
        durations = [r.duration for r in interactions]
        tokens = [r.tokens_used for r in interactions]
        tool_calls_list = [len(r.tool_calls) for r in interactions]

        metrics.details = {
            "avg_duration": round(float(np.mean(durations)), 2),
            "median_duration": round(float(np.median(durations)), 2),
            "p90_duration": round(float(np.percentile(durations, 90)), 2),
            "avg_tokens": int(np.mean(tokens)),
            "median_tokens": int(np.median(tokens)),
            "avg_tool_calls": round(float(np.mean(tool_calls_list)), 2),
            "median_tool_calls": int(np.median(tool_calls_list)),
            "total_interactions": n,
            "successful": sum(1 for r in interactions if r.success),
            "failed": sum(1 for r in interactions if not r.success),
        }

        metrics.compute_overall()
        return metrics

    def _generate_recommendations(
        self,
        metrics: EvaluationMetrics,
        interactions: List[InteractionRecord],
    ) -> List[str]:
        """根据评估结果生成改进建议.

        Args:
            metrics: 评估指标.
            interactions: 交互记录.

        Returns:
            建议字符串列表.
        """
        recs: List[str] = []

        # 完成率
        if metrics.completion_rate < 0.7:
            recs.append(
                f"任务完成率偏低（{metrics.completion_rate:.0%}），"
                "建议分析失败交互的常见原因并优化工具选择策略."
            )

        # 效率
        if metrics.efficiency_score < 0.5:
            avg_duration = metrics.details.get("avg_duration", 0)
            avg_tokens = metrics.details.get("avg_tokens", 0)
            recs.append(
                f"效率分数偏低（{metrics.efficiency_score:.2f}），"
                f"平均耗时 {avg_duration}s，平均 token {avg_tokens}，"
                "建议减少不必要的工具调用或优化上下文压缩."
            )

        # 质量
        if metrics.quality_score < 0.5:
            avg_calls = metrics.details.get("avg_tool_calls", 0)
            recs.append(
                f"质量分数偏低（{metrics.quality_score:.2f}），"
                f"平均工具调用 {avg_calls} 次，"
                "建议提高工具选择准确性，减少失败重试."
            )

        # 满意度
        if metrics.user_satisfaction < 0.5:
            recs.append(
                f"用户满意度偏低（{metrics.user_satisfaction:.2f}），"
                "建议收集更多显式反馈，分析低满意度交互的共同特征."
            )

        # 工具失败率
        total_tool_calls = sum(len(r.tool_calls) for r in interactions)
        failed_tool_calls = sum(
            1 for r in interactions
            for tc in r.tool_calls
            if not tc.get("success", False)
        )
        if total_tool_calls > 0:
            tool_fail_rate = failed_tool_calls / total_tool_calls
            if tool_fail_rate > 0.2:
                recs.append(
                    f"工具调用失败率 {tool_fail_rate:.0%}，"
                    "建议检查工具参数验证逻辑或增加重试策略."
                )

        if not recs:
            recs.append("各项指标表现良好，建议继续保持当前策略.")

        return recs

    # ── 持久化 ────────────────────────────────────────────

    def _save_report(self, report: EvaluationReport) -> None:
        """保存评估报告到 JSON 文件."""
        report_path = os.path.join(
            self.storage_dir, f"report_{report.id}.json"
        )
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report.to_json())

    def load_reports(self) -> List[EvaluationReport]:
        """从磁盘加载所有评估报告."""
        reports: List[EvaluationReport] = []
        if not os.path.isdir(self.storage_dir):
            return reports

        for filename in sorted(os.listdir(self.storage_dir)):
            if not filename.startswith("report_") or not filename.endswith(".json"):
                continue
            filepath = os.path.join(self.storage_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                reports.append(EvaluationReport.from_dict(data))
            except (json.JSONDecodeError, TypeError, KeyError):
                continue

        self._reports = reports
        return reports
