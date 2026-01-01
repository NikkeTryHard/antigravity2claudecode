"""
a2c.providers - AI provider implementations.

This module contains provider implementations for various AI backends:
- Anthropic: Native Anthropic Claude API
- Antigravity: Google Antigravity (Claude via Google Cloud)
- OpenAI: OpenAI-compatible endpoints
- Gemini: Direct Google Gemini API (coming soon)
"""

from a2c.providers.anthropic import AnthropicProvider
from a2c.providers.antigravity import AntigravityProvider
from a2c.providers.base import (
    ApiFormat,
    BaseProvider,
    ProviderHealth,
    ProviderInfo,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
)
from a2c.providers.gemini import GeminiProvider
from a2c.providers.openai import OpenAIProvider
from a2c.providers.registry import (
    ProviderRegistry,
    get_registry,
    reset_registry,
)

__all__ = [
    # Base classes
    "BaseProvider",
    "ProviderInfo",
    "ProviderHealth",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderStatus",
    "ApiFormat",
    # Registry
    "ProviderRegistry",
    "get_registry",
    "reset_registry",
    # Providers
    "AnthropicProvider",
    "AntigravityProvider",
    "GeminiProvider",
    "OpenAIProvider",
]
