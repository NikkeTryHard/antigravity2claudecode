"""
Admin API endpoints.

Provides configuration, provider management, and routing control.
"""

from typing import Any

from fastapi import APIRouter, Response, status

from a2c.debug import get_debug_store
from a2c.providers import get_registry
from a2c.router import get_router
from a2c.server.config import get_settings, get_settings_dict

router = APIRouter()


@router.get("/config")
async def get_config() -> dict[str, Any]:
    """
    Get current server configuration.

    Returns non-sensitive configuration values.
    """
    return get_settings_dict()


@router.get("/providers")
async def list_providers() -> dict[str, Any]:
    """
    List all registered providers with their status.
    """
    registry = get_registry()
    return registry.to_dict()


@router.get("/providers/{name}")
async def get_provider(name: str, response: Response) -> dict[str, Any]:
    """
    Get details for a specific provider.
    """
    registry = get_registry()
    provider = registry.get(name)

    if not provider:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"error": f"Provider '{name}' not found"}

    return provider.to_dict()


@router.post("/providers/{name}/test")
async def test_provider(name: str, response: Response) -> dict[str, Any]:
    """
    Test provider connectivity.

    Triggers a health check and returns the result.
    """
    registry = get_registry()
    provider = registry.get(name)

    if not provider:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"error": f"Provider '{name}' not found"}

    health = await provider.health_check()

    return {
        "provider": name,
        "success": health.status.value == "healthy",
        "health": {
            "status": health.status.value,
            "latency_ms": health.latency_ms,
            "error": health.error,
        },
    }


@router.get("/routing/rules")
async def get_routing_rules() -> dict[str, Any]:
    """
    Get current routing rules.
    """
    routing = get_router()
    return routing.to_dict()


@router.get("/routing/test")
async def test_routing(
    model: str = "claude-opus-4-5",
    thinking: bool = False,
    agent_type: str | None = None,
    context_tokens: int = 0,
) -> dict[str, Any]:
    """
    Test routing for a hypothetical request.

    Args:
        model: Model name
        thinking: Whether thinking is enabled
        agent_type: Agent type header value
        context_tokens: Estimated context tokens
    """
    routing = get_router()

    # Build test request
    test_request = {
        "model": model,
        "messages": [],
    }

    if thinking:
        test_request["thinking"] = {"type": "enabled"}

    # Select provider
    provider_name = routing.select_provider(
        request=test_request,
        agent_type=agent_type,
        context_tokens=context_tokens,
    )

    # Get matching rule
    matching_rule = routing.get_matching_rule(
        request=test_request,
        agent_type=agent_type,
        context_tokens=context_tokens,
    )

    return {
        "input": {
            "model": model,
            "thinking": thinking,
            "agent_type": agent_type,
            "context_tokens": context_tokens,
        },
        "result": {
            "provider": provider_name,
            "rule": matching_rule,
        },
    }


@router.get("/stats")
async def get_stats(hours: int = 24) -> dict[str, Any]:
    """
    Get server statistics.

    Returns request counts, latency, and usage metrics.

    Args:
        hours: Number of hours to look back (default 24)
    """
    settings = get_settings()

    # Return empty stats if database not enabled
    if not settings.database.enabled:
        return {
            "period_hours": hours,
            "requests": {"total": 0, "success": 0, "errors": 0},
            "latency": {"avg_ms": None},
            "tokens": {"input": 0, "output": 0},
            "by_provider": {},
        }

    store = get_debug_store()
    stats = await store.get_stats(hours=hours)

    # Calculate success/error counts
    total = stats.get("total_requests", 0)
    errors = stats.get("total_errors", 0)

    return {
        "period_hours": stats.get("period_hours", hours),
        "requests": {
            "total": total,
            "success": total - errors,
            "errors": errors,
            "error_rate": stats.get("error_rate", 0),
        },
        "latency": {
            "avg_ms": stats.get("avg_latency_ms"),
        },
        "tokens": {
            "input": stats.get("total_input_tokens", 0),
            "output": stats.get("total_output_tokens", 0),
        },
        "by_provider": stats.get("by_provider", {}),
    }
