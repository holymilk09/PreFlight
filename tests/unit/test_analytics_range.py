"""Unit tests for analytics range resolution and validation (no DB required)."""

from datetime import UTC, datetime, timedelta

import pytest

from src.api.analytics_routes import (
    DEFAULT_RANGE_DAYS,
    MAX_RANGE_DAYS,
    _resolve_range,
)
from src.api.errors import APIError


class TestResolveRange:
    def test_defaults_to_last_30_days(self):
        start, end = _resolve_range(None, None)
        delta = end - start
        # Allow a small tolerance for execution time.
        assert abs(delta.days - DEFAULT_RANGE_DAYS) <= 1

    def test_explicit_range_naive(self):
        a = datetime(2026, 1, 1)
        b = datetime(2026, 1, 10)
        start, end = _resolve_range(a, b)
        assert start == a
        assert end == b

    def test_tz_aware_normalized_to_naive(self):
        a = datetime(2026, 1, 1, tzinfo=UTC)
        b = datetime(2026, 1, 2, tzinfo=UTC)
        start, end = _resolve_range(a, b)
        assert start.tzinfo is None
        assert end.tzinfo is None

    def test_from_after_to_rejected(self):
        a = datetime(2026, 2, 1)
        b = datetime(2026, 1, 1)
        with pytest.raises(APIError) as exc:
            _resolve_range(a, b)
        assert exc.value.status_code == 400

    def test_from_equal_to_rejected(self):
        a = datetime(2026, 1, 1)
        with pytest.raises(APIError):
            _resolve_range(a, a)

    def test_range_too_large_rejected(self):
        a = datetime(2020, 1, 1)
        b = a + timedelta(days=MAX_RANGE_DAYS + 5)
        with pytest.raises(APIError) as exc:
            _resolve_range(a, b)
        assert exc.value.status_code == 400
