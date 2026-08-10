"""
Cron Expression Parser — Standard 5-field cron expression support.

Parses and evaluates cron expressions in the classic Unix format::

    ┌───────────── minute (0-59)
    │ ┌───────────── hour (0-23)
    │ │ ┌───────────── day of month (1-31)
    │ │ │ ┌───────────── month (1-12)
    │ │ │ │ ┌───────────── day of week (0-6, 0=Sunday)
    │ │ │ │ │
    * * * * *

Supported syntax within each field:
    *       — all values
    */n     — every *n* values (step)
    a-b     — inclusive range
    a,b,c   — comma-separated list
    a-b/n   — step within a range
    a       — single value

Special notes:
    - Day-of-week 0 and 7 both represent Sunday.
    - When both day-of-month and day-of-week are restricted (not ``*``),
      the match succeeds if *either* field matches (OR logic, per
      standard cron behaviour).
    - ``next_run`` returns the first matching time strictly *after*
      the given ``after`` datetime, with seconds and microseconds
      zeroed out.

Design:
    - Pure Python standard library only.
    - ``CronExpression`` is immutable after parsing.
    - Serialization via ``to_dict`` / ``from_dict``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════
#  Field Boundaries
# ═══════════════════════════════════════════════════════════════

# (min, max) for each of the 5 cron fields, in order:
#   minute, hour, day-of-month, month, day-of-week
_FIELD_BOUNDS: list[tuple[int, int]] = [
    (0, 59),   # minute
    (0, 23),   # hour
    (1, 31),   # day of month
    (1, 12),   # month
    (0, 7),    # day of week (0-7, where 0 and 7 = Sunday)
]

_FIELD_NAMES: list[str] = [
    "minute",
    "hour",
    "day_of_month",
    "month",
    "day_of_week",
]

# Maximum iterations for next_run search (safety valve).
# 366 days * 24 * 60 = 527,040 minutes — covers a full year.
_MAX_SEARCH_ITERATIONS: int = 366 * 24 * 60


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════


def _parse_field(
    expr: str,
    min_val: int,
    max_val: int,
    field_name: str,
) -> set[int]:
    """Parse a single cron field expression into a set of matching values.

    Args:
        expr:       Raw field string (e.g. ``"*/5"``, ``"1-10"``, ``"1,3,5"``).
        min_val:    Minimum allowed value for this field.
        max_val:    Maximum allowed value for this field.
        field_name: Field name for error messages.

    Returns:
        A set of integers that this field matches.

    Raises:
        ValueError: If the expression is invalid or values are out of range.
    """
    expr = expr.strip()
    if not expr:
        raise ValueError(f"Empty {field_name} field in cron expression")

    result: set[int] = set()

    # Handle comma-separated lists: "1,3,5" or "1-3,10-12/2"
    for part in expr.split(","):
        part = part.strip()
        if not part:
            raise ValueError(
                f"Empty list element in {field_name} field: '{expr}'"
            )
        result.update(_parse_range_or_step(part, min_val, max_val, field_name))

    return result


def _parse_range_or_step(
    part: str,
    min_val: int,
    max_val: int,
    field_name: str,
) -> set[int]:
    """Parse a single field component that may contain a step (``/``).

    Handles:
        ``*``     → all values
        ``*/n``   → every n-th value
        ``a-b``   → range a to b inclusive
        ``a-b/n`` → every n-th value in range a to b
        ``a``     → single value
        ``a/n``   → from a to max, every n-th

    Args:
        part:       Single component (no commas).
        min_val:    Field minimum.
        max_val:    Field maximum.
        field_name: Field name for errors.

    Returns:
        Set of matching integers.
    """
    # Split on '/' for step
    if "/" in part:
        base, _, step_str = part.partition("/")
        try:
            step = int(step_str)
        except ValueError:
            raise ValueError(
                f"Invalid step '{step_str}' in {field_name} field"
            )
        if step <= 0:
            raise ValueError(
                f"Step must be positive in {field_name} field, got {step}"
            )
    else:
        base = part
        step = 1

    # Determine the range
    if base == "*":
        lo, hi = min_val, max_val
    elif "-" in base:
        lo_str, _, hi_str = base.partition("-")
        try:
            lo = int(lo_str)
            hi = int(hi_str)
        except ValueError:
            raise ValueError(
                f"Invalid range '{base}' in {field_name} field"
            )
    else:
        try:
            val = int(base)
        except ValueError:
            raise ValueError(
                f"Invalid value '{base}' in {field_name} field"
            )
        if "/" in part:
            # "a/n" → from a to max, every n
            lo = val
            hi = max_val
        else:
            lo = hi = val

    # For day-of-week, normalize 7 → 0 (both = Sunday).
    # Only normalize when the user explicitly specified 7 (not when
    # it comes from the wildcard * expanding to the field max).
    if field_name == "day_of_week" and base != "*":
        if lo == 7:
            lo = 0
        if hi == 7:
            hi = 0

    # Validate bounds
    _validate_bounds(lo, hi, min_val, max_val, field_name, part)

    # Build the set
    result: set[int] = set()

    if field_name == "day_of_week" and lo > hi:
        # Wrap-around range like 5-1 (Fri to Mon) — non-standard
        # but useful extension.  Iterate from lo to max (6), then
        # from min (0) to hi, applying the step.
        for v in range(lo, 7, step):
            result.add(v)
        offset = (7 - lo) % step
        start = (step - offset) % step
        if start <= hi:
            for v in range(start, hi + 1, step):
                result.add(v)
    else:
        for v in range(lo, hi + 1, step):
            if field_name == "day_of_week" and v == 7:
                result.add(0)
            else:
                result.add(v)

    return result


def _validate_bounds(
    lo: int,
    hi: int,
    min_val: int,
    max_val: int,
    field_name: str,
    raw: str,
) -> None:
    """Validate that lo and hi are within the allowed range.

    Args:
        lo:        Parsed low value.
        hi:        Parsed high value.
        min_val:   Field minimum.
        max_val:   Field maximum.
        field_name: Field name for error message.
        raw:       Original raw string for error context.

    Raises:
        ValueError: If any value is out of range or lo > hi.
    """
    effective_max = max_val
    if field_name == "day_of_week":
        effective_max = 7  # Allow 7 as Sunday before normalization

    if lo < min_val or lo > effective_max:
        raise ValueError(
            f"{field_name} value {lo} out of range "
            f"[{min_val}-{effective_max}]: '{raw}'"
        )
    if hi < min_val or hi > effective_max:
        raise ValueError(
            f"{field_name} value {hi} out of range "
            f"[{min_val}-{effective_max}]: '{raw}'"
        )
    if lo > hi and not (field_name == "day_of_week" and lo > hi):
        raise ValueError(
            f"Range start {lo} > end {hi} in {field_name} field: '{raw}'"
        )


# ═══════════════════════════════════════════════════════════════
#  CronExpression
# ═══════════════════════════════════════════════════════════════


class CronExpression:
    """
    Parsed 5-field cron expression.

    Parses a standard cron expression and provides matching and
    next-run computation.

    Attributes:
        expression:    The original expression string.
        minutes:       Set of matching minutes (0-59).
        hours:         Set of matching hours (0-23).
        days_of_month: Set of matching days (1-31).
        months:        Set of matching months (1-12).
        days_of_week:  Set of matching weekdays (0-6, 0=Sunday).
        _dom_restricted: True if day-of-month is not ``*``.
        _dow_restricted: True if day-of-week is not ``*``.

    Usage::

        cron = CronExpression("*/5 * * * *")
        cron.matches(datetime(2025, 1, 1, 12, 0))  # True
        cron.matches(datetime(2025, 1, 1, 12, 3))  # False

        next_time = cron.next_run(datetime(2025, 1, 1, 12, 0))
        # → datetime(2025, 1, 1, 12, 5, 0)
    """

    def __init__(self, expression: str) -> None:
        """Parse a cron expression string.

        Args:
            expression: A 5-field cron expression (e.g. ``"*/5 * * * *"``).

        Raises:
            ValueError: If the expression is malformed or contains
                out-of-range values.
        """
        self.expression: str = expression.strip()

        fields = self.expression.split()
        if len(fields) != 5:
            raise ValueError(
                f"Cron expression must have exactly 5 fields, "
                f"got {len(fields)}: '{expression}'"
            )

        # Track whether day-of-month / day-of-week are restricted (not '*')
        self._dom_restricted: bool = fields[2] != "*"
        self._dow_restricted: bool = fields[3] != "*" if len(fields) > 3 else False
        # Re-check with correct field index (weekday is field[4])
        self._dow_restricted = fields[4] != "*"

        # Parse each field
        self.minutes: set[int] = _parse_field(
            fields[0], *_FIELD_BOUNDS[0], _FIELD_NAMES[0]
        )
        self.hours: set[int] = _parse_field(
            fields[1], *_FIELD_BOUNDS[1], _FIELD_NAMES[1]
        )
        self.days_of_month: set[int] = _parse_field(
            fields[2], *_FIELD_BOUNDS[2], _FIELD_NAMES[2]
        )
        self.months: set[int] = _parse_field(
            fields[3], *_FIELD_BOUNDS[3], _FIELD_NAMES[3]
        )
        self.days_of_week: set[int] = _parse_field(
            fields[4], *_FIELD_BOUNDS[4], _FIELD_NAMES[4]
        )

    # ── Matching ───────────────────────────────────────────────

    def matches(self, dt: datetime) -> bool:
        """Check whether *dt* matches this cron expression.

        Only minute, hour, day, month, and weekday are evaluated;
        seconds and microseconds are ignored.

        Standard cron OR-logic applies: when both day-of-month and
        day-of-week are restricted, the datetime matches if *either*
        field matches. When only one is restricted, that field must
        match.

        Args:
            dt: The datetime to check.

        Returns:
            ``True`` if *dt* satisfies all applicable field constraints.
        """
        if dt.minute not in self.minutes:
            return False
        if dt.hour not in self.hours:
            return False
        if dt.month not in self.months:
            return False

        # Python weekday(): Monday=0, Sunday=6
        # Cron weekday: Sunday=0, Saturday=6
        cron_weekday = (dt.weekday() + 1) % 7

        # Day-of-month and day-of-week OR-logic
        if self._dom_restricted and self._dow_restricted:
            return (
                dt.day in self.days_of_month
                or cron_weekday in self.days_of_week
            )
        elif self._dom_restricted:
            return dt.day in self.days_of_month
        elif self._dow_restricted:
            return cron_weekday in self.days_of_week
        else:
            return True

    # ── Next Run ───────────────────────────────────────────────

    def next_run(self, after: datetime) -> datetime:
        """Compute the next matching time strictly after *after*.

        Starts from ``after`` truncated to the minute, then increments
        by one minute until a match is found (or the safety limit is
        reached).

        Args:
            after: The reference datetime. The returned time will be
                   the first match at or after ``after`` with seconds
                   and microseconds zeroed, but strictly greater than
                   ``after`` if ``after`` already has zeroed seconds.

        Returns:
            The next datetime that matches this cron expression.

        Raises:
            ValueError: If no match is found within one year
                (indicates an impossible or overly restrictive expression).
        """
        # Start from the next minute after `after`, with seconds zeroed
        candidate = after.replace(second=0, microsecond=0)
        if candidate <= after:
            candidate += timedelta(minutes=1)

        for _ in range(_MAX_SEARCH_ITERATIONS):
            if self.matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)

        raise ValueError(
            f"No matching time found within {_MAX_SEARCH_ITERATIONS} "
            f"minutes for expression '{self.expression}'"
        )

    def prev_run(self, before: datetime) -> Optional[datetime]:
        """Compute the most recent matching time at or before *before*.

        This is useful for determining the last time a task *should*
        have run.

        Args:
            before: The reference datetime (inclusive).

        Returns:
            The most recent matching datetime, or ``None`` if none
            found within the search window.
        """
        candidate = before.replace(second=0, microsecond=0)
        if candidate > before:
            candidate -= timedelta(minutes=1)

        for _ in range(_MAX_SEARCH_ITERATIONS):
            if self.matches(candidate):
                return candidate
            candidate -= timedelta(minutes=1)
            # Don't go before year 2000 as a sanity check
            if candidate.year < 2000:
                return None

        return None

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for persistence.

        Returns:
            A dict with the expression string and parsed field sets.
        """
        return {
            "expression": self.expression,
            "minutes": sorted(self.minutes),
            "hours": sorted(self.hours),
            "days_of_month": sorted(self.days_of_month),
            "months": sorted(self.months),
            "days_of_week": sorted(self.days_of_week),
            "dom_restricted": self._dom_restricted,
            "dow_restricted": self._dow_restricted,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CronExpression":
        """Reconstruct from a dict produced by ``to_dict``.

        Args:
            d: A dict containing at least an ``"expression"`` key.

        Returns:
            A new ``CronExpression`` parsed from the stored expression.
        """
        return cls(d["expression"])

    # ── Dunder Methods ─────────────────────────────────────────

    def __repr__(self) -> str:
        return f"CronExpression('{self.expression}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CronExpression):
            return NotImplemented
        return self.expression == other.expression

    def __hash__(self) -> int:
        return hash(self.expression)
