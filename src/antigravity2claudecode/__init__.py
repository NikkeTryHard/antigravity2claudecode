"""
antigravity2claudecode - Convert Anthropic Messages API to Google Antigravity API

This package provides conversion utilities for translating between Anthropic's
Claude API format and Google's Antigravity API format, with full support for
extended thinking (Opus 4.5 thinking blocks).

MIT License - See LICENSE file for details.
"""

from .converter import (
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
from .helpers import (
    DEBUG_TRUE,
    anthropic_debug_enabled,
    remove_nulls_for_tool_input,
)
from .streaming import (
    antigravity_sse_to_anthropic_sse,
)
from .token_estimator import estimate_input_tokens

__version__ = "0.1.0"
__all__ = [
    # Helpers
    "DEBUG_TRUE",
    "anthropic_debug_enabled",
    "remove_nulls_for_tool_input",
    # Converter
    "DEFAULT_THINKING_BUDGET",
    "DEFAULT_TEMPERATURE",
    "get_thinking_config",
    "map_claude_model_to_gemini",
    "clean_json_schema",
    "convert_tools",
    "convert_messages_to_contents",
    "reorganize_tool_messages",
    "build_system_instruction",
    "build_generation_config",
    "convert_anthropic_request_to_antigravity_components",
    # Streaming
    "antigravity_sse_to_anthropic_sse",
    # Token estimation
    "estimate_input_tokens",
]
