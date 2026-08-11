"""
LLM Factory — Create LLM instances from configuration.

Provides a unified interface for creating LLM adapters based on provider name.
Supports 'openai' (and compatible providers) and 'anthropic'.

Usage::

    from suyi.llm import create_llm
    from suyi.config import LLMConfig

    # From kwargs
    llm = create_llm("openai", api_key="sk-...", model="gpt-4o")

    # From config
    config = LLMConfig(provider="openai", api_key="sk-...", model="gpt-4o")
    llm = create_llm_from_config(config)

    # Custom OpenAI-compatible provider
    llm = create_llm(
        "openai",
        api_key="sk-...",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
    )
"""

from __future__ import annotations

from typing import Any

from ..core.loop import LLMInterface
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .omniroute_adapter import OmniRouteAdapter
from .auto_router import AutoRouter


# Registry of provider → adapter class
_PROVIDER_REGISTRY: dict[str, type] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "omniroute": OmniRouteAdapter,
    "auto": AutoRouter,
}

# Aliases for common OpenAI-compatible providers
_PROVIDER_ALIASES: dict[str, str] = {
    "deepseek": "openai",
    "moonshot": "openai",
    "kimi": "openai",
    "together": "openai",
    "groq": "openai",
    "openrouter": "openai",
    "ollama": "openai",
    "vllm": "openai",
    "claude": "anthropic",
    "omni": "omniroute",
    "smart": "auto",
    "router": "auto",
}


def register_provider(name: str, adapter_class: type) -> None:
    """
    Register a custom LLM provider adapter.

    Args:
        name: Provider name (e.g., "my_provider")
        adapter_class: Class implementing the LLMInterface protocol
    """
    _PROVIDER_REGISTRY[name] = adapter_class


def create_llm(provider: str, **kwargs: Any) -> LLMInterface:
    """
    Create an LLM adapter instance.

    Args:
        provider: Provider name. Supported:
            - "openai" (also: deepseek, moonshot, together, groq, etc.)
            - "anthropic" (also: claude)
        **kwargs: Provider-specific arguments (api_key, model, base_url, etc.)

    Returns:
        An LLMInterface instance.

    Raises:
        ValueError: If the provider is not supported.
    """
    # Resolve aliases
    resolved = _PROVIDER_ALIASES.get(provider.lower(), provider.lower())

    if resolved not in _PROVIDER_REGISTRY:
        supported = ", ".join(sorted(set(_PROVIDER_REGISTRY) | set(_PROVIDER_ALIASES)))
        raise ValueError(
            f"Unsupported LLM provider: '{provider}'. "
            f"Supported providers: {supported}"
        )

    # AutoRouter 特殊处理：先创建底层 adapter，再用 AutoRouter 包装
    if resolved == "auto":
        # 如果传入了 adapter 实例，直接包装
        if "adapter" in kwargs:
            return AutoRouter(**kwargs)
        # 否则创建 OmniRouteAdapter 作为底层
        adapter_kwargs = {k: v for k, v in kwargs.items()
                          if k in ("api_key", "base_url", "model", "temperature",
                                    "max_tokens", "timeout", "max_retries", "retry_interval")}
        inner_adapter = OmniRouteAdapter(**adapter_kwargs)
        router_kwargs = {k: v for k, v in kwargs.items()
                         if k in ("model_tiers", "strategy", "enable_fallback",
                                   "history_size", "enable_logging")}
        return AutoRouter(adapter=inner_adapter, **router_kwargs)

    adapter_class = _PROVIDER_REGISTRY[resolved]
    return adapter_class(**kwargs)


def create_llm_from_config(config) -> LLMInterface:
    """
    Create an LLM adapter from a LLMConfig dataclass.

    Args:
        config: An LLMConfig instance with provider, api_key, model, etc.

    Returns:
        An LLMInterface instance.
    """
    kwargs: dict[str, Any] = {}

    # Extract all non-None fields from the config
    for field_name in ("api_key", "base_url", "model", "temperature", "max_tokens"):
        value = getattr(config, field_name, None)
        if value is not None:
            kwargs[field_name] = value

    return create_llm(config.provider, **kwargs)


def list_providers() -> list[str]:
    """List all supported provider names (including aliases)."""
    return sorted(set(_PROVIDER_REGISTRY) | set(_PROVIDER_ALIASES))
