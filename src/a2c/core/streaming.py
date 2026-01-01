"""
Convert Google Antigravity SSE streams to Anthropic Messages Streaming SSE format.

This module handles the real-time conversion of Server-Sent Events (SSE) from
Google's Antigravity API format to Anthropic's Messages API streaming format,
with full support for extended thinking blocks and signatures.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, Protocol

from .helpers import anthropic_debug_enabled, remove_nulls_for_tool_input

logger = logging.getLogger(__name__)


class CredentialManager(Protocol):
    """Protocol for credential managers that can record API call results."""

    async def record_api_call_result(
        self, credential_name: str, success: bool, is_antigravity: bool = False
    ) -> None:
        """Record the result of an API call for a credential."""
        ...


def _sse_event(event: str, data: dict[str, Any]) -> bytes:
    """Format an SSE event with the given event type and JSON data."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n".encode()


class _StreamingState:
    """Internal state tracker for streaming conversion."""

    def __init__(self, message_id: str, model: str):
        self.message_id = message_id
        self.model = model

        self._current_block_type: str | None = None
        self._current_block_index: int = -1
        self._current_thinking_signature: str | None = None

        self.has_tool_use: bool = False
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.has_input_tokens: bool = False
        self.has_output_tokens: bool = False
        self.finish_reason: str | None = None

    def _next_index(self) -> int:
        self._current_block_index += 1
        return self._current_block_index

    def close_block_if_open(self) -> bytes | None:
        """Close current content block if one is open."""
        if self._current_block_type is None:
            return None
        event = _sse_event(
            "content_block_stop",
            {"type": "content_block_stop", "index": self._current_block_index},
        )
        self._current_block_type = None
        self._current_thinking_signature = None
        return event

    def open_text_block(self) -> bytes:
        """Open a new text content block."""
        idx = self._next_index()
        self._current_block_type = "text"
        return _sse_event(
            "content_block_start",
            {
                "type": "content_block_start",
                "index": idx,
                "content_block": {"type": "text", "text": ""},
            },
        )

    def open_thinking_block(self, signature: str | None) -> bytes:
        """Open a new thinking content block with optional signature."""
        idx = self._next_index()
        self._current_block_type = "thinking"
        self._current_thinking_signature = signature
        block: dict[str, Any] = {"type": "thinking", "thinking": ""}
        if signature:
            block["signature"] = signature
        return _sse_event(
            "content_block_start",
            {
                "type": "content_block_start",
                "index": idx,
                "content_block": block,
            },
        )


async def antigravity_sse_to_anthropic_sse(
    lines: AsyncIterator[str],
    *,
    model: str,
    message_id: str,
    initial_input_tokens: int = 0,
    credential_manager: CredentialManager | None = None,
    credential_name: str | None = None,
    client_thinking_enabled: bool = True,
    thinking_to_text: bool = False,
) -> AsyncIterator[bytes]:
    """
    Convert Antigravity SSE (data: {...}) to Anthropic Messages Streaming SSE.

    Args:
        lines: Async iterator of SSE lines from Antigravity API
        model: Model name to include in response
        message_id: Unique message ID for correlation
        initial_input_tokens: Estimated input tokens (fallback if not in response)
        credential_manager: Optional manager to record API call results
        credential_name: Name of credential used (for recording)
        client_thinking_enabled: If False, thinking blocks are filtered/converted
        thinking_to_text: If True and thinking disabled, convert thinking to text
                         wrapped in <assistant_thinking> tags (preserves context).
                         If False and thinking disabled, thinking is stripped.

    Yields:
        Encoded SSE event bytes in Anthropic format
    """
    state = _StreamingState(message_id=message_id, model=model)
    success_recorded = False
    message_start_sent = False
    pending_output: list[bytes] = []
    # Buffer for thinking content when converting to text
    thinking_text_buffer: str = ""

    try:
        initial_input_tokens_int = max(0, int(initial_input_tokens or 0))
    except Exception:
        initial_input_tokens_int = 0

    def pick_usage_metadata(
        response: dict[str, Any], candidate: dict[str, Any]
    ) -> dict[str, Any]:
        """Pick the more complete usage metadata from response or candidate."""
        response_usage = response.get("usageMetadata", {}) or {}
        if not isinstance(response_usage, dict):
            response_usage = {}

        candidate_usage = candidate.get("usageMetadata", {}) or {}
        if not isinstance(candidate_usage, dict):
            candidate_usage = {}

        fields = ("promptTokenCount", "candidatesTokenCount", "totalTokenCount")

        def score(d: dict[str, Any]) -> int:
            s = 0
            for f in fields:
                if f in d and d.get(f) is not None:
                    s += 1
            return s

        if score(candidate_usage) > score(response_usage):
            return candidate_usage
        return response_usage

    def enqueue(evt: bytes) -> None:
        pending_output.append(evt)

    def flush_pending_ready(ready: list[bytes]) -> None:
        if not pending_output:
            return
        ready.extend(pending_output)
        pending_output.clear()

    def send_message_start(ready: list[bytes], *, input_tokens: int) -> None:
        nonlocal message_start_sent
        if message_start_sent:
            return
        message_start_sent = True
        ready.append(
            _sse_event(
                "message_start",
                {
                    "type": "message_start",
                    "message": {
                        "id": message_id,
                        "type": "message",
                        "role": "assistant",
                        "model": model,
                        "content": [],
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {
                            "input_tokens": int(input_tokens or 0),
                            "output_tokens": 0,
                        },
                    },
                },
            )
        )
        flush_pending_ready(ready)

    try:
        async for line in lines:
            ready_output: list[bytes] = []
            if not line or not line.startswith("data: "):
                continue

            raw = line[6:].strip()
            if raw == "[DONE]":
                break

            if not success_recorded and credential_manager and credential_name:
                await credential_manager.record_api_call_result(
                    credential_name, True, is_antigravity=True
                )
                success_recorded = True

            try:
                data = json.loads(raw)
            except Exception:
                continue

            response = data.get("response", {}) or {}
            candidate = (response.get("candidates", []) or [{}])[0] or {}
            parts = (candidate.get("content", {}) or {}).get("parts", []) or []

            # Capture usageMetadata from any chunk
            if isinstance(response, dict) and isinstance(candidate, dict):
                usage = pick_usage_metadata(response, candidate)
                if isinstance(usage, dict):
                    if "promptTokenCount" in usage:
                        state.input_tokens = int(usage.get("promptTokenCount", 0) or 0)
                        state.has_input_tokens = True
                    if "candidatesTokenCount" in usage:
                        state.output_tokens = int(
                            usage.get("candidatesTokenCount", 0) or 0
                        )
                        state.has_output_tokens = True

            # Ensure message_start is always the first event
            if state.has_input_tokens and not message_start_sent:
                send_message_start(ready_output, input_tokens=state.input_tokens)

            for part in parts:
                if not isinstance(part, dict):
                    continue

                if anthropic_debug_enabled() and "thoughtSignature" in part:
                    try:
                        sig_val = part.get("thoughtSignature")
                        sig_len = len(str(sig_val)) if sig_val is not None else 0
                    except Exception:
                        sig_len = -1
                    logger.info(
                        "[ANTHROPIC][thinking_signature] Received thoughtSignature: "
                        f"current_block_type={state._current_block_type}, "
                        f"current_index={state._current_block_index}, len={sig_len}",
                    )

                # Handle signature delta for thinking blocks
                signature = part.get("thoughtSignature")
                if (
                    signature
                    and state._current_block_type == "thinking"
                    and not state._current_thinking_signature
                ):
                    evt = _sse_event(
                        "content_block_delta",
                        {
                            "type": "content_block_delta",
                            "index": state._current_block_index,
                            "delta": {
                                "type": "signature_delta",
                                "signature": signature,
                            },
                        },
                    )
                    state._current_thinking_signature = str(signature)
                    if message_start_sent:
                        ready_output.append(evt)
                    else:
                        enqueue(evt)
                    if anthropic_debug_enabled():
                        logger.info(
                            "[ANTHROPIC][thinking_signature] Emitted signature_delta: "
                            f"index={state._current_block_index}",
                        )

                if part.get("thought") is True:
                    thinking_text = part.get("text", "")

                    # Handle thinking based on client preference
                    if not client_thinking_enabled:
                        # Client requested thinking disabled
                        if thinking_to_text and thinking_text:
                            # Buffer thinking content to prepend to next text block
                            thinking_text_buffer += thinking_text
                        # Skip emitting thinking blocks entirely
                        continue

                    # Client wants thinking - emit native thinking blocks
                    if state._current_block_type != "thinking":
                        stop_evt = state.close_block_if_open()
                        if stop_evt:
                            if message_start_sent:
                                ready_output.append(stop_evt)
                            else:
                                enqueue(stop_evt)
                        signature = part.get("thoughtSignature")
                        evt = state.open_thinking_block(signature=signature)
                        if message_start_sent:
                            ready_output.append(evt)
                        else:
                            enqueue(evt)
                    if thinking_text:
                        evt = _sse_event(
                            "content_block_delta",
                            {
                                "type": "content_block_delta",
                                "index": state._current_block_index,
                                "delta": {
                                    "type": "thinking_delta",
                                    "thinking": thinking_text,
                                },
                            },
                        )
                        if message_start_sent:
                            ready_output.append(evt)
                        else:
                            enqueue(evt)
                    continue

                if "text" in part:
                    text = part.get("text", "")
                    if isinstance(text, str) and not text.strip():
                        continue

                    if state._current_block_type != "text":
                        stop_evt = state.close_block_if_open()
                        if stop_evt:
                            if message_start_sent:
                                ready_output.append(stop_evt)
                            else:
                                enqueue(stop_evt)
                        evt = state.open_text_block()
                        if message_start_sent:
                            ready_output.append(evt)
                        else:
                            enqueue(evt)

                    # Flush buffered thinking content as text (wrapped in tags)
                    if thinking_text_buffer:
                        wrapped_thinking = f"<assistant_thinking>\n{thinking_text_buffer}</assistant_thinking>\n\n"
                        evt = _sse_event(
                            "content_block_delta",
                            {
                                "type": "content_block_delta",
                                "index": state._current_block_index,
                                "delta": {
                                    "type": "text_delta",
                                    "text": wrapped_thinking,
                                },
                            },
                        )
                        if message_start_sent:
                            ready_output.append(evt)
                        else:
                            enqueue(evt)
                        thinking_text_buffer = ""

                    if text:
                        evt = _sse_event(
                            "content_block_delta",
                            {
                                "type": "content_block_delta",
                                "index": state._current_block_index,
                                "delta": {"type": "text_delta", "text": text},
                            },
                        )
                        if message_start_sent:
                            ready_output.append(evt)
                        else:
                            enqueue(evt)
                    continue

                if "inlineData" in part:
                    stop_evt = state.close_block_if_open()
                    if stop_evt:
                        if message_start_sent:
                            ready_output.append(stop_evt)
                        else:
                            enqueue(stop_evt)

                    inline = part.get("inlineData", {}) or {}
                    idx = state._next_index()
                    block = {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": inline.get("mimeType", "image/png"),
                            "data": inline.get("data", ""),
                        },
                    }
                    evt1 = _sse_event(
                        "content_block_start",
                        {
                            "type": "content_block_start",
                            "index": idx,
                            "content_block": block,
                        },
                    )
                    evt2 = _sse_event(
                        "content_block_stop",
                        {"type": "content_block_stop", "index": idx},
                    )
                    if message_start_sent:
                        ready_output.extend([evt1, evt2])
                    else:
                        enqueue(evt1)
                        enqueue(evt2)
                    continue

                if "functionCall" in part:
                    stop_evt = state.close_block_if_open()
                    if stop_evt:
                        if message_start_sent:
                            ready_output.append(stop_evt)
                        else:
                            enqueue(stop_evt)

                    state.has_tool_use = True

                    fc = part.get("functionCall", {}) or {}
                    tool_id = fc.get("id") or f"toolu_{uuid.uuid4().hex}"
                    tool_name = fc.get("name") or ""
                    tool_args = remove_nulls_for_tool_input(fc.get("args", {}) or {})

                    idx = state._next_index()
                    evt_start = _sse_event(
                        "content_block_start",
                        {
                            "type": "content_block_start",
                            "index": idx,
                            "content_block": {
                                "type": "tool_use",
                                "id": tool_id,
                                "name": tool_name,
                                "input": {},
                            },
                        },
                    )

                    input_json = json.dumps(
                        tool_args, ensure_ascii=False, separators=(",", ":")
                    )
                    evt_delta = _sse_event(
                        "content_block_delta",
                        {
                            "type": "content_block_delta",
                            "index": idx,
                            "delta": {
                                "type": "input_json_delta",
                                "partial_json": input_json,
                            },
                        },
                    )
                    evt_stop = _sse_event(
                        "content_block_stop",
                        {"type": "content_block_stop", "index": idx},
                    )
                    if message_start_sent:
                        ready_output.extend([evt_start, evt_delta, evt_stop])
                    else:
                        enqueue(evt_start)
                        enqueue(evt_delta)
                        enqueue(evt_stop)
                    continue

            finish_reason = candidate.get("finishReason")

            if ready_output:
                for evt in ready_output:
                    yield evt

            if finish_reason:
                state.finish_reason = str(finish_reason)
                break

        # Flush any remaining thinking buffer as a text block
        if thinking_text_buffer:
            # Close any open block first
            stop_evt = state.close_block_if_open()
            if stop_evt:
                if message_start_sent:
                    yield stop_evt
                else:
                    enqueue(stop_evt)

            # Open a new text block for the buffered thinking
            evt = state.open_text_block()
            if message_start_sent:
                yield evt
            else:
                enqueue(evt)

            wrapped_thinking = (
                f"<assistant_thinking>\n{thinking_text_buffer}</assistant_thinking>"
            )
            evt = _sse_event(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": state._current_block_index,
                    "delta": {"type": "text_delta", "text": wrapped_thinking},
                },
            )
            if message_start_sent:
                yield evt
            else:
                enqueue(evt)

        stop_evt = state.close_block_if_open()
        if stop_evt:
            if message_start_sent:
                yield stop_evt
            else:
                enqueue(stop_evt)

        # Send message_start with fallback tokens if not sent yet
        if not message_start_sent:
            ready_output = []
            send_message_start(ready_output, input_tokens=initial_input_tokens_int)
            for evt in ready_output:
                yield evt

        stop_reason = "tool_use" if state.has_tool_use else "end_turn"
        if state.finish_reason == "MAX_TOKENS" and not state.has_tool_use:
            stop_reason = "max_tokens"

        if anthropic_debug_enabled():
            estimated_input = initial_input_tokens_int
            downstream_input = state.input_tokens if state.has_input_tokens else 0
            logger.info(
                f"[ANTHROPIC][TOKEN] Streaming tokens: estimated={estimated_input}, "
                f"downstream={downstream_input}",
            )

        yield _sse_event(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {
                    "input_tokens": state.input_tokens
                    if state.has_input_tokens
                    else initial_input_tokens_int,
                    "output_tokens": state.output_tokens
                    if state.has_output_tokens
                    else 0,
                },
            },
        )
        yield _sse_event("message_stop", {"type": "message_stop"})

    except Exception as e:
        logger.error(f"[ANTHROPIC] Streaming conversion failed: {e}")
        # Ensure client receives message_start even on error
        if not message_start_sent:
            yield _sse_event(
                "message_start",
                {
                    "type": "message_start",
                    "message": {
                        "id": message_id,
                        "type": "message",
                        "role": "assistant",
                        "model": model,
                        "content": [],
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {
                            "input_tokens": initial_input_tokens_int,
                            "output_tokens": 0,
                        },
                    },
                },
            )
        yield _sse_event(
            "error",
            {"type": "error", "error": {"type": "api_error", "message": str(e)}},
        )
