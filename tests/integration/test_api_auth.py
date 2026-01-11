"""Integration tests for API authentication."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


class TestAPIKeyAuthentication:
    """Tests for API key authentication flow."""

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_401(self, test_client: AsyncClient):
        """Request without API key should return 401."""
        response = await test_client.get("/v1/status")

        assert response.status_code == 401
        assert "Missing API key" in response.json()["detail"]
        assert response.headers.get("WWW-Authenticate") == "ApiKey"

    @pytest.mark.asyncio
    async def test_invalid_format_no_prefix_returns_401(self, test_client: AsyncClient):
        """API key without cp_ prefix should return 401."""
        response = await test_client.get(
            "/v1/status",
            headers={"X-API-Key": "abc123def456abc123def456abc123de"},
        )

        assert response.status_code == 401
        assert "Invalid API key format" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_invalid_format_wrong_length_returns_401(self, test_client: AsyncClient):
        """API key with wrong length should return 401."""
        response = await test_client.get(
            "/v1/status",
            headers={"X-API-Key": "cp_tooshort"},
        )

        assert response.status_code == 401
        assert "Invalid API key format" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_invalid_key_not_in_database_returns_401(self, test_client: AsyncClient):
        """API key not in database should return 401."""
        # Valid format but not in database
        fake_key = "cp_" + "a" * 32

        response = await test_client.get(
            "/v1/status",
            headers={"X-API-Key": fake_key},
        )

        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_valid_key_returns_200(self, authenticated_client: AsyncClient):
        """Valid API key should allow access."""
        response = await authenticated_client.get("/v1/status")

        assert response.status_code == 200
        assert "status" in response.json()

    @pytest.mark.asyncio
    async def test_revoked_key_returns_401(
        self,
        test_client: AsyncClient,
        test_api_key,
        test_engine,
    ):
        """Revoked API key should return 401."""
        from sqlalchemy import update
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from src.models import APIKey

        api_key_record, plain_key = test_api_key

        # Use a new session to update the key (must commit for visibility)
        session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        async with session_maker() as session:
            # Revoke the key via UPDATE statement
            stmt = (
                update(APIKey)
                .where(APIKey.id == api_key_record.id)
                .values(revoked_at=datetime.utcnow())
            )
            await session.execute(stmt)
            await session.commit()

        response = await test_client.get(
            "/v1/status",
            headers={"X-API-Key": plain_key},
        )

        assert response.status_code == 401
        assert "revoked" in response.json()["detail"].lower()


class TestAuthenticatedTenant:
    """Tests for AuthenticatedTenant class."""

    def test_has_scope_direct_match(self):
        """has_scope should return True for direct scope match."""
        from uuid_extensions import uuid7

        from src.api.auth import AuthenticatedTenant

        tenant = AuthenticatedTenant(
            tenant_id=uuid7(),
            tenant_name="Test",
            api_key_id=uuid7(),
            api_key_name="test-key",
            scopes=["read", "write"],
            rate_limit=1000,
        )

        assert tenant.has_scope("read") is True
        assert tenant.has_scope("write") is True
        assert tenant.has_scope("admin") is False

    def test_has_scope_wildcard(self):
        """has_scope should return True for wildcard scope."""
        from uuid_extensions import uuid7

        from src.api.auth import AuthenticatedTenant

        tenant = AuthenticatedTenant(
            tenant_id=uuid7(),
            tenant_name="Test",
            api_key_id=uuid7(),
            api_key_name="test-key",
            scopes=["*"],
            rate_limit=1000,
        )

        assert tenant.has_scope("anything") is True
        assert tenant.has_scope("read") is True
        assert tenant.has_scope("admin") is True

    def test_has_scope_empty_scopes(self):
        """has_scope should return False for empty scopes."""
        from uuid_extensions import uuid7

        from src.api.auth import AuthenticatedTenant

        tenant = AuthenticatedTenant(
            tenant_id=uuid7(),
            tenant_name="Test",
            api_key_id=uuid7(),
            api_key_name="test-key",
            scopes=[],
            rate_limit=1000,
        )

        assert tenant.has_scope("read") is False


class TestSecurityHeaders:
    """Tests for security headers on authenticated endpoints."""

    @pytest.mark.asyncio
    async def test_security_headers_present(self, authenticated_client: AsyncClient):
        """Security headers should be present on all responses."""
        response = await authenticated_client.get("/v1/status")

        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "strict-origin" in response.headers.get("Referrer-Policy", "")
        assert "no-store" in response.headers.get("Cache-Control", "")

    @pytest.mark.asyncio
    async def test_request_id_header_echoed(self, authenticated_client: AsyncClient):
        """X-Request-ID should be echoed in response."""
        request_id = "test-request-123"
        response = await authenticated_client.get(
            "/v1/status",
            headers={"X-Request-ID": request_id},
        )

        assert response.headers.get("X-Request-ID") == request_id

    @pytest.mark.asyncio
    async def test_request_id_generated_if_missing(self, authenticated_client: AsyncClient):
        """X-Request-ID should be generated if not provided."""
        response = await authenticated_client.get("/v1/status")

        request_id = response.headers.get("X-Request-ID")
        assert request_id is not None
        assert len(request_id) == 32  # 16 bytes hex


class TestAuthFailedLogging:
    """Tests for failed authentication logging."""

    @pytest.mark.asyncio
    async def test_invalid_key_logs_failed_attempt(
        self,
        test_client: AsyncClient,
        test_engine,
    ):
        """Invalid API key should log a failed authentication attempt."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from src.models import AuditAction, AuditLog

        # Make request with invalid key
        fake_key = "cp_" + "x" * 32
        await test_client.get(
            "/v1/status",
            headers={"X-API-Key": fake_key},
        )

        # Check audit log for failed attempt
        session_maker = async_sessionmaker(test_engine, class_=AsyncSession)
        async with session_maker() as session:
            stmt = select(AuditLog).where(AuditLog.action == AuditAction.AUTH_FAILED)
            result = await session.execute(stmt)
            logs = result.scalars().all()

            # Should have at least one failed auth log
            assert len(logs) >= 1
            latest_log = logs[-1]
            assert latest_log.details.get("reason") == "invalid"
            assert latest_log.details.get("key_prefix") == "cp_xxxxx"

    @pytest.mark.asyncio
    async def test_revoked_key_logs_failed_attempt(
        self,
        test_client: AsyncClient,
        test_api_key,
        test_engine,
    ):
        """Revoked API key should log a failed authentication attempt."""
        from sqlalchemy import select, update
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from src.models import APIKey, AuditAction, AuditLog

        api_key_record, plain_key = test_api_key

        # Revoke the key
        session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        async with session_maker() as session:
            stmt = (
                update(APIKey)
                .where(APIKey.id == api_key_record.id)
                .values(revoked_at=datetime.utcnow())
            )
            await session.execute(stmt)
            await session.commit()

        # Make request with revoked key
        await test_client.get(
            "/v1/status",
            headers={"X-API-Key": plain_key},
        )

        # Check audit log for revoked attempt
        async with session_maker() as session:
            stmt = select(AuditLog).where(AuditLog.action == AuditAction.AUTH_FAILED)
            result = await session.execute(stmt)
            logs = result.scalars().all()

            # Find the log with "revoked" reason
            revoked_logs = [log for log in logs if log.details.get("reason") == "revoked"]
            assert len(revoked_logs) >= 1


class TestAPIKeyLastUsedUpdate:
    """Tests for last_used_at timestamp update."""

    @pytest.mark.asyncio
    async def test_valid_key_updates_last_used_at(
        self,
        test_client: AsyncClient,
        test_api_key,
        test_engine,
    ):
        """Valid API key usage should update last_used_at timestamp."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from src.models import APIKey

        api_key_record, plain_key = test_api_key
        original_last_used = api_key_record.last_used_at

        # Make a valid request
        response = await test_client.get(
            "/v1/status",
            headers={"X-API-Key": plain_key},
        )
        assert response.status_code == 200

        # Check that last_used_at was updated
        session_maker = async_sessionmaker(test_engine, class_=AsyncSession)
        async with session_maker() as session:
            stmt = select(APIKey).where(APIKey.id == api_key_record.id)
            result = await session.execute(stmt)
            updated_key = result.scalar_one()

            assert updated_key.last_used_at is not None
            if original_last_used is not None:
                assert updated_key.last_used_at >= original_last_used


class TestRateLimiting:
    """Tests for rate limiting on authenticated endpoints."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(self, authenticated_client: AsyncClient):
        """Rate limit headers should be present on responses."""
        response = await authenticated_client.get("/v1/status")

        # Rate limit headers should be present
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_returns_429(self, test_client: AsyncClient, mock_redis):
        """Rate limit exceeded should return 429."""
        # Configure mock to return denied
        mock_redis.evalsha = AsyncMock(return_value=[0, 100, 45])  # denied, 100 requests, 45s reset

        # Make request with valid format key (will trigger rate limiting before auth)
        response = await test_client.get(
            "/v1/status",
            headers={"X-API-Key": "cp_" + "a" * 32},
        )

        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]
        assert response.headers.get("Retry-After") == "45"
