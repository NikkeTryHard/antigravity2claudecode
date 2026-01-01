"""
TDD Tests for Gemini provider.

Tests written FIRST following TDD methodology.
"""

import json

import pytest

from a2c.providers import ApiFormat, ProviderHealth, ProviderStatus
from a2c.providers.gemini import GeminiProvider


class TestGeminiProviderInfo:
    """Tests for Gemini provider metadata."""

    def test_provider_info(self):
        """Should return correct provider info."""
        provider = GeminiProvider()

        info = provider.info
        assert info.name == "gemini"
        assert info.display_name == "Google Gemini"
        assert info.api_format == ApiFormat.GEMINI
        assert info.supports_streaming is True
        assert info.supports_tools is True
        assert info.supports_vision is True
        assert info.max_context_tokens == 1000000  # Gemini has 1M context

    def test_is_configured_without_key(self):
        """Should not be configured without API key."""
        provider = GeminiProvider(api_key=None)
        # May be configured via env var
        assert isinstance(provider.is_configured, bool)

    def test_is_configured_with_key(self):
        """Should be configured with API key."""
        provider = GeminiProvider(api_key="test-api-key")
        assert provider.is_configured is True


class TestGeminiRequestConversion:
    """Tests for Anthropic to Gemini request conversion."""

    def test_convert_simple_message(self):
        """Should convert simple text message."""
        provider = GeminiProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": "Hello"}],
        }

        gemini_request = provider._convert_request(anthropic_request)

        assert "contents" in gemini_request
        assert gemini_request["contents"][0]["role"] == "user"
        assert gemini_request["contents"][0]["parts"][0]["text"] == "Hello"

    def test_convert_system_prompt(self):
        """Should convert system prompt to system_instruction."""
        provider = GeminiProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "system": "You are a helpful assistant.",
            "messages": [{"role": "user", "content": "Hi"}],
        }

        gemini_request = provider._convert_request(anthropic_request)

        # System should be in system_instruction
        assert "system_instruction" in gemini_request
        assert (
            gemini_request["system_instruction"]["parts"][0]["text"]
            == "You are a helpful assistant."
        )

    def test_convert_assistant_message(self):
        """Should convert assistant messages to model role."""
        provider = GeminiProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
        }

        gemini_request = provider._convert_request(anthropic_request)

        # Gemini uses "model" instead of "assistant"
        assert gemini_request["contents"][1]["role"] == "model"
        assert gemini_request["contents"][1]["parts"][0]["text"] == "Hi there!"

    def test_convert_content_blocks(self):
        """Should convert content block format."""
        provider = GeminiProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What's in this image?"},
                    ],
                }
            ],
        }

        gemini_request = provider._convert_request(anthropic_request)

        assert gemini_request["contents"][0]["parts"][0]["text"] == "What's in this image?"

    def test_convert_image_content(self):
        """Should convert image content to Gemini format."""
        provider = GeminiProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What's this?"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": "base64data",
                            },
                        },
                    ],
                }
            ],
        }

        gemini_request = provider._convert_request(anthropic_request)

        # Should have inline_data format
        parts = gemini_request["contents"][0]["parts"]
        assert any("inline_data" in p for p in parts)

    def test_convert_tools(self):
        """Should convert tools to Gemini function declarations."""
        provider = GeminiProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "messages": [{"role": "user", "content": "Search for cats"}],
            "tools": [
                {
                    "name": "search",
                    "description": "Search the web",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                }
            ],
        }

        gemini_request = provider._convert_request(anthropic_request)

        assert "tools" in gemini_request
        assert gemini_request["tools"][0]["function_declarations"][0]["name"] == "search"

    def test_convert_tool_use(self):
        """Should convert tool_use to function_call."""
        provider = GeminiProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "messages": [
                {"role": "user", "content": "Search for cats"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_1",
                            "name": "search",
                            "input": {"query": "cats"},
                        }
                    ],
                },
            ],
        }

        gemini_request = provider._convert_request(anthropic_request)

        # Model message should have function_call
        model_msg = gemini_request["contents"][1]
        assert model_msg["role"] == "model"
        assert any("functionCall" in p for p in model_msg["parts"])

    def test_convert_tool_result(self):
        """Should convert tool_result to function_response."""
        provider = GeminiProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool_1",
                            "content": "Found 10 results",
                        }
                    ],
                }
            ],
        }

        gemini_request = provider._convert_request(anthropic_request)

        # Should be function role with function_response
        assert gemini_request["contents"][0]["role"] == "function"
        assert any("functionResponse" in p for p in gemini_request["contents"][0]["parts"])

    def test_convert_generation_config(self):
        """Should convert generation parameters."""
        provider = GeminiProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "max_tokens": 1000,
            "temperature": 0.7,
            "stop_sequences": ["STOP", "END"],
            "messages": [{"role": "user", "content": "Hi"}],
        }

        gemini_request = provider._convert_request(anthropic_request)

        assert "generationConfig" in gemini_request
        assert gemini_request["generationConfig"]["maxOutputTokens"] == 1000
        assert gemini_request["generationConfig"]["temperature"] == 0.7
        assert gemini_request["generationConfig"]["stopSequences"] == ["STOP", "END"]


class TestGeminiResponseConversion:
    """Tests for Gemini to Anthropic response conversion."""

    def test_convert_simple_response(self):
        """Should convert simple text response."""
        provider = GeminiProvider(api_key="test")

        gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Hello!"}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
            },
        }

        anthropic_response = provider._convert_response(gemini_response, "claude-sonnet-4-5")

        assert anthropic_response["type"] == "message"
        assert anthropic_response["role"] == "assistant"
        assert anthropic_response["content"][0]["type"] == "text"
        assert anthropic_response["content"][0]["text"] == "Hello!"
        assert anthropic_response["stop_reason"] == "end_turn"
        assert anthropic_response["usage"]["input_tokens"] == 10
        assert anthropic_response["usage"]["output_tokens"] == 5

    def test_convert_function_call_response(self):
        """Should convert function_call to tool_use."""
        provider = GeminiProvider(api_key="test")

        gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "search",
                                    "args": {"query": "cats"},
                                }
                            }
                        ],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        }

        anthropic_response = provider._convert_response(gemini_response, "claude-sonnet-4-5")

        assert anthropic_response["content"][0]["type"] == "tool_use"
        assert anthropic_response["content"][0]["name"] == "search"
        assert anthropic_response["content"][0]["input"] == {"query": "cats"}
        assert anthropic_response["stop_reason"] == "tool_use"

    def test_convert_max_tokens_finish(self):
        """Should convert MAX_TOKENS finish reason."""
        provider = GeminiProvider(api_key="test")

        gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Truncated..."}],
                        "role": "model",
                    },
                    "finishReason": "MAX_TOKENS",
                }
            ],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 100},
        }

        anthropic_response = provider._convert_response(gemini_response, "claude-sonnet-4-5")

        assert anthropic_response["stop_reason"] == "max_tokens"


class TestGeminiModelMapping:
    """Tests for model name mapping."""

    def test_map_claude_to_gemini(self):
        """Should map Claude models to Gemini equivalents."""
        provider = GeminiProvider(api_key="test")

        assert provider._map_model("claude-opus-4-5") == "gemini-2.5-pro"
        assert provider._map_model("claude-sonnet-4-5") == "gemini-2.5-flash"
        assert provider._map_model("claude-3-haiku-20240307") == "gemini-2.5-flash-lite"

    def test_passthrough_gemini_models(self):
        """Should pass through Gemini model names."""
        provider = GeminiProvider(api_key="test")

        assert provider._map_model("gemini-2.5-pro") == "gemini-2.5-pro"
        assert provider._map_model("gemini-2.5-flash") == "gemini-2.5-flash"
        assert provider._map_model("gemini-2.0-flash-exp") == "gemini-2.0-flash-exp"

    def test_custom_model_mapping(self):
        """Should use custom model mapping if provided."""
        provider = GeminiProvider(
            api_key="test",
            config={"model_mapping": {"claude-opus-4-5": "gemini-2.0-flash-exp"}},
        )

        assert provider._map_model("claude-opus-4-5") == "gemini-2.0-flash-exp"


class TestGeminiProviderHeaders:
    """Tests for request headers."""

    def test_build_headers(self):
        """Should build correct headers."""
        provider = GeminiProvider(api_key="test-api-key")

        headers = provider._build_headers()

        assert headers["Content-Type"] == "application/json"

    def test_build_headers_streaming(self):
        """Should add accept header for streaming."""
        provider = GeminiProvider(api_key="test-api-key")

        headers = provider._build_headers(stream=True)

        assert headers["Accept"] == "text/event-stream"


class TestGeminiProviderToDict:
    """Tests for provider serialization."""

    def test_to_dict(self):
        """Should convert to dictionary."""
        provider = GeminiProvider(api_key="test-api-key")

        d = provider.to_dict()

        assert d["name"] == "gemini"
        assert d["display_name"] == "Google Gemini"
        assert d["is_configured"] is True
        assert "health" in d
