"""
Antigravity provider.

Routes requests through Google's Antigravity API, converting between
Anthropic and Gemini formats using the core converter module.
"""

import json
import logging
import time
import uuid
from typing import Any, AsyncIterator

import httpx

from a2c.core import (
    antigravity_sse_to_anthropic_sse,
    convert_anthropic_request_to_antigravity_components,
    estimate_input_tokens,
)
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


class AntigravityProvider(BaseProvider):
    """
    Google Antigravity API provider.

    Converts Anthropic requests to Antigravity format using the core
    converter, and converts streaming responses back to Anthropic format.

    Supports extended thinking with Opus 4.5.
    """

    def __init__(
        self,
        name: str = "antigravity",
        api_key: str | None = None,
        project_id: str | None = None,
        location: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize Antigravity provider.

        Args:
            name: Provider name
            api_key: Google API key
            project_id: Google Cloud project ID
            location: Antigravity region
            config: Additional configuration
        """
        super().__init__(name, config)

        settings = get_settings()
        self._api_key = api_key or settings.providers.google_api_key
        self._project_id = project_id or settings.providers.antigravity_project_id
        self._location = location or settings.providers.antigravity_location

        # Build endpoint URL
        self._base_url = self._build_endpoint_url()

        # HTTP client
        self._client: httpx.AsyncClient | None = None

    def _build_endpoint_url(self) -> str:
        """Build the Antigravity endpoint URL."""
        if self._project_id:
            # Google Cloud Vertex AI endpoint
            return (
                f"https://{self._location}-aiplatform.googleapis.com/"
                f"v1/projects/{self._project_id}/locations/{self._location}"
            )
        else:
            # Direct Gemini API (fallback)
            return "https://generativelanguage.googleapis.com/v1beta"

    @property
    def info(self) -> ProviderInfo:
        """Get provider metadata."""
        return ProviderInfo(
            name=self.name,
            display_name="Antigravity (Google)",
            api_format=ApiFormat.GEMINI,
            supports_streaming=True,
            supports_thinking=True,
            supports_tools=True,
            supports_vision=True,
            max_context_tokens=1000000,
            description="Google Antigravity API with Claude model support",
        )

    @property
    def is_configured(self) -> bool:
        """Check if provider is configured."""
        return bool(self._api_key or self._project_id)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(180.0, connect=10.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
        return self._client

    def _build_headers(self) -> dict[str, str]:
        """Build request headers."""
        headers = {
            "content-type": "application/json",
        }
        if self._api_key:
            headers["x-goog-api-key"] = self._api_key
        return headers

    def _build_url(self, model: str, stream: bool = False) -> str:
        """Build request URL for model."""
        action = "streamGenerateContent" if stream else "generateContent"

        if self._project_id:
            # Vertex AI format
            return f"{self._base_url}/publishers/google/models/{model}:{action}"
        else:
            # Direct API format
            url = f"{self._base_url}/models/{model}:{action}"
            if self._api_key:
                url += f"?key={self._api_key}"
            if stream:
                url += "&alt=sse" if "?" in url else "?alt=sse"
            return url

    async def send_request(
        self,
        request: dict[str, Any],
        *,
        stream: bool = False,
        timeout: float = 180.0,
    ) -> ProviderResponse:
        """
        Send a request to Antigravity API.

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
                error="Antigravity not configured (need API key or project ID)",
            )

        start_time = time.monotonic()
        client = await self._get_client()

        try:
            # Convert Anthropic request to Antigravity format
            components = convert_anthropic_request_to_antigravity_components(request)

            model = components["model"]
            url = self._build_url(model, stream=stream)

            # Build Antigravity request body
            antigravity_body = {
                "contents": components["contents"],
                "generationConfig": components["generation_config"],
            }

            if components.get("system_instruction"):
                antigravity_body["systemInstruction"] = components["system_instruction"]

            if components.get("tools"):
                antigravity_body["tools"] = components["tools"]

            # Send request
            response = await client.post(
                url,
                headers=self._build_headers(),
                json=antigravity_body,
                timeout=timeout,
            )

            latency_ms = (time.monotonic() - start_time) * 1000

            if stream:
                # For streaming, we need to convert the response
                # This is handled separately in stream_response
                return ProviderResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    stream=response.aiter_bytes(),
                    latency_ms=latency_ms,
                )
            else:
                body = response.json()
                # TODO: Convert response to Anthropic format
                return ProviderResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=body,
                    latency_ms=latency_ms,
                )

        except httpx.TimeoutException as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            return ProviderResponse(
                status_code=408,
                headers={},
                error=f"Request timeout: {e}",
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            logger.exception(f"Antigravity request failed: {e}")
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
        timeout: float = 180.0,
    ) -> AsyncIterator[bytes]:
        """
        Stream response from Antigravity API.

        Converts Antigravity SSE to Anthropic SSE format.

        Args:
            request: Anthropic-format request body
            timeout: Request timeout

        Yields:
            SSE event bytes in Anthropic format
        """
        if not self.is_configured:
            error_event = {
                "type": "error",
                "error": {"type": "authentication_error", "message": "Provider not configured"},
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()
            return

        client = await self._get_client()

        try:
            # Convert Anthropic request to Antigravity format
            components = convert_anthropic_request_to_antigravity_components(request)

            model = components["model"]
            url = self._build_url(model, stream=True)

            # Estimate input tokens for response
            input_tokens = estimate_input_tokens(
                messages=request.get("messages", []),
                system=request.get("system"),
                tools=request.get("tools"),
            )

            # Determine thinking mode
            thinking = request.get("thinking", {})
            client_thinking_enabled = True
            thinking_to_text = False

            if isinstance(thinking, dict):
                client_thinking_enabled = thinking.get("type") != "disabled"
            elif thinking is False:
                client_thinking_enabled = False

            # Check for -nothinking model variant
            original_model = request.get("model", "")
            if "-nothinking" in original_model.lower():
                client_thinking_enabled = False
                thinking_to_text = True

            # Build Antigravity request body
            antigravity_body = {
                "contents": components["contents"],
                "generationConfig": components["generation_config"],
            }

            if components.get("system_instruction"):
                antigravity_body["systemInstruction"] = components["system_instruction"]

            if components.get("tools"):
                antigravity_body["tools"] = components["tools"]

            # Generate message ID
            message_id = f"msg_{uuid.uuid4().hex[:24]}"

            async with client.stream(
                "POST",
                url,
                headers=self._build_headers(),
                json=antigravity_body,
                timeout=timeout,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    try:
                        error_json = json.loads(error_body)
                        error_msg = error_json.get("error", {}).get("message", str(error_body))
                    except Exception:
                        error_msg = error_body.decode("utf-8", errors="replace")

                    error_event = {
                        "type": "error",
                        "error": {"type": "api_error", "message": error_msg},
                    }
                    yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()
                    return

                # Convert Antigravity SSE to Anthropic SSE
                async for chunk in antigravity_sse_to_anthropic_sse(
                    response.aiter_lines(),
                    model=original_model,
                    message_id=message_id,
                    client_thinking_enabled=client_thinking_enabled,
                    thinking_to_text=thinking_to_text,
                    initial_input_tokens=input_tokens,
                ):
                    yield chunk

        except httpx.TimeoutException:
            error_event = {
                "type": "error",
                "error": {"type": "timeout_error", "message": "Request timed out"},
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()

        except Exception as e:
            logger.exception(f"Antigravity stream failed: {e}")
            error_event = {
                "type": "error",
                "error": {"type": "internal_error", "message": str(e)},
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()

    async def health_check(self) -> ProviderHealth:
        """
        Check Antigravity API health.

        Returns:
            Health check result
        """
        if not self.is_configured:
            self._health = ProviderHealth(
                status=ProviderStatus.UNHEALTHY,
                error="Provider not configured",
            )
            return self._health

        start_time = time.monotonic()

        try:
            client = await self._get_client()

            # Send minimal request
            url = self._build_url("gemini-1.5-flash", stream=False)

            response = await client.post(
                url,
                headers=self._build_headers(),
                json={
                    "contents": [{"role": "user", "parts": [{"text": "hi"}]}],
                    "generationConfig": {"maxOutputTokens": 1},
                },
                timeout=10.0,
            )

            latency_ms = (time.monotonic() - start_time) * 1000

            if response.status_code == 200:
                self._health = ProviderHealth(
                    status=ProviderStatus.HEALTHY,
                    latency_ms=latency_ms,
                )
            elif response.status_code == 401 or response.status_code == 403:
                self._health = ProviderHealth(
                    status=ProviderStatus.UNHEALTHY,
                    latency_ms=latency_ms,
                    error="Invalid credentials",
                )
            elif response.status_code == 429:
                self._health = ProviderHealth(
                    status=ProviderStatus.DEGRADED,
                    latency_ms=latency_ms,
                    error="Rate limited",
                )
            else:
                self._health = ProviderHealth(
                    status=ProviderStatus.DEGRADED,
                    latency_ms=latency_ms,
                    error=f"Status {response.status_code}",
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
