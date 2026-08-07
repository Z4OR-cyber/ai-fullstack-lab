"""
Gateway Fallback Chain — Resilient LLM calling with retry and degradation.

The :class:`FallbackChain` wraps a :class:`~suyi.gateway.router.GatewayRouter`
and provides a multi-layered fallback strategy:

    1. **Retry**:          Retry the same provider on transient failures.
    2. **Provider switch**: Switch to the next provider on repeated failures.
    3. **Model downgrade**: Optionally fall back to a cheaper/faster model.
    4. **Cache**:          Optionally return a cached response from a prior call.

The chain implements the :class:`~suyi.core.loop.LLMInterface` protocol,
so it can be used as a drop-in replacement for a single LLM adapter.

Usage::

    from suyi.gateway import FallbackChain, FallbackConfig, GatewayRouter

    router = GatewayRouter(providers=[...])
    chain = FallbackChain(
        router=router,
        config=FallbackConfig(max_retries=2, enable_cache=True),
    )

    # Use as LLMInterface
    response = await chain.chat(messages, tools, system_prompt)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core.loop import LLMInterface, LLMResponse
from .router import GatewayRouter, ProviderEntry
from .ratelimit import RateLimiter
from .cost import CostTracker


# ═══════════════════════════════════════════════════════════════
#  Fallback Configuration
# ═══════════════════════════════════════════════════════════════


@dataclass
class FallbackConfig:
    """Configuration for the fallback chain.

    Attributes:
        max_retries:          Max retry attempts per provider before switching.
        retry_delay:          Delay between retries in seconds (0 = no delay).
        enable_provider_switch: Whether to try the next provider on failure.
        enable_model_downgrade: Whether to try a fallback model on failure.
        fallback_model:       Model name to use when downgrading.
        enable_cache:         Whether to cache successful responses.
        cache_ttl:            Cache time-to-live in seconds.
    """

    max_retries: int = 1
    retry_delay: float = 0.0
    enable_provider_switch: bool = True
    enable_model_downgrade: bool = False
    fallback_model: Optional[str] = None
    enable_cache: bool = False
    cache_ttl: float = 300.0  # 5 minutes


# ═══════════════════════════════════════════════════════════════
#  Fallback Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class FallbackResult:
    """Result of a fallback chain call.

    Attributes:
        response:        The successful LLM response.
        provider_name:   Name of the provider that succeeded.
        attempts:        Total number of attempts made.
        used_cache:      Whether the response came from cache.
        used_fallback:   Whether a fallback model/provider was used.
        errors:          List of error messages from failed attempts.
    """

    response: LLMResponse
    provider_name: str
    attempts: int
    used_cache: bool = False
    used_fallback: bool = False
    errors: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  Fallback Chain
# ═══════════════════════════════════════════════════════════════


class FallbackChain:
    """Resilient LLM calling with retry, provider switch, and degradation.

    Wraps a :class:`GatewayRouter` and implements the
    :class:`~suyi.core.loop.LLMInterface` protocol.

    Args:
        router:        The gateway router with registered providers.
        config:        Fallback configuration. Defaults to 1 retry per provider.
        cost_tracker:  Optional cost tracker for recording usage.
        rate_limiter:  Optional rate limiter for throttling requests.
    """

    def __init__(
        self,
        router: GatewayRouter,
        config: Optional[FallbackConfig] = None,
        cost_tracker: Optional[CostTracker] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.router = router
        self.config = config or FallbackConfig()
        self.cost_tracker = cost_tracker
        self.rate_limiter = rate_limiter
        self._cache: dict[str, tuple[float, LLMResponse]] = {}

    # ── Cache Management ───────────────────────────────────────

    def _cache_key(
        self,
        messages: list[dict],
        system_prompt: str,
        model: Optional[str],
    ) -> str:
        """Generate a cache key from request parameters."""
        key_data = json.dumps(
            {
                "messages": messages,
                "system_prompt": system_prompt,
                "model": model,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.md5(key_data.encode("utf-8")).hexdigest()

    def _get_cached(self, key: str) -> Optional[LLMResponse]:
        """Get a cached response if still valid."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        timestamp, response = entry
        if time.monotonic() - timestamp > self.config.cache_ttl:
            del self._cache[key]
            return None
        return response

    def _set_cached(self, key: str, response: LLMResponse) -> None:
        """Cache a response."""
        self._cache[key] = (time.monotonic(), response)

    def clear_cache(self) -> None:
        """Clear all cached responses."""
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        """Number of cached responses."""
        return len(self._cache)

    # ── LLMInterface Implementation ────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> LLMResponse:
        """Call LLM with fallback strategy.

        Implements the :class:`~suyi.core.loop.LLMInterface` protocol.

        Strategy (in order):
        1. Check cache (if enabled).
        2. Try each provider with retries.
        3. If model downgrade is enabled, try with fallback model.
        4. If cache is enabled and all else fails, return last cached response.

        Raises:
            RuntimeError: If all strategies fail and no cache is available.
        """
        result = await self.chat_with_details(
            messages, tools, system_prompt, model, task_type
        )
        return result.response

    async def chat_with_details(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> FallbackResult:
        """Call LLM with fallback strategy and return detailed result.

        Returns a :class:`FallbackResult` with metadata about which
        provider succeeded, how many attempts were made, etc.
        """
        cache_key = self._cache_key(messages, system_prompt, model)
        errors: list[str] = []
        attempts = 0

        # 1. Check cache
        if self.config.enable_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return FallbackResult(
                    response=cached,
                    provider_name="cache",
                    attempts=0,
                    used_cache=True,
                    errors=[],
                )

        # 2. Try providers with retries
        providers = self.router.get_sorted_providers(model, task_type)
        if not providers:
            raise RuntimeError(
                "No healthy providers available for fallback"
            )

        used_fallback = False

        for provider in providers:
            for attempt in range(self.config.max_retries + 1):
                attempts += 1

                # Rate limiting
                if self.rate_limiter is not None:
                    if not self.rate_limiter.acquire(key=provider.name):
                        errors.append(
                            f"{provider.name}: rate limited"
                        )
                        break  # Skip remaining retries for this provider

                try:
                    response = await provider.llm.chat(
                        messages, tools, system_prompt
                    )

                    # Success
                    self.router.mark_healthy(provider.name)

                    # Track cost
                    if self.cost_tracker is not None:
                        self.cost_tracker.record(
                            provider=provider.name,
                            model=model or "unknown",
                            usage=response.usage,
                        )

                    # Cache
                    if self.config.enable_cache:
                        self._set_cached(cache_key, response)

                    return FallbackResult(
                        response=response,
                        provider_name=provider.name,
                        attempts=attempts,
                        used_fallback=used_fallback,
                        errors=errors,
                    )

                except Exception as e:
                    error_msg = f"{provider.name} (attempt {attempt + 1}): {e}"
                    errors.append(error_msg)
                    self.router.mark_unhealthy(provider.name)

                    if self.config.retry_delay > 0:
                        await asyncio.sleep(self.config.retry_delay)

                    # Continue to next retry or next provider

        # 3. Model downgrade
        if (
            self.config.enable_model_downgrade
            and self.config.fallback_model
            and model != self.config.fallback_model
        ):
            used_fallback = True
            fallback_model = self.config.fallback_model
            fallback_providers = self.router.get_sorted_providers(
                fallback_model, task_type
            )

            for provider in fallback_providers:
                attempts += 1
                try:
                    response = await provider.llm.chat(
                        messages, tools, system_prompt
                    )
                    self.router.mark_healthy(provider.name)

                    if self.cost_tracker is not None:
                        self.cost_tracker.record(
                            provider=provider.name,
                            model=fallback_model,
                            usage=response.usage,
                        )

                    if self.config.enable_cache:
                        self._set_cached(cache_key, response)

                    return FallbackResult(
                        response=response,
                        provider_name=provider.name,
                        attempts=attempts,
                        used_fallback=True,
                        errors=errors,
                    )
                except Exception as e:
                    errors.append(
                        f"{provider.name} (fallback model): {e}"
                    )
                    self.router.mark_unhealthy(provider.name)

        # 4. Return cached response as last resort
        if self.config.enable_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return FallbackResult(
                    response=cached,
                    provider_name="cache",
                    attempts=attempts,
                    used_cache=True,
                    used_fallback=True,
                    errors=errors,
                )

        # All strategies failed
        raise RuntimeError(
            f"All fallback strategies failed. Errors: {'; '.join(errors)}"
        )

    # ── Status ─────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Get the status of the fallback chain."""
        return {
            "router": self.router.get_status(),
            "cache_size": self.cache_size,
            "config": {
                "max_retries": self.config.max_retries,
                "enable_provider_switch": self.config.enable_provider_switch,
                "enable_model_downgrade": self.config.enable_model_downgrade,
                "enable_cache": self.config.enable_cache,
                "fallback_model": self.config.fallback_model,
            },
            "has_cost_tracker": self.cost_tracker is not None,
            "has_rate_limiter": self.rate_limiter is not None,
        }
