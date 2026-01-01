"""
Base provider interface and types.

All providers must implement the BaseProvider abstract class.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, AsyncIterator


class ProviderStatus(str, Enum):
    """Provider health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ApiFormat(str, Enum):
    """API format type."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"


@dataclass
class ProviderHealth:
    """Provider health check result."""

    status: ProviderStatus
    latency_ms: float | None = None
    last_check: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderRequest:
    """Normalized request to send to provider."""

    method: str
    path: str
    headers: dict[str, str]
    body: dict[str, Any]
    stream: bool = False
    timeout: float = 120.0


@dataclass
class ProviderResponse:
    """Response from provider."""

    status_code: int
    headers: dict[str, str]
    body: dict[str, Any] | None = None
    stream: AsyncIterator[bytes] | None = None
    error: str | None = None
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ProviderInfo:
    """Provider metadata."""

    name: str
    display_name: str
    api_format: ApiFormat
    supports_streaming: bool = True
    supports_thinking: bool = False
    supports_tools: bool = True
    supports_vision: bool = True
    max_context_tokens: int = 200000
    description: str = ""


class BaseProvider(ABC):
    """
    Abstract base class for all AI providers.

    Each provider implementation handles:
    - Request conversion to provider format
    - Response conversion to Anthropic format
    - Health checks
    - Streaming handling
    """

    def __init__(self, name: str, config: dict[str, Any] | None = None):
        """
        Initialize provider.

        Args:
            name: Unique provider name
            config: Provider-specific configuration
        """
        self.name = name
        self.config = config or {}
        self._health = ProviderHealth(status=ProviderStatus.UNKNOWN)

    @property
    @abstractmethod
    def info(self) -> ProviderInfo:
        """Get provider metadata."""
        ...

    @abstractmethod
    async def send_request(
        self,
        request: dict[str, Any],
        *,
        stream: bool = False,
        timeout: float = 120.0,
    ) -> ProviderResponse:
        """
        Send a request to the provider.

        Args:
            request: Anthropic-format request body
            stream: Whether to stream the response
            timeout: Request timeout in seconds

        Returns:
            Provider response (may include stream iterator)
        """
        ...

    @abstractmethod
    async def stream_response(
        self,
        request: dict[str, Any],
        *,
        timeout: float = 120.0,
    ) -> AsyncIterator[bytes]:
        """
        Stream a response from the provider.

        Args:
            request: Anthropic-format request body
            timeout: Request timeout in seconds

        Yields:
            SSE event bytes in Anthropic format
        """
        ...

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """
        Check provider health.

        Returns:
            Health check result
        """
        ...

    @property
    def health(self) -> ProviderHealth:
        """Get last known health status."""
        return self._health

    @property
    def is_healthy(self) -> bool:
        """Check if provider is healthy."""
        return self._health.status == ProviderStatus.HEALTHY

    @property
    def is_configured(self) -> bool:
        """Check if provider is properly configured."""
        return True  # Override in subclasses

    def to_dict(self) -> dict[str, Any]:
        """Convert provider info to dictionary."""
        return {
            "name": self.name,
            "display_name": self.info.display_name,
            "api_format": self.info.api_format.value,
            "supports_streaming": self.info.supports_streaming,
            "supports_thinking": self.info.supports_thinking,
            "supports_tools": self.info.supports_tools,
            "supports_vision": self.info.supports_vision,
            "max_context_tokens": self.info.max_context_tokens,
            "is_configured": self.is_configured,
            "is_healthy": self.is_healthy,
            "health": {
                "status": self._health.status.value,
                "latency_ms": self._health.latency_ms,
                "last_check": self._health.last_check.isoformat(),
                "error": self._health.error,
            },
        }
