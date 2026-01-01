"""
Simple token estimation utilities.

This provides rough token counts for Anthropic Messages API requests,
useful for pre-flight checks and fallback values when downstream
doesn't provide actual counts.
"""

from __future__ import annotations

from typing import Any


def estimate_input_tokens(payload: dict[str, Any]) -> int:
    """
    Roughly estimate token count: characters / 4 + image fixed value.

    Args:
        payload: Anthropic Messages API request payload

    Returns:
        Estimated input token count (minimum 1)
    """
    total_chars = 0
    image_count = 0

    def count_str(obj: Any) -> None:
        nonlocal total_chars, image_count
        if isinstance(obj, str):
            total_chars += len(obj)
        elif isinstance(obj, dict):
            # Detect images
            if obj.get("type") == "image" or "inlineData" in obj:
                image_count += 1
            for v in obj.values():
                count_str(v)
        elif isinstance(obj, list):
            for item in obj:
                count_str(item)

    count_str(payload)

    # Rough estimate: chars/4 + 300 tokens per image
    return max(1, total_chars // 4 + image_count * 300)
