"""Alerting CRUD and delivery routes (alert rules, webhooks, alert events)."""

import ipaddress
import secrets
import socket
from urllib.parse import urlparse
from uuid import UUID

import structlog
from fastapi import APIRouter, Request, status
from sqlalchemy import func, select

from src.api.auth import ManageAlertsTenant, ReadTenant
from src.api.deps import TenantDbSession
from src.api.errors import (
    ALERT_RULE_NOT_FOUND,
    WEBHOOK_NOT_FOUND,
    ErrorCode,
    bad_request,
)
from src.api.mappers import (
    alert_event_to_record,
    alert_rule_to_response,
    webhook_to_created_response,
    webhook_to_response,
)
from src.audit import (
    log_alert_rule_created,
    log_alert_rule_deleted,
    log_webhook_created,
    log_webhook_deleted,
)
from src.models import (
    ALERT_COMPARATORS,
    ALERT_DELIVERY_STATUSES,
    ALERT_METRICS,
    ALERT_SEVERITIES,
    AlertEvent,
    AlertEventListResponse,
    AlertRule,
    AlertRuleCreate,
    AlertRuleResponse,
    WebhookCreate,
    WebhookCreatedResponse,
    WebhookEndpoint,
    WebhookResponse,
    WebhookTestResponse,
)
from src.services.alerting import _deliver_one

logger = structlog.get_logger()

router = APIRouter()

MAX_LIST_LIMIT = 100


def _request_id(request: Request) -> UUID | None:
    rid = getattr(request.state, "request_id", None)
    return UUID(rid) if rid else None


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Reject IPs that could be used for SSRF (loopback, private, link-local,
    reserved, multicast, unspecified). Link-local covers the cloud metadata
    endpoint (169.254.169.254)."""
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _validate_webhook_url(url: str) -> None:
    """Validate an outbound webhook URL, rejecting SSRF-prone targets.

    Enforces an http(s) scheme and blocks internal/reserved address space. When
    the host is a DNS name we resolve it best-effort and block if any resolved
    address is internal; resolution failures do not block creation (the host may
    be resolvable only from the delivery network). DNS-rebinding is a residual
    risk left for a future hardening pass.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise bad_request(ErrorCode.INVALID_REQUEST, "Webhook url must be an http(s) URL", url=url)
    host = parsed.hostname
    if not host:
        raise bad_request(ErrorCode.INVALID_REQUEST, "Webhook url must include a host", url=url)
    if host.lower() == "localhost" or host.lower().endswith(".localhost"):
        raise bad_request(ErrorCode.INVALID_REQUEST, "Webhook url host is not allowed", url=url)

    # Direct IP literal.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        if _is_blocked_ip(ip):
            raise bad_request(ErrorCode.INVALID_REQUEST, "Webhook url host is not allowed", url=url)
        return

    # DNS name: best-effort resolution; block if any resolved address is internal.
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return
    for info in infos:
        addr = info[4][0]
        try:
            resolved = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _is_blocked_ip(resolved):
            raise bad_request(
                ErrorCode.INVALID_REQUEST, "Webhook url resolves to a blocked address", url=url
            )


# -----------------------------------------------------------------------------
# Alert Rules
# -----------------------------------------------------------------------------


@router.post(
    "/alert-rules",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Alerting"],
    summary="Create an alert rule",
)
async def create_alert_rule(
    request: Request,
    body: AlertRuleCreate,
    tenant: ManageAlertsTenant,
    db: TenantDbSession,
) -> AlertRuleResponse:
    """Create a tenant alert rule.

    When a tenant has no rules, built-in default rules apply during evaluation.
    """
    if body.metric not in ALERT_METRICS:
        raise bad_request(
            ErrorCode.INVALID_REQUEST,
            f"Invalid metric. Must be one of: {', '.join(ALERT_METRICS)}",
            metric=body.metric,
        )
    if body.comparator not in ALERT_COMPARATORS:
        raise bad_request(
            ErrorCode.INVALID_REQUEST,
            f"Invalid comparator. Must be one of: {', '.join(ALERT_COMPARATORS)}",
            comparator=body.comparator,
        )
    if body.severity not in ALERT_SEVERITIES:
        raise bad_request(
            ErrorCode.INVALID_REQUEST,
            f"Invalid severity. Must be one of: {', '.join(ALERT_SEVERITIES)}",
            severity=body.severity,
        )
    if body.metric in ("drift", "reliability") and body.threshold is None:
        raise bad_request(
            ErrorCode.INVALID_REQUEST,
            f"threshold is required for metric '{body.metric}'",
            metric=body.metric,
        )

    rule = AlertRule(
        tenant_id=tenant.tenant_id,
        name=body.name,
        metric=body.metric,
        comparator=body.comparator,
        threshold=body.threshold,
        severity=body.severity,
        enabled=body.enabled,
    )
    db.add(rule)
    await db.commit()

    await log_alert_rule_created(
        tenant_id=tenant.tenant_id,
        rule_id=rule.id,
        name=rule.name,
        metric=rule.metric,
        actor_id=tenant.api_key_id,
        ip_address=_client_ip(request),
        request_id=_request_id(request),
    )

    return alert_rule_to_response(rule)


@router.get(
    "/alert-rules",
    response_model=list[AlertRuleResponse],
    tags=["Alerting"],
    summary="List alert rules",
)
async def list_alert_rules(
    tenant: ReadTenant,
    db: TenantDbSession,
    enabled: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AlertRuleResponse]:
    """List alert rules for the current tenant (RLS-scoped)."""
    stmt = select(AlertRule).order_by(AlertRule.created_at.desc())
    if enabled is not None:
        stmt = stmt.where(AlertRule.enabled == enabled)
    stmt = stmt.limit(min(limit, MAX_LIST_LIMIT)).offset(offset)
    result = await db.execute(stmt)
    return [alert_rule_to_response(r) for r in result.scalars().all()]


@router.delete(
    "/alert-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Alerting"],
    summary="Delete an alert rule",
)
async def delete_alert_rule(
    request: Request,
    rule_id: UUID,
    tenant: ManageAlertsTenant,
    db: TenantDbSession,
) -> None:
    """Delete an alert rule (RLS ensures it belongs to the tenant)."""
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise ALERT_RULE_NOT_FOUND

    await db.delete(rule)
    await db.commit()

    await log_alert_rule_deleted(
        tenant_id=tenant.tenant_id,
        rule_id=rule_id,
        actor_id=tenant.api_key_id,
        ip_address=_client_ip(request),
        request_id=_request_id(request),
    )


# -----------------------------------------------------------------------------
# Webhook Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/webhooks",
    response_model=WebhookCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Alerting"],
    summary="Create a webhook endpoint",
)
async def create_webhook(
    request: Request,
    body: WebhookCreate,
    tenant: ManageAlertsTenant,
    db: TenantDbSession,
) -> WebhookCreatedResponse:
    """Create a webhook endpoint. The signing secret is returned only once."""
    _validate_webhook_url(body.url)

    endpoint = WebhookEndpoint(
        tenant_id=tenant.tenant_id,
        url=body.url,
        secret=secrets.token_hex(32),
        description=body.description,
    )
    db.add(endpoint)
    await db.commit()

    await log_webhook_created(
        tenant_id=tenant.tenant_id,
        webhook_id=endpoint.id,
        url=endpoint.url,
        actor_id=tenant.api_key_id,
        ip_address=_client_ip(request),
        request_id=_request_id(request),
    )

    return webhook_to_created_response(endpoint)


@router.get(
    "/webhooks",
    response_model=list[WebhookResponse],
    tags=["Alerting"],
    summary="List webhook endpoints",
)
async def list_webhooks(
    tenant: ReadTenant,
    db: TenantDbSession,
    limit: int = 100,
    offset: int = 0,
) -> list[WebhookResponse]:
    """List webhook endpoints (secrets never included)."""
    stmt = (
        select(WebhookEndpoint)
        .order_by(WebhookEndpoint.created_at.desc())
        .limit(min(limit, MAX_LIST_LIMIT))
        .offset(offset)
    )
    result = await db.execute(stmt)
    return [webhook_to_response(e) for e in result.scalars().all()]


@router.delete(
    "/webhooks/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Alerting"],
    summary="Delete a webhook endpoint",
)
async def delete_webhook(
    request: Request,
    webhook_id: UUID,
    tenant: ManageAlertsTenant,
    db: TenantDbSession,
) -> None:
    """Delete a webhook endpoint (RLS ensures it belongs to the tenant)."""
    result = await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == webhook_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise WEBHOOK_NOT_FOUND

    await db.delete(endpoint)
    await db.commit()

    await log_webhook_deleted(
        tenant_id=tenant.tenant_id,
        webhook_id=webhook_id,
        actor_id=tenant.api_key_id,
        ip_address=_client_ip(request),
        request_id=_request_id(request),
    )


@router.post(
    "/webhooks/{webhook_id}/test",
    response_model=WebhookTestResponse,
    tags=["Alerting"],
    summary="Send a test webhook delivery",
)
async def test_webhook(
    webhook_id: UUID,
    tenant: ManageAlertsTenant,
    db: TenantDbSession,
) -> WebhookTestResponse:
    """Send a signed sample payload now and return the delivery result (sync)."""
    import httpx

    from src.config import settings
    from src.models import AlertEvent as _AlertEvent

    result = await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == webhook_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise WEBHOOK_NOT_FOUND

    # Build an ephemeral sample event (not persisted).
    sample = _AlertEvent(
        tenant_id=tenant.tenant_id,
        evaluation_id=None,
        rule_id=None,
        metric="drift",
        value=0.42,
        threshold=0.30,
        severity="info",
        message="PreFlight test webhook delivery",
        delivery_status="pending",
        delivery_attempts=0,
    )

    async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
        status_str, code, error = await _deliver_one(client, endpoint, sample)

    return WebhookTestResponse(
        webhook_id=webhook_id,
        delivery_status=status_str,
        status_code=code,
        error=error,
    )


# -----------------------------------------------------------------------------
# Alert Events
# -----------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=AlertEventListResponse,
    tags=["Alerting"],
    summary="List alert events",
)
async def list_alerts(
    tenant: ReadTenant,
    db: TenantDbSession,
    severity: str | None = None,
    metric: str | None = None,
    delivery_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> AlertEventListResponse:
    """List alert events for the current tenant with optional filters."""
    if severity is not None and severity not in ALERT_SEVERITIES:
        raise bad_request(
            ErrorCode.INVALID_REQUEST,
            f"Invalid severity. Must be one of: {', '.join(ALERT_SEVERITIES)}",
            severity=severity,
        )
    if metric is not None and metric not in ALERT_METRICS:
        raise bad_request(
            ErrorCode.INVALID_REQUEST,
            f"Invalid metric. Must be one of: {', '.join(ALERT_METRICS)}",
            metric=metric,
        )
    if delivery_status is not None and delivery_status not in ALERT_DELIVERY_STATUSES:
        raise bad_request(
            ErrorCode.INVALID_REQUEST,
            f"Invalid delivery_status. Must be one of: {', '.join(ALERT_DELIVERY_STATUSES)}",
            delivery_status=delivery_status,
        )

    stmt = select(AlertEvent).order_by(AlertEvent.created_at.desc())
    if severity is not None:
        stmt = stmt.where(AlertEvent.severity == severity)
    if metric is not None:
        stmt = stmt.where(AlertEvent.metric == metric)
    if delivery_status is not None:
        stmt = stmt.where(AlertEvent.delivery_status == delivery_status)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    capped_limit = min(limit, MAX_LIST_LIMIT)
    stmt = stmt.limit(capped_limit).offset(offset)
    result = await db.execute(stmt)
    events = result.scalars().all()

    return AlertEventListResponse(
        items=[alert_event_to_record(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(events)) < total,
    )
