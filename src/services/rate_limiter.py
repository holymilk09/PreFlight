"""Redis-based rate limiting using sliding window algorithm."""

import asyncio
import time
from dataclasses import dataclass

import redis.asyncio as aioredis
import structlog
from redis.exceptions import NoScriptError, RedisError

from src.config import settings

logger = structlog.get_logger()


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_after_seconds: int


# Lua script for atomic rate limiting (single round trip, no race conditions)
RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local window_start = now - window

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

-- Get current count
local count = redis.call('ZCARD', key)

if count >= limit then
    -- Over limit - get oldest entry for reset time calculation
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local reset_after = window
    if oldest[2] then
        reset_after = math.ceil(oldest[2] + window - now) + 1
    end
    return {0, count, reset_after}
else
    -- Under limit - add this request
    redis.call('ZADD', key, now, tostring(now) .. ':' .. tostring(math.random(1000000)))
    redis.call('EXPIRE', key, window + 1)
    return {1, count, window}
end
"""


class RateLimiter:
    """Sliding window rate limiter using Redis.

    Uses a Lua script for atomic operations - single round trip,
    no race conditions between check and increment.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client
        self.window_seconds = 60  # 1 minute window
        self._script_sha: str | None = None

    async def _get_script_sha(self) -> str:
        """Load and cache the Lua script."""
        if self._script_sha is None:
            self._script_sha = await self.redis.script_load(RATE_LIMIT_SCRIPT)
        return self._script_sha

    async def check(self, key: str, limit: int) -> RateLimitResult:
        """Check if request is allowed and record it if so.

        Args:
            key: Unique identifier (e.g., api_key_id or IP address)
            limit: Maximum requests per window

        Returns:
            RateLimitResult with allowed status and metadata
        """
        now = time.time()

        try:
            # Try to use cached script
            script_sha = await self._get_script_sha()
            result = await self.redis.evalsha(
                script_sha,
                1,  # number of keys
                key,
                limit,
                self.window_seconds,
                now,
            )
        except NoScriptError:
            # Script was flushed, reload it
            self._script_sha = None
            script_sha = await self._get_script_sha()
            result = await self.redis.evalsha(
                script_sha,
                1,
                key,
                limit,
                self.window_seconds,
                now,
            )

        allowed = bool(result[0])
        current_count = int(result[1])
        reset_after = int(result[2])

        if allowed:
            remaining = max(0, limit - current_count - 1)
        else:
            remaining = 0

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_after_seconds=reset_after,
        )


# Global Redis client and rate limiter (initialized on first use)
_redis_client: aioredis.Redis | None = None
_rate_limiter: RateLimiter | None = None

# Circuit breaker state (protected by lock)
_circuit_breaker_failures: int = 0
_circuit_breaker_last_failure: float = 0.0
_circuit_breaker_open: bool = False
_circuit_breaker_lock: asyncio.Lock | None = None

# Circuit breaker configuration
CIRCUIT_BREAKER_THRESHOLD = 5  # Number of failures to open circuit
CIRCUIT_BREAKER_RESET_SECONDS = 30  # Time before attempting to close circuit


def _get_circuit_breaker_lock() -> asyncio.Lock:
    """Get or create the circuit breaker lock.

    Creates the lock lazily to ensure it's created in the correct event loop.
    """
    global _circuit_breaker_lock
    if _circuit_breaker_lock is None:
        _circuit_breaker_lock = asyncio.Lock()
    return _circuit_breaker_lock


async def get_redis_client() -> aioredis.Redis:
    """Get or create Redis client with connection pooling."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            password=settings.redis_password,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,  # Connection pool limit
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _redis_client


async def close_redis_client() -> None:
    """Close Redis client on shutdown."""
    global _redis_client, _rate_limiter
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        _rate_limiter = None


async def _get_rate_limiter() -> RateLimiter:
    """Get or create rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        client = await get_redis_client()
        _rate_limiter = RateLimiter(client)
    return _rate_limiter


async def _record_failure() -> None:
    """Record a rate limiting failure for circuit breaker (thread-safe)."""
    global _circuit_breaker_failures, _circuit_breaker_last_failure, _circuit_breaker_open
    lock = _get_circuit_breaker_lock()
    async with lock:
        _circuit_breaker_failures += 1
        _circuit_breaker_last_failure = time.time()
        if _circuit_breaker_failures >= CIRCUIT_BREAKER_THRESHOLD:
            _circuit_breaker_open = True
            logger.warning(
                "rate_limiter_circuit_breaker_open",
                failures=_circuit_breaker_failures,
                threshold=CIRCUIT_BREAKER_THRESHOLD,
            )


async def _record_success() -> None:
    """Record a rate limiting success for circuit breaker (thread-safe)."""
    global _circuit_breaker_failures, _circuit_breaker_open
    lock = _get_circuit_breaker_lock()
    async with lock:
        if _circuit_breaker_failures > 0 or _circuit_breaker_open:
            _circuit_breaker_failures = 0
            _circuit_breaker_open = False
            logger.info("rate_limiter_circuit_breaker_closed")


async def _should_attempt_rate_limit() -> bool:
    """Check if we should attempt rate limiting based on circuit breaker state (thread-safe)."""
    global _circuit_breaker_open, _circuit_breaker_last_failure
    lock = _get_circuit_breaker_lock()
    async with lock:
        if not _circuit_breaker_open:
            return True

        # Check if enough time has passed to try again (half-open state)
        if time.time() - _circuit_breaker_last_failure > CIRCUIT_BREAKER_RESET_SECONDS:
            logger.info("rate_limiter_circuit_breaker_half_open", attempting_reset=True)
            return True

        return False


async def check_rate_limit(
    identifier: str,
    limit: int,
    prefix: str = "ratelimit",
) -> RateLimitResult:
    """Check rate limit for an identifier.

    Uses a circuit breaker pattern to fail-open when Redis is unavailable.
    This prevents Redis failures from blocking all requests.

    Args:
        identifier: Unique ID (api_key_id, IP address, etc.)
        limit: Max requests per minute
        prefix: Key prefix for Redis

    Returns:
        RateLimitResult with status
    """
    # Check circuit breaker state
    if not await _should_attempt_rate_limit():
        # Circuit is open - fail-open (allow request)
        logger.debug(
            "rate_limit_circuit_breaker_bypass",
            identifier=identifier[:8] + "..." if len(identifier) > 8 else identifier,
        )
        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=limit,  # Unknown, assume full
            reset_after_seconds=60,
        )

    try:
        limiter = await _get_rate_limiter()
        key = f"{prefix}:{identifier}"
        result = await limiter.check(key, limit)
        await _record_success()
        return result

    except (RedisError, ConnectionError, TimeoutError, OSError) as e:
        # Redis unavailable - fail-open (allow request)
        await _record_failure()
        logger.warning(
            "rate_limit_redis_unavailable",
            error_type=type(e).__name__,
            identifier=identifier[:8] + "..." if len(identifier) > 8 else identifier,
        )
        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=limit,  # Unknown, assume full
            reset_after_seconds=60,
        )
