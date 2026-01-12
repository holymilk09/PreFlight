"""Audit logging for security-sensitive operations."""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import async_session_maker
from src.models import AuditAction, AuditLog
from src.security import sanitize_for_log

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


async def log_audit_event(
    action: AuditAction | str,
    tenant_id: UUID | None = None,
    actor_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    request_id: UUID | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Log an audit event to both database and structured log.

    This function:
    1. Sanitizes any sensitive data in details
    2. Writes to audit_log table (append-only, no RLS)
    3. Writes to structured log for external aggregation

    Args:
        action: The type of action being audited.
        tenant_id: Optional tenant context.
        actor_id: Optional actor (user/api key) that performed action.
        resource_type: Type of resource affected (e.g., "template", "api_key").
        resource_id: ID of the affected resource.
        details: Additional context (will be sanitized).
        ip_address: Client IP address.
        request_id: Request ID for tracing.
        session: Optional existing session (creates new one if None).
    """
    # Sanitize details before logging
    safe_details = sanitize_for_log(details) if details else None

    # Get action string value
    action_str = action.value if isinstance(action, AuditAction) else action

    # Create audit log entry
    audit_entry = AuditLog(
        timestamp=datetime.utcnow(),
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action_str,
        resource_type=resource_type,
        resource_id=resource_id,
        details=safe_details,
        ip_address=ip_address,
        request_id=request_id,
    )

    # Write to database
    if session:
        session.add(audit_entry)
        # Don't commit - let the caller manage the transaction
    else:
        async with async_session_maker() as new_session:
            new_session.add(audit_entry)
            await new_session.commit()

    # Write to structured log
    log_context = {
        "audit_action": action_str,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "actor_id": str(actor_id) if actor_id else None,
        "resource_type": resource_type,
        "resource_id": str(resource_id) if resource_id else None,
        "ip_address": ip_address,
        "request_id": str(request_id) if request_id else None,
    }

    if safe_details:
        log_context["details"] = safe_details

    # Log at appropriate level based on action type
    if action_str in (AuditAction.AUTH_FAILED.value, AuditAction.RATE_LIMIT_EXCEEDED.value):
        logger.warning("audit_event", **log_context)
    else:
        logger.info("audit_event", **log_context)


async def log_api_key_created(
    tenant_id: UUID,
    api_key_id: UUID,
    key_name: str | None,
    ip_address: str | None = None,
    request_id: UUID | None = None,
) -> None:
    """Log API key creation event."""
    await log_audit_event(
        action=AuditAction.API_KEY_CREATED,
        tenant_id=tenant_id,
        resource_type="api_key",
        resource_id=api_key_id,
        details={"key_name": key_name},
        ip_address=ip_address,
        request_id=request_id,
    )


async def log_api_key_revoked(
    tenant_id: UUID,
    api_key_id: UUID,
    actor_id: UUID | None = None,
    ip_address: str | None = None,
    request_id: UUID | None = None,
) -> None:
    """Log API key revocation event."""
    await log_audit_event(
        action=AuditAction.API_KEY_REVOKED,
        tenant_id=tenant_id,
        actor_id=actor_id,
        resource_type="api_key",
        resource_id=api_key_id,
        ip_address=ip_address,
        request_id=request_id,
    )


async def log_template_created(
    tenant_id: UUID,
    template_id: UUID,
    template_name: str,
    version: str,
    actor_id: UUID | None = None,
    ip_address: str | None = None,
    request_id: UUID | None = None,
) -> None:
    """Log template creation event."""
    await log_audit_event(
        action=AuditAction.TEMPLATE_CREATED,
        tenant_id=tenant_id,
        actor_id=actor_id,
        resource_type="template",
        resource_id=template_id,
        details={"template_name": template_name, "version": version},
        ip_address=ip_address,
        request_id=request_id,
    )


async def log_evaluation_requested(
    tenant_id: UUID,
    evaluation_id: UUID,
    correlation_id: str,
    decision: str,
    processing_time_ms: int,
    ip_address: str | None = None,
    request_id: UUID | None = None,
) -> None:
    """Log evaluation request event (metadata only, no document content)."""
    await log_audit_event(
        action=AuditAction.EVALUATION_REQUESTED,
        tenant_id=tenant_id,
        resource_type="evaluation",
        resource_id=evaluation_id,
        details={
            "correlation_id": correlation_id,
            "decision": decision,
            "processing_time_ms": processing_time_ms,
        },
        ip_address=ip_address,
        request_id=request_id,
    )


async def log_rate_limit_exceeded(
    tenant_id: UUID | None,
    api_key_id: UUID | None,
    limit: int,
    current: int,
    ip_address: str | None = None,
    request_id: UUID | None = None,
) -> None:
    """Log rate limit exceeded event."""
    await log_audit_event(
        action=AuditAction.RATE_LIMIT_EXCEEDED,
        tenant_id=tenant_id,
        actor_id=api_key_id,
        details={"limit": limit, "current": current},
        ip_address=ip_address,
        request_id=request_id,
    )
