"""
Debug store for request/response storage.

Provides CRUD operations for debug data in PostgreSQL.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select

from a2c.debug.database import get_session
from a2c.debug.models import Request, SSEEvent

logger = logging.getLogger(__name__)


class DebugStore:
    """
    Store for debug request/response data.

    Provides methods to save, retrieve, and query debug data.
    """

    async def save_request(
        self,
        request_id: str,
        path: str,
        provider: str,
        request_body: dict[str, Any],
        request_headers: dict[str, str] | None = None,
        agent_type: str | None = None,
        model: str | None = None,
        matched_rule: str | None = None,
        is_streaming: bool = False,
    ) -> uuid.UUID:
        """
        Save a new request to the database.

        Args:
            request_id: Unique request identifier (e.g., req_xxx)
            path: Request path (e.g., /v1/messages)
            provider: Selected provider name
            request_body: Full request body
            request_headers: Request headers (sensitive data filtered)
            agent_type: Agent type from header
            model: Model name from request
            matched_rule: Name of matched routing rule
            is_streaming: Whether this is a streaming request

        Returns:
            Database ID of the saved request
        """
        async with get_session() as session:
            db_request = Request(
                request_id=request_id,
                path=path,
                provider=provider,
                agent_type=agent_type,
                model=model,
                matched_rule=matched_rule,
                is_streaming=is_streaming,
                request_headers=self._filter_headers(request_headers),
                request_body=request_body,
            )
            session.add(db_request)
            await session.flush()
            return db_request.id

    async def update_response(
        self,
        request_id: str,
        status_code: int,
        latency_ms: int,
        response_body: dict[str, Any] | None = None,
        response_headers: dict[str, str] | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        error: str | None = None,
        error_type: str | None = None,
    ) -> None:
        """
        Update request with response data.

        Args:
            request_id: Request identifier to update
            status_code: HTTP status code
            latency_ms: Total latency in milliseconds
            response_body: Full response body
            response_headers: Response headers
            input_tokens: Input token count
            output_tokens: Output token count
            error: Error message if any
            error_type: Error type/category
        """
        async with get_session() as session:
            stmt = select(Request).where(Request.request_id == request_id)
            result = await session.execute(stmt)
            db_request = result.scalar_one_or_none()

            if db_request:
                db_request.completed_at = datetime.utcnow()
                db_request.status_code = status_code
                db_request.latency_ms = latency_ms
                db_request.response_headers = self._filter_headers(response_headers)
                db_request.response_body = response_body
                db_request.input_tokens = input_tokens
                db_request.output_tokens = output_tokens
                db_request.error = error
                db_request.error_type = error_type

    async def save_sse_event(
        self,
        request_id: str,
        sequence: int,
        event_type: str,
        data: dict[str, Any] | None = None,
        raw_data: str | None = None,
        delta_ms: int | None = None,
    ) -> None:
        """
        Save an SSE event for a streaming request.

        Args:
            request_id: Request identifier
            sequence: Event sequence number
            event_type: SSE event type
            data: Parsed event data (JSON)
            raw_data: Raw event string
            delta_ms: Time since previous event
        """
        async with get_session() as session:
            # Get the database request ID
            stmt = select(Request.id).where(Request.request_id == request_id)
            result = await session.execute(stmt)
            db_id = result.scalar_one_or_none()

            if db_id:
                event = SSEEvent(
                    request_id=db_id,
                    sequence=sequence,
                    event_type=event_type,
                    data=data,
                    raw_data=raw_data,
                    delta_ms=delta_ms,
                )
                session.add(event)

    async def get_request(self, request_id: str) -> dict[str, Any] | None:
        """
        Get a request by ID.

        Args:
            request_id: Request identifier

        Returns:
            Request data or None if not found
        """
        async with get_session() as session:
            stmt = select(Request).where(Request.request_id == request_id)
            result = await session.execute(stmt)
            db_request = result.scalar_one_or_none()

            if db_request:
                return db_request.to_full_dict()
            return None

    async def get_request_by_uuid(self, uuid_id: uuid.UUID) -> dict[str, Any] | None:
        """
        Get a request by database UUID.

        Args:
            uuid_id: Database UUID

        Returns:
            Request data or None if not found
        """
        async with get_session() as session:
            stmt = select(Request).where(Request.id == uuid_id)
            result = await session.execute(stmt)
            db_request = result.scalar_one_or_none()

            if db_request:
                return db_request.to_full_dict()
            return None

    async def list_requests(
        self,
        limit: int = 50,
        offset: int = 0,
        provider: str | None = None,
        status_code: int | None = None,
        model: str | None = None,
        agent_type: str | None = None,
        has_error: bool | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        """
        List requests with filtering and pagination.

        Args:
            limit: Maximum number of results
            offset: Offset for pagination
            provider: Filter by provider
            status_code: Filter by status code
            model: Filter by model name
            agent_type: Filter by agent type
            has_error: Filter by error presence
            since: Filter by created_at >= since
            until: Filter by created_at <= until

        Returns:
            Dict with items, total count, and pagination info
        """
        async with get_session() as session:
            # Build query
            stmt = select(Request).order_by(Request.created_at.desc())

            # Apply filters
            if provider:
                stmt = stmt.where(Request.provider == provider)
            if status_code:
                stmt = stmt.where(Request.status_code == status_code)
            if model:
                stmt = stmt.where(Request.model.ilike(f"%{model}%"))
            if agent_type:
                stmt = stmt.where(Request.agent_type == agent_type)
            if has_error is True:
                stmt = stmt.where(Request.error.isnot(None))
            elif has_error is False:
                stmt = stmt.where(Request.error.is_(None))
            if since:
                stmt = stmt.where(Request.created_at >= since)
            if until:
                stmt = stmt.where(Request.created_at <= until)

            # Get total count
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = await session.scalar(count_stmt) or 0

            # Apply pagination
            stmt = stmt.limit(limit).offset(offset)
            result = await session.execute(stmt)
            requests = result.scalars().all()

            return {
                "items": [r.to_dict() for r in requests],
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(requests) < total,
            }

    async def get_sse_events(self, request_id: str) -> list[dict[str, Any]]:
        """
        Get SSE events for a streaming request.

        Args:
            request_id: Request identifier

        Returns:
            List of SSE events in order
        """
        async with get_session() as session:
            # Get database ID
            stmt = select(Request.id).where(Request.request_id == request_id)
            result = await session.execute(stmt)
            db_id = result.scalar_one_or_none()

            if not db_id:
                return []

            # Get events
            stmt = select(SSEEvent).where(SSEEvent.request_id == db_id).order_by(SSEEvent.sequence)
            result = await session.execute(stmt)
            events = result.scalars().all()

            return [e.to_dict() for e in events]

    async def delete_old_requests(self, days: int = 7) -> int:
        """
        Delete requests older than specified days.

        Args:
            days: Number of days to retain

        Returns:
            Number of deleted requests
        """
        async with get_session() as session:
            cutoff = datetime.utcnow() - timedelta(days=days)
            stmt = delete(Request).where(Request.created_at < cutoff)
            result = await session.execute(stmt)
            # CursorResult has rowcount, Result does not - type narrowing
            rowcount = getattr(result, "rowcount", 0)
            return rowcount or 0

    async def get_stats(
        self,
        hours: int = 24,
    ) -> dict[str, Any]:
        """
        Get aggregated statistics.

        Args:
            hours: Number of hours to look back

        Returns:
            Aggregated stats
        """
        async with get_session() as session:
            since = datetime.utcnow() - timedelta(hours=hours)

            # Total requests
            total_stmt = (
                select(func.count()).select_from(Request).where(Request.created_at >= since)
            )
            total = await session.scalar(total_stmt) or 0

            # Error count
            error_stmt = (
                select(func.count())
                .select_from(Request)
                .where(Request.created_at >= since)
                .where(Request.error.isnot(None))
            )
            errors = await session.scalar(error_stmt) or 0

            # Avg latency
            latency_stmt = select(func.avg(Request.latency_ms)).where(
                Request.created_at >= since,
                Request.latency_ms.isnot(None),
            )
            avg_latency = await session.scalar(latency_stmt)

            # Token totals
            tokens_stmt = select(
                func.sum(Request.input_tokens),
                func.sum(Request.output_tokens),
            ).where(Request.created_at >= since)
            result = await session.execute(tokens_stmt)
            row = result.one()
            input_tokens = row[0] or 0
            output_tokens = row[1] or 0

            # Requests by provider
            provider_stmt = (
                select(Request.provider, func.count())
                .where(Request.created_at >= since)
                .group_by(Request.provider)
            )
            result = await session.execute(provider_stmt)
            by_provider = {row[0]: row[1] for row in result.all()}

            return {
                "period_hours": hours,
                "total_requests": total,
                "total_errors": errors,
                "error_rate": errors / total if total > 0 else 0,
                "avg_latency_ms": round(avg_latency, 2) if avg_latency else None,
                "total_input_tokens": input_tokens,
                "total_output_tokens": output_tokens,
                "by_provider": by_provider,
            }

    def _filter_headers(self, headers: dict[str, str] | None) -> dict[str, str] | None:
        """Filter sensitive headers before storage."""
        if not headers:
            return None

        sensitive_keys = {
            "authorization",
            "x-api-key",
            "api-key",
            "x-goog-api-key",
            "cookie",
            "set-cookie",
        }

        return {k: "[REDACTED]" if k.lower() in sensitive_keys else v for k, v in headers.items()}


# Global store instance
_store: DebugStore | None = None


def get_debug_store() -> DebugStore:
    """Get the global debug store instance."""
    global _store
    if _store is None:
        _store = DebugStore()
    return _store
