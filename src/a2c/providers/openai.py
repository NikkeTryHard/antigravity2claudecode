"""
OpenAI-compatible provider.

Converts Anthropic requests to OpenAI format and vice versa.
Supports any OpenAI-compatible endpoint.
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

# Default model mapping from Claude to OpenAI
DEFAULT_MODEL_MAPPING = {
    # Claude 4.5 models -> GPT-4.1 (latest flagship)
    "claude-opus-4-5": "gpt-4.1",
    "claude-opus-4-5-20251101": "gpt-4.1",
    "claude-sonnet-4-5": "gpt-4.1",
    "claude-sonnet-4-5-20250929": "gpt-4.1",
    # Claude 3.5 models
    "claude-3-5-sonnet-20241022": "gpt-4o",
    # Claude 3 Haiku -> GPT-4.1 mini (fast/cheap)
    "claude-3-haiku-20240307": "gpt-4.1-mini",
    "claude-haiku-4-5": "gpt-4.1-mini",
}


class OpenAIProvider(BaseProvider):
    """
    OpenAI-compatible API provider.

    Converts Anthropic requests to OpenAI format and responses back.
    Works with OpenAI API and any compatible endpoint.
    """

    def __init__(
        self,
        name: str = "openai",
        api_key: str | None = None,
        base_url: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize OpenAI provider.

        Args:
            name: Provider name
            api_key: OpenAI API key
            base_url: API base URL
            config: Additional configuration including model_mapping
        """
        super().__init__(name, config)

        settings = get_settings()
        self._api_key = api_key or settings.providers.openai_api_key
        self._base_url = (base_url or settings.providers.openai_base_url).rstrip("/")

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
            display_name="OpenAI",
            api_format=ApiFormat.OPENAI,
            supports_streaming=True,
            supports_thinking=False,
            supports_tools=True,
            supports_vision=True,
            max_context_tokens=128000,
            description="OpenAI-compatible API endpoint",
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
            "Authorization": f"Bearer {self._api_key or ''}",
            "Content-Type": "application/json",
        }
        if stream:
            headers["Accept"] = "text/event-stream"
        return headers

    def _map_model(self, model: str) -> str:
        """Map Claude model name to OpenAI model."""
        # Check custom mapping first
        if model in self._model_mapping:
            return self._model_mapping[model]

        # Pass through if already an OpenAI model
        if (
            model.startswith("gpt-")
            or model.startswith("o1")
            or model.startswith("o3")
            or model.startswith("o4")
        ):
            return model

        # Default to gpt-4.1
        return "gpt-4.1"

    def _convert_request(self, anthropic_request: dict[str, Any]) -> dict[str, Any]:
        """
        Convert Anthropic request to OpenAI format.

        Args:
            anthropic_request: Anthropic Messages API request

        Returns:
            OpenAI Chat Completions API request
        """
        openai_request: dict[str, Any] = {
            "model": self._map_model(anthropic_request.get("model", "")),
        }

        # Convert max_tokens
        if "max_tokens" in anthropic_request:
            openai_request["max_tokens"] = anthropic_request["max_tokens"]

        # Convert temperature
        if "temperature" in anthropic_request:
            openai_request["temperature"] = anthropic_request["temperature"]

        # Convert stop_sequences to stop
        if "stop_sequences" in anthropic_request:
            openai_request["stop"] = anthropic_request["stop_sequences"]

        # Convert messages
        messages = []

        # Add system message if present
        if "system" in anthropic_request:
            system = anthropic_request["system"]
            if isinstance(system, str):
                messages.append({"role": "system", "content": system})
            elif isinstance(system, list):
                # Extract text from content blocks
                text_parts = []
                for block in system:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                if text_parts:
                    messages.append({"role": "system", "content": "\n".join(text_parts)})

        # Convert each message
        for msg in anthropic_request.get("messages", []):
            converted = self._convert_message(msg)
            if converted:
                messages.append(converted)

        openai_request["messages"] = messages

        # Convert tools
        if "tools" in anthropic_request:
            openai_request["tools"] = self._convert_tools(anthropic_request["tools"])

        return openai_request

    def _convert_message(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        """Convert a single message to OpenAI format."""
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Handle string content
        if isinstance(content, str):
            return {"role": role, "content": content}

        # Handle content blocks
        if isinstance(content, list):
            # Check for tool_result (becomes tool role)
            tool_results = [
                b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"
            ]
            if tool_results:
                result = tool_results[0]
                return {
                    "role": "tool",
                    "tool_call_id": result.get("tool_use_id", ""),
                    "content": self._extract_content_text(result.get("content", "")),
                }

            # Check for tool_use (becomes tool_calls)
            tool_uses = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
            if tool_uses:
                tool_calls = []
                for tu in tool_uses:
                    tool_calls.append(
                        {
                            "id": tu.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tu.get("name", ""),
                                "arguments": json.dumps(tu.get("input", {})),
                            },
                        }
                    )
                return {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls,
                }

            # Check for images
            has_images = any(isinstance(b, dict) and b.get("type") == "image" for b in content)

            if has_images:
                # Convert to OpenAI vision format
                openai_content = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            openai_content.append(
                                {
                                    "type": "text",
                                    "text": block.get("text", ""),
                                }
                            )
                        elif block.get("type") == "image":
                            source = block.get("source", {})
                            if source.get("type") == "base64":
                                openai_content.append(
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{source.get('media_type', 'image/png')};base64,{source.get('data', '')}",
                                        },
                                    }
                                )
                return {"role": role, "content": openai_content}

            # Simple text blocks - flatten to string
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    text_parts.append(block)

            if text_parts:
                return {"role": role, "content": "\n".join(text_parts)}

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
        """Convert Anthropic tools to OpenAI function format."""
        openai_tools = []
        for tool in tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {}),
                    },
                }
            )
        return openai_tools

    def _convert_response(
        self, openai_response: dict[str, Any], original_model: str
    ) -> dict[str, Any]:
        """
        Convert OpenAI response to Anthropic format.

        Args:
            openai_response: OpenAI Chat Completions response
            original_model: Original model name from request

        Returns:
            Anthropic Messages API response
        """
        choice = openai_response.get("choices", [{}])[0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "stop")

        # Convert finish_reason
        stop_reason_map = {
            "stop": "end_turn",
            "length": "max_tokens",
            "tool_calls": "tool_use",
            "content_filter": "end_turn",
        }
        stop_reason = stop_reason_map.get(finish_reason, "end_turn")

        # Build content
        content = []

        # Handle tool_calls
        tool_calls = message.get("tool_calls", [])
        if tool_calls:
            for tc in tool_calls:
                func = tc.get("function", {})
                try:
                    input_data = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    input_data = {"raw": func.get("arguments", "")}

                content.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": func.get("name", ""),
                        "input": input_data,
                    }
                )
        elif message.get("content"):
            content.append(
                {
                    "type": "text",
                    "text": message.get("content", ""),
                }
            )

        # Build usage
        usage = openai_response.get("usage", {})

        return {
            "id": openai_response.get("id", ""),
            "type": "message",
            "role": "assistant",
            "model": original_model,
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
        }

    async def send_request(
        self,
        request: dict[str, Any],
        *,
        stream: bool = False,
        timeout: float = 120.0,
    ) -> ProviderResponse:
        """Send request to OpenAI API."""
        if not self.is_configured:
            return ProviderResponse(
                status_code=401,
                headers={},
                error="OpenAI API key not configured",
            )

        start_time = time.monotonic()
        client = await self._get_client()
        original_model = request.get("model", "")

        try:
            openai_request = self._convert_request(request)
            openai_request["stream"] = stream

            response = await client.post(
                "/chat/completions",
                headers=self._build_headers(stream=stream),
                json=openai_request,
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
                openai_response = response.json()
                anthropic_response = self._convert_response(openai_response, original_model)

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
            logger.exception(f"OpenAI request failed: {e}")
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
        """Stream response from OpenAI API, converting to Anthropic SSE format."""
        if not self.is_configured:
            error_event = {
                "type": "error",
                "error": {"type": "authentication_error", "message": "API key not configured"},
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()
            return

        client = await self._get_client()
        original_model = request.get("model", "")

        try:
            openai_request = self._convert_request(request)
            openai_request["stream"] = True

            async with client.stream(
                "POST",
                "/chat/completions",
                headers=self._build_headers(stream=True),
                json=openai_request,
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

                # Convert OpenAI SSE to Anthropic SSE
                async for chunk in self._convert_stream(response.aiter_lines(), original_model):
                    yield chunk

        except Exception as e:
            logger.exception(f"OpenAI stream failed: {e}")
            error_event = {
                "type": "error",
                "error": {"type": "internal_error", "message": str(e)},
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()

    async def _convert_stream(
        self, lines: AsyncIterator[str], original_model: str
    ) -> AsyncIterator[bytes]:
        """Convert OpenAI SSE stream to Anthropic format."""
        import uuid

        message_id = f"msg_{uuid.uuid4().hex[:24]}"
        content_index = 0
        sent_start = False

        async for line in lines:
            if not line.startswith("data: "):
                continue

            data = line[6:]
            if data == "[DONE]":
                # Send message_delta with stop_reason
                delta_event = {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                    "usage": {"output_tokens": 0},
                }
                yield f"event: message_delta\ndata: {json.dumps(delta_event)}\n\n".encode()

                # Send message_stop
                yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n".encode()
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

            # Process delta
            choice = chunk.get("choices", [{}])[0]
            delta = choice.get("delta", {})

            if delta.get("content"):
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
                    "delta": {"type": "text_delta", "text": delta["content"]},
                }
                yield f"event: content_block_delta\ndata: {json.dumps(block_delta)}\n\n".encode()

            # Check for finish
            if choice.get("finish_reason"):
                # Send content_block_stop
                if content_index > 0:
                    yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n".encode()

    async def health_check(self) -> ProviderHealth:
        """Check OpenAI API health."""
        if not self.is_configured:
            self._health = ProviderHealth(
                status=ProviderStatus.UNHEALTHY,
                error="API key not configured",
            )
            return self._health

        start_time = time.monotonic()

        try:
            client = await self._get_client()

            response = await client.post(
                "/chat/completions",
                headers=self._build_headers(),
                json={
                    "model": "gpt-4.1-mini",
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
