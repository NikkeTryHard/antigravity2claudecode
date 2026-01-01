"""
YAML configuration loading for routing rules.

Supports:
- Loading routing rules from YAML files
- Validation of rule structure
- Conversion to Router instances
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from a2c.router.rules import Router, RoutingRule


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    pass


# Valid match conditions
VALID_MATCH_CONDITIONS = {
    "agent_type",
    "model_pattern",
    "thinking",
    "min_context_tokens",
    "max_context_tokens",
}


@dataclass
class RuleConfig:
    """Configuration for a single routing rule."""

    name: str
    provider: str
    priority: int = 0
    fallback_provider: str | None = None
    match: dict[str, Any] = field(default_factory=dict)

    def to_routing_rule(self) -> RoutingRule:
        """Convert to RoutingRule instance."""
        return RoutingRule(
            name=self.name,
            provider=self.provider,
            priority=self.priority,
            fallback_provider=self.fallback_provider,
            agent_type=self.match.get("agent_type"),
            model_pattern=self.match.get("model_pattern"),
            thinking_enabled=self._parse_thinking(self.match.get("thinking")),
            min_context_tokens=self.match.get("min_context_tokens"),
            max_context_tokens=self.match.get("max_context_tokens"),
        )

    def _parse_thinking(self, value: Any) -> bool | None:
        """Parse thinking match condition."""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "enabled"
        return None


@dataclass
class RoutingConfig:
    """Complete routing configuration."""

    default_provider: str = "anthropic"
    long_context_threshold: int = 100000
    rules: list[RuleConfig] = field(default_factory=list)

    def to_router(self) -> Router:
        """Convert to Router instance."""
        router = Router(default_provider=self.default_provider)

        for rule_config in self.rules:
            router.add_rule(rule_config.to_routing_rule())

        return router

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "default_provider": self.default_provider,
            "long_context_threshold": self.long_context_threshold,
            "rules": [
                {
                    "name": r.name,
                    "provider": r.provider,
                    "priority": r.priority,
                    "fallback_provider": r.fallback_provider,
                    "match": r.match,
                }
                for r in self.rules
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoutingConfig":
        """Create from dictionary."""
        rules = []
        for rule_data in data.get("rules", []):
            rules.append(
                RuleConfig(
                    name=rule_data.get("name", ""),
                    provider=rule_data.get("provider", ""),
                    priority=rule_data.get("priority", 0),
                    fallback_provider=rule_data.get("fallback_provider"),
                    match=rule_data.get("match", {}),
                )
            )

        # Sort rules by priority (highest first)
        rules.sort(key=lambda r: r.priority, reverse=True)

        return cls(
            default_provider=data.get("default_provider", "anthropic"),
            long_context_threshold=data.get("long_context_threshold", 100000),
            rules=rules,
        )


def validate_routing_config(config_dict: dict[str, Any]) -> RoutingConfig:
    """
    Validate routing configuration dictionary.

    Args:
        config_dict: Raw configuration dictionary

    Returns:
        Validated RoutingConfig

    Raises:
        ConfigValidationError: If validation fails
    """
    rules = config_dict.get("rules", [])
    seen_names: set[str] = set()

    for i, rule in enumerate(rules):
        # Check required fields
        if "name" not in rule or not rule["name"]:
            raise ConfigValidationError(f"Rule {i}: missing required field 'name'")

        if "provider" not in rule or not rule["provider"]:
            raise ConfigValidationError(f"Rule {i}: missing required field 'provider'")

        # Check for duplicate names
        name = rule["name"]
        if name in seen_names:
            raise ConfigValidationError(f"Rule '{name}': duplicate rule name")
        seen_names.add(name)

        # Validate priority type
        if "priority" in rule and not isinstance(rule["priority"], int):
            raise ConfigValidationError(
                f"Rule '{name}': priority must be an integer, got {type(rule['priority']).__name__}"
            )

        # Validate match conditions
        match = rule.get("match", {})
        for condition in match:
            if condition not in VALID_MATCH_CONDITIONS:
                raise ConfigValidationError(
                    f"Rule '{name}': unknown match condition '{condition}'. "
                    f"Valid conditions: {VALID_MATCH_CONDITIONS}"
                )

    return RoutingConfig.from_dict(config_dict)


def load_routing_config(config_path: Path) -> RoutingConfig:
    """
    Load routing configuration from YAML file.

    Args:
        config_path: Path to YAML config file

    Returns:
        Loaded and validated RoutingConfig

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML syntax is invalid
        ConfigValidationError: If config validation fails
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        content = f.read()

    if not content.strip():
        return RoutingConfig()

    data = yaml.safe_load(content)

    if data is None:
        return RoutingConfig()

    routing_data = data.get("routing", {})

    if not routing_data:
        return RoutingConfig()

    return validate_routing_config(routing_data)
