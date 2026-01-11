"""API routes for the Control Plane."""

import hashlib
import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from uuid_extensions import uuid7

from src.api.auth import CurrentTenant
from src.api.deps import TenantDbSession
from src.audit import log_audit_event, log_evaluation_requested, log_template_created
from src.metrics import record_evaluation
from src.models import (
    AuditAction,
    CorrectionRule,
    Decision,
    DetailedHealthResponse,
    EvaluateRequest,
    EvaluateResponse,
    Evaluation,
    ServiceStatus,
    Template,
    TemplateCreate,
    TemplateResponse,
    TemplateStatus,
    TemplateStatusUpdate,
    TemplateUpdate,
)
from src.services.correction_rules import select_correction_rules
from src.services.drift_detector import compute_drift_score
from src.services.reliability_scorer import compute_reliability_score
from src.services.template_matcher import match_template

router = APIRouter()


# -----------------------------------------------------------------------------
# Evaluation Endpoint (Core)
# -----------------------------------------------------------------------------


@router.post(
    "/evaluate",
    response_model=EvaluateResponse,
    tags=["Evaluation"],
    summary="Evaluate document extraction metadata",
)
async def evaluate(
    request: Request,
    body: EvaluateRequest,
    tenant: CurrentTenant,
    db: TenantDbSession,
) -> EvaluateResponse:
    """Evaluate document extraction metadata and return governance decision.

    This is the core endpoint that:
    1. Matches the document to a known template
    2. Computes drift score
    3. Computes reliability score
    4. Returns correction rules to apply

    All operations are on metadata only - no document content is ever received.
    """
    start_time = time.perf_counter()

    # Match template
    matched_template, match_confidence = await match_template(
        fingerprint=body.layout_fingerprint,
        features=body.structural_features,
        tenant_id=tenant.tenant_id,
        db=db,
    )

    # Determine decision based on match confidence
    if matched_template is None or match_confidence < 0.50:
        decision = Decision.NEW
        drift_score = 0.0
        reliability_score = 0.0
        correction_rules = []
        template_version_id = None
    elif match_confidence < 0.85:
        decision = Decision.REVIEW
        drift_score = await compute_drift_score(
            template=matched_template,
            current_features=body.structural_features,
        )
        reliability_score = await compute_reliability_score(
            template=matched_template,
            extractor=body.extractor_metadata,
            drift_score=drift_score,
        )
        correction_rules = await select_correction_rules(
            template=matched_template,
            reliability_score=reliability_score,
        )
        template_version_id = f"{matched_template.template_id}:{matched_template.version}"
    else:
        decision = Decision.MATCH
        drift_score = await compute_drift_score(
            template=matched_template,
            current_features=body.structural_features,
        )
        reliability_score = await compute_reliability_score(
            template=matched_template,
            extractor=body.extractor_metadata,
            drift_score=drift_score,
        )
        correction_rules = await select_correction_rules(
            template=matched_template,
            reliability_score=reliability_score,
        )
        template_version_id = f"{matched_template.template_id}:{matched_template.version}"

    # Generate evaluation ID and replay hash
    evaluation_id = uuid7()
    replay_hash = hashlib.sha256(
        f"{evaluation_id}:{body.client_doc_hash}:{decision.value}".encode()
    ).hexdigest()

    # Calculate processing time
    processing_time_ms = int((time.perf_counter() - start_time) * 1000)

    # Store evaluation record
    evaluation = Evaluation(
        id=evaluation_id,
        tenant_id=tenant.tenant_id,
        correlation_id=body.client_correlation_id,
        document_hash=body.client_doc_hash,
        template_id=matched_template.id if matched_template else None,
        decision=decision,
        match_confidence=match_confidence if matched_template else None,
        drift_score=drift_score,
        reliability_score=reliability_score,
        correction_rules=[r.model_dump() for r in correction_rules],
        extractor_vendor=body.extractor_metadata.vendor,
        extractor_model=body.extractor_metadata.model,
        processing_time_ms=processing_time_ms,
    )
    db.add(evaluation)
    await db.commit()

    # Log audit event
    await log_evaluation_requested(
        tenant_id=tenant.tenant_id,
        evaluation_id=evaluation_id,
        correlation_id=body.client_correlation_id,
        decision=decision.value,
        processing_time_ms=processing_time_ms,
        ip_address=request.client.host if request.client else None,
        request_id=UUID(request.state.request_id) if hasattr(request.state, "request_id") else None,
    )

    # Record metrics
    record_evaluation(
        decision=decision.value,
        drift_score=drift_score,
        reliability_score=reliability_score,
        template_matched=matched_template is not None,
    )

    # Build alerts
    alerts = []
    if drift_score > 0.30:
        alerts.append(f"High drift detected: {drift_score:.2f}")
    if reliability_score < 0.80:
        alerts.append(f"Low reliability: {reliability_score:.2f}")

    return EvaluateResponse(
        decision=decision,
        template_version_id=template_version_id,
        drift_score=drift_score,
        reliability_score=reliability_score,
        correction_rules=correction_rules,
        replay_hash=replay_hash,
        evaluation_id=evaluation_id,
        alerts=alerts,
    )


# -----------------------------------------------------------------------------
# Template Endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/templates",
    response_model=list[TemplateResponse],
    tags=["Templates"],
    summary="List templates",
)
async def list_templates(
    tenant: CurrentTenant,
    db: TenantDbSession,
    status_filter: TemplateStatus | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[TemplateResponse]:
    """List all templates for the current tenant.

    RLS ensures only templates belonging to the authenticated tenant are returned.
    """
    stmt = select(Template).order_by(Template.created_at.desc())

    if status_filter:
        stmt = stmt.where(Template.status == status_filter)

    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    templates = result.scalars().all()

    return [
        TemplateResponse(
            id=t.id,
            template_id=t.template_id,
            version=t.version,
            fingerprint=t.fingerprint,
            baseline_reliability=t.baseline_reliability,
            status=t.status,
            created_at=t.created_at,
            correction_rules=[],  # Simplified for list view
        )
        for t in templates
    ]


@router.post(
    "/templates",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Templates"],
    summary="Register a new template",
)
async def create_template(
    request: Request,
    body: TemplateCreate,
    tenant: CurrentTenant,
    db: TenantDbSession,
) -> TemplateResponse:
    """Register a new document template.

    The template's structural features are used to match future documents.
    """
    # Compute fingerprint from structural features
    features_json = body.structural_features.model_dump_json()
    fingerprint = hashlib.sha256(features_json.encode()).hexdigest()

    # Check for duplicate
    stmt = select(Template).where(
        Template.template_id == body.template_id,
        Template.version == body.version,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template {body.template_id} version {body.version} already exists",
        )

    # Create template
    template = Template(
        tenant_id=tenant.tenant_id,
        template_id=body.template_id,
        version=body.version,
        fingerprint=fingerprint,
        structural_features=body.structural_features.model_dump(),
        baseline_reliability=body.baseline_reliability,
        correction_rules=[r.model_dump() for r in body.correction_rules],
        status=TemplateStatus.ACTIVE,
        created_by=tenant.api_key_id,
    )

    db.add(template)
    await db.commit()
    # Note: No refresh needed - all fields are populated from the constructor
    # Refresh would fail with RLS because SET LOCAL expires after commit

    # Log audit event
    await log_template_created(
        tenant_id=tenant.tenant_id,
        template_id=template.id,
        template_name=body.template_id,
        version=body.version,
        actor_id=tenant.api_key_id,
        ip_address=request.client.host if request.client else None,
        request_id=UUID(request.state.request_id) if hasattr(request.state, "request_id") else None,
    )

    return TemplateResponse(
        id=template.id,
        template_id=template.template_id,
        version=template.version,
        fingerprint=template.fingerprint,
        baseline_reliability=template.baseline_reliability,
        status=template.status,
        created_at=template.created_at,
        correction_rules=body.correction_rules,
    )


@router.get(
    "/templates/{template_id}",
    response_model=TemplateResponse,
    tags=["Templates"],
    summary="Get template details",
)
async def get_template(
    template_id: UUID,
    tenant: CurrentTenant,
    db: TenantDbSession,
) -> TemplateResponse:
    """Get details of a specific template.

    RLS ensures the template belongs to the authenticated tenant.
    """
    stmt = select(Template).where(Template.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return TemplateResponse(
        id=template.id,
        template_id=template.template_id,
        version=template.version,
        fingerprint=template.fingerprint,
        baseline_reliability=template.baseline_reliability,
        status=template.status,
        created_at=template.created_at,
        correction_rules=[],  # Could parse from template.correction_rules
    )


@router.put(
    "/templates/{template_id}",
    response_model=TemplateResponse,
    tags=["Templates"],
    summary="Update template",
)
async def update_template(
    request: Request,
    template_id: UUID,
    body: TemplateUpdate,
    tenant: CurrentTenant,
    db: TenantDbSession,
) -> TemplateResponse:
    """Update a template's configurable fields.

    Only baseline_reliability and correction_rules can be updated.
    RLS ensures the template belongs to the authenticated tenant.
    """
    stmt = select(Template).where(Template.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Track what fields were updated
    updated_fields: dict[str, object] = {}

    if body.baseline_reliability is not None:
        updated_fields["baseline_reliability"] = {
            "old": template.baseline_reliability,
            "new": body.baseline_reliability,
        }
        template.baseline_reliability = body.baseline_reliability

    if body.correction_rules is not None:
        updated_fields["correction_rules"] = {"count": len(body.correction_rules)}
        template.correction_rules = [r.model_dump() for r in body.correction_rules]

    if not updated_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    db.add(template)
    await db.commit()

    # Log audit event
    await log_audit_event(
        action=AuditAction.TEMPLATE_UPDATED,
        tenant_id=tenant.tenant_id,
        actor_id=tenant.api_key_id,
        resource_type="template",
        resource_id=template.id,
        details={
            "template_id": template.template_id,
            "version": template.version,
            "updated_fields": updated_fields,
        },
        ip_address=request.client.host if request.client else None,
        request_id=UUID(request.state.request_id) if hasattr(request.state, "request_id") else None,
    )

    # Parse correction rules from stored JSON
    correction_rules = [
        CorrectionRule(**r) for r in (template.correction_rules or [])
    ]

    return TemplateResponse(
        id=template.id,
        template_id=template.template_id,
        version=template.version,
        fingerprint=template.fingerprint,
        baseline_reliability=template.baseline_reliability,
        status=template.status,
        created_at=template.created_at,
        correction_rules=correction_rules,
    )


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Templates"],
    summary="Deprecate template",
)
async def delete_template(
    request: Request,
    template_id: UUID,
    tenant: CurrentTenant,
    db: TenantDbSession,
) -> None:
    """Deprecate a template (soft delete).

    The template is not actually deleted, but its status is changed to DEPRECATED.
    Deprecated templates are not used for matching new documents.
    RLS ensures the template belongs to the authenticated tenant.
    """
    stmt = select(Template).where(Template.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    if template.status == TemplateStatus.DEPRECATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template is already deprecated",
        )

    old_status = template.status
    template.status = TemplateStatus.DEPRECATED
    db.add(template)
    await db.commit()

    # Log audit event
    await log_audit_event(
        action=AuditAction.TEMPLATE_DEPRECATED,
        tenant_id=tenant.tenant_id,
        actor_id=tenant.api_key_id,
        resource_type="template",
        resource_id=template.id,
        details={
            "template_id": template.template_id,
            "version": template.version,
            "old_status": old_status.value,
        },
        ip_address=request.client.host if request.client else None,
        request_id=UUID(request.state.request_id) if hasattr(request.state, "request_id") else None,
    )


@router.patch(
    "/templates/{template_id}/status",
    response_model=TemplateResponse,
    tags=["Templates"],
    summary="Change template status",
)
async def update_template_status(
    request: Request,
    template_id: UUID,
    body: TemplateStatusUpdate,
    tenant: CurrentTenant,
    db: TenantDbSession,
) -> TemplateResponse:
    """Change a template's status.

    Valid transitions:
    - ACTIVE -> DEPRECATED, REVIEW
    - REVIEW -> ACTIVE, DEPRECATED
    - DEPRECATED -> ACTIVE (re-activation)

    RLS ensures the template belongs to the authenticated tenant.
    """
    stmt = select(Template).where(Template.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    if template.status == body.status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template is already in {body.status.value} status",
        )

    old_status = template.status
    template.status = body.status
    db.add(template)
    await db.commit()

    # Log audit event
    await log_audit_event(
        action=AuditAction.TEMPLATE_STATUS_CHANGED,
        tenant_id=tenant.tenant_id,
        actor_id=tenant.api_key_id,
        resource_type="template",
        resource_id=template.id,
        details={
            "template_id": template.template_id,
            "version": template.version,
            "old_status": old_status.value,
            "new_status": body.status.value,
        },
        ip_address=request.client.host if request.client else None,
        request_id=UUID(request.state.request_id) if hasattr(request.state, "request_id") else None,
    )

    # Parse correction rules from stored JSON
    correction_rules = [
        CorrectionRule(**r) for r in (template.correction_rules or [])
    ]

    return TemplateResponse(
        id=template.id,
        template_id=template.template_id,
        version=template.version,
        fingerprint=template.fingerprint,
        baseline_reliability=template.baseline_reliability,
        status=template.status,
        created_at=template.created_at,
        correction_rules=correction_rules,
    )


# -----------------------------------------------------------------------------
# Status Endpoint (Authenticated)
# -----------------------------------------------------------------------------


@router.get(
    "/status",
    response_model=DetailedHealthResponse,
    tags=["Health"],
    summary="Get detailed service status",
)
async def get_status(
    tenant: CurrentTenant,
    db: TenantDbSession,
) -> DetailedHealthResponse:
    """Get detailed service status (requires authentication).

    Unlike /health, this endpoint requires authentication and
    returns detailed status of all dependencies (database, Redis).
    """
    from sqlalchemy import text

    from src.services.rate_limiter import get_redis_client

    services: dict[str, ServiceStatus] = {}

    # Check PostgreSQL
    try:
        start = time.perf_counter()
        await db.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000
        services["database"] = ServiceStatus(healthy=True, latency_ms=round(latency, 2))
    except Exception:
        # Don't expose internal error details - log them separately
        services["database"] = ServiceStatus(healthy=False, error="Connection failed")

    # Check Redis
    try:
        start = time.perf_counter()
        redis = await get_redis_client()
        await redis.ping()
        latency = (time.perf_counter() - start) * 1000
        services["redis"] = ServiceStatus(healthy=True, latency_ms=round(latency, 2))
    except Exception:
        # Don't expose internal error details - log them separately
        services["redis"] = ServiceStatus(healthy=False, error="Connection failed")

    # Overall status
    all_healthy = all(s.healthy for s in services.values())

    return DetailedHealthResponse(
        status="healthy" if all_healthy else "degraded",
        version="0.1.0",
        services=services,
    )
