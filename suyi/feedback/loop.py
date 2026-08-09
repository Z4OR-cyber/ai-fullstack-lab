"""
用户反馈收集与学习闭环 — 支持显式反馈 + 隐式反馈，喂入 Evolution 引擎.

设计原则:
    - **双通道收集**：显式反馈（点赞/点踩/评分/评论）和隐式反馈
      （重试/编辑/放弃/停留时长）并行收集.
    - **信号归一化**：所有反馈信号统一归一化到 [-1, 1] 区间.
    - **闭环传递**：反馈数据传递给 Evolution 引擎（LearningEngine /
      FeedbackCollector / EvolutionOrchestrator），形成完整学习闭环.
    - **JSON 持久化**：反馈数据存储在 JSON 文件中.
    - **趋势分析**：支持时间窗口内的反馈趋势分析.

与 evolution/feedback.py 的区别:
    - evolution FeedbackCollector 侧重基本的反馈收集
    - 本模块增加了隐式反馈信号（编辑/放弃/停留时长），
      更丰富的评分方式（1-5 星评分），趋势分析，
      以及更深入的 Evolution 引擎集成

信号流转::

    用户交互 ──┬──▶ 显式反馈 (thumbs_up/down + 评分 + 评论)
               │           │
               ├──▶ 隐式反馈 (retry / edit / abandon / dwell)
               │           │
               ▼           ▼
            FeedbackEntry → FeedbackSignalV2([-1, 1])
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
              LearningEngine  FeedbackCollector  EvolutionOrchestrator
              (策略更新)      (信号传递)         (编排进化)

使用示例::

    from suyi.feedback import FeedbackLoop, FeedbackEntry, FeedbackType

    loop = FeedbackLoop(storage_dir="data/feedback")
    loop.collect_explicit(
        interaction_id="int_001",
        feedback_type=FeedbackType.THUMBS_UP,
        comment="很好的回答",
    )
    loop.collect_implicit(
        interaction_id="int_001",
        retries=0,
        edited=False,
        abandoned=False,
        dwell_time=3.5,
    )
    signal = loop.get_signal("int_001")
    loop.feed_to_evolution(learning_engine)
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..evolution.learner import LearningEngine
    from ..evolution.feedback import FeedbackCollector
    from ..evolution.orchestrator import EvolutionOrchestrator


# ═══════════════════════════════════════════════════════════════
#  枚举
# ═══════════════════════════════════════════════════════════════


class FeedbackType(Enum):
    """显式反馈类型."""

    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    NEUTRAL = "neutral"
    STAR_1 = "star_1"
    STAR_2 = "star_2"
    STAR_3 = "star_3"
    STAR_4 = "star_4"
    STAR_5 = "star_5"


class ImplicitSignalType(Enum):
    """隐式反馈信号类型."""

    RETRY = "retry"          # 用户重试了请求
    EDIT = "edit"            # 用户编辑了之前的消息
    ABANDON = "abandon"      # 用户放弃了对话（未等回答完成）
    DWELL = "dwell"          # 用户在回答上停留的时间
    COPY = "copy"            # 用户复制了回答
    REGENERATE = "regenerate"  # 用户要求重新生成


# ═══════════════════════════════════════════════════════════════
#  数据结构
# ═══════════════════════════════════════════════════════════════


@dataclass
class FeedbackEntry:
    """单次交互的完整反馈信息.

    包含显式反馈和隐式反馈两个通道的数据.

    Attributes:
        id:               反馈唯一 ID.
        interaction_id:   关联的交互记录 ID.
        session_id:       会话 ID.
        user_id:          用户标识.
        # 显式反馈
        explicit_type:    显式反馈类型（FeedbackType 枚举值）.
        explicit_comment: 用户文本评论.
        explicit_rating:  数值评分（1-5，与 explicit_type 互补）.
        # 隐式反馈
        implicit_retries:      重试次数.
        implicit_edited:       是否编辑过消息.
        implicit_abandoned:    是否放弃对话.
        implicit_dwell_time:   停留时长（秒）.
        implicit_copied:       是否复制了回答.
        implicit_regenerated:  是否要求重新生成.
        # 元数据
        timestamp:        反馈时间戳.
        metadata:         附加元数据.
    """

    id: str = ""
    interaction_id: str = ""
    session_id: str = "default"
    user_id: str = "default"

    # 显式反馈
    explicit_type: Optional[str] = None
    explicit_comment: Optional[str] = None
    explicit_rating: Optional[int] = None

    # 隐式反馈
    implicit_retries: int = 0
    implicit_edited: bool = False
    implicit_abandoned: bool = False
    implicit_dwell_time: float = 0.0
    implicit_copied: bool = False
    implicit_regenerated: bool = False

    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = f"fb_{uuid.uuid4().hex[:12]}"
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def has_explicit(self) -> bool:
        """是否有显式反馈."""
        return self.explicit_type is not None or self.explicit_rating is not None

    @property
    def has_implicit(self) -> bool:
        """是否有隐式反馈."""
        return (
            self.implicit_retries > 0
            or self.implicit_edited
            or self.implicit_abandoned
            or self.implicit_dwell_time > 0
            or self.implicit_copied
            or self.implicit_regenerated
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FeedbackEntry":
        # 过滤未知字段
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class FeedbackSignalV2:
    """归一化的反馈信号 V2.

    所有信号归一化到 [-1, 1] 区间:
        +1.0: 强烈正面
         0.0: 中性
        -1.0: 强烈负面

    Attributes:
        interaction_id:     关联的交互 ID.
        explicit_signal:    显式反馈信号 [-1, 1].
        implicit_signal:    隐式反馈信号 [-1, 1].
        combined:           加权综合信号 [-1, 1].
        weight:             信号权重.
        components:         各信号分量的详细值.
    """

    interaction_id: str = ""
    explicit_signal: float = 0.0
    implicit_signal: float = 0.0
    combined: float = 0.0
    weight: float = 1.0
    components: dict = field(default_factory=dict)

    # 显式/隐式权重
    EXPLICIT_WEIGHT: float = 0.6
    IMPLICIT_WEIGHT: float = 0.4

    def compute_combined(self) -> float:
        """计算加权综合信号."""
        # 如果只有隐式反馈，全部使用隐式权重
        if self.explicit_signal == 0.0 and self.implicit_signal != 0.0:
            self.combined = round(self.implicit_signal, 4)
        elif self.implicit_signal == 0.0 and self.explicit_signal != 0.0:
            self.combined = round(self.explicit_signal, 4)
        else:
            self.combined = round(
                self.explicit_signal * self.EXPLICIT_WEIGHT
                + self.implicit_signal * self.IMPLICIT_WEIGHT,
                4,
            )
        return self.combined

    def to_dict(self) -> dict:
        return asdict(self)

    def __repr__(self) -> str:
        return (
            f"FeedbackSignalV2(combined={self.combined:+.3f}, "
            f"explicit={self.explicit_signal:+.3f}, "
            f"implicit={self.implicit_signal:+.3f})"
        )


# ═══════════════════════════════════════════════════════════════
#  反馈闭环
# ═══════════════════════════════════════════════════════════════


class FeedbackLoop:
    """用户反馈收集与学习闭环.

    核心功能:
        - 显式反馈收集：collect_explicit()
        - 隐式反馈收集：collect_implicit()
        - 信号归一化：get_signal()
        - 趋势分析：get_trend()
        - Evolution 引擎集成：feed_to_evolution()

    Args:
        storage_dir: 数据持久化目录.
        explicit_weight: 显式反馈在综合信号中的权重.
        implicit_weight: 隐式反馈在综合信号中的权重.

    使用示例::

        loop = FeedbackLoop(storage_dir="data/feedback")

        # 收集显式反馈
        loop.collect_explicit(
            interaction_id="int_001",
            feedback_type=FeedbackType.THUMBS_UP,
            comment="回答很有帮助",
        )

        # 收集隐式反馈
        loop.collect_implicit(
            interaction_id="int_001",
            retries=0,
            edited=False,
            dwell_time=5.0,
        )

        # 获取归一化信号
        signal = loop.get_signal("int_001")

        # 传递给 Evolution 引擎
        loop.feed_to_evolution(learning_engine)
    """

    # 显式反馈类型 → 信号值
    TYPE_TO_SIGNAL: dict[str, float] = {
        FeedbackType.THUMBS_UP.value: 1.0,
        FeedbackType.THUMBS_DOWN.value: -1.0,
        FeedbackType.NEUTRAL.value: 0.0,
        FeedbackType.STAR_1.value: -1.0,
        FeedbackType.STAR_2.value: -0.5,
        FeedbackType.STAR_3.value: 0.0,
        FeedbackType.STAR_4.value: 0.5,
        FeedbackType.STAR_5.value: 1.0,
    }

    # 隐式信号参数
    MAX_RETRIES: int = 3
    MAX_DWELL_TIME: float = 60.0  # 秒

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        explicit_weight: float = 0.6,
        implicit_weight: float = 0.4,
    ):
        if storage_dir is None:
            pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            storage_dir = os.path.join(pkg_root, "data", "feedback")
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

        self.explicit_weight = explicit_weight
        self.implicit_weight = implicit_weight

        # interaction_id → FeedbackEntry
        self._entries: dict[str, FeedbackEntry] = {}
        self._load()

    # ── 显式反馈收集 ──────────────────────────────────────

    def collect_explicit(
        self,
        interaction_id: str,
        feedback_type: Optional[FeedbackType] = None,
        rating: Optional[int] = None,
        comment: Optional[str] = None,
        session_id: str = "default",
        user_id: str = "default",
    ) -> FeedbackEntry:
        """收集显式反馈.

        Args:
            interaction_id: 交互记录 ID.
            feedback_type:  反馈类型（FeedbackType 枚举）.
            rating:         数值评分（1-5，与 feedback_type 互补使用）.
            comment:        用户文本评论.
            session_id:     会话 ID.
            user_id:        用户标识.

        Returns:
            更新后的 FeedbackEntry.
        """
        entry = self._get_or_create(interaction_id, session_id, user_id)
        if feedback_type is not None:
            entry.explicit_type = feedback_type.value
        if rating is not None:
            entry.explicit_rating = max(1, min(5, rating))
            # 如果未指定 feedback_type，根据评分自动推导
            if feedback_type is None:
                if rating <= 2:
                    entry.explicit_type = FeedbackType.THUMBS_DOWN.value
                elif rating >= 4:
                    entry.explicit_type = FeedbackType.THUMBS_UP.value
                else:
                    entry.explicit_type = FeedbackType.NEUTRAL.value
        if comment is not None:
            entry.explicit_comment = comment
        self._entries[interaction_id] = entry
        self._save()
        return entry

    # ── 隐式反馈收集 ──────────────────────────────────────

    def collect_implicit(
        self,
        interaction_id: str,
        retries: int = 0,
        edited: bool = False,
        abandoned: bool = False,
        dwell_time: float = 0.0,
        copied: bool = False,
        regenerated: bool = False,
        session_id: str = "default",
        user_id: str = "default",
    ) -> FeedbackEntry:
        """收集隐式反馈.

        Args:
            interaction_id: 交互记录 ID.
            retries:        重试次数.
            edited:         是否编辑过消息.
            abandoned:      是否放弃对话.
            dwell_time:     停留时长（秒）.
            copied:         是否复制了回答.
            regenerated:    是否要求重新生成.
            session_id:     会话 ID.
            user_id:        用户标识.

        Returns:
            更新后的 FeedbackEntry.
        """
        entry = self._get_or_create(interaction_id, session_id, user_id)
        entry.implicit_retries = retries
        entry.implicit_edited = edited
        entry.implicit_abandoned = abandoned
        entry.implicit_dwell_time = dwell_time
        entry.implicit_copied = copied
        entry.implicit_regenerated = regenerated
        self._entries[interaction_id] = entry
        self._save()
        return entry

    def record_implicit_signal(
        self,
        interaction_id: str,
        signal_type: ImplicitSignalType,
        session_id: str = "default",
        user_id: str = "default",
    ) -> FeedbackEntry:
        """记录单个隐式信号事件.

        Args:
            interaction_id: 交互记录 ID.
            signal_type:    隐式信号类型.
            session_id:     会话 ID.
            user_id:        用户标识.

        Returns:
            更新后的 FeedbackEntry.
        """
        entry = self._get_or_create(interaction_id, session_id, user_id)
        if signal_type == ImplicitSignalType.RETRY:
            entry.implicit_retries += 1
        elif signal_type == ImplicitSignalType.EDIT:
            entry.implicit_edited = True
        elif signal_type == ImplicitSignalType.ABANDON:
            entry.implicit_abandoned = True
        elif signal_type == ImplicitSignalType.COPY:
            entry.implicit_copied = True
        elif signal_type == ImplicitSignalType.REGENERATE:
            entry.implicit_regenerated = True
        self._entries[interaction_id] = entry
        self._save()
        return entry

    # ── 信号计算 ──────────────────────────────────────────

    def get_entry(self, interaction_id: str) -> Optional[FeedbackEntry]:
        """获取反馈条目."""
        return self._entries.get(interaction_id)

    def get_signal(self, interaction_id: str) -> Optional[FeedbackSignalV2]:
        """获取归一化反馈信号.

        Args:
            interaction_id: 交互记录 ID.

        Returns:
            FeedbackSignalV2 实例，不存在时返回 None.
        """
        entry = self._entries.get(interaction_id)
        if entry is None:
            return None

        signal = FeedbackSignalV2(interaction_id=interaction_id)

        # 计算显式信号
        signal.explicit_signal = self._compute_explicit_signal(entry)
        signal.components["explicit"] = signal.explicit_signal

        # 计算隐式信号
        signal.implicit_signal = self._compute_implicit_signal(entry)
        signal.components["implicit"] = signal.implicit_signal

        # 各隐式分量
        signal.components["retry"] = self._retry_signal(entry.implicit_retries)
        signal.components["edit"] = -0.3 if entry.implicit_edited else 0.0
        signal.components["abandon"] = -0.8 if entry.implicit_abandoned else 0.0
        signal.components["dwell"] = self._dwell_signal(entry.implicit_dwell_time)
        signal.components["copy"] = 0.4 if entry.implicit_copied else 0.0
        signal.components["regenerate"] = -0.5 if entry.implicit_regenerated else 0.0

        # 计算综合信号
        signal.compute_combined()

        # 权重
        signal.weight = 1.0 if entry.has_explicit else 0.5

        return signal

    def get_all_signals(self) -> list[FeedbackSignalV2]:
        """获取所有反馈信号."""
        signals: list[FeedbackSignalV2] = []
        for iid in self._entries:
            sig = self.get_signal(iid)
            if sig is not None:
                signals.append(sig)
        return signals

    def get_average_signal(self) -> float:
        """平均反馈信号."""
        signals = self.get_all_signals()
        if not signals:
            return 0.0
        return round(sum(s.combined for s in signals) / len(signals), 4)

    # ── 趋势分析 ──────────────────────────────────────────

    def get_trend(
        self, window_seconds: float = 3600
    ) -> dict[str, Any]:
        """获取时间窗口内的反馈趋势.

        Args:
            window_seconds: 时间窗口大小（秒），默认 1 小时.

        Returns:
            趋势字典，包含:
                - window_seconds: 窗口大小
                - count: 窗口内反馈数
                - average_signal: 平均信号
                - positive_ratio: 正面比例
                - negative_ratio: 负面比例
                - trend_direction: 趋势方向 ("improving" / "declining" / "stable")
        """
        now = time.time()
        cutoff = now - window_seconds
        recent_entries = [
            e for e in self._entries.values()
            if e.timestamp >= cutoff
        ]

        if not recent_entries:
            return {
                "window_seconds": window_seconds,
                "count": 0,
                "average_signal": 0.0,
                "positive_ratio": 0.0,
                "negative_ratio": 0.0,
                "trend_direction": "stable",
            }

        signals: list[float] = []
        for entry in recent_entries:
            sig = self.get_signal(entry.interaction_id)
            if sig:
                signals.append(sig.combined)

        if not signals:
            return {
                "window_seconds": window_seconds,
                "count": len(recent_entries),
                "average_signal": 0.0,
                "positive_ratio": 0.0,
                "negative_ratio": 0.0,
                "trend_direction": "stable",
            }

        avg = sum(signals) / len(signals)
        positive = sum(1 for s in signals if s > 0.2)
        negative = sum(1 for s in signals if s < -0.2)

        # 趋势方向：比较前半段和后半段
        mid = len(signals) // 2
        if mid > 0:
            first_half_avg = sum(signals[:mid]) / mid
            second_half_avg = sum(signals[mid:]) / (len(signals) - mid)
            diff = second_half_avg - first_half_avg
            if diff > 0.1:
                direction = "improving"
            elif diff < -0.1:
                direction = "declining"
            else:
                direction = "stable"
        else:
            direction = "stable"

        return {
            "window_seconds": window_seconds,
            "count": len(recent_entries),
            "average_signal": round(avg, 4),
            "positive_ratio": round(positive / len(signals), 4),
            "negative_ratio": round(negative / len(signals), 4),
            "trend_direction": direction,
        }

    # ── Evolution 引擎集成 ─────────────────────────────────

    def feed_to_evolution(
        self,
        engine: Optional["LearningEngine"] = None,
        collector: Optional["FeedbackCollector"] = None,
        orchestrator: Optional["EvolutionOrchestrator"] = None,
    ) -> dict[str, int]:
        """将反馈数据喂入 Evolution 引擎.

        可以同时传入多个引擎组件，反馈数据会被传递到所有提供的组件中.

        Args:
            engine:       LearningEngine 实例（可选）.
            collector:    evolution.FeedbackCollector 实例（可选）.
            orchestrator: EvolutionOrchestrator 实例（可选）.

        Returns:
            各组件更新的记录数.
        """
        results: dict[str, int] = {}

        # 传递给 LearningEngine
        if engine is not None:
            results["learning_engine"] = self._feed_to_learning_engine(engine)

        # 传递给 evolution.FeedbackCollector
        if collector is not None:
            results["feedback_collector"] = self._feed_to_feedback_collector(collector)

        # 传递给 EvolutionOrchestrator
        if orchestrator is not None:
            results["orchestrator"] = self._feed_to_orchestrator(orchestrator)

        return results

    def _feed_to_learning_engine(self, engine: "LearningEngine") -> int:
        """将反馈传递给 LearningEngine.

        遍历所有交互记录，将反馈信号附加到对应的 InteractionRecord 上.
        """
        updated = 0
        try:
            interactions = engine.get_interactions()
        except Exception:
            return 0

        for record in interactions:
            entry = self._entries.get(record.id)
            if entry is None:
                continue

            signal = self.get_signal(record.id)
            feedback_dict = {
                "rating": entry.explicit_type,
                "comment": entry.explicit_comment,
                "signal": signal.combined if signal else 0.0,
                "retries": entry.implicit_retries,
                "edited": entry.implicit_edited,
                "abandoned": entry.implicit_abandoned,
                "dwell_time": entry.implicit_dwell_time,
            }
            record.feedback = feedback_dict
            updated += 1

        return updated

    def _feed_to_feedback_collector(self, collector: "FeedbackCollector") -> int:
        """将反馈传递给 evolution.FeedbackCollector.

        将显式反馈和隐式反馈分别传递给 collector.
        """
        updated = 0
        for iid, entry in self._entries.items():
            try:
                # 显式反馈
                if entry.has_explicit:
                    rating = entry.explicit_type or "neutral"
                    # 将 star_X 转换为 thumbs_up/down/neutral
                    if rating and rating.startswith("star_"):
                        star_num = int(rating.split("_")[1])
                        if star_num >= 4:
                            rating = "thumbs_up"
                        elif star_num <= 2:
                            rating = "thumbs_down"
                        else:
                            rating = "neutral"
                    collector.collect_explicit(
                        interaction_id=iid,
                        rating=rating,
                        comment=entry.explicit_comment,
                    )

                # 隐式反馈
                completion = not entry.implicit_abandoned
                collector.collect_implicit(
                    interaction_id=iid,
                    completion=completion,
                    retries=entry.implicit_retries,
                    duration=entry.implicit_dwell_time,
                    tool_failures=0,
                )
                updated += 1
            except Exception:
                continue

        return updated

    def _feed_to_orchestrator(self, orchestrator: "EvolutionOrchestrator") -> int:
        """将反馈传递给 EvolutionOrchestrator.

        通过 orchestrator 的 learner 或 feedback_collector 属性传递.
        """
        updated = 0
        # 尝试通过 orchestrator 的子组件传递
        learner = getattr(orchestrator, "learner", None)
        if learner is not None:
            updated += self._feed_to_learning_engine(learner)

        fb_collector = getattr(orchestrator, "feedback_collector", None)
        if fb_collector is not None:
            updated += self._feed_to_feedback_collector(fb_collector)

        return updated

    # ── 统计信息 ──────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """返回反馈收集统计信息."""
        total = len(self._entries)
        explicit_count = sum(1 for e in self._entries.values() if e.has_explicit)
        implicit_count = sum(1 for e in self._entries.values() if e.has_implicit)

        signals = self.get_all_signals()
        positive = sum(1 for s in signals if s.combined > 0.2)
        negative = sum(1 for s in signals if s.combined < -0.2)
        neutral = total - positive - negative

        # 隐式信号统计
        edited_count = sum(1 for e in self._entries.values() if e.implicit_edited)
        abandoned_count = sum(1 for e in self._entries.values() if e.implicit_abandoned)
        copied_count = sum(1 for e in self._entries.values() if e.implicit_copied)
        regenerated_count = sum(1 for e in self._entries.values() if e.implicit_regenerated)

        return {
            "total_entries": total,
            "explicit_feedbacks": explicit_count,
            "implicit_feedbacks": implicit_count,
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "average_signal": self.get_average_signal(),
            "edited_count": edited_count,
            "abandoned_count": abandoned_count,
            "copied_count": copied_count,
            "regenerated_count": regenerated_count,
        }

    # ── 持久化 ────────────────────────────────────────────

    def _save(self) -> None:
        """保存到 JSON 文件."""
        filepath = os.path.join(self.storage_dir, "feedback_loop.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._entries.items()},
                f, ensure_ascii=False, indent=2,
            )

    def _load(self) -> None:
        """从 JSON 文件加载."""
        filepath = os.path.join(self.storage_dir, "feedback_loop.json")
        if not os.path.isfile(filepath):
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._entries = {
                k: FeedbackEntry.from_dict(v) for k, v in data.items()
            }
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    def clear(self) -> None:
        """清空所有反馈数据."""
        self._entries.clear()
        self._save()

    # ── 内部方法 ──────────────────────────────────────────

    def _get_or_create(
        self, interaction_id: str, session_id: str, user_id: str
    ) -> FeedbackEntry:
        """获取或创建 FeedbackEntry."""
        if interaction_id in self._entries:
            entry = self._entries[interaction_id]
            # 更新 session/user 如果提供了新的
            if session_id != "default":
                entry.session_id = session_id
            if user_id != "default":
                entry.user_id = user_id
            return entry
        return FeedbackEntry(
            interaction_id=interaction_id,
            session_id=session_id,
            user_id=user_id,
        )

    def _compute_explicit_signal(self, entry: FeedbackEntry) -> float:
        """计算显式反馈信号 [-1, 1]."""
        if not entry.has_explicit:
            return 0.0

        # 优先使用 explicit_type
        if entry.explicit_type and entry.explicit_type in self.TYPE_TO_SIGNAL:
            return self.TYPE_TO_SIGNAL[entry.explicit_type]

        # 使用数值评分
        if entry.explicit_rating is not None:
            # 1→-1, 3→0, 5→+1
            normalized = (float(entry.explicit_rating) - 3.0) / 2.0
            return round(max(-1.0, min(1.0, normalized)), 4)

        return 0.0

    def _compute_implicit_signal(self, entry: FeedbackEntry) -> float:
        """计算隐式反馈信号 [-1, 1].

        综合考虑:
            - 放弃对话（权重 35%）
            - 重试次数（权重 20%）
            - 编辑消息（权重 15%）
            - 停留时长（权重 10%）
            - 复制回答（权重 10%，正面）
            - 重新生成（权重 10%）
        """
        # 放弃：强烈负面
        abandon_score = -0.35 if entry.implicit_abandoned else 0.0

        # 重试：0 次 → 0, 越多越负面
        retry_score = self._retry_signal(entry.implicit_retries) * 0.20

        # 编辑：轻微负面
        edit_score = -0.15 if entry.implicit_edited else 0.0

        # 停留时长：适中最好
        dwell_score = self._dwell_signal(entry.implicit_dwell_time) * 0.10

        # 复制：正面
        copy_score = 0.10 if entry.implicit_copied else 0.0

        # 重新生成：负面
        regen_score = -0.10 if entry.implicit_regenerated else 0.0

        signal = abandon_score + retry_score + edit_score + dwell_score + copy_score + regen_score
        return round(max(-1.0, min(1.0, signal)), 4)

    def _retry_signal(self, retries: int) -> float:
        """重试次数信号 [-1, 1]."""
        if retries == 0:
            return 0.0
        max_r = self.MAX_RETRIES
        return round(-min(retries, max_r) / max_r, 4)

    def _dwell_signal(self, dwell_time: float) -> float:
        """停留时长信号 [-1, 1].

        适中停留（5-30 秒）表示用户在认真阅读，偏正面.
        过短（<1 秒）可能表示不感兴趣，偏负面.
        过长（>60 秒）可能表示困惑，轻微负面.
        """
        if dwell_time <= 0:
            return 0.0
        if dwell_time < 1.0:
            return -0.3
        if dwell_time < 5.0:
            return 0.2
        if dwell_time <= 30.0:
            return 0.5
        if dwell_time <= 60.0:
            return 0.2
        return -0.2

    @property
    def entries(self) -> list[FeedbackEntry]:
        """所有反馈条目."""
        return list(self._entries.values())

    @property
    def entry_count(self) -> int:
        """反馈条目数."""
        return len(self._entries)
