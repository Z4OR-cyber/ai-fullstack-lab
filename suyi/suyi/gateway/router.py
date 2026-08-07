"""
Gateway Router — Multi-LLM provider routing with failover and health checks.

The :class:`GatewayRouter` manages multiple LLM providers and routes
requests based on configurable rules:

    - **Rule-based routing**: By model name, task type, or explicit rules.
    - **Weight-based routing**: Weighted random selection for load balancing.
    - **Priority routing**: Lower priority value = higher preference.
    - **Failover**: If the primary provider fails, automatically try backups.
    - **Health checking**: Mark providers as healthy/unhealthy; skip unhealthy ones.

The router implements the :class:`~suyi.core.loop.LLMInterface` protocol,
so it can be used as a drop-in replacement for a single LLM adapter:

    .. code-block:: python

        from suyi.gateway import GatewayRouter, ProviderEntry
        from suyi.llm import OpenAIAdapter

        router = GatewayRouter(providers=[
            ProviderEntry(name="primary", llm=OpenAIAdapter(api_key="sk-1", model="gpt-4o"), priority=0),
            ProviderEntry(name="backup", llm=OpenAIAdapter(api_key="sk-2", model="gpt-4o"), priority=1),
        ])

        # Use as LLMInterface
        response = await router.chat(messages, tools, system_prompt)
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core.loop import LLMInterface, LLMResponse


# ═══════════════════════════════════════════════════════════════
#  Provider Entry
# ═══════════════════════════════════════════════════════════════


@dataclass
class ProviderEntry:
    """A registered LLM provider in the gateway.

    Attributes:
        name:        Unique provider name (e.g., "openai-primary").
        llm:         The LLMInterface instance (OpenAIAdapter, AnthropicAdapter, etc.).
        weight:      Load-balancing weight (higher = more traffic). Default 1.
        models:      List of model names this provider supports.
        priority:    Priority for failover (lower = tried first). Default 0.
        task_types:  Task types this provider is optimized for (e.g., ["chat", "code"]).
        healthy:     Whether the provider is currently considered healthy.
        last_check:  Timestamp of the last health check.
        failure_count: Number of consecutive failures.
    """

    name: str
    llm: LLMInterface
    weight: int = 1
    models: list[str] = field(default_factory=list)
    priority: int = 0
    task_types: list[str] = field(default_factory=list)
    healthy: bool = True
    last_check: float = 0.0
    failure_count: int = 0


# ═══════════════════════════════════════════════════════════════
#  Routing Rules
# ═══════════════════════════════════════════════════════════════


@dataclass
class RoutingRule:
    """A routing rule that maps a condition to a provider.

    Attributes:
        name:           Rule name for debugging.
        provider_name:  Provider to route to when this rule matches.
        model:          Model name to match (None = any).
        task_type:      Task type to match (None = any).
        priority:       Rule priority (lower = evaluated first).
    """

    name: str = ""
    provider_name: str = ""
    model: Optional[str] = None
    task_type: Optional[str] = None
    priority: int = 0


# ═══════════════════════════════════════════════════════════════
#  Gateway Router
# ═══════════════════════════════════════════════════════════════


class GatewayRouter:
    """Multi-LLM provider router with failover and health checks.

    Implements the :class:`~suyi.core.loop.LLMInterface` protocol,
    so it can be used anywhere a single LLM adapter is expected.

    Args:
        providers:     Initial list of providers.
        routing_rules: Routing rules for model/task-type-based routing.
    """

    def __init__(
        self,
        providers: Optional[list[ProviderEntry]] = None,
        routing_rules: Optional[list[RoutingRule]] = None,
    ):
        self._providers: dict[str, ProviderEntry] = {}
        self._routing_rules: list[RoutingRule] = list(routing_rules) if routing_rules else []

        if providers:
            for p in providers:
                self._providers[p.name] = p

    # ── Provider Management ────────────────────────────────────

    def add_provider(self, provider: ProviderEntry) -> None:
        """Register a new provider."""
        self._providers[provider.name] = provider

    def remove_provider(self, name: str) -> None:
        """Remove a provider by name."""
        self._providers.pop(name, None)

    def get_provider(self, name: str) -> Optional[ProviderEntry]:
        """Get a provider by name."""
        return self._providers.get(name)

    def list_providers(self) -> list[str]:
        """List all provider names."""
        return list(self._providers.keys())

    def add_routing_rule(self, rule: RoutingRule) -> None:
        """Add a routing rule."""
        self._routing_rules.append(rule)
        # Keep rules sorted by priority
        self._routing_rules.sort(key=lambda r: r.priority)

    @property
    def routing_rules(self) -> list[RoutingRule]:
        return list(self._routing_rules)

    # ── Health Management ──────────────────────────────────────

    def mark_unhealthy(self, name: str) -> None:
        """Mark a provider as unhealthy (will be skipped in routing)."""
        provider = self._providers.get(name)
        if provider:
            provider.healthy = False
            provider.failure_count += 1
            provider.last_check = time.monotonic()

    def mark_healthy(self, name: str) -> None:
        """Mark a provider as healthy (reset failure count)."""
        provider = self._providers.get(name)
        if provider:
            provider.healthy = True
            provider.failure_count = 0
            provider.last_check = time.monotonic()

    def get_healthy_providers(self) -> list[ProviderEntry]:
        """Get all healthy providers."""
        return [p for p in self._providers.values() if p.healthy]

    async def health_check(self) -> dict[str, bool]:
        """Check the health of all providers.

        Attempts a ``chat()`` call with a minimal message on each provider.
        Returns a dict of provider_name → healthy status.

        Note: This method calls ``chat()`` on each provider, which will
        make real API calls. Use sparingly.
        """
        results: dict[str, bool] = {}
        for name, provider in list(self._providers.items()):
            try:
                # Simple health check: try a minimal chat
                response = await provider.llm.chat(
                    messages=[{"role": "user", "content": "ping"}],
                    tools=[],
                    system_prompt="",
                )
                results[name] = True
                self.mark_healthy(name)
            except Exception:
                results[name] = False
                self.mark_unhealthy(name)
        return results

    # ── Routing ────────────────────────────────────────────────

    def route(
        self,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> Optional[ProviderEntry]:
        """Select a provider based on routing rules and health.

        Routing logic (in order):
        1. Check explicit routing rules for model/task_type matches.
        2. Filter healthy providers.
        3. If model specified, filter by providers that support it.
        4. If task_type specified, filter by providers configured for it.
        5. Among remaining, select by priority (lower first), then weighted random.

        Args:
            model:     Preferred model name.
            task_type: Task type (e.g., "chat", "code", "analysis").

        Returns:
            The selected provider, or None if no provider is available.
        """
        # 1. Check routing rules
        for rule in self._routing_rules:
            rule_match = True
            if rule.model is not None and model != rule.model:
                rule_match = False
            if rule.task_type is not None and task_type != rule.task_type:
                rule_match = False
            if rule_match:
                provider = self._providers.get(rule.provider_name)
                if provider and provider.healthy:
                    return provider

        # 2. Filter healthy providers
        candidates = self.get_healthy_providers()
        if not candidates:
            return None

        # 3. Filter by model
        if model:
            model_candidates = [
                p for p in candidates
                if not p.models or model in p.models
            ]
            if model_candidates:
                candidates = model_candidates

        # 4. Filter by task type
        if task_type:
            task_candidates = [
                p for p in candidates
                if not p.task_types or task_type in p.task_types
            ]
            if task_candidates:
                candidates = task_candidates

        if not candidates:
            return None

        # 5. Select by priority, then weighted random
        # Group by priority, take the lowest priority group
        min_priority = min(p.priority for p in candidates)
        priority_group = [p for p in candidates if p.priority == min_priority]

        if len(priority_group) == 1:
            return priority_group[0]

        # Weighted random selection
        total_weight = sum(p.weight for p in priority_group)
        if total_weight <= 0:
            return priority_group[0]

        r = random.uniform(0, total_weight)
        cumulative = 0
        for p in priority_group:
            cumulative += p.weight
            if r <= cumulative:
                return p

        return priority_group[-1]

    def get_sorted_providers(
        self,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> list[ProviderEntry]:
        """Get all providers sorted by priority for failover.

        Returns healthy providers sorted by priority (lowest first).
        The primary provider (from ``route()``) is first, followed by
        others as failover candidates.
        """
        candidates = self.get_healthy_providers()

        # Filter by model
        if model:
            filtered = [
                p for p in candidates
                if not p.models or model in p.models
            ]
            if filtered:
                candidates = filtered

        # Filter by task type
        if task_type:
            filtered = [
                p for p in candidates
                if not p.task_types or task_type in p.task_types
            ]
            if filtered:
                candidates = filtered

        # Sort by priority, then by weight (higher weight = preferred)
        candidates.sort(key=lambda p: (p.priority, -p.weight))
        return candidates

    # ── LLMInterface Implementation ────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> LLMResponse:
        """Route a chat request to a provider with automatic failover.

        Implements the :class:`~suyi.core.loop.LLMInterface` protocol.

        If the primary provider fails, automatically tries the next
        available provider. Failed providers are marked unhealthy.

        Args:
            messages:      Conversation messages.
            tools:         Tool definitions.
            system_prompt: System prompt.
            model:         Preferred model name (for routing).
            task_type:     Task type (for routing).

        Returns:
            The LLM response from the first successful provider.

        Raises:
            RuntimeError: If all providers fail.
        """
        providers = self.get_sorted_providers(model, task_type)
        if not providers:
            raise RuntimeError(
                "No healthy providers available for routing"
            )

        errors: list[str] = []
        for provider in providers:
            try:
                response = await provider.llm.chat(
                    messages, tools, system_prompt
                )
                # Success — mark healthy and return
                self.mark_healthy(provider.name)
                return response
            except Exception as e:
                errors.append(f"{provider.name}: {e}")
                self.mark_unhealthy(provider.name)

        raise RuntimeError(
            f"All providers failed: {'; '.join(errors)}"
        )

    # ── Status ─────────────────────────────────────────────────

    def get_status(self) -> dict[str, dict]:
        """Get the status of all providers.

        Returns:
            Dict of provider_name → status dict.
        """
        return {
            name: {
                "healthy": p.healthy,
                "priority": p.priority,
                "weight": p.weight,
                "models": p.models,
                "task_types": p.task_types,
                "failure_count": p.failure_count,
                "last_check": p.last_check,
            }
            for name, p in self._providers.items()
        }

    def __repr__(self) -> str:
        healthy = sum(1 for p in self._providers.values() if p.healthy)
        return (
            f"GatewayRouter(providers={len(self._providers)}, "
            f"healthy={healthy})"
        )
