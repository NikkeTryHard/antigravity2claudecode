"""
Comprehensive tests for OpenAI provider edge cases.
"""

import json
import pytest

from a2c.providers.openai import OpenAIProvider, DEFAULT_MODEL_MAPPING


class TestOpenAIProviderEdgeCases:
    """Edge case tests for OpenAI provider."""

    def test_convert_empty_messages(self):
        """Should handle empty messages list."""
        provider = OpenAIProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "messages": [],
        }

        openai_request = provider._convert_request(anthropic_request)

        assert openai_request["messages"] == []

    def test_convert_system_prompt_as_list(self):
        """Should handle system prompt as list of content blocks."""
        provider = OpenAIProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "system": [
                {"type": "text", "text": "You are helpful."},
                {"type": "text", "text": "Be concise."},
            ],
            "messages": [{"role": "user", "content": "Hi"}],
        }

        openai_request = provider._convert_request(anthropic_request)

        assert openai_request["messages"][0]["role"] == "system"
        assert "You are helpful." in openai_request["messages"][0]["content"]
        assert "Be concise." in openai_request["messages"][0]["content"]

    def test_convert_multiple_tool_uses(self):
        """Should handle multiple tool uses in one message."""
        provider = OpenAIProvider(api_key="test")

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

        openai_request = provider._convert_request(anthropic_request)

        tool_calls = openai_request["messages"][0]["tool_calls"]
        assert len(tool_calls) == 2
        assert tool_calls[0]["function"]["name"] == "search"
        assert tool_calls[1]["function"]["name"] == "calculate"

    def test_convert_mixed_content_with_images(self):
        """Should handle mixed text and image content."""
        provider = OpenAIProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What's in these images?"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": "base64data1",
                            },
                        },
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

        openai_request = provider._convert_request(anthropic_request)

        content = openai_request["messages"][0]["content"]
        assert isinstance(content, list)
        assert len(content) == 3
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        assert content[2]["type"] == "image_url"

    def test_convert_tool_result_with_content_blocks(self):
        """Should handle tool result with content blocks."""
        provider = OpenAIProvider(api_key="test")

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

        openai_request = provider._convert_request(anthropic_request)

        assert openai_request["messages"][0]["role"] == "tool"
        assert "Result line 1" in openai_request["messages"][0]["content"]
        assert "Result line 2" in openai_request["messages"][0]["content"]

    def test_convert_response_invalid_json_arguments(self):
        """Should handle invalid JSON in function arguments."""
        provider = OpenAIProvider(api_key="test")

        openai_response = {
            "id": "chatcmpl-123",
            "model": "gpt-4.1",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "search",
                                    "arguments": "invalid json {",
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        anthropic_response = provider._convert_response(openai_response, "claude-sonnet-4-5")

        # Should handle gracefully with raw argument
        assert anthropic_response["content"][0]["type"] == "tool_use"
        assert "raw" in anthropic_response["content"][0]["input"]

    def test_convert_response_content_filter(self):
        """Should handle content_filter finish reason."""
        provider = OpenAIProvider(api_key="test")

        openai_response = {
            "id": "chatcmpl-123",
            "model": "gpt-4.1",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Filtered content"},
                    "finish_reason": "content_filter",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        anthropic_response = provider._convert_response(openai_response, "claude-sonnet-4-5")

        assert anthropic_response["stop_reason"] == "end_turn"

    def test_model_mapping_o_series(self):
        """Should pass through o-series models."""
        provider = OpenAIProvider(api_key="test")

        assert provider._map_model("o1-preview") == "o1-preview"
        assert provider._map_model("o1-mini") == "o1-mini"
        assert provider._map_model("o3-mini") == "o3-mini"
        assert provider._map_model("o4-mini") == "o4-mini"

    def test_model_mapping_all_claude_models(self):
        """Should map all known Claude models."""
        provider = OpenAIProvider(api_key="test")

        for claude_model, openai_model in DEFAULT_MODEL_MAPPING.items():
            assert provider._map_model(claude_model) == openai_model

    def test_custom_model_mapping_override(self):
        """Should allow custom mapping to override defaults."""
        provider = OpenAIProvider(
            api_key="test",
            config={
                "model_mapping": {
                    "claude-sonnet-4-5": "gpt-4-turbo",
                    "custom-model": "gpt-custom",
                }
            },
        )

        assert provider._map_model("claude-sonnet-4-5") == "gpt-4-turbo"
        assert provider._map_model("custom-model") == "gpt-custom"
        # Default mapping should still work for non-overridden models
        assert provider._map_model("claude-opus-4-5") == "gpt-4.1"

    def test_convert_multiple_tools(self):
        """Should convert multiple tools correctly."""
        provider = OpenAIProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "messages": [{"role": "user", "content": "Help me"}],
            "tools": [
                {
                    "name": "search",
                    "description": "Search the web",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                },
                {
                    "name": "calculate",
                    "description": "Do math",
                    "input_schema": {
                        "type": "object",
                        "properties": {"expression": {"type": "string"}},
                    },
                },
            ],
        }

        openai_request = provider._convert_request(anthropic_request)

        assert len(openai_request["tools"]) == 2
        assert openai_request["tools"][0]["function"]["name"] == "search"
        assert openai_request["tools"][1]["function"]["name"] == "calculate"


class TestOpenAIProviderAsync:
    """Async tests for OpenAI provider."""

    @pytest.mark.asyncio
    async def test_send_request_not_configured(self):
        """Should return error when not configured."""
        provider = OpenAIProvider(api_key=None)

        response = await provider.send_request(
            {"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "Hi"}]}
        )

        assert response.status_code == 401
        assert "not configured" in response.error.lower()

    @pytest.mark.asyncio
    async def test_health_check_not_configured(self):
        """Should return unhealthy when not configured."""
        provider = OpenAIProvider(api_key=None)

        health = await provider.health_check()

        assert health.status.value == "unhealthy"
        assert "not configured" in health.error.lower()

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Should close HTTP client properly."""
        provider = OpenAIProvider(api_key="test")

        # Create client
        await provider._get_client()
        assert provider._client is not None

        # Close client
        await provider.close()
        assert provider._client is None
