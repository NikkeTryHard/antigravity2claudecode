"""
TDD Tests for YAML configuration loading.

These tests are written FIRST following TDD methodology.
The implementation will be written to make these tests pass.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

# These imports will fail until we implement the code
from a2c.router.config import (
    ConfigValidationError,
    RoutingConfig,
    load_routing_config,
    validate_routing_config,
)


class TestLoadRoutingConfig:
    """Tests for loading routing configuration from YAML."""

    def test_load_yaml_config_file(self, tmp_path: Path):
        """Should load valid YAML config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
routing:
  default_provider: anthropic
  rules:
    - name: test-rule
      provider: antigravity
      match:
        agent_type: background
""")

        config = load_routing_config(config_file)

        assert config.default_provider == "anthropic"
        assert len(config.rules) == 1
        assert config.rules[0].name == "test-rule"

    def test_load_yaml_with_multiple_rules(self, tmp_path: Path):
        """Should load config with multiple routing rules."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
routing:
  default_provider: anthropic
  rules:
    - name: thinking-requests
      provider: antigravity
      priority: 100
      match:
        thinking: enabled

    - name: long-context
      provider: gemini
      priority: 90
      match:
        min_context_tokens: 100000

    - name: background
      provider: antigravity
      priority: 80
      match:
        agent_type: background
""")

        config = load_routing_config(config_file)

        assert len(config.rules) == 3
        # Rules should be sorted by priority
        assert config.rules[0].name == "thinking-requests"
        assert config.rules[0].priority == 100
        assert config.rules[1].name == "long-context"
        assert config.rules[2].name == "background"

    def test_load_yaml_with_fallback_providers(self, tmp_path: Path):
        """Should load rules with fallback providers."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
routing:
  default_provider: anthropic
  rules:
    - name: primary-rule
      provider: antigravity
      fallback_provider: anthropic
      match:
        model_pattern: ".*opus.*"
""")

        config = load_routing_config(config_file)

        assert config.rules[0].fallback_provider == "anthropic"

    def test_load_yaml_file_not_found(self):
        """Should raise error for missing config file."""
        with pytest.raises(FileNotFoundError):
            load_routing_config(Path("/nonexistent/config.yaml"))

    def test_load_yaml_invalid_syntax(self, tmp_path: Path):
        """Should raise error for invalid YAML syntax."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
routing:
  rules:
    - name: test
      provider: [invalid yaml
""")

        with pytest.raises(yaml.YAMLError):
            load_routing_config(config_file)

    def test_load_yaml_empty_file(self, tmp_path: Path):
        """Should return default config for empty file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        config = load_routing_config(config_file)

        assert config.default_provider == "anthropic"
        assert len(config.rules) == 0

    def test_load_yaml_missing_routing_section(self, tmp_path: Path):
        """Should return default config if routing section missing."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
server:
  port: 8080
""")

        config = load_routing_config(config_file)

        assert config.default_provider == "anthropic"


class TestValidateRoutingConfig:
    """Tests for routing config validation."""

    def test_validate_valid_config(self):
        """Should pass validation for valid config."""
        config_dict = {
            "default_provider": "anthropic",
            "rules": [
                {
                    "name": "test-rule",
                    "provider": "antigravity",
                    "match": {"agent_type": "background"},
                }
            ],
        }

        # Should not raise
        config = validate_routing_config(config_dict)
        assert config.default_provider == "anthropic"

    def test_validate_missing_rule_name(self):
        """Should fail validation if rule missing name."""
        config_dict = {
            "rules": [
                {
                    "provider": "antigravity",
                    "match": {"agent_type": "background"},
                }
            ],
        }

        with pytest.raises(ConfigValidationError, match="name"):
            validate_routing_config(config_dict)

    def test_validate_missing_rule_provider(self):
        """Should fail validation if rule missing provider."""
        config_dict = {
            "rules": [
                {
                    "name": "test-rule",
                    "match": {"agent_type": "background"},
                }
            ],
        }

        with pytest.raises(ConfigValidationError, match="provider"):
            validate_routing_config(config_dict)

    def test_validate_duplicate_rule_names(self):
        """Should fail validation for duplicate rule names."""
        config_dict = {
            "rules": [
                {"name": "same-name", "provider": "a", "match": {}},
                {"name": "same-name", "provider": "b", "match": {}},
            ],
        }

        with pytest.raises(ConfigValidationError, match="duplicate"):
            validate_routing_config(config_dict)

    def test_validate_invalid_match_condition(self):
        """Should fail validation for unknown match condition."""
        config_dict = {
            "rules": [
                {
                    "name": "test",
                    "provider": "a",
                    "match": {"unknown_condition": "value"},
                }
            ],
        }

        with pytest.raises(ConfigValidationError, match="unknown"):
            validate_routing_config(config_dict)

    def test_validate_invalid_priority_type(self):
        """Should fail validation for non-integer priority."""
        config_dict = {
            "rules": [
                {
                    "name": "test",
                    "provider": "a",
                    "priority": "high",  # Should be int
                    "match": {},
                }
            ],
        }

        with pytest.raises(ConfigValidationError, match="priority"):
            validate_routing_config(config_dict)


class TestRoutingConfig:
    """Tests for RoutingConfig dataclass."""

    def test_routing_config_defaults(self):
        """Should have sensible defaults."""
        config = RoutingConfig()

        assert config.default_provider == "anthropic"
        assert config.rules == []
        assert config.long_context_threshold == 100000

    def test_routing_config_to_router(self):
        """Should convert to Router instance."""
        config = RoutingConfig(
            default_provider="anthropic",
            rules=[],
        )

        router = config.to_router()

        assert router.default_provider == "anthropic"

    def test_routing_config_from_dict(self):
        """Should create from dictionary."""
        config = RoutingConfig.from_dict(
            {
                "default_provider": "gemini",
                "long_context_threshold": 50000,
                "rules": [
                    {
                        "name": "test",
                        "provider": "anthropic",
                        "match": {},
                    }
                ],
            }
        )

        assert config.default_provider == "gemini"
        assert config.long_context_threshold == 50000
        assert len(config.rules) == 1

    def test_routing_config_to_dict(self):
        """Should convert to dictionary."""
        config = RoutingConfig(
            default_provider="anthropic",
            long_context_threshold=100000,
        )

        d = config.to_dict()

        assert d["default_provider"] == "anthropic"
        assert d["long_context_threshold"] == 100000
        assert "rules" in d


class TestConfigHotReload:
    """Tests for config hot-reloading."""

    def test_config_watcher_detects_changes(self, tmp_path: Path):
        """Config watcher should detect file changes."""
        # This test is for future implementation
        pytest.skip("Hot reload not yet implemented")

    def test_config_reload_updates_router(self, tmp_path: Path):
        """Reloading config should update router rules."""
        # This test is for future implementation
        pytest.skip("Hot reload not yet implemented")
