"""
FastAPI application factory and server setup.

This module creates and configures the FastAPI application with:
- CORS middleware
- Request logging
- Debug data storage
- Error handling
- Route registration
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from a2c.debug import close_database, init_database
from a2c.providers import (
    AnthropicProvider,
    AntigravityProvider,
    get_registry,
)
from a2c.server.config import get_settings
from a2c.server.middleware import DebugLoggingMiddleware
from a2c.server.routes import admin, anthropic, debug, health
from a2c.server.websocket import router as ws_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events:
    - Initialize database
    - Register default providers
    - Start health monitoring
    - Cleanup on shutdown
    """
    settings = get_settings()
    registry = get_registry()

    # Initialize debug database
    if settings.database.enabled:
        try:
            await init_database()
            logger.info("Debug database initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize debug database: {e}")
            logger.warning("Debug storage will be disabled")

    # Register default providers
    logger.info("Registering providers...")

    # Anthropic provider
    if settings.providers.anthropic_api_key:
        registry.register(AnthropicProvider())
        logger.info("Registered Anthropic provider")

    # Antigravity provider
    if settings.providers.google_api_key or settings.providers.antigravity_project_id:
        registry.register(AntigravityProvider())
        logger.info("Registered Antigravity provider")

    # Start health monitoring
    await registry.start_health_monitoring(interval=60.0)

    logger.info(f"Server starting on {settings.server.host}:{settings.server.port}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await registry.stop_health_monitoring()

    # Close provider connections
    for provider in registry.list_providers():
        close_fn = getattr(provider, "close", None)
        if close_fn is not None:
            await close_fn()

    # Close database connection
    if settings.database.enabled:
        await close_database()
        logger.info("Debug database closed")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI instance
    """
    settings = get_settings()

    app = FastAPI(
        title="a2c - AI API Router",
        description="Route AI requests to multiple providers with intelligent routing",
        version="0.1.0",
        docs_url="/docs" if settings.server.debug_enabled else None,
        redoc_url="/redoc" if settings.server.debug_enabled else None,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add debug logging middleware
    if settings.database.enabled:
        app.add_middleware(DebugLoggingMiddleware)

    # Register routes
    app.include_router(health.router, prefix="/health", tags=["Health"])
    app.include_router(anthropic.router, prefix="/v1", tags=["Anthropic API"])
    app.include_router(admin.router, prefix="/admin", tags=["Admin"])

    # Register debug routes if enabled
    if settings.server.debug_enabled:
        app.include_router(debug.router, prefix="/debug", tags=["Debug"])

    # Register WebSocket routes
    app.include_router(ws_router, prefix="/ws", tags=["WebSocket"])

    @app.get("/")
    async def root() -> dict:  # pyright: ignore[reportUnusedFunction]
        """Root endpoint with basic info."""
        return {
            "name": "a2c",
            "version": "0.1.0",
            "status": "running",
            "docs": "/docs" if settings.server.debug_enabled else None,
        }

    return app


# Create default app instance
app = create_app()
