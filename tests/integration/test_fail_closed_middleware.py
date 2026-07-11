"""Integration tests for fail-closed behavior in the rate-limit middleware.

Existing tests mock Redis as available (happy path). These specifically force
the rate-limit backend to be unavailable and assert the fail-closed 503 vs the
legacy fail-open passthrough.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from src.config import settings


class TestRateLimitMiddlewareFailClosed:
    @pytest.mark.asyncio
    async def test_check_raises_fail_closed_returns_503(
        self, authenticated_client: AsyncClient, monkeypatch
    ):
        monkeypatch.setattr(settings, "security_fail_closed", True)
        # Force check_rate_limit to raise a connection error inside the middleware.
        from src.api import main

        monkeypatch.setattr(
            main, "check_rate_limit", AsyncMock(side_effect=ConnectionError("redis down"))
        )

        resp = await authenticated_client.get("/v1/templates")
        assert resp.status_code == 503
        assert resp.headers.get("Retry-After") is not None

    @pytest.mark.asyncio
    async def test_check_raises_fail_open_passes_through(
        self, authenticated_client: AsyncClient, monkeypatch
    ):
        monkeypatch.setattr(settings, "security_fail_closed", False)
        from src.api import main

        monkeypatch.setattr(
            main, "check_rate_limit", AsyncMock(side_effect=ConnectionError("redis down"))
        )

        resp = await authenticated_client.get("/v1/templates")
        # Legacy fail-open: request proceeds (200 list).
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_degraded_result_returns_503(
        self, authenticated_client: AsyncClient, monkeypatch
    ):
        monkeypatch.setattr(settings, "security_fail_closed", True)
        from src.api import main
        from src.services.rate_limiter import RateLimitResult

        degraded = RateLimitResult(
            allowed=False, limit=10, remaining=0, reset_after_seconds=42, degraded=True
        )
        monkeypatch.setattr(main, "check_rate_limit", AsyncMock(return_value=degraded))

        resp = await authenticated_client.get("/v1/templates")
        assert resp.status_code == 503
        assert resp.headers.get("Retry-After") == "42"
