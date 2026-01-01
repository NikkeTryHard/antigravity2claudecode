"""
Debug infrastructure for request/response logging and replay.

Provides database storage and retrieval for debugging API requests.
"""

from a2c.debug.database import (
    check_database_health,
    close_database,
    get_engine,
    get_session,
    get_session_factory,
    init_database,
)
from a2c.debug.models import Base, MetricsHourly, Request, SSEEvent
from a2c.debug.store import DebugStore, get_debug_store

__all__ = [
    # Database
    "init_database",
    "close_database",
    "get_engine",
    "get_session",
    "get_session_factory",
    "check_database_health",
    # Models
    "Base",
    "Request",
    "SSEEvent",
    "MetricsHourly",
    # Store
    "DebugStore",
    "get_debug_store",
]
