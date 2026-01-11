"""Integration tests for /metrics endpoint."""

import pytest
from httpx import AsyncClient


class TestMetricsEndpoint:
    """Tests for /metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_no_auth_required(self, test_client: AsyncClient):
        """Metrics endpoint should not require authentication."""
        response = await test_client.get("/metrics")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_returns_prometheus_format(self, test_client: AsyncClient):
        """Metrics endpoint should return Prometheus text format."""
        response = await test_client.get("/metrics")

        content_type = response.headers.get("content-type", "")
        # Prometheus format uses text/plain or openmetrics
        assert "text/plain" in content_type or "openmetrics" in content_type.lower()

    @pytest.mark.asyncio
    async def test_metrics_contains_request_metrics(self, test_client: AsyncClient):
        """Metrics endpoint should contain request count metrics."""
        response = await test_client.get("/metrics")
        content = response.text

        assert "preflight_requests_total" in content
        assert "preflight_request_duration_seconds" in content

    @pytest.mark.asyncio
    async def test_metrics_contains_evaluation_metrics(self, test_client: AsyncClient):
        """Metrics endpoint should contain evaluation metrics."""
        response = await test_client.get("/metrics")
        content = response.text

        assert "preflight_evaluations_total" in content
        assert "preflight_template_matches_total" in content
        assert "preflight_drift_score" in content
        assert "preflight_reliability_score" in content

    @pytest.mark.asyncio
    async def test_metrics_contains_security_metrics(self, test_client: AsyncClient):
        """Metrics endpoint should contain security metrics."""
        response = await test_client.get("/metrics")
        content = response.text

        assert "preflight_rate_limit_hits_total" in content
        assert "preflight_auth_failures_total" in content


class TestMetricsRequestTracking:
    """Tests for request metrics tracking."""

    @pytest.mark.asyncio
    async def test_health_request_increments_counter(self, test_client: AsyncClient):
        """Health requests should increment request counter."""
        # Make a few health requests
        for _ in range(3):
            await test_client.get("/health")

        # Check metrics
        response = await test_client.get("/metrics")
        content = response.text

        # Should have health endpoint metrics
        assert 'endpoint="/health"' in content
        assert 'method="GET"' in content
        assert 'status="200"' in content

    @pytest.mark.asyncio
    async def test_metrics_request_not_tracked(self, test_client: AsyncClient):
        """Metrics endpoint should not track its own requests."""
        # Make metrics requests
        await test_client.get("/metrics")
        await test_client.get("/metrics")

        # Check metrics
        response = await test_client.get("/metrics")
        content = response.text

        # Should NOT have /metrics endpoint in the metrics (would cause recursion)
        # Look for the exact pattern that would indicate /metrics is being tracked
        lines = content.split("\n")
        metrics_tracked = any(
            'endpoint="/metrics"' in line and "preflight_requests_total" in line for line in lines
        )
        assert not metrics_tracked


class TestMetricsBypassesRateLimiting:
    """Tests that metrics endpoint bypasses rate limiting."""

    @pytest.mark.asyncio
    async def test_metrics_bypasses_rate_limit(self, test_client: AsyncClient, mock_redis):
        """Metrics endpoint should bypass rate limiting."""
        from unittest.mock import AsyncMock

        # Configure mock to deny all requests
        mock_redis.evalsha = AsyncMock(return_value=[0, 1000, 60])

        # Metrics should still work
        response = await test_client.get("/metrics")
        assert response.status_code == 200
