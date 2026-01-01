"""
Anthropic Messages API endpoint.

Handles /v1/messages requests and routes them to the appropriate provider.
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import StreamingResponse

from a2c.providers import get_registry
from a2c.router import get_router
from a2c.server.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/messages")
async def create_message(
    request: Request,
    response: Response,
    x_api_key: str | None = Header(None),
    anthropic_version: str | None = Header(None, alias="anthropic-version"),
    x_agent_type: str | None = Header(None, alias="x-agent-type"),
) -> Any:
    """
    Create a message (Anthropic Messages API).

    Accepts Anthropic-format requests and routes them to the appropriate
    provider based on routing rules.

    Headers:
        x-api-key: API key (optional, uses configured provider key)
        anthropic-version: Anthropic API version
        x-agent-type: Override agent type for routing

    Request Body:
        Standard Anthropic Messages API request format
    """
    settings = get_settings()
    registry = get_registry()
    routing = get_router()

    # Parse request body
    try:
        body = await request.json()
    except Exception as e:
        return Response(
            content=f'{{"error": {{"type": "invalid_request_error", "message": "Invalid JSON: {e}"}}}}',
            status_code=400,
            media_type="application/json",
        )

    # Generate request ID for tracking
    request_id = f"req_{uuid.uuid4().hex[:24]}"

    # Determine if streaming
    is_streaming = body.get("stream", False)

    # Select provider using routing rules
    try:
        provider_name = routing.select_provider(
            request=body,
            agent_type=x_agent_type,
        )
    except Exception as e:
        logger.error(f"Routing error: {e}")
        return Response(
            content=f'{{"error": {{"type": "routing_error", "message": "{e}"}}}}',
            status_code=500,
            media_type="application/json",
        )

    # Get provider
    provider = registry.get(provider_name)
    if not provider:
        # Fallback to first available provider
        providers = registry.list_configured_providers()
        if not providers:
            return Response(
                content='{"error": {"type": "configuration_error", "message": "No providers configured"}}',
                status_code=503,
                media_type="application/json",
            )
        provider = providers[0]
        logger.warning(f"Provider '{provider_name}' not found, using fallback: {provider.name}")

    logger.info(
        f"[{request_id}] Routing to {provider.name} "
        f"(model={body.get('model')}, stream={is_streaming}, agent={x_agent_type or 'default'})"
    )

    # Handle streaming response
    if is_streaming:
        return StreamingResponse(
            provider.stream_response(body),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-Id": request_id,
                "X-Provider": provider.name,
            },
        )

    # Handle non-streaming response
    result = await provider.send_request(body, stream=False)

    if result.error:
        return Response(
            content=f'{{"error": {{"type": "provider_error", "message": "{result.error}"}}}}',
            status_code=result.status_code or 500,
            media_type="application/json",
            headers={
                "X-Request-Id": request_id,
                "X-Provider": provider.name,
            },
        )

    # Add tracking headers
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Provider"] = provider.name

    return result.body


@router.get("/models")
async def list_models() -> dict[str, Any]:
    """
    List available models.

    Returns models from all configured providers.
    """
    registry = get_registry()

    models = []

    for provider in registry.list_configured_providers():
        if provider.name == "anthropic":
            models.extend(
                [
                    {
                        "id": "claude-opus-4-5-20251101",
                        "provider": "anthropic",
                        "display_name": "Claude Opus 4.5",
                        "supports_thinking": True,
                    },
                    {
                        "id": "claude-sonnet-4-5-20250929",
                        "provider": "anthropic",
                        "display_name": "Claude Sonnet 4.5",
                        "supports_thinking": True,
                    },
                    {
                        "id": "claude-3-5-sonnet-20241022",
                        "provider": "anthropic",
                        "display_name": "Claude 3.5 Sonnet",
                        "supports_thinking": False,
                    },
                    {
                        "id": "claude-3-haiku-20240307",
                        "provider": "anthropic",
                        "display_name": "Claude 3 Haiku",
                        "supports_thinking": False,
                    },
                ]
            )
        elif provider.name == "antigravity":
            models.extend(
                [
                    {
                        "id": "claude-opus-4-5",
                        "provider": "antigravity",
                        "display_name": "Claude Opus 4.5 (Antigravity)",
                        "supports_thinking": True,
                    },
                    {
                        "id": "claude-sonnet-4-5",
                        "provider": "antigravity",
                        "display_name": "Claude Sonnet 4.5 (Antigravity)",
                        "supports_thinking": True,
                    },
                    {
                        "id": "gemini-2.5-pro",
                        "provider": "antigravity",
                        "display_name": "Gemini 2.5 Pro",
                        "supports_thinking": True,
                    },
                    {
                        "id": "gemini-2.5-flash",
                        "provider": "antigravity",
                        "display_name": "Gemini 2.5 Flash",
                        "supports_thinking": False,
                    },
                ]
            )

    return {
        "models": models,
        "total": len(models),
    }
