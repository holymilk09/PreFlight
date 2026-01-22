"""API routes for the Control Plane."""

import hashlib
import json
import time
from uuid import UUID

import structlog
from fastapi import APIRouter, Request, status
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_extensions import uuid7

from src.api.auth import CurrentTenant
from src.api.deps import TenantDbSession
from src.api.errors import (
    EVALUATION_NOT_FOUND,
    NO_FIELDS_TO_UPDATE,
    TEMPLATE_NOT_FOUND,
    ErrorCode,
    bad_request,
    conflict,
)
from src.api.mappers import create_evaluation, evaluation_to_record, template_to_response
from src.audit import log_audit_event, log_evaluation_requested, log_template_created
from src.metrics import record_evaluation
from src.models import (
    AuditAction,
    Decision,
    DetailedHealthResponse,
    EvaluateRequest,
    EvaluateResponse,
    Evaluation,
    EvaluationListResponse,
    EvaluationRecord,
    ExtractorProvider,
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
from src.services.rate_limiter import get_redis_client
from src.services.reliability_scorer import compute_reliability_score
from src.services.safeguard_engine import safeguard_engine
from src.services.template_matcher import match_template

logger = structlog.get_logger()

# Provider cache TTL (5 minutes)
PROVIDER_CACHE_TTL_SECONDS = 300

router = APIRouter()


async def get_cached_provider(
    vendor: str,
    db: AsyncSession,
) -> ExtractorProvider | None:
    """Get ExtractorProvider with Redis caching.

    Cache key: provider:{vendor_lower}
    TTL: 5 minutes

    Falls back to database query on cache miss or Redis error.
    """
    vendor_lower = vendor.lower()
    cache_key = f"provider:{vendor_lower}"

    # Try cache first
    try:
        redis = await get_redis_client()
        cached = await redis.get(cache_key)
        # Check for valid cached data (must be str or bytes, not None or mock objects)
        if cached and isinstance(cached, (str, bytes)):
            data = json.loads(cached)
            logger.debug("provider_cache_hit", vendor=vendor_lower)
            return ExtractorProvider(
                id=UUID(data["id"]),
                vendor=data["vendor"],
                display_name=data["display_name"],
                confidence_multiplier=data["confidence_multiplier"],
                drift_sensitivity=data["drift_sensitivity"],
                supported_element_types=data["supported_element_types"],
                typical_latency_ms=data["typical_latency_ms"],
                is_active=data["is_active"],
                is_known=data["is_known"],
            )
    except (
        RedisError,
        ConnectionError,
        json.JSONDecodeError,
        TypeError,
        RuntimeError,
        OSError,
    ) as e:
        # Fall through to database query on any Redis error
        logger.debug("provider_cache_skip", error=str(e), vendor=vendor_lower)

    # Cache miss or error - query database
    stmt = select(ExtractorProvider).where(
        func.lower(ExtractorProvider.vendor) == vendor_lower,
        ExtractorProvider.is_active == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    provider = result.scalar_one_or_none()

    # Populate cache if provider found
    if provider:
        try:
            redis = await get_redis_client()
            cache_data = json.dumps(
                {
                    "id": str(provider.id),
                    "vendor": provider.vendor,
                    "display_name": provider.display_name,
                    "confidence_multiplier": provider.confidence_multiplier,
                    "drift_sensitivity": provider.drift_sensitivity,
                    "supported_element_types": provider.supported_element_types,
                    "typical_latency_ms": provider.typical_latency_ms,
                    "is_active": provider.is_active,
                    "is_known": provider.is_known,
                }
            )
            await redis.setex(cache_key, PROVIDER_CACHE_TTL_SECONDS, cache_data)
            logger.debug("provider_cache_set", vendor=vendor_lower)
        except (RedisError, ConnectionError, RuntimeError, OSError) as e:
            # Cache set failures are non-critical
            logger.debug("provider_cache_set_skip", error=str(e), vendor=vendor_lower)

    return provider


async def get_template_or_404(template_id: UUID, db: AsyncSession) -> Template:
    """Fetch template by ID or raise TEMPLATE_NOT_FOUND.

    Args:
        template_id: The UUID of the template to fetch.
        db: Database session with RLS context set.

    Returns:
        The Template if found.

    Raises:
        HTTPException: TEMPLATE_NOT_FOUND if template doesn't exist.
    """
    stmt = select(Template).where(Template.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()

    if not template:
        raise TEMPLATE_NOT_FOUND

    return template


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
    1. Looks up provider configuration for calibration
    2. Runs safeguard validation on the request
    3. Matches the document to a known template
    4. Computes drift score with provider sensitivity
    5. Computes reliability score with provider calibration
    6. Returns correction rules to apply

    All operations are on metadata only - no document content is ever received.
    """
    start_time = time.perf_counter()
    alerts: list[str] = []

    # Look up provider configuration (cached)
    provider = await get_cached_provider(body.extractor_metadata.vendor, db)

    # Run safeguard validation
    validation_warnings = safeguard_engine.validate_request(
        features=body.structural_features,
        extractor=body.extractor_metadata,
        provider=provider,
    )
    alerts.extend(validation_warnings)

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
        reliability_score = await compute_reliability_score(
            template=None,
            extractor=body.extractor_metadata,
            drift_score=0.0,
            provider=provider,
        )
        correction_rules = []
        template_version_id = None
    else:
        # REVIEW (0.50-0.85) or MATCH (>=0.85) - same computation, different decision
        decision = Decision.REVIEW if match_confidence < 0.85 else Decision.MATCH
        drift_score = await compute_drift_score(
            template=matched_template,
            current_features=body.structural_features,
        )
        reliability_score = await compute_reliability_score(
            template=matched_template,
            extractor=body.extractor_metadata,
            drift_score=drift_score,
            provider=provider,
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

    # Store evaluation record with enhanced extractor tracking
    evaluation = create_evaluation(
        evaluation_id=evaluation_id,
        tenant_id=tenant.tenant_id,
        correlation_id=body.client_correlation_id,
        document_hash=body.client_doc_hash,
        template_id=matched_template.id if matched_template else None,
        decision=decision,
        match_confidence=match_confidence if matched_template else None,
        drift_score=drift_score,
        reliability_score=reliability_score,
        correction_rules=correction_rules,
        extractor=body.extractor_metadata,
        provider=provider,
        validation_warnings=validation_warnings,
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

    # Add drift/reliability alerts (validation warnings already in alerts)
    if drift_score > 0.30:
        alerts.append(f"High drift detected: {drift_score:.2f}")
    if reliability_score < 0.80 and matched_template is not None:
        alerts.append(f"Low reliability: {reliability_score:.2f}")
    if provider is None:
        alerts.append(f"Unknown provider: {body.extractor_metadata.vendor}")

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
# Evaluation History Endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/evaluations",
    response_model=EvaluationListResponse,
    tags=["Evaluations"],
    summary="List evaluation history",
)
async def list_evaluations(
    tenant: CurrentTenant,
    db: TenantDbSession,
    decision_filter: Decision | None = None,
    correlation_id: str | None = None,
    template_id: UUID | None = None,
    min_reliability: float | None = None,
    max_drift: float | None = None,
    limit: int = 100,
    offset: int = 0,
) -> EvaluationListResponse:
    """List evaluation history for the current tenant.

    Supports filtering by:
    - decision: MATCH, REVIEW, NEW, REJECT
    - correlation_id: Client's correlation ID (exact match)
    - template_id: Filter by matched template
    - min_reliability: Minimum reliability score
    - max_drift: Maximum drift score

    Results are ordered by created_at descending (newest first).
    RLS ensures only evaluations belonging to the authenticated tenant are returned.
    """
    # Build base query
    stmt = select(Evaluation).order_by(Evaluation.created_at.desc())

    # Apply filters
    if decision_filter:
        stmt = stmt.where(Evaluation.decision == decision_filter)

    if correlation_id:
        stmt = stmt.where(Evaluation.correlation_id == correlation_id)

    if template_id:
        stmt = stmt.where(Evaluation.template_id == template_id)

    if min_reliability is not None:
        stmt = stmt.where(Evaluation.reliability_score >= min_reliability)

    if max_drift is not None:
        stmt = stmt.where(Evaluation.drift_score <= max_drift)

    # Count total (for pagination)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Apply pagination
    stmt = stmt.limit(min(limit, 100)).offset(offset)

    result = await db.execute(stmt)
    evaluations = result.scalars().all()

    # Batch fetch all templates to avoid N+1 query
    template_ids = [e.template_id for e in evaluations if e.template_id]
    templates_by_id = {}
    if template_ids:
        template_stmt = select(Template).where(Template.id.in_(template_ids))
        template_result = await db.execute(template_stmt)
        templates_by_id = {t.id: t for t in template_result.scalars().all()}

    # Build response with template version info
    evaluation_records = []
    for e in evaluations:
        # Get template version if template exists
        template_version_id = None
        if e.template_id and e.template_id in templates_by_id:
            template = templates_by_id[e.template_id]
            template_version_id = f"{template.template_id}:{template.version}"

        evaluation_records.append(evaluation_to_record(e, template_version_id))

    return EvaluationListResponse(
        evaluations=evaluation_records,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(evaluations)) < total,
    )


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=EvaluationRecord,
    tags=["Evaluations"],
    summary="Get evaluation details",
)
async def get_evaluation(
    evaluation_id: UUID,
    tenant: CurrentTenant,
    db: TenantDbSession,
) -> EvaluationRecord:
    """Get details of a specific evaluation.

    RLS ensures the evaluation belongs to the authenticated tenant.
    """
    stmt = select(Evaluation).where(Evaluation.id == evaluation_id)
    result = await db.execute(stmt)
    evaluation = result.scalar_one_or_none()

    if not evaluation:
        raise EVALUATION_NOT_FOUND

    # Get template version if template exists
    template_version_id = None
    if evaluation.template_id:
        template_stmt = select(Template).where(Template.id == evaluation.template_id)
        template_result = await db.execute(template_stmt)
        template = template_result.scalar_one_or_none()
        if template:
            template_version_id = f"{template.template_id}:{template.version}"

    return evaluation_to_record(evaluation, template_version_id)


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

    return [template_to_response(t, include_rules=False) for t in templates]


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
        raise conflict(
            ErrorCode.TEMPLATE_ALREADY_EXISTS,
            f"Template {body.template_id} version {body.version} already exists",
            template_id=body.template_id,
            version=body.version,
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
    template = await get_template_or_404(template_id, db)

    return template_to_response(template, include_rules=False)


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
    template = await get_template_or_404(template_id, db)

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
        raise NO_FIELDS_TO_UPDATE

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

    return template_to_response(template, include_rules=True)


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
    template = await get_template_or_404(template_id, db)

    if template.status == TemplateStatus.DEPRECATED:
        raise bad_request(
            ErrorCode.TEMPLATE_ALREADY_DEPRECATED,
            "Template is already deprecated",
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
    template = await get_template_or_404(template_id, db)

    if template.status == body.status:
        raise bad_request(
            ErrorCode.INVALID_REQUEST,
            f"Template is already in {body.status.value} status",
            current_status=body.status.value,
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

    return template_to_response(template, include_rules=True)


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
