"""
Anthropic native provider.

Direct passthrough to Anthropic API with minimal transformation.
"""

import json
import logging
import time
from typing import Any, AsyncIterator

import httpx

from a2c.providers.base import (
    ApiFormat,
    BaseProvider,
    ProviderHealth,
    ProviderInfo,
    ProviderResponse,
    ProviderStatus,
)
from a2c.server.config import get_settings

logger = logging.getLogger(__name__)

# Anthropic API version
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(BaseProvider):
    """
    Native Anthropic API provider.

    Sends requests directly to Anthropic's API with minimal transformation.
    Supports streaming and all Anthropic features.
    """

    def __init__(
        self,
        name: str = "anthropic",
        api_key: str | None = None,
        base_url: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize Anthropic provider.

        Args:
            name: Provider name
            api_key: Anthropic API key (defaults to env var)
            base_url: API base URL (defaults to official API)
            config: Additional configuration
        """
        super().__init__(name, config)

        settings = get_settings()
        self._api_key = api_key or settings.providers.anthropic_api_key
        self._base_url = (base_url or settings.providers.anthropic_base_url).rstrip("/")

        # HTTP client with connection pooling
        self._client: httpx.AsyncClient | None = None

    @property
    def info(self) -> ProviderInfo:
        """Get provider metadata."""
        return ProviderInfo(
            name=self.name,
            display_name="Anthropic",
            api_format=ApiFormat.ANTHROPIC,
            supports_streaming=True,
            supports_thinking=True,
            supports_tools=True,
            supports_vision=True,
            max_context_tokens=200000,
            description="Native Anthropic Claude API",
        )

    @property
    def is_configured(self) -> bool:
        """Check if provider is configured."""
        return bool(self._api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(120.0, connect=10.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
        return self._client

    def _build_headers(self, stream: bool = False) -> dict[str, str]:
        """Build request headers."""
        headers = {
            "x-api-key": self._api_key or "",
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        if stream:
            headers["accept"] = "text/event-stream"
        return headers

    async def send_request(
        self,
        request: dict[str, Any],
        *,
        stream: bool = False,
        timeout: float = 120.0,
    ) -> ProviderResponse:
        """
        Send a request to Anthropic API.

        Args:
            request: Anthropic-format request body
            stream: Whether to stream response
            timeout: Request timeout

        Returns:
            Provider response
        """
        if not self.is_configured:
            return ProviderResponse(
                status_code=401,
                headers={},
                error="Anthropic API key not configured",
            )

        start_time = time.monotonic()
        client = await self._get_client()

        try:
            # Build request
            headers = self._build_headers(stream=stream)
            request_copy = dict(request)
            request_copy["stream"] = stream

            # Send request
            response = await client.post(
                "/v1/messages",
                headers=headers,
                json=request_copy,
                timeout=timeout,
            )

            latency_ms = (time.monotonic() - start_time) * 1000

            if stream:
                # Return stream iterator
                return ProviderResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    stream=response.aiter_bytes(),
                    latency_ms=latency_ms,
                )
            else:
                # Parse response body
                body = response.json()
                return ProviderResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=body,
                    latency_ms=latency_ms,
                    input_tokens=body.get("usage", {}).get("input_tokens", 0),
                    output_tokens=body.get("usage", {}).get("output_tokens", 0),
                )

        except httpx.TimeoutException as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            return ProviderResponse(
                status_code=408,
                headers={},
                error=f"Request timeout: {e}",
                latency_ms=latency_ms,
            )
        except httpx.HTTPError as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            return ProviderResponse(
                status_code=502,
                headers={},
                error=f"HTTP error: {e}",
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            logger.exception(f"Anthropic request failed: {e}")
            return ProviderResponse(
                status_code=500,
                headers={},
                error=f"Internal error: {e}",
                latency_ms=latency_ms,
            )

    async def stream_response(
        self,
        request: dict[str, Any],
        *,
        timeout: float = 120.0,
    ) -> AsyncIterator[bytes]:
        """
        Stream response from Anthropic API.

        Args:
            request: Anthropic-format request body
            timeout: Request timeout

        Yields:
            SSE event bytes
        """
        if not self.is_configured:
            error_event = {
                "type": "error",
                "error": {"type": "authentication_error", "message": "API key not configured"},
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()
            return

        client = await self._get_client()
        headers = self._build_headers(stream=True)

        request_copy = dict(request)
        request_copy["stream"] = True

        try:
            async with client.stream(
                "POST",
                "/v1/messages",
                headers=headers,
                json=request_copy,
                timeout=timeout,
            ) as response:
                if response.status_code != 200:
                    # Read error body
                    error_body = await response.aread()
                    try:
                        error_json = json.loads(error_body)
                        error_msg = error_json.get("error", {}).get("message", str(error_body))
                    except Exception:
                        error_msg = error_body.decode("utf-8", errors="replace")

                    error_event = {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": error_msg,
                        },
                    }
                    yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()
                    return

                # Stream response bytes directly
                async for chunk in response.aiter_bytes():
                    yield chunk

        except httpx.TimeoutException:
            error_event = {
                "type": "error",
                "error": {"type": "timeout_error", "message": "Request timed out"},
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()

        except httpx.HTTPError as e:
            error_event = {
                "type": "error",
                "error": {"type": "network_error", "message": str(e)},
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()

        except Exception as e:
            logger.exception(f"Anthropic stream failed: {e}")
            error_event = {
                "type": "error",
                "error": {"type": "internal_error", "message": str(e)},
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()

    async def health_check(self) -> ProviderHealth:
        """
        Check Anthropic API health.

        Sends a minimal request to verify connectivity.

        Returns:
            Health check result
        """
        if not self.is_configured:
            self._health = ProviderHealth(
                status=ProviderStatus.UNHEALTHY,
                error="API key not configured",
            )
            return self._health

        start_time = time.monotonic()

        try:
            client = await self._get_client()

            # Send minimal request to check connectivity
            # Using a simple message that should fail fast with minimal tokens
            response = await client.post(
                "/v1/messages",
                headers=self._build_headers(),
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                },
                timeout=10.0,
            )

            latency_ms = (time.monotonic() - start_time) * 1000

            if response.status_code == 200:
                self._health = ProviderHealth(
                    status=ProviderStatus.HEALTHY,
                    latency_ms=latency_ms,
                )
            elif response.status_code == 401:
                self._health = ProviderHealth(
                    status=ProviderStatus.UNHEALTHY,
                    latency_ms=latency_ms,
                    error="Invalid API key",
                )
            elif response.status_code == 429:
                self._health = ProviderHealth(
                    status=ProviderStatus.DEGRADED,
                    latency_ms=latency_ms,
                    error="Rate limited",
                )
            else:
                body = response.json()
                error_msg = body.get("error", {}).get("message", f"Status {response.status_code}")
                self._health = ProviderHealth(
                    status=ProviderStatus.DEGRADED,
                    latency_ms=latency_ms,
                    error=error_msg,
                )

        except httpx.TimeoutException:
            latency_ms = (time.monotonic() - start_time) * 1000
            self._health = ProviderHealth(
                status=ProviderStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error="Connection timeout",
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            self._health = ProviderHealth(
                status=ProviderStatus.UNHEALTHY,
                latency_ms=latency_ms,
                error=str(e),
            )

        return self._health

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
