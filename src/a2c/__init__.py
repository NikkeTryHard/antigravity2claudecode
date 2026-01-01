"""
a2c - AI API Router and Proxy

A full-featured AI proxy/router that supports multiple providers
(Anthropic, OpenAI, Gemini, Antigravity) with intelligent routing,
debugging, and a beautiful web UI.

Example usage:
    # Start the server
    $ a2c serve

    # Launch Claude Code with a2c proxy
    $ a2c code

    # View status dashboard
    $ a2c status
"""

__version__ = "0.1.0"
__author__ = "Louis (nikketryhard)"

# Re-export core functionality for backwards compatibility
from a2c.core import (
    # Converter exports
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
    # Streaming exports
    antigravity_sse_to_anthropic_sse,
    # Helpers exports
    DEBUG_TRUE,
    anthropic_debug_enabled,
    remove_nulls_for_tool_input,
    # Token estimator exports
    estimate_input_tokens,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
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
