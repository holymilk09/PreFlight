"""Tests for configuration and settings validation."""

import pytest
from pydantic import ValidationError


class TestSettingsValidation:
    """Tests for Settings validation."""

    def test_jwt_secret_placeholder_rejected(self):
        """Should reject placeholder JWT secret values."""
        from src.config import Settings

        with pytest.raises(ValidationError) as exc:
            Settings(
                jwt_secret="change-me-to-a-real-secret-value",  # Placeholder pattern (change-me)
                api_key_salt="a" * 32,
                postgres_password="valid-password-here-123",
                redis_password="valid-password-here-456",
            )

        assert "placeholder" in str(exc.value).lower()

    def test_jwt_secret_xxx_rejected(self):
        """Should reject xxx placeholder pattern."""
        from src.config import Settings

        with pytest.raises(ValidationError) as exc:
            Settings(
                jwt_secret="xxxsecretxxx12345678901234567890",  # Contains xxx
                api_key_salt="a" * 32,
                postgres_password="valid-password-here-123",
                redis_password="valid-password-here-456",
            )

        assert "placeholder" in str(exc.value).lower()

    def test_jwt_secret_min_length(self):
        """Should require minimum length for JWT secret."""
        from src.config import Settings

        with pytest.raises(ValidationError) as exc:
            Settings(
                jwt_secret="tooshort",  # Less than 32 chars
                api_key_salt="a" * 32,
                postgres_password="valid-password-here-123",
                redis_password="valid-password-here-456",
            )

        assert "32 characters" in str(exc.value).lower()

    def test_api_key_salt_min_length(self):
        """Should require minimum length for API key salt."""
        from src.config import Settings

        with pytest.raises(ValidationError) as exc:
            Settings(
                jwt_secret="a" * 32,
                api_key_salt="short",  # Less than 32 chars
                postgres_password="valid-password-here-123",
                redis_password="valid-password-here-456",
            )

        assert "32 characters" in str(exc.value).lower()

    def test_password_placeholder_rejected(self):
        """Should reject placeholder password values."""
        from src.config import Settings

        with pytest.raises(ValidationError) as exc:
            Settings(
                jwt_secret="a" * 32,
                api_key_salt="a" * 32,
                postgres_password="GENERATE_SECURE_PASSWORD",  # Placeholder
                redis_password="valid-password-here-456",
            )

        assert "placeholder" in str(exc.value).lower()

    def test_password_default_rejected(self):
        """Should reject 'password' as password value."""
        from src.config import Settings

        with pytest.raises(ValidationError) as exc:
            Settings(
                jwt_secret="a" * 32,
                api_key_salt="a" * 32,
                postgres_password="password",  # Common default
                redis_password="valid-password-here-456",
            )

        assert "placeholder" in str(exc.value).lower()


class TestCorsOrigins:
    """Tests for CORS origins parsing."""

    def test_cors_origins_empty(self):
        """Should return empty list when allowed_origins is empty."""
        from src.config import Settings

        settings = Settings(
            jwt_secret="a" * 32,
            api_key_salt="b" * 32,
            postgres_password="valid-password-here-123",
            redis_password="valid-password-here-456",
            allowed_origins="",
        )

        assert settings.cors_origins == []

    def test_cors_origins_single(self):
        """Should parse single origin."""
        from src.config import Settings

        settings = Settings(
            jwt_secret="a" * 32,
            api_key_salt="b" * 32,
            postgres_password="valid-password-here-123",
            redis_password="valid-password-here-456",
            allowed_origins="https://example.com",
        )

        assert settings.cors_origins == ["https://example.com"]

    def test_cors_origins_multiple(self):
        """Should parse comma-separated origins."""
        from src.config import Settings

        settings = Settings(
            jwt_secret="a" * 32,
            api_key_salt="b" * 32,
            postgres_password="valid-password-here-123",
            redis_password="valid-password-here-456",
            allowed_origins="https://example.com, https://other.com",
        )

        assert settings.cors_origins == ["https://example.com", "https://other.com"]
