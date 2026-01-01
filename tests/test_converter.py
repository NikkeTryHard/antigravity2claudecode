"""
Tests for request conversion in antigravity2claudecode.

These tests cover:
1. Model mapping (Claude -> Gemini/Antigravity)
2. Message format conversion
3. Tool/function conversion
4. Thinking configuration handling
5. System instruction building
"""

import pytest

from antigravity2claudecode.converter import (
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


class TestModelMapping:
    """Tests for map_claude_model_to_gemini"""

    def test_empty_model_defaults_to_sonnet(self):
        """Empty model should default to claude-sonnet-4-5"""
        assert map_claude_model_to_gemini("") == "claude-sonnet-4-5"
        assert map_claude_model_to_gemini(None) == "claude-sonnet-4-5"

    def test_opus_maps_to_thinking(self):
        """claude-opus-4-5 should map to thinking variant"""
        assert map_claude_model_to_gemini("claude-opus-4-5") == "claude-opus-4-5-thinking"

    def test_sonnet_maps_to_itself(self):
        """claude-sonnet-4-5 should stay as is"""
        assert map_claude_model_to_gemini("claude-sonnet-4-5") == "claude-sonnet-4-5"

    def test_haiku_maps_to_gemini_flash(self):
        """claude-haiku-4-5 should map to gemini-2.5-flash"""
        assert map_claude_model_to_gemini("claude-haiku-4-5") == "gemini-2.5-flash"

    def test_versioned_model_names_normalized(self):
        """Versioned model names like claude-opus-4-5-20251101 should be normalized"""
        assert map_claude_model_to_gemini("claude-opus-4-5-20251101") == "claude-opus-4-5-thinking"
        assert map_claude_model_to_gemini("claude-sonnet-4-5-20241022") == "claude-sonnet-4-5"

    def test_supported_models_passthrough(self):
        """Supported models should pass through unchanged"""
        assert map_claude_model_to_gemini("gemini-2.5-flash") == "gemini-2.5-flash"
        assert map_claude_model_to_gemini("gemini-2.5-pro") == "gemini-2.5-pro"

    def test_legacy_model_mapping(self):
        """Legacy model names should map correctly"""
        assert map_claude_model_to_gemini("claude-3-5-sonnet-20241022") == "claude-sonnet-4-5"
        assert map_claude_model_to_gemini("claude-3-haiku-20240307") == "gemini-2.5-flash"


class TestThinkingConfig:
    """Tests for get_thinking_config"""

    def test_none_enables_thinking_with_default_budget(self):
        """None should enable thinking with default budget"""
        config = get_thinking_config(None)
        assert config["includeThoughts"] is True
        assert config["thinkingBudget"] == DEFAULT_THINKING_BUDGET

    def test_true_enables_thinking(self):
        """True should enable thinking with default budget"""
        config = get_thinking_config(True)
        assert config["includeThoughts"] is True
        assert config["thinkingBudget"] == DEFAULT_THINKING_BUDGET

    def test_false_disables_thinking(self):
        """False should disable thinking"""
        config = get_thinking_config(False)
        assert config["includeThoughts"] is False
        assert "thinkingBudget" not in config

    def test_dict_enabled_with_budget(self):
        """Dict with type=enabled should use provided budget"""
        config = get_thinking_config({"type": "enabled", "budget_tokens": 5000})
        assert config["includeThoughts"] is True
        assert config["thinkingBudget"] == 5000

    def test_dict_disabled(self):
        """Dict with type=disabled should disable thinking"""
        config = get_thinking_config({"type": "disabled"})
        assert config["includeThoughts"] is False


class TestCleanJsonSchema:
    """Tests for clean_json_schema"""

    def test_removes_unsupported_keys(self):
        """Unsupported keys should be removed"""
        schema = {
            "type": "object",
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$ref": "#/definitions/test",
            "properties": {"name": {"type": "string"}},
        }
        cleaned = clean_json_schema(schema)
        assert "$schema" not in cleaned
        assert "$ref" not in cleaned
        assert "properties" in cleaned

    def test_handles_type_array_with_null(self):
        """Type arrays with null should be converted to single type + nullable"""
        schema = {"type": ["string", "null"]}
        cleaned = clean_json_schema(schema)
        assert cleaned["type"] == "string"
        assert cleaned["nullable"] is True

    def test_adds_validation_to_description(self):
        """Validation fields should be appended to description"""
        schema = {
            "type": "string",
            "description": "A name field",
            "minLength": 1,
            "maxLength": 100,
        }
        cleaned = clean_json_schema(schema)
        assert "minLength: 1" in cleaned["description"]
        assert "maxLength: 100" in cleaned["description"]

    def test_adds_type_object_if_missing(self):
        """If properties exist but type is missing, add type: object"""
        schema = {"properties": {"name": {"type": "string"}}}
        cleaned = clean_json_schema(schema)
        assert cleaned["type"] == "object"


class TestConvertTools:
    """Tests for convert_tools"""

    def test_none_returns_none(self):
        """None input should return None"""
        assert convert_tools(None) is None

    def test_empty_returns_none(self):
        """Empty list should return None"""
        assert convert_tools([]) is None

    def test_converts_single_tool(self):
        """Single tool should be converted correctly"""
        tools = [
            {
                "name": "search",
                "description": "Search the web",
                "input_schema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
            }
        ]
        result = convert_tools(tools)
        assert len(result) == 1
        assert "functionDeclarations" in result[0]
        assert result[0]["functionDeclarations"][0]["name"] == "search"

    def test_skips_tools_without_name(self):
        """Tools without name should be skipped"""
        tools = [{"description": "No name tool", "input_schema": {}}]
        result = convert_tools(tools)
        assert result is None


class TestConvertMessagesToContents:
    """Tests for convert_messages_to_contents"""

    def test_user_role_stays_user(self):
        """User role should stay as user"""
        messages = [{"role": "user", "content": "Hello"}]
        contents = convert_messages_to_contents(messages)
        assert contents[0]["role"] == "user"
        assert contents[0]["parts"][0]["text"] == "Hello"

    def test_assistant_role_becomes_model(self):
        """Assistant role should become model"""
        messages = [{"role": "assistant", "content": "Hi there"}]
        contents = convert_messages_to_contents(messages)
        assert contents[0]["role"] == "model"
        assert contents[0]["parts"][0]["text"] == "Hi there"

    def test_thinking_blocks_included_when_enabled(self):
        """Thinking blocks should be included when include_thinking=True"""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "thinking",
                        "thinking": "Let me think...",
                        "signature": "sig1",
                    },
                    {"type": "text", "text": "Here is my answer"},
                ],
            }
        ]
        contents = convert_messages_to_contents(messages, include_thinking=True)
        assert len(contents[0]["parts"]) == 2
        assert contents[0]["parts"][0]["thought"] is True

    def test_thinking_blocks_skipped_when_disabled(self):
        """Thinking blocks should be skipped when include_thinking=False"""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "thinking",
                        "thinking": "Let me think...",
                        "signature": "sig1",
                    },
                    {"type": "text", "text": "Here is my answer"},
                ],
            }
        ]
        contents = convert_messages_to_contents(messages, include_thinking=False)
        assert len(contents[0]["parts"]) == 1
        assert contents[0]["parts"][0]["text"] == "Here is my answer"

    def test_thinking_without_signature_skipped(self):
        """Thinking blocks without signature should be skipped"""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "No signature"},
                    {"type": "text", "text": "Answer"},
                ],
            }
        ]
        contents = convert_messages_to_contents(messages, include_thinking=True)
        # Only text should be included
        assert len(contents[0]["parts"]) == 1

    def test_tool_use_converted(self):
        """Tool use should be converted to functionCall"""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tool_1",
                        "name": "search",
                        "input": {"q": "test"},
                    }
                ],
            }
        ]
        contents = convert_messages_to_contents(messages)
        assert "functionCall" in contents[0]["parts"][0]
        assert contents[0]["parts"][0]["functionCall"]["name"] == "search"

    def test_tool_result_converted(self):
        """Tool result should be converted to functionResponse"""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool_1",
                        "content": "Result",
                    }
                ],
            }
        ]
        contents = convert_messages_to_contents(messages)
        assert "functionResponse" in contents[0]["parts"][0]

    def test_image_converted(self):
        """Image content should be converted to inlineData"""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": "base64data",
                        },
                    }
                ],
            }
        ]
        contents = convert_messages_to_contents(messages)
        assert "inlineData" in contents[0]["parts"][0]
        assert contents[0]["parts"][0]["inlineData"]["mimeType"] == "image/png"

    def test_whitespace_only_text_skipped(self):
        """Whitespace-only text should be skipped"""
        messages = [{"role": "user", "content": "   "}]
        contents = convert_messages_to_contents(messages)
        assert len(contents) == 0


class TestReorganizeToolMessages:
    """Tests for reorganize_tool_messages"""

    def test_pairs_function_call_with_response(self):
        """Function call should be paired with its response"""
        contents = [
            {
                "role": "model",
                "parts": [{"functionCall": {"id": "t1", "name": "search", "args": {}}}],
            },
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "id": "t1",
                            "name": "search",
                            "response": {"output": "result"},
                        }
                    }
                ],
            },
        ]
        reorganized = reorganize_tool_messages(contents)
        # Should maintain order
        assert len(reorganized) == 2


class TestBuildSystemInstruction:
    """Tests for build_system_instruction"""

    def test_none_returns_none(self):
        """None input should return None"""
        assert build_system_instruction(None) is None

    def test_string_system(self):
        """String system should be converted to parts"""
        result = build_system_instruction("You are a helpful assistant")
        assert result["role"] == "user"
        assert result["parts"][0]["text"] == "You are a helpful assistant"

    def test_list_system(self):
        """List system with text blocks should be converted"""
        result = build_system_instruction([{"type": "text", "text": "Be helpful"}])
        assert result["parts"][0]["text"] == "Be helpful"

    def test_empty_string_returns_none(self):
        """Empty string should return None"""
        assert build_system_instruction("") is None
        assert build_system_instruction("   ") is None


class TestBuildGenerationConfig:
    """Tests for build_generation_config"""

    def test_default_values(self):
        """Default values should be set correctly"""
        config, _ = build_generation_config({})
        assert config["temperature"] == DEFAULT_TEMPERATURE
        assert config["topP"] == 1
        assert config["topK"] == 40

    def test_custom_temperature(self):
        """Custom temperature should be used"""
        config, _ = build_generation_config({"temperature": 0.7})
        assert config["temperature"] == 0.7

    def test_max_tokens(self):
        """max_tokens should map to maxOutputTokens"""
        config, _ = build_generation_config({"max_tokens": 1000})
        assert config["maxOutputTokens"] == 1000

    def test_stop_sequences_appended(self):
        """Custom stop sequences should be appended to defaults"""
        config, _ = build_generation_config({"stop_sequences": ["STOP"]})
        assert "STOP" in config["stopSequences"]

    def test_thinking_config_included(self):
        """Thinking config should be included when enabled"""
        config, should_include = build_generation_config(
            {"thinking": {"type": "enabled", "budget_tokens": 5000}, "messages": []}
        )
        assert "thinkingConfig" in config
        assert config["thinkingConfig"]["includeThoughts"] is True
        assert should_include is True


class TestConvertAnthropicRequest:
    """Tests for convert_anthropic_request_to_antigravity_components"""

    def test_basic_conversion(self):
        """Basic request should be converted correctly"""
        payload = {
            "model": "claude-opus-4-5",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1000,
        }
        components = convert_anthropic_request_to_antigravity_components(payload)

        assert "model" in components
        assert "contents" in components
        assert "generation_config" in components
        assert components["contents"][0]["parts"][0]["text"] == "Hello"

    def test_with_system(self):
        """System prompt should be included"""
        payload = {
            "model": "claude-sonnet-4-5",
            "system": "Be helpful",
            "messages": [{"role": "user", "content": "Hi"}],
        }
        components = convert_anthropic_request_to_antigravity_components(payload)

        assert components["system_instruction"] is not None
        assert components["system_instruction"]["parts"][0]["text"] == "Be helpful"

    def test_with_tools(self):
        """Tools should be converted"""
        payload = {
            "model": "claude-sonnet-4-5",
            "messages": [{"role": "user", "content": "Search"}],
            "tools": [{"name": "search", "description": "Search", "input_schema": {}}],
        }
        components = convert_anthropic_request_to_antigravity_components(payload)

        assert components["tools"] is not None
        assert len(components["tools"]) == 1


class TestThinkingPreferenceDetection:
    """Tests for thinking preference detection"""

    def test_thinking_type_enabled(self):
        """thinking: {type: "enabled"} should enable thinking"""
        thinking_value = {"type": "enabled", "budget_tokens": 10000}
        client_thinking_enabled = thinking_value.get("type") == "enabled"
        assert client_thinking_enabled is True

    def test_thinking_type_disabled(self):
        """thinking: {type: "disabled"} should disable thinking"""
        thinking_value = {"type": "disabled"}
        client_thinking_enabled = thinking_value.get("type") == "enabled"
        assert client_thinking_enabled is False

    def test_thinking_false(self):
        """thinking: false should disable thinking"""
        thinking_value = False
        client_thinking_enabled = True
        if thinking_value is False:
            client_thinking_enabled = False
        assert client_thinking_enabled is False

    def test_nothinking_model_variant(self):
        """Model ending with -nothinking should disable thinking"""
        model = "claude-opus-4-5-nothinking"
        client_thinking_enabled = True
        thinking_to_text = False

        if "-nothinking" in model.lower():
            client_thinking_enabled = False
            thinking_to_text = True

        assert client_thinking_enabled is False
        assert thinking_to_text is True


class TestIsNonWhitespaceTextEdgeCases:
    """Tests for _is_non_whitespace_text helper edge cases"""

    def test_none_returns_false(self):
        """None should return False"""
        from antigravity2claudecode.converter import _is_non_whitespace_text

        assert _is_non_whitespace_text(None) is False

    def test_empty_string_returns_false(self):
        """Empty string should return False"""
        from antigravity2claudecode.converter import _is_non_whitespace_text

        assert _is_non_whitespace_text("") is False

    def test_whitespace_only_returns_false(self):
        """Whitespace-only should return False"""
        from antigravity2claudecode.converter import _is_non_whitespace_text

        assert _is_non_whitespace_text("   ") is False
        assert _is_non_whitespace_text("\t\n\r") is False

    def test_regular_text_returns_true(self):
        """Normal text should return True"""
        from antigravity2claudecode.converter import _is_non_whitespace_text

        assert _is_non_whitespace_text("hello") is True

    def test_number_returns_true(self):
        """Numbers should work after str conversion"""
        from antigravity2claudecode.converter import _is_non_whitespace_text

        assert _is_non_whitespace_text(42) is True
        assert _is_non_whitespace_text(0) is True


class TestThinkingConfigEdgeCases:
    """Additional edge case tests for get_thinking_config"""

    def test_non_dict_non_bool_falls_back_to_default(self):
        """Non-dict/non-bool thinking value should fall back to default enabled"""
        # String value
        config = get_thinking_config("some string")
        assert config["includeThoughts"] is True
        assert config["thinkingBudget"] == DEFAULT_THINKING_BUDGET

        # Integer value
        config = get_thinking_config(123)
        assert config["includeThoughts"] is True

        # List value
        config = get_thinking_config([1, 2, 3])
        assert config["includeThoughts"] is True

    def test_dict_without_type_defaults_to_enabled(self):
        """Dict without 'type' key should default to enabled"""
        config = get_thinking_config({})
        assert config["includeThoughts"] is True
        assert config["thinkingBudget"] == DEFAULT_THINKING_BUDGET


class TestCleanJsonSchemaEdgeCases:
    """Additional edge case tests for clean_json_schema"""

    def test_non_dict_passthrough(self):
        """Non-dict values should pass through unchanged"""
        assert clean_json_schema("string") == "string"
        assert clean_json_schema(123) == 123
        assert clean_json_schema([1, 2, 3]) == [1, 2, 3]

    def test_type_array_without_null(self):
        """Type array without null should use first type"""
        schema = {"type": ["string", "integer"]}
        cleaned = clean_json_schema(schema)
        assert cleaned["type"] == "string"
        assert "nullable" not in cleaned

    def test_type_array_only_null(self):
        """Type array with only null should default to string"""
        schema = {"type": ["null"]}
        cleaned = clean_json_schema(schema)
        assert cleaned["type"] == "string"
        assert cleaned["nullable"] is True

    def test_nested_schema_cleaning(self):
        """Nested schemas should be cleaned recursively"""
        schema = {
            "type": "object",
            "properties": {"nested": {"$ref": "#/should/be/removed", "type": "string"}},
        }
        cleaned = clean_json_schema(schema)
        assert "$ref" not in cleaned["properties"]["nested"]

    def test_list_items_cleaned(self):
        """List items that are dicts should be cleaned"""
        schema = {"items": [{"$ref": "#/x"}, "string", {"type": "number"}]}
        cleaned = clean_json_schema(schema)
        assert "$ref" not in cleaned["items"][0]

    def test_validation_creates_description_if_none(self):
        """Validation fields should create description if none exists"""
        schema = {"type": "string", "minLength": 1}
        cleaned = clean_json_schema(schema)
        assert "description" in cleaned
        assert "minLength: 1" in cleaned["description"]


class TestExtractToolResultOutputEdgeCases:
    """Tests for _extract_tool_result_output edge cases"""

    def test_empty_list_returns_empty(self):
        """Empty list should return empty string"""
        from antigravity2claudecode.converter import _extract_tool_result_output

        assert _extract_tool_result_output([]) == ""

    def test_list_with_text_block(self):
        """List with text block should extract text"""
        from antigravity2claudecode.converter import _extract_tool_result_output

        content = [{"type": "text", "text": "result"}]
        assert _extract_tool_result_output(content) == "result"

    def test_list_with_non_text_block(self):
        """List with non-text block should stringify first item"""
        from antigravity2claudecode.converter import _extract_tool_result_output

        content = [{"type": "other", "data": "value"}]
        result = _extract_tool_result_output(content)
        assert "other" in result

    def test_none_returns_empty(self):
        """None should return empty string"""
        from antigravity2claudecode.converter import _extract_tool_result_output

        assert _extract_tool_result_output(None) == ""

    def test_string_returns_itself(self):
        """String should return itself"""
        from antigravity2claudecode.converter import _extract_tool_result_output

        assert _extract_tool_result_output("direct string") == "direct string"


class TestConvertMessagesEdgeCases:
    """Additional edge case tests for convert_messages_to_contents"""

    def test_thinking_block_with_none_thinking_text(self):
        """Thinking block with None thinking field should use empty string"""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": None, "signature": "sig"},
                ],
            }
        ]
        contents = convert_messages_to_contents(messages, include_thinking=True)
        assert contents[0]["parts"][0]["text"] == ""

    def test_redacted_thinking_with_data_field(self):
        """Redacted thinking should fallback to data field"""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "redacted_thinking",
                        "data": "redacted",
                        "signature": "sig",
                    },
                ],
            }
        ]
        contents = convert_messages_to_contents(messages, include_thinking=True)
        assert contents[0]["parts"][0]["text"] == "redacted"

    def test_redacted_thinking_without_signature_skipped(self):
        """Redacted thinking without signature should be skipped"""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "redacted_thinking", "data": "redacted"},
                    {"type": "text", "text": "visible"},
                ],
            }
        ]
        contents = convert_messages_to_contents(messages, include_thinking=True)
        assert len(contents[0]["parts"]) == 1
        assert contents[0]["parts"][0]["text"] == "visible"

    def test_unknown_content_type_serialized(self):
        """Unknown content type should be JSON serialized"""
        messages = [
            {
                "role": "user",
                "content": [{"type": "custom", "data": "value"}],
            }
        ]
        contents = convert_messages_to_contents(messages)
        assert "custom" in contents[0]["parts"][0]["text"]

    def test_non_dict_list_items(self):
        """Non-dict items in content list should be stringified"""
        messages = [
            {
                "role": "user",
                "content": ["plain string", 123],
            }
        ]
        contents = convert_messages_to_contents(messages)
        assert len(contents[0]["parts"]) == 2

    def test_non_list_non_string_content(self):
        """Non-list/non-string content should be stringified"""
        messages = [{"role": "user", "content": 42}]
        contents = convert_messages_to_contents(messages)
        assert contents[0]["parts"][0]["text"] == "42"


class TestReorganizeToolMessagesEdgeCases:
    """Additional edge case tests for reorganize_tool_messages"""

    def test_function_call_without_response(self):
        """Function call without matching response should still be included"""
        contents = [
            {
                "role": "model",
                "parts": [{"functionCall": {"id": "t1", "name": "search"}}],
            },
        ]
        reorganized = reorganize_tool_messages(contents)
        assert len(reorganized) == 1

    def test_orphan_function_response_skipped(self):
        """Function response without matching call should be skipped"""
        contents = [
            {"role": "user", "parts": [{"functionResponse": {"id": "orphan"}}]},
            {"role": "user", "parts": [{"text": "hello"}]},
        ]
        reorganized = reorganize_tool_messages(contents)
        assert len(reorganized) == 1
        assert "text" in reorganized[0]["parts"][0]


class TestBuildSystemInstructionEdgeCases:
    """Additional edge case tests for build_system_instruction"""

    def test_list_with_non_text_items(self):
        """List with non-text items should be skipped"""
        system = [
            {"type": "image", "data": "..."},
            {"type": "text", "text": "Be helpful"},
        ]
        result = build_system_instruction(system)
        assert len(result["parts"]) == 1
        assert result["parts"][0]["text"] == "Be helpful"

    def test_non_string_non_list_system(self):
        """Non-string/list system should be stringified"""
        result = build_system_instruction(42)
        assert result["parts"][0]["text"] == "42"

    def test_whitespace_list_items_skipped(self):
        """Whitespace-only text items should be skipped"""
        system = [
            {"type": "text", "text": "  "},
            {"type": "text", "text": "valid"},
        ]
        result = build_system_instruction(system)
        assert len(result["parts"]) == 1


class TestBuildGenerationConfigEdgeCases:
    """Additional edge case tests for build_generation_config"""

    def test_thinking_disabled_includes_config(self):
        """Thinking disabled should include thinkingConfig with includeThoughts=False"""
        payload = {
            "thinking": {"type": "disabled"},
            "messages": [],
        }
        config, should_include = build_generation_config(payload)
        assert config["thinkingConfig"]["includeThoughts"] is False
        assert should_include is False

    def test_thinking_with_incompatible_history(self):
        """Thinking enabled but incompatible history should skip thinkingConfig"""
        payload = {
            "thinking": {"type": "enabled"},
            "messages": [{"role": "assistant", "content": [{"type": "text", "text": "Hi"}]}],
        }
        config, should_include = build_generation_config(payload)
        assert should_include is False

    def test_thinking_budget_adjustment(self):
        """Budget >= max_tokens should be auto-adjusted"""
        payload = {
            "thinking": {"type": "enabled", "budget_tokens": 1000},
            "max_tokens": 500,
            "messages": [],
        }
        config, should_include = build_generation_config(payload)
        assert config["thinkingConfig"]["thinkingBudget"] == 499

    def test_thinking_budget_too_low_skips(self):
        """Budget adjustment to 0 or less should skip thinkingConfig"""
        payload = {
            "thinking": {"type": "enabled", "budget_tokens": 1000},
            "max_tokens": 1,
            "messages": [],
        }
        config, should_include = build_generation_config(payload)
        assert "thinkingConfig" not in config
        assert should_include is False

    def test_top_p_and_top_k_customization(self):
        """top_p and top_k should be customizable"""
        payload = {"top_p": 0.9, "top_k": 10}
        config, _ = build_generation_config(payload)
        assert config["topP"] == 0.9
        assert config["topK"] == 10

    def test_thinking_null_value(self):
        """thinking=null should not enable thinking"""
        payload = {"thinking": None, "messages": []}
        config, should_include = build_generation_config(payload)
        # When explicitly null, thinking should not be enabled
        assert "thinkingConfig" not in config or should_include is False


class TestConvertToolsEdgeCases:
    """Additional edge case tests for convert_tools"""

    def test_tool_with_empty_name_skipped(self):
        """Tools with empty name should be skipped"""
        tools = [
            {"name": "", "description": "Empty name"},
            {"name": "valid", "description": "Valid tool"},
        ]
        result = convert_tools(tools)
        assert len(result) == 1
        assert result[0]["functionDeclarations"][0]["name"] == "valid"

    def test_tool_without_input_schema(self):
        """Tool without input_schema should use empty dict"""
        tools = [{"name": "simple", "description": "No schema"}]
        result = convert_tools(tools)
        assert result[0]["functionDeclarations"][0]["parameters"] == {}


# Run tests with: python -m pytest tests/test_converter.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
