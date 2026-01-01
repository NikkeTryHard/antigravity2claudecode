"""
a2c.router - Request routing system.

Routes requests to providers based on configurable rules.
"""

from a2c.router.config import (
    ConfigValidationError,
    RoutingConfig,
    load_routing_config,
    validate_routing_config,
)
from a2c.router.failover import (
    FailoverResult,
    FailoverService,
)
from a2c.router.rules import (
    AgentType,
    Router,
    RoutingRule,
    create_default_router,
    get_router,
    reset_router,
)

__all__ = [
    # Rules
    "AgentType",
    "Router",
    "RoutingRule",
    "create_default_router",
    "get_router",
    "reset_router",
    # Config
    "ConfigValidationError",
    "RoutingConfig",
    "load_routing_config",
    "validate_routing_config",
    # Failover
    "FailoverResult",
    "FailoverService",
]
