"""Unit tests for Prometheus metrics."""

import pytest
from prometheus_client import REGISTRY

from src.metrics import (
    AUTH_FAILURES,
    DRIFT_SCORE,
    EVALUATION_DECISIONS,
    RATE_LIMIT_HITS,
    RELIABILITY_SCORE,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    TEMPLATE_MATCHES,
    get_metrics,
    get_metrics_content_type,
    record_auth_failure,
    record_evaluation,
    record_rate_limit_hit,
)


class TestMetricDefinitions:
    """Test that all metrics are properly defined."""

    def test_request_count_defined(self):
        """REQUEST_COUNT metric should be defined with correct labels."""
        # prometheus_client stores base name without _total suffix
        assert "preflight_requests" in REQUEST_COUNT._name
        assert set(REQUEST_COUNT._labelnames) == {"endpoint", "method", "status"}

    def test_request_latency_defined(self):
        """REQUEST_LATENCY metric should be defined with correct labels."""
        assert REQUEST_LATENCY._name == "preflight_request_duration_seconds"
        assert set(REQUEST_LATENCY._labelnames) == {"endpoint"}

    def test_evaluation_decisions_defined(self):
        """EVALUATION_DECISIONS metric should be defined with correct labels."""
        assert "preflight_evaluations" in EVALUATION_DECISIONS._name
        assert set(EVALUATION_DECISIONS._labelnames) == {"decision"}

    def test_template_matches_defined(self):
        """TEMPLATE_MATCHES metric should be defined with correct labels."""
        assert "preflight_template_matches" in TEMPLATE_MATCHES._name
        assert set(TEMPLATE_MATCHES._labelnames) == {"matched"}

    def test_drift_score_defined(self):
        """DRIFT_SCORE metric should be defined."""
        assert DRIFT_SCORE._name == "preflight_drift_score"

    def test_reliability_score_defined(self):
        """RELIABILITY_SCORE metric should be defined."""
        assert RELIABILITY_SCORE._name == "preflight_reliability_score"

    def test_rate_limit_hits_defined(self):
        """RATE_LIMIT_HITS metric should be defined with correct labels."""
        assert "preflight_rate_limit_hits" in RATE_LIMIT_HITS._name
        assert set(RATE_LIMIT_HITS._labelnames) == {"identifier_type"}

    def test_auth_failures_defined(self):
        """AUTH_FAILURES metric should be defined with correct labels."""
        assert "preflight_auth_failures" in AUTH_FAILURES._name
        assert set(AUTH_FAILURES._labelnames) == {"reason"}


class TestMetricRecording:
    """Test metric recording functions."""

    def test_record_evaluation_match(self):
        """record_evaluation should record MATCH decision metrics."""
        # Get initial values
        initial_decisions = EVALUATION_DECISIONS.labels(decision="MATCH")._value.get()
        initial_matches = TEMPLATE_MATCHES.labels(matched="true")._value.get()

        # Record an evaluation
        record_evaluation(
            decision="MATCH",
            drift_score=0.15,
            reliability_score=0.92,
            template_matched=True,
        )

        # Verify metrics incremented
        assert EVALUATION_DECISIONS.labels(decision="MATCH")._value.get() == initial_decisions + 1
        assert TEMPLATE_MATCHES.labels(matched="true")._value.get() == initial_matches + 1

    def test_record_evaluation_new(self):
        """record_evaluation should record NEW decision metrics."""
        initial_decisions = EVALUATION_DECISIONS.labels(decision="NEW")._value.get()
        initial_matches = TEMPLATE_MATCHES.labels(matched="false")._value.get()

        record_evaluation(
            decision="NEW",
            drift_score=0.0,
            reliability_score=0.0,
            template_matched=False,
        )

        assert EVALUATION_DECISIONS.labels(decision="NEW")._value.get() == initial_decisions + 1
        assert TEMPLATE_MATCHES.labels(matched="false")._value.get() == initial_matches + 1

    def test_record_evaluation_review(self):
        """record_evaluation should record REVIEW decision metrics."""
        initial_decisions = EVALUATION_DECISIONS.labels(decision="REVIEW")._value.get()

        record_evaluation(
            decision="REVIEW",
            drift_score=0.25,
            reliability_score=0.75,
            template_matched=True,
        )

        assert EVALUATION_DECISIONS.labels(decision="REVIEW")._value.get() == initial_decisions + 1

    def test_record_rate_limit_hit_key(self):
        """record_rate_limit_hit should record key-based rate limits."""
        initial = RATE_LIMIT_HITS.labels(identifier_type="key")._value.get()

        record_rate_limit_hit("key")

        assert RATE_LIMIT_HITS.labels(identifier_type="key")._value.get() == initial + 1

    def test_record_rate_limit_hit_ip(self):
        """record_rate_limit_hit should record IP-based rate limits."""
        initial = RATE_LIMIT_HITS.labels(identifier_type="ip")._value.get()

        record_rate_limit_hit("ip")

        assert RATE_LIMIT_HITS.labels(identifier_type="ip")._value.get() == initial + 1

    def test_record_auth_failure(self):
        """record_auth_failure should record authentication failures."""
        initial = AUTH_FAILURES.labels(reason="invalid_key")._value.get()

        record_auth_failure("invalid_key")

        assert AUTH_FAILURES.labels(reason="invalid_key")._value.get() == initial + 1


class TestMetricsOutput:
    """Test metrics output functions."""

    def test_get_metrics_returns_bytes(self):
        """get_metrics should return bytes."""
        result = get_metrics()
        assert isinstance(result, bytes)

    def test_get_metrics_contains_metric_names(self):
        """get_metrics output should contain metric names."""
        result = get_metrics().decode("utf-8")

        assert "preflight_requests_total" in result
        assert "preflight_request_duration_seconds" in result
        assert "preflight_evaluations_total" in result
        assert "preflight_template_matches_total" in result
        assert "preflight_drift_score" in result
        assert "preflight_reliability_score" in result
        assert "preflight_rate_limit_hits_total" in result
        assert "preflight_auth_failures_total" in result

    def test_get_metrics_content_type(self):
        """get_metrics_content_type should return prometheus content type."""
        result = get_metrics_content_type()
        assert "text/plain" in result or "openmetrics" in result.lower()


class TestRequestMetrics:
    """Test request count and latency metrics."""

    def test_request_count_increment(self):
        """REQUEST_COUNT should increment with labels."""
        initial = REQUEST_COUNT.labels(
            endpoint="/health",
            method="GET",
            status=200,
        )._value.get()

        REQUEST_COUNT.labels(
            endpoint="/health",
            method="GET",
            status=200,
        ).inc()

        assert REQUEST_COUNT.labels(
            endpoint="/health",
            method="GET",
            status=200,
        )._value.get() == initial + 1

    def test_request_latency_observe(self):
        """REQUEST_LATENCY should record observations."""
        # Record a latency observation
        REQUEST_LATENCY.labels(endpoint="/test").observe(0.05)

        # Get metrics output and verify histogram exists
        result = get_metrics().decode("utf-8")
        assert "preflight_request_duration_seconds" in result
