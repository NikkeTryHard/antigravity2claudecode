"""
WebSocket event broadcasting for live updates.

Provides real-time updates to connected clients for:
- New requests
- Provider health changes
- Stats updates
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """WebSocket event types."""

    # Request events
    REQUEST_STARTED = "request.started"
    REQUEST_COMPLETED = "request.completed"
    REQUEST_ERROR = "request.error"

    # Provider events
    PROVIDER_HEALTH = "provider.health"
    PROVIDER_REGISTERED = "provider.registered"
    PROVIDER_REMOVED = "provider.removed"

    # Stats events
    STATS_UPDATE = "stats.update"

    # Connection events
    CONNECTED = "connected"
    PING = "ping"
    PONG = "pong"


class ConnectionManager:
    """
    Manages WebSocket connections and event broadcasting.

    Supports multiple topics for selective subscription:
    - "requests": Request lifecycle events
    - "providers": Provider health and status
    - "stats": Aggregated statistics
    - "all": All events
    """

    def __init__(self) -> None:
        """Initialize connection manager."""
        self.active_connections: dict[str, set[WebSocket]] = {
            "requests": set(),
            "providers": set(),
            "stats": set(),
            "all": set(),
        }
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, topics: list[str] | None = None) -> None:
        """
        Accept WebSocket connection and subscribe to topics.

        Args:
            websocket: WebSocket connection
            topics: List of topics to subscribe (defaults to ["all"])
        """
        await websocket.accept()

        if topics is None:
            topics = ["all"]

        async with self._lock:
            for topic in topics:
                if topic in self.active_connections:
                    self.active_connections[topic].add(websocket)

        # Send connected confirmation
        await self._send_event(
            websocket,
            EventType.CONNECTED,
            {
                "topics": topics,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        logger.debug(f"WebSocket connected, topics: {topics}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove WebSocket from all topics.

        Args:
            websocket: WebSocket connection to remove
        """
        async with self._lock:
            for connections in self.active_connections.values():
                connections.discard(websocket)

        logger.debug("WebSocket disconnected")

    async def broadcast(
        self,
        event_type: EventType,
        data: dict[str, Any],
        topic: str = "all",
    ) -> None:
        """
        Broadcast event to all connections on a topic.

        Args:
            event_type: Type of event
            data: Event payload
            topic: Topic to broadcast to
        """
        # Get connections for this topic and "all"
        async with self._lock:
            connections = set(self.active_connections.get(topic, set()))
            connections.update(self.active_connections.get("all", set()))

        if not connections:
            return

        # Create message
        message = {
            "type": event_type.value,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Send to all connections
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.debug(f"Failed to send to WebSocket: {e}")
                disconnected.append(websocket)

        # Clean up disconnected
        for websocket in disconnected:
            await self.disconnect(websocket)

    async def broadcast_request_started(
        self,
        request_id: str,
        provider: str,
        model: str | None,
        agent_type: str | None,
    ) -> None:
        """Broadcast request started event."""
        await self.broadcast(
            EventType.REQUEST_STARTED,
            {
                "request_id": request_id,
                "provider": provider,
                "model": model,
                "agent_type": agent_type,
            },
            topic="requests",
        )

    async def broadcast_request_completed(
        self,
        request_id: str,
        provider: str,
        status_code: int,
        latency_ms: int,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        """Broadcast request completed event."""
        await self.broadcast(
            EventType.REQUEST_COMPLETED,
            {
                "request_id": request_id,
                "provider": provider,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
            topic="requests",
        )

    async def broadcast_request_error(
        self,
        request_id: str,
        provider: str,
        error: str,
        error_type: str | None = None,
    ) -> None:
        """Broadcast request error event."""
        await self.broadcast(
            EventType.REQUEST_ERROR,
            {
                "request_id": request_id,
                "provider": provider,
                "error": error,
                "error_type": error_type,
            },
            topic="requests",
        )

    async def broadcast_provider_health(
        self,
        provider: str,
        status: str,
        latency_ms: float | None = None,
    ) -> None:
        """Broadcast provider health update."""
        await self.broadcast(
            EventType.PROVIDER_HEALTH,
            {
                "provider": provider,
                "status": status,
                "latency_ms": latency_ms,
            },
            topic="providers",
        )

    async def broadcast_stats_update(self, stats: dict[str, Any]) -> None:
        """Broadcast stats update."""
        await self.broadcast(
            EventType.STATS_UPDATE,
            stats,
            topic="stats",
        )

    async def _send_event(
        self,
        websocket: WebSocket,
        event_type: EventType,
        data: dict[str, Any],
    ) -> None:
        """Send event to specific connection."""
        message = {
            "type": event_type.value,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.debug(f"Failed to send event: {e}")

    @property
    def connection_count(self) -> int:
        """Get total unique connection count."""
        all_connections: set[WebSocket] = set()
        for connections in self.active_connections.values():
            all_connections.update(connections)
        return len(all_connections)


# Global connection manager
_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
