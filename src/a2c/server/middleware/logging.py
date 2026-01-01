"""
Request logging middleware for debug storage.

Captures request/response data and stores it in the debug database.
"""

import json
import logging
import time
import uuid
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from a2c.debug import get_debug_store
from a2c.server.config import get_settings
from a2c.server.websocket.events import get_connection_manager

logger = logging.getLogger(__name__)


class DebugLoggingMiddleware:
    """
    Pure ASGI middleware that logs requests and responses to the debug store.

    Captures:
    - Request path, method, headers, body
    - Response status, headers, body
    - Latency and token usage
    - SSE events for streaming responses

    Uses pure ASGI to properly handle request body caching and replaying,
    avoiding the body double-read issue from BaseHTTPMiddleware.
    """

    # Paths to log (only API paths)
    LOGGED_PATHS = ["/v1/messages", "/v1/chat/completions"]

    # Paths to skip
    SKIP_PATHS = ["/health", "/admin", "/debug", "/docs", "/redoc", "/openapi.json"]

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI interface."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = get_settings()

        # Skip if debug is disabled
        if not settings.database.enabled:
            await self.app(scope, receive, send)
            return

        # Skip non-logged paths
        path = scope["path"]
        if not self._should_log(path):
            await self.app(scope, receive, send)
            return

        # Generate request ID and store in scope state
        request_id = f"req_{uuid.uuid4().hex[:24]}"
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id

        # Start timing
        start_time = time.perf_counter()

        # Collect and cache request body
        body_chunks: list[bytes] = []
        body_received = False

        async def receive_wrapper() -> Message:
            nonlocal body_received
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if body:
                    body_chunks.append(body)
                if not message.get("more_body", False):
                    body_received = True
            return message

        # Create a replay receive for downstream
        async def receive_replay() -> Message:
            if body_chunks:
                # Return cached body in one chunk
                full_body = b"".join(body_chunks)
                body_chunks.clear()  # Only send once
                return {"type": "http.request", "body": full_body, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        # Read the body first for logging
        while not body_received:
            await receive_wrapper()

        full_body = b"".join(body_chunks)
        request_body = self._parse_body(full_body)
        request_headers = dict(
            (k.decode("utf-8"), v.decode("utf-8")) for k, v in scope.get("headers", [])
        )

        # Determine provider and agent type from routing
        provider = scope.get("state", {}).get("provider")
        agent_type = request_headers.get("x-agent-type")
        model = request_body.get("model") if request_body else None
        is_streaming = request_body.get("stream", False) if request_body else False

        # Save initial request
        store = get_debug_store()
        ws_manager = get_connection_manager()
        provider_name = provider or "unknown"

        try:
            await store.save_request(
                request_id=request_id,
                path=path,
                provider=provider_name,
                request_body=request_body or {},
                request_headers=request_headers,
                agent_type=agent_type,
                model=model,
                is_streaming=is_streaming,
            )
            # Broadcast request started event
            await ws_manager.broadcast_request_started(
                request_id=request_id,
                provider=provider_name,
                model=model,
                agent_type=agent_type,
            )
        except Exception as e:
            logger.warning(f"Failed to save request: {e}")

        # Refill body_chunks so replay can work
        body_chunks.append(full_body)

        # Capture response
        response_status = 0
        response_headers: dict[str, str] = {}
        response_body_chunks: list[bytes] = []
        is_streaming_response = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_status, response_headers, is_streaming_response

            if message["type"] == "http.response.start":
                response_status = message["status"]
                response_headers = dict(
                    (k.decode("utf-8"), v.decode("utf-8")) for k, v in message.get("headers", [])
                )
                # Check if SSE streaming
                content_type = response_headers.get("content-type", "")
                is_streaming_response = "text/event-stream" in content_type

            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body:
                    response_body_chunks.append(body)

            await send(message)

        # Call the downstream app
        try:
            await self.app(scope, receive_replay, send_wrapper)
        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            await self._update_with_error(
                store, ws_manager, request_id, provider_name, latency_ms, str(e), type(e).__name__
            )
            raise

        # Calculate latency
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Update with response
        if is_streaming_response and is_streaming:
            # For SSE, parse events from collected chunks
            await self._process_sse_response(
                store,
                ws_manager,
                request_id,
                provider_name,
                response_body_chunks,
                response_status,
                latency_ms,
            )
        else:
            # For regular responses
            response_body = self._parse_body(b"".join(response_body_chunks))
            await self._update_with_response_data(
                store,
                ws_manager,
                request_id,
                provider_name,
                response_status,
                response_body,
                response_headers,
                latency_ms,
            )

    def _should_log(self, path: str) -> bool:
        """Check if this path should be logged."""
        for skip in self.SKIP_PATHS:
            if path.startswith(skip):
                return False

        for logged in self.LOGGED_PATHS:
            if path.startswith(logged):
                return True

        return False

    def _parse_body(self, body: bytes) -> dict[str, Any] | None:
        """Parse body as JSON."""
        if not body:
            return None
        try:
            return json.loads(body)
        except Exception:
            return None

    async def _update_with_response_data(
        self,
        store: Any,
        ws_manager: Any,
        request_id: str,
        provider: str,
        status_code: int,
        response_body: dict[str, Any] | None,
        response_headers: dict[str, str],
        latency_ms: int,
    ) -> None:
        """Update request record with response data."""
        try:
            # Extract token usage from response
            input_tokens = None
            output_tokens = None
            if response_body and "usage" in response_body:
                usage = response_body["usage"]
                input_tokens = usage.get("input_tokens")
                output_tokens = usage.get("output_tokens")

            # Check for error
            error = None
            error_type = None
            if response_body and "error" in response_body:
                error_info = response_body["error"]
                error = error_info.get("message", str(error_info))
                error_type = error_info.get("type", "unknown")

            await store.update_response(
                request_id=request_id,
                status_code=status_code,
                latency_ms=latency_ms,
                response_body=response_body,
                response_headers=response_headers,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                error=error,
                error_type=error_type,
            )

            # Broadcast completion or error event
            if error:
                await ws_manager.broadcast_request_error(
                    request_id=request_id,
                    provider=provider,
                    error=error,
                    error_type=error_type,
                )
            else:
                await ws_manager.broadcast_request_completed(
                    request_id=request_id,
                    provider=provider,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
        except Exception as e:
            logger.warning(f"Failed to update response: {e}")

    async def _update_with_error(
        self,
        store: Any,
        ws_manager: Any,
        request_id: str,
        provider: str,
        latency_ms: int,
        error: str,
        error_type: str,
    ) -> None:
        """Update request record with error data."""
        try:
            await store.update_response(
                request_id=request_id,
                status_code=500,
                latency_ms=latency_ms,
                error=error,
                error_type=error_type,
            )
            # Broadcast error event
            await ws_manager.broadcast_request_error(
                request_id=request_id,
                provider=provider,
                error=error,
                error_type=error_type,
            )
        except Exception as e:
            logger.warning(f"Failed to update error: {e}")

    async def _process_sse_response(
        self,
        store: Any,
        ws_manager: Any,
        request_id: str,
        provider: str,
        response_chunks: list[bytes],
        status_code: int,
        latency_ms: int,
    ) -> None:
        """Process collected SSE response chunks and update the store."""
        total_input_tokens = 0
        total_output_tokens = 0
        error = None
        error_type = None
        sequence = 0

        # Process all chunks
        full_data = b"".join(response_chunks).decode("utf-8", errors="replace")

        # Split into SSE events (events are separated by double newlines)
        for chunk_str in full_data.split("\n\n"):
            if not chunk_str.strip():
                continue

            event_data = self._parse_sse_event(chunk_str)

            if event_data:
                event_type_parsed = event_data.get("event", "message")
                data = event_data.get("data")

                # Extract token usage
                if data and isinstance(data, dict):
                    if "usage" in data:
                        usage = data["usage"]
                        total_input_tokens = usage.get("input_tokens", total_input_tokens)
                        total_output_tokens = usage.get("output_tokens", total_output_tokens)

                    # Check for error in stream
                    if "error" in data:
                        error_info = data["error"]
                        error = error_info.get("message", str(error_info))
                        error_type = error_info.get("type", "stream_error")

                # Save SSE event
                await self._save_sse_event(
                    store,
                    request_id,
                    sequence,
                    event_type_parsed,
                    data,
                    chunk_str,
                    0,  # Delta not available post-hoc
                )
                sequence += 1

        # Update request with final stats
        try:
            await store.update_response(
                request_id=request_id,
                status_code=status_code,
                latency_ms=latency_ms,
                input_tokens=total_input_tokens if total_input_tokens else None,
                output_tokens=total_output_tokens if total_output_tokens else None,
                error=error,
                error_type=error_type,
            )

            # Broadcast completion or error event
            if error:
                await ws_manager.broadcast_request_error(
                    request_id=request_id,
                    provider=provider,
                    error=error,
                    error_type=error_type,
                )
            else:
                await ws_manager.broadcast_request_completed(
                    request_id=request_id,
                    provider=provider,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    input_tokens=total_input_tokens if total_input_tokens else None,
                    output_tokens=total_output_tokens if total_output_tokens else None,
                )
        except Exception as e:
            logger.warning(f"Failed to update streaming response: {e}")

    def _parse_sse_event(self, chunk: str) -> dict[str, Any] | None:
        """Parse an SSE event from a chunk."""

        event_type = "message"
        data = None

        for line in chunk.strip().split("\n"):
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    return {"event": "done", "data": None}
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    data = data_str

        if data is not None or event_type != "message":
            return {"event": event_type, "data": data}

        return None

    async def _save_sse_event(
        self,
        store: Any,
        request_id: str,
        sequence: int,
        event_type: str,
        data: dict[str, Any] | None,
        raw_data: str,
        delta_ms: int,
    ) -> None:
        """Save an SSE event to the store."""
        try:
            await store.save_sse_event(
                request_id=request_id,
                sequence=sequence,
                event_type=event_type,
                data=data,
                raw_data=raw_data,
                delta_ms=delta_ms,
            )
        except Exception as e:
            logger.debug(f"Failed to save SSE event: {e}")
