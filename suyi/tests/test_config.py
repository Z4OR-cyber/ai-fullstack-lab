"""
Tests for Suyi Configuration System.

Tests cover:
    - Schema dataclasses: defaults, field validation
    - Loader: YAML, JSON, dict loading, file not found
    - LLMConfig: API key resolution, base URL defaults
    - Round-trip: config → dict → config
    - Default config generation
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from suyi.config import (
    SuyiConfig,
    LLMConfig,
    MemoryConfig,
    ToolConfig,
    MiddlewareConfig,
    AgentConfig,
    EvolutionConfig,
    load_config,
    load_config_from_dict,
    get_default_config,
    save_config,
)


# ═══════════════════════════════════════════════════════════════
#  Schema Tests
# ═══════════════════════════════════════════════════════════════


class TestLLMConfig:
    """Test LLMConfig dataclass."""

    def test_defaults(self):
        config = LLMConfig()
        assert config.provider == "openai"
        assert config.api_key is None
        assert config.base_url is None
        assert config.model == "gpt-4o"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096

    def test_custom_values(self):
        config = LLMConfig(
            provider="anthropic",
            api_key="sk-ant-test",
            model="claude-sonnet-4-20250514",
            temperature=0.3,
            max_tokens=8192,
        )
        assert config.provider == "anthropic"
        assert config.api_key == "sk-ant-test"
        assert config.temperature == 0.3
        assert config.max_tokens == 8192

    def test_get_base_url_explicit(self):
        config = LLMConfig(base_url="https://custom.api.com/v1")
        assert config.get_base_url() == "https://custom.api.com/v1"

    def test_get_base_url_default_openai(self):
        config = LLMConfig(provider="openai")
        assert config.get_base_url() == "https://api.openai.com/v1"

    def test_get_base_url_default_anthropic(self):
        config = LLMConfig(provider="anthropic")
        assert config.get_base_url() == "https://api.anthropic.com"

    def test_get_base_url_default_deepseek(self):
        config = LLMConfig(provider="deepseek")
        assert config.get_base_url() == "https://api.deepseek.com/v1"

    def test_get_api_key_explicit(self):
        config = LLMConfig(api_key="sk-direct")
        assert config.get_api_key() == "sk-direct"

    def test_get_api_key_from_env(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("OPENAI_API_KEY", "sk-env-key")
            config = LLMConfig(provider="openai")
            assert config.get_api_key() == "sk-env-key"

    def test_get_api_key_anthropic_env(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
            config = LLMConfig(provider="anthropic")
            assert config.get_api_key() == "sk-ant-env"

    def test_get_api_key_returns_none_if_not_set(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.delenv("OPENAI_API_KEY", raising=False)
            config = LLMConfig(provider="openai")
            assert config.get_api_key() is None


class TestMemoryConfig:
    """Test MemoryConfig dataclass."""

    def test_defaults(self):
        config = MemoryConfig()
        assert config.working_capacity == 20
        assert config.episodic_compression_threshold == 10
        assert config.semantic_top_k == 5

    def test_custom_values(self):
        config = MemoryConfig(
            working_capacity=50,
            episodic_compression_threshold=20,
            semantic_top_k=10,
        )
        assert config.working_capacity == 50
        assert config.episodic_compression_threshold == 20
        assert config.semantic_top_k == 10


class TestToolConfig:
    """Test ToolConfig dataclass."""

    def test_defaults(self):
        config = ToolConfig()
        assert config.max_retries == 2
        assert config.parallel_enabled is True
        assert config.timeout == 60.0

    def test_custom_values(self):
        config = ToolConfig(max_retries=5, parallel_enabled=False, timeout=120.0)
        assert config.max_retries == 5
        assert config.parallel_enabled is False
        assert config.timeout == 120.0


class TestMiddlewareConfig:
    """Test MiddlewareConfig dataclass."""

    def test_defaults(self):
        config = MiddlewareConfig()
        assert "summarization" in config.enabled
        assert "memory_inject" in config.enabled
        assert "loop_detection" in config.enabled
        assert "clarification" in config.enabled
        assert config.summarize is True
        assert config.memory_inject is True

    def test_custom_values(self):
        config = MiddlewareConfig(
            enabled=["summarization"],
            summarize=True,
            memory_inject=False,
        )
        assert config.enabled == ["summarization"]
        assert config.memory_inject is False


class TestAgentConfig:
    """Test AgentConfig dataclass (config module)."""

    def test_defaults(self):
        config = AgentConfig()
        assert config.name == "suyi"
        assert config.max_iterations == 25
        assert "max_turns" in config.budget

    def test_custom_values(self):
        config = AgentConfig(name="custom-agent", max_iterations=50)
        assert config.name == "custom-agent"
        assert config.max_iterations == 50


class TestEvolutionConfig:
    """Test EvolutionConfig dataclass."""

    def test_defaults(self):
        config = EvolutionConfig()
        assert config.learning_enabled is False
        assert config.eval_interval == 50

    def test_custom_values(self):
        config = EvolutionConfig(learning_enabled=True, eval_interval=100)
        assert config.learning_enabled is True
        assert config.eval_interval == 100


class TestSuyiConfig:
    """Test top-level SuyiConfig."""

    def test_defaults(self):
        config = SuyiConfig()
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.memory, MemoryConfig)
        assert isinstance(config.tools, ToolConfig)
        assert isinstance(config.middleware, MiddlewareConfig)
        assert isinstance(config.agent, AgentConfig)
        assert isinstance(config.evolution, EvolutionConfig)

    def test_custom_llm(self):
        config = SuyiConfig(
            llm=LLMConfig(provider="anthropic", model="claude-sonnet-4-20250514")
        )
        assert config.llm.provider == "anthropic"
        assert config.llm.model == "claude-sonnet-4-20250514"

    def test_to_dict(self):
        config = SuyiConfig()
        d = config.to_dict()
        assert "llm" in d
        assert "memory" in d
        assert "tools" in d
        assert "middleware" in d
        assert "agent" in d
        assert "evolution" in d
        assert d["llm"]["provider"] == "openai"
        assert d["llm"]["model"] == "gpt-4o"
        assert d["agent"]["name"] == "suyi"

    def test_to_dict_round_trip(self):
        """Config → dict → config should preserve values."""
        original = SuyiConfig(
            llm=LLMConfig(provider="deepseek", model="deepseek-chat", temperature=0.5),
            memory=MemoryConfig(working_capacity=30),
            agent=AgentConfig(name="test-agent", max_iterations=15),
        )
        d = original.to_dict()
        restored = load_config_from_dict(d)

        assert restored.llm.provider == "deepseek"
        assert restored.llm.model == "deepseek-chat"
        assert restored.llm.temperature == 0.5
        assert restored.memory.working_capacity == 30
        assert restored.agent.name == "test-agent"
        assert restored.agent.max_iterations == 15


# ═══════════════════════════════════════════════════════════════
#  Loader Tests
# ═══════════════════════════════════════════════════════════════


class TestLoadConfigFromDict:
    """Test load_config_from_dict."""

    def test_empty_dict(self):
        """Empty dict should return defaults."""
        config = load_config_from_dict({})
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4o"

    def test_partial_dict(self):
        """Only specified sections should be customized."""
        config = load_config_from_dict({
            "llm": {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
        })
        assert config.llm.provider == "anthropic"
        assert config.llm.model == "claude-sonnet-4-20250514"
        # Unspecified sections should use defaults
        assert config.memory.working_capacity == 20

    def test_full_dict(self):
        config = load_config_from_dict({
            "llm": {
                "provider": "deepseek",
                "api_key": "sk-ds",
                "model": "deepseek-chat",
                "temperature": 0.3,
                "max_tokens": 2048,
            },
            "memory": {
                "working_capacity": 50,
                "episodic_compression_threshold": 15,
                "semantic_top_k": 8,
            },
            "tools": {"max_retries": 5, "parallel_enabled": False, "timeout": 90.0},
            "middleware": {
                "enabled": ["summarization"],
                "summarize": True,
                "memory_inject": False,
            },
            "agent": {"name": "custom", "max_iterations": 10},
            "evolution": {"learning_enabled": True, "eval_interval": 25},
        })
        assert config.llm.provider == "deepseek"
        assert config.llm.api_key == "sk-ds"
        assert config.memory.working_capacity == 50
        assert config.tools.max_retries == 5
        assert config.tools.parallel_enabled is False
        assert config.middleware.enabled == ["summarization"]
        assert config.agent.name == "custom"
        assert config.evolution.learning_enabled is True

    def test_unknown_keys_ignored(self):
        """Unknown keys should be silently ignored."""
        config = load_config_from_dict({
            "llm": {"provider": "openai", "unknown_field": "value"},
            "unknown_section": {"foo": "bar"},
        })
        assert config.llm.provider == "openai"


class TestLoadConfigFromFile:
    """Test load_config from files."""

    def test_load_yaml_file(self):
        """Test loading a YAML config file."""
        yaml_content = """
llm:
  provider: anthropic
  api_key: sk-ant-test
  model: claude-sonnet-4-20250514
  temperature: 0.5
  max_tokens: 8192
memory:
  working_capacity: 40
  episodic_compression_threshold: 15
  semantic_top_k: 8
agent:
  name: yaml-agent
  max_iterations: 30
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(yaml_content)
            f.flush()
            path = f.name

        try:
            config = load_config(path)
            assert config.llm.provider == "anthropic"
            assert config.llm.model == "claude-sonnet-4-20250514"
            assert config.llm.temperature == 0.5
            assert config.llm.max_tokens == 8192
            assert config.memory.working_capacity == 40
            assert config.agent.name == "yaml-agent"
            assert config.agent.max_iterations == 30
        finally:
            os.unlink(path)

    def test_load_json_file(self):
        """Test loading a JSON config file."""
        json_content = json.dumps({
            "llm": {
                "provider": "deepseek",
                "api_key": "sk-ds",
                "model": "deepseek-chat",
            },
            "evolution": {"learning_enabled": True, "eval_interval": 10},
        })
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(json_content)
            f.flush()
            path = f.name

        try:
            config = load_config(path)
            assert config.llm.provider == "deepseek"
            assert config.llm.api_key == "sk-ds"
            assert config.evolution.learning_enabled is True
            assert config.evolution.eval_interval == 10
        finally:
            os.unlink(path)

    def test_load_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config("/nonexistent/path/config.yaml")

    def test_load_default_yaml(self):
        """Test loading the packaged default.yaml."""
        default_path = Path(__file__).parent.parent / "suyi" / "config" / "default.yaml"
        if default_path.exists():
            config = load_config(str(default_path))
            assert config.llm.provider == "openai"
            assert config.llm.model == "gpt-4o"
            assert config.llm.temperature == 0.7
            assert config.memory.working_capacity == 20
            assert config.agent.name == "suyi"
            assert config.evolution.learning_enabled is False


class TestGetDefaultConfig:
    """Test get_default_config."""

    def test_returns_suyi_config(self):
        config = get_default_config()
        assert isinstance(config, SuyiConfig)

    def test_defaults_match(self):
        config = get_default_config()
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4o"
        assert config.memory.working_capacity == 20
        assert config.tools.max_retries == 2
        assert config.agent.name == "suyi"
        assert config.evolution.learning_enabled is False

    def test_returns_fresh_instance(self):
        """Each call should return a new instance."""
        c1 = get_default_config()
        c2 = get_default_config()
        assert c1 is not c2
        c1.llm.model = "modified"
        assert c2.llm.model == "gpt-4o"  # Unchanged


class TestSaveConfig:
    """Test save_config."""

    def test_save_json(self):
        config = SuyiConfig(llm=LLMConfig(provider="anthropic", model="claude-sonnet-4-20250514"))
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            path = f.name

        try:
            save_config(config, path, format="json")
            # Reload and verify
            loaded = load_config(path)
            assert loaded.llm.provider == "anthropic"
            assert loaded.llm.model == "claude-sonnet-4-20250514"
        finally:
            os.unlink(path)

    def test_save_yaml(self):
        config = SuyiConfig(
            llm=LLMConfig(provider="deepseek", model="deepseek-chat"),
            memory=MemoryConfig(working_capacity=42),
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            path = f.name

        try:
            save_config(config, path, format="yaml")
            # Reload and verify
            loaded = load_config(path)
            assert loaded.llm.provider == "deepseek"
            assert loaded.llm.model == "deepseek-chat"
            assert loaded.memory.working_capacity == 42
        finally:
            os.unlink(path)

    def test_save_unsupported_format(self):
        config = SuyiConfig()
        with pytest.raises(ValueError, match="Unsupported format"):
            save_config(config, "/tmp/test.toml", format="toml")


# ═══════════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestConfigIntegration:
    """Integration tests for config + LLM factory."""

    def test_config_to_llm(self):
        """Test creating an LLM from a config."""
        from suyi.llm import create_llm_from_config

        config = LLMConfig(
            provider="openai",
            api_key="sk-test",
            model="gpt-4o-mini",
            temperature=0.3,
        )
        llm = create_llm_from_config(config)
        assert llm.api_key == "sk-test"
        assert llm.model == "gpt-4o-mini"
        assert llm.temperature == 0.3

    def test_full_config_to_llm(self):
        """Test creating an LLM from a full SuyiConfig."""
        from suyi.llm import create_llm_from_config

        suyiconfig = SuyiConfig(
            llm=LLMConfig(
                provider="anthropic",
                api_key="sk-ant-test",
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
            )
        )
        llm = create_llm_from_config(suyiconfig.llm)
        assert llm.api_key == "sk-ant-test"
        assert llm.model == "claude-sonnet-4-20250514"
        assert llm.max_tokens == 2048
