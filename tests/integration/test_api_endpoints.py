"""
Integration tests for API endpoints.

Tests the health, admin, and debug API endpoints.
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Set database to disabled for tests
os.environ["A2C_DATABASE_ENABLED"] = "false"

from a2c.server.app import create_app


@pytest.fixture
def app():
    """Create test application."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    async def test_liveness(self, client: AsyncClient):
        """Test liveness probe returns 200."""
        response = await client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    async def test_readiness(self, client: AsyncClient):
        """Test readiness probe returns status."""
        response = await client.get("/health/ready")
        # May be 200 or 503 depending on provider state
        assert response.status_code in (200, 503)
        data = response.json()
        assert data["status"] in ("ready", "not_ready")
        assert "providers" in data

    async def test_health_summary(self, client: AsyncClient):
        """Test health summary endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "server" in data
        assert "providers" in data
        assert data["server"]["status"] == "running"

    async def test_provider_health(self, client: AsyncClient):
        """Test provider health endpoint."""
        response = await client.get("/health/providers")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "providers" in data


class TestAdminEndpoints:
    """Tests for admin API endpoints."""

    async def test_get_config(self, client: AsyncClient):
        """Test config endpoint returns configuration."""
        response = await client.get("/admin/config")
        assert response.status_code == 200
        data = response.json()
        assert "server" in data
        assert "routing" in data
        assert "providers" in data

    async def test_list_providers(self, client: AsyncClient):
        """Test list providers endpoint."""
        response = await client.get("/admin/providers")
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data

    async def test_get_provider_not_found(self, client: AsyncClient):
        """Test get provider returns 404 for unknown provider."""
        response = await client.get("/admin/providers/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    async def test_get_routing_rules(self, client: AsyncClient):
        """Test routing rules endpoint."""
        response = await client.get("/admin/routing/rules")
        assert response.status_code == 200
        data = response.json()
        assert "rules" in data

    async def test_test_routing(self, client: AsyncClient):
        """Test routing test endpoint."""
        response = await client.get(
            "/admin/routing/test",
            params={"model": "claude-opus-4-5", "thinking": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert "input" in data
        assert "result" in data
        assert "provider" in data["result"]

    async def test_get_stats(self, client: AsyncClient):
        """Test stats endpoint."""
        response = await client.get("/admin/stats")
        assert response.status_code == 200
        data = response.json()
        assert "requests" in data
        assert "latency" in data
        assert "tokens" in data


class TestDebugEndpoints:
    """Tests for debug API endpoints (database disabled)."""

    async def test_list_requests_db_disabled(self, client: AsyncClient):
        """Test list requests returns empty when database disabled."""
        response = await client.get("/debug/requests")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["items"] == []
        assert data["total"] == 0

    async def test_get_stats_db_disabled(self, client: AsyncClient):
        """Test debug stats returns zeros when database disabled."""
        response = await client.get("/debug/stats", params={"hours": 24})
        assert response.status_code == 200
        data = response.json()
        assert "period_hours" in data
        assert data["total_requests"] == 0
        assert data["total_errors"] == 0


class TestWebSocketEndpoints:
    """Tests for WebSocket endpoints."""

    async def test_connections_info(self, client: AsyncClient):
        """Test WebSocket connections info endpoint."""
        response = await client.get("/ws/connections")
        assert response.status_code == 200
        data = response.json()
        assert "total_connections" in data
        assert "topics" in data


class TestOpenAPIEndpoints:
    """Tests for OpenAPI documentation endpoints."""

    async def test_openapi_json(self, client: AsyncClient):
        """Test OpenAPI JSON endpoint."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    async def test_docs_redirect(self, client: AsyncClient):
        """Test docs endpoint returns HTML."""
        response = await client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
