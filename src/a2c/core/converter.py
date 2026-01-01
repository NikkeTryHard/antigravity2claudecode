"""
Convert Anthropic Messages API requests to Google Antigravity API format.

This module handles the transformation of request structures, including:
- Model name mapping (Claude -> Antigravity/Gemini)
- Message format conversion
- Tool/function declaration conversion
- Extended thinking configuration
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from .helpers import anthropic_debug_enabled

logger = logging.getLogger(__name__)

DEFAULT_THINKING_BUDGET = 1024
DEFAULT_TEMPERATURE = 0.4


def _is_non_whitespace_text(value: Any) -> bool:
    """
    Check if text contains non-whitespace content.

    The downstream API validates text content blocks:
    - text cannot be empty string
    - text cannot be only whitespace characters

    This filters out whitespace-only text parts to avoid 400 errors:
    `messages: text content blocks must contain non-whitespace text`
    """
    if value is None:
        return False
    try:
        return bool(str(value).strip())
    except Exception:
        return False


def get_thinking_config(
    thinking: bool | dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Generate downstream thinkingConfig from Anthropic thinking parameter.

    Semantics:
    - thinking=None: Enable includeThoughts with default budget
    - thinking=bool: True enables / False disables
    - thinking=dict: {'type':'enabled'|'disabled', 'budget_tokens': int}
    """
    if thinking is None:
        return {"includeThoughts": True, "thinkingBudget": DEFAULT_THINKING_BUDGET}

    if isinstance(thinking, bool):
        if thinking:
            return {"includeThoughts": True, "thinkingBudget": DEFAULT_THINKING_BUDGET}
        return {"includeThoughts": False}

    if isinstance(thinking, dict):
        thinking_type = thinking.get("type", "enabled")
        is_enabled = thinking_type == "enabled"
        if not is_enabled:
            return {"includeThoughts": False}

        budget = thinking.get("budget_tokens", DEFAULT_THINKING_BUDGET)
        return {"includeThoughts": True, "thinkingBudget": budget}

    return {"includeThoughts": True, "thinkingBudget": DEFAULT_THINKING_BUDGET}


def map_claude_model_to_gemini(claude_model: str) -> str:
    """
    Map Claude model names to downstream model names.

    Handles:
    - Direct passthrough for supported models
    - Version-dated model name normalization (e.g., claude-opus-4-5-20251101)
    - Fixed mappings for common aliases
    """
    claude_model = str(claude_model or "").strip()
    if not claude_model:
        return "claude-sonnet-4-5"

    # Normalize version-dated model names like:
    # - claude-opus-4-5-20251101
    # - claude-haiku-4-5-20251001
    m = re.match(r"^(claude-(?:opus|sonnet|haiku)-4-5)-\d{8}$", claude_model)
    if m:
        claude_model = m.group(1)

    # Reasonable mappings for claude 4.5 series
    if claude_model == "claude-opus-4-5":
        return "claude-opus-4-5-thinking"
    if claude_model == "claude-sonnet-4-5":
        return "claude-sonnet-4-5"
    if claude_model == "claude-haiku-4-5":
        return "gemini-2.5-flash"

    supported_models = {
        "gemini-2.5-flash",
        "gemini-2.5-flash-thinking",
        "gemini-2.5-pro",
        "gemini-3-pro-low",
        "gemini-3-pro-high",
        "gemini-3-pro-image",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash-image",
        "claude-sonnet-4-5",
        "claude-sonnet-4-5-thinking",
        "claude-opus-4-5-thinking",
        "gpt-oss-120b-medium",
    }

    if claude_model in supported_models:
        return claude_model

    model_mapping = {
        "claude-sonnet-4.5": "claude-sonnet-4-5",
        "claude-3-5-sonnet-20241022": "claude-sonnet-4-5",
        "claude-3-5-sonnet-20240620": "claude-sonnet-4-5",
        "claude-opus-4": "gemini-3-pro-high",
        "claude-haiku-4": "claude-haiku-4.5",
        "claude-3-haiku-20240307": "gemini-2.5-flash",
    }

    return model_mapping.get(claude_model, "claude-sonnet-4-5")


def clean_json_schema(schema: Any) -> Any:
    """
    Clean JSON Schema, removing unsupported fields and appending validation to description.

    The downstream API has limited JSON Schema support - many standard fields
    cause 400 errors (e.g., $ref, exclusiveMinimum).
    """
    if not isinstance(schema, dict):
        return schema

    # Fields that cause 400 errors in downstream
    unsupported_keys = {
        "$schema",
        "$id",
        "$ref",
        "$defs",
        "definitions",
        "title",
        "example",
        "examples",
        "readOnly",
        "writeOnly",
        "default",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "oneOf",
        "anyOf",
        "allOf",
        "const",
        "additionalItems",
        "contains",
        "patternProperties",
        "dependencies",
        "propertyNames",
        "if",
        "then",
        "else",
        "contentEncoding",
        "contentMediaType",
    }

    validation_fields = {
        "minLength": "minLength",
        "maxLength": "maxLength",
        "minimum": "minimum",
        "maximum": "maximum",
        "minItems": "minItems",
        "maxItems": "maxItems",
    }
    fields_to_remove = {"additionalProperties"}

    validations: list[str] = []
    for field, label in validation_fields.items():
        if field in schema:
            validations.append(f"{label}: {schema[field]}")

    cleaned: dict[str, Any] = {}
    for key, value in schema.items():
        if (
            key in unsupported_keys
            or key in fields_to_remove
            or key in validation_fields
        ):
            continue

        if key == "type" and isinstance(value, list):
            # Handle type arrays like: type: ["string", "null"]
            # Downstream requires single type + nullable flag
            has_null = any(
                isinstance(t, str) and t.strip() and t.strip().lower() == "null"
                for t in value
            )
            non_null_types = [
                t.strip()
                for t in value
                if isinstance(t, str) and t.strip() and t.strip().lower() != "null"
            ]

            cleaned[key] = non_null_types[0] if non_null_types else "string"
            if has_null:
                cleaned["nullable"] = True
            continue

        if key == "description" and validations:
            cleaned[key] = f"{value} ({', '.join(validations)})"
        elif isinstance(value, dict):
            cleaned[key] = clean_json_schema(value)
        elif isinstance(value, list):
            cleaned[key] = [
                clean_json_schema(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned[key] = value

    if validations and "description" not in cleaned:
        cleaned["description"] = f"Validation: {', '.join(validations)}"

    # Add type: object if properties exist but type is missing
    if "properties" in cleaned and "type" not in cleaned:
        cleaned["type"] = "object"

    return cleaned


def convert_tools(
    anthropic_tools: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    """
    Convert Anthropic tools[] to downstream functionDeclarations structure.
    """
    if not anthropic_tools:
        return None

    gemini_tools: list[dict[str, Any]] = []
    for tool in anthropic_tools:
        name = tool.get("name")
        if not name:
            continue
        description = tool.get("description", "")
        input_schema = tool.get("input_schema", {}) or {}
        parameters = clean_json_schema(input_schema)

        gemini_tools.append(
            {
                "functionDeclarations": [
                    {
                        "name": name,
                        "description": description,
                        "parameters": parameters,
                    }
                ]
            }
        )

    return gemini_tools or None


def _extract_tool_result_output(content: Any) -> str:
    """
    Extract output string from tool_result.content.
    """
    if isinstance(content, list):
        if not content:
            return ""
        first = content[0]
        if isinstance(first, dict) and first.get("type") == "text":
            return str(first.get("text", ""))
        return str(first)
    if content is None:
        return ""
    return str(content)


def convert_messages_to_contents(
    messages: list[dict[str, Any]], *, include_thinking: bool = True
) -> list[dict[str, Any]]:
    """
    Convert Anthropic messages[] to downstream contents[] (role: user/model, parts: []).

    Args:
        messages: Anthropic format message list
        include_thinking: Whether to include thinking blocks (set False when thinking disabled)
    """
    contents: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "user")
        gemini_role = "model" if role == "assistant" else "user"
        raw_content = msg.get("content", "")

        parts: list[dict[str, Any]] = []
        if isinstance(raw_content, str):
            if _is_non_whitespace_text(raw_content):
                parts = [{"text": str(raw_content)}]
        elif isinstance(raw_content, list):
            for item in raw_content:
                if not isinstance(item, dict):
                    if _is_non_whitespace_text(item):
                        parts.append({"text": str(item)})
                    continue

                item_type = item.get("type")
                if item_type == "thinking":
                    # Skip historical thinking blocks if thinking disabled
                    if not include_thinking:
                        continue

                    # Thinking blocks require signature for replay
                    signature = item.get("signature")
                    if not signature:
                        continue

                    thinking_text = item.get("thinking", "")
                    if thinking_text is None:
                        thinking_text = ""
                    part: dict[str, Any] = {
                        "text": str(thinking_text),
                        "thought": True,
                        "thoughtSignature": signature,
                    }
                    parts.append(part)
                elif item_type == "redacted_thinking":
                    # Skip historical redacted_thinking blocks if thinking disabled
                    if not include_thinking:
                        continue

                    signature = item.get("signature")
                    if not signature:
                        continue

                    thinking_text = item.get("thinking")
                    if thinking_text is None:
                        thinking_text = item.get("data", "")
                    parts.append(
                        {
                            "text": str(thinking_text or ""),
                            "thought": True,
                            "thoughtSignature": signature,
                        }
                    )
                elif item_type == "text":
                    text = item.get("text", "")
                    if _is_non_whitespace_text(text):
                        parts.append({"text": str(text)})
                elif item_type == "image":
                    source = item.get("source", {}) or {}
                    if source.get("type") == "base64":
                        parts.append(
                            {
                                "inlineData": {
                                    "mimeType": source.get("media_type", "image/png"),
                                    "data": source.get("data", ""),
                                }
                            }
                        )
                elif item_type == "tool_use":
                    parts.append(
                        {
                            "functionCall": {
                                "id": item.get("id"),
                                "name": item.get("name"),
                                "args": item.get("input", {}) or {},
                            }
                        }
                    )
                elif item_type == "tool_result":
                    output = _extract_tool_result_output(item.get("content"))
                    parts.append(
                        {
                            "functionResponse": {
                                "id": item.get("tool_use_id"),
                                "name": item.get("name", ""),
                                "response": {"output": output},
                            }
                        }
                    )
                else:
                    parts.append({"text": json.dumps(item, ensure_ascii=False)})
        else:
            if _is_non_whitespace_text(raw_content):
                parts = [{"text": str(raw_content)}]

        # Skip empty parts (downstream may error)
        if not parts:
            continue

        contents.append({"role": gemini_role, "parts": parts})

    return contents


def reorganize_tool_messages(contents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Reorganize messages to satisfy Anthropic tool_use/tool_result constraints:
    - Each tool_use (functionCall) must be followed by corresponding tool_result (functionResponse)

    Algorithm:
    - Collect all functionResponses
    - Flatten all parts to individual messages
    - Insert matching functionResponse after each functionCall
    """
    tool_results: dict[str, dict[str, Any]] = {}

    for msg in contents:
        for part in msg.get("parts", []) or []:
            if isinstance(part, dict) and "functionResponse" in part:
                tool_id = (part.get("functionResponse") or {}).get("id")
                if tool_id:
                    tool_results[str(tool_id)] = part

    flattened: list[dict[str, Any]] = []
    for msg in contents:
        role = msg.get("role")
        for part in msg.get("parts", []) or []:
            flattened.append({"role": role, "parts": [part]})

    new_contents: list[dict[str, Any]] = []
    i = 0
    while i < len(flattened):
        msg = flattened[i]
        part = msg["parts"][0]

        if isinstance(part, dict) and "functionResponse" in part:
            i += 1
            continue

        if isinstance(part, dict) and "functionCall" in part:
            tool_id = (part.get("functionCall") or {}).get("id")
            new_contents.append({"role": "model", "parts": [part]})

            if tool_id is not None and str(tool_id) in tool_results:
                new_contents.append(
                    {"role": "user", "parts": [tool_results[str(tool_id)]]}
                )

            i += 1
            continue

        new_contents.append(msg)
        i += 1

    return new_contents


def build_system_instruction(system: Any) -> dict[str, Any] | None:
    """
    Convert Anthropic system field to downstream systemInstruction.
    """
    if not system:
        return None

    parts: list[dict[str, Any]] = []
    if isinstance(system, str):
        if _is_non_whitespace_text(system):
            parts.append({"text": str(system)})
    elif isinstance(system, list):
        for item in system:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                if _is_non_whitespace_text(text):
                    parts.append({"text": str(text)})
    else:
        if _is_non_whitespace_text(system):
            parts.append({"text": str(system)})

    if not parts:
        return None

    return {"role": "user", "parts": parts}


def build_generation_config(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """
    Build downstream generationConfig from Anthropic Messages request.

    Returns:
        (generation_config, should_include_thinking): Tuple with config and thinking flag
    """
    config: dict[str, Any] = {
        "topP": 1,
        "topK": 40,
        "candidateCount": 1,
        "stopSequences": [
            "<|user|>",
            "<|bot|>",
            "<|context_request|>",
            "<|endoftext|>",
            "<|end_of_turn|>",
        ],
    }

    temperature = payload.get("temperature", None)
    config["temperature"] = DEFAULT_TEMPERATURE if temperature is None else temperature

    top_p = payload.get("top_p", None)
    if top_p is not None:
        config["topP"] = top_p

    top_k = payload.get("top_k", None)
    if top_k is not None:
        config["topK"] = top_k

    max_tokens = payload.get("max_tokens")
    if max_tokens is not None:
        config["maxOutputTokens"] = max_tokens

    stop_sequences = payload.get("stop_sequences")
    if isinstance(stop_sequences, list) and stop_sequences:
        config["stopSequences"] = config["stopSequences"] + [
            str(s) for s in stop_sequences
        ]

    # Handle Anthropic extended thinking configuration
    should_include_thinking = False
    if "thinking" in payload:
        thinking_value = payload.get("thinking")
        if thinking_value is not None:
            thinking_config = get_thinking_config(thinking_value)
            include_thoughts = bool(thinking_config.get("includeThoughts", False))

            # Check if last assistant message starts with thinking block
            last_assistant_first_block_type = None
            for msg in reversed(payload.get("messages") or []):
                if not isinstance(msg, dict):
                    continue
                if msg.get("role") != "assistant":
                    continue
                content = msg.get("content")
                if not isinstance(content, list) or not content:
                    continue
                first_block = content[0]
                if isinstance(first_block, dict):
                    last_assistant_first_block_type = first_block.get("type")
                else:
                    last_assistant_first_block_type = None
                break

            # Skip thinkingConfig if history doesn't have proper thinking blocks
            if include_thoughts and last_assistant_first_block_type not in {
                None,
                "thinking",
                "redacted_thinking",
            }:
                if anthropic_debug_enabled():
                    logger.info(
                        "[ANTHROPIC][thinking] Thinking enabled but history missing "
                        "thinking/redacted_thinking block, skipping thinkingConfig"
                    )
                return config, False

            # Adjust budget if >= max_tokens
            max_tokens = payload.get("max_tokens")
            if include_thoughts and isinstance(max_tokens, int):
                budget = thinking_config.get("thinkingBudget")
                if isinstance(budget, int) and budget >= max_tokens:
                    adjusted_budget = max(0, max_tokens - 1)
                    if adjusted_budget <= 0:
                        if anthropic_debug_enabled():
                            logger.info(
                                "[ANTHROPIC][thinking] thinkingBudget>=max_tokens, "
                                "cannot adjust, skipping thinkingConfig"
                            )
                        return config, False
                    if anthropic_debug_enabled():
                        logger.info(
                            f"[ANTHROPIC][thinking] Adjusted budget: {budget} -> {adjusted_budget}"
                        )
                    thinking_config["thinkingBudget"] = adjusted_budget

            config["thinkingConfig"] = thinking_config
            should_include_thinking = include_thoughts
            if anthropic_debug_enabled():
                logger.info(
                    f"[ANTHROPIC][thinking] thinkingConfig: includeThoughts="
                    f"{thinking_config.get('includeThoughts')}, thinkingBudget="
                    f"{thinking_config.get('thinkingBudget')}"
                )
        else:
            if anthropic_debug_enabled():
                logger.info(
                    "[ANTHROPIC][thinking] thinking=null, not enabling thinking"
                )
    else:
        if anthropic_debug_enabled():
            logger.info("[ANTHROPIC][thinking] No thinking field provided")
    return config, should_include_thinking


def convert_anthropic_request_to_antigravity_components(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert Anthropic Messages request to downstream request components.

    Returns dict with:
    - model: Downstream model name
    - contents: Downstream contents[]
    - system_instruction: Downstream systemInstruction (optional)
    - tools: Downstream tools (optional)
    - generation_config: Downstream generationConfig
    """
    model = map_claude_model_to_gemini(str(payload.get("model", "")))
    messages = payload.get("messages") or []
    if not isinstance(messages, list):
        messages = []

    # Build generation_config first to determine thinking state
    generation_config, should_include_thinking = build_generation_config(payload)

    # Convert messages based on thinking configuration
    contents = convert_messages_to_contents(
        messages, include_thinking=should_include_thinking
    )
    contents = reorganize_tool_messages(contents)
    system_instruction = build_system_instruction(payload.get("system"))
    tools = convert_tools(payload.get("tools"))

    return {
        "model": model,
        "contents": contents,
        "system_instruction": system_instruction,
        "tools": tools,
        "generation_config": generation_config,
    }
