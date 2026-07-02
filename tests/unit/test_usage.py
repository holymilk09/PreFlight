"""Tests for the monthly usage metering service."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.usage import (
    PLAN_MONTHLY_LIMITS,
    UsageSnapshot,
    current_period,
    get_usage,
    resolve_plan_and_limit,
)


class TestCurrentPeriod:
    """Tests for calendar-month period bounds."""

    def test_mid_month(self):
        """Mid-month timestamps map to [1st of month, 1st of next month)."""
        start, end = current_period(datetime(2026, 6, 15, 13, 45, 12))
        assert start == datetime(2026, 6, 1)
        assert end == datetime(2026, 7, 1)

    def test_first_instant_of_month(self):
        """Exactly midnight on the 1st belongs to that month's period."""
        start, end = current_period(datetime(2026, 6, 1, 0, 0, 0))
        assert start == datetime(2026, 6, 1)
        assert end == datetime(2026, 7, 1)

    def test_december_rolls_over_year(self):
        """December's period ends on January 1st of the next year."""
        start, end = current_period(datetime(2026, 12, 31, 23, 59, 59))
        assert start == datetime(2026, 12, 1)
        assert end == datetime(2027, 1, 1)


class TestResolvePlanAndLimit:
    """Tests for plan/limit resolution from tenant settings."""

    def test_known_plans(self):
        """Each known plan resolves to its published quota."""
        assert resolve_plan_and_limit({"plan": "free"}) == ("free", 1_000)
        assert resolve_plan_and_limit({"plan": "developer"}) == ("developer", 10_000)
        assert resolve_plan_and_limit({"plan": "team"}) == ("team", 100_000)
        assert resolve_plan_and_limit({"plan": "enterprise"}) == ("enterprise", None)

    def test_missing_settings_defaults_to_free(self):
        """No settings at all -> free plan quota (most conservative)."""
        assert resolve_plan_and_limit(None) == ("free", PLAN_MONTHLY_LIMITS["free"])
        assert resolve_plan_and_limit({}) == ("free", PLAN_MONTHLY_LIMITS["free"])

    def test_unknown_plan_falls_back_to_free_quota(self):
        """An unrecognized plan keeps its name but gets the free quota."""
        plan, limit = resolve_plan_and_limit({"plan": "bespoke-tier"})
        assert plan == "bespoke-tier"
        assert limit == PLAN_MONTHLY_LIMITS["free"]

    def test_tenant_override_takes_precedence(self):
        """A tenant-level monthly_evaluation_limit overrides the plan default."""
        plan, limit = resolve_plan_and_limit({"plan": "free", "monthly_evaluation_limit": 5_000})
        assert (plan, limit) == ("free", 5_000)

    def test_tenant_override_null_means_unlimited(self):
        """An explicit null override means unlimited, whatever the plan."""
        plan, limit = resolve_plan_and_limit({"plan": "free", "monthly_evaluation_limit": None})
        assert (plan, limit) == ("free", None)


class TestUsageSnapshot:
    """Tests for snapshot-derived fields."""

    def _snapshot(self, limit: int | None, used: int) -> UsageSnapshot:
        return UsageSnapshot(
            plan="free",
            period_start=datetime(2026, 6, 1),
            period_end=datetime(2026, 7, 1),
            monthly_limit=limit,
            used=used,
        )

    def test_remaining_under_limit(self):
        assert self._snapshot(limit=1_000, used=250).remaining == 750

    def test_remaining_clamped_at_zero(self):
        """Over-quota usage never reports negative remaining."""
        assert self._snapshot(limit=1_000, used=1_500).remaining == 0

    def test_unlimited_remaining_is_none(self):
        assert self._snapshot(limit=None, used=999_999).remaining is None

    def test_exceeded_at_limit(self):
        """The quota is exhausted at exactly the limit (used >= limit)."""
        assert self._snapshot(limit=1_000, used=1_000).exceeded is True
        assert self._snapshot(limit=1_000, used=999).exceeded is False

    def test_unlimited_never_exceeded(self):
        assert self._snapshot(limit=None, used=10**9).exceeded is False


class TestGetUsage:
    """Tests for the DB-backed snapshot computation."""

    @pytest.mark.asyncio
    async def test_counts_current_period(self):
        """Counts evaluations in the current month with the resolved plan/limit."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 42
        mock_db.execute.return_value = mock_result

        snapshot = await get_usage(
            mock_db,
            {"plan": "developer"},
            now=datetime(2026, 6, 15, 12, 0, 0),
        )

        assert snapshot.plan == "developer"
        assert snapshot.monthly_limit == 10_000
        assert snapshot.used == 42
        assert snapshot.remaining == 9_958
        assert snapshot.period_start == datetime(2026, 6, 1)
        assert snapshot.period_end == datetime(2026, 7, 1)
        assert snapshot.exceeded is False
