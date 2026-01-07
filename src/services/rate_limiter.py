"""Redis-based rate limiting using sliding window algorithm."""

import time
from dataclasses import dataclass

import redis.asyncio as redis

from src.config import settings


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_after_seconds: int


class RateLimiter:
    """Sliding window rate limiter using Redis.

    Uses a sorted set to track request timestamps, allowing for accurate
    sliding window rate limiting without race conditions.
    """

    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis = redis_client
        self.window_seconds = 60  # 1 minute window

    async def check(self, key: str, limit: int) -> RateLimitResult:
        """Check if request is allowed and record it if so.

        Args:
            key: Unique identifier (e.g., api_key_id or IP address)
            limit: Maximum requests per window

        Returns:
            RateLimitResult with allowed status and metadata
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Use Redis pipeline for atomic operations
        pipe = self.redis.pipeline()

        # Remove old entries outside the window
        pipe.zremrangebyscore(key, 0, window_start)

        # Count current requests in window
        pipe.zcard(key)

        # Add current request (will be rolled back if over limit)
        request_id = f"{now}"
        pipe.zadd(key, {request_id: now})

        # Set expiry on the key to auto-cleanup
        pipe.expire(key, self.window_seconds + 1)

        results = await pipe.execute()
        current_count = results[1]  # zcard result

        if current_count >= limit:
            # Over limit - remove the request we just added
            await self.redis.zrem(key, request_id)

            # Calculate reset time (when oldest request expires)
            oldest = await self.redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                reset_after = int(oldest[0][1] + self.window_seconds - now) + 1
            else:
                reset_after = self.window_seconds

            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_after_seconds=reset_after,
            )

        remaining = max(0, limit - current_count - 1)
        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=remaining,
            reset_after_seconds=self.window_seconds,
        )


# Global Redis client (initialized on first use)
_redis_client: redis.Redis | None = None


async def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            password=settings.redis_password,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis_client() -> None:
    """Close Redis client on shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


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
    client = await get_redis_client()
    limiter = RateLimiter(client)
    key = f"{prefix}:{identifier}"
    return await limiter.check(key, limit)
