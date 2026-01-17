"""Temporal activities for document processing.

Activities are the building blocks of workflows - they perform the actual work.
Each activity wraps an existing service function to make it callable from
a Temporal workflow.
"""

from dataclasses import dataclass
from uuid import UUID

from temporalio import activity

from src.models import (
    ExtractorMetadata,
    StructuralFeatures,
    Template,
)

# -----------------------------------------------------------------------------
# Activity Input/Output Data Classes
# -----------------------------------------------------------------------------


@dataclass
class MatchTemplateInput:
    """Input for template matching activity."""

    fingerprint: str
    features: dict  # StructuralFeatures as dict for serialization
    tenant_id: str  # UUID as string for serialization


@dataclass
class MatchTemplateOutput:
    """Output from template matching activity."""

    matched: bool
    template_id: str | None  # UUID as string
    template_data: dict | None  # Full template data for downstream activities
    confidence: float


@dataclass
class ComputeDriftInput:
    """Input for drift computation activity."""

    template_data: dict  # Template as dict
    current_features: dict  # StructuralFeatures as dict


@dataclass
class ComputeReliabilityInput:
    """Input for reliability computation activity."""

    template_data: dict  # Template as dict
    extractor: dict  # ExtractorMetadata as dict
    drift_score: float


@dataclass
class SelectRulesInput:
    """Input for correction rules selection activity."""

    template_data: dict  # Template as dict
    reliability_score: float


# -----------------------------------------------------------------------------
# Activities
# -----------------------------------------------------------------------------


@activity.defn
async def match_template_activity(input: MatchTemplateInput) -> MatchTemplateOutput:
    """Match document features to a known template.

    This activity wraps the template_matcher service, providing
    database access within the activity context.
    """
    from sqlalchemy import select, text

    from src.db import async_session_maker
    from src.models import Template, TemplateStatus
    from src.services.template_matcher import _cosine_similarity, _extract_feature_vector

    features = StructuralFeatures.model_validate(input.features)
    tenant_id = UUID(input.tenant_id)

    async with async_session_maker() as db:
        # Set tenant context for RLS using parameterized set_config()
        await db.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)}
        )

        # Quick check: exact fingerprint match
        stmt = select(Template).where(
            Template.fingerprint == input.fingerprint,
            Template.status == TemplateStatus.ACTIVE,
        )
        result = await db.execute(stmt)
        exact_match = result.scalar_one_or_none()

        if exact_match:
            return MatchTemplateOutput(
                matched=True,
                template_id=str(exact_match.id),
                template_data=_template_to_dict(exact_match),
                confidence=1.0,
            )

        # Get all active templates for similarity search
        stmt = select(Template).where(Template.status == TemplateStatus.ACTIVE)
        result = await db.execute(stmt)
        templates = result.scalars().all()

        if not templates:
            return MatchTemplateOutput(
                matched=False,
                template_id=None,
                template_data=None,
                confidence=0.0,
            )

        # Extract feature vector for input
        input_vector = _extract_feature_vector(features)

        # Find best match
        best_match: Template | None = None
        best_similarity = 0.0

        for template in templates:
            template_features = StructuralFeatures.model_validate(template.structural_features)
            template_vector = _extract_feature_vector(template_features)
            similarity = _cosine_similarity(input_vector, template_vector)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = template

        # Return best match if above minimum threshold
        if best_similarity >= 0.50 and best_match:
            return MatchTemplateOutput(
                matched=True,
                template_id=str(best_match.id),
                template_data=_template_to_dict(best_match),
                confidence=best_similarity,
            )

        return MatchTemplateOutput(
            matched=False,
            template_id=None,
            template_data=None,
            confidence=0.0,
        )


@activity.defn
async def compute_drift_activity(input: ComputeDriftInput) -> float:
    """Compute drift score comparing current features to template baseline.

    This activity wraps the drift_detector service.
    """
    from src.services.drift_detector import compute_drift_score

    template = _dict_to_template(input.template_data)
    features = StructuralFeatures.model_validate(input.current_features)

    return await compute_drift_score(template, features)


@activity.defn
async def compute_reliability_activity(input: ComputeReliabilityInput) -> float:
    """Compute reliability score for the extraction.

    This activity wraps the reliability_scorer service.
    """
    from src.services.reliability_scorer import compute_reliability_score

    template = _dict_to_template(input.template_data)
    extractor = ExtractorMetadata.model_validate(input.extractor)

    return await compute_reliability_score(template, extractor, input.drift_score)


@activity.defn
async def select_rules_activity(input: SelectRulesInput) -> list[dict]:
    """Select correction rules based on template and reliability.

    This activity wraps the correction_rules service.
    Returns rules as dicts for serialization.
    """
    from src.services.correction_rules import select_correction_rules

    template = _dict_to_template(input.template_data)
    rules = await select_correction_rules(template, input.reliability_score)

    return [rule.model_dump() for rule in rules]


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def _template_to_dict(template: Template) -> dict:
    """Convert Template model to dict for serialization."""
    return {
        "id": str(template.id),
        "tenant_id": str(template.tenant_id),
        "template_id": template.template_id,
        "version": template.version,
        "fingerprint": template.fingerprint,
        "structural_features": template.structural_features,
        "baseline_reliability": template.baseline_reliability,
        "correction_rules": template.correction_rules,
        "status": template.status.value,
        "created_at": template.created_at.isoformat() if template.created_at else None,
    }


def _dict_to_template(data: dict) -> Template:
    """Convert dict back to Template model for service calls."""
    from src.models import TemplateStatus

    return Template(
        id=UUID(data["id"]),
        tenant_id=UUID(data["tenant_id"]),
        template_id=data["template_id"],
        version=data["version"],
        fingerprint=data["fingerprint"],
        structural_features=data["structural_features"],
        baseline_reliability=data["baseline_reliability"],
        correction_rules=data["correction_rules"],
        status=TemplateStatus(data["status"]),
    )
