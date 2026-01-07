"""API routes for the Control Plane."""

import hashlib
import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from uuid7 import uuid7

from src.api.auth import CurrentTenant
from src.api.deps import TenantDbSession
from src.audit import log_evaluation_requested, log_template_created
from src.models import (
    Decision,
    Evaluation,
    EvaluateRequest,
    EvaluateResponse,
    HealthResponse,
    Template,
    TemplateCreate,
    TemplateResponse,
    TemplateStatus,
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
    await db.refresh(template)

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


# -----------------------------------------------------------------------------
# Status Endpoint (Authenticated)
# -----------------------------------------------------------------------------


@router.get(
    "/status",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Get detailed service status",
)
async def get_status(
    tenant: CurrentTenant,
) -> HealthResponse:
    """Get detailed service status (requires authentication).

    Unlike /health, this endpoint requires authentication and
    returns more detailed status information.
    """
    return HealthResponse(
        status="healthy",
        version="0.1.0",
    )
