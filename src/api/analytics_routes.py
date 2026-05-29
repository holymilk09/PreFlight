"""Read-only analytics routes over evaluation history (tenant-scoped via RLS)."""

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter
from sqlalchemy import func, select

from src.api.auth import CurrentTenant
from src.api.deps import TenantDbSession
from src.api.errors import ErrorCode, bad_request
from src.models import (
    AnalyticsExtractorResponse,
    AnalyticsExtractorStat,
    AnalyticsSummaryResponse,
    AnalyticsTimeseriesBucket,
    AnalyticsTimeseriesResponse,
    Evaluation,
)

logger = structlog.get_logger()

router = APIRouter()

DEFAULT_RANGE_DAYS = 30
# Cap to bound query cost / response size.
MAX_RANGE_DAYS = 366
MAX_BUCKETS = 1000


def _resolve_range(from_ts: datetime | None, to_ts: datetime | None) -> tuple[datetime, datetime]:
    """Resolve and validate the analytics time range (defaults to last 30 days)."""
    now = datetime.now(UTC)
    resolved_to = to_ts or now
    resolved_from = from_ts or (resolved_to - timedelta(days=DEFAULT_RANGE_DAYS))

    # Normalize to naive UTC to match DB-stored naive datetimes (datetime.utcnow).
    if resolved_from.tzinfo is not None:
        resolved_from = resolved_from.astimezone(UTC).replace(tzinfo=None)
    if resolved_to.tzinfo is not None:
        resolved_to = resolved_to.astimezone(UTC).replace(tzinfo=None)

    if resolved_from >= resolved_to:
        raise bad_request(
            ErrorCode.INVALID_REQUEST,
            "from_ts must be strictly before to_ts",
        )
    if (resolved_to - resolved_from) > timedelta(days=MAX_RANGE_DAYS):
        raise bad_request(
            ErrorCode.INVALID_REQUEST,
            f"Time range too large (max {MAX_RANGE_DAYS} days)",
        )
    return resolved_from, resolved_to


@router.get(
    "/analytics/summary",
    response_model=AnalyticsSummaryResponse,
    tags=["Analytics"],
    summary="Aggregate analytics summary",
)
async def analytics_summary(
    tenant: CurrentTenant,
    db: TenantDbSession,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> AnalyticsSummaryResponse:
    """Aggregate totals, decision breakdown, and drift/reliability stats."""
    start, end = _resolve_range(from_ts, to_ts)
    window = (Evaluation.created_at >= start, Evaluation.created_at < end)

    # Decision breakdown + total.
    decision_stmt = (
        select(Evaluation.decision, func.count()).where(*window).group_by(Evaluation.decision)
    )
    decision_rows = (await db.execute(decision_stmt)).all()
    decision_breakdown: dict[str, int] = {}
    total = 0
    for decision, count in decision_rows:
        key = decision.value if hasattr(decision, "value") else str(decision)
        decision_breakdown[key] = count
        total += count

    # Aggregate metrics (SQL AVG / percentile_cont ignore NULLs).
    agg_stmt = select(
        func.avg(Evaluation.drift_score),
        func.percentile_cont(0.95).within_group(Evaluation.drift_score.asc()),
        func.avg(Evaluation.reliability_score),
        func.percentile_cont(0.95).within_group(Evaluation.reliability_score.asc()),
    ).where(*window)
    avg_drift, p95_drift, avg_rel, p95_rel = (await db.execute(agg_stmt)).one()

    return AnalyticsSummaryResponse(
        from_ts=start,
        to_ts=end,
        total_evaluations=total,
        decision_breakdown=decision_breakdown,
        avg_drift=float(avg_drift) if avg_drift is not None else None,
        p95_drift=float(p95_drift) if p95_drift is not None else None,
        avg_reliability=float(avg_rel) if avg_rel is not None else None,
        p95_reliability=float(p95_rel) if p95_rel is not None else None,
    )


@router.get(
    "/analytics/timeseries",
    response_model=AnalyticsTimeseriesResponse,
    tags=["Analytics"],
    summary="Timeseries analytics",
)
async def analytics_timeseries(
    tenant: CurrentTenant,
    db: TenantDbSession,
    interval: str = "day",
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> AnalyticsTimeseriesResponse:
    """Per-bucket counts-by-decision and avg drift/reliability."""
    if interval not in ("day", "hour"):
        raise bad_request(
            ErrorCode.INVALID_REQUEST,
            "interval must be 'day' or 'hour'",
            interval=interval,
        )
    start, end = _resolve_range(from_ts, to_ts)

    # Guard against excessive bucket counts.
    span_seconds = (end - start).total_seconds()
    bucket_seconds = 3600 if interval == "hour" else 86400
    if span_seconds / bucket_seconds > MAX_BUCKETS:
        raise bad_request(
            ErrorCode.INVALID_REQUEST,
            f"Range/interval would produce more than {MAX_BUCKETS} buckets",
        )

    window = (Evaluation.created_at >= start, Evaluation.created_at < end)
    bucket_col = func.date_trunc(interval, Evaluation.created_at).label("bucket")

    # Per-bucket per-decision counts.
    count_stmt = (
        select(bucket_col, Evaluation.decision, func.count())
        .where(*window)
        .group_by(bucket_col, Evaluation.decision)
    )
    count_rows = (await db.execute(count_stmt)).all()

    # Per-bucket aggregate metrics.
    metric_stmt = (
        select(
            bucket_col,
            func.count(),
            func.avg(Evaluation.drift_score),
            func.avg(Evaluation.reliability_score),
        )
        .where(*window)
        .group_by(bucket_col)
    )
    metric_rows = (await db.execute(metric_stmt)).all()

    buckets: dict[datetime, AnalyticsTimeseriesBucket] = {}
    for bucket, count, avg_drift, avg_rel in metric_rows:
        buckets[bucket] = AnalyticsTimeseriesBucket(
            bucket=bucket,
            total=count,
            decision_breakdown={},
            avg_drift=float(avg_drift) if avg_drift is not None else None,
            avg_reliability=float(avg_rel) if avg_rel is not None else None,
        )
    for bucket, decision, count in count_rows:
        key = decision.value if hasattr(decision, "value") else str(decision)
        if bucket not in buckets:
            buckets[bucket] = AnalyticsTimeseriesBucket(bucket=bucket, total=0)
        buckets[bucket].decision_breakdown[key] = count

    ordered = [buckets[k] for k in sorted(buckets.keys())]

    return AnalyticsTimeseriesResponse(
        from_ts=start,
        to_ts=end,
        interval=interval,
        buckets=ordered,
    )


@router.get(
    "/analytics/extractors",
    response_model=AnalyticsExtractorResponse,
    tags=["Analytics"],
    summary="Per-vendor extractor analytics",
)
async def analytics_extractors(
    tenant: CurrentTenant,
    db: TenantDbSession,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> AnalyticsExtractorResponse:
    """Per-vendor counts and drift/reliability/confidence/latency aggregates."""
    start, end = _resolve_range(from_ts, to_ts)
    window = (Evaluation.created_at >= start, Evaluation.created_at < end)

    agg_stmt = (
        select(
            Evaluation.extractor_vendor,
            func.count(),
            func.avg(Evaluation.drift_score),
            func.percentile_cont(0.95).within_group(Evaluation.drift_score.asc()),
            func.avg(Evaluation.reliability_score),
            func.avg(Evaluation.extractor_confidence),
            func.avg(Evaluation.extractor_latency_ms),
        )
        .where(*window)
        .group_by(Evaluation.extractor_vendor)
    )
    agg_rows = (await db.execute(agg_stmt)).all()

    decision_stmt = (
        select(Evaluation.extractor_vendor, Evaluation.decision, func.count())
        .where(*window)
        .group_by(Evaluation.extractor_vendor, Evaluation.decision)
    )
    decision_rows = (await db.execute(decision_stmt)).all()

    breakdown_by_vendor: dict[str | None, dict[str, int]] = {}
    for vendor, decision, count in decision_rows:
        key = decision.value if hasattr(decision, "value") else str(decision)
        breakdown_by_vendor.setdefault(vendor, {})[key] = count

    extractors: list[AnalyticsExtractorStat] = []
    for vendor, count, avg_drift, p95_drift, avg_rel, avg_conf, avg_latency in agg_rows:
        extractors.append(
            AnalyticsExtractorStat(
                vendor=vendor,
                count=count,
                avg_drift=float(avg_drift) if avg_drift is not None else None,
                p95_drift=float(p95_drift) if p95_drift is not None else None,
                avg_reliability=float(avg_rel) if avg_rel is not None else None,
                avg_extractor_confidence=float(avg_conf) if avg_conf is not None else None,
                avg_extractor_latency_ms=float(avg_latency) if avg_latency is not None else None,
                decision_breakdown=breakdown_by_vendor.get(vendor, {}),
            )
        )

    return AnalyticsExtractorResponse(from_ts=start, to_ts=end, extractors=extractors)
