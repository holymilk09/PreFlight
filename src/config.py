"""Application configuration with pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation.

    All sensitive values are required and validated to ensure
    they are not placeholder values.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = Field(
        ...,
        description="PostgreSQL connection URL with asyncpg driver",
    )
    postgres_user: str = Field(default="controlplane")
    postgres_password: str = Field(
        default="",
        description=(
            "PostgreSQL password. Only needed when DATABASE_URL omits credentials "
            "(e.g. local docker-compose); managed deploys carry creds in DATABASE_URL."
        ),
    )
    postgres_db: str = Field(default="controlplane")

    # Redis
    redis_url: str = Field(..., description="Redis connection URL")
    redis_password: str = Field(
        default="",
        description=(
            "Redis password. Leave empty when REDIS_URL embeds credentials or the "
            "broker needs no auth (e.g. managed Redis on an isolated network)."
        ),
    )

    # Temporal
    temporal_host: str = Field(default="localhost:7233")
    temporal_namespace: str = Field(default="controlplane")

    # Authentication
    jwt_secret: str = Field(..., description="JWT signing secret (min 32 chars)")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=60, ge=1, le=1440)

    api_key_salt: str = Field(..., description="Salt for API key hashing")

    # Login Lockout (per-user brute-force protection)
    login_max_failed_attempts: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Consecutive failed logins before an account is temporarily locked",
    )
    login_lockout_minutes: int = Field(
        default=15,
        ge=1,
        le=1440,
        description="Minutes an account stays locked after too many failed logins",
    )
    login_lockout_reveal: bool = Field(
        default=False,
        description=(
            "When True, a locked account is told so explicitly (HTTP 429 + Retry-After). "
            "When False (default), it receives the same generic 401 as a wrong password "
            "so the lock does not become an account-enumeration oracle. Lockouts are always "
            "recorded in the audit trail regardless of this setting."
        ),
    )

    # Webhook secret encryption at rest (Fernet). If unset, a key is derived
    # from jwt_secret. Generate a dedicated key with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    webhook_enc_key: str | None = Field(
        default=None,
        description="Fernet key for encrypting webhook signing secrets at rest",
    )

    # CORS
    allowed_origins: str = Field(
        default="",
        description="Comma-separated list of allowed CORS origins",
    )

    # Feature Flags
    enable_docs: bool = Field(default=False, description="Enable API docs (disable in prod)")

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_format: Literal["json", "console"] = Field(default="json")

    # API
    api_host: str = Field(
        default="0.0.0.0",  # nosec B104 - intentional for container deployments
        description="API host binding. Use 0.0.0.0 for container deployments, 127.0.0.1 for local-only",
    )
    api_port: int = Field(default=8000, ge=1, le=65535)

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=1000, ge=1)
    rate_limit_unauthenticated: int = Field(default=10, ge=1)

    # Fail-Closed Security & Webhooks (Phase 1)
    security_fail_closed: bool = Field(
        default=True,
        description=(
            "When True, reject requests if Redis (rate-limit/revocation backend) "
            "is unavailable. Governance posture."
        ),
    )
    webhook_timeout_seconds: float = Field(default=5.0, ge=0.5, le=30.0)
    webhook_replay_window_seconds: int = Field(default=300, ge=30, le=3600)

    # Request Limits
    max_request_body_size: int = Field(
        default=1_048_576,  # 1MB
        ge=1024,
        le=10_485_760,  # Max 10MB
        description="Maximum request body size in bytes (default 1MB)",
    )

    # Sentry (Error Tracking)
    sentry_dsn: str | None = Field(
        default=None,
        description="Sentry DSN for error tracking (optional, prod recommended)",
    )
    sentry_environment: str = Field(
        default="development",
        description="Sentry environment (development, staging, production)",
    )
    sentry_traces_sample_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Sentry traces sample rate (0.0 to 1.0)",
    )

    @field_validator("jwt_secret", "api_key_salt")
    @classmethod
    def validate_not_placeholder(cls, v: str, info: object) -> str:
        """Ensure secrets are not placeholder values."""
        placeholder_patterns = [
            "GENERATE_",
            "your-secret",
            "change-me",
            "placeholder",
            "xxx",
            "TODO",
        ]
        v_upper = v.upper()
        for pattern in placeholder_patterns:
            if pattern.upper() in v_upper:
                raise ValueError(
                    "Secret appears to be a placeholder. "
                    "Generate a secure value with: openssl rand -hex 32"
                )
        return v

    @field_validator("jwt_secret", "api_key_salt")
    @classmethod
    def validate_min_length(cls, v: str) -> str:
        """Ensure secrets have minimum length for security."""
        if len(v) < 32:
            raise ValueError("Secret must be at least 32 characters long")
        return v

    @field_validator("postgres_password", "redis_password")
    @classmethod
    def validate_password_not_placeholder(cls, v: str) -> str:
        """Reject obvious placeholder passwords when one is provided.

        An empty value is allowed and means "not set": credentials then come from
        the connection URL, or the backend needs no auth (e.g. a managed Redis on
        an isolated network). This keeps managed-platform deploys turn-key while
        still catching a committed placeholder when a value *is* supplied.
        """
        if v and ("GENERATE_" in v.upper() or v == "password"):
            raise ValueError(
                "Password appears to be a placeholder. "
                "Generate a secure value with: openssl rand -hex 32"
            )
        return v

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Normalize the DB URL scheme to the asyncpg driver.

        Managed platforms (Render, Railway, Heroku) hand out ``postgres://`` or
        ``postgresql://`` URLs, but both the async engine (src/db.py) and Alembic
        (migrations/env.py) require the asyncpg driver. Normalizing here means the
        same value works locally and in the cloud with no manual rewriting. URLs
        that already pin a driver (``postgresql+asyncpg://`` etc.) are left as-is.
        """
        if v.startswith(("postgresql+", "postgres+")):
            return v
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://") :]
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://") :]
        return v

    @property
    def cors_origins(self) -> list[str]:
        """Parse comma-separated CORS origins into list."""
        if not self.allowed_origins:
            return []
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Settings are loaded once and cached for the lifetime of the application.
    """
    return Settings()


# Convenience alias
settings = get_settings()
