"""Tests for rate limiting service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.rate_limiter import RateLimiter, RateLimitResult


class TestRateLimitResult:
    """Tests for RateLimitResult dataclass."""

    def test_allowed_result(self):
        """Test allowed rate limit result."""
        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_after_seconds=60,
        )
        assert result.allowed is True
        assert result.limit == 100
        assert result.remaining == 99
        assert result.reset_after_seconds == 60

    def test_denied_result(self):
        """Test denied rate limit result."""
        result = RateLimitResult(
            allowed=False,
            limit=10,
            remaining=0,
            reset_after_seconds=45,
        )
        assert result.allowed is False
        assert result.remaining == 0


class TestRateLimiter:
    """Tests for RateLimiter class with Lua script."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        # Mock script_load to return a fake SHA
        redis.script_load = AsyncMock(return_value="fake_sha_123")
        # Default: allowed with 5 existing requests
        redis.evalsha = AsyncMock(return_value=[1, 5, 60])
        return redis

    @pytest.mark.asyncio
    async def test_check_allowed(self, mock_redis):
        """Request should be allowed when under limit."""
        limiter = RateLimiter(mock_redis)
        result = await limiter.check("test_key", limit=100)

        assert result.allowed is True
        assert result.limit == 100
        assert result.remaining == 94  # 100 - 5 - 1 = 94

    @pytest.mark.asyncio
    async def test_check_denied(self, mock_redis):
        """Request should be denied when over limit."""
        # Simulate being at the limit
        mock_redis.evalsha = AsyncMock(return_value=[0, 100, 45])

        limiter = RateLimiter(mock_redis)
        result = await limiter.check("test_key", limit=100)

        assert result.allowed is False
        assert result.remaining == 0
        assert result.reset_after_seconds == 45

    @pytest.mark.asyncio
    async def test_script_caching(self, mock_redis):
        """Script SHA should be cached after first load."""
        limiter = RateLimiter(mock_redis)

        # First call should load the script
        await limiter.check("key1", limit=10)
        assert mock_redis.script_load.call_count == 1

        # Second call should reuse cached SHA
        await limiter.check("key2", limit=10)
        assert mock_redis.script_load.call_count == 1  # Still 1

    @pytest.mark.asyncio
    async def test_script_reload_on_noscript_error(self, mock_redis):
        """Script should be reloaded if Redis returns NOSCRIPT error."""
        import redis.asyncio as redis

        # First evalsha fails with NoScriptError, second succeeds
        mock_redis.evalsha = AsyncMock(
            side_effect=[
                redis.exceptions.NoScriptError("Script not found"),
                [1, 0, 60],
            ]
        )

        limiter = RateLimiter(mock_redis)
        limiter._script_sha = "old_sha"  # Simulate cached SHA

        result = await limiter.check("test", limit=10)

        # Should have reloaded script and retried
        assert mock_redis.script_load.call_count == 1
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_window_is_60_seconds(self, mock_redis):
        """Limiter window should be 60 seconds."""
        limiter = RateLimiter(mock_redis)
        assert limiter.window_seconds == 60

    @pytest.mark.asyncio
    async def test_remaining_calculation_allowed(self, mock_redis):
        """Remaining should be calculated correctly when allowed."""
        # 10 requests already made, limit is 100
        mock_redis.evalsha = AsyncMock(return_value=[1, 10, 60])

        limiter = RateLimiter(mock_redis)
        result = await limiter.check("test_key", limit=100)

        # Remaining = limit - current_count - 1 (for this request)
        assert result.remaining == 89

    @pytest.mark.asyncio
    async def test_remaining_is_zero_when_denied(self, mock_redis):
        """Remaining should be 0 when request is denied."""
        mock_redis.evalsha = AsyncMock(return_value=[0, 100, 30])

        limiter = RateLimiter(mock_redis)
        result = await limiter.check("test_key", limit=100)

        assert result.allowed is False
        assert result.remaining == 0


class TestRateLimiterIntegration:
    """Integration-style tests for rate limiter behavior."""

    @pytest.mark.asyncio
    async def test_first_request_allowed(self):
        """First request should always be allowed."""
        redis = AsyncMock()
        redis.script_load = AsyncMock(return_value="sha")
        redis.evalsha = AsyncMock(return_value=[1, 0, 60])  # No previous requests

        limiter = RateLimiter(redis)
        result = await limiter.check("new_key", limit=10)

        assert result.allowed is True
        assert result.remaining == 9  # 10 - 0 - 1

    @pytest.mark.asyncio
    async def test_evalsha_called_with_correct_args(self):
        """Verify evalsha is called with correct key, limit, and window."""
        redis = AsyncMock()
        redis.script_load = AsyncMock(return_value="sha123")
        redis.evalsha = AsyncMock(return_value=[1, 0, 60])

        limiter = RateLimiter(redis)
        await limiter.check("my_key", limit=50)

        # Verify evalsha was called with correct arguments
        call_args = redis.evalsha.call_args
        assert call_args[0][0] == "sha123"  # Script SHA
        assert call_args[0][1] == 1  # Number of keys
        assert call_args[0][2] == "my_key"  # Key
        assert call_args[0][3] == 50  # Limit
        assert call_args[0][4] == 60  # Window seconds
        # call_args[0][5] would be the timestamp


class TestGetClientIP:
    """Tests for IP extraction from requests."""

    def test_direct_connection(self):
        """Test IP extraction from direct connection."""
        from src.api.main import _get_client_ip
        from unittest.mock import MagicMock

        request = MagicMock()
        request.headers = {}
        request.client.host = "192.168.1.100"

        ip = _get_client_ip(request)
        assert ip == "192.168.1.100"

    def test_x_forwarded_for_single(self):
        """Test IP extraction with single X-Forwarded-For."""
        from src.api.main import _get_client_ip
        from unittest.mock import MagicMock

        request = MagicMock()
        request.headers = {"X-Forwarded-For": "10.0.0.1"}
        request.client.host = "127.0.0.1"

        ip = _get_client_ip(request)
        assert ip == "10.0.0.1"

    def test_x_forwarded_for_chain(self):
        """Test IP extraction takes rightmost IP from chain."""
        from src.api.main import _get_client_ip
        from unittest.mock import MagicMock

        request = MagicMock()
        # Client-provided: 1.1.1.1, passed through proxy at 10.0.0.1
        # Rightmost (10.0.0.1) is from our trusted proxy
        request.headers = {"X-Forwarded-For": "1.1.1.1, 10.0.0.1"}
        request.client.host = "127.0.0.1"

        ip = _get_client_ip(request)
        assert ip == "10.0.0.1"  # Rightmost, added by trusted proxy

    def test_no_client(self):
        """Test IP extraction when client is None."""
        from src.api.main import _get_client_ip
        from unittest.mock import MagicMock

        request = MagicMock()
        request.headers = {}
        request.client = None

        ip = _get_client_ip(request)
        assert ip == "unknown"
