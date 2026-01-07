"""Template matching service using cosine similarity.

MVP implementation: Simple cosine similarity on structural features.
Future: LSH for O(1) lookup, tree edit distance refinement.
"""

import math
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import StructuralFeatures, Template, TemplateStatus


def _extract_feature_vector(features: StructuralFeatures) -> list[float]:
    """Extract a normalized feature vector from structural features.

    This creates a fixed-size vector suitable for similarity computation.
    """
    # Normalize counts to reasonable ranges
    max_elements = 1000
    max_tables = 50
    max_text_blocks = 200
    max_images = 100
    max_pages = 500
    max_columns = 10

    return [
        min(features.element_count / max_elements, 1.0),
        min(features.table_count / max_tables, 1.0),
        min(features.text_block_count / max_text_blocks, 1.0),
        min(features.image_count / max_images, 1.0),
        min(features.page_count / max_pages, 1.0),
        features.text_density,  # Already 0-1 normalized
        features.layout_complexity,  # Already 0-1 normalized
        min(features.column_count / max_columns, 1.0),
        1.0 if features.has_header else 0.0,
        1.0 if features.has_footer else 0.0,
    ]


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Returns a value between 0 (orthogonal) and 1 (identical).
    """
    if len(vec_a) != len(vec_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    magnitude_a = math.sqrt(sum(a * a for a in vec_a))
    magnitude_b = math.sqrt(sum(b * b for b in vec_b))

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


async def match_template(
    fingerprint: str,
    features: StructuralFeatures,
    tenant_id: UUID,
    db: AsyncSession,
) -> tuple[Template | None, float]:
    """Match document features to a known template.

    MVP algorithm:
    1. Query all active templates for tenant (RLS enforced)
    2. Compute cosine similarity with each template's features
    3. Return best match above threshold

    Args:
        fingerprint: SHA256 hash of structural features (for quick lookup).
        features: Structural features to match.
        tenant_id: Tenant ID (for logging, RLS handles filtering).
        db: Database session with tenant context.

    Returns:
        Tuple of (matched_template, confidence) or (None, 0.0) if no match.

    Thresholds:
        - >= 0.85: High confidence MATCH
        - 0.50-0.85: Needs REVIEW
        - < 0.50: NEW template
    """
    # Quick check: exact fingerprint match
    stmt = select(Template).where(
        Template.fingerprint == fingerprint,
        Template.status == TemplateStatus.ACTIVE,
    )
    result = await db.execute(stmt)
    exact_match = result.scalar_one_or_none()

    if exact_match:
        return exact_match, 1.0

    # Get all active templates for similarity search
    stmt = select(Template).where(Template.status == TemplateStatus.ACTIVE)
    result = await db.execute(stmt)
    templates = result.scalars().all()

    if not templates:
        return None, 0.0

    # Extract feature vector for input
    input_vector = _extract_feature_vector(features)

    # Find best match
    best_match: Template | None = None
    best_similarity = 0.0

    for template in templates:
        # Extract template's feature vector
        template_features = StructuralFeatures.model_validate(template.structural_features)
        template_vector = _extract_feature_vector(template_features)

        # Compute similarity
        similarity = _cosine_similarity(input_vector, template_vector)

        if similarity > best_similarity:
            best_similarity = similarity
            best_match = template

    # Return best match if above minimum threshold
    if best_similarity >= 0.50:
        return best_match, best_similarity

    return None, 0.0
