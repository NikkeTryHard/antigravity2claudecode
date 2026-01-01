"""
Routing rules engine.

Matches requests to providers based on configurable rules.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from a2c.server.config import get_settings

logger = logging.getLogger(__name__)


class AgentType(str, Enum):
    """Supported agent types for routing."""

    DEFAULT = "default"
    BACKGROUND = "background"
    THINK = "think"
    LONG_CONTEXT = "long_context"
    WEBSEARCH = "websearch"
    CODE = "code"


@dataclass
class RoutingRule:
    """A single routing rule."""

    name: str
    provider: str
    priority: int = 0

    # Match conditions (all must match)
    agent_type: str | None = None
    model_pattern: str | None = None
    thinking_enabled: bool | None = None
    min_context_tokens: int | None = None
    max_context_tokens: int | None = None

    # Fallback provider if primary fails
    fallback_provider: str | None = None

    def matches(
        self,
        request: dict[str, Any],
        agent_type: str | None = None,
        context_tokens: int = 0,
    ) -> bool:
        """
        Check if this rule matches the request.

        Args:
            request: Anthropic-format request
            agent_type: Agent type from header
            context_tokens: Estimated context tokens

        Returns:
            True if all conditions match
        """
        # Check agent type
        if self.agent_type and self.agent_type != (agent_type or "default"):
            return False

        # Check model pattern
        if self.model_pattern:
            model = request.get("model", "")
            if not re.match(self.model_pattern, model, re.IGNORECASE):
                return False

        # Check thinking enabled
        if self.thinking_enabled is not None:
            thinking = request.get("thinking", {})
            is_thinking = False

            if isinstance(thinking, dict):
                is_thinking = thinking.get("type") == "enabled"
            elif thinking is True:
                is_thinking = True

            if self.thinking_enabled != is_thinking:
                return False

        # Check context tokens
        if self.min_context_tokens is not None and context_tokens < self.min_context_tokens:
            return False

        if self.max_context_tokens is not None and context_tokens > self.max_context_tokens:
            return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert rule to dictionary."""
        return {
            "name": self.name,
            "provider": self.provider,
            "priority": self.priority,
            "conditions": {
                "agent_type": self.agent_type,
                "model_pattern": self.model_pattern,
                "thinking_enabled": self.thinking_enabled,
                "min_context_tokens": self.min_context_tokens,
                "max_context_tokens": self.max_context_tokens,
            },
            "fallback_provider": self.fallback_provider,
        }


@dataclass
class Router:
    """
    Request router with configurable rules.

    Routes requests to providers based on:
    - Agent type (from header or detected)
    - Model name patterns
    - Thinking configuration
    - Context size
    """

    rules: list[RoutingRule] = field(default_factory=list)
    default_provider: str = "anthropic"

    def add_rule(self, rule: RoutingRule) -> None:
        """Add a routing rule."""
        self.rules.append(rule)
        # Sort by priority (higher first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name."""
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                del self.rules[i]
                return True
        return False

    def get_matching_rule(
        self,
        request: dict[str, Any],
        agent_type: str | None = None,
        context_tokens: int = 0,
    ) -> str | None:
        """
        Get the name of the matching rule.

        Args:
            request: Anthropic-format request
            agent_type: Agent type from header
            context_tokens: Estimated context tokens

        Returns:
            Rule name or None if no match
        """
        for rule in self.rules:
            if rule.matches(request, agent_type, context_tokens):
                return rule.name
        return None

    def select_provider(
        self,
        request: dict[str, Any],
        agent_type: str | None = None,
        context_tokens: int = 0,
    ) -> str:
        """
        Select provider for a request.

        Args:
            request: Anthropic-format request
            agent_type: Agent type from header
            context_tokens: Estimated context tokens

        Returns:
            Provider name
        """
        for rule in self.rules:
            if rule.matches(request, agent_type, context_tokens):
                logger.debug(f"Matched rule '{rule.name}' -> provider '{rule.provider}'")
                return rule.provider

        logger.debug(f"No rule matched, using default provider '{self.default_provider}'")
        return self.default_provider

    def to_dict(self) -> dict[str, Any]:
        """Convert router config to dictionary."""
        return {
            "default_provider": self.default_provider,
            "rules": [r.to_dict() for r in self.rules],
            "total_rules": len(self.rules),
        }


def create_default_router() -> Router:
    """
    Create router with default rules based on settings.

    Returns:
        Configured router instance
    """
    settings = get_settings()
    router = Router(default_provider=settings.routing.default_provider)

    # Rule 1: Extended thinking requests
    router.add_rule(
        RoutingRule(
            name="thinking-requests",
            provider=settings.routing.think_provider,
            priority=100,
            thinking_enabled=True,
        )
    )

    # Rule 2: Long context requests
    router.add_rule(
        RoutingRule(
            name="long-context",
            provider=settings.routing.long_context_provider,
            priority=90,
            min_context_tokens=settings.routing.long_context_threshold,
        )
    )

    # Rule 3: Web search agent
    router.add_rule(
        RoutingRule(
            name="websearch",
            provider=settings.routing.websearch_provider,
            priority=80,
            agent_type="websearch",
        )
    )

    # Rule 4: Background agents
    router.add_rule(
        RoutingRule(
            name="background",
            provider=settings.routing.background_provider,
            priority=70,
            agent_type="background",
        )
    )

    # Rule 5: Think agent type
    router.add_rule(
        RoutingRule(
            name="think-agent",
            provider=settings.routing.think_provider,
            priority=60,
            agent_type="think",
        )
    )

    # Rule 6: Opus models to Antigravity (for thinking support)
    router.add_rule(
        RoutingRule(
            name="opus-models",
            provider="antigravity",
            priority=50,
            model_pattern=r".*opus.*",
        )
    )

    return router


# Global router instance
_router: Router | None = None


def get_router() -> Router:
    """Get the global router instance."""
    global _router
    if _router is None:
        _router = create_default_router()
    return _router


def reset_router() -> None:
    """Reset the global router (for testing)."""
    global _router
    _router = None
