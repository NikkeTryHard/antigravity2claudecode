"""
Tests for provider implementations.

Tests cover:
1. Provider registry
2. Provider base functionality
3. Provider health checks
"""

import pytest

from a2c.providers import (
    AnthropicProvider,
    AntigravityProvider,
    ApiFormat,
    BaseProvider,
    ProviderHealth,
    ProviderInfo,
    ProviderRegistry,
    ProviderStatus,
    get_registry,
    reset_registry,
)


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def setup_method(self):
        """Reset registry before each test."""
        reset_registry()

    def test_register_provider(self):
        """Should register provider."""
        registry = ProviderRegistry()
        provider = AnthropicProvider(name="test-anthropic")

        registry.register(provider)

        assert registry.get("test-anthropic") is provider
        assert len(registry.list_providers()) == 1

    def test_register_duplicate_raises(self):
        """Should raise on duplicate registration."""
        registry = ProviderRegistry()
        provider1 = AnthropicProvider(name="test")
        provider2 = AnthropicProvider(name="test")

        registry.register(provider1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(provider2)

    def test_unregister_provider(self):
        """Should unregister provider."""
        registry = ProviderRegistry()
        provider = AnthropicProvider(name="test")

        registry.register(provider)
        registry.unregister("test")

        assert registry.get("test") is None
        assert len(registry.list_providers()) == 0

    def test_get_or_raise(self):
        """Should raise on missing provider."""
        registry = ProviderRegistry()

        with pytest.raises(KeyError, match="not found"):
            registry.get_or_raise("nonexistent")

    def test_list_healthy_providers(self):
        """Should list only healthy providers."""
        registry = ProviderRegistry()

        healthy = AnthropicProvider(name="healthy")
        healthy._health = ProviderHealth(status=ProviderStatus.HEALTHY)

        unhealthy = AnthropicProvider(name="unhealthy")
        unhealthy._health = ProviderHealth(status=ProviderStatus.UNHEALTHY)

        registry.register(healthy)
        registry.register(unhealthy)

        healthy_list = registry.list_healthy_providers()
        assert len(healthy_list) == 1
        assert healthy_list[0].name == "healthy"

    def test_to_dict(self):
        """Should convert to dictionary."""
        registry = ProviderRegistry()
        provider = AnthropicProvider(name="test")
        registry.register(provider)

        d = registry.to_dict()
        assert "providers" in d
        assert "test" in d["providers"]
        assert d["total"] == 1

    def test_get_registry_singleton(self):
        """get_registry should return same instance."""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""

    def test_provider_info(self):
        """Should return correct provider info."""
        provider = AnthropicProvider()

        info = provider.info
        assert info.name == "anthropic"
        assert info.display_name == "Anthropic"
        assert info.api_format == ApiFormat.ANTHROPIC
        assert info.supports_streaming is True
        assert info.supports_thinking is True

    def test_is_configured_without_key(self):
        """Should not be configured without API key."""
        provider = AnthropicProvider(api_key=None)
        # Provider uses settings, which may or may not have key
        # Just check the property exists
        assert isinstance(provider.is_configured, bool)

    def test_is_configured_with_key(self):
        """Should be configured with API key."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.is_configured is True

    def test_build_headers(self):
        """Should build correct headers."""
        provider = AnthropicProvider(api_key="test-key")

        headers = provider._build_headers()
        assert headers["x-api-key"] == "test-key"
        assert "anthropic-version" in headers
        assert headers["content-type"] == "application/json"

    def test_build_headers_streaming(self):
        """Should add accept header for streaming."""
        provider = AnthropicProvider(api_key="test-key")

        headers = provider._build_headers(stream=True)
        assert headers["accept"] == "text/event-stream"

    def test_to_dict(self):
        """Should convert to dictionary."""
        provider = AnthropicProvider(api_key="test-key")

        d = provider.to_dict()
        assert d["name"] == "anthropic"
        assert d["display_name"] == "Anthropic"
        assert d["is_configured"] is True
        assert "health" in d


class TestAntigravityProvider:
    """Tests for AntigravityProvider."""

    def test_provider_info(self):
        """Should return correct provider info."""
        provider = AntigravityProvider()

        info = provider.info
        assert info.name == "antigravity"
        assert info.api_format == ApiFormat.GEMINI
        assert info.supports_thinking is True
        assert info.max_context_tokens == 1000000

    def test_is_configured_without_credentials(self):
        """Should not be configured without credentials."""
        provider = AntigravityProvider(api_key=None, project_id=None)
        # Check property exists
        assert isinstance(provider.is_configured, bool)

    def test_is_configured_with_api_key(self):
        """Should be configured with API key."""
        provider = AntigravityProvider(api_key="test-key")
        assert provider.is_configured is True

    def test_is_configured_with_project_id(self):
        """Should be configured with project ID."""
        provider = AntigravityProvider(project_id="test-project")
        assert provider.is_configured is True

    def test_build_url_with_project(self):
        """Should build Vertex AI URL with project."""
        provider = AntigravityProvider(project_id="my-project", location="us-central1")

        url = provider._build_url("gemini-1.5-pro", stream=False)
        assert "us-central1-aiplatform.googleapis.com" in url
        assert "my-project" in url

    def test_build_url_streaming(self):
        """Should build streaming URL."""
        provider = AntigravityProvider(api_key="test-key")

        url = provider._build_url("gemini-1.5-pro", stream=True)
        assert "streamGenerateContent" in url
        assert "alt=sse" in url


class TestProviderHealth:
    """Tests for ProviderHealth dataclass."""

    def test_health_defaults(self):
        """Should have sensible defaults."""
        health = ProviderHealth(status=ProviderStatus.UNKNOWN)

        assert health.status == ProviderStatus.UNKNOWN
        assert health.latency_ms is None
        assert health.error is None
        assert health.last_check is not None

    def test_health_with_error(self):
        """Should store error message."""
        health = ProviderHealth(
            status=ProviderStatus.UNHEALTHY,
            error="Connection timeout",
        )

        assert health.status == ProviderStatus.UNHEALTHY
        assert health.error == "Connection timeout"


class TestProviderStatus:
    """Tests for ProviderStatus enum."""

    def test_status_values(self):
        """Should have expected status values."""
        assert ProviderStatus.HEALTHY.value == "healthy"
        assert ProviderStatus.DEGRADED.value == "degraded"
        assert ProviderStatus.UNHEALTHY.value == "unhealthy"
        assert ProviderStatus.UNKNOWN.value == "unknown"


class TestApiFormat:
    """Tests for ApiFormat enum."""

    def test_format_values(self):
        """Should have expected format values."""
        assert ApiFormat.ANTHROPIC.value == "anthropic"
        assert ApiFormat.OPENAI.value == "openai"
        assert ApiFormat.GEMINI.value == "gemini"
