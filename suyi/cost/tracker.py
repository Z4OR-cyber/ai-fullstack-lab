"""
LLM 调用成本追踪 — 按模型/时间/会话维度统计 token 消耗和费用.

设计原则:
    - **多维度统计**：按 provider / model / session / time 四个维度
      聚合 token 消耗和费用.
    - **预算告警**：支持多级阈值告警（warning / critical / exhausted），
      与 core/budget.py 的 BudgetTracker 集成.
    - **会话关联**：每条成本记录关联 session_id，支持按会话查询.
    - **JSON 持久化**：成本数据持久化到 JSON 文件.
    - **实时查询**：支持随时查询累计费用、剩余预算、告警状态.

与 gateway/cost.py 的区别:
    - gateway CostTracker 侧重 API 网关层面的成本统计
    - 本模块侧重 Agent 运行时的成本追踪，增加了 session 维度
      和与 BudgetTracker 的深度集成

信号流转::

    LLM 调用 ──▶ CostRecord(provider, model, tokens, session_id)
                    │
                    ├─▶ 计算费用（基于定价表）
                    ├─▶ 记录到内存 + JSON
                    ├─▶ 检查预算阈值
                    │      ├─▶ warning alert
                    │      ├─▶ critical alert
                    │      └─▶ exhausted → 通知 BudgetTracker
                    └─▶ 返回 CostRecord

使用示例::

    from suyi.cost import CostTrackerV2, CostConfig, ModelPricing

    config = CostConfig(budget=10.0, warning_threshold=0.8)
    tracker = CostTrackerV2(config)

    record = tracker.record(
        provider="openai",
        model="gpt-4o",
        prompt_tokens=1000,
        completion_tokens=500,
        session_id="session_001",
    )
    print(f"本次费用: ${record.cost:.4f}")
    print(f"累计费用: ${tracker.total_cost():.4f}")
    print(f"预算告警: {tracker.alerts}")
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.budget import BudgetTracker, BudgetLevel


# ═══════════════════════════════════════════════════════════════
#  默认定价表（每 1K tokens，单位 USD）
# ═══════════════════════════════════════════════════════════════

DEFAULT_MODEL_PRICING: dict[str, dict[str, dict[str, float]]] = {
    "openai": {
        "gpt-4o": {"prompt": 0.0025, "completion": 0.01},
        "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
        "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
        "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
        "o1": {"prompt": 0.015, "completion": 0.06},
        "o1-mini": {"prompt": 0.003, "completion": 0.012},
    },
    "anthropic": {
        "claude-sonnet-4-20250514": {"prompt": 0.003, "completion": 0.015},
        "claude-3-5-sonnet-20241022": {"prompt": 0.003, "completion": 0.015},
        "claude-3-opus-20240229": {"prompt": 0.015, "completion": 0.075},
        "claude-3-haiku-20240307": {"prompt": 0.00025, "completion": 0.00125},
    },
    "deepseek": {
        "deepseek-chat": {"prompt": 0.00014, "completion": 0.00028},
        "deepseek-reasoner": {"prompt": 0.00055, "completion": 0.00219},
    },
}


# ═══════════════════════════════════════════════════════════════
#  数据结构
# ═══════════════════════════════════════════════════════════════


class AlertLevel(Enum):
    """告警级别."""

    WARNING = "warning"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"


@dataclass
class CostConfig:
    """成本追踪配置.

    Attributes:
        budget:              总预算（USD），None 表示无限制.
        warning_threshold:   告警阈值（预算使用百分比，0-1）.
        critical_threshold:  严重告警阈值.
        exhausted_threshold: 耗尽阈值.
        storage_path:        JSON 持久化路径.
        pricing:             自定义定价表（None 使用默认）.
        session_budget:      每会话预算（USD），None 表示不限制.
    """

    budget: Optional[float] = None
    warning_threshold: float = 0.8
    critical_threshold: float = 0.95
    exhausted_threshold: float = 1.0
    storage_path: Optional[str] = None
    pricing: Optional[dict] = None
    session_budget: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CostRecord:
    """单次 LLM 调用的成本记录.

    Attributes:
        timestamp:        时间戳.
        provider:         提供商名称.
        model:            模型名称.
        prompt_tokens:    输入 token 数.
        completion_tokens: 输出 token 数.
        total_tokens:     总 token 数.
        cost:             费用（USD）.
        session_id:       会话 ID.
        user:             用户标识.
        metadata:         附加元数据.
    """

    timestamp: float
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    session_id: str = "default"
    user: str = "default"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CostRecord":
        return cls(**d)


@dataclass
class CostAlert:
    """成本告警.

    Attributes:
        level:      告警级别.
        message:    告警消息.
        spent:      已花费金额.
        budget:     预算总额.
        percentage: 预算使用百分比.
        session_id: 关联的会话 ID（None 表示全局告警）.
        timestamp:  告警时间.
    """

    level: AlertLevel
    message: str
    spent: float
    budget: float
    percentage: float
    session_id: Optional[str] = None
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["level"] = self.level.value
        return d


@dataclass
class CostReport:
    """成本报告.

    Attributes:
        dimension:    聚合维度.
        entries:      聚合结果 {key: stats_dict}.
        total_cost:   总费用.
        total_tokens: 总 token 数.
        total_requests: 总请求数.
    """

    dimension: str
    entries: dict[str, dict[str, Any]]
    total_cost: float
    total_tokens: int
    total_requests: int

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════
#  成本追踪器
# ═══════════════════════════════════════════════════════════════


class CostTrackerV2:
    """LLM 调用成本追踪器（V2）.

    相比 gateway.CostTracker，增加了:
        - session 维度统计
        - 与 core.budget.BudgetTracker 集成
        - 多级告警（warning / critical / exhausted）
        - 每会话预算限制

    Args:
        config: 成本追踪配置.
        budget_tracker: 可选的 BudgetTracker 实例（用于集成）.

    使用示例::

        tracker = CostTrackerV2(CostConfig(budget=5.0))
        record = tracker.record(
            provider="openai", model="gpt-4o",
            prompt_tokens=1000, completion_tokens=500,
            session_id="s1",
        )
        report = tracker.get_report(by="session")
        alerts = tracker.alerts
    """

    def __init__(
        self,
        config: Optional[CostConfig] = None,
        budget_tracker: Optional["BudgetTracker"] = None,
    ):
        self.config = config or CostConfig()
        self.pricing = (
            self.config.pricing
            if self.config.pricing is not None
            else json.loads(json.dumps(DEFAULT_MODEL_PRICING))
        )
        self._records: list[CostRecord] = []
        self._alerts: list[CostAlert] = []
        self._alerted_levels: set[str] = set()  # 已触发过的告警级别
        self._session_alerted: dict[str, set[str]] = {}  # 会话级告警记录
        self._budget_tracker = budget_tracker

        # 从存储加载
        if self.config.storage_path and os.path.exists(self.config.storage_path):
            self.load()

    # ── 费用计算 ──────────────────────────────────────────

    def calculate_cost(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """计算单次调用费用.

        Args:
            provider:         提供商.
            model:            模型.
            prompt_tokens:    输入 token 数.
            completion_tokens: 输出 token 数.

        Returns:
            费用（USD）.
        """
        provider_pricing = self.pricing.get(provider, {})
        model_pricing = provider_pricing.get(
            model, {"prompt": 0.0, "completion": 0.0}
        )
        prompt_cost = (prompt_tokens / 1000.0) * model_pricing.get("prompt", 0.0)
        completion_cost = (completion_tokens / 1000.0) * model_pricing.get("completion", 0.0)
        return round(prompt_cost + completion_cost, 6)

    def get_pricing(self, provider: str, model: str) -> Optional[dict[str, float]]:
        """获取定价信息."""
        return self.pricing.get(provider, {}).get(model)

    def set_pricing(
        self, provider: str, model: str, prompt: float, completion: float
    ) -> None:
        """设置定价."""
        if provider not in self.pricing:
            self.pricing[provider] = {}
        self.pricing[provider][model] = {"prompt": prompt, "completion": completion}

    # ── 记录 ──────────────────────────────────────────────

    def record(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        session_id: str = "default",
        user: str = "default",
        metadata: Optional[dict] = None,
    ) -> CostRecord:
        """记录一次 LLM 调用的成本.

        Args:
            provider:         提供商.
            model:            模型.
            prompt_tokens:    输入 token 数.
            completion_tokens: 输出 token 数.
            session_id:       会话 ID.
            user:             用户标识.
            metadata:         附加元数据.

        Returns:
            CostRecord 实例.
        """
        total_tokens = prompt_tokens + completion_tokens
        cost = self.calculate_cost(
            provider, model, prompt_tokens, completion_tokens
        )
        record = CostRecord(
            timestamp=time.time(),
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            session_id=session_id,
            user=user,
            metadata=metadata or {},
        )
        self._records.append(record)

        # 检查全局预算告警
        self._check_global_alerts()

        # 检查会话预算告警
        if self.config.session_budget is not None:
            self._check_session_alerts(session_id)

        # 同步到 BudgetTracker
        self._sync_to_budget_tracker(total_tokens)

        # 持久化
        if self.config.storage_path:
            self._save()

        return record

    # ── 预算管理 ──────────────────────────────────────────

    def total_cost(self) -> float:
        """总费用."""
        return round(sum(r.cost for r in self._records), 6)

    def total_tokens(self) -> dict[str, int]:
        """总 token 数统计."""
        prompt = sum(r.prompt_tokens for r in self._records)
        completion = sum(r.completion_tokens for r in self._records)
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        }

    def session_cost(self, session_id: str) -> float:
        """指定会话的费用."""
        return round(
            sum(r.cost for r in self._records if r.session_id == session_id), 6
        )

    def session_tokens(self, session_id: str) -> dict[str, int]:
        """指定会话的 token 统计."""
        records = [r for r in self._records if r.session_id == session_id]
        prompt = sum(r.prompt_tokens for r in records)
        completion = sum(r.completion_tokens for r in records)
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        }

    def check_budget(self) -> bool:
        """检查是否在预算内."""
        if self.config.budget is None:
            return True
        return self.total_cost() < self.config.budget

    def budget_remaining(self) -> Optional[float]:
        """剩余预算."""
        if self.config.budget is None:
            return None
        return round(max(0.0, self.config.budget - self.total_cost()), 6)

    def budget_percentage(self) -> Optional[float]:
        """预算使用百分比."""
        if self.config.budget is None or self.config.budget == 0:
            return None
        return round((self.total_cost() / self.config.budget) * 100.0, 2)

    def session_budget_remaining(self, session_id: str) -> Optional[float]:
        """会话剩余预算."""
        if self.config.session_budget is None:
            return None
        return round(
            max(0.0, self.config.session_budget - self.session_cost(session_id)), 6
        )

    # ── 告警 ──────────────────────────────────────────────

    @property
    def alerts(self) -> list[CostAlert]:
        """所有告警列表."""
        return list(self._alerts)

    def clear_alerts(self) -> None:
        """清空告警."""
        self._alerts.clear()
        self._alerted_levels.clear()
        self._session_alerted.clear()

    def _check_global_alerts(self) -> None:
        """检查全局预算告警.

        三个级别独立检查，允许同时触发多个级别的告警
        （例如从 warning 直接跳到 exhausted 时也会触发 critical）.
        """
        if self.config.budget is None:
            return
        spent = self.total_cost()
        pct = spent / self.config.budget

        # 独立检查每个级别（不使用 elif，避免跳过中间级别）
        if pct >= self.config.warning_threshold and "warning" not in self._alerted_levels:
            alert = CostAlert(
                level=AlertLevel.WARNING,
                message=f"预算告警: ${spent:.4f} / ${self.config.budget:.2f} ({pct*100:.1f}%)",
                spent=spent,
                budget=self.config.budget,
                percentage=pct * 100,
            )
            self._alerts.append(alert)
            self._alerted_levels.add("warning")

        if pct >= self.config.critical_threshold and "critical" not in self._alerted_levels:
            alert = CostAlert(
                level=AlertLevel.CRITICAL,
                message=f"预算严重告警: ${spent:.4f} / ${self.config.budget:.2f} ({pct*100:.1f}%)",
                spent=spent,
                budget=self.config.budget,
                percentage=pct * 100,
            )
            self._alerts.append(alert)
            self._alerted_levels.add("critical")

        if pct >= self.config.exhausted_threshold and "exhausted" not in self._alerted_levels:
            alert = CostAlert(
                level=AlertLevel.EXHAUSTED,
                message=f"预算已耗尽: ${spent:.4f} / ${self.config.budget:.2f} ({pct*100:.1f}%)",
                spent=spent,
                budget=self.config.budget,
                percentage=pct * 100,
            )
            self._alerts.append(alert)
            self._alerted_levels.add("exhausted")

    def _check_session_alerts(self, session_id: str) -> None:
        """检查会话预算告警."""
        if self.config.session_budget is None:
            return
        spent = self.session_cost(session_id)
        pct = spent / self.config.session_budget
        session_alerts = self._session_alerted.setdefault(session_id, set())

        if pct >= 1.0 and "exhausted" not in session_alerts:
            alert = CostAlert(
                level=AlertLevel.EXHAUSTED,
                message=f"会话 {session_id} 预算耗尽: ${spent:.4f} / ${self.config.session_budget:.2f}",
                spent=spent,
                budget=self.config.session_budget,
                percentage=pct * 100,
                session_id=session_id,
            )
            self._alerts.append(alert)
            session_alerts.add("exhausted")

        elif pct >= 0.95 and "critical" not in session_alerts:
            alert = CostAlert(
                level=AlertLevel.CRITICAL,
                message=f"会话 {session_id} 预算严重告警: ${spent:.4f} / ${self.config.session_budget:.2f}",
                spent=spent,
                budget=self.config.session_budget,
                percentage=pct * 100,
                session_id=session_id,
            )
            self._alerts.append(alert)
            session_alerts.add("critical")

        elif pct >= 0.8 and "warning" not in session_alerts:
            alert = CostAlert(
                level=AlertLevel.WARNING,
                message=f"会话 {session_id} 预算告警: ${spent:.4f} / ${self.config.session_budget:.2f}",
                spent=spent,
                budget=self.config.session_budget,
                percentage=pct * 100,
                session_id=session_id,
            )
            self._alerts.append(alert)
            session_alerts.add("warning")

    # ── BudgetTracker 集成 ─────────────────────────────────

    def _sync_to_budget_tracker(self, tokens: int) -> None:
        """同步 token 消耗到 BudgetTracker.

        将 LLM 调用的 token 消耗记录到 core.budget.BudgetTracker，
        使其能感知到 token 预算的使用情况.
        """
        if self._budget_tracker is None:
            return
        # BudgetTracker.record_turn 接受 tokens_used 参数
        self._budget_tracker.record_turn(tokens_used=tokens)

    def get_budget_status(self) -> Optional[dict]:
        """获取 BudgetTracker 的预算状态（如果已集成）."""
        if self._budget_tracker is None:
            return None
        status = self._budget_tracker.status()
        return {
            "level": status.level.value,
            "turns_used": status.turns_used,
            "turns_max": status.turns_max,
            "tokens_used": status.tokens_used,
            "tokens_max": status.tokens_max,
            "wall_clock_ms": status.wall_clock_ms,
            "wall_clock_max": status.wall_clock_max,
            "is_exhausted": status.is_exhausted,
        }

    # ── 报告 ──────────────────────────────────────────────

    def get_report(self, by: str = "provider") -> CostReport:
        """生成聚合成本报告.

        Args:
            by: 聚合维度 — "provider" / "model" / "session" / "user" / "time".

        Returns:
            CostReport 实例.
        """
        key_fns = {
            "provider": lambda r: r.provider,
            "model": lambda r: f"{r.provider}/{r.model}",
            "session": lambda r: r.session_id,
            "user": lambda r: r.user,
        }
        if by == "time":
            entries = self._report_by_time()
        elif by in key_fns:
            entries = self._report_by_key(key_fns[by])
        else:
            raise ValueError(
                f"未知的报告维度: '{by}'. "
                f"支持: provider, model, session, user, time"
            )

        return CostReport(
            dimension=by,
            entries=entries,
            total_cost=self.total_cost(),
            total_tokens=self.total_tokens()["total_tokens"],
            total_requests=len(self._records),
        )

    def _report_by_key(self, key_fn) -> dict[str, dict[str, Any]]:
        """按键函数聚合."""
        report: dict[str, dict[str, Any]] = {}
        for r in self._records:
            k = key_fn(r)
            if k not in report:
                report[k] = {
                    "cost": 0.0,
                    "requests": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }
            report[k]["cost"] = round(report[k]["cost"] + r.cost, 6)
            report[k]["requests"] += 1
            report[k]["prompt_tokens"] += r.prompt_tokens
            report[k]["completion_tokens"] += r.completion_tokens
            report[k]["total_tokens"] += r.total_tokens
        return report

    def _report_by_time(self) -> dict[str, dict[str, Any]]:
        """按日期聚合."""
        report: dict[str, dict[str, Any]] = {}
        for r in self._records:
            date_str = time.strftime("%Y-%m-%d", time.localtime(r.timestamp))
            if date_str not in report:
                report[date_str] = {
                    "cost": 0.0,
                    "requests": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }
            report[date_str]["cost"] = round(report[date_str]["cost"] + r.cost, 6)
            report[date_str]["requests"] += 1
            report[date_str]["prompt_tokens"] += r.prompt_tokens
            report[date_str]["completion_tokens"] += r.completion_tokens
            report[date_str]["total_tokens"] += r.total_tokens
        return report

    # ── 持久化 ────────────────────────────────────────────

    def _save(self) -> None:
        """保存到 JSON 文件."""
        if not self.config.storage_path:
            return
        data = {
            "records": [r.to_dict() for r in self._records],
            "pricing": self.pricing,
            "config": self.config.to_dict(),
        }
        dir_path = os.path.dirname(self.config.storage_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(self.config.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self) -> None:
        """从 JSON 文件加载."""
        if not self.config.storage_path or not os.path.exists(self.config.storage_path):
            return
        try:
            with open(self.config.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._records = [
                CostRecord.from_dict(r) for r in data.get("records", [])
            ]
            if "pricing" in data:
                self.pricing = data["pricing"]
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    def clear(self) -> None:
        """清空所有记录和告警."""
        self._records.clear()
        self._alerts.clear()
        self._alerted_levels.clear()
        self._session_alerted.clear()

    # ── 属性 ──────────────────────────────────────────────

    @property
    def records(self) -> list[CostRecord]:
        """所有成本记录."""
        return list(self._records)

    @property
    def record_count(self) -> int:
        """记录数."""
        return len(self._records)

    @property
    def sessions(self) -> list[str]:
        """所有会话 ID."""
        return sorted(set(r.session_id for r in self._records))

    def __repr__(self) -> str:
        return (
            f"CostTrackerV2(records={len(self._records)}, "
            f"total_cost=${self.total_cost():.4f}, "
            f"budget={'$'+str(self.config.budget) if self.config.budget else '无限'})"
        )
