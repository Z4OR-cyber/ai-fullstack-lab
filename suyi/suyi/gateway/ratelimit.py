"""
Gateway Rate Limiting — Token bucket and sliding window algorithms.

Pure Python implementations of two classic rate-limiting algorithms:

    - **TokenBucket**:   Smooth rate limiting with burst capacity.
      Tokens refill at a fixed rate; each request consumes tokens.
      Allows short bursts up to the bucket capacity.

    - **SlidingWindow**: Exact count-based rate limiting.
      Tracks request timestamps within a sliding time window.
      No bursts beyond the max request count.

    - **RateLimiter**: Composite limiter supporting per-provider and
      per-user limiting with configurable strategy.

All algorithms use ``time.monotonic()`` for elapsed-time calculation,
making them immune to system clock adjustments.

Usage::

    from suyi.gateway import TokenBucket, SlidingWindow, RateLimiter

    # Token bucket: 60 requests/min, burst of 10
    bucket = TokenBucket(capacity=10, refill_rate=1.0)  # 1 token/sec
    if bucket.try_acquire(1):
        # proceed

    # Sliding window: 100 requests per 60 seconds
    window = SlidingWindow(window_size=60, max_requests=100)
    if window.try_acquire(1):
        # proceed

    # Composite limiter (per-provider)
    limiter = RateLimiter(strategy="token_bucket", requests_per_minute=60)
    if limiter.acquire(key="openai"):
        # proceed
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import deque
from typing import Optional, Union


# ═══════════════════════════════════════════════════════════════
#  Abstract Rate Limit Algorithm
# ═══════════════════════════════════════════════════════════════


class RateLimitAlgorithm(ABC):
    """Abstract base for rate-limiting algorithms.

    All algorithms implement a unified interface:
        - ``try_acquire(count)``: Attempt to acquire ``count`` units.
        - ``available()``:        Query available units (non-consuming).
    """

    @abstractmethod
    def try_acquire(self, count: float = 1) -> bool:
        """Try to acquire ``count`` units.

        Returns:
            True if successful (units consumed), False if rate limited.
        """
        ...

    @abstractmethod
    def available(self) -> float:
        """Query available units without consuming.

        Returns:
            Approximate number of units available.
        """
        ...

    def check(self) -> bool:
        """Check if 1 unit is available (non-consuming)."""
        return self.available() >= 1


# ═══════════════════════════════════════════════════════════════
#  Token Bucket
# ═══════════════════════════════════════════════════════════════


class TokenBucket(RateLimitAlgorithm):
    """Token bucket rate limiter.

    Tokens are added to the bucket at a fixed ``refill_rate`` (tokens/sec).
    Each request consumes tokens. The bucket has a maximum ``capacity``,
    allowing short bursts.

    Attributes:
        capacity:    Maximum tokens the bucket can hold (burst size).
        refill_rate: Tokens added per second.
    """

    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self._tokens: float = float(capacity)
        self._last_update: float = time.monotonic()

    def _refill(self) -> None:
        """Add tokens based on elapsed time since last update."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(
            self.capacity,
            self._tokens + elapsed * self.refill_rate,
        )
        self._last_update = now

    def try_acquire(self, count: float = 1) -> bool:
        """Try to consume ``count`` tokens.

        Returns True if enough tokens were available (and consumed),
        False otherwise.
        """
        self._refill()
        if self._tokens >= count:
            self._tokens -= count
            return True
        return False

    def available(self) -> float:
        """Return current available tokens (after refilling)."""
        self._refill()
        return self._tokens

    def reset(self) -> None:
        """Reset the bucket to full capacity."""
        self._tokens = self.capacity
        self._last_update = time.monotonic()

    def __repr__(self) -> str:
        return (
            f"TokenBucket(capacity={self.capacity}, "
            f"refill_rate={self.refill_rate}, tokens={self._tokens:.2f})"
        )


# ═══════════════════════════════════════════════════════════════
#  Sliding Window
# ═══════════════════════════════════════════════════════════════


class SlidingWindow(RateLimitAlgorithm):
    """Sliding window rate limiter.

    Tracks request timestamps within a sliding time window of
    ``window_size`` seconds. Allows at most ``max_requests`` within
    any window.

    More precise than token bucket for request counting, but uses
    O(max_requests) memory for timestamp storage.

    Attributes:
        window_size:   Window duration in seconds.
        max_requests:  Maximum requests allowed within the window.
    """

    def __init__(self, window_size: float, max_requests: int):
        self.window_size = float(window_size)
        self.max_requests = int(max_requests)
        self._requests: deque[float] = deque()

    def _purge(self) -> None:
        """Remove timestamps that have fallen outside the window."""
        cutoff = time.monotonic() - self.window_size
        while self._requests and self._requests[0] <= cutoff:
            self._requests.popleft()

    def try_acquire(self, count: float = 1) -> bool:
        """Try to record ``count`` requests.

        Returns True if there's room for ``count`` more requests
        within the window (and records them), False otherwise.
        """
        self._purge()
        if len(self._requests) + count > self.max_requests:
            return False
        now = time.monotonic()
        for _ in range(int(count)):
            self._requests.append(now)
        return True

    def available(self) -> float:
        """Return available request slots in the current window."""
        self._purge()
        return max(0, self.max_requests - len(self._requests))

    def reset(self) -> None:
        """Clear all recorded requests."""
        self._requests.clear()

    @property
    def current_count(self) -> int:
        """Number of requests in the current window."""
        self._purge()
        return len(self._requests)

    def __repr__(self) -> str:
        return (
            f"SlidingWindow(window_size={self.window_size}, "
            f"max_requests={self.max_requests}, current={len(self._requests)})"
        )


# ═══════════════════════════════════════════════════════════════
#  Composite Rate Limiter
# ═══════════════════════════════════════════════════════════════


class RateLimiter:
    """Composite rate limiter with per-key (provider/user) tracking.

    Maintains separate limiters for each key, supporting both
    request-count and token-count limits.

    Args:
        strategy:            "token_bucket" or "sliding_window".
        requests_per_minute: Max requests per minute per key.
        tokens_per_minute:   Max tokens per minute per key.
    """

    def __init__(
        self,
        strategy: str = "token_bucket",
        requests_per_minute: int = 60,
        tokens_per_minute: int = 100_000,
    ):
        if strategy not in ("token_bucket", "sliding_window"):
            raise ValueError(
                f"Unknown strategy: {strategy}. "
                f"Supported: 'token_bucket', 'sliding_window'"
            )
        self.strategy = strategy
        self._rpm = requests_per_minute
        self._tpm = tokens_per_minute
        self._request_limiters: dict[str, RateLimitAlgorithm] = {}
        self._token_limiters: dict[str, RateLimitAlgorithm] = {}

    def _make_limiter(self, capacity: int) -> RateLimitAlgorithm:
        """Create a new limiter with the configured strategy."""
        if self.strategy == "token_bucket":
            return TokenBucket(
                capacity=capacity,
                refill_rate=capacity / 60.0,  # tokens per second
            )
        else:
            return SlidingWindow(
                window_size=60,
                max_requests=capacity,
            )

    def _get_request_limiter(self, key: str) -> RateLimitAlgorithm:
        if key not in self._request_limiters:
            self._request_limiters[key] = self._make_limiter(self._rpm)
        return self._request_limiters[key]

    def _get_token_limiter(self, key: str) -> RateLimitAlgorithm:
        if key not in self._token_limiters:
            self._token_limiters[key] = self._make_limiter(self._tpm)
        return self._token_limiters[key]

    # ── Public API ─────────────────────────────────────────────

    def check(self, key: str = "default") -> bool:
        """Check if a request would be allowed (non-consuming).

        Args:
            key: Provider name, user ID, or "default".

        Returns:
            True if a request is currently allowed.
        """
        return self._get_request_limiter(key).check()

    def acquire(self, key: str = "default", tokens: int = 0) -> bool:
        """Try to acquire a request (and optionally tokens).

        Args:
            key:    Provider name, user ID, or "default".
            tokens: Number of tokens to consume (0 = don't track tokens).

        Returns:
            True if the request is allowed (and tokens consumed),
            False if rate limited.
        """
        req_limiter = self._get_request_limiter(key)
        if not req_limiter.try_acquire(1):
            return False
        if tokens > 0:
            tok_limiter = self._get_token_limiter(key)
            if not tok_limiter.try_acquire(tokens):
                # Token limit exceeded — request slot is consumed
                # (no refund, to keep the algorithm simple)
                return False
        return True

    def reset(self, key: Optional[str] = None) -> None:
        """Reset limiters for a key (or all keys if None)."""
        if key is None:
            self._request_limiters.clear()
            self._token_limiters.clear()
        else:
            self._request_limiters.pop(key, None)
            self._token_limiters.pop(key, None)

    @property
    def keys(self) -> list[str]:
        """List all keys that have limiters."""
        return sorted(
            set(self._request_limiters.keys())
            | set(self._token_limiters.keys())
        )

    def get_status(self, key: str = "default") -> dict:
        """Get the current rate limit status for a key.

        Returns:
            Dict with ``requests_available`` and ``tokens_available``.
        """
        req_limiter = self._get_request_limiter(key)
        tok_limiter = self._get_token_limiter(key)
        return {
            "key": key,
            "strategy": self.strategy,
            "requests_available": req_limiter.available(),
            "tokens_available": tok_limiter.available(),
            "requests_per_minute": self._rpm,
            "tokens_per_minute": self._tpm,
        }
