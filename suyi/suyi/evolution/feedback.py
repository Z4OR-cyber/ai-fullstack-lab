"""反馈循环 — 收集显式和隐式反馈信号.

设计原则：
- **双通道收集**：显式反馈（用户主动提供）和隐式反馈
  （从交互行为推断）并行收集，互为补充.
- **信号归一化**：所有反馈信号统一归一化到 [-1, 1] 区间，
  -1 表示强烈负面，+1 表示强烈正面，0 表示中性.
- **闭环传递**：反馈信号传递给 LearningEngine 更新策略，
  形成完整的反馈闭环.
- **JSON 持久化**：反馈数据存储在 JSON 文件中.

信号流转::

    用户交互 ──┬──▶ 显式反馈 (thumbs up/down + text)
               │           │
               └──▶ 隐式反馈 (completion / retries / duration)
                           │
                    FeedbackSignal ([-1, 1])
                           │
                    LearningEngine.update_policy()
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .learner import LearningEngine
    from .learned.weak_signals import WeakSignalCollector


# ═══════════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════════


@dataclass
class Feedback:
    """单次交互的反馈信息.

    包含显式反馈（用户主动提供）和隐式反馈（从行为推断）.

    Attributes:
        id: 反馈唯一标识符.
        interaction_id: 关联的交互记录 ID.
        explicit_rating: 显式评分 — ``'thumbs_up'`` / ``'thumbs_down'`` / ``'neutral'``.
        explicit_comment: 用户文本评论.
        implicit_completion: 任务是否完成.
        implicit_retries: 重试次数.
        implicit_duration: 执行耗时（秒）.
        implicit_tool_failures: 工具调用失败次数.
        timestamp: 反馈时间戳.
    """

    id: str = ""
    interaction_id: str = ""
    explicit_rating: Optional[str] = None
    explicit_comment: Optional[str] = None
    implicit_completion: bool = False
    implicit_retries: int = 0
    implicit_duration: float = 0.0
    implicit_tool_failures: int = 0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.id:
            self.id = f"fb_{uuid.uuid4().hex[:12]}"
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def has_explicit(self) -> bool:
        """是否有显式反馈."""
        return self.explicit_rating is not None

    @property
    def has_implicit(self) -> bool:
        """是否有隐式反馈."""
        return self.interaction_id != ""

    def to_dict(self) -> dict:
        """转换为字典."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Feedback":
        """从字典创建实例."""
        return cls(**d)


@dataclass
class FeedbackSignal:
    """归一化的反馈信号.

    所有信号归一化到 [-1, 1] 区间：
    - +1.0: 强烈正面
    -  0.0: 中性
    - -1.0: 强烈负面

    Attributes:
        interaction_id: 关联的交互记录 ID.
        explicit_signal: 显式反馈信号 [-1, 1].
        implicit_signal: 隐式反馈信号 [-1, 1].
        combined: 加权综合信号 [-1, 1].
        weight: 信号权重（基于反馈来源的可靠度）.
        components: 各信号分量的详细值.
    """

    interaction_id: str = ""
    explicit_signal: float = 0.0
    implicit_signal: float = 0.0
    combined: float = 0.0
    weight: float = 1.0
    components: Dict[str, float] = field(default_factory=dict)

    # 显式/隐式权重
    EXPLICIT_WEIGHT: float = 0.6
    IMPLICIT_WEIGHT: float = 0.4

    def compute_combined(self) -> float:
        """计算加权综合信号."""
        self.combined = round(
            self.explicit_signal * self.EXPLICIT_WEIGHT
            + self.implicit_signal * self.IMPLICIT_WEIGHT,
            4,
        )
        return self.combined

    def to_dict(self) -> dict:
        """转换为字典."""
        return asdict(self)

    def __repr__(self) -> str:
        return (
            f"FeedbackSignal(combined={self.combined:+.3f}, "
            f"explicit={self.explicit_signal:+.3f}, "
            f"implicit={self.implicit_signal:+.3f})"
        )


# ═══════════════════════════════════════════════════════════════
#  Feedback Collector
# ═══════════════════════════════════════════════════════════════


class FeedbackCollector:
    """反馈收集器 — 收集显式和隐式反馈信号.

    支持两种反馈通道：
    1. **显式反馈**：用户主动提供的评分和评论.
    2. **隐式反馈**：从交互行为推断的信号
       （任务完成状态、重试次数、执行耗时、工具失败次数）.

    收集的反馈信号可传递给 LearningEngine 更新策略.

    Usage::

        collector = FeedbackCollector(storage_dir="data/evolution")

        # 收集显式反馈
        collector.collect_explicit(
            interaction_id="int_abc",
            rating="thumbs_up",
            comment="Great work!",
        )

        # 收集隐式反馈
        collector.collect_implicit(
            interaction_id="int_abc",
            completion=True,
            retries=0,
            duration=5.2,
            tool_failures=0,
        )

        # 获取反馈信号
        signal = collector.get_feedback_signal("int_abc")

        # 传递给学习引擎
        collector.pass_to_learner(engine)
    """

    # 显式评分 → 信号值映射
    RATING_TO_SIGNAL: Dict[str, float] = {
        "thumbs_up": 1.0,
        "thumbs_down": -1.0,
        "neutral": 0.0,
        "up": 1.0,
        "down": -1.0,
    }

    # 隐式信号参数
    IMPLICIT_MAX_RETRIES: int = 3
    IMPLICIT_MAX_DURATION: float = 60.0  # 秒

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        weak_signal_collector: "Optional[WeakSignalCollector]" = None,
    ):
        """
        Args:
            storage_dir: 数据持久化目录.
            weak_signal_collector: 可选的弱信号积累器（v1.6.0 旁路知识层）。
                传入后，负面反馈（thumbs_down / comment / 未完成）会自动
                记录为弱信号。为 None 时行为与旧版完全一致（向后兼容）.
        """
        if storage_dir is None:
            pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            storage_dir = os.path.join(pkg_root, "data", "evolution")

        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

        # interaction_id → Feedback
        self._feedbacks: Dict[str, Feedback] = {}
        # 旁路知识层：弱信号积累器（可选，向后兼容）
        self.weak_signal_collector = weak_signal_collector
        self._load()

    # ── 显式反馈收集 ──────────────────────────────────────

    def collect_explicit(
        self,
        interaction_id: str,
        rating: str,
        comment: Optional[str] = None,
    ) -> Feedback:
        """收集显式反馈.

        Args:
            interaction_id: 交互记录 ID.
            rating: 评分 — ``'thumbs_up'`` / ``'thumbs_down'`` / ``'neutral'``.
            comment: 可选的用户文本评论.

        Returns:
            更新后的 Feedback 实例.
        """
        fb = self._get_or_create(interaction_id)
        fb.explicit_rating = rating
        fb.explicit_comment = comment
        self._feedbacks[interaction_id] = fb
        self._save()

        # 旁路知识层：负面显式反馈记录为弱信号
        self._record_weak_signal_from_feedback(fb)
        return fb

    # ── 隐式反馈收集 ──────────────────────────────────────

    def collect_implicit(
        self,
        interaction_id: str,
        completion: bool,
        retries: int = 0,
        duration: float = 0.0,
        tool_failures: int = 0,
    ) -> Feedback:
        """收集隐式反馈.

        Args:
            interaction_id: 交互记录 ID.
            completion: 任务是否完成.
            retries: 重试次数.
            duration: 执行耗时（秒）.
            tool_failures: 工具调用失败次数.

        Returns:
            更新后的 Feedback 实例.
        """
        fb = self._get_or_create(interaction_id)
        fb.implicit_completion = completion
        fb.implicit_retries = retries
        fb.implicit_duration = duration
        fb.implicit_tool_failures = tool_failures
        self._feedbacks[interaction_id] = fb
        self._save()

        # 旁路知识层：未完成或有重试时记录弱信号
        if not completion or retries > 0:
            self._record_weak_signal_from_feedback(fb)
        return fb

    def collect_from_interaction(self, record: Any) -> Feedback:
        """从 InteractionRecord 自动提取隐式反馈.

        Args:
            record: InteractionRecord 实例（鸭子类型，需有
                id, success, tool_calls, duration 字段）.

        Returns:
            更新后的 Feedback 实例.
        """
        interaction_id = getattr(record, "id", "")
        completion = getattr(record, "success", False)
        duration = getattr(record, "duration", 0.0)

        # 计算重试次数（工具调用中失败后重试的次数）
        tool_calls = getattr(record, "tool_calls", [])
        retries = sum(
            1 for tc in tool_calls
            if not tc.get("success", False)
        )
        tool_failures = retries

        return self.collect_implicit(
            interaction_id=interaction_id,
            completion=completion,
            retries=retries,
            duration=duration,
            tool_failures=tool_failures,
        )

    # ── 反馈信号计算 ──────────────────────────────────────

    def get_feedback(self, interaction_id: str) -> Optional[Feedback]:
        """获取指定交互的反馈信息.

        Args:
            interaction_id: 交互记录 ID.

        Returns:
            Feedback 实例，不存在时返回 None.
        """
        return self._feedbacks.get(interaction_id)

    def get_feedback_signal(self, interaction_id: str) -> Optional[FeedbackSignal]:
        """获取归一化的反馈信号.

        将显式和隐式反馈归一化到 [-1, 1] 区间，
        并计算加权综合信号.

        Args:
            interaction_id: 交互记录 ID.

        Returns:
            FeedbackSignal 实例，不存在时返回 None.
        """
        fb = self._feedbacks.get(interaction_id)
        if fb is None:
            return None

        signal = FeedbackSignal(interaction_id=interaction_id)

        # 计算显式信号
        signal.explicit_signal = self._compute_explicit_signal(fb)
        signal.components["explicit"] = signal.explicit_signal

        # 计算隐式信号
        signal.implicit_signal = self._compute_implicit_signal(fb)
        signal.components["implicit"] = signal.implicit_signal

        # 计算综合信号
        signal.compute_combined()

        # 计算权重（有显式反馈时权重更高）
        if fb.has_explicit:
            signal.weight = 1.0
        else:
            signal.weight = 0.5  # 纯隐式反馈权重降低

        return signal

    def get_all_signals(self) -> List[FeedbackSignal]:
        """获取所有交互的反馈信号.

        Returns:
            FeedbackSignal 列表.
        """
        signals: List[FeedbackSignal] = []
        for interaction_id in self._feedbacks:
            signal = self.get_feedback_signal(interaction_id)
            if signal is not None:
                signals.append(signal)
        return signals

    def get_average_signal(self) -> float:
        """计算所有反馈信号的平均值.

        Returns:
            平均反馈信号 [-1, 1].
        """
        signals = self.get_all_signals()
        if not signals:
            return 0.0
        return round(
            sum(s.combined for s in signals) / len(signals), 4
        )

    # ── 传递给学习引擎 ────────────────────────────────────

    def pass_to_learner(self, engine: "LearningEngine") -> int:
        """将反馈信号传递给学习引擎，更新交互记录.

        遍历所有收集到的反馈，将反馈信息附加到
        对应的交互记录上，以便学习引擎在下次
        extract_patterns / update_policy 时使用.

        Args:
            engine: LearningEngine 实例.

        Returns:
            更新的交互记录数量.
        """
        from .learner import InteractionRecord

        updated = 0
        interactions = engine.get_interactions()

        for record in interactions:
            fb = self._feedbacks.get(record.id)
            if fb is None:
                continue

            # 构建反馈字典
            signal = self.get_feedback_signal(record.id)
            feedback_dict = {
                "rating": fb.explicit_rating,
                "comment": fb.explicit_comment,
                "signal": signal.combined if signal else 0.0,
                "completion": fb.implicit_completion,
                "retries": fb.implicit_retries,
                "duration": fb.implicit_duration,
                "tool_failures": fb.implicit_tool_failures,
            }

            record.feedback = feedback_dict
            updated += 1

        return updated

    # ── 统计信息 ──────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """返回反馈收集统计信息.

        Returns:
            统计信息字典.
        """
        total = len(self._feedbacks)
        explicit_count = sum(1 for fb in self._feedbacks.values() if fb.has_explicit)
        signals = self.get_all_signals()

        positive = sum(1 for s in signals if s.combined > 0.2)
        negative = sum(1 for s in signals if s.combined < -0.2)
        neutral = total - positive - negative

        return {
            "total_feedbacks": total,
            "explicit_feedbacks": explicit_count,
            "implicit_only": total - explicit_count,
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "average_signal": self.get_average_signal(),
        }

    # ── 持久化 ────────────────────────────────────────────

    def _save(self) -> None:
        """保存反馈数据到 JSON 文件."""
        filepath = os.path.join(self.storage_dir, "feedbacks.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._feedbacks.items()},
                f, ensure_ascii=False, indent=2,
            )

    def _load(self) -> None:
        """从 JSON 文件加载反馈数据."""
        filepath = os.path.join(self.storage_dir, "feedbacks.json")
        if not os.path.isfile(filepath):
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._feedbacks = {
                k: Feedback.from_dict(v) for k, v in data.items()
            }
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    # ── 内部方法 ──────────────────────────────────────────

    def _get_or_create(self, interaction_id: str) -> Feedback:
        """获取或创建 Feedback 实例."""
        if interaction_id in self._feedbacks:
            return self._feedbacks[interaction_id]
        return Feedback(interaction_id=interaction_id)

    def _record_weak_signal_from_feedback(self, fb: Feedback) -> None:
        """将反馈转化为旁路弱信号（v1.6.0）.

        规则：
            - thumbs_down → ``thumbs_down`` 弱信号
            - 显式 comment（任意评分）→ ``user_comment`` 弱信号
            - 未完成（implicit_completion=False）或有重试 → ``retry`` 弱信号

        未配置 weak_signal_collector 时为空操作，保持向后兼容。

        Args:
            fb: 反馈实例.
        """
        collector = self.weak_signal_collector
        if collector is None:
            return

        # 任务摘要：用 comment 或 interaction_id 构造（不存完整 prompt）
        summary = fb.explicit_comment or f"interaction {fb.interaction_id}"
        category_hint = self._infer_weak_category(fb)

        if fb.explicit_rating in ("thumbs_down", "down"):
            collector.record(
                signal_type="thumbs_down",
                context_summary=summary,
                category_hint=category_hint,
            )
        if fb.explicit_comment:
            collector.record(
                signal_type="user_comment",
                context_summary=summary,
                category_hint=category_hint,
            )
        if not fb.implicit_completion or fb.implicit_retries > 0:
            # 仅在确实有隐式反馈信息（非默认零值）时记录 retry
            if fb.has_implicit:
                collector.record(
                    signal_type="retry",
                    context_summary=summary,
                    category_hint=category_hint,
                )

    @staticmethod
    def _infer_weak_category(fb: Feedback) -> str:
        """从反馈推断弱信号类别提示（用于同类归并）."""
        if fb.implicit_tool_failures > 0:
            return f"tool_failure_{fb.implicit_tool_failures}"
        if not fb.implicit_completion:
            return "incomplete"
        if fb.explicit_rating in ("thumbs_down", "down"):
            return "negative_rating"
        if fb.explicit_comment:
            return "user_comment"
        return "general"

    def _compute_explicit_signal(self, fb: Feedback) -> float:
        """计算显式反馈信号 [-1, 1].

        映射规则：
        - thumbs_up → +1.0
        - thumbs_down → -1.0
        - neutral → 0.0
        - 数值评分 → 归一化到 [-1, 1]
        - 无显式反馈 → 0.0
        """
        if not fb.has_explicit:
            return 0.0

        rating = fb.explicit_rating
        if rating in self.RATING_TO_SIGNAL:
            return self.RATING_TO_SIGNAL[rating]

        # 数值评分（1-5 星 → [-1, 1]）
        if isinstance(rating, (int, float)):
            # 1→-1, 3→0, 5→+1
            normalized = (float(rating) - 3.0) / 2.0
            return round(max(-1.0, min(1.0, normalized)), 4)

        return 0.0

    def _compute_implicit_signal(self, fb: Feedback) -> float:
        """计算隐式反馈信号 [-1, 1].

        综合考虑：
        - 任务完成状态（权重 50%）
        - 重试次数（权重 20%）
        - 执行耗时（权重 15%）
        - 工具失败次数（权重 15%）

        Returns:
            隐式反馈信号 [-1, 1].
        """
        # 完成状态：+0.5 / -0.5
        completion_score = 0.5 if fb.implicit_completion else -0.5

        # 重试次数：0 次 → +0.2, max_retries → -0.2
        max_r = self.IMPLICIT_MAX_RETRIES
        retry_score = 0.2 * (1 - min(fb.implicit_retries, max_r) / max_r) - 0.0
        if fb.implicit_retries > 0:
            retry_score = 0.2 - 0.4 * min(fb.implicit_retries, max_r) / max_r

        # 耗时：越短越好
        max_d = self.IMPLICIT_MAX_DURATION
        if fb.implicit_duration <= 0:
            duration_score = 0.0
        elif fb.implicit_duration < max_d:
            duration_score = 0.15 * (1 - fb.implicit_duration / max_d)
        else:
            duration_score = -0.15

        # 工具失败：每次 -0.05，最多 -0.15
        failure_score = max(-0.15, -0.05 * fb.implicit_tool_failures)

        signal = completion_score + retry_score + duration_score + failure_score
        return round(max(-1.0, min(1.0, signal)), 4)
