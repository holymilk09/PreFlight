"""Monthly usage metering against plan quotas.

Meters evaluations per tenant per calendar month (UTC) against the limit implied
by the tenant's plan (``Tenant.settings["plan"]``, set at signup). A tenant-level
``monthly_evaluation_limit`` in settings overrides the plan default, which is how
custom enterprise contracts are represented. ``None`` means unlimited.

Counting queries run on a tenant-scoped session (RLS filters rows), using the
composite (tenant_id, created_at) index from migration 006.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Evaluation

# Monthly evaluation quotas per plan (see README pricing). None = unlimited.
PLAN_MONTHLY_LIMITS: dict[str, int | None] = {
    "free": 1_000,
    "developer": 10_000,
    "team": 100_000,
    "enterprise": None,
}

# Unknown/missing plans get the most conservative quota. Only consequential when
# quota enforcement is enabled; metering itself just reports the numbers.
DEFAULT_PLAN = "free"


@dataclass
class UsageSnapshot:
    """A tenant's evaluation usage for the current calendar month."""

    plan: str
    period_start: datetime
    period_end: datetime
    monthly_limit: int | None  # None = unlimited
    used: int

    @property
    def remaining(self) -> int | None:
        """Evaluations left this period (None = unlimited)."""
        if self.monthly_limit is None:
            return None
        return max(0, self.monthly_limit - self.used)

    @property
    def exceeded(self) -> bool:
        """Whether the tenant has used up its monthly quota."""
        return self.monthly_limit is not None and self.used >= self.monthly_limit


def current_period(now: datetime) -> tuple[datetime, datetime]:
    """Return the [start, end) bounds of the calendar month containing ``now``.

    Bounds are naive UTC to match DB-stored timestamps (datetime.utcnow).
    """
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def resolve_plan_and_limit(tenant_settings: dict[str, Any] | None) -> tuple[str, int | None]:
    """Resolve the plan name and monthly evaluation limit for a tenant.

    A tenant-level ``monthly_evaluation_limit`` (int, or None for unlimited)
    overrides the plan default; unknown plans fall back to the free quota.
    """
    settings = tenant_settings or {}
    plan = str(settings.get("plan") or DEFAULT_PLAN)
    if "monthly_evaluation_limit" in settings:
        override = settings["monthly_evaluation_limit"]
        return plan, int(override) if override is not None else None
    if plan in PLAN_MONTHLY_LIMITS:
        return plan, PLAN_MONTHLY_LIMITS[plan]
    return plan, PLAN_MONTHLY_LIMITS[DEFAULT_PLAN]


async def get_usage(
    db: AsyncSession,
    tenant_settings: dict[str, Any] | None,
    now: datetime | None = None,
) -> UsageSnapshot:
    """Compute the tenant's usage snapshot for the current calendar month.

    ``db`` must be a tenant-scoped session: RLS restricts the count to the
    tenant's own evaluations.
    """
    resolved_now = now or datetime.utcnow()
    start, end = current_period(resolved_now)
    plan, limit = resolve_plan_and_limit(tenant_settings)

    stmt = select(func.count()).where(
        Evaluation.created_at >= start,
        Evaluation.created_at < end,
    )
    used = (await db.execute(stmt)).scalar_one()

    return UsageSnapshot(
        plan=plan,
        period_start=start,
        period_end=end,
        monthly_limit=limit,
        used=int(used),
    )
