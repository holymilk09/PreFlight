"""Integration tests for API-key scope enforcement (src/api/auth.py require_scope)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models import APIKey, Tenant
from src.security import generate_api_key


async def _make_key(test_engine, tenant_id, scopes: list[str]) -> str:
    """Create an API key with the given scopes; return the plaintext key."""
    sm = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    kc = generate_api_key()
    async with sm() as s:
        s.add(
            APIKey(
                tenant_id=tenant_id,
                key_hash=kc.key_hash,
                key_prefix=kc.key_prefix,
                name=f"scoped-{'-'.join(scopes)}",
                scopes=scopes,
                rate_limit=1000,
            )
        )
        await s.commit()
    return kc.full_key


@pytest.mark.asyncio
class TestScopeEnforcement:
    """A key may only perform operations covered by its scopes; '*' covers all."""

    async def test_read_key_cannot_evaluate(
        self, test_client: AsyncClient, test_engine, test_tenant: Tenant
    ):
        key = await _make_key(test_engine, test_tenant.id, ["read"])
        r = await test_client.post("/v1/evaluate", headers={"X-API-Key": key}, json={})
        assert r.status_code == 403
        assert "evaluate" in r.json()["detail"]

    async def test_read_key_can_list_templates(
        self, test_client: AsyncClient, test_engine, test_tenant: Tenant
    ):
        key = await _make_key(test_engine, test_tenant.id, ["read"])
        r = await test_client.get("/v1/templates", headers={"X-API-Key": key})
        assert r.status_code != 403  # passes the scope gate (200 with empty list)

    async def test_evaluate_key_cannot_read_templates(
        self, test_client: AsyncClient, test_engine, test_tenant: Tenant
    ):
        key = await _make_key(test_engine, test_tenant.id, ["evaluate"])
        r = await test_client.get("/v1/templates", headers={"X-API-Key": key})
        assert r.status_code == 403

    async def test_read_key_cannot_manage_templates(
        self, test_client: AsyncClient, test_engine, test_tenant: Tenant
    ):
        key = await _make_key(test_engine, test_tenant.id, ["read"])
        r = await test_client.post("/v1/templates", headers={"X-API-Key": key}, json={})
        assert r.status_code == 403

    async def test_read_key_cannot_manage_alerts(
        self, test_client: AsyncClient, test_engine, test_tenant: Tenant
    ):
        key = await _make_key(test_engine, test_tenant.id, ["read"])
        r = await test_client.post("/v1/alert-rules", headers={"X-API-Key": key}, json={})
        assert r.status_code == 403

    async def test_wildcard_key_allowed_everywhere(
        self, test_client: AsyncClient, test_engine, test_tenant: Tenant
    ):
        key = await _make_key(test_engine, test_tenant.id, ["*"])
        # read endpoint
        assert (
            await test_client.get("/v1/templates", headers={"X-API-Key": key})
        ).status_code != 403
        # manage endpoint (bad body -> 422, but NOT 403)
        assert (
            await test_client.post("/v1/alert-rules", headers={"X-API-Key": key}, json={})
        ).status_code != 403
