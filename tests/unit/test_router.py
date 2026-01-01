"""
Tests for the routing system.

Tests cover:
1. Routing rule matching
2. Provider selection
3. Default routing behavior
"""

import pytest

from a2c.router import (
    AgentType,
    Router,
    RoutingRule,
    create_default_router,
    get_router,
    reset_router,
)


class TestRoutingRule:
    """Tests for RoutingRule matching logic."""

    def test_matches_agent_type(self):
        """Rule should match on agent type."""
        rule = RoutingRule(
            name="background-rule",
            provider="antigravity",
            agent_type="background",
        )

        # Should match
        assert rule.matches({}, agent_type="background") is True

        # Should not match
        assert rule.matches({}, agent_type="default") is False
        assert rule.matches({}, agent_type=None) is False

    def test_matches_model_pattern(self):
        """Rule should match on model pattern."""
        rule = RoutingRule(
            name="opus-rule",
            provider="antigravity",
            model_pattern=r".*opus.*",
        )

        # Should match
        assert rule.matches({"model": "claude-opus-4-5"}) is True
        assert rule.matches({"model": "claude-opus-4-5-20251101"}) is True

        # Should not match
        assert rule.matches({"model": "claude-sonnet-4-5"}) is False
        assert rule.matches({"model": "gpt-4"}) is False

    def test_matches_thinking_enabled(self):
        """Rule should match on thinking enabled."""
        rule = RoutingRule(
            name="thinking-rule",
            provider="antigravity",
            thinking_enabled=True,
        )

        # Should match
        assert rule.matches({"thinking": {"type": "enabled"}}) is True
        assert rule.matches({"thinking": True}) is True

        # Should not match
        assert rule.matches({"thinking": {"type": "disabled"}}) is False
        assert rule.matches({"thinking": False}) is False
        assert rule.matches({}) is False

    def test_matches_context_tokens(self):
        """Rule should match on context token range."""
        rule = RoutingRule(
            name="long-context-rule",
            provider="gemini",
            min_context_tokens=100000,
        )

        # Should match
        assert rule.matches({}, context_tokens=150000) is True
        assert rule.matches({}, context_tokens=100000) is True

        # Should not match
        assert rule.matches({}, context_tokens=50000) is False
        assert rule.matches({}, context_tokens=0) is False

    def test_matches_multiple_conditions(self):
        """Rule should require all conditions to match."""
        rule = RoutingRule(
            name="specific-rule",
            provider="antigravity",
            agent_type="think",
            thinking_enabled=True,
        )

        # Should match (both conditions)
        assert rule.matches({"thinking": {"type": "enabled"}}, agent_type="think") is True

        # Should not match (only one condition)
        assert rule.matches({"thinking": {"type": "enabled"}}, agent_type="default") is False
        assert rule.matches({}, agent_type="think") is False

    def test_to_dict(self):
        """Rule should convert to dictionary."""
        rule = RoutingRule(
            name="test-rule",
            provider="anthropic",
            priority=50,
            agent_type="background",
            model_pattern=r".*opus.*",
        )

        d = rule.to_dict()
        assert d["name"] == "test-rule"
        assert d["provider"] == "anthropic"
        assert d["priority"] == 50
        assert d["conditions"]["agent_type"] == "background"


class TestRouter:
    """Tests for Router class."""

    def test_add_rule_sorts_by_priority(self):
        """Rules should be sorted by priority (highest first)."""
        router = Router()

        router.add_rule(RoutingRule(name="low", provider="a", priority=10))
        router.add_rule(RoutingRule(name="high", provider="b", priority=100))
        router.add_rule(RoutingRule(name="mid", provider="c", priority=50))

        assert router.rules[0].name == "high"
        assert router.rules[1].name == "mid"
        assert router.rules[2].name == "low"

    def test_select_provider_matches_first_rule(self):
        """Should return provider from first matching rule."""
        router = Router(default_provider="default")

        router.add_rule(
            RoutingRule(
                name="thinking",
                provider="antigravity",
                priority=100,
                thinking_enabled=True,
            )
        )
        router.add_rule(
            RoutingRule(
                name="opus",
                provider="opus-provider",
                priority=50,
                model_pattern=r".*opus.*",
            )
        )

        # Should match thinking rule first
        result = router.select_provider(
            {"model": "claude-opus-4-5", "thinking": {"type": "enabled"}}
        )
        assert result == "antigravity"

    def test_select_provider_uses_default(self):
        """Should return default provider if no rules match."""
        router = Router(default_provider="anthropic")

        router.add_rule(
            RoutingRule(
                name="background",
                provider="antigravity",
                agent_type="background",
            )
        )

        # No matching rule
        result = router.select_provider({"model": "claude-sonnet-4-5"})
        assert result == "anthropic"

    def test_remove_rule(self):
        """Should remove rule by name."""
        router = Router()
        router.add_rule(RoutingRule(name="test", provider="a"))

        assert len(router.rules) == 1
        assert router.remove_rule("test") is True
        assert len(router.rules) == 0
        assert router.remove_rule("nonexistent") is False

    def test_get_matching_rule(self):
        """Should return matching rule name."""
        router = Router()

        router.add_rule(
            RoutingRule(
                name="background",
                provider="antigravity",
                agent_type="background",
            )
        )

        assert router.get_matching_rule({}, agent_type="background") == "background"
        assert router.get_matching_rule({}, agent_type="default") is None

    def test_to_dict(self):
        """Router should convert to dictionary."""
        router = Router(default_provider="anthropic")
        router.add_rule(RoutingRule(name="test", provider="a"))

        d = router.to_dict()
        assert d["default_provider"] == "anthropic"
        assert d["total_rules"] == 1
        assert len(d["rules"]) == 1


class TestDefaultRouter:
    """Tests for default router configuration."""

    def setup_method(self):
        """Reset router before each test."""
        reset_router()

    def test_create_default_router(self):
        """Should create router with default rules."""
        router = create_default_router()

        assert len(router.rules) > 0
        assert router.default_provider == "anthropic"

    def test_default_router_has_thinking_rule(self):
        """Default router should have thinking rule."""
        router = create_default_router()

        # Find thinking rule
        thinking_rules = [r for r in router.rules if r.thinking_enabled is True]
        assert len(thinking_rules) > 0

    def test_default_router_has_agent_type_rules(self):
        """Default router should have agent type rules."""
        router = create_default_router()

        # Find agent type rules
        agent_rules = [r for r in router.rules if r.agent_type is not None]
        assert len(agent_rules) >= 3  # background, think, websearch

    def test_get_router_singleton(self):
        """get_router should return same instance."""
        router1 = get_router()
        router2 = get_router()

        assert router1 is router2

    def test_reset_router(self):
        """reset_router should clear singleton."""
        router1 = get_router()
        reset_router()
        router2 = get_router()

        assert router1 is not router2


class TestAgentType:
    """Tests for AgentType enum."""

    def test_agent_type_values(self):
        """Should have expected agent types."""
        assert AgentType.DEFAULT.value == "default"
        assert AgentType.BACKGROUND.value == "background"
        assert AgentType.THINK.value == "think"
        assert AgentType.LONG_CONTEXT.value == "long_context"
        assert AgentType.WEBSEARCH.value == "websearch"
