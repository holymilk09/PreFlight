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

    def test_empty_infra_passwords_allowed(self):
        """Empty postgres/redis passwords are accepted (managed-deploy posture).

        On managed platforms credentials live in the connection URL (or the broker
        needs no auth), so an empty value must not fail validation.
        """
        from src.config import Settings

        settings = Settings(
            jwt_secret="a" * 32,
            api_key_salt="b" * 32,
            postgres_password="",
            redis_password="",
        )

        assert settings.postgres_password == ""
        assert settings.redis_password == ""


class TestDatabaseUrlNormalization:
    """Tests for DATABASE_URL scheme normalization to the asyncpg driver."""

    def _settings(self, database_url: str):
        from src.config import Settings

        return Settings(
            jwt_secret="a" * 32,
            api_key_salt="b" * 32,
            postgres_password="",
            redis_password="",
            database_url=database_url,
        )

    def test_bare_postgres_scheme_normalized(self):
        """`postgres://` (Render/Railway/Heroku) -> `postgresql+asyncpg://`."""
        s = self._settings("postgres://user:pw@host:5432/db")
        assert s.database_url == "postgresql+asyncpg://user:pw@host:5432/db"

    def test_bare_postgresql_scheme_normalized(self):
        """`postgresql://` (no driver) -> `postgresql+asyncpg://`."""
        s = self._settings("postgresql://user:pw@host:5432/db")
        assert s.database_url == "postgresql+asyncpg://user:pw@host:5432/db"

    def test_asyncpg_scheme_unchanged(self):
        """A URL that already pins the asyncpg driver is left untouched."""
        url = "postgresql+asyncpg://user:pw@host:5432/db"
        assert self._settings(url).database_url == url

    def test_explicit_other_driver_unchanged(self):
        """A URL that pins another driver is not rewritten."""
        url = "postgresql+psycopg://user:pw@host:5432/db"
        assert self._settings(url).database_url == url


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
