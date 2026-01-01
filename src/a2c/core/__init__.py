"""
a2c.core - Core conversion and streaming functionality.

This module contains the core library code for converting between
Anthropic Messages API and Antigravity/Gemini API formats.
"""

from a2c.core.converter import (
    DEFAULT_TEMPERATURE,
    DEFAULT_THINKING_BUDGET,
    build_generation_config,
    build_system_instruction,
    clean_json_schema,
    convert_anthropic_request_to_antigravity_components,
    convert_messages_to_contents,
    convert_tools,
    get_thinking_config,
    map_claude_model_to_gemini,
    reorganize_tool_messages,
)
from a2c.core.helpers import (
    DEBUG_TRUE,
    anthropic_debug_enabled,
    remove_nulls_for_tool_input,
)
from a2c.core.streaming import antigravity_sse_to_anthropic_sse
from a2c.core.token_estimator import estimate_input_tokens

__all__ = [
    # Converter
    "DEFAULT_TEMPERATURE",
    "DEFAULT_THINKING_BUDGET",
    "build_generation_config",
    "build_system_instruction",
    "clean_json_schema",
    "convert_anthropic_request_to_antigravity_components",
    "convert_messages_to_contents",
    "convert_tools",
    "get_thinking_config",
    "map_claude_model_to_gemini",
    "reorganize_tool_messages",
    # Streaming
    "antigravity_sse_to_anthropic_sse",
    # Helpers
    "DEBUG_TRUE",
    "anthropic_debug_enabled",
    "remove_nulls_for_tool_input",
    # Token estimator
    "estimate_input_tokens",
]
