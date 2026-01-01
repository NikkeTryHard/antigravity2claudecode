"""
a2c.server - FastAPI server application.

Note: app and create_app are imported lazily to avoid circular imports.
Use `from a2c.server.app import app, create_app` directly when needed.
"""

from a2c.server.config import Settings, get_settings


def __getattr__(name: str):
    """Lazy import for app to avoid circular imports."""
    if name in ("app", "create_app"):
        from a2c.server.app import app, create_app

        if name == "app":
            return app
        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["app", "create_app", "Settings", "get_settings"]
