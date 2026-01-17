"""Additional tests for model properties and validation."""

import pytest
from datetime import datetime
from uuid import uuid4
from pydantic import ValidationError


class TestAPIKeyModel:
    """Tests for APIKey model."""

    def test_api_key_is_active_when_not_revoked(self):
        """is_active should return True when revoked_at is None."""
        from src.models import APIKey
        from uuid_extensions import uuid7

        api_key = APIKey(
            id=uuid7(),
            tenant_id=uuid7(),
            key_hash="hash123",
            key_prefix="cp_123",
            scopes=["read"],
            rate_limit=1000,
        )

        assert api_key.is_active is True

    def test_api_key_is_inactive_when_revoked(self):
        """is_active should return False when revoked_at is set."""
        from src.models import APIKey
        from uuid_extensions import uuid7

        api_key = APIKey(
            id=uuid7(),
            tenant_id=uuid7(),
            key_hash="hash123",
            key_prefix="cp_123",
            scopes=["read"],
            rate_limit=1000,
            revoked_at=datetime.utcnow(),
        )

        assert api_key.is_active is False


class TestSignupRequestValidation:
    """Tests for SignupRequest model validation."""

    def test_invalid_email_rejected(self):
        """Should reject invalid email format."""
        from src.models import SignupRequest

        with pytest.raises(ValidationError) as exc:
            SignupRequest(
                email="not-an-email",
                password="validpassword123",
            )

        assert "email" in str(exc.value).lower() or "invalid" in str(exc.value).lower()

    def test_valid_email_accepted(self):
        """Should accept valid email format."""
        from src.models import SignupRequest

        user = SignupRequest(
            email="Test@Example.COM",
            password="validpassword123",
        )

        # Email should be lowercased
        assert user.email == "test@example.com"
