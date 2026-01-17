"""Tests for API key authentication."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException


class TestAuthenticatedTenant:
    """Tests for AuthenticatedTenant class."""

    def test_has_scope_with_specific_scope(self):
        """Should return True when scope matches."""
        from src.api.auth import AuthenticatedTenant

        tenant = AuthenticatedTenant(
            tenant_id=uuid4(),
            tenant_name="Test",
            api_key_id=uuid4(),
            api_key_name="test-key",
            scopes=["read", "write"],
            rate_limit=1000,
        )

        assert tenant.has_scope("read") is True
        assert tenant.has_scope("write") is True
        assert tenant.has_scope("admin") is False

    def test_has_scope_with_wildcard(self):
        """Should return True for any scope when wildcard present."""
        from src.api.auth import AuthenticatedTenant

        tenant = AuthenticatedTenant(
            tenant_id=uuid4(),
            tenant_name="Test",
            api_key_id=uuid4(),
            api_key_name="test-key",
            scopes=["*"],
            rate_limit=1000,
        )

        assert tenant.has_scope("read") is True
        assert tenant.has_scope("write") is True
        assert tenant.has_scope("admin") is True
        assert tenant.has_scope("anything") is True


class TestValidateApiKey:
    """Tests for validate_api_key dependency."""

    @pytest.mark.asyncio
    async def test_missing_api_key(self):
        """Should raise 401 when API key is missing."""
        from src.api.auth import validate_api_key

        mock_request = MagicMock()

        with pytest.raises(HTTPException) as exc:
            await validate_api_key(mock_request, None)

        assert exc.value.status_code == 401
        assert "Missing API key" in exc.value.detail

    @pytest.mark.asyncio
    async def test_invalid_format_wrong_prefix(self):
        """Should raise 401 when API key has wrong prefix."""
        from src.api.auth import validate_api_key

        mock_request = MagicMock()

        with pytest.raises(HTTPException) as exc:
            await validate_api_key(mock_request, "xx_12345678901234567890123456789012")

        assert exc.value.status_code == 401
        assert "Invalid API key format" in exc.value.detail

    @pytest.mark.asyncio
    async def test_invalid_format_wrong_length(self):
        """Should raise 401 when API key has wrong length."""
        from src.api.auth import validate_api_key

        mock_request = MagicMock()

        with pytest.raises(HTTPException) as exc:
            await validate_api_key(mock_request, "cp_short")

        assert exc.value.status_code == 401
        assert "Invalid API key format" in exc.value.detail

    @pytest.mark.asyncio
    async def test_key_not_found_in_database(self):
        """Should raise 401 when key not found in database."""
        from src.api.auth import validate_api_key

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = None
        mock_request.url.path = "/v1/status"
        mock_request.method = "GET"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None  # Key not found
        mock_session.execute.return_value = mock_result

        with patch("src.api.auth.async_session_maker") as mock_maker:
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_session
            mock_cm.__aexit__.return_value = None
            mock_maker.return_value = mock_cm

            with pytest.raises(HTTPException) as exc:
                await validate_api_key(
                    mock_request, "cp_12345678901234567890123456789012"
                )

            assert exc.value.status_code == 401
            assert "Invalid API key" in exc.value.detail

    @pytest.mark.asyncio
    async def test_revoked_key(self):
        """Should raise 401 when key is revoked."""
        from src.api.auth import validate_api_key

        tenant_id = uuid4()
        api_key_id = uuid4()

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = None
        mock_request.url.path = "/v1/status"
        mock_request.method = "GET"

        # Mock API key record (revoked)
        mock_api_key = MagicMock()
        mock_api_key.id = api_key_id
        mock_api_key.revoked_at = datetime.utcnow()  # Revoked

        # Mock tenant
        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.name = "Test Tenant"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (mock_api_key, mock_tenant)
        mock_session.execute.return_value = mock_result

        with patch("src.api.auth.async_session_maker") as mock_maker:
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_session
            mock_cm.__aexit__.return_value = None
            mock_maker.return_value = mock_cm

            with pytest.raises(HTTPException) as exc:
                await validate_api_key(
                    mock_request, "cp_12345678901234567890123456789012"
                )

            assert exc.value.status_code == 401
            assert "revoked" in exc.value.detail

    @pytest.mark.asyncio
    async def test_valid_key_returns_authenticated_tenant(self):
        """Should return AuthenticatedTenant for valid key."""
        from src.api.auth import AuthenticatedTenant, validate_api_key

        tenant_id = uuid4()
        api_key_id = uuid4()

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = "req-123"
        mock_request.url.path = "/v1/status"
        mock_request.method = "GET"

        # Mock API key record (not revoked)
        mock_api_key = MagicMock()
        mock_api_key.id = api_key_id
        mock_api_key.name = "test-key"
        mock_api_key.revoked_at = None  # Not revoked
        mock_api_key.scopes = ["read", "write"]
        mock_api_key.rate_limit = 1000

        # Mock tenant
        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.name = "Test Tenant"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (mock_api_key, mock_tenant)
        mock_session.execute.return_value = mock_result

        with patch("src.api.auth.async_session_maker") as mock_maker:
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_session
            mock_cm.__aexit__.return_value = None
            mock_maker.return_value = mock_cm

            result = await validate_api_key(
                mock_request, "cp_12345678901234567890123456789012"
            )

            assert isinstance(result, AuthenticatedTenant)
            assert result.tenant_id == tenant_id
            assert result.tenant_name == "Test Tenant"
            assert result.api_key_id == api_key_id
            assert result.api_key_name == "test-key"
            assert result.scopes == ["read", "write"]
            assert result.rate_limit == 1000

            # Verify last_used_at was updated
            assert mock_session.execute.call_count == 2  # Select + Update
            assert mock_session.commit.called


class TestLogFailedAuth:
    """Tests for _log_failed_auth helper."""

    @pytest.mark.asyncio
    async def test_log_failed_auth_creates_audit_entry(self):
        """Should create audit log entry for failed auth."""
        from src.api.auth import _log_failed_auth

        mock_session = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.1"
        mock_request.headers.get.return_value = None
        mock_request.url.path = "/v1/evaluate"
        mock_request.method = "POST"

        await _log_failed_auth(mock_session, mock_request, "cp_12345", "invalid")

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        # Check the audit log entry
        audit_entry = mock_session.add.call_args[0][0]
        assert audit_entry.details["key_prefix"] == "cp_12345"
        assert audit_entry.details["reason"] == "invalid"
        assert audit_entry.ip_address == "192.168.1.1"


class TestAuditEvents:
    """Tests for audit event logging."""

    @pytest.mark.asyncio
    async def test_log_audit_event_warning_for_auth_failed(self):
        """Should log at warning level for AUTH_FAILED."""
        from src.audit import log_audit_event
        from src.models import AuditAction
        from unittest.mock import patch

        with patch("src.audit.logger") as mock_logger:
            with patch("src.audit.async_session_maker") as mock_maker:
                mock_session = AsyncMock()
                mock_maker.return_value.__aenter__.return_value = mock_session

                await log_audit_event(
                    action=AuditAction.AUTH_FAILED,
                    tenant_id=None,
                    actor_id=None,
                )

                mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_log_audit_event_info_for_other_actions(self):
        """Should log at info level for other actions."""
        from src.audit import log_audit_event
        from src.models import AuditAction
        from unittest.mock import patch

        with patch("src.audit.logger") as mock_logger:
            with patch("src.audit.async_session_maker") as mock_maker:
                mock_session = AsyncMock()
                mock_maker.return_value.__aenter__.return_value = mock_session

                await log_audit_event(
                    action=AuditAction.API_KEY_CREATED,
                    tenant_id=uuid4(),
                    actor_id=uuid4(),
                )

                mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_log_failed_auth_with_request_id(self):
        """Should include request ID when provided."""
        from src.api.auth import _log_failed_auth
        from uuid import UUID

        request_id = str(uuid4())
        mock_session = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.1"
        mock_request.headers.get.return_value = request_id
        mock_request.url.path = "/v1/evaluate"
        mock_request.method = "POST"

        await _log_failed_auth(mock_session, mock_request, "cp_12345", "revoked")

        audit_entry = mock_session.add.call_args[0][0]
        assert audit_entry.request_id == UUID(request_id)

    @pytest.mark.asyncio
    async def test_log_failed_auth_no_client(self):
        """Should handle missing client."""
        from src.api.auth import _log_failed_auth

        mock_session = AsyncMock()
        mock_request = MagicMock()
        mock_request.client = None
        mock_request.headers.get.return_value = None
        mock_request.url.path = "/v1/status"
        mock_request.method = "GET"

        await _log_failed_auth(mock_session, mock_request, "cp_12345", "invalid")

        audit_entry = mock_session.add.call_args[0][0]
        assert audit_entry.ip_address is None
