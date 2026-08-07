"""
Budget Manager — Three-dimensional budget tracking with progressive thresholds.

Dimensions:
    - max_turns:       Maximum number of agent loop iterations
    - max_tokens:      Maximum total token consumption
    - max_wall_clock_ms: Maximum wall-clock time in milliseconds

Thresholds (progressive, not cliff — smooth degradation curve):
    approaching (0.70) → gentle reminder to be efficient
    critical    (0.85) → explicit instruction to wrap up
    compacting  (0.90) → urgent: provide final answer now
    exhausted   (1.00) → stop, return partial result with explanation

Design principles:
    - Budget check goes at the TOP of the loop (single chokepoint)
    - format_constraint_as_instruction() returns natural language, not numbers
    - Exhaustion returns a text explanation, never raises an exception
    - Adding a new budget dimension only requires changing _compute_level()
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class BudgetLevel(Enum):
    """Progressive budget levels — smooth degradation, not cliff."""

    NORMAL = "normal"
    APPROACHING = "approaching"
    CRITICAL = "critical"
    COMPACTING = "compacting"
    EXHAUSTED = "exhausted"


@dataclass
class BudgetConfig:
    """Configuration for the three-dimensional budget."""

    max_turns: int = 25
    max_tokens: int = 100_000
    max_wall_clock_ms: int = 300_000  # 5 minutes

    def validate(self) -> None:
        if self.max_turns <= 0:
            raise ValueError("max_turns must be positive")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if self.max_wall_clock_ms <= 0:
            raise ValueError("max_wall_clock_ms must be positive")


@dataclass
class BudgetStatus:
    """Immutable snapshot of budget usage at a point in time."""

    level: BudgetLevel
    turns_used: int
    turns_max: int
    tokens_used: int
    tokens_max: int
    wall_clock_ms: int
    wall_clock_max: int

    @property
    def is_exhausted(self) -> bool:
        return self.level == BudgetLevel.EXHAUSTED

    @property
    def is_normal(self) -> bool:
        return self.level == BudgetLevel.NORMAL

    def utilization(self) -> dict[str, float]:
        """Return utilization ratio for each dimension (0.0 – 1.0+)."""
        return {
            "turns": self.turns_used / self.turns_max if self.turns_max > 0 else 0.0,
            "tokens": self.tokens_used / self.tokens_max if self.tokens_max > 0 else 0.0,
            "wall_clock": (
                self.wall_clock_ms / self.wall_clock_max
                if self.wall_clock_max > 0
                else 0.0
            ),
        }

    def max_utilization(self) -> float:
        """Return the highest utilization across all dimensions."""
        return max(self.utilization().values())

    def __str__(self) -> str:
        u = self.utilization()
        return (
            f"BudgetStatus(level={self.level.value}, "
            f"turns={self.turns_used}/{self.turns_max} ({u['turns']:.0%}), "
            f"tokens={self.tokens_used}/{self.tokens_max} ({u['tokens']:.0%}), "
            f"wall_clock={self.wall_clock_ms}ms/{self.wall_clock_max}ms "
            f"({u['wall_clock']:.0%}))"
        )


class BudgetTracker:
    """
    Tracks three-dimensional budget and provides progressive constraint instructions.

    Usage:
        tracker = BudgetTracker(BudgetConfig(max_turns=10))
        tracker.start()
        for _ in range(10):
            if tracker.is_exhausted():
                break
            tracker.record_turn(tokens_used=500)
            instruction = tracker.format_constraint_as_instruction()
            if instruction:
                # inject into system prompt
                print(instruction)

    Adding a new budget dimension:
        1. Add field to BudgetConfig + BudgetStatus
        2. Update _compute_level() to include the new dimension
        3. Update format_constraint_as_instruction() if needed
    """

    # Progressive thresholds — smooth degradation curve
    THRESHOLDS: dict[str, float] = {
        "approaching": 0.70,
        "critical": 0.85,
        "compacting": 0.90,
    }

    def __init__(self, config: Optional[BudgetConfig] = None):
        self.config = config or BudgetConfig()
        self.config.validate()
        self._turns_used: int = 0
        self._tokens_used: int = 0
        self._start_time: Optional[float] = None

    # ── Lifecycle ──────────────────────────────────────────────

    def start(self) -> None:
        """Start the wall-clock timer. Call once at the beginning of the loop."""
        self._start_time = time.monotonic()

    def reset(self) -> None:
        """Reset all counters. Useful for a fresh run."""
        self._turns_used = 0
        self._tokens_used = 0
        self._start_time = None

    def record_turn(self, tokens_used: int = 0) -> None:
        """Record one completed turn and its token consumption."""
        self._turns_used += 1
        self._tokens_used += tokens_used

    # ── Queries ────────────────────────────────────────────────

    @property
    def turns_used(self) -> int:
        return self._turns_used

    @property
    def tokens_used(self) -> int:
        return self._tokens_used

    @property
    def wall_clock_ms(self) -> int:
        if self._start_time is None:
            return 0
        return int((time.monotonic() - self._start_time) * 1000)

    def _compute_level(self) -> BudgetLevel:
        """
        Determine the current budget level based on max utilization.

        Adding a new dimension: include it in the max() call below.
        This is the ONLY place that needs to change for new budget axes.
        """
        util = max(
            self._turns_used / self.config.max_turns
            if self.config.max_turns > 0
            else 0.0,
            self._tokens_used / self.config.max_tokens
            if self.config.max_tokens > 0
            else 0.0,
            self.wall_clock_ms / self.config.max_wall_clock_ms
            if self.config.max_wall_clock_ms > 0
            else 0.0,
        )

        if util >= 1.0:
            return BudgetLevel.EXHAUSTED
        if util >= self.THRESHOLDS["compacting"]:
            return BudgetLevel.COMPACTING
        if util >= self.THRESHOLDS["critical"]:
            return BudgetLevel.CRITICAL
        if util >= self.THRESHOLDS["approaching"]:
            return BudgetLevel.APPROACHING
        return BudgetLevel.NORMAL

    def status(self) -> BudgetStatus:
        """Return a snapshot of current budget status."""
        return BudgetStatus(
            level=self._compute_level(),
            turns_used=self._turns_used,
            turns_max=self.config.max_turns,
            tokens_used=self._tokens_used,
            tokens_max=self.config.max_tokens,
            wall_clock_ms=self.wall_clock_ms,
            wall_clock_max=self.config.max_wall_clock_ms,
        )

    def is_exhausted(self) -> bool:
        """Check if any dimension has exceeded its budget."""
        return self._compute_level() == BudgetLevel.EXHAUSTED

    # ── Natural Language Constraints ───────────────────────────

    def format_constraint_as_instruction(self) -> Optional[str]:
        """
        Return a natural-language constraint instruction based on current budget level.

        Returns None when:
            - Budget is NORMAL (no constraint needed)
            - Budget is EXHAUSTED (use exhaustion_message() instead)

        The returned text is designed to be injected into the system prompt
        as a <budget_constraint> section.
        """
        level = self._compute_level()

        if level == BudgetLevel.NORMAL:
            return None

        if level == BudgetLevel.APPROACHING:
            return (
                "You are approaching your resource budget. "
                "Be more concise and focus on completing the task efficiently. "
                "Avoid unnecessary exploration or redundant tool calls."
            )

        if level == BudgetLevel.CRITICAL:
            return (
                "You are in a critical resource state. "
                "You must now work toward your final answer directly. "
                "Do not explore further — synthesize what you have and conclude."
            )

        if level == BudgetLevel.COMPACTING:
            return (
                "Resources are nearly exhausted. "
                "Provide your final answer immediately using only the information "
                "you already have. Do not make any more tool calls."
            )

        # EXHAUSTED — handled by exhaustion_message()
        return None

    def exhaustion_message(self) -> str:
        """
        Return a human-readable explanation of why the budget was exhausted.

        Does NOT raise an exception — the caller decides how to handle it.
        The message is designed to be returned as the agent's final output
        when the budget runs out.
        """
        status = self.status()
        reasons: list[str] = []

        if status.turns_used >= status.turns_max:
            reasons.append(
                f"turn limit reached ({status.turns_used}/{status.turns_max})"
            )
        if status.tokens_used >= status.tokens_max:
            reasons.append(
                f"token budget exceeded ({status.tokens_used}/{status.tokens_max})"
            )
        if status.wall_clock_ms >= status.wall_clock_max:
            reasons.append(
                f"time limit exceeded ({status.wall_clock_ms}ms/"
                f"{status.wall_clock_max}ms)"
            )

        if not reasons:
            return "Budget exhausted for unknown reasons."

        return (
            "Agent stopped due to budget exhaustion: "
            + "; ".join(reasons)
            + ". Partial results may be available in the conversation history."
        )
