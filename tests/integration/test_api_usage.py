"""Integration tests for the usage metering endpoint and quota enforcement.

Require Postgres (run in CI). Quota enforcement is exercised by rewriting the
test tenant's plan settings and toggling USAGE_ENFORCE_QUOTA on the shared
settings instance.
"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import settings
from src.models import Tenant


async def _set_tenant_plan(test_engine, tenant_id, plan_settings: dict) -> None:
    """Rewrite the test tenant's settings JSONB (plan / custom limit)."""
    session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        tenant = await session.get(Tenant, tenant_id)
        assert tenant is not None
        tenant.settings = plan_settings
        session.add(tenant)
        await session.commit()


class TestUsageAuth:
    @pytest.mark.asyncio
    async def test_usage_requires_auth(self, test_client: AsyncClient):
        resp = await test_client.get("/v1/usage")
        assert resp.status_code == 401


class TestUsageMetering:
    @pytest.mark.asyncio
    async def test_usage_empty_enterprise_tenant(self, authenticated_client: AsyncClient):
        """The fixture tenant is on the enterprise plan: unlimited, zero used."""
        resp = await authenticated_client.get("/v1/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "enterprise"
        assert data["monthly_limit"] is None
        assert data["used"] == 0
        assert data["remaining"] is None
        assert data["enforcement_enabled"] is False

    @pytest.mark.asyncio
    async def test_usage_counts_evaluations(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        for _ in range(2):
            resp = await authenticated_client.post("/v1/evaluate", json=valid_evaluate_request_data)
            assert resp.status_code == 200

        resp = await authenticated_client.get("/v1/usage")
        assert resp.status_code == 200
        assert resp.json()["used"] == 2

    @pytest.mark.asyncio
    async def test_usage_reports_plan_limit_and_remaining(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
        test_engine,
        test_tenant: Tenant,
    ):
        await _set_tenant_plan(test_engine, test_tenant.id, {"plan": "free"})

        resp = await authenticated_client.post("/v1/evaluate", json=valid_evaluate_request_data)
        assert resp.status_code == 200

        resp = await authenticated_client.get("/v1/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "free"
        assert data["monthly_limit"] == 1_000
        assert data["used"] == 1
        assert data["remaining"] == 999


class TestQuotaEnforcement:
    @pytest.mark.asyncio
    async def test_exhausted_quota_blocks_evaluate_when_enforced(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
        test_engine,
        test_tenant: Tenant,
    ):
        """With enforcement on and a zero limit, evaluate returns 429 QUOTA_EXCEEDED."""
        await _set_tenant_plan(
            test_engine, test_tenant.id, {"plan": "free", "monthly_evaluation_limit": 0}
        )

        with patch.object(settings, "usage_enforce_quota", True):
            resp = await authenticated_client.post("/v1/evaluate", json=valid_evaluate_request_data)

        assert resp.status_code == 429
        assert resp.json()["detail"]["code"] == "QUOTA_EXCEEDED"

    @pytest.mark.asyncio
    async def test_exhausted_quota_is_metering_only_by_default(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
        test_engine,
        test_tenant: Tenant,
    ):
        """Default posture: an exhausted quota never blocks the pipeline."""
        await _set_tenant_plan(
            test_engine, test_tenant.id, {"plan": "free", "monthly_evaluation_limit": 0}
        )

        resp = await authenticated_client.post("/v1/evaluate", json=valid_evaluate_request_data)
        assert resp.status_code == 200

        resp = await authenticated_client.get("/v1/usage")
        data = resp.json()
        assert data["monthly_limit"] == 0
        assert data["used"] == 1
        assert data["remaining"] == 0
