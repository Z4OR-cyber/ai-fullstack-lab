"""
Suyi Configuration Schema — Dataclasses for all config sections.

Defines the type-safe configuration structure for the Suyi framework.
All config sections are dataclasses with sensible defaults.

Sections:
    LLMConfig:        LLM provider, model, API settings
    MemoryConfig:     Memory system tuning
    ToolConfig:       Tool system settings
    MiddlewareConfig: Middleware chain configuration
    AgentConfig:      Agent behavior and limits
    EvolutionConfig:  Self-evolution settings
    SuyiConfig:       Top-level container

Usage::

    from suyi.config import SuyiConfig, LLMConfig

    config = SuyiConfig(
        llm=LLMConfig(provider="openai", model="gpt-4o", api_key="sk-..."),
    )
    print(config.llm.model)  # "gpt-4o"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════
#  LLM Config
# ═══════════════════════════════════════════════════════════════


@dataclass
class LLMConfig:
    """
    LLM provider configuration.

    Attributes:
        provider:    Provider name ("openai", "anthropic", "deepseek", etc.)
        api_key:     API key (if None, reads from env var)
        base_url:    API base URL (auto-set for known providers if empty)
        model:       Model name
        temperature: Sampling temperature (0.0 - 2.0)
        max_tokens:  Max output tokens per response
    """

    provider: str = "openai"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 4096

    # Known provider default base URLs
    _DEFAULT_URLS: dict[str, str] = field(
        default_factory=lambda: {
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com",
            "deepseek": "https://api.deepseek.com/v1",
            "moonshot": "https://api.moonshot.cn/v1",
            "together": "https://api.together.xyz/v1",
            "groq": "https://api.groq.com/openai/v1",
            "openrouter": "https://openrouter.ai/api/v1",
        },
        repr=False,
        compare=False,
    )

    def get_base_url(self) -> str:
        """Get the effective base URL, falling back to provider default."""
        if self.base_url:
            return self.base_url
        return self._DEFAULT_URLS.get(self.provider, "https://api.openai.com/v1")

    def get_api_key(self) -> Optional[str]:
        """Get the API key, falling back to env var based on provider."""
        if self.api_key:
            return self.api_key
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "moonshot": "MOONSHOT_API_KEY",
            "together": "TOGETHER_API_KEY",
            "groq": "GROQ_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }
        import os

        env_var = env_map.get(self.provider, "OPENAI_API_KEY")
        return os.environ.get(env_var)


# ═══════════════════════════════════════════════════════════════
#  Memory Config
# ═══════════════════════════════════════════════════════════════


@dataclass
class MemoryConfig:
    """
    Memory system configuration.

    Attributes:
        working_capacity:              Max items in working memory
        episodic_compression_threshold: Turn count before compressing episodic memory
        semantic_top_k:                Number of semantic memory items to retrieve
    """

    working_capacity: int = 20
    episodic_compression_threshold: int = 10
    semantic_top_k: int = 5


# ═══════════════════════════════════════════════════════════════
#  Tool Config
# ═══════════════════════════════════════════════════════════════


@dataclass
class ToolConfig:
    """
    Tool system configuration.

    Attributes:
        max_retries:       Max retry attempts for tool execution
        parallel_enabled:  Whether tools can run in parallel
        timeout:           Per-tool timeout in seconds
    """

    max_retries: int = 2
    parallel_enabled: bool = True
    timeout: float = 60.0


# ═══════════════════════════════════════════════════════════════
#  Middleware Config
# ═══════════════════════════════════════════════════════════════


@dataclass
class MiddlewareConfig:
    """
    Middleware chain configuration.

    Attributes:
        enabled:    List of middleware names to enable (in order)
        summarize:  Whether to enable summarization middleware
        memory_inject: Whether to enable memory injection
        loop_detection: Whether to enable loop detection
        clarification: Whether to enable clarification middleware
    """

    enabled: list[str] = field(
        default_factory=lambda: [
            "summarization",
            "memory_inject",
            "loop_detection",
            "clarification",
        ]
    )
    summarize: bool = True
    memory_inject: bool = True
    loop_detection: bool = True
    clarification: bool = True


# ═══════════════════════════════════════════════════════════════
#  Agent Config
# ═══════════════════════════════════════════════════════════════


@dataclass
class AgentConfig:
    """
    Agent behavior configuration.

    Attributes:
        name:           Agent name
        max_iterations: Max loop iterations before forced stop
        budget:         Budget config for tokens/turns/time
    """

    name: str = "suyi"
    max_iterations: int = 25
    budget: dict[str, Any] = field(
        default_factory=lambda: {
            "max_turns": 25,
            "max_tokens": 100_000,
            "max_wall_clock": 300,
        }
    )


# ═══════════════════════════════════════════════════════════════
#  Evolution Config
# ═══════════════════════════════════════════════════════════════


@dataclass
class EvolutionConfig:
    """
    Self-evolution engine configuration.

    Attributes:
        learning_enabled: Whether the learning engine is active
        eval_interval:    How often (in interactions) to run evaluation
    """

    learning_enabled: bool = False
    eval_interval: int = 50


# ═══════════════════════════════════════════════════════════════
#  Top-Level Config
# ═══════════════════════════════════════════════════════════════


@dataclass
class SuyiConfig:
    """
    Top-level Suyi configuration.

    Container for all subsystem configs.

    Attributes:
        llm:        LLM provider configuration
        memory:     Memory system configuration
        tools:      Tool system configuration
        middleware: Middleware chain configuration
        agent:      Agent behavior configuration
        evolution:  Self-evolution configuration
    """

    llm: LLMConfig = field(default_factory=LLMConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    middleware: MiddlewareConfig = field(default_factory=MiddlewareConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    evolution: EvolutionConfig = field(default_factory=EvolutionConfig)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to a plain dict (for serialization)."""
        return {
            "llm": {
                "provider": self.llm.provider,
                "api_key": self.llm.api_key,
                "base_url": self.llm.base_url,
                "model": self.llm.model,
                "temperature": self.llm.temperature,
                "max_tokens": self.llm.max_tokens,
            },
            "memory": {
                "working_capacity": self.memory.working_capacity,
                "episodic_compression_threshold": self.memory.episodic_compression_threshold,
                "semantic_top_k": self.memory.semantic_top_k,
            },
            "tools": {
                "max_retries": self.tools.max_retries,
                "parallel_enabled": self.tools.parallel_enabled,
                "timeout": self.tools.timeout,
            },
            "middleware": {
                "enabled": list(self.middleware.enabled),
                "summarize": self.middleware.summarize,
                "memory_inject": self.middleware.memory_inject,
                "loop_detection": self.middleware.loop_detection,
                "clarification": self.middleware.clarification,
            },
            "agent": {
                "name": self.agent.name,
                "max_iterations": self.agent.max_iterations,
                "budget": dict(self.agent.budget),
            },
            "evolution": {
                "learning_enabled": self.evolution.learning_enabled,
                "eval_interval": self.evolution.eval_interval,
            },
        }
