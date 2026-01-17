"""Tests for API main module middleware and configuration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse


class TestRequestSizeLimitMiddleware:
    """Tests for request size limit middleware."""

    @pytest.mark.asyncio
    async def test_request_within_limit_passes_through(self):
        """Should pass through requests within size limit."""
        from src.api.main import request_size_limit_middleware

        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "1000"

        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        with patch("src.api.main.settings") as mock_settings:
            mock_settings.max_request_body_size = 10000

            result = await request_size_limit_middleware(mock_request, mock_call_next)

        assert result == mock_response
        mock_call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_request_exceeds_limit_returns_413(self):
        """Should return 413 when request body exceeds limit."""
        from src.api.main import request_size_limit_middleware

        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "100000"

        mock_call_next = AsyncMock()

        with patch("src.api.main.settings") as mock_settings:
            mock_settings.max_request_body_size = 1000

            result = await request_size_limit_middleware(mock_request, mock_call_next)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 413
        mock_call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_content_length_passes_through(self):
        """Should pass through requests without content-length header."""
        from src.api.main import request_size_limit_middleware

        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = None

        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        result = await request_size_limit_middleware(mock_request, mock_call_next)

        assert result == mock_response

    @pytest.mark.asyncio
    async def test_invalid_content_length_passes_through(self):
        """Should pass through requests with invalid content-length."""
        from src.api.main import request_size_limit_middleware

        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "not-a-number"

        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        with patch("src.api.main.settings") as mock_settings:
            mock_settings.max_request_body_size = 1000

            result = await request_size_limit_middleware(mock_request, mock_call_next)

        assert result == mock_response


class TestSecurityHeadersMiddleware:
    """Tests for security headers middleware."""

    @pytest.mark.asyncio
    async def test_adds_security_headers(self):
        """Should add security headers to response."""
        from src.api.main import security_headers_middleware

        mock_request = MagicMock(spec=Request)
        mock_response = MagicMock()
        mock_response.headers = {}

        mock_call_next = AsyncMock(return_value=mock_response)

        result = await security_headers_middleware(mock_request, mock_call_next)

        assert "X-Content-Type-Options" in result.headers
        assert result.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Frame-Options" in result.headers
        assert result.headers["X-Frame-Options"] == "DENY"
        assert "X-XSS-Protection" in result.headers


class TestRateLimitMiddleware:
    """Tests for rate limit middleware."""

    @pytest.mark.asyncio
    async def test_rate_limit_redis_error_fails_open(self):
        """Should fail open when Redis is unavailable."""
        from src.api.main import rate_limit_middleware

        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = None  # No API key
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/v1/status"
        mock_request.method = "GET"

        mock_response = MagicMock()
        mock_response.headers = {}
        mock_call_next = AsyncMock(return_value=mock_response)

        with patch("src.api.main.check_rate_limit") as mock_check:
            mock_check.side_effect = ConnectionError("Redis unavailable")

            result = await rate_limit_middleware(mock_request, mock_call_next)

        # Should fail open and allow request through
        assert result == mock_response


class TestExceptionHandler:
    """Tests for exception handlers."""

    @pytest.mark.asyncio
    async def test_generic_exception_handler(self):
        """Should return 500 error for unhandled exceptions."""
        from src.api.main import generic_exception_handler

        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "test-123"
        mock_request.url.path = "/v1/status"
        mock_request.method = "GET"

        exc = Exception("Test error")

        with patch("src.api.main.logger"):
            result = await generic_exception_handler(mock_request, exc)

        assert result.status_code == 500
        assert "Internal server error" in result.body.decode()


class TestAppConfiguration:
    """Tests for app configuration."""

    def test_app_exists(self):
        """App should be created and configured."""
        from src.api.main import app

        assert app is not None
        assert app.title == "Document Extraction Control Plane"

    def test_health_endpoint_registered(self):
        """Health endpoint should be registered."""
        from src.api.main import app

        routes = [route.path for route in app.routes]
        assert "/health" in routes
