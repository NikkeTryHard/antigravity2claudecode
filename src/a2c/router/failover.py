"""
Failover service for provider resilience.

Handles:
- Automatic retry with exponential backoff
- Provider failover when primary fails
- Health-based provider selection
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from a2c.providers.base import ProviderHealth, ProviderResponse, ProviderStatus

logger = logging.getLogger(__name__)


@dataclass
class FailoverResult:
    """Result of a failover operation."""

    success: bool
    provider_used: str
    response: ProviderResponse | None
    attempts: int
    failover_chain: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "success": self.success,
            "provider_used": self.provider_used,
            "attempts": self.attempts,
            "failover_chain": self.failover_chain,
            "error": self.error,
        }
        if self.response:
            result["response"] = {
                "status_code": self.response.status_code,
                "latency_ms": self.response.latency_ms,
                "input_tokens": self.response.input_tokens,
                "output_tokens": self.response.output_tokens,
            }
        return result


class FailoverService:
    """
    Service for handling provider failover and retries.

    Provides:
    - Retry logic with exponential backoff
    - Provider failover chain building
    - Health-based failover decisions
    """

    # Status codes that should trigger retry
    # 408: Request Timeout - transient, should retry
    # 429: Too Many Requests - rate limited, should retry with backoff
    # 500: Internal Server Error - may be transient
    # 502: Bad Gateway - proxy/upstream issue, often transient
    # 503: Service Unavailable - temporary overload
    # 504: Gateway Timeout - upstream timeout, may succeed on retry
    RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_ms: int = 100,
        max_retry_delay_ms: int = 5000,
        latency_threshold_ms: float = 5000,
    ):
        """
        Initialize failover service.

        Args:
            max_retries: Maximum retry attempts per provider
            retry_delay_ms: Base delay between retries in milliseconds
            max_retry_delay_ms: Maximum delay between retries
            latency_threshold_ms: Latency threshold for failover decision
        """
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
        self.max_retry_delay_ms = max_retry_delay_ms
        self.latency_threshold_ms = latency_threshold_ms

    def should_retry(self, status_code: int) -> bool:
        """
        Check if a request should be retried based on status code.

        Args:
            status_code: HTTP status code from response

        Returns:
            True if request should be retried
        """
        return status_code in self.RETRYABLE_STATUS_CODES

    def should_failover(self, health: ProviderHealth) -> bool:
        """
        Check if should failover to another provider based on health.

        Args:
            health: Provider health status

        Returns:
            True if should failover to another provider
        """
        if health.status == ProviderStatus.UNHEALTHY:
            return True

        if health.status == ProviderStatus.DEGRADED:
            # Failover if latency is too high
            if health.latency_ms and health.latency_ms > self.latency_threshold_ms:
                return True

        return False

    def build_failover_chain(
        self,
        primary: str,
        fallback: str | None,
        available: list[str],
    ) -> list[str]:
        """
        Build ordered list of providers to try.

        Args:
            primary: Primary provider name
            fallback: Explicit fallback provider (if any)
            available: List of available provider names

        Returns:
            Ordered list of providers to try
        """
        chain = []

        # Add primary if available
        if primary in available:
            chain.append(primary)

        # Add explicit fallback if available
        if fallback and fallback in available and fallback not in chain:
            chain.append(fallback)

        # Add remaining available providers
        for provider in available:
            if provider not in chain:
                chain.append(provider)

        return chain

    def get_retry_delay(self, attempt: int) -> int:
        """
        Calculate retry delay with exponential backoff.

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Delay in milliseconds
        """
        # Exponential backoff: base * 2^(attempt-1)
        delay = self.retry_delay_ms * (2 ** (attempt - 1))
        return min(delay, self.max_retry_delay_ms)
