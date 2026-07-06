"""Read-only analytics routes over evaluation history (tenant-scoped via RLS)."""

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter
from sqlalchemy import func, select

from src.api.auth import ReadTenant
from src.api.deps import TenantDbSession
from src.api.errors import ErrorCode, bad_request
from src.models import (
    AnalyticsExtractorResponse,
    AnalyticsExtractorStat,
    AnalyticsSummaryResponse,
    AnalyticsTimeseriesBucket,
    AnalyticsTimeseriesResponse,
    CalibrationBand,
    CalibrationResponse,
    Evaluation,
    EvaluationFeedback,
    FeedbackOutcome,
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
    tenant: ReadTenant,
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
    tenant: ReadTenant,
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
    tenant: ReadTenant,
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


# Reliability-score bands for calibration (10 equal bands over [0, 1]).
CALIBRATION_BANDS = 10


def _enum_key(value: object) -> str:
    """Normalize an enum-or-string DB value to its string key."""
    return value.value if hasattr(value, "value") else str(value)


def summarize_calibration(
    decision_outcome_counts: dict[str, dict[str, int]],
) -> tuple[float | None, float | None, int, int]:
    """Derive headline calibration metrics from decision × outcome counts.

    Returns (auto_process_precision, review_catch_rate, errors_caught,
    missed_errors). MATCH is the auto-process path; every other decision is a
    "flagged" document. An outcome other than ``correct`` counts as bad.
    """
    correct = FeedbackOutcome.CORRECT.value

    match_counts = decision_outcome_counts.get("MATCH", {})
    match_total = sum(match_counts.values())
    match_correct = match_counts.get(correct, 0)

    flagged_total = 0
    flagged_bad = 0
    for decision, outcomes in decision_outcome_counts.items():
        if decision == "MATCH":
            continue
        for outcome, count in outcomes.items():
            flagged_total += count
            if outcome != correct:
                flagged_bad += count

    precision = match_correct / match_total if match_total else None
    catch_rate = flagged_bad / flagged_total if flagged_total else None
    missed = match_total - match_correct
    return precision, catch_rate, flagged_bad, missed


@router.get(
    "/analytics/calibration",
    response_model=CalibrationResponse,
    tags=["Analytics"],
    summary="Score calibration against reported outcomes",
)
async def analytics_calibration(
    tenant: ReadTenant,
    db: TenantDbSession,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
) -> CalibrationResponse:
    """How decisions and reliability scores line up with reported outcomes.

    Powered by POST /v1/evaluations/{id}/feedback. Headline metrics:
    auto-process precision (safety of MATCH), review catch rate (how often a
    flagged document was actually bad), errors caught vs missed.
    """
    start, end = _resolve_range(from_ts, to_ts)
    window = (Evaluation.created_at >= start, Evaluation.created_at < end)

    total_evaluations = (await db.execute(select(func.count()).where(*window))).scalar_one()

    # Decision × outcome counts over evaluations that have feedback.
    decision_stmt = (
        select(Evaluation.decision, EvaluationFeedback.outcome, func.count())
        .join(EvaluationFeedback, EvaluationFeedback.evaluation_id == Evaluation.id)
        .where(*window)
        .group_by(Evaluation.decision, EvaluationFeedback.outcome)
    )
    decision_rows = (await db.execute(decision_stmt)).all()

    decision_outcomes: dict[str, dict[str, int]] = {}
    feedback_count = 0
    for decision, outcome, count in decision_rows:
        decision_outcomes.setdefault(_enum_key(decision), {})[_enum_key(outcome)] = count
        feedback_count += count

    precision, catch_rate, errors_caught, missed_errors = summarize_calibration(decision_outcomes)

    # Outcome accuracy per reliability-score band. width_bucket puts values
    # equal to the upper bound (1.0) into band N+1 — fold that into band N.
    band_col = func.width_bucket(Evaluation.reliability_score, 0.0, 1.0, CALIBRATION_BANDS).label(
        "band"
    )
    band_stmt = (
        select(band_col, EvaluationFeedback.outcome, func.count())
        .join(EvaluationFeedback, EvaluationFeedback.evaluation_id == Evaluation.id)
        .where(*window, Evaluation.reliability_score.is_not(None))
        .group_by(band_col)
        .group_by(EvaluationFeedback.outcome)
    )
    band_rows = (await db.execute(band_stmt)).all()

    band_totals: dict[int, dict[str, int]] = {}
    for band, outcome, count in band_rows:
        idx = min(int(band), CALIBRATION_BANDS)
        band_totals.setdefault(idx, {})[_enum_key(outcome)] = (
            band_totals.get(idx, {}).get(_enum_key(outcome), 0) + count
        )

    bands: list[CalibrationBand] = []
    for idx in sorted(band_totals):
        outcomes = band_totals[idx]
        total = sum(outcomes.values())
        band_correct = outcomes.get(FeedbackOutcome.CORRECT.value, 0)
        bands.append(
            CalibrationBand(
                band_start=round((idx - 1) / CALIBRATION_BANDS, 2),
                band_end=round(idx / CALIBRATION_BANDS, 2),
                total=total,
                correct=band_correct,
                accuracy=band_correct / total if total else None,
            )
        )

    return CalibrationResponse(
        from_ts=start,
        to_ts=end,
        total_evaluations=total_evaluations,
        feedback_count=feedback_count,
        feedback_coverage=(feedback_count / total_evaluations) if total_evaluations else None,
        auto_process_precision=precision,
        review_catch_rate=catch_rate,
        errors_caught=errors_caught,
        missed_errors=missed_errors,
        decision_outcomes=decision_outcomes,
        reliability_bands=bands,
    )
