"""
Gateway Cost Tracking — Token-based cost calculation and budget management.

Tracks LLM API costs based on per-provider, per-model token pricing.
Provides budget alerts, aggregated reports, and JSON persistence.

Features:
    - Cost calculation from token usage and pricing tables
    - Budget threshold monitoring with alerts
    - Aggregated reports by provider, model, user, or time
    - JSON file persistence for cost history

Default pricing covers common OpenAI and Anthropic models (per 1K tokens).
Custom pricing can be provided via the ``pricing`` constructor argument.

Usage::

    from suyi.gateway import CostTracker

    tracker = CostTracker(budget=10.0)  # $10 budget

    # Record a request
    entry = tracker.record(
        provider="openai",
        model="gpt-4o",
        usage={"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
    )
    print(f"Cost: ${entry.cost:.4f}")
    print(f"Total: ${tracker.total_cost():.4f}")
    print(f"Within budget: {tracker.check_budget()}")

    # Get report
    report = tracker.get_report(by="provider")
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════
#  Default Pricing (per 1K tokens, in USD)
# ═══════════════════════════════════════════════════════════════

DEFAULT_PRICING: dict[str, dict[str, dict[str, float]]] = {
    "openai": {
        "gpt-4o": {"prompt": 0.0025, "completion": 0.01},
        "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
        "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
        "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
    },
    "anthropic": {
        "claude-sonnet-4-20250514": {"prompt": 0.003, "completion": 0.015},
        "claude-3-5-sonnet-20241022": {"prompt": 0.003, "completion": 0.015},
        "claude-3-opus-20240229": {"prompt": 0.015, "completion": 0.075},
        "claude-3-haiku-20240307": {"prompt": 0.00025, "completion": 0.00125},
    },
    "deepseek": {
        "deepseek-chat": {"prompt": 0.00014, "completion": 0.00028},
    },
}


# ═══════════════════════════════════════════════════════════════
#  Cost Entry
# ═══════════════════════════════════════════════════════════════


@dataclass
class CostEntry:
    """A single cost record for one LLM API call.

    Attributes:
        timestamp:        Unix timestamp of the request.
        provider:         Provider name (e.g., "openai").
        model:            Model name (e.g., "gpt-4o").
        prompt_tokens:    Input tokens consumed.
        completion_tokens: Output tokens consumed.
        cost:             Calculated cost in USD.
        user:             User identifier (default "default").
    """

    timestamp: float
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost: float
    user: str = "default"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CostEntry":
        return cls(**d)


# ═══════════════════════════════════════════════════════════════
#  Budget Alert
# ═══════════════════════════════════════════════════════════════


@dataclass
class BudgetAlert:
    """Budget alert notification.

    Attributes:
        level:      "warning" or "critical".
        message:    Alert message.
        spent:      Amount spent so far.
        budget:     Total budget.
        percentage: Percentage of budget used.
    """

    level: str  # "warning" or "critical"
    message: str
    spent: float
    budget: float
    percentage: float


# ═══════════════════════════════════════════════════════════════
#  Cost Tracker
# ═══════════════════════════════════════════════════════════════


class CostTracker:
    """Track and report LLM API costs.

    Args:
        pricing:      Custom pricing table (provider → model → {prompt, completion}).
                      If None, uses :data:`DEFAULT_PRICING`.
        budget:       Total budget in USD. ``None`` = no budget limit.
        storage_path: Path to JSON file for persistence. If None, no persistence.
        warning_threshold:  Fraction of budget that triggers a warning (default 0.8).
        critical_threshold: Fraction of budget that triggers a critical alert (default 1.0).
    """

    def __init__(
        self,
        pricing: Optional[dict] = None,
        budget: Optional[float] = None,
        storage_path: Optional[str] = None,
        warning_threshold: float = 0.8,
        critical_threshold: float = 1.0,
    ):
        self.pricing = pricing if pricing is not None else _deep_copy_pricing(DEFAULT_PRICING)
        self.budget = budget
        self.storage_path = storage_path
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self._entries: list[CostEntry] = []
        self._alerts: list[BudgetAlert] = []
        self._alerted_warning = False
        self._alerted_critical = False

        # Load from storage if available
        if storage_path and os.path.exists(storage_path):
            self.load()

    # ── Cost Calculation ───────────────────────────────────────

    def calculate_cost(
        self,
        provider: str,
        model: str,
        usage: dict,
    ) -> float:
        """Calculate the cost for a single API call.

        Args:
            provider: Provider name.
            model:    Model name.
            usage:    Usage dict with ``prompt_tokens`` and ``completion_tokens``.

        Returns:
            Cost in USD.
        """
        provider_pricing = self.pricing.get(provider, {})
        model_pricing = provider_pricing.get(
            model,
            {"prompt": 0.0, "completion": 0.0},
        )
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        prompt_cost = (prompt_tokens / 1000.0) * model_pricing.get("prompt", 0.0)
        completion_cost = (completion_tokens / 1000.0) * model_pricing.get("completion", 0.0)
        return prompt_cost + completion_cost

    def get_pricing(
        self, provider: str, model: str
    ) -> Optional[dict[str, float]]:
        """Get the pricing for a specific provider/model.

        Returns:
            Dict with ``prompt`` and ``completion`` rates, or None if unknown.
        """
        provider_pricing = self.pricing.get(provider, {})
        return provider_pricing.get(model)

    def set_pricing(
        self, provider: str, model: str, prompt: float, completion: float
    ) -> None:
        """Set or update pricing for a provider/model."""
        if provider not in self.pricing:
            self.pricing[provider] = {}
        self.pricing[provider][model] = {
            "prompt": prompt,
            "completion": completion,
        }

    # ── Recording ──────────────────────────────────────────────

    def record(
        self,
        provider: str,
        model: str,
        usage: dict,
        user: str = "default",
    ) -> CostEntry:
        """Record a cost entry.

        Args:
            provider: Provider name.
            model:    Model name.
            usage:    Usage dict with token counts.
            user:     User identifier.

        Returns:
            The created :class:`CostEntry`.
        """
        cost = self.calculate_cost(provider, model, usage)
        entry = CostEntry(
            timestamp=time.time(),
            provider=provider,
            model=model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            cost=cost,
            user=user,
        )
        self._entries.append(entry)

        # Check budget alerts
        self._check_budget_alerts()

        # Persist
        if self.storage_path:
            self.save()

        return entry

    # ── Budget Management ──────────────────────────────────────

    def total_cost(self) -> float:
        """Total cost across all entries."""
        return sum(e.cost for e in self._entries)

    def total_tokens(self) -> dict[str, int]:
        """Total tokens across all entries.

        Returns:
            Dict with ``prompt_tokens``, ``completion_tokens``, and ``total_tokens``.
        """
        prompt = sum(e.prompt_tokens for e in self._entries)
        completion = sum(e.completion_tokens for e in self._entries)
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        }

    def check_budget(self) -> bool:
        """Check if the total cost is within the budget.

        Returns:
            True if within budget (or no budget set), False if exceeded.
        """
        if self.budget is None:
            return True
        return self.total_cost() < self.budget

    def budget_remaining(self) -> Optional[float]:
        """Remaining budget. Returns None if no budget set."""
        if self.budget is None:
            return None
        return max(0.0, self.budget - self.total_cost())

    def budget_percentage(self) -> Optional[float]:
        """Percentage of budget used. Returns None if no budget set."""
        if self.budget is None or self.budget == 0:
            return None
        return (self.total_cost() / self.budget) * 100.0

    def _check_budget_alerts(self) -> None:
        """Generate budget alerts if thresholds are crossed."""
        if self.budget is None:
            return

        percentage = self.total_cost() / self.budget

        if (
            percentage >= self.critical_threshold
            and not self._alerted_critical
        ):
            alert = BudgetAlert(
                level="critical",
                message=(
                    f"Budget critical: ${self.total_cost():.4f} spent "
                    f"of ${self.budget:.2f} ({percentage*100:.1f}%)"
                ),
                spent=self.total_cost(),
                budget=self.budget,
                percentage=percentage * 100,
            )
            self._alerts.append(alert)
            self._alerted_critical = True

        elif (
            percentage >= self.warning_threshold
            and not self._alerted_warning
        ):
            alert = BudgetAlert(
                level="warning",
                message=(
                    f"Budget warning: ${self.total_cost():.4f} spent "
                    f"of ${self.budget:.2f} ({percentage*100:.1f}%)"
                ),
                spent=self.total_cost(),
                budget=self.budget,
                percentage=percentage * 100,
            )
            self._alerts.append(alert)
            self._alerted_warning = True

    @property
    def alerts(self) -> list[BudgetAlert]:
        """List of generated budget alerts."""
        return list(self._alerts)

    def clear_alerts(self) -> None:
        """Clear all alerts and reset alert flags."""
        self._alerts.clear()
        self._alerted_warning = False
        self._alerted_critical = False

    # ── Reports ────────────────────────────────────────────────

    def get_report(self, by: str = "provider") -> dict:
        """Generate an aggregated cost report.

        Args:
            by: Aggregation dimension: "provider", "model", "user", or "time".

        Returns:
            Dict mapping aggregation key to stats dict.
        """
        if by == "provider":
            return self._report_by_key(lambda e: e.provider)
        elif by == "model":
            return self._report_by_key(lambda e: f"{e.provider}/{e.model}")
        elif by == "user":
            return self._report_by_key(lambda e: e.user)
        elif by == "time":
            return self._report_by_time()
        else:
            raise ValueError(
                f"Unknown report type: {by}. "
                f"Supported: 'provider', 'model', 'user', 'time'"
            )

    def _report_by_key(self, key_fn) -> dict:
        """Aggregate by a key function."""
        report: dict[str, dict[str, Any]] = {}
        for e in self._entries:
            k = key_fn(e)
            if k not in report:
                report[k] = {
                    "cost": 0.0,
                    "requests": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                }
            report[k]["cost"] += e.cost
            report[k]["requests"] += 1
            report[k]["prompt_tokens"] += e.prompt_tokens
            report[k]["completion_tokens"] += e.completion_tokens
        return report

    def _report_by_time(self) -> dict:
        """Aggregate by date (YYYY-MM-DD)."""
        report: dict[str, dict[str, Any]] = {}
        for e in self._entries:
            date_str = time.strftime("%Y-%m-%d", time.localtime(e.timestamp))
            if date_str not in report:
                report[date_str] = {
                    "cost": 0.0,
                    "requests": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                }
            report[date_str]["cost"] += e.cost
            report[date_str]["requests"] += 1
            report[date_str]["prompt_tokens"] += e.prompt_tokens
            report[date_str]["completion_tokens"] += e.completion_tokens
        return report

    # ── Persistence ────────────────────────────────────────────

    def save(self) -> None:
        """Save cost data to the configured storage path (JSON)."""
        if not self.storage_path:
            return
        data = {
            "entries": [e.to_dict() for e in self._entries],
            "pricing": self.pricing,
            "budget": self.budget,
        }
        # Ensure directory exists
        dir_path = os.path.dirname(self.storage_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self) -> None:
        """Load cost data from the configured storage path."""
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        with open(self.storage_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._entries = [
            CostEntry.from_dict(e) for e in data.get("entries", [])
        ]
        if "pricing" in data:
            self.pricing = data["pricing"]
        if "budget" in data:
            self.budget = data["budget"]

    def clear(self) -> None:
        """Clear all entries and alerts."""
        self._entries.clear()
        self._alerts.clear()
        self._alerted_warning = False
        self._alerted_critical = False

    # ── Properties ─────────────────────────────────────────────

    @property
    def entries(self) -> list[CostEntry]:
        """All cost entries."""
        return list(self._entries)

    @property
    def entry_count(self) -> int:
        """Number of recorded entries."""
        return len(self._entries)


def _deep_copy_pricing(pricing: dict) -> dict:
    """Deep copy a pricing table (avoid shared mutable state)."""
    return json.loads(json.dumps(pricing))
