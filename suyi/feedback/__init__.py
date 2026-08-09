"""
Suyi Phase 12 — 用户反馈收集与学习闭环模块.

支持显式反馈（点赞/点踩/评分/评论）+ 隐式反馈（重试/编辑/放弃/停留时长），
反馈数据喂入 Evolution 引擎.

Exports:
    Enums:
        FeedbackType, ImplicitSignalType
    Data:
        FeedbackEntry, FeedbackSignalV2
    Loop:
        FeedbackLoop

Usage::

    from suyi.feedback import FeedbackLoop, FeedbackType

    loop = FeedbackLoop(storage_dir="data/feedback")
    loop.collect_explicit(
        interaction_id="int_001",
        feedback_type=FeedbackType.THUMBS_UP,
    )
    signal = loop.get_signal("int_001")
"""

from .loop import (
    FeedbackType,
    ImplicitSignalType,
    FeedbackEntry,
    FeedbackSignalV2,
    FeedbackLoop,
)

__all__ = [
    # 枚举
    "FeedbackType",
    "ImplicitSignalType",
    # 数据结构
    "FeedbackEntry",
    "FeedbackSignalV2",
    # 反馈闭环
    "FeedbackLoop",
]
