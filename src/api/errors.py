"""Standardized API error responses.

Provides consistent error codes and response formats across all endpoints.
"""

from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel


class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""

    # Authentication errors (401)
    INVALID_API_KEY = "INVALID_API_KEY"
    EXPIRED_API_KEY = "EXPIRED_API_KEY"
    REVOKED_API_KEY = "REVOKED_API_KEY"
    MISSING_API_KEY = "MISSING_API_KEY"
    INVALID_TOKEN = "INVALID_TOKEN"
    EXPIRED_TOKEN = "EXPIRED_TOKEN"
    REVOKED_TOKEN = "REVOKED_TOKEN"

    # Authorization errors (403)
    TENANT_ACCESS_DENIED = "TENANT_ACCESS_DENIED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"

    # Not found errors (404)
    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
    EVALUATION_NOT_FOUND = "EVALUATION_NOT_FOUND"
    TENANT_NOT_FOUND = "TENANT_NOT_FOUND"
    API_KEY_NOT_FOUND = "API_KEY_NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"

    # Conflict errors (409)
    TEMPLATE_ALREADY_EXISTS = "TEMPLATE_ALREADY_EXISTS"
    TEMPLATE_ALREADY_DEPRECATED = "TEMPLATE_ALREADY_DEPRECATED"
    USER_ALREADY_EXISTS = "USER_ALREADY_EXISTS"

    # Validation errors (400)
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_FINGERPRINT = "INVALID_FINGERPRINT"
    INVALID_FEATURES = "INVALID_FEATURES"
    NO_FIELDS_TO_UPDATE = "NO_FIELDS_TO_UPDATE"

    # Rate limiting (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class ErrorDetail(BaseModel):
    """Standardized error response body."""

    code: str
    message: str
    details: dict[str, Any] = {}


class APIError(HTTPException):
    """HTTPException with standardized error code and details."""

    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        error_detail = ErrorDetail(
            code=code.value,
            message=message,
            details=details or {},
        )
        super().__init__(status_code=status_code, detail=error_detail.model_dump())
        self.code = code


# Convenience functions for common errors


def not_found(code: ErrorCode, message: str, **details: Any) -> APIError:
    """Create a 404 Not Found error."""
    return APIError(
        status_code=status.HTTP_404_NOT_FOUND,
        code=code,
        message=message,
        details=details if details else None,
    )


def bad_request(code: ErrorCode, message: str, **details: Any) -> APIError:
    """Create a 400 Bad Request error."""
    return APIError(
        status_code=status.HTTP_400_BAD_REQUEST,
        code=code,
        message=message,
        details=details if details else None,
    )


def conflict(code: ErrorCode, message: str, **details: Any) -> APIError:
    """Create a 409 Conflict error."""
    return APIError(
        status_code=status.HTTP_409_CONFLICT,
        code=code,
        message=message,
        details=details if details else None,
    )


def unauthorized(code: ErrorCode, message: str, **details: Any) -> APIError:
    """Create a 401 Unauthorized error."""
    return APIError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code=code,
        message=message,
        details=details if details else None,
    )


def forbidden(code: ErrorCode, message: str, **details: Any) -> APIError:
    """Create a 403 Forbidden error."""
    return APIError(
        status_code=status.HTTP_403_FORBIDDEN,
        code=code,
        message=message,
        details=details if details else None,
    )


def rate_limited(message: str = "Rate limit exceeded", **details: Any) -> APIError:
    """Create a 429 Too Many Requests error."""
    return APIError(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        code=ErrorCode.RATE_LIMIT_EXCEEDED,
        message=message,
        details=details if details else None,
    )


# Pre-built common errors for convenience

TEMPLATE_NOT_FOUND = not_found(ErrorCode.TEMPLATE_NOT_FOUND, "Template not found")
EVALUATION_NOT_FOUND = not_found(ErrorCode.EVALUATION_NOT_FOUND, "Evaluation not found")
TENANT_NOT_FOUND = not_found(ErrorCode.TENANT_NOT_FOUND, "Tenant not found")
API_KEY_NOT_FOUND = not_found(ErrorCode.API_KEY_NOT_FOUND, "API key not found")
USER_NOT_FOUND = not_found(ErrorCode.USER_NOT_FOUND, "User not found")
NO_FIELDS_TO_UPDATE = bad_request(ErrorCode.NO_FIELDS_TO_UPDATE, "No fields to update")
