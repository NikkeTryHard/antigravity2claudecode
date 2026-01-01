"""
Provider registry for managing available providers.

The registry handles:
- Provider registration and discovery
- Provider health monitoring
- Provider selection for routing
"""

import asyncio
import logging
from typing import Any

from a2c.providers.base import BaseProvider, ProviderHealth, ProviderStatus

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Registry for managing AI providers.

    Thread-safe registry that supports:
    - Dynamic provider registration
    - Health monitoring with background checks
    - Provider lookup by name
    """

    def __init__(self):
        """Initialize empty registry."""
        self._providers: dict[str, BaseProvider] = {}
        self._health_check_task: asyncio.Task | None = None
        self._health_check_interval: float = 60.0  # seconds

    def register(self, provider: BaseProvider) -> None:
        """
        Register a provider.

        Args:
            provider: Provider instance to register

        Raises:
            ValueError: If provider with same name already exists
        """
        if provider.name in self._providers:
            raise ValueError(f"Provider '{provider.name}' already registered")

        self._providers[provider.name] = provider
        logger.info(f"Registered provider: {provider.name}")

    def unregister(self, name: str) -> None:
        """
        Unregister a provider.

        Args:
            name: Provider name to unregister
        """
        if name in self._providers:
            del self._providers[name]
            logger.info(f"Unregistered provider: {name}")

    def get(self, name: str) -> BaseProvider | None:
        """
        Get a provider by name.

        Args:
            name: Provider name

        Returns:
            Provider instance or None if not found
        """
        return self._providers.get(name)

    def get_or_raise(self, name: str) -> BaseProvider:
        """
        Get a provider by name, raising if not found.

        Args:
            name: Provider name

        Returns:
            Provider instance

        Raises:
            KeyError: If provider not found
        """
        provider = self.get(name)
        if provider is None:
            raise KeyError(f"Provider '{name}' not found")
        return provider

    def list_providers(self) -> list[BaseProvider]:
        """
        List all registered providers.

        Returns:
            List of provider instances
        """
        return list(self._providers.values())

    def list_healthy_providers(self) -> list[BaseProvider]:
        """
        List all healthy providers.

        Returns:
            List of healthy provider instances
        """
        return [p for p in self._providers.values() if p.is_healthy]

    def list_configured_providers(self) -> list[BaseProvider]:
        """
        List all configured providers.

        Returns:
            List of configured provider instances
        """
        return [p for p in self._providers.values() if p.is_configured]

    async def check_health(self, name: str) -> ProviderHealth:
        """
        Check health of a specific provider.

        Args:
            name: Provider name

        Returns:
            Health check result
        """
        provider = self.get_or_raise(name)
        return await provider.health_check()

    async def check_all_health(self) -> dict[str, ProviderHealth]:
        """
        Check health of all providers.

        Returns:
            Dictionary mapping provider names to health results
        """
        results = {}

        async def check_one(provider: BaseProvider) -> tuple[str, ProviderHealth]:
            try:
                health = await provider.health_check()
            except Exception as e:
                health = ProviderHealth(
                    status=ProviderStatus.UNHEALTHY,
                    error=str(e),
                )
            return provider.name, health

        # Run health checks concurrently
        tasks = [check_one(p) for p in self._providers.values()]
        for coro in asyncio.as_completed(tasks):
            name, health = await coro
            results[name] = health

        return results

    async def start_health_monitoring(self, interval: float = 60.0) -> None:
        """
        Start background health monitoring.

        Args:
            interval: Seconds between health checks
        """
        self._health_check_interval = interval

        async def monitor() -> None:
            while True:
                try:
                    await self.check_all_health()
                except Exception as e:
                    logger.error(f"Health check failed: {e}")
                await asyncio.sleep(self._health_check_interval)

        self._health_check_task = asyncio.create_task(monitor())
        logger.info(f"Started health monitoring (interval: {interval}s)")

    async def stop_health_monitoring(self) -> None:
        """Stop background health monitoring."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            logger.info("Stopped health monitoring")

    def to_dict(self) -> dict[str, Any]:
        """
        Get registry state as dictionary.

        Returns:
            Dictionary with provider information
        """
        return {
            "providers": {name: p.to_dict() for name, p in self._providers.items()},
            "total": len(self._providers),
            "healthy": len(self.list_healthy_providers()),
            "configured": len(self.list_configured_providers()),
        }


# Global registry instance
_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    """
    Get the global provider registry.

    Returns:
        Global registry instance
    """
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry (for testing)."""
    global _registry
    _registry = None
