"""Unit tests for the alerting engine (rule evaluation + HMAC signing).

These tests are pure-unit: rule evaluation uses a fake async DB session and
the HMAC signing test is self-contained. No Postgres/Redis required.
"""

import hashlib
import hmac
from uuid import uuid4

import pytest

from src.services.alerting import (
    DEFAULT_ALERT_RULES,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    _comparator_breached,
    evaluate_alerts,
    sign_payload,
)


class TestSignPayload:
    """Tests for the outbound webhook HMAC signature."""

    def test_signature_format_and_value(self):
        secret = "topsecret"
        body = b'{"event_id":"abc"}'
        timestamp = "1700000000"

        sig = sign_payload(secret, body, timestamp)

        assert sig.startswith("sha256=")
        expected = hmac.new(
            secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
        ).hexdigest()
        assert sig == f"sha256={expected}"

    def test_signature_is_deterministic(self):
        secret = "k"
        body = b"payload"
        ts = "123"
        assert sign_payload(secret, body, ts) == sign_payload(secret, body, ts)

    def test_signature_changes_with_timestamp(self):
        """Timestamp binding means different timestamps produce different sigs."""
        secret = "k"
        body = b"payload"
        assert sign_payload(secret, body, "1") != sign_payload(secret, body, "2")

    def test_signature_changes_with_body(self):
        secret = "k"
        ts = "1"
        assert sign_payload(secret, body=b"a", timestamp=ts) != sign_payload(
            secret, body=b"b", timestamp=ts
        )

    def test_header_names(self):
        assert SIGNATURE_HEADER == "X-PreFlight-Signature"
        assert TIMESTAMP_HEADER == "X-PreFlight-Timestamp"


class TestComparator:
    def test_gt(self):
        assert _comparator_breached("gt", 0.5, 0.3) is True
        assert _comparator_breached("gt", 0.2, 0.3) is False

    def test_lt(self):
        assert _comparator_breached("lt", 0.5, 0.8) is True
        assert _comparator_breached("lt", 0.9, 0.8) is False

    def test_eq(self):
        assert _comparator_breached("eq", 0.5, 0.5) is True
        assert _comparator_breached("eq", 0.5, 0.6) is False

    def test_unknown_comparator(self):
        assert _comparator_breached("zz", 0.5, 0.3) is False


class FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class FakeSession:
    """Minimal async session stub for evaluate_alerts.

    ``rules`` is what a SELECT AlertRule returns. ``added`` records db.add() calls.
    """

    def __init__(self, rules):
        self._rules = rules
        self.added = []

    async def execute(self, _stmt):
        return FakeResult(self._rules)

    def add(self, obj):
        self.added.append(obj)


class TestDefaultRules:
    def test_default_rules_encode_thresholds(self):
        by_metric = {r.metric: r for r in DEFAULT_ALERT_RULES}
        assert by_metric["drift"].comparator == "gt"
        assert by_metric["drift"].threshold == 0.30
        assert by_metric["drift"].severity == "warning"
        assert by_metric["reliability"].comparator == "lt"
        assert by_metric["reliability"].threshold == 0.80
        assert by_metric["unknown_provider"].severity == "info"


@pytest.mark.asyncio
class TestEvaluateAlertsDefaults:
    """When tenant has no rules, defaults apply (rule_id is None)."""

    async def test_high_drift_triggers_default(self):
        session = FakeSession(rules=[])
        tenant_id = uuid4()
        eval_id = uuid4()

        events = await evaluate_alerts(
            session,
            tenant_id,
            eval_id,
            drift_score=0.5,
            reliability_score=0.95,
            provider_known=True,
            vendor="nvidia",
        )

        assert len(events) == 1
        ev = events[0]
        assert ev.metric == "drift"
        assert ev.rule_id is None  # default rule
        assert ev.severity == "warning"
        assert ev.value == 0.5
        assert ev.threshold == 0.30
        assert session.added == events

    async def test_low_reliability_triggers_default(self):
        session = FakeSession(rules=[])
        events = await evaluate_alerts(
            session,
            uuid4(),
            uuid4(),
            drift_score=0.0,
            reliability_score=0.5,
            provider_known=True,
            vendor="nvidia",
        )
        metrics = {e.metric for e in events}
        assert "reliability" in metrics

    async def test_unknown_provider_triggers_info(self):
        session = FakeSession(rules=[])
        events = await evaluate_alerts(
            session,
            uuid4(),
            uuid4(),
            drift_score=0.0,
            reliability_score=0.99,
            provider_known=False,
            vendor="mystery",
        )
        unknown = [e for e in events if e.metric == "unknown_provider"]
        assert len(unknown) == 1
        assert unknown[0].severity == "info"
        assert "mystery" in unknown[0].message

    async def test_no_breach_no_events(self):
        session = FakeSession(rules=[])
        events = await evaluate_alerts(
            session,
            uuid4(),
            uuid4(),
            drift_score=0.0,
            reliability_score=0.99,
            provider_known=True,
            vendor="nvidia",
        )
        assert events == []


@pytest.mark.asyncio
class TestEvaluateAlertsTenantRules:
    """When tenant defines rules, those rules apply (rule_id set)."""

    async def test_tenant_rule_used_over_defaults(self):
        from src.models import AlertRule

        rule = AlertRule(
            tenant_id=uuid4(),
            name="strict drift",
            metric="drift",
            comparator="gt",
            threshold=0.10,
            severity="critical",
            enabled=True,
        )
        session = FakeSession(rules=[rule])

        events = await evaluate_alerts(
            session,
            uuid4(),
            uuid4(),
            drift_score=0.15,
            reliability_score=0.99,
            provider_known=True,
            vendor="nvidia",
        )

        assert len(events) == 1
        assert events[0].rule_id == rule.id
        assert events[0].severity == "critical"
        assert events[0].threshold == 0.10
