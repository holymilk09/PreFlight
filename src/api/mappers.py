"""Response mappers for API routes.

These functions convert database models to API response schemas,
centralizing the mapping logic to avoid duplication across endpoints.
"""

from uuid import UUID

from src.models import (
    CorrectionRule,
    Decision,
    Evaluation,
    EvaluationRecord,
    ExtractorMetadata,
    ExtractorProvider,
    Template,
    TemplateResponse,
)


def evaluation_to_record(
    evaluation: Evaluation,
    template_version_id: str | None = None,
) -> EvaluationRecord:
    """Convert an Evaluation model to an EvaluationRecord response.

    Args:
        evaluation: The database Evaluation model.
        template_version_id: Pre-computed template version string
            (format: "template_id:version"). If None, will not be included.

    Returns:
        EvaluationRecord suitable for API response.
    """
    return EvaluationRecord(
        id=evaluation.id,
        correlation_id=evaluation.correlation_id,
        document_hash=evaluation.document_hash,
        template_id=evaluation.template_id,
        template_version_id=template_version_id,
        decision=evaluation.decision,
        match_confidence=evaluation.match_confidence,
        drift_score=evaluation.drift_score,
        reliability_score=evaluation.reliability_score,
        correction_rules=[
            CorrectionRule(**r) for r in (evaluation.correction_rules or [])
        ],
        extractor_vendor=evaluation.extractor_vendor,
        extractor_model=evaluation.extractor_model,
        extractor_version=evaluation.extractor_version,
        extractor_confidence=evaluation.extractor_confidence,
        extractor_latency_ms=evaluation.extractor_latency_ms,
        validation_warnings=evaluation.validation_warnings or [],
        processing_time_ms=evaluation.processing_time_ms,
        created_at=evaluation.created_at,
    )


def template_to_response(
    template: Template,
    include_rules: bool = False,
) -> TemplateResponse:
    """Convert a Template model to a TemplateResponse.

    Args:
        template: The database Template model.
        include_rules: If True, parse and include correction_rules.
            If False, returns empty list (for list views).

    Returns:
        TemplateResponse suitable for API response.
    """
    correction_rules: list[CorrectionRule] = []
    if include_rules and template.correction_rules:
        correction_rules = [CorrectionRule(**r) for r in template.correction_rules]

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


def create_evaluation(
    evaluation_id: UUID,
    tenant_id: UUID,
    correlation_id: str,
    document_hash: str,
    template_id: UUID | None,
    decision: Decision,
    match_confidence: float | None,
    drift_score: float,
    reliability_score: float,
    correction_rules: list[CorrectionRule],
    extractor: ExtractorMetadata,
    provider: ExtractorProvider | None,
    validation_warnings: list[str],
    processing_time_ms: int,
) -> Evaluation:
    """Create an Evaluation model from evaluation components.

    This factory function centralizes the creation of Evaluation records,
    ensuring consistent field mapping from the evaluate endpoint.

    Args:
        evaluation_id: Pre-generated UUID7 for the evaluation.
        tenant_id: The tenant's UUID.
        correlation_id: Client-provided correlation ID.
        document_hash: Client's document hash (SHA256).
        template_id: Matched template's database UUID, or None if NEW.
        decision: The evaluation decision (MATCH, REVIEW, NEW, REJECT).
        match_confidence: Confidence score if template matched, else None.
        drift_score: Computed drift score (0.0 for NEW).
        reliability_score: Computed reliability score.
        correction_rules: List of correction rules to apply.
        extractor: Extractor metadata from the request.
        provider: Extractor provider config, or None if unknown.
        validation_warnings: List of validation warnings from safeguards.
        processing_time_ms: Total processing time in milliseconds.

    Returns:
        Evaluation model ready to be added to the database session.
    """
    return Evaluation(
        id=evaluation_id,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        document_hash=document_hash,
        template_id=template_id,
        decision=decision,
        match_confidence=match_confidence,
        drift_score=drift_score,
        reliability_score=reliability_score,
        correction_rules=[r.model_dump() for r in correction_rules],
        extractor_vendor=extractor.vendor,
        extractor_model=extractor.model,
        extractor_version=extractor.version,
        extractor_confidence=extractor.confidence,
        extractor_latency_ms=extractor.latency_ms,
        extractor_cost_usd=extractor.cost_usd,
        provider_id=provider.id if provider else None,
        validation_warnings=validation_warnings,
        processing_time_ms=processing_time_ms,
    )
