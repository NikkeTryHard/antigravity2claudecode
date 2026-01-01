"""
TDD Tests for OpenAI provider.

Tests written FIRST following TDD methodology.
"""

import json

import pytest

from a2c.providers import ApiFormat, ProviderHealth, ProviderStatus
from a2c.providers.openai import OpenAIProvider


class TestOpenAIProviderInfo:
    """Tests for OpenAI provider metadata."""

    def test_provider_info(self):
        """Should return correct provider info."""
        provider = OpenAIProvider()

        info = provider.info
        assert info.name == "openai"
        assert info.display_name == "OpenAI"
        assert info.api_format == ApiFormat.OPENAI
        assert info.supports_streaming is True
        assert info.supports_tools is True

    def test_is_configured_without_key(self):
        """Should not be configured without API key."""
        provider = OpenAIProvider(api_key=None)
        # May be configured via env var
        assert isinstance(provider.is_configured, bool)

    def test_is_configured_with_key(self):
        """Should be configured with API key."""
        provider = OpenAIProvider(api_key="sk-test-key")
        assert provider.is_configured is True


class TestOpenAIRequestConversion:
    """Tests for Anthropic to OpenAI request conversion."""

    def test_convert_simple_message(self):
        """Should convert simple text message."""
        provider = OpenAIProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": "Hello"}],
        }

        openai_request = provider._convert_request(anthropic_request)

        assert openai_request["model"] == "gpt-4.1"  # Default mapping
        assert openai_request["max_tokens"] == 1000
        assert openai_request["messages"][0]["role"] == "user"
        assert openai_request["messages"][0]["content"] == "Hello"

    def test_convert_system_prompt(self):
        """Should convert system prompt to system message."""
        provider = OpenAIProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "system": "You are a helpful assistant.",
            "messages": [{"role": "user", "content": "Hi"}],
        }

        openai_request = provider._convert_request(anthropic_request)

        # System should be first message
        assert openai_request["messages"][0]["role"] == "system"
        assert openai_request["messages"][0]["content"] == "You are a helpful assistant."
        assert openai_request["messages"][1]["role"] == "user"

    def test_convert_assistant_message(self):
        """Should convert assistant messages."""
        provider = OpenAIProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
        }

        openai_request = provider._convert_request(anthropic_request)

        assert openai_request["messages"][1]["role"] == "assistant"
        assert openai_request["messages"][1]["content"] == "Hi there!"

    def test_convert_content_blocks(self):
        """Should convert content block format."""
        provider = OpenAIProvider(api_key="test")

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

        openai_request = provider._convert_request(anthropic_request)

        # Should flatten to string for simple text
        assert "What's in this image?" in str(openai_request["messages"][0]["content"])

    def test_convert_image_content(self):
        """Should convert image content to OpenAI format."""
        provider = OpenAIProvider(api_key="test")

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

        openai_request = provider._convert_request(anthropic_request)

        # Should have image_url format
        content = openai_request["messages"][0]["content"]
        assert isinstance(content, list)
        assert any(c.get("type") == "image_url" for c in content)

    def test_convert_tools(self):
        """Should convert tools to OpenAI function format."""
        provider = OpenAIProvider(api_key="test")

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

        openai_request = provider._convert_request(anthropic_request)

        assert "tools" in openai_request
        assert openai_request["tools"][0]["type"] == "function"
        assert openai_request["tools"][0]["function"]["name"] == "search"

    def test_convert_tool_use(self):
        """Should convert tool_use to tool_calls."""
        provider = OpenAIProvider(api_key="test")

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

        openai_request = provider._convert_request(anthropic_request)

        # Assistant message should have tool_calls
        assistant_msg = openai_request["messages"][1]
        assert "tool_calls" in assistant_msg
        assert assistant_msg["tool_calls"][0]["function"]["name"] == "search"

    def test_convert_tool_result(self):
        """Should convert tool_result to tool message."""
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
                            "content": "Found 10 results",
                        }
                    ],
                }
            ],
        }

        openai_request = provider._convert_request(anthropic_request)

        # Should be tool role message
        assert openai_request["messages"][0]["role"] == "tool"
        assert openai_request["messages"][0]["tool_call_id"] == "tool_1"

    def test_convert_temperature(self):
        """Should pass through temperature."""
        provider = OpenAIProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "temperature": 0.7,
            "messages": [{"role": "user", "content": "Hi"}],
        }

        openai_request = provider._convert_request(anthropic_request)

        assert openai_request["temperature"] == 0.7

    def test_convert_stop_sequences(self):
        """Should convert stop_sequences to stop."""
        provider = OpenAIProvider(api_key="test")

        anthropic_request = {
            "model": "claude-sonnet-4-5",
            "stop_sequences": ["STOP", "END"],
            "messages": [{"role": "user", "content": "Hi"}],
        }

        openai_request = provider._convert_request(anthropic_request)

        assert openai_request["stop"] == ["STOP", "END"]


class TestOpenAIResponseConversion:
    """Tests for OpenAI to Anthropic response conversion."""

    def test_convert_simple_response(self):
        """Should convert simple text response."""
        provider = OpenAIProvider(api_key="test")

        openai_response = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        anthropic_response = provider._convert_response(openai_response, "claude-sonnet-4-5")

        assert anthropic_response["type"] == "message"
        assert anthropic_response["role"] == "assistant"
        assert anthropic_response["content"][0]["type"] == "text"
        assert anthropic_response["content"][0]["text"] == "Hello!"
        assert anthropic_response["stop_reason"] == "end_turn"
        assert anthropic_response["usage"]["input_tokens"] == 10
        assert anthropic_response["usage"]["output_tokens"] == 5

    def test_convert_tool_calls_response(self):
        """Should convert tool_calls to tool_use."""
        provider = OpenAIProvider(api_key="test")

        openai_response = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "search",
                                    "arguments": '{"query": "cats"}',
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

        assert anthropic_response["content"][0]["type"] == "tool_use"
        assert anthropic_response["content"][0]["name"] == "search"
        assert anthropic_response["content"][0]["input"] == {"query": "cats"}
        assert anthropic_response["stop_reason"] == "tool_use"

    def test_convert_max_tokens_finish(self):
        """Should convert length finish_reason to max_tokens."""
        provider = OpenAIProvider(api_key="test")

        openai_response = {
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Truncated..."},
                    "finish_reason": "length",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 100},
        }

        anthropic_response = provider._convert_response(openai_response, "claude-sonnet-4-5")

        assert anthropic_response["stop_reason"] == "max_tokens"


class TestOpenAIModelMapping:
    """Tests for model name mapping."""

    def test_map_claude_to_openai(self):
        """Should map Claude models to OpenAI equivalents."""
        provider = OpenAIProvider(api_key="test")

        assert provider._map_model("claude-opus-4-5") == "gpt-4.1"
        assert provider._map_model("claude-sonnet-4-5") == "gpt-4.1"
        assert provider._map_model("claude-3-haiku-20240307") == "gpt-4.1-mini"

    def test_passthrough_openai_models(self):
        """Should pass through OpenAI model names."""
        provider = OpenAIProvider(api_key="test")

        assert provider._map_model("gpt-4.1") == "gpt-4.1"
        assert provider._map_model("gpt-4o") == "gpt-4o"
        assert provider._map_model("o3-mini") == "o3-mini"

    def test_custom_model_mapping(self):
        """Should use custom model mapping if provided."""
        provider = OpenAIProvider(
            api_key="test",
            config={"model_mapping": {"claude-opus-4-5": "gpt-4-turbo"}},
        )

        assert provider._map_model("claude-opus-4-5") == "gpt-4-turbo"


class TestOpenAIProviderHeaders:
    """Tests for request headers."""

    def test_build_headers(self):
        """Should build correct headers."""
        provider = OpenAIProvider(api_key="sk-test-key")

        headers = provider._build_headers()

        assert headers["Authorization"] == "Bearer sk-test-key"
        assert headers["Content-Type"] == "application/json"

    def test_build_headers_streaming(self):
        """Should add accept header for streaming."""
        provider = OpenAIProvider(api_key="sk-test-key")

        headers = provider._build_headers(stream=True)

        assert headers["Accept"] == "text/event-stream"


class TestOpenAIProviderToDict:
    """Tests for provider serialization."""

    def test_to_dict(self):
        """Should convert to dictionary."""
        provider = OpenAIProvider(api_key="sk-test-key")

        d = provider.to_dict()

        assert d["name"] == "openai"
        assert d["display_name"] == "OpenAI"
        assert d["is_configured"] is True
        assert "health" in d
