"""
Suyi AI Gateway Module — Multi-provider LLM routing, rate limiting, cost tracking, and fallback.

Exports:
    Router:
        GatewayRouter, ProviderEntry, RoutingRule

    Rate Limiting:
        RateLimiter, TokenBucket, SlidingWindow, RateLimitAlgorithm

    Cost Tracking:
        CostTracker, CostEntry, BudgetAlert, DEFAULT_PRICING

    Fallback:
        FallbackChain, FallbackConfig, FallbackResult

Usage::

    from suyi.gateway import (
        GatewayRouter, ProviderEntry,
        RateLimiter, TokenBucket, SlidingWindow,
        CostTracker, CostEntry,
        FallbackChain, FallbackConfig,
    )

    # Create a resilient LLM gateway
    router = GatewayRouter(providers=[
        ProviderEntry(name="primary", llm=openai_adapter, priority=0),
        ProviderEntry(name="backup", llm=anthropic_adapter, priority=1),
    ])
    chain = FallbackChain(
        router=router,
        config=FallbackConfig(max_retries=2, enable_cache=True),
    )

    # Use as LLMInterface
    response = await chain.chat(messages, tools, system_prompt)
"""

from .router import GatewayRouter, ProviderEntry, RoutingRule
from .ratelimit import (
    RateLimiter,
    TokenBucket,
    SlidingWindow,
    RateLimitAlgorithm,
)
from .cost import (
    CostTracker,
    CostEntry,
    BudgetAlert,
    DEFAULT_PRICING,
)
from .fallback import (
    FallbackChain,
    FallbackConfig,
    FallbackResult,
)

__all__ = [
    # Router
    "GatewayRouter",
    "ProviderEntry",
    "RoutingRule",
    # Rate Limiting
    "RateLimiter",
    "TokenBucket",
    "SlidingWindow",
    "RateLimitAlgorithm",
    # Cost Tracking
    "CostTracker",
    "CostEntry",
    "BudgetAlert",
    "DEFAULT_PRICING",
    # Fallback
    "FallbackChain",
    "FallbackConfig",
    "FallbackResult",
]
