"""
Database connection management.

Provides async database engine and session management for PostgreSQL.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from a2c.server.config import get_settings

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str:
    """
    Get database URL from settings.

    Returns:
        PostgreSQL async connection URL
    """
    settings = get_settings()
    url = settings.database.url

    # Ensure we use asyncpg driver
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    return url


async def init_database() -> None:
    """
    Initialize database connection and create tables.

    Should be called during application startup.
    """
    global _engine, _session_factory

    if _engine is not None:
        return

    settings = get_settings()
    url = get_database_url()
    logger.info(f"Connecting to database: {url.split('@')[-1]}")

    _engine = create_async_engine(
        url,
        echo=False,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_pre_ping=True,
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create tables
    from a2c.debug.models import Base

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized")


async def close_database() -> None:
    """
    Close database connection.

    Should be called during application shutdown.
    """
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connection closed")


def get_engine() -> AsyncEngine:
    """Get the database engine."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the session factory."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Get a database session.

    Usage:
        async with get_session() as session:
            # Use session
            ...

    Yields:
        AsyncSession: Database session
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def check_database_health() -> dict[str, bool | float | str | None]:
    """
    Check database connectivity and health.

    Returns:
        Dict with connection status, latency, and any error
    """
    import time

    from sqlalchemy import text

    if _engine is None:
        return {
            "connected": False,
            "latency_ms": None,
            "error": "Database not initialized",
        }

    try:
        start = time.perf_counter()
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000

        return {
            "connected": True,
            "latency_ms": round(latency, 2),
            "error": None,
        }
    except Exception as e:
        return {
            "connected": False,
            "latency_ms": None,
            "error": str(e),
        }
