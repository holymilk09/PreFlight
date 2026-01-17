"""Tests for rate limiter with circuit breaker."""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch


class TestRateLimitResult:
    """Tests for RateLimitResult dataclass."""

    def test_rate_limit_result_creation(self):
        """Should create RateLimitResult with all fields."""
        from src.services.rate_limiter import RateLimitResult

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

    def test_rate_limit_result_denied(self):
        """Should create RateLimitResult for denied request."""
        from src.services.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=False,
            limit=100,
            remaining=0,
            reset_after_seconds=30,
        )

        assert result.allowed is False
        assert result.remaining == 0


class TestCircuitBreaker:
    """Tests for circuit breaker functions."""

    @pytest.mark.asyncio
    async def test_record_failure_increments_counter(self):
        """Should increment failure counter."""
        import src.services.rate_limiter as rate_limiter

        # Reset state
        rate_limiter._circuit_breaker_failures = 0
        rate_limiter._circuit_breaker_open = False
        rate_limiter._circuit_breaker_lock = None  # Reset lock for clean test

        await rate_limiter._record_failure()

        assert rate_limiter._circuit_breaker_failures == 1
        assert rate_limiter._circuit_breaker_open is False

    @pytest.mark.asyncio
    async def test_record_failure_opens_circuit_at_threshold(self):
        """Should open circuit when threshold is reached."""
        import src.services.rate_limiter as rate_limiter

        # Reset state
        rate_limiter._circuit_breaker_failures = rate_limiter.CIRCUIT_BREAKER_THRESHOLD - 1
        rate_limiter._circuit_breaker_open = False
        rate_limiter._circuit_breaker_lock = None  # Reset lock for clean test

        await rate_limiter._record_failure()

        assert rate_limiter._circuit_breaker_failures == rate_limiter.CIRCUIT_BREAKER_THRESHOLD
        assert rate_limiter._circuit_breaker_open is True

    @pytest.mark.asyncio
    async def test_record_success_resets_circuit(self):
        """Should reset circuit breaker on success."""
        import src.services.rate_limiter as rate_limiter

        # Set up open circuit
        rate_limiter._circuit_breaker_failures = 5
        rate_limiter._circuit_breaker_open = True
        rate_limiter._circuit_breaker_lock = None  # Reset lock for clean test

        await rate_limiter._record_success()

        assert rate_limiter._circuit_breaker_failures == 0
        assert rate_limiter._circuit_breaker_open is False

    @pytest.mark.asyncio
    async def test_record_success_no_op_when_healthy(self):
        """Should not change state when already healthy."""
        import src.services.rate_limiter as rate_limiter

        # Already healthy
        rate_limiter._circuit_breaker_failures = 0
        rate_limiter._circuit_breaker_open = False
        rate_limiter._circuit_breaker_lock = None  # Reset lock for clean test

        await rate_limiter._record_success()

        # State should remain unchanged
        assert rate_limiter._circuit_breaker_failures == 0
        assert rate_limiter._circuit_breaker_open is False

    @pytest.mark.asyncio
    async def test_should_attempt_rate_limit_when_closed(self):
        """Should allow rate limit attempts when circuit is closed."""
        import src.services.rate_limiter as rate_limiter

        rate_limiter._circuit_breaker_open = False
        rate_limiter._circuit_breaker_lock = None  # Reset lock for clean test

        result = await rate_limiter._should_attempt_rate_limit()
        assert result is True

    @pytest.mark.asyncio
    async def test_should_attempt_rate_limit_when_open_and_recent(self):
        """Should not allow rate limit when circuit is open and failure is recent."""
        import src.services.rate_limiter as rate_limiter

        rate_limiter._circuit_breaker_open = True
        rate_limiter._circuit_breaker_last_failure = time.time()
        rate_limiter._circuit_breaker_lock = None  # Reset lock for clean test

        result = await rate_limiter._should_attempt_rate_limit()
        assert result is False

    @pytest.mark.asyncio
    async def test_should_attempt_rate_limit_half_open_state(self):
        """Should allow rate limit in half-open state after reset time."""
        import src.services.rate_limiter as rate_limiter

        rate_limiter._circuit_breaker_open = True
        # Set failure time to past the reset threshold
        rate_limiter._circuit_breaker_last_failure = (
            time.time() - rate_limiter.CIRCUIT_BREAKER_RESET_SECONDS - 1
        )
        rate_limiter._circuit_breaker_lock = None  # Reset lock for clean test

        result = await rate_limiter._should_attempt_rate_limit()
        assert result is True


class TestCheckRateLimit:
    """Tests for check_rate_limit function."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_bypasses_when_circuit_open(self):
        """Should bypass rate limiting when circuit breaker is open."""
        import src.services.rate_limiter as rate_limiter

        # Open circuit breaker
        rate_limiter._circuit_breaker_open = True
        rate_limiter._circuit_breaker_last_failure = time.time()
        rate_limiter._circuit_breaker_lock = None  # Reset lock for clean test

        result = await rate_limiter.check_rate_limit("test-key", 100)

        assert result.allowed is True
        assert result.limit == 100
        assert result.remaining == 100

    @pytest.mark.asyncio
    async def test_check_rate_limit_handles_redis_error(self):
        """Should fail-open when Redis is unavailable."""
        import src.services.rate_limiter as rate_limiter
        from redis.exceptions import RedisError

        # Reset circuit breaker
        rate_limiter._circuit_breaker_open = False
        rate_limiter._circuit_breaker_failures = 0
        rate_limiter._circuit_breaker_lock = None  # Reset lock for clean test

        # Mock Redis to raise error
        with patch.object(rate_limiter, "_get_rate_limiter") as mock_get:
            mock_limiter = AsyncMock()
            mock_limiter.check.side_effect = RedisError("Connection failed")
            mock_get.return_value = mock_limiter

            result = await rate_limiter.check_rate_limit("test-key", 100)

        assert result.allowed is True  # Fail-open
        assert rate_limiter._circuit_breaker_failures == 1

    @pytest.mark.asyncio
    async def test_check_rate_limit_success(self):
        """Should check rate limit and record success."""
        import src.services.rate_limiter as rate_limiter

        # Reset circuit breaker
        rate_limiter._circuit_breaker_open = False
        rate_limiter._circuit_breaker_failures = 1  # Some previous failures
        rate_limiter._circuit_breaker_lock = None  # Reset lock for clean test

        # Mock successful rate limit check
        mock_result = rate_limiter.RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_after_seconds=60,
        )

        with patch.object(rate_limiter, "_get_rate_limiter") as mock_get:
            mock_limiter = AsyncMock()
            mock_limiter.check.return_value = mock_result
            mock_get.return_value = mock_limiter

            result = await rate_limiter.check_rate_limit("test-key", 100)

        assert result.allowed is True
        assert rate_limiter._circuit_breaker_failures == 0  # Reset on success


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_rate_limiter_initialization(self):
        """Should initialize with Redis client."""
        from src.services.rate_limiter import RateLimiter

        mock_redis = MagicMock()
        limiter = RateLimiter(mock_redis)

        assert limiter.redis == mock_redis
        assert limiter.window_seconds == 60
        assert limiter._script_sha is None

    @pytest.mark.asyncio
    async def test_rate_limiter_get_script_sha(self):
        """Should load and cache Lua script."""
        from src.services.rate_limiter import RateLimiter

        mock_redis = AsyncMock()
        mock_redis.script_load.return_value = "abc123sha"

        limiter = RateLimiter(mock_redis)

        sha = await limiter._get_script_sha()

        assert sha == "abc123sha"
        mock_redis.script_load.assert_called_once()

        # Second call should use cached value
        sha2 = await limiter._get_script_sha()
        assert sha2 == "abc123sha"
        assert mock_redis.script_load.call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_rate_limiter_check_allowed(self):
        """Should allow request when under limit."""
        from src.services.rate_limiter import RateLimiter

        mock_redis = AsyncMock()
        mock_redis.script_load.return_value = "abc123sha"
        mock_redis.evalsha.return_value = [1, 5, 60]  # allowed, count, reset_after

        limiter = RateLimiter(mock_redis)

        result = await limiter.check("test-key", 100)

        assert result.allowed is True
        assert result.limit == 100
        assert result.remaining == 94  # 100 - 5 - 1

    @pytest.mark.asyncio
    async def test_rate_limiter_check_denied(self):
        """Should deny request when over limit."""
        from src.services.rate_limiter import RateLimiter

        mock_redis = AsyncMock()
        mock_redis.script_load.return_value = "abc123sha"
        mock_redis.evalsha.return_value = [0, 100, 30]  # denied, count, reset_after

        limiter = RateLimiter(mock_redis)

        result = await limiter.check("test-key", 100)

        assert result.allowed is False
        assert result.remaining == 0
        assert result.reset_after_seconds == 30

    @pytest.mark.asyncio
    async def test_rate_limiter_handles_no_script_error(self):
        """Should reload script when it's flushed from Redis."""
        from redis.exceptions import NoScriptError
        from src.services.rate_limiter import RateLimiter

        mock_redis = AsyncMock()
        mock_redis.script_load.return_value = "abc123sha"
        # First call fails with NoScriptError, second succeeds
        mock_redis.evalsha.side_effect = [
            NoScriptError("Script not found"),
            [1, 5, 60],
        ]

        limiter = RateLimiter(mock_redis)
        limiter._script_sha = "old_sha"  # Pretend we had a cached SHA

        result = await limiter.check("test-key", 100)

        assert result.allowed is True
        # Script should be reloaded after error
        assert mock_redis.script_load.call_count == 1


class TestCloseRedisClient:
    """Tests for close_redis_client function."""

    @pytest.mark.asyncio
    async def test_close_redis_client(self):
        """Should close Redis client and reset state."""
        import src.services.rate_limiter as rate_limiter

        # Set up mock client
        mock_client = AsyncMock()
        rate_limiter._redis_client = mock_client
        rate_limiter._rate_limiter = MagicMock()

        await rate_limiter.close_redis_client()

        mock_client.close.assert_called_once()
        assert rate_limiter._redis_client is None
        assert rate_limiter._rate_limiter is None

    @pytest.mark.asyncio
    async def test_close_redis_client_when_none(self):
        """Should handle case when client is already None."""
        import src.services.rate_limiter as rate_limiter

        rate_limiter._redis_client = None
        rate_limiter._rate_limiter = None

        # Should not raise
        await rate_limiter.close_redis_client()

        assert rate_limiter._redis_client is None
