"""
Comprehensive tests for Gemini provider edge cases.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from a2c.providers.gemini import GeminiProvider, DEFAULT_MODEL_MAPPING


class TestGeminiProviderEdgeCases:
    """Edge case tests for Gemini provider."""

    def test_convert_empty_messages(self):
        """Should handle empty messages list."""
        provider = GeminiProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "messages": [],
        }

        gemini_request = provider._convert_request(anthropic_request)

        assert gemini_request["contents"] == []

    def test_convert_system_prompt_as_list(self):
        """Should handle system prompt as list of content blocks."""
        provider = GeminiProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "system": [
                {"type": "text", "text": "You are helpful."},
                {"type": "text", "text": "Be concise."},
            ],
            "messages": [{"role": "user", "content": "Hi"}],
        }

        gemini_request = provider._convert_request(anthropic_request)

        assert "system_instruction" in gemini_request
        assert "You are helpful." in gemini_request["system_instruction"]["parts"][0]["text"]
        assert "Be concise." in gemini_request["system_instruction"]["parts"][0]["text"]

    def test_convert_multiple_tool_uses(self):
        """Should handle multiple tool uses in one message."""
        provider = GeminiProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_1",
                            "name": "search",
                            "input": {"query": "cats"},
                        },
                        {
                            "type": "tool_use",
                            "id": "tool_2",
                            "name": "calculate",
                            "input": {"expression": "2+2"},
                        },
                    ],
                }
            ],
        }

        gemini_request = provider._convert_request(anthropic_request)

        parts = gemini_request["contents"][0]["parts"]
        assert len(parts) == 2
        assert parts[0]["functionCall"]["name"] == "search"
        assert parts[1]["functionCall"]["name"] == "calculate"

    def test_convert_mixed_content(self):
        """Should handle mixed text and image content."""
        provider = GeminiProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "First text"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": "base64data1",
                            },
                        },
                        {"type": "text", "text": "Second text"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": "base64data2",
                            },
                        },
                    ],
                }
            ],
        }

        gemini_request = provider._convert_request(anthropic_request)

        parts = gemini_request["contents"][0]["parts"]
        assert len(parts) == 4
        assert parts[0]["text"] == "First text"
        assert parts[1]["inline_data"]["mime_type"] == "image/jpeg"
        assert parts[2]["text"] == "Second text"
        assert parts[3]["inline_data"]["mime_type"] == "image/png"

    def test_convert_tool_result_with_content_blocks(self):
        """Should handle tool result with content blocks."""
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
                            "content": [
                                {"type": "text", "text": "Result line 1"},
                                {"type": "text", "text": "Result line 2"},
                            ],
                        }
                    ],
                }
            ],
        }

        gemini_request = provider._convert_request(anthropic_request)

        assert gemini_request["contents"][0]["role"] == "function"
        response = gemini_request["contents"][0]["parts"][0]["functionResponse"]["response"]
        assert "Result line 1" in response["content"]
        assert "Result line 2" in response["content"]

    def test_convert_all_generation_params(self):
        """Should convert all generation parameters."""
        provider = GeminiProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "max_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.9,
            "stop_sequences": ["STOP", "END"],
            "messages": [{"role": "user", "content": "Hi"}],
        }

        gemini_request = provider._convert_request(anthropic_request)

        config = gemini_request["generationConfig"]
        assert config["maxOutputTokens"] == 1000
        assert config["temperature"] == 0.7
        assert config["topP"] == 0.9
        assert config["stopSequences"] == ["STOP", "END"]

    def test_convert_response_empty_candidates(self):
        """Should handle empty candidates in response."""
        provider = GeminiProvider(api_key="test")

        gemini_response = {
            "candidates": [],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 0},
        }

        anthropic_response = provider._convert_response(gemini_response, "claude-sonnet-4-5")

        assert anthropic_response["content"] == []
        assert anthropic_response["stop_reason"] == "end_turn"

    def test_convert_response_safety_finish(self):
        """Should handle SAFETY finish reason."""
        provider = GeminiProvider(api_key="test")

        gemini_response = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Blocked"}], "role": "model"},
                    "finishReason": "SAFETY",
                }
            ],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        }

        anthropic_response = provider._convert_response(gemini_response, "claude-sonnet-4-5")

        assert anthropic_response["stop_reason"] == "end_turn"

    def test_convert_response_multiple_function_calls(self):
        """Should handle multiple function calls in response."""
        provider = GeminiProvider(api_key="test")

        gemini_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"functionCall": {"name": "search", "args": {"q": "cats"}}},
                            {"functionCall": {"name": "calc", "args": {"x": 1}}},
                        ],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        }

        anthropic_response = provider._convert_response(gemini_response, "claude-sonnet-4-5")

        assert len(anthropic_response["content"]) == 2
        assert anthropic_response["content"][0]["type"] == "tool_use"
        assert anthropic_response["content"][1]["type"] == "tool_use"
        assert anthropic_response["stop_reason"] == "tool_use"

    def test_model_mapping_unknown_model(self):
        """Should default to gemini-2.5-flash for unknown models."""
        provider = GeminiProvider(api_key="test")

        assert provider._map_model("unknown-model") == "gemini-2.5-flash"
        assert provider._map_model("some-random-model") == "gemini-2.5-flash"

    def test_model_mapping_all_claude_models(self):
        """Should map all known Claude models."""
        provider = GeminiProvider(api_key="test")

        for claude_model, gemini_model in DEFAULT_MODEL_MAPPING.items():
            assert provider._map_model(claude_model) == gemini_model

    def test_custom_model_mapping_override(self):
        """Should allow custom mapping to override defaults."""
        provider = GeminiProvider(
            api_key="test",
            config={
                "model_mapping": {
                    "claude-sonnet-4-5": "gemini-2.0-flash-exp",
                    "custom-model": "gemini-custom",
                }
            },
        )

        assert provider._map_model("claude-sonnet-4-5") == "gemini-2.0-flash-exp"
        assert provider._map_model("custom-model") == "gemini-custom"
        # Default mapping should still work for non-overridden models
        assert provider._map_model("claude-opus-4-5") == "gemini-2.5-pro"


class TestGeminiProviderAsync:
    """Async tests for Gemini provider."""

    @pytest.mark.asyncio
    async def test_send_request_not_configured(self):
        """Should return error when not configured."""
        provider = GeminiProvider(api_key=None)

        response = await provider.send_request(
            {"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "Hi"}]}
        )

        assert response.status_code == 401
        assert "not configured" in response.error.lower()

    @pytest.mark.asyncio
    async def test_health_check_not_configured(self):
        """Should return unhealthy when not configured."""
        provider = GeminiProvider(api_key=None)

        health = await provider.health_check()

        assert health.status.value == "unhealthy"
        assert "not configured" in health.error.lower()

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Should close HTTP client properly."""
        provider = GeminiProvider(api_key="test")

        # Create client
        await provider._get_client()
        assert provider._client is not None

        # Close client
        await provider.close()
        assert provider._client is None
