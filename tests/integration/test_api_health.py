"""Integration tests for health and status endpoints."""

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, test_client: AsyncClient):
        """Health endpoint should not require authentication."""
        response = await test_client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_returns_json(self, test_client: AsyncClient):
        """Health endpoint should return JSON."""
        response = await test_client.get("/health")

        assert response.headers.get("content-type") == "application/json"

    @pytest.mark.asyncio
    async def test_health_response_structure(self, test_client: AsyncClient):
        """Health endpoint should have expected structure."""
        response = await test_client.get("/health")

        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"


class TestRootEndpoint:
    """Tests for / root endpoint."""

    @pytest.mark.asyncio
    async def test_root_no_auth_required(self, test_client: AsyncClient):
        """Root endpoint should not require authentication."""
        response = await test_client.get("/")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_root_returns_service_info(self, test_client: AsyncClient):
        """Root endpoint should return service information."""
        response = await test_client.get("/")

        data = response.json()
        assert "service" in data
        assert "version" in data
        assert data["version"] == "0.1.0"


class TestStatusEndpoint:
    """Tests for /v1/status endpoint."""

    @pytest.mark.asyncio
    async def test_status_requires_auth(self, test_client: AsyncClient):
        """Status endpoint should require authentication."""
        response = await test_client.get("/v1/status")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_status_with_valid_key(self, authenticated_client: AsyncClient):
        """Status endpoint should return status with valid key."""
        response = await authenticated_client.get("/v1/status")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_status_response_structure(self, authenticated_client: AsyncClient):
        """Status endpoint should have expected structure."""
        response = await authenticated_client.get("/v1/status")

        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"


class TestHealthEndpointBypassesRateLimiting:
    """Tests that health endpoints bypass rate limiting."""

    @pytest.mark.asyncio
    async def test_health_bypasses_rate_limit(self, test_client: AsyncClient, mock_redis):
        """Health endpoint should bypass rate limiting."""
        from unittest.mock import AsyncMock

        # Configure mock to deny all requests
        mock_redis.evalsha = AsyncMock(return_value=[0, 1000, 60])

        # Health should still work
        response = await test_client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_root_bypasses_rate_limit(self, test_client: AsyncClient, mock_redis):
        """Root endpoint should bypass rate limiting."""
        from unittest.mock import AsyncMock

        # Configure mock to deny all requests
        mock_redis.evalsha = AsyncMock(return_value=[0, 1000, 60])

        # Root should still work
        response = await test_client.get("/")
        assert response.status_code == 200
