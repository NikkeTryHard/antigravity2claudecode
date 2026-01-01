"""
Tests for token estimation in antigravity2claudecode.

These tests cover:
1. Basic token estimation
2. Image token counting
3. Nested structure handling
4. Edge cases
"""

import pytest

from antigravity2claudecode.token_estimator import estimate_input_tokens


class TestEstimateInputTokens:
    """Tests for estimate_input_tokens"""

    def test_empty_payload(self):
        """Empty payload should return minimum 1 token"""
        result = estimate_input_tokens({})
        assert result >= 1

    def test_simple_text_message(self):
        """Simple text message should estimate based on character count"""
        payload = {"messages": [{"role": "user", "content": "Hello world"}]}
        result = estimate_input_tokens(payload)
        # "Hello world" is 11 chars, so roughly 11/4 = 2-3 tokens
        assert result >= 1

    def test_longer_text(self):
        """Longer text should estimate more tokens"""
        short_payload = {"messages": [{"role": "user", "content": "Hi"}]}
        long_payload = {
            "messages": [{"role": "user", "content": "This is a much longer message " * 10}]
        }

        short_result = estimate_input_tokens(short_payload)
        long_result = estimate_input_tokens(long_payload)

        assert long_result > short_result

    def test_image_adds_fixed_tokens(self):
        """Images should add fixed token count"""
        text_only = {"messages": [{"role": "user", "content": "Hello"}]}
        with_image = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Hello"},
                        {"type": "image", "source": {"data": "base64data"}},
                    ],
                }
            ]
        }

        text_result = estimate_input_tokens(text_only)
        image_result = estimate_input_tokens(with_image)

        # Image should add approximately 300 tokens
        assert image_result > text_result + 200

    def test_multiple_images(self):
        """Multiple images should each add tokens"""
        one_image = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "image", "source": {"data": "x"}}],
                }
            ]
        }
        two_images = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"data": "x"}},
                        {"type": "image", "source": {"data": "y"}},
                    ],
                }
            ]
        }

        one_result = estimate_input_tokens(one_image)
        two_result = estimate_input_tokens(two_images)

        # Each image adds ~300 tokens
        assert two_result > one_result + 200

    def test_inline_data_detected(self):
        """inlineData format should also be detected as image"""
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"inlineData": {"mimeType": "image/png", "data": "base64"}}],
                }
            ]
        }
        result = estimate_input_tokens(payload)
        # Should include image token count
        assert result >= 300

    def test_nested_structure(self):
        """Nested structures should be traversed"""
        payload = {
            "model": "claude-opus-4-5",
            "system": "You are a helpful assistant",
            "messages": [
                {"role": "user", "content": "Hello"},
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Hi there!"},
                        {"type": "text", "text": "How can I help?"},
                    ],
                },
                {"role": "user", "content": "What is the weather?"},
            ],
        }
        result = estimate_input_tokens(payload)
        # Should count all text content
        assert result > 10

    def test_tools_counted(self):
        """Tool definitions should contribute to token count"""
        without_tools = {"messages": [{"role": "user", "content": "Hi"}]}
        with_tools = {
            "messages": [{"role": "user", "content": "Hi"}],
            "tools": [
                {
                    "name": "search",
                    "description": "Search the web for information",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query",
                            }
                        },
                    },
                }
            ],
        }

        without_result = estimate_input_tokens(without_tools)
        with_result = estimate_input_tokens(with_tools)

        assert with_result > without_result

    def test_minimum_one_token(self):
        """Result should always be at least 1"""
        result = estimate_input_tokens({})
        assert result >= 1

    def test_list_content(self):
        """List content should be traversed"""
        payload = {"messages": [{"role": "user", "content": ["Hello", "World", "Test"]}]}
        result = estimate_input_tokens(payload)
        assert result >= 1

    def test_numeric_values_ignored(self):
        """Numeric values should not crash the function"""
        payload = {
            "max_tokens": 1000,
            "temperature": 0.7,
            "messages": [{"role": "user", "content": "Hi"}],
        }
        result = estimate_input_tokens(payload)
        assert result >= 1

    def test_none_values_handled(self):
        """None values should not crash"""
        payload = {
            "system": None,
            "messages": [{"role": "user", "content": "Hi"}],
        }
        result = estimate_input_tokens(payload)
        assert result >= 1


# Run tests with: python -m pytest tests/test_token_estimator.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
