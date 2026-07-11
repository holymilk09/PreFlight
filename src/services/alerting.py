"""Alerting engine: rule evaluation and webhook delivery.

Design:
- ``evaluate_alerts`` runs inside the evaluate request transaction. It loads the
  tenant's enabled rules (RLS-scoped via the passed session) or falls back to the
  built-in defaults, builds AlertEvent rows for each breach, and adds them to the
  session WITHOUT committing (the caller commits evaluation + events together).
- ``dispatch_webhooks`` runs as a fire-and-forget background task. It opens its
  OWN tenant-scoped session via ``get_tenant_session`` (so RLS applies), re-loads
  events by id, signs the outbound body, and POSTs to each enabled endpoint. It
  never raises and never reuses the request session or detached ORM objects.
"""

import hashlib
import hmac
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_tenant_session
from src.metrics import record_alert_event, record_webhook_delivery
from src.models import AlertEvent, AlertRule, WebhookEndpoint
from src.security import decrypt_secret

logger = structlog.get_logger()


# Signature/timestamp header names for outbound webhook deliveries.
SIGNATURE_HEADER = "X-PreFlight-Signature"
TIMESTAMP_HEADER = "X-PreFlight-Timestamp"


@dataclass(frozen=True)
class DefaultRule:
    """Built-in default alert rule (used when a tenant defines none)."""

    name: str
    metric: str  # "drift" | "reliability" | "unknown_provider"
    comparator: str  # "gt" | "lt" | "eq"
    threshold: float | None
    severity: str


# Built-in defaults encode the CLAUDE.md governance thresholds.
DEFAULT_ALERT_RULES: tuple[DefaultRule, ...] = (
    DefaultRule(
        name="High drift (default)",
        metric="drift",
        comparator="gt",
        threshold=0.30,
        severity="warning",
    ),
    DefaultRule(
        name="Low reliability (default)",
        metric="reliability",
        comparator="lt",
        threshold=0.80,
        severity="warning",
    ),
    DefaultRule(
        name="Unknown provider (default)",
        metric="unknown_provider",
        comparator="eq",
        threshold=None,
        severity="info",
    ),
)


def sign_payload(secret: str, body: bytes, timestamp: str) -> str:
    """Compute the outbound webhook signature header value.

    Signs ``"<timestamp>." + body`` with HMAC-SHA256 (timestamp binding
    mitigates replay). Returns the header value ``"sha256=<hex>"``.

    Args:
        secret: The endpoint's signing secret.
        body: The exact outbound body bytes that will be sent.
        timestamp: The value placed in the timestamp header.

    Returns:
        Signature header value, e.g. ``"sha256=ab12..."``.
    """
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def _comparator_breached(comparator: str, value: float, threshold: float) -> bool:
    """Return True if ``value <comparator> threshold`` indicates a breach."""
    if comparator == "gt":
        return value > threshold
    if comparator == "lt":
        return value < threshold
    if comparator == "eq":
        return value == threshold
    return False


def _build_event(
    *,
    tenant_id: UUID,
    evaluation_id: UUID | None,
    rule_id: UUID | None,
    metric: str,
    value: float | None,
    threshold: float | None,
    severity: str,
    message: str,
) -> AlertEvent:
    return AlertEvent(
        tenant_id=tenant_id,
        evaluation_id=evaluation_id,
        rule_id=rule_id,
        metric=metric,
        value=value,
        threshold=threshold,
        severity=severity,
        message=message,
        delivery_status="pending",
        delivery_attempts=0,
    )


def _evaluate_rule(
    *,
    metric: str,
    comparator: str,
    threshold: float | None,
    severity: str,
    rule_id: UUID | None,
    tenant_id: UUID,
    evaluation_id: UUID | None,
    drift_score: float | None,
    reliability_score: float | None,
    provider_known: bool,
    vendor: str | None,
) -> AlertEvent | None:
    """Evaluate a single rule (default or tenant). Returns an event on breach."""
    if metric == "unknown_provider":
        if not provider_known:
            return _build_event(
                tenant_id=tenant_id,
                evaluation_id=evaluation_id,
                rule_id=rule_id,
                metric=metric,
                value=None,
                threshold=None,
                severity=severity,
                message=f"Unknown extractor provider: {vendor or 'unknown'}",
            )
        return None

    if metric == "drift":
        value = drift_score
    elif metric == "reliability":
        value = reliability_score
    else:
        return None

    if value is None or threshold is None:
        return None

    if _comparator_breached(comparator, value, threshold):
        if metric == "drift":
            message = f"High drift detected: {value:.2f} (threshold {threshold:.2f})"
        else:
            message = f"Low reliability: {value:.2f} (threshold {threshold:.2f})"
        return _build_event(
            tenant_id=tenant_id,
            evaluation_id=evaluation_id,
            rule_id=rule_id,
            metric=metric,
            value=value,
            threshold=threshold,
            severity=severity,
            message=message,
        )
    return None


async def evaluate_alerts(
    db: AsyncSession,
    tenant_id: UUID,
    evaluation_id: UUID | None,
    drift_score: float | None,
    reliability_score: float | None,
    provider_known: bool,
    vendor: str | None,
) -> list[AlertEvent]:
    """Evaluate alert rules for an evaluation and stage AlertEvents on the session.

    Loads the tenant's enabled rules (RLS-scoped via ``db``). If the tenant has
    no rules, the built-in :data:`DEFAULT_ALERT_RULES` apply. Built-in rules are
    persisted with ``rule_id = None``.

    Does NOT commit — the caller commits the evaluation and events together so
    the AlertEvents are durable and tenant-correct.
    """
    events: list[AlertEvent] = []

    result = await db.execute(select(AlertRule).where(AlertRule.enabled == True))  # noqa: E712
    rules = list(result.scalars().all())

    if rules:
        for rule in rules:
            event = _evaluate_rule(
                metric=rule.metric,
                comparator=rule.comparator,
                threshold=rule.threshold,
                severity=rule.severity,
                rule_id=rule.id,
                tenant_id=tenant_id,
                evaluation_id=evaluation_id,
                drift_score=drift_score,
                reliability_score=reliability_score,
                provider_known=provider_known,
                vendor=vendor,
            )
            if event is not None:
                events.append(event)
    else:
        for default in DEFAULT_ALERT_RULES:
            event = _evaluate_rule(
                metric=default.metric,
                comparator=default.comparator,
                threshold=default.threshold,
                severity=default.severity,
                rule_id=None,
                tenant_id=tenant_id,
                evaluation_id=evaluation_id,
                drift_score=drift_score,
                reliability_score=reliability_score,
                provider_known=provider_known,
                vendor=vendor,
            )
            if event is not None:
                events.append(event)

    for event in events:
        db.add(event)
        record_alert_event(event.severity)

    return events


def _event_body(event: AlertEvent) -> dict:
    """Build the JSON-serializable webhook body for an alert event."""
    return {
        "event_id": str(event.id),
        "metric": event.metric,
        "value": event.value,
        "threshold": event.threshold,
        "severity": event.severity,
        "message": event.message,
        "evaluation_id": str(event.evaluation_id) if event.evaluation_id else None,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


async def _deliver_one(
    client: httpx.AsyncClient,
    endpoint: WebhookEndpoint,
    event: AlertEvent,
) -> tuple[str, int | None, str | None]:
    """Deliver a single event to a single endpoint. Returns (status, code, error).

    Single attempt; never raises.
    """
    import json

    body = json.dumps(_event_body(event), separators=(",", ":")).encode()
    timestamp = str(int(datetime.now(UTC).timestamp()))
    signature = sign_payload(decrypt_secret(endpoint.secret), body, timestamp)
    headers = {
        "Content-Type": "application/json",
        TIMESTAMP_HEADER: timestamp,
        SIGNATURE_HEADER: signature,
    }
    try:
        response = await client.post(endpoint.url, content=body, headers=headers)
        if 200 <= response.status_code < 300:
            return "sent", response.status_code, None
        return "failed", response.status_code, f"HTTP {response.status_code}"
    except Exception as exc:  # noqa: BLE001 - delivery must never raise
        return "failed", None, str(exc)[:500]


async def dispatch_webhooks(tenant_id: UUID, event_ids: Sequence[UUID]) -> None:
    """Background task: deliver alert events to the tenant's webhook endpoints.

    Opens its OWN tenant-scoped session (RLS-safe). Events are re-loaded by id
    inside this session — detached ORM objects are never passed across sessions.
    Each endpoint delivery is wrapped so a failure never escapes the task.
    """
    if not event_ids:
        return
    try:
        async with get_tenant_session(tenant_id) as session:
            ep_result = await session.execute(
                select(WebhookEndpoint).where(WebhookEndpoint.enabled == True)  # noqa: E712
            )
            endpoints = list(ep_result.scalars().all())

            ev_result = await session.execute(
                select(AlertEvent).where(AlertEvent.id.in_(list(event_ids)))
            )
            events = list(ev_result.scalars().all())

            if not endpoints:
                for event in events:
                    event.delivery_status = "no_endpoint"
                    session.add(event)
                    record_webhook_delivery("no_endpoint")
                await session.commit()
                return

            async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
                for event in events:
                    final_status = "failed"
                    last_error: str | None = None
                    for endpoint in endpoints:
                        status, _code, error = await _deliver_one(client, endpoint, event)
                        event.delivery_attempts += 1
                        record_webhook_delivery(status)
                        if status == "sent":
                            final_status = "sent"
                        else:
                            last_error = error
                    event.delivery_status = final_status
                    event.last_error = last_error if final_status != "sent" else None
                    session.add(event)
            await session.commit()
    except Exception:  # noqa: BLE001 - background task must never crash the loop
        logger.warning("webhook_dispatch_failed", tenant_id=str(tenant_id))
