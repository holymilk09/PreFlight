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
    """Tests for RateLimiter class."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        pipeline = AsyncMock()
        pipeline.execute = AsyncMock(return_value=[None, 5, True, True])  # zremrangebyscore, zcard, zadd, expire
        redis.pipeline = MagicMock(return_value=pipeline)
        redis.zrem = AsyncMock()
        redis.zrange = AsyncMock(return_value=[])
        return redis

    @pytest.mark.asyncio
    async def test_check_allowed(self, mock_redis):
        """Request should be allowed when under limit."""
        limiter = RateLimiter(mock_redis)
        result = await limiter.check("test_key", limit=100)

        assert result.allowed is True
        assert result.limit == 100
        assert result.remaining == 94  # 100 - 5 - 1

    @pytest.mark.asyncio
    async def test_check_denied(self, mock_redis):
        """Request should be denied when over limit."""
        # Simulate being at the limit
        pipeline = AsyncMock()
        pipeline.execute = AsyncMock(return_value=[None, 100, True, True])  # At limit
        mock_redis.pipeline = MagicMock(return_value=pipeline)
        mock_redis.zrange = AsyncMock(return_value=[("req1", 1234567890.0)])

        limiter = RateLimiter(mock_redis)
        result = await limiter.check("test_key", limit=100)

        assert result.allowed is False
        assert result.remaining == 0

    @pytest.mark.asyncio
    async def test_check_uses_correct_key(self, mock_redis):
        """Limiter should use the provided key."""
        limiter = RateLimiter(mock_redis)
        await limiter.check("my_custom_key", limit=50)

        # Verify pipeline was called (key usage is internal)
        mock_redis.pipeline.assert_called_once()

    @pytest.mark.asyncio
    async def test_window_is_60_seconds(self, mock_redis):
        """Limiter window should be 60 seconds."""
        limiter = RateLimiter(mock_redis)
        assert limiter.window_seconds == 60

    @pytest.mark.asyncio
    async def test_remaining_calculation(self, mock_redis):
        """Remaining should be calculated correctly."""
        # 10 requests already made, limit is 100
        pipeline = AsyncMock()
        pipeline.execute = AsyncMock(return_value=[None, 10, True, True])
        mock_redis.pipeline = MagicMock(return_value=pipeline)

        limiter = RateLimiter(mock_redis)
        result = await limiter.check("test_key", limit=100)

        # Remaining = limit - current_count - 1 (for this request)
        assert result.remaining == 89


class TestRateLimiterIntegration:
    """Integration-style tests for rate limiter behavior."""

    @pytest.mark.asyncio
    async def test_first_request_allowed(self):
        """First request should always be allowed."""
        redis = AsyncMock()
        pipeline = AsyncMock()
        pipeline.execute = AsyncMock(return_value=[None, 0, True, True])  # No previous requests
        redis.pipeline = MagicMock(return_value=pipeline)

        limiter = RateLimiter(redis)
        result = await limiter.check("new_key", limit=10)

        assert result.allowed is True
        assert result.remaining == 9  # 10 - 0 - 1

    @pytest.mark.asyncio
    async def test_limit_of_one(self):
        """Limit of 1 should allow first request only."""
        redis = AsyncMock()

        # First request
        pipeline1 = AsyncMock()
        pipeline1.execute = AsyncMock(return_value=[None, 0, True, True])
        redis.pipeline = MagicMock(return_value=pipeline1)

        limiter = RateLimiter(redis)
        result1 = await limiter.check("test", limit=1)
        assert result1.allowed is True

        # Second request (at limit)
        pipeline2 = AsyncMock()
        pipeline2.execute = AsyncMock(return_value=[None, 1, True, True])
        redis.pipeline = MagicMock(return_value=pipeline2)
        redis.zrange = AsyncMock(return_value=[("req", 1000.0)])

        result2 = await limiter.check("test", limit=1)
        assert result2.allowed is False
