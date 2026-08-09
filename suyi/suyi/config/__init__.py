"""
Suyi Configuration — Schema and loader for the Suyi framework.

Exports:
    SuyiConfig:        Top-level configuration container
    LLMConfig:         LLM provider configuration
    MemoryConfig:      Memory system configuration
    ToolConfig:        Tool system configuration
    MiddlewareConfig:  Middleware chain configuration
    AgentConfig:       Agent behavior configuration
    EvolutionConfig:   Self-evolution configuration

    load_config:           Load config from YAML/JSON file
    load_config_from_dict: Build config from a dict
    get_default_config:    Get default config
    save_config:           Save config to file

Usage::

    from suyi.config import load_config, get_default_config, SuyiConfig

    # Default
    config = get_default_config()

    # From file
    config = load_config("config.yaml")

    # From dict
    config = load_config_from_dict({"llm": {"provider": "openai"}})
"""

from .schema import (
    SuyiConfig,
    LLMConfig,
    MemoryConfig,
    ToolConfig,
    MiddlewareConfig,
    AgentConfig,
    EvolutionConfig,
    PersistenceConfig,
)
from .loader import (
    load_config,
    load_config_from_dict,
    get_default_config,
    save_config,
)

__all__ = [
    # Schema
    "SuyiConfig",
    "LLMConfig",
    "MemoryConfig",
    "ToolConfig",
    "MiddlewareConfig",
    "AgentConfig",
    "EvolutionConfig",
    "PersistenceConfig",
    # Loader
    "load_config",
    "load_config_from_dict",
    "get_default_config",
    "save_config",
]
