"""
Comprehensive tests for failover edge cases.
"""

import pytest

from a2c.providers import ProviderHealth, ProviderResponse, ProviderStatus
from a2c.router.failover import FailoverService, FailoverResult


class TestFailoverServiceEdgeCases:
    """Edge case tests for failover service."""

    def test_should_retry_timeout(self):
        """Should retry on timeout (408)."""
        service = FailoverService()
        assert service.should_retry(408) is True

    def test_should_not_retry_on_success_codes(self):
        """Should not retry on any 2xx codes."""
        service = FailoverService()

        for code in [200, 201, 202, 204]:
            assert service.should_retry(code) is False

    def test_should_not_retry_on_redirect(self):
        """Should not retry on redirect codes."""
        service = FailoverService()

        for code in [301, 302, 303, 307, 308]:
            assert service.should_retry(code) is False

    def test_should_failover_on_unknown_status(self):
        """Should not failover on unknown status."""
        service = FailoverService()

        health = ProviderHealth(status=ProviderStatus.UNKNOWN)
        assert service.should_failover(health) is False

    def test_should_failover_with_none_latency(self):
        """Should handle None latency in degraded state."""
        service = FailoverService(latency_threshold_ms=1000)

        health = ProviderHealth(status=ProviderStatus.DEGRADED, latency_ms=None)
        assert service.should_failover(health) is False

    def test_build_chain_empty_available(self):
        """Should handle empty available providers."""
        service = FailoverService()

        chain = service.build_failover_chain(
            primary="anthropic",
            fallback="openai",
            available=[],
        )

        assert chain == []

    def test_build_chain_single_provider(self):
        """Should handle single available provider."""
        service = FailoverService()

        chain = service.build_failover_chain(
            primary="anthropic",
            fallback="openai",
            available=["gemini"],
        )

        assert chain == ["gemini"]

    def test_build_chain_primary_equals_fallback(self):
        """Should handle primary same as fallback."""
        service = FailoverService()

        chain = service.build_failover_chain(
            primary="anthropic",
            fallback="anthropic",
            available=["anthropic", "openai"],
        )

        # Should not duplicate
        assert chain.count("anthropic") == 1
        assert "openai" in chain

    def test_retry_delay_first_attempt(self):
        """Should return base delay for first attempt."""
        service = FailoverService(retry_delay_ms=100)

        assert service.get_retry_delay(attempt=1) == 100

    def test_retry_delay_large_attempt(self):
        """Should cap delay at max for large attempt numbers."""
        service = FailoverService(retry_delay_ms=100, max_retry_delay_ms=1000)

        # 2^10 * 100 = 102400, should be capped at 1000
        assert service.get_retry_delay(attempt=10) == 1000

    def test_retry_delay_zero_base(self):
        """Should handle zero base delay."""
        service = FailoverService(retry_delay_ms=0, max_retry_delay_ms=1000)

        assert service.get_retry_delay(attempt=1) == 0
        assert service.get_retry_delay(attempt=5) == 0


class TestFailoverResultEdgeCases:
    """Edge case tests for failover result."""

    def test_to_dict_with_none_response(self):
        """Should handle None response in to_dict."""
        result = FailoverResult(
            success=False,
            provider_used="anthropic",
            response=None,
            attempts=3,
            error="All providers failed",
        )

        d = result.to_dict()

        assert d["success"] is False
        assert "response" not in d or d.get("response") is None

    def test_to_dict_with_full_response(self):
        """Should include all response fields in to_dict."""
        response = ProviderResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            body={"content": []},
            latency_ms=150.5,
            input_tokens=100,
            output_tokens=50,
        )
        result = FailoverResult(
            success=True,
            provider_used="anthropic",
            response=response,
            attempts=1,
        )

        d = result.to_dict()

        assert d["response"]["status_code"] == 200
        assert d["response"]["latency_ms"] == 150.5
        assert d["response"]["input_tokens"] == 100
        assert d["response"]["output_tokens"] == 50

    def test_failover_chain_ordering(self):
        """Should preserve failover chain order."""
        result = FailoverResult(
            success=True,
            provider_used="gemini",
            response=ProviderResponse(status_code=200, headers={}),
            attempts=3,
            failover_chain=["anthropic", "openai", "gemini"],
        )

        assert result.failover_chain == ["anthropic", "openai", "gemini"]
        assert result.provider_used == "gemini"


class TestFailoverServiceConfiguration:
    """Tests for failover service configuration."""

    def test_default_configuration(self):
        """Should have sensible defaults."""
        service = FailoverService()

        assert service.max_retries == 3
        assert service.retry_delay_ms == 100
        assert service.max_retry_delay_ms == 5000
        assert service.latency_threshold_ms == 5000

    def test_custom_configuration(self):
        """Should accept custom configuration."""
        service = FailoverService(
            max_retries=5,
            retry_delay_ms=200,
            max_retry_delay_ms=10000,
            latency_threshold_ms=2000,
        )

        assert service.max_retries == 5
        assert service.retry_delay_ms == 200
        assert service.max_retry_delay_ms == 10000
        assert service.latency_threshold_ms == 2000

    def test_retryable_status_codes(self):
        """Should have correct retryable status codes."""
        service = FailoverService()

        expected_codes = {408, 429, 500, 502, 503, 504}
        assert service.RETRYABLE_STATUS_CODES == expected_codes
