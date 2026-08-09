"""
Suyi Phase 12 — LLM 调用成本追踪模块.

按模型/时间/会话维度统计 token 消耗和费用，支持预算告警，
与 core/budget.BudgetTracker 集成.

Exports:
    Config:
        CostConfig
    Data:
        CostRecord, CostAlert, CostReport, AlertLevel
    Pricing:
        DEFAULT_MODEL_PRICING
    Tracker:
        CostTrackerV2

Usage::

    from suyi.cost import CostTrackerV2, CostConfig

    tracker = CostTrackerV2(CostConfig(budget=10.0))
    record = tracker.record(
        provider="openai", model="gpt-4o",
        prompt_tokens=1000, completion_tokens=500,
        session_id="s1",
    )
    report = tracker.get_report(by="session")
"""

from .tracker import (
    CostConfig,
    CostRecord,
    CostAlert,
    CostReport,
    AlertLevel,
    DEFAULT_MODEL_PRICING,
    CostTrackerV2,
)

__all__ = [
    "CostConfig",
    "CostRecord",
    "CostAlert",
    "CostReport",
    "AlertLevel",
    "DEFAULT_MODEL_PRICING",
    "CostTrackerV2",
]
