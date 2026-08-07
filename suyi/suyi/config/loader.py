"""
Suyi Configuration Loader — Load config from YAML or dict.

Supports:
    - YAML files (requires PyYAML; falls back to JSON if unavailable)
    - JSON files (always supported via stdlib)
    - Dict → SuyiConfig
    - Default config generation

YAML parsing strategy:
    1. Try `import yaml` (PyYAML)
    2. If unavailable, try to parse as JSON (many YAML files are valid JSON)
    3. If neither works, raise an informative error

Usage::

    from suyi.config import load_config, get_default_config

    # From YAML file
    config = load_config("config.yaml")

    # From dict
    config = load_config_from_dict({"llm": {"provider": "openai", "model": "gpt-4o"}})

    # Default config
    config = get_default_config()
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .schema import (
    SuyiConfig,
    LLMConfig,
    MemoryConfig,
    ToolConfig,
    MiddlewareConfig,
    AgentConfig,
    EvolutionConfig,
)


# ═══════════════════════════════════════════════════════════════
#  YAML / JSON Parsing
# ═══════════════════════════════════════════════════════════════


def _try_import_yaml():
    """Try to import PyYAML. Returns the yaml module or None."""
    try:
        import yaml

        return yaml
    except ImportError:
        return None


def _parse_config_file(path: str) -> dict[str, Any]:
    """
    Parse a config file (YAML or JSON).

    Strategy:
        1. If file ends with .json, parse as JSON
        2. If file ends with .yaml/.yml, try PyYAML
        3. If PyYAML unavailable, try JSON as fallback
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    content = file_path.read_text(encoding="utf-8")

    # Determine file type
    suffix = file_path.suffix.lower()

    if suffix == ".json":
        return json.loads(content)

    # YAML file — try PyYAML first
    yaml = _try_import_yaml()
    if yaml is not None:
        return yaml.safe_load(content)

    # PyYAML not available — try JSON as fallback
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"Cannot parse '{path}': PyYAML is not installed and the file "
            f"is not valid JSON. Install PyYAML with: pip install pyyaml"
        )


# ═══════════════════════════════════════════════════════════════
#  Dict → Dataclass Conversion
# ═══════════════════════════════════════════════════════════════


def _build_llm_config(d: dict[str, Any]) -> LLMConfig:
    """Build LLMConfig from dict, ignoring unknown keys."""
    known_fields = {"provider", "api_key", "base_url", "model", "temperature", "max_tokens"}
    filtered = {k: v for k, v in d.items() if k in known_fields}
    return LLMConfig(**filtered)


def _build_memory_config(d: dict[str, Any]) -> MemoryConfig:
    """Build MemoryConfig from dict."""
    known_fields = {"working_capacity", "episodic_compression_threshold", "semantic_top_k"}
    filtered = {k: v for k, v in d.items() if k in known_fields}
    return MemoryConfig(**filtered)


def _build_tool_config(d: dict[str, Any]) -> ToolConfig:
    """Build ToolConfig from dict."""
    known_fields = {"max_retries", "parallel_enabled", "timeout"}
    filtered = {k: v for k, v in d.items() if k in known_fields}
    return ToolConfig(**filtered)


def _build_middleware_config(d: dict[str, Any]) -> MiddlewareConfig:
    """Build MiddlewareConfig from dict."""
    known_fields = {"enabled", "summarize", "memory_inject", "loop_detection", "clarification"}
    filtered = {k: v for k, v in d.items() if k in known_fields}
    return MiddlewareConfig(**filtered)


def _build_agent_config(d: dict[str, Any]) -> AgentConfig:
    """Build AgentConfig from dict."""
    known_fields = {"name", "max_iterations", "budget"}
    filtered = {k: v for k, v in d.items() if k in known_fields}
    return AgentConfig(**filtered)


def _build_evolution_config(d: dict[str, Any]) -> EvolutionConfig:
    """Build EvolutionConfig from dict."""
    known_fields = {"learning_enabled", "eval_interval"}
    filtered = {k: v for k, v in d.items() if k in known_fields}
    return EvolutionConfig(**filtered)


# ═══════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════


def load_config_from_dict(d: dict[str, Any]) -> SuyiConfig:
    """
    Build a SuyiConfig from a plain dict.

    Unknown keys are silently ignored. Missing sections use defaults.

    Args:
        d: Dict with optional keys: llm, memory, tools, middleware, agent, evolution

    Returns:
        A fully populated SuyiConfig.
    """
    config = SuyiConfig()  # Start with defaults

    if "llm" in d and isinstance(d["llm"], dict):
        config.llm = _build_llm_config(d["llm"])

    if "memory" in d and isinstance(d["memory"], dict):
        config.memory = _build_memory_config(d["memory"])

    if "tools" in d and isinstance(d["tools"], dict):
        config.tools = _build_tool_config(d["tools"])

    if "middleware" in d and isinstance(d["middleware"], dict):
        config.middleware = _build_middleware_config(d["middleware"])

    if "agent" in d and isinstance(d["agent"], dict):
        config.agent = _build_agent_config(d["agent"])

    if "evolution" in d and isinstance(d["evolution"], dict):
        config.evolution = _build_evolution_config(d["evolution"])

    return config


def load_config(path: str) -> SuyiConfig:
    """
    Load configuration from a YAML or JSON file.

    Args:
        path: Path to config file (.yaml, .yml, or .json)

    Returns:
        A SuyiConfig instance.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        RuntimeError: If the file can't be parsed (PyYAML missing + non-JSON content).
    """
    data = _parse_config_file(path)
    return load_config_from_dict(data)


def get_default_config() -> SuyiConfig:
    """
    Return the default Suyi configuration.

    All settings have sensible defaults — this returns a fresh copy
    with no customizations.
    """
    return SuyiConfig()


def save_config(config: SuyiConfig, path: str, format: str = "yaml") -> None:
    """
    Save a SuyiConfig to a file.

    Args:
        config: The SuyiConfig to save.
        path: Output file path.
        format: "yaml" or "json"
    """
    data = config.to_dict()

    if format == "json":
        Path(path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    elif format == "yaml":
        yaml = _try_import_yaml()
        if yaml is not None:
            Path(path).write_text(
                yaml.dump(data, default_flow_style=False, allow_unicode=True),
                encoding="utf-8",
            )
        else:
            # Fallback to JSON with .yaml extension
            Path(path).write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
    else:
        raise ValueError(f"Unsupported format: {format}. Use 'yaml' or 'json'.")
