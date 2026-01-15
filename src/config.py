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
    postgres_password: str = Field(..., description="PostgreSQL password")
    postgres_db: str = Field(default="controlplane")

    # Redis
    redis_url: str = Field(..., description="Redis connection URL")
    redis_password: str = Field(..., description="Redis password")

    # Temporal
    temporal_host: str = Field(default="localhost:7233")
    temporal_namespace: str = Field(default="controlplane")

    # Authentication
    jwt_secret: str = Field(..., description="JWT signing secret (min 32 chars)")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=60, ge=1, le=1440)

    api_key_salt: str = Field(..., description="Salt for API key hashing")

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
        default="0.0.0.0",
        description="API host binding. Use 0.0.0.0 for container deployments, 127.0.0.1 for local-only",
    )
    api_port: int = Field(default=8000, ge=1, le=65535)

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=1000, ge=1)
    rate_limit_unauthenticated: int = Field(default=10, ge=1)

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
        """Ensure passwords are not placeholder values."""
        if "GENERATE_" in v.upper() or v == "password" or v == "":
            raise ValueError(
                "Password appears to be a placeholder. "
                "Generate a secure value with: openssl rand -hex 32"
            )
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
