"""
Health check endpoints.

Provides liveness, readiness, and detailed health information.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Response, status

from a2c.debug import check_database_health
from a2c.providers import ProviderStatus, get_registry
from a2c.server.config import get_settings

router = APIRouter()


@router.get("/live")
async def liveness() -> dict[str, str]:
    """
    Liveness probe.

    Returns 200 if the server is running.
    Used by orchestrators to check if the process is alive.
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/ready")
async def readiness(response: Response) -> dict[str, Any]:
    """
    Readiness probe.

    Returns 200 if the server is ready to accept requests.
    Checks that at least one provider is healthy.
    """
    registry = get_registry()
    healthy_providers = registry.list_healthy_providers()
    configured_providers = registry.list_configured_providers()

    is_ready = len(healthy_providers) > 0 or len(configured_providers) > 0

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
        "providers": {
            "total": len(registry.list_providers()),
            "configured": len(configured_providers),
            "healthy": len(healthy_providers),
        },
    }


@router.get("/providers")
async def provider_health() -> dict[str, Any]:
    """
    Detailed provider health status.

    Returns health information for all registered providers.
    """
    registry = get_registry()

    providers = {}
    for provider in registry.list_providers():
        providers[provider.name] = {
            "display_name": provider.info.display_name,
            "is_configured": provider.is_configured,
            "is_healthy": provider.is_healthy,
            "health": {
                "status": provider.health.status.value,
                "latency_ms": provider.health.latency_ms,
                "last_check": provider.health.last_check.isoformat(),
                "error": provider.health.error,
            },
            "capabilities": {
                "streaming": provider.info.supports_streaming,
                "thinking": provider.info.supports_thinking,
                "tools": provider.info.supports_tools,
                "vision": provider.info.supports_vision,
                "max_context": provider.info.max_context_tokens,
            },
        }

    # Determine overall status
    all_healthy = all(p.is_healthy for p in registry.list_providers())
    any_healthy = any(p.is_healthy for p in registry.list_providers())

    if all_healthy:
        overall = "healthy"
    elif any_healthy:
        overall = "degraded"
    else:
        overall = "unhealthy"

    return {
        "status": overall,
        "timestamp": datetime.utcnow().isoformat(),
        "providers": providers,
    }


@router.post("/providers/{name}/check")
async def check_provider(name: str, response: Response) -> dict[str, Any]:
    """
    Trigger health check for a specific provider.

    Args:
        name: Provider name to check
    """
    registry = get_registry()
    provider = registry.get(name)

    if not provider:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"error": f"Provider '{name}' not found"}

    health = await provider.health_check()

    return {
        "provider": name,
        "health": {
            "status": health.status.value,
            "latency_ms": health.latency_ms,
            "last_check": health.last_check.isoformat(),
            "error": health.error,
        },
    }


@router.get("")
async def health_summary() -> dict[str, Any]:
    """
    Overall health summary.

    Returns a summary of server and provider health.
    """
    settings = get_settings()
    registry = get_registry()

    providers = registry.list_providers()
    healthy = [p for p in providers if p.is_healthy]
    degraded = [p for p in providers if p.health.status == ProviderStatus.DEGRADED]
    unhealthy = [
        p
        for p in providers
        if p.health.status in (ProviderStatus.UNHEALTHY, ProviderStatus.UNKNOWN)
    ]

    # Check database health if enabled
    database_health = None
    if settings.database.enabled:
        database_health = await check_database_health()

    return {
        "server": {
            "status": "running",
            "version": "0.1.0",
            "host": settings.server.host,
            "port": settings.server.port,
            "debug": settings.server.debug_enabled,
        },
        "providers": {
            "total": len(providers),
            "healthy": len(healthy),
            "degraded": len(degraded),
            "unhealthy": len(unhealthy),
            "names": {
                "healthy": [p.name for p in healthy],
                "degraded": [p.name for p in degraded],
                "unhealthy": [p.name for p in unhealthy],
            },
        },
        "database": database_health,
        "timestamp": datetime.utcnow().isoformat(),
    }
