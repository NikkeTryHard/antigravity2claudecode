"""
WebSocket route handlers.

Provides WebSocket endpoints for real-time updates.
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from a2c.server.websocket.events import EventType, get_connection_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/live")
async def websocket_live(
    websocket: WebSocket,
    topics: str = Query(
        default="all", description="Comma-separated topics: requests,providers,stats,all"
    ),
) -> None:
    """
    WebSocket endpoint for live updates.

    Query Parameters:
        topics: Comma-separated list of topics to subscribe to

    Events sent:
        - connected: Initial connection confirmation
        - request.started: New request started
        - request.completed: Request completed
        - request.error: Request error
        - provider.health: Provider health change
        - stats.update: Stats update

    Messages received:
        - ping: Respond with pong
    """
    manager = get_connection_manager()
    topic_list = [t.strip() for t in topics.split(",")]

    await manager.connect(websocket, topic_list)

    try:
        while True:
            try:
                # Receive messages (for ping/pong)
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30)

                if data.get("type") == "ping":
                    await websocket.send_json(
                        {
                            "type": EventType.PONG.value,
                            "data": {},
                        }
                    )

            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json(
                        {
                            "type": EventType.PING.value,
                            "data": {},
                        }
                    )
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        await manager.disconnect(websocket)


@router.websocket("/requests/stream")
async def websocket_requests_stream(websocket: WebSocket) -> None:
    """
    WebSocket endpoint specifically for request events.

    Subscribes only to the "requests" topic.
    """
    manager = get_connection_manager()

    await manager.connect(websocket, ["requests"])

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30)
                if data.get("type") == "ping":
                    await websocket.send_json({"type": EventType.PONG.value, "data": {}})
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": EventType.PING.value, "data": {}})
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        await manager.disconnect(websocket)


@router.get("/connections")
async def get_connections() -> dict[str, Any]:
    """
    Get WebSocket connection info.

    Returns current connection count and topic subscriptions.
    """
    manager = get_connection_manager()

    return {
        "total_connections": manager.connection_count,
        "topics": {
            topic: len(connections) for topic, connections in manager.active_connections.items()
        },
    }
