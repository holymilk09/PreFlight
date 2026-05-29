"""Tests for fail-closed security posture (rate limiting + token revocation).

These exercise the degraded paths with Redis unavailable. They do NOT require
a running Redis; they mock the backend to fail. Existing tests (which mock Redis
as available) are unaffected because the happy path is unchanged.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.config import settings
from src.services import rate_limiter
from src.services.rate_limiter import RateLimitResult, check_rate_limit


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    """Ensure circuit breaker state does not leak between tests."""
    rate_limiter._circuit_breaker_failures = 0
    rate_limiter._circuit_breaker_open = False
    rate_limiter._circuit_breaker_last_failure = 0.0
    yield
    rate_limiter._circuit_breaker_failures = 0
    rate_limiter._circuit_breaker_open = False
    rate_limiter._circuit_breaker_last_failure = 0.0


class TestRateLimitResultDegraded:
    def test_degraded_defaults_false(self):
        r = RateLimitResult(allowed=True, limit=10, remaining=9, reset_after_seconds=60)
        assert r.degraded is False

    def test_degraded_can_be_set(self):
        r = RateLimitResult(
            allowed=False, limit=10, remaining=0, reset_after_seconds=60, degraded=True
        )
        assert r.degraded is True


@pytest.mark.asyncio
class TestRateLimitFailClosed:
    async def test_redis_down_fail_closed_denies(self, monkeypatch):
        monkeypatch.setattr(settings, "security_fail_closed", True)

        with patch.object(rate_limiter, "_get_rate_limiter", new=AsyncMock()) as m:
            limiter = m.return_value
            limiter.check = AsyncMock(side_effect=ConnectionError("redis down"))
            result = await check_rate_limit("ip:1.2.3.4", 10)

        assert result.allowed is False
        assert result.degraded is True

    async def test_redis_down_fail_open_allows(self, monkeypatch):
        monkeypatch.setattr(settings, "security_fail_closed", False)

        with patch.object(rate_limiter, "_get_rate_limiter", new=AsyncMock()) as m:
            limiter = m.return_value
            limiter.check = AsyncMock(side_effect=ConnectionError("redis down"))
            result = await check_rate_limit("ip:1.2.3.4", 10)

        assert result.allowed is True
        assert result.degraded is False

    async def test_circuit_open_fail_closed_denies(self, monkeypatch):
        monkeypatch.setattr(settings, "security_fail_closed", True)
        rate_limiter._circuit_breaker_open = True
        rate_limiter._circuit_breaker_last_failure = 9e18  # far future-ish; stays open

        result = await check_rate_limit("ip:1.2.3.4", 10)

        assert result.allowed is False
        assert result.degraded is True


@pytest.mark.asyncio
class TestTokenRevocationFailClosed:
    async def test_redis_down_fail_closed_treats_revoked(self, monkeypatch):
        from src import security

        monkeypatch.setattr(settings, "security_fail_closed", True)

        async def fake_get_redis():
            raise ConnectionError("redis down")

        monkeypatch.setattr("src.services.rate_limiter.get_redis_client", fake_get_redis)
        # is_token_revoked_async wraps _async_is_revoked.
        assert await security.is_token_revoked_async("some-jti") is True

    async def test_redis_down_fail_open_treats_not_revoked(self, monkeypatch):
        from src import security

        monkeypatch.setattr(settings, "security_fail_closed", False)

        async def fake_get_redis():
            raise ConnectionError("redis down")

        monkeypatch.setattr("src.services.rate_limiter.get_redis_client", fake_get_redis)
        assert await security.is_token_revoked_async("some-jti") is False

    async def test_redis_up_not_revoked_allows(self, monkeypatch):
        """Happy path unchanged: Redis up, jti not in blocklist -> not revoked."""
        from src import security

        monkeypatch.setattr(settings, "security_fail_closed", True)

        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=0)

        async def fake_get_redis():
            return redis

        monkeypatch.setattr("src.services.rate_limiter.get_redis_client", fake_get_redis)
        assert await security.is_token_revoked_async("some-jti") is False

    async def test_redis_up_revoked_denies(self, monkeypatch):
        from src import security

        redis = AsyncMock()
        redis.exists = AsyncMock(return_value=1)

        async def fake_get_redis():
            return redis

        monkeypatch.setattr("src.services.rate_limiter.get_redis_client", fake_get_redis)
        assert await security.is_token_revoked_async("some-jti") is True
