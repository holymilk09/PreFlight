"""Prometheus metrics for the Document Extraction Control Plane.

Defines all metrics for monitoring API performance, evaluation decisions,
template matching, and drift detection.
"""

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# -----------------------------------------------------------------------------
# Request Metrics
# -----------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "preflight_requests_total",
    "Total API requests",
    ["endpoint", "method", "status"],
)

REQUEST_LATENCY = Histogram(
    "preflight_request_duration_seconds",
    "Request latency in seconds",
    ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# -----------------------------------------------------------------------------
# Evaluation Metrics
# -----------------------------------------------------------------------------

EVALUATION_DECISIONS = Counter(
    "preflight_evaluations_total",
    "Evaluation decisions by type",
    ["decision"],
)

TEMPLATE_MATCHES = Counter(
    "preflight_template_matches_total",
    "Template match attempts",
    ["matched"],  # "true" or "false"
)

DRIFT_SCORE = Histogram(
    "preflight_drift_score",
    "Distribution of drift scores",
    buckets=(0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.75, 1.0),
)

RELIABILITY_SCORE = Histogram(
    "preflight_reliability_score",
    "Distribution of reliability scores",
    buckets=(0.0, 0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95, 1.0),
)

# -----------------------------------------------------------------------------
# Security Metrics
# -----------------------------------------------------------------------------

RATE_LIMIT_HITS = Counter(
    "preflight_rate_limit_hits_total",
    "Rate limit violations",
    ["identifier_type"],  # "key" or "ip"
)

AUTH_FAILURES = Counter(
    "preflight_auth_failures_total",
    "Authentication failures",
    ["reason"],  # "invalid_key", "expired", "missing"
)

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------


def get_metrics() -> bytes:
    """Generate latest metrics in Prometheus format."""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get the content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST


def record_evaluation(
    decision: str,
    drift_score: float,
    reliability_score: float,
    template_matched: bool,
) -> None:
    """Record metrics for an evaluation request.

    Args:
        decision: The evaluation decision (MATCH, REVIEW, NEW)
        drift_score: Computed drift score (0-1)
        reliability_score: Computed reliability score (0-1)
        template_matched: Whether a template was matched
    """
    EVALUATION_DECISIONS.labels(decision=decision).inc()
    TEMPLATE_MATCHES.labels(matched=str(template_matched).lower()).inc()

    if template_matched:
        DRIFT_SCORE.observe(drift_score)
        RELIABILITY_SCORE.observe(reliability_score)


def record_rate_limit_hit(identifier_type: str) -> None:
    """Record a rate limit violation.

    Args:
        identifier_type: Type of identifier ("key" or "ip")
    """
    RATE_LIMIT_HITS.labels(identifier_type=identifier_type).inc()


def record_auth_failure(reason: str) -> None:
    """Record an authentication failure.

    Args:
        reason: Reason for failure (invalid_key, expired, missing)
    """
    AUTH_FAILURES.labels(reason=reason).inc()
