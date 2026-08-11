"""
Suyi LLM Adapters — Real LLM API integration.

Exports:
    OpenAIAdapter:     OpenAI-compatible adapter (DeepSeek, Moonshot, etc.)
    AnthropicAdapter:  Anthropic Claude adapter
    create_llm:        Factory function to create LLM instances
    create_llm_from_config: Create LLM from LLMConfig
    register_provider: Register custom provider adapters
    list_providers:    List supported providers

Usage::

    from suyi.llm import OpenAIAdapter, create_llm

    # Direct
    llm = OpenAIAdapter(api_key="sk-...", model="gpt-4o")

    # Factory
    llm = create_llm("openai", api_key="sk-...", model="gpt-4o")
    llm = create_llm("anthropic", api_key="sk-ant-...", model="claude-sonnet-4-20250514")
"""

from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .omniroute_adapter import OmniRouteAdapter
from .auto_router import (
    AutoRouter,
    ModelTier,
    ModelClassifier,
    TaskComplexity,
    RoutingDecision,
)
from .factory import (
    create_llm,
    create_llm_from_config,
    register_provider,
    list_providers,
)

__all__ = [
    "OpenAIAdapter",
    "AnthropicAdapter",
    "OmniRouteAdapter",
    "AutoRouter",
    "ModelTier",
    "ModelClassifier",
    "TaskComplexity",
    "RoutingDecision",
    "create_llm",
    "create_llm_from_config",
    "register_provider",
    "list_providers",
]
