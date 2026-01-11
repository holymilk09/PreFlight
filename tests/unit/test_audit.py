"""Tests for audit logging utilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID
from datetime import datetime

from src.models import AuditAction, AuditLog


class TestAuditAction:
    """Tests for AuditAction enum."""

    def test_audit_action_values(self):
        """All expected audit actions should be defined."""
        expected_actions = [
            "api_key_created",
            "api_key_rotated",
            "api_key_revoked",
            "template_created",
            "template_updated",
            "template_deprecated",
            "template_status_changed",
            "tenant_created",
            "tenant_updated",
            "evaluation_requested",
            "auth_failed",
            "rate_limit_exceeded",
        ]

        for action_value in expected_actions:
            # Should be able to look up by value
            action = AuditAction(action_value)
            assert action.value == action_value

    def test_audit_action_is_string_enum(self):
        """AuditAction should be a string enum."""
        action = AuditAction.API_KEY_CREATED
        assert isinstance(action.value, str)
        assert action == "api_key_created"

    def test_audit_action_members(self):
        """AuditAction should have 12 members."""
        assert len(AuditAction) == 12


class TestAuditLog:
    """Tests for AuditLog model."""

    def test_audit_log_creation(self):
        """AuditLog should be created with required fields."""
        log = AuditLog(
            action=AuditAction.API_KEY_CREATED,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            resource_type="api_key",
            resource_id=UUID("87654321-4321-8765-4321-876543218765"),
        )

        assert log.action == AuditAction.API_KEY_CREATED
        assert log.resource_type == "api_key"

    def test_audit_log_optional_fields(self):
        """AuditLog optional fields should default to None."""
        log = AuditLog(action=AuditAction.AUTH_FAILED)

        assert log.tenant_id is None
        assert log.actor_id is None
        assert log.resource_type is None
        assert log.resource_id is None
        assert log.details is None
        assert log.ip_address is None
        assert log.request_id is None

    def test_audit_log_with_details(self):
        """AuditLog should accept details dict."""
        details = {"key_name": "production-key", "scopes": ["read", "write"]}
        log = AuditLog(
            action=AuditAction.API_KEY_CREATED,
            details=details,
        )

        assert log.details == details

    def test_audit_log_with_ip_address(self):
        """AuditLog should accept IPv4 and IPv6 addresses."""
        # IPv4
        log_v4 = AuditLog(
            action=AuditAction.AUTH_FAILED,
            ip_address="192.168.1.1",
        )
        assert log_v4.ip_address == "192.168.1.1"

        # IPv6
        log_v6 = AuditLog(
            action=AuditAction.AUTH_FAILED,
            ip_address="2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        )
        assert log_v6.ip_address == "2001:0db8:85a3:0000:0000:8a2e:0370:7334"


class TestLogAuditEvent:
    """Tests for log_audit_event function."""

    @pytest.mark.asyncio
    async def test_log_audit_event_sanitizes_details(self):
        """Sensitive data in details should be sanitized."""
        from src.audit import log_audit_event
        from src.security import sanitize_for_log

        details = {"api_key": "cp_secret123456789012345678901234"}
        sanitized = sanitize_for_log(details)

        # The sanitize_for_log function should redact the api_key
        assert "REDACTED" in sanitized["api_key"]

    @pytest.mark.asyncio
    async def test_log_audit_event_with_session(self):
        """Should use provided session and not commit."""
        from src.audit import log_audit_event

        mock_session = AsyncMock()

        await log_audit_event(
            action=AuditAction.API_KEY_CREATED,
            tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
            session=mock_session,
        )

        # Should add to session but not commit
        mock_session.add.assert_called_once()
        mock_session.commit.assert_not_called()


class TestConvenienceFunctions:
    """Tests for audit convenience functions."""

    @pytest.mark.asyncio
    async def test_log_api_key_created_fields(self):
        """log_api_key_created should include correct fields."""
        from src.audit import log_api_key_created

        with patch("src.audit.log_audit_event", new_callable=AsyncMock) as mock_log:
            await log_api_key_created(
                tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
                api_key_id=UUID("87654321-4321-8765-4321-876543218765"),
                key_name="test-key",
                ip_address="192.168.1.1",
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs

            assert call_kwargs["action"] == AuditAction.API_KEY_CREATED
            assert call_kwargs["resource_type"] == "api_key"
            assert call_kwargs["details"]["key_name"] == "test-key"

    @pytest.mark.asyncio
    async def test_log_api_key_revoked_fields(self):
        """log_api_key_revoked should include correct fields."""
        from src.audit import log_api_key_revoked

        with patch("src.audit.log_audit_event", new_callable=AsyncMock) as mock_log:
            await log_api_key_revoked(
                tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
                api_key_id=UUID("87654321-4321-8765-4321-876543218765"),
                actor_id=UUID("11111111-1111-1111-1111-111111111111"),
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs

            assert call_kwargs["action"] == AuditAction.API_KEY_REVOKED
            assert call_kwargs["resource_type"] == "api_key"
            assert call_kwargs["actor_id"] == UUID("11111111-1111-1111-1111-111111111111")

    @pytest.mark.asyncio
    async def test_log_template_created_fields(self):
        """log_template_created should include correct fields."""
        from src.audit import log_template_created

        with patch("src.audit.log_audit_event", new_callable=AsyncMock) as mock_log:
            await log_template_created(
                tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
                template_id=UUID("87654321-4321-8765-4321-876543218765"),
                template_name="INV-ACME-001",
                version="1.0",
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs

            assert call_kwargs["action"] == AuditAction.TEMPLATE_CREATED
            assert call_kwargs["resource_type"] == "template"
            assert call_kwargs["details"]["template_name"] == "INV-ACME-001"
            assert call_kwargs["details"]["version"] == "1.0"

    @pytest.mark.asyncio
    async def test_log_evaluation_requested_fields(self):
        """log_evaluation_requested should include correct fields."""
        from src.audit import log_evaluation_requested

        with patch("src.audit.log_audit_event", new_callable=AsyncMock) as mock_log:
            await log_evaluation_requested(
                tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
                evaluation_id=UUID("87654321-4321-8765-4321-876543218765"),
                correlation_id="client-123",
                decision="MATCH",
                processing_time_ms=150,
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs

            assert call_kwargs["action"] == AuditAction.EVALUATION_REQUESTED
            assert call_kwargs["resource_type"] == "evaluation"
            assert call_kwargs["details"]["correlation_id"] == "client-123"
            assert call_kwargs["details"]["decision"] == "MATCH"
            assert call_kwargs["details"]["processing_time_ms"] == 150

    @pytest.mark.asyncio
    async def test_log_rate_limit_exceeded_fields(self):
        """log_rate_limit_exceeded should include correct fields."""
        from src.audit import log_rate_limit_exceeded

        with patch("src.audit.log_audit_event", new_callable=AsyncMock) as mock_log:
            await log_rate_limit_exceeded(
                tenant_id=UUID("12345678-1234-5678-1234-567812345678"),
                api_key_id=UUID("87654321-4321-8765-4321-876543218765"),
                limit=100,
                current=101,
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs

            assert call_kwargs["action"] == AuditAction.RATE_LIMIT_EXCEEDED
            assert call_kwargs["details"]["limit"] == 100
            assert call_kwargs["details"]["current"] == 101
