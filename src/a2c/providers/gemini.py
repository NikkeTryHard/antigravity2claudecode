"""
Google Gemini provider.

Converts Anthropic requests to Gemini format and vice versa.
Supports the Gemini API with its 1M+ context window.
"""

import json
import logging
import time
import uuid
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

# Default model mapping from Claude to Gemini
DEFAULT_MODEL_MAPPING = {
    # Claude 4.5 models -> Gemini 2.5 Pro (best quality)
    "claude-opus-4-5": "gemini-2.5-pro",
    "claude-opus-4-5-20251101": "gemini-2.5-pro",
    "claude-sonnet-4-5": "gemini-2.5-flash",
    "claude-sonnet-4-5-20250929": "gemini-2.5-flash",
    # Claude 3.5 models
    "claude-3-5-sonnet-20241022": "gemini-2.5-flash",
    # Claude 3 Haiku -> Gemini Flash Lite (fast/cheap)
    "claude-3-haiku-20240307": "gemini-2.5-flash-lite",
    "claude-haiku-4-5": "gemini-2.5-flash-lite",
}


class GeminiProvider(BaseProvider):
    """
    Google Gemini API provider.

    Converts Anthropic requests to Gemini format and responses back.
    Supports Gemini's large context window (1M+ tokens).
    """

    def __init__(
        self,
        name: str = "gemini",
        api_key: str | None = None,
        base_url: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize Gemini provider.

        Args:
            name: Provider name
            api_key: Google API key
            base_url: API base URL
            config: Additional configuration including model_mapping
        """
        super().__init__(name, config)

        settings = get_settings()
        self._api_key = api_key or settings.providers.google_api_key
        self._base_url = (base_url or settings.providers.gemini_base_url).rstrip("/")

        # Custom model mapping
        self._model_mapping = {
            **DEFAULT_MODEL_MAPPING,
            **(config or {}).get("model_mapping", {}),
        }

        self._client: httpx.AsyncClient | None = None

    @property
    def info(self) -> ProviderInfo:
        """Get provider metadata."""
        return ProviderInfo(
            name=self.name,
            display_name="Google Gemini",
            api_format=ApiFormat.GEMINI,
            supports_streaming=True,
            supports_thinking=False,
            supports_tools=True,
            supports_vision=True,
            max_context_tokens=1000000,  # Gemini 1.5 Pro has 1M context
            description="Google Gemini API with large context window",
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
            "Content-Type": "application/json",
        }
        if stream:
            headers["Accept"] = "text/event-stream"
        return headers

    def _map_model(self, model: str) -> str:
        """Map Claude model name to Gemini model."""
        # Check custom mapping first
        if model in self._model_mapping:
            return self._model_mapping[model]

        # Pass through if already a Gemini model
        if model.startswith("gemini-"):
            return model

        # Default to gemini-2.5-flash (good balance of speed/quality)
        return "gemini-2.5-flash"

    def _convert_request(self, anthropic_request: dict[str, Any]) -> dict[str, Any]:
        """
        Convert Anthropic request to Gemini format.

        Args:
            anthropic_request: Anthropic Messages API request

        Returns:
            Gemini generateContent API request
        """
        gemini_request: dict[str, Any] = {}

        # Convert system prompt to system_instruction
        if "system" in anthropic_request:
            system = anthropic_request["system"]
            if isinstance(system, str):
                gemini_request["system_instruction"] = {"parts": [{"text": system}]}
            elif isinstance(system, list):
                # Extract text from content blocks
                text_parts = []
                for block in system:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                if text_parts:
                    gemini_request["system_instruction"] = {
                        "parts": [{"text": "\n".join(text_parts)}]
                    }

        # Convert messages to contents
        contents = []
        for msg in anthropic_request.get("messages", []):
            converted = self._convert_message(msg)
            if converted:
                contents.append(converted)

        gemini_request["contents"] = contents

        # Convert generation config
        generation_config: dict[str, Any] = {}

        if "max_tokens" in anthropic_request:
            generation_config["maxOutputTokens"] = anthropic_request["max_tokens"]

        if "temperature" in anthropic_request:
            generation_config["temperature"] = anthropic_request["temperature"]

        if "stop_sequences" in anthropic_request:
            generation_config["stopSequences"] = anthropic_request["stop_sequences"]

        if "top_p" in anthropic_request:
            generation_config["topP"] = anthropic_request["top_p"]

        if generation_config:
            gemini_request["generationConfig"] = generation_config

        # Convert tools
        if "tools" in anthropic_request:
            gemini_request["tools"] = self._convert_tools(anthropic_request["tools"])

        return gemini_request

    def _convert_message(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        """Convert a single message to Gemini format."""
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Map role: assistant -> model
        gemini_role = "model" if role == "assistant" else role

        # Handle string content
        if isinstance(content, str):
            return {"role": gemini_role, "parts": [{"text": content}]}

        # Handle content blocks
        if isinstance(content, list):
            parts = []

            for block in content:
                if not isinstance(block, dict):
                    continue

                block_type = block.get("type")

                if block_type == "text":
                    parts.append({"text": block.get("text", "")})

                elif block_type == "image":
                    source = block.get("source", {})
                    if source.get("type") == "base64":
                        parts.append(
                            {
                                "inline_data": {
                                    "mime_type": source.get("media_type", "image/png"),
                                    "data": source.get("data", ""),
                                }
                            }
                        )

                elif block_type == "tool_use":
                    # Convert to functionCall
                    parts.append(
                        {
                            "functionCall": {
                                "name": block.get("name", ""),
                                "args": block.get("input", {}),
                            }
                        }
                    )

                elif block_type == "tool_result":
                    # Convert to functionResponse - this changes the role to "function"
                    return {
                        "role": "function",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": block.get("tool_use_id", ""),
                                    "response": {
                                        "content": self._extract_content_text(
                                            block.get("content", "")
                                        )
                                    },
                                }
                            }
                        ],
                    }

            if parts:
                return {"role": gemini_role, "parts": parts}

        return None

    def _extract_content_text(self, content: Any) -> str:
        """Extract text from content (string or blocks)."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            return "\n".join(parts)
        return str(content)

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert Anthropic tools to Gemini function declarations."""
        function_declarations = []
        for tool in tools:
            function_declarations.append(
                {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                }
            )
        return [{"function_declarations": function_declarations}]

    def _convert_response(
        self, gemini_response: dict[str, Any], original_model: str
    ) -> dict[str, Any]:
        """
        Convert Gemini response to Anthropic format.

        Args:
            gemini_response: Gemini generateContent response
            original_model: Original model name from request

        Returns:
            Anthropic Messages API response
        """
        candidates = gemini_response.get("candidates", [])
        if not candidates:
            return {
                "id": f"msg_{uuid.uuid4().hex[:24]}",
                "type": "message",
                "role": "assistant",
                "model": original_model,
                "content": [],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }

        candidate = candidates[0]
        content_data = candidate.get("content", {})
        parts = content_data.get("parts", [])
        finish_reason = candidate.get("finishReason", "STOP")

        # Convert finish_reason
        stop_reason_map = {
            "STOP": "end_turn",
            "MAX_TOKENS": "max_tokens",
            "SAFETY": "end_turn",
            "RECITATION": "end_turn",
            "OTHER": "end_turn",
        }

        # Check if there are function calls
        has_function_call = any("functionCall" in p for p in parts)
        if has_function_call:
            stop_reason = "tool_use"
        else:
            stop_reason = stop_reason_map.get(finish_reason, "end_turn")

        # Build content
        content = []
        for part in parts:
            if "text" in part:
                content.append({"type": "text", "text": part["text"]})
            elif "functionCall" in part:
                fc = part["functionCall"]
                content.append(
                    {
                        "type": "tool_use",
                        "id": f"toolu_{uuid.uuid4().hex[:24]}",
                        "name": fc.get("name", ""),
                        "input": fc.get("args", {}),
                    }
                )

        # Build usage
        usage_metadata = gemini_response.get("usageMetadata", {})

        return {
            "id": f"msg_{uuid.uuid4().hex[:24]}",
            "type": "message",
            "role": "assistant",
            "model": original_model,
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {
                "input_tokens": usage_metadata.get("promptTokenCount", 0),
                "output_tokens": usage_metadata.get("candidatesTokenCount", 0),
            },
        }

    async def send_request(
        self,
        request: dict[str, Any],
        *,
        stream: bool = False,
        timeout: float = 120.0,
    ) -> ProviderResponse:
        """Send request to Gemini API."""
        if not self.is_configured:
            return ProviderResponse(
                status_code=401,
                headers={},
                error="Google API key not configured",
            )

        start_time = time.monotonic()
        client = await self._get_client()
        original_model = request.get("model", "")
        gemini_model = self._map_model(original_model)

        try:
            gemini_request = self._convert_request(request)

            # Build URL with API key
            endpoint = "streamGenerateContent" if stream else "generateContent"
            url = f"/v1beta/models/{gemini_model}:{endpoint}?key={self._api_key}"

            response = await client.post(
                url,
                headers=self._build_headers(stream=stream),
                json=gemini_request,
                timeout=timeout,
            )

            latency_ms = (time.monotonic() - start_time) * 1000

            if stream:
                return ProviderResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    stream=response.aiter_bytes(),
                    latency_ms=latency_ms,
                )
            else:
                gemini_response = response.json()

                if response.status_code != 200:
                    error_msg = gemini_response.get("error", {}).get(
                        "message", f"Status {response.status_code}"
                    )
                    return ProviderResponse(
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        error=error_msg,
                        latency_ms=latency_ms,
                    )

                anthropic_response = self._convert_response(gemini_response, original_model)

                return ProviderResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=anthropic_response,
                    latency_ms=latency_ms,
                    input_tokens=anthropic_response["usage"]["input_tokens"],
                    output_tokens=anthropic_response["usage"]["output_tokens"],
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
            logger.exception(f"Gemini request failed: {e}")
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
        """Stream response from Gemini API, converting to Anthropic SSE format."""
        if not self.is_configured:
            error_event = {
                "type": "error",
                "error": {"type": "authentication_error", "message": "API key not configured"},
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()
            return

        client = await self._get_client()
        original_model = request.get("model", "")
        gemini_model = self._map_model(original_model)

        try:
            gemini_request = self._convert_request(request)

            url = f"/v1beta/models/{gemini_model}:streamGenerateContent?key={self._api_key}&alt=sse"

            async with client.stream(
                "POST",
                url,
                headers=self._build_headers(stream=True),
                json=gemini_request,
                timeout=timeout,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    error_event = {
                        "type": "error",
                        "error": {"type": "api_error", "message": error_body.decode()},
                    }
                    yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()
                    return

                # Convert Gemini SSE to Anthropic SSE
                async for chunk in self._convert_stream(response.aiter_lines(), original_model):
                    yield chunk

        except Exception as e:
            logger.exception(f"Gemini stream failed: {e}")
            error_event = {
                "type": "error",
                "error": {"type": "internal_error", "message": str(e)},
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()

    async def _convert_stream(
        self, lines: AsyncIterator[str], original_model: str
    ) -> AsyncIterator[bytes]:
        """Convert Gemini SSE stream to Anthropic format."""
        message_id = f"msg_{uuid.uuid4().hex[:24]}"
        content_index = 0
        sent_start = False

        async for line in lines:
            if not line.startswith("data: "):
                continue

            data = line[6:]
            if not data or data == "[DONE]":
                continue

            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue

            # Send message_start on first chunk
            if not sent_start:
                start_event = {
                    "type": "message_start",
                    "message": {
                        "id": message_id,
                        "type": "message",
                        "role": "assistant",
                        "model": original_model,
                        "content": [],
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                    },
                }
                yield f"event: message_start\ndata: {json.dumps(start_event)}\n\n".encode()
                sent_start = True

            # Process candidates
            candidates = chunk.get("candidates", [])
            if not candidates:
                continue

            candidate = candidates[0]
            content_data = candidate.get("content", {})
            parts = content_data.get("parts", [])

            for part in parts:
                if "text" in part:
                    # Send content_block_start if first content
                    if content_index == 0:
                        block_start = {
                            "type": "content_block_start",
                            "index": 0,
                            "content_block": {"type": "text", "text": ""},
                        }
                        yield f"event: content_block_start\ndata: {json.dumps(block_start)}\n\n".encode()
                        content_index = 1

                    # Send content_block_delta
                    block_delta = {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": part["text"]},
                    }
                    yield f"event: content_block_delta\ndata: {json.dumps(block_delta)}\n\n".encode()

            # Check for finish
            finish_reason = candidate.get("finishReason")
            if finish_reason:
                # Send content_block_stop
                if content_index > 0:
                    yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n".encode()

                # Send message_delta with stop_reason
                stop_reason = "end_turn" if finish_reason == "STOP" else "max_tokens"
                delta_event = {
                    "type": "message_delta",
                    "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                    "usage": {"output_tokens": 0},
                }
                yield f"event: message_delta\ndata: {json.dumps(delta_event)}\n\n".encode()

                # Send message_stop
                yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n".encode()

    async def health_check(self) -> ProviderHealth:
        """Check Gemini API health."""
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
            response = await client.post(
                f"/v1beta/models/gemini-2.5-flash-lite:generateContent?key={self._api_key}",
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
                    error="Invalid API key",
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
