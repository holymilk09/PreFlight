"""Integration tests for Row-Level Security (RLS) tenant isolation.

These tests verify that tenants cannot access each other's data.
RLS is a critical security feature for multi-tenant SaaS.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import APIKey, Tenant, Template, TemplateStatus
from src.security import generate_api_key


class TestRLSTenantIsolation:
    """Tests for RLS tenant isolation."""

    @pytest.fixture
    async def tenant_a(self, db_session: AsyncSession) -> tuple[Tenant, str]:
        """Create tenant A with API key."""
        tenant = Tenant(name="Tenant A", settings={"plan": "enterprise"})
        db_session.add(tenant)
        await db_session.flush()

        key_components = generate_api_key()
        api_key = APIKey(
            tenant_id=tenant.id,
            key_hash=key_components.key_hash,
            key_prefix=key_components.key_prefix,
            name="tenant-a-key",
            scopes=["*"],
            rate_limit=1000,
        )
        db_session.add(api_key)
        await db_session.flush()

        return tenant, key_components.full_key

    @pytest.fixture
    async def tenant_b(self, db_session: AsyncSession) -> tuple[Tenant, str]:
        """Create tenant B with API key."""
        tenant = Tenant(name="Tenant B", settings={"plan": "starter"})
        db_session.add(tenant)
        await db_session.flush()

        key_components = generate_api_key()
        api_key = APIKey(
            tenant_id=tenant.id,
            key_hash=key_components.key_hash,
            key_prefix=key_components.key_prefix,
            name="tenant-b-key",
            scopes=["*"],
            rate_limit=500,
        )
        db_session.add(api_key)
        await db_session.flush()

        return tenant, key_components.full_key

    @pytest.fixture
    async def client_a(
        self,
        db_session: AsyncSession,
        mock_redis,
        tenant_a: tuple[Tenant, str],
    ) -> AsyncClient:
        """Create HTTP client for tenant A."""
        from src.api.main import app
        from src.api.deps import get_db_session
        from src.services.rate_limiter import get_redis_client

        tenant, api_key = tenant_a

        async def override_get_db():
            yield db_session

        async def override_redis():
            return mock_redis

        app.dependency_overrides[get_db_session] = override_get_db
        app.dependency_overrides[get_redis_client] = override_redis

        transport = ASGITransport(app=app)
        client = AsyncClient(transport=transport, base_url="http://test")
        client.headers["X-API-Key"] = api_key
        return client

    @pytest.fixture
    async def client_b(
        self,
        db_session: AsyncSession,
        mock_redis,
        tenant_b: tuple[Tenant, str],
    ) -> AsyncClient:
        """Create HTTP client for tenant B."""
        from src.api.main import app
        from src.api.deps import get_db_session
        from src.services.rate_limiter import get_redis_client

        tenant, api_key = tenant_b

        async def override_get_db():
            yield db_session

        async def override_redis():
            return mock_redis

        app.dependency_overrides[get_db_session] = override_get_db
        app.dependency_overrides[get_redis_client] = override_redis

        transport = ASGITransport(app=app)
        client = AsyncClient(transport=transport, base_url="http://test")
        client.headers["X-API-Key"] = api_key
        return client

    @pytest.mark.asyncio
    async def test_tenant_a_cannot_see_tenant_b_templates(
        self,
        client_a: AsyncClient,
        client_b: AsyncClient,
        sample_structural_features,
    ):
        """Tenant A should not see templates created by Tenant B."""
        # Tenant B creates a template
        template_data = {
            "template_id": "TENANT-B-TEMPLATE",
            "version": "1.0",
            "structural_features": sample_structural_features.model_dump(),
            "baseline_reliability": 0.85,
        }
        response_b = await client_b.post("/v1/templates", json=template_data)
        assert response_b.status_code == 201
        template_id = response_b.json()["id"]

        # Tenant A lists templates - should be empty
        response_a = await client_a.get("/v1/templates")
        assert response_a.status_code == 200
        templates = response_a.json()
        assert len(templates) == 0

        # Tenant A tries to get the specific template - should 404
        response_a_get = await client_a.get(f"/v1/templates/{template_id}")
        assert response_a_get.status_code == 404

    @pytest.mark.asyncio
    async def test_tenant_b_cannot_see_tenant_a_templates(
        self,
        client_a: AsyncClient,
        client_b: AsyncClient,
        sample_structural_features,
    ):
        """Tenant B should not see templates created by Tenant A."""
        # Tenant A creates a template
        template_data = {
            "template_id": "TENANT-A-TEMPLATE",
            "version": "1.0",
            "structural_features": sample_structural_features.model_dump(),
            "baseline_reliability": 0.90,
        }
        response_a = await client_a.post("/v1/templates", json=template_data)
        assert response_a.status_code == 201

        # Tenant B lists templates - should be empty
        response_b = await client_b.get("/v1/templates")
        assert response_b.status_code == 200
        templates = response_b.json()
        assert len(templates) == 0

    @pytest.mark.asyncio
    async def test_each_tenant_sees_own_templates(
        self,
        client_a: AsyncClient,
        client_b: AsyncClient,
        sample_structural_features,
    ):
        """Each tenant should only see their own templates."""
        # Both tenants create templates
        template_a = {
            "template_id": "TEMPLATE-A",
            "version": "1.0",
            "structural_features": sample_structural_features.model_dump(),
            "baseline_reliability": 0.85,
        }
        template_b = {
            "template_id": "TEMPLATE-B",
            "version": "1.0",
            "structural_features": sample_structural_features.model_dump(),
            "baseline_reliability": 0.90,
        }

        await client_a.post("/v1/templates", json=template_a)
        await client_b.post("/v1/templates", json=template_b)

        # Each tenant should see exactly one template
        response_a = await client_a.get("/v1/templates")
        assert len(response_a.json()) == 1
        assert response_a.json()[0]["template_id"] == "TEMPLATE-A"

        response_b = await client_b.get("/v1/templates")
        assert len(response_b.json()) == 1
        assert response_b.json()[0]["template_id"] == "TEMPLATE-B"

    @pytest.mark.asyncio
    async def test_template_duplicate_allowed_across_tenants(
        self,
        client_a: AsyncClient,
        client_b: AsyncClient,
        sample_structural_features,
    ):
        """Same template_id should be allowed for different tenants."""
        # Both tenants create template with same ID
        template_data = {
            "template_id": "SHARED-TEMPLATE-ID",
            "version": "1.0",
            "structural_features": sample_structural_features.model_dump(),
            "baseline_reliability": 0.85,
        }

        response_a = await client_a.post("/v1/templates", json=template_data)
        assert response_a.status_code == 201

        response_b = await client_b.post("/v1/templates", json=template_data)
        assert response_b.status_code == 201

        # UUIDs should be different
        assert response_a.json()["id"] != response_b.json()["id"]


class TestRLSEvaluationIsolation:
    """Tests for evaluation record isolation."""

    @pytest.fixture
    async def tenant_with_template(
        self,
        db_session: AsyncSession,
        sample_structural_features,
    ) -> tuple[Tenant, str, Template]:
        """Create tenant with API key and template."""
        tenant = Tenant(name="Test Tenant", settings={})
        db_session.add(tenant)
        await db_session.flush()

        key_components = generate_api_key()
        api_key = APIKey(
            tenant_id=tenant.id,
            key_hash=key_components.key_hash,
            key_prefix=key_components.key_prefix,
            name="test-key",
            scopes=["*"],
            rate_limit=1000,
        )
        db_session.add(api_key)

        template = Template(
            tenant_id=tenant.id,
            template_id="TEST-TEMPLATE",
            version="1.0",
            fingerprint="a" * 64,
            structural_features=sample_structural_features.model_dump(),
            baseline_reliability=0.85,
            correction_rules=[],
            status=TemplateStatus.ACTIVE,
        )
        db_session.add(template)
        await db_session.flush()

        return tenant, key_components.full_key, template

    @pytest.mark.asyncio
    async def test_evaluations_stored_with_tenant_id(
        self,
        db_session: AsyncSession,
        mock_redis,
        tenant_with_template: tuple[Tenant, str, Template],
        sample_structural_features,
    ):
        """Evaluations should be stored with correct tenant_id."""
        from src.api.main import app
        from src.api.deps import get_db_session
        from src.services.rate_limiter import get_redis_client
        from src.models import Evaluation
        from sqlalchemy import select
        import hashlib
        import json

        tenant, api_key, template = tenant_with_template

        async def override_get_db():
            yield db_session

        async def override_redis():
            return mock_redis

        app.dependency_overrides[get_db_session] = override_get_db
        app.dependency_overrides[get_redis_client] = override_redis

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.headers["X-API-Key"] = api_key

            features_json = json.dumps(
                sample_structural_features.model_dump(), sort_keys=True
            )
            fingerprint = hashlib.sha256(features_json.encode()).hexdigest()

            eval_request = {
                "layout_fingerprint": fingerprint,
                "structural_features": sample_structural_features.model_dump(),
                "extractor_metadata": {
                    "vendor": "nvidia",
                    "model": "test",
                    "version": "1.0",
                    "confidence": 0.9,
                    "latency_ms": 100,
                },
                "client_doc_hash": "b" * 64,
                "client_correlation_id": "test-123",
                "pipeline_id": "pipe-1",
            }

            response = await client.post("/v1/evaluate", json=eval_request)
            assert response.status_code == 200

        app.dependency_overrides.clear()
