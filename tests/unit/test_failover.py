"""
TDD Tests for failover logic.

Tests written FIRST following TDD methodology.
"""

import pytest

from a2c.providers import ProviderHealth, ProviderResponse, ProviderStatus
from a2c.router.failover import FailoverService, FailoverResult


class TestFailoverService:
    """Tests for failover service."""

    def test_create_failover_service(self):
        """Should create failover service with default config."""
        service = FailoverService()

        assert service.max_retries == 3
        assert service.retry_delay_ms == 100

    def test_create_with_custom_config(self):
        """Should create with custom configuration."""
        service = FailoverService(max_retries=5, retry_delay_ms=200)

        assert service.max_retries == 5
        assert service.retry_delay_ms == 200

    def test_should_retry_on_5xx(self):
        """Should retry on 5xx errors."""
        service = FailoverService()

        assert service.should_retry(500) is True
        assert service.should_retry(502) is True
        assert service.should_retry(503) is True
        assert service.should_retry(504) is True

    def test_should_retry_on_429(self):
        """Should retry on rate limit errors."""
        service = FailoverService()

        assert service.should_retry(429) is True

    def test_should_not_retry_on_4xx(self):
        """Should not retry on client errors (except 429)."""
        service = FailoverService()

        assert service.should_retry(400) is False
        assert service.should_retry(401) is False
        assert service.should_retry(403) is False
        assert service.should_retry(404) is False

    def test_should_not_retry_on_success(self):
        """Should not retry on success."""
        service = FailoverService()

        assert service.should_retry(200) is False
        assert service.should_retry(201) is False

    def test_should_failover_on_unhealthy(self):
        """Should failover when provider is unhealthy."""
        service = FailoverService()

        health = ProviderHealth(status=ProviderStatus.UNHEALTHY)
        assert service.should_failover(health) is True

    def test_should_not_failover_on_healthy(self):
        """Should not failover when provider is healthy."""
        service = FailoverService()

        health = ProviderHealth(status=ProviderStatus.HEALTHY)
        assert service.should_failover(health) is False

    def test_should_failover_on_degraded_with_high_latency(self):
        """Should failover when provider is degraded with high latency."""
        service = FailoverService(latency_threshold_ms=1000)

        health = ProviderHealth(status=ProviderStatus.DEGRADED, latency_ms=2000)
        assert service.should_failover(health) is True

    def test_should_not_failover_on_degraded_with_low_latency(self):
        """Should not failover when provider is degraded but latency is acceptable."""
        service = FailoverService(latency_threshold_ms=1000)

        health = ProviderHealth(status=ProviderStatus.DEGRADED, latency_ms=500)
        assert service.should_failover(health) is False


class TestFailoverResult:
    """Tests for failover result."""

    def test_create_success_result(self):
        """Should create successful result."""
        response = ProviderResponse(status_code=200, headers={}, body={"content": []})
        result = FailoverResult(
            success=True,
            provider_used="anthropic",
            response=response,
            attempts=1,
        )

        assert result.success is True
        assert result.provider_used == "anthropic"
        assert result.response == response
        assert result.attempts == 1
        assert result.failover_chain == []

    def test_create_failover_result(self):
        """Should create result with failover chain."""
        response = ProviderResponse(status_code=200, headers={}, body={"content": []})
        result = FailoverResult(
            success=True,
            provider_used="openai",
            response=response,
            attempts=3,
            failover_chain=["anthropic", "gemini", "openai"],
        )

        assert result.success is True
        assert result.provider_used == "openai"
        assert result.attempts == 3
        assert result.failover_chain == ["anthropic", "gemini", "openai"]

    def test_create_failure_result(self):
        """Should create failure result."""
        result = FailoverResult(
            success=False,
            provider_used="anthropic",
            response=None,
            attempts=3,
            error="All providers failed",
        )

        assert result.success is False
        assert result.error == "All providers failed"
        assert result.response is None

    def test_to_dict(self):
        """Should convert to dictionary."""
        response = ProviderResponse(status_code=200, headers={}, body={"content": []})
        result = FailoverResult(
            success=True,
            provider_used="anthropic",
            response=response,
            attempts=1,
        )

        d = result.to_dict()

        assert d["success"] is True
        assert d["provider_used"] == "anthropic"
        assert d["attempts"] == 1
        assert "response" in d


class TestFailoverChain:
    """Tests for failover chain building."""

    def test_build_chain_with_fallback(self):
        """Should build chain with fallback provider prioritized."""
        service = FailoverService()

        chain = service.build_failover_chain(
            primary="anthropic",
            fallback="openai",
            available=["anthropic", "openai", "gemini"],
        )

        # Primary first, then fallback, then others
        assert chain[0] == "anthropic"
        assert chain[1] == "openai"
        assert "gemini" in chain

    def test_build_chain_without_fallback(self):
        """Should build chain with all available providers."""
        service = FailoverService()

        chain = service.build_failover_chain(
            primary="anthropic",
            fallback=None,
            available=["anthropic", "openai", "gemini"],
        )

        assert chain[0] == "anthropic"
        assert "openai" in chain
        assert "gemini" in chain

    def test_build_chain_excludes_unavailable(self):
        """Should exclude unavailable providers."""
        service = FailoverService()

        chain = service.build_failover_chain(
            primary="anthropic",
            fallback="openai",
            available=["anthropic", "gemini"],  # openai not available
        )

        assert chain == ["anthropic", "gemini"]

    def test_build_chain_primary_not_available(self):
        """Should handle primary not being available."""
        service = FailoverService()

        chain = service.build_failover_chain(
            primary="anthropic",
            fallback="openai",
            available=["openai", "gemini"],  # anthropic not available
        )

        assert chain == ["openai", "gemini"]


class TestRetryBackoff:
    """Tests for retry backoff calculation."""

    def test_exponential_backoff(self):
        """Should calculate exponential backoff."""
        service = FailoverService(retry_delay_ms=100)

        assert service.get_retry_delay(attempt=1) == 100
        assert service.get_retry_delay(attempt=2) == 200
        assert service.get_retry_delay(attempt=3) == 400

    def test_backoff_max_cap(self):
        """Should cap backoff at max delay."""
        service = FailoverService(retry_delay_ms=100, max_retry_delay_ms=500)

        assert service.get_retry_delay(attempt=1) == 100
        assert service.get_retry_delay(attempt=2) == 200
        assert service.get_retry_delay(attempt=3) == 400
        assert service.get_retry_delay(attempt=4) == 500  # Capped
        assert service.get_retry_delay(attempt=5) == 500  # Still capped
