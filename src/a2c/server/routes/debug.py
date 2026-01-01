"""
Debug API endpoints for request inspection and replay.

Provides REST endpoints for querying and replaying stored requests.
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from a2c.debug import get_debug_store
from a2c.providers import get_registry
from a2c.server.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


class RequestListResponse(BaseModel):
    """Response for request list endpoint."""

    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
    has_more: bool


class StatsResponse(BaseModel):
    """Response for stats endpoint."""

    period_hours: int
    total_requests: int
    total_errors: int
    error_rate: float
    avg_latency_ms: float | None
    total_input_tokens: int
    total_output_tokens: int
    by_provider: dict[str, int]


class CleanupResponse(BaseModel):
    """Response for cleanup endpoint."""

    deleted: int
    message: str


@router.get("/requests", response_model=RequestListResponse)
async def list_requests(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    provider: str | None = Query(default=None),
    status_code: int | None = Query(default=None),
    model: str | None = Query(default=None),
    agent_type: str | None = Query(default=None),
    has_error: bool | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
) -> RequestListResponse:
    """
    List stored requests with filtering and pagination.

    Query Parameters:
        limit: Maximum results (1-100, default 50)
        offset: Pagination offset
        provider: Filter by provider name
        status_code: Filter by HTTP status code
        model: Filter by model name (partial match)
        agent_type: Filter by agent type
        has_error: Filter by error presence
        since: Filter by created_at >= since
        until: Filter by created_at <= until
    """
    settings = get_settings()

    # Return empty if database disabled
    if not settings.database.enabled:
        return RequestListResponse(
            items=[],
            total=0,
            limit=limit,
            offset=offset,
            has_more=False,
        )

    store = get_debug_store()

    result = await store.list_requests(
        limit=limit,
        offset=offset,
        provider=provider,
        status_code=status_code,
        model=model,
        agent_type=agent_type,
        has_error=has_error,
        since=since,
        until=until,
    )

    return RequestListResponse(**result)


@router.get("/requests/{request_id}")
async def get_request(request_id: str) -> dict[str, Any]:
    """
    Get a specific request by ID.

    Supports both request_id (req_xxx format) and database UUID.
    Returns full request/response data including headers and bodies.
    """
    store = get_debug_store()

    # Try to parse as UUID first
    try:
        uuid_id = uuid.UUID(request_id)
        result = await store.get_request_by_uuid(uuid_id)
    except ValueError:
        # Not a UUID, try as request_id string
        result = await store.get_request(request_id)

    if not result:
        raise HTTPException(status_code=404, detail="Request not found")

    return result


@router.get("/requests/{request_id}/events")
async def get_request_events(request_id: str) -> dict[str, Any]:
    """
    Get SSE events for a streaming request.

    Returns ordered list of SSE events with timing information.
    """
    store = get_debug_store()

    # Get request first to verify it exists
    request = await store.get_request(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if not request.get("is_streaming"):
        raise HTTPException(status_code=400, detail="Request is not a streaming request")

    events = await store.get_sse_events(request_id)

    return {
        "request_id": request_id,
        "is_streaming": True,
        "events_count": len(events),
        "events": events,
    }


@router.post("/requests/{request_id}/replay")
async def replay_request(request_id: str) -> Response:
    """
    Replay a stored request.

    Sends the original request to the same provider and returns the response.
    Useful for debugging and testing.
    """
    store = get_debug_store()
    registry = get_registry()

    # Get the original request
    original = await store.get_request(request_id)
    if not original:
        raise HTTPException(status_code=404, detail="Request not found")

    # Get the provider
    provider_name = original.get("provider")
    if not provider_name:
        raise HTTPException(status_code=400, detail="Request has no provider")

    provider = registry.get(provider_name)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' not available")

    # Get request body
    request_body = original.get("request_body")
    if not request_body:
        raise HTTPException(status_code=400, detail="Request has no body")

    # Check if streaming - for replay, force non-streaming
    if request_body.get("stream"):
        request_body = {**request_body, "stream": False}

    logger.info(f"Replaying request {request_id} to {provider_name}")

    # Send the request
    result = await provider.send_request(request_body, stream=False)

    if result.error:
        return Response(
            content=f'{{"error": {{"type": "provider_error", "message": "{result.error}"}}}}',
            status_code=result.status_code or 500,
            media_type="application/json",
            headers={
                "X-Original-Request-Id": request_id,
                "X-Provider": provider_name,
            },
        )

    return Response(
        content=str(result.body) if result.body else "{}",
        status_code=200,
        media_type="application/json",
        headers={
            "X-Original-Request-Id": request_id,
            "X-Provider": provider_name,
        },
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    hours: int = Query(default=24, ge=1, le=168),
) -> StatsResponse:
    """
    Get aggregated statistics for the specified time period.

    Query Parameters:
        hours: Number of hours to look back (1-168, default 24)

    Returns aggregated counts, latency stats, and breakdowns by provider.
    """
    settings = get_settings()

    # Return empty stats if database disabled
    if not settings.database.enabled:
        return StatsResponse(
            period_hours=hours,
            total_requests=0,
            total_errors=0,
            error_rate=0.0,
            avg_latency_ms=None,
            total_input_tokens=0,
            total_output_tokens=0,
            by_provider={},
        )

    store = get_debug_store()

    stats = await store.get_stats(hours=hours)

    return StatsResponse(**stats)


@router.delete("/cleanup")
async def cleanup_old_requests(
    days: int | None = Query(default=None, ge=1, le=30),
) -> CleanupResponse:
    """
    Delete requests older than specified days.

    Query Parameters:
        days: Number of days to retain (1-30, uses config default if not specified)

    Returns count of deleted requests.
    """
    settings = get_settings()
    store = get_debug_store()

    retention_days = days if days is not None else settings.database.retention_days

    deleted = await store.delete_old_requests(days=retention_days)

    return CleanupResponse(
        deleted=deleted,
        message=f"Deleted {deleted} requests older than {retention_days} days",
    )


@router.get("/providers")
async def list_debug_providers() -> dict[str, Any]:
    """
    List providers with debug statistics.

    Returns provider information with request counts and error rates.
    """
    store = get_debug_store()
    registry = get_registry()

    # Get stats for last 24 hours
    stats = await store.get_stats(hours=24)
    by_provider = stats.get("by_provider", {})

    providers = []
    for provider in registry.list_providers():
        request_count = by_provider.get(provider.name, 0)

        providers.append(
            {
                "name": provider.name,
                "configured": provider.is_configured,
                "healthy": provider.is_healthy,
                "request_count_24h": request_count,
            }
        )

    return {
        "providers": providers,
        "total": len(providers),
    }
