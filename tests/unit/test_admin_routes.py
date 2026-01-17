"""Tests for admin API routes."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi import HTTPException


class TestRequireAdmin:
    """Tests for require_admin dependency."""

    @pytest.mark.asyncio
    async def test_require_admin_with_admin_scope(self):
        """Should allow tenant with admin scope."""
        from src.api.admin_routes import require_admin
        from src.api.auth import AuthenticatedTenant

        tenant = AuthenticatedTenant(
            tenant_id=uuid4(),
            tenant_name="Test Tenant",
            api_key_id=uuid4(),
            api_key_name="admin-key",
            scopes=["admin"],
            rate_limit=1000,
        )

        result = await require_admin(tenant)

        assert result == tenant

    @pytest.mark.asyncio
    async def test_require_admin_with_wildcard_scope(self):
        """Should allow tenant with wildcard scope."""
        from src.api.admin_routes import require_admin
        from src.api.auth import AuthenticatedTenant

        tenant = AuthenticatedTenant(
            tenant_id=uuid4(),
            tenant_name="Test Tenant",
            api_key_id=uuid4(),
            api_key_name="super-key",
            scopes=["*"],
            rate_limit=1000,
        )

        result = await require_admin(tenant)

        assert result == tenant

    @pytest.mark.asyncio
    async def test_require_admin_without_admin_scope(self):
        """Should reject tenant without admin scope."""
        from src.api.admin_routes import require_admin
        from src.api.auth import AuthenticatedTenant

        tenant = AuthenticatedTenant(
            tenant_id=uuid4(),
            tenant_name="Test Tenant",
            api_key_id=uuid4(),
            api_key_name="user-key",
            scopes=["read", "write"],  # No admin scope
            rate_limit=1000,
        )

        with pytest.raises(HTTPException) as exc:
            await require_admin(tenant)

        assert exc.value.status_code == 403
        assert "Admin scope required" in exc.value.detail


class TestSchemas:
    """Tests for admin route schemas."""

    def test_tenant_create_schema(self):
        """TenantCreate should validate name."""
        from src.api.admin_routes import TenantCreate

        data = TenantCreate(name="Test Tenant")
        assert data.name == "Test Tenant"

    def test_tenant_response_schema(self):
        """TenantResponse should include all fields."""
        from src.api.admin_routes import TenantResponse
        from datetime import datetime

        now = datetime.utcnow()
        response = TenantResponse(
            id=uuid4(),
            name="Test Tenant",
            created_at=now,
            settings={},
            api_key_count=5,
            template_count=3,
        )

        assert response.name == "Test Tenant"
        assert response.api_key_count == 5

    def test_api_key_create_schema(self):
        """APIKeyCreate should validate all fields."""
        from src.api.admin_routes import APIKeyCreate

        data = APIKeyCreate(
            name="test-key",
            scopes=["read", "write"],
            rate_limit=1000,
        )

        assert data.name == "test-key"
        assert "read" in data.scopes
        assert data.rate_limit == 1000

    def test_api_key_response_schema(self):
        """APIKeyResponse should include all fields."""
        from src.api.admin_routes import APIKeyResponse
        from datetime import datetime

        now = datetime.utcnow()
        response = APIKeyResponse(
            id=uuid4(),
            tenant_id=uuid4(),
            name="test-key",
            key_prefix="cp_1234",
            scopes=["read"],
            rate_limit=1000,
            created_at=now,
            last_used_at=now,
            revoked_at=None,
            is_active=True,
        )

        assert response.name == "test-key"
        assert response.key_prefix == "cp_1234"

    def test_api_key_create_response(self):
        """APIKeyCreateResponse should include api_key."""
        from src.api.admin_routes import APIKeyCreateResponse
        from datetime import datetime

        now = datetime.utcnow()
        response = APIKeyCreateResponse(
            id=uuid4(),
            tenant_id=uuid4(),
            name="test-key",
            key_prefix="cp_1234",
            scopes=["read"],
            rate_limit=1000,
            created_at=now,
            api_key="cp_abcdef1234567890abcdef1234567890",
        )

        assert response.api_key.startswith("cp_")
