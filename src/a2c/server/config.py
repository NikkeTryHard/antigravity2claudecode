"""
Server configuration using Pydantic settings.

Configuration is loaded from environment variables with A2C_ prefix,
and can be overridden via config file.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    """Server configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="A2C_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server settings
    host: str = Field(default="127.0.0.1", description="Server bind host")
    port: int = Field(default=8080, description="Server bind port")
    log_level: str = Field(default="INFO", description="Log level")
    reload: bool = Field(default=False, description="Enable hot reload (dev mode)")

    # Debug settings
    debug_enabled: bool = Field(default=True, description="Enable debug endpoints")
    debug_retention_days: int = Field(default=7, description="Days to retain debug data")
    debug_max_requests: int = Field(default=10000, description="Max requests to store in debug")

    # Metrics settings
    metrics_enabled: bool = Field(default=True, description="Enable Prometheus metrics")

    # Config file path
    config_path: Path | None = Field(default=None, description="Path to YAML config file")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="A2C_DATABASE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Connection URL
    url: str = Field(
        default="postgresql://localhost/a2c",
        description="PostgreSQL connection URL",
    )

    # Pool settings
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max overflow connections")
    pool_timeout: int = Field(default=30, description="Pool connection timeout in seconds")

    # Debug storage settings
    enabled: bool = Field(default=True, description="Enable debug data storage")
    retention_days: int = Field(default=7, description="Days to retain debug data")
    max_requests: int = Field(default=10000, description="Max requests to store")


class ProviderSettings(BaseSettings):
    """Provider credential settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Anthropic
    anthropic_api_key: str | None = Field(
        default=None, alias="ANTHROPIC_API_KEY", description="Anthropic API key"
    )
    anthropic_base_url: str = Field(
        default="https://api.anthropic.com",
        description="Anthropic API base URL",
    )

    # Google/Gemini
    google_api_key: str | None = Field(
        default=None, alias="GOOGLE_API_KEY", description="Google API key"
    )
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com",
        description="Gemini API base URL",
    )

    # Antigravity (Google Cloud)
    antigravity_project_id: str | None = Field(
        default=None, description="Google Cloud project ID for Antigravity"
    )
    antigravity_location: str = Field(default="us-central1", description="Antigravity region")

    # OpenAI
    openai_api_key: str | None = Field(
        default=None, alias="OPENAI_API_KEY", description="OpenAI API key"
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API base URL",
    )


class RoutingSettings(BaseSettings):
    """Routing configuration."""

    model_config = SettingsConfigDict(
        env_prefix="A2C_ROUTING_",
        extra="ignore",
    )

    # Context threshold for long_context routing
    long_context_threshold: int = Field(
        default=100000,
        description="Token threshold for routing to long context provider",
    )

    # Default providers for each agent type
    default_provider: str = Field(
        default="anthropic", description="Default provider for standard requests"
    )
    background_provider: str = Field(
        default="antigravity", description="Provider for background agents"
    )
    think_provider: str = Field(default="antigravity", description="Provider for extended thinking")
    long_context_provider: str = Field(
        default="gemini", description="Provider for long context requests"
    )
    websearch_provider: str = Field(
        default="gemini", description="Provider for web search requests"
    )


class Settings(BaseSettings):
    """Combined application settings."""

    server: ServerSettings = Field(default_factory=ServerSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    routing: RoutingSettings = Field(default_factory=RoutingSettings)

    def load_from_yaml(self, path: Path) -> None:
        """Load additional settings from YAML file."""
        if not path.exists():
            return

        with open(path) as f:
            config = yaml.safe_load(f)

        if not config:
            return

        # Update settings from YAML
        if "server" in config:
            for key, value in config["server"].items():
                if hasattr(self.server, key):
                    setattr(self.server, key, value)

        if "routing" in config:
            for key, value in config["routing"].items():
                if hasattr(self.routing, key):
                    setattr(self.routing, key, value)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()

    # Load from config file if specified
    if settings.server.config_path:
        settings.load_from_yaml(settings.server.config_path)

    return settings


def get_settings_dict() -> dict[str, Any]:
    """Get settings as dictionary (for API responses)."""
    settings = get_settings()
    return {
        "server": {
            "host": settings.server.host,
            "port": settings.server.port,
            "log_level": settings.server.log_level,
            "debug_enabled": settings.server.debug_enabled,
            "metrics_enabled": settings.server.metrics_enabled,
        },
        "routing": {
            "long_context_threshold": settings.routing.long_context_threshold,
            "default_provider": settings.routing.default_provider,
            "background_provider": settings.routing.background_provider,
            "think_provider": settings.routing.think_provider,
            "long_context_provider": settings.routing.long_context_provider,
            "websearch_provider": settings.routing.websearch_provider,
        },
        "providers": {
            "anthropic": {
                "configured": bool(settings.providers.anthropic_api_key),
                "base_url": settings.providers.anthropic_base_url,
            },
            "google": {
                "configured": bool(settings.providers.google_api_key),
            },
            "openai": {
                "configured": bool(settings.providers.openai_api_key),
                "base_url": settings.providers.openai_base_url,
            },
        },
    }
