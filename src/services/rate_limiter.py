"""Redis-based rate limiting using sliding window algorithm."""

import time
from dataclasses import dataclass

import redis.asyncio as aioredis
from redis.exceptions import NoScriptError

from src.config import settings


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


async def check_rate_limit(
    identifier: str,
    limit: int,
    prefix: str = "ratelimit",
) -> RateLimitResult:
    """Check rate limit for an identifier.

    Args:
        identifier: Unique ID (api_key_id, IP address, etc.)
        limit: Max requests per minute
        prefix: Key prefix for Redis

    Returns:
        RateLimitResult with status
    """
    limiter = await _get_rate_limiter()
    key = f"{prefix}:{identifier}"
    return await limiter.check(key, limit)
