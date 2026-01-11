"""Template matching service using LSH and cosine similarity.

Uses LSH (Locality-Sensitive Hashing) for O(1) candidate retrieval,
then refines with cosine similarity for accurate ranking.
Falls back to O(n) scan if LSH is unavailable.
"""

import math
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import StructuralFeatures, Template, TemplateStatus

logger = structlog.get_logger()


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

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
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
    use_lsh: bool = True,
) -> tuple[Template | None, float]:
    """Match document features to a known template.

    Algorithm:
    1. Quick check: exact fingerprint match (O(1) with index)
    2. LSH lookup for candidates (O(1) if available)
    3. Cosine similarity refinement on candidates
    4. Fallback to O(n) scan if LSH unavailable

    Args:
        fingerprint: SHA256 hash of structural features (for quick lookup).
        features: Structural features to match.
        tenant_id: Tenant ID (for logging, RLS handles filtering).
        db: Database session with tenant context.
        use_lsh: Whether to use LSH for candidate retrieval (default True).

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

    # Try LSH for O(1) candidate retrieval
    if use_lsh:
        lsh_result = await _match_with_lsh(features, tenant_id, db)
        if lsh_result is not None:
            return lsh_result

    # Fallback: O(n) scan of all templates
    return await _match_with_scan(features, db)


async def _match_with_lsh(
    features: StructuralFeatures,
    tenant_id: UUID,
    db: AsyncSession,
) -> tuple[Template | None, float] | None:
    """Attempt to match using LSH index.

    Returns None if LSH is unavailable or has no candidates (triggers fallback).
    Returns (template, score) or (None, 0.0) if LSH worked but found no match.
    """
    try:
        from src.services.lsh_index import get_lsh_index

        lsh = await get_lsh_index()
        if not lsh.available:
            logger.debug("lsh_unavailable_fallback_to_scan")
            return None

        # Get candidates from LSH
        candidates = await lsh.query(features, k=10, tenant_id=tenant_id)

        if not candidates:
            # No candidates in LSH - fall back to scan
            # (LSH index might be empty or not yet populated)
            logger.debug("lsh_no_candidates_fallback_to_scan")
            return None

        # Load candidate templates from database
        candidate_ids = [c.template_id for c in candidates]
        stmt = select(Template).where(
            Template.id.in_(candidate_ids),
            Template.status == TemplateStatus.ACTIVE,
        )
        result = await db.execute(stmt)
        templates = {t.id: t for t in result.scalars().all()}

        if not templates:
            return None, 0.0

        # Refine with cosine similarity
        input_vector = _extract_feature_vector(features)
        best_match: Template | None = None
        best_similarity = 0.0

        for candidate in candidates:
            template = templates.get(candidate.template_id)
            if not template:
                continue

            template_features = StructuralFeatures.model_validate(template.structural_features)
            template_vector = _extract_feature_vector(template_features)
            similarity = _cosine_similarity(input_vector, template_vector)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = template

        if best_similarity >= 0.50:
            logger.debug(
                "lsh_match_found",
                template_id=str(best_match.id) if best_match else None,
                similarity=best_similarity,
                num_candidates=len(candidates),
            )
            return best_match, best_similarity

        return None, 0.0

    except Exception as e:
        logger.warning("lsh_match_failed", error=str(e))
        return None  # Signal to fall back to scan


async def _match_with_scan(
    features: StructuralFeatures,
    db: AsyncSession,
) -> tuple[Template | None, float]:
    """Match using O(n) scan of all templates.

    Fallback when LSH is unavailable.
    """
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


async def index_template(
    template_id: UUID,
    tenant_id: UUID,
    features: StructuralFeatures,
) -> bool:
    """Add a template to the LSH index.

    Should be called when a template is created or updated.

    Args:
        template_id: Template UUID
        tenant_id: Tenant UUID
        features: Template structural features

    Returns:
        True if indexed successfully, False if LSH unavailable
    """
    try:
        from src.services.lsh_index import get_lsh_index

        lsh = await get_lsh_index()
        if lsh.available:
            return await lsh.add_template(template_id, tenant_id, features)
        return False
    except Exception as e:
        logger.warning("lsh_index_template_failed", error=str(e))
        return False


async def unindex_template(template_id: UUID) -> bool:
    """Remove a template from the LSH index.

    Should be called when a template is deleted or deactivated.

    Args:
        template_id: Template UUID

    Returns:
        True if removed successfully
    """
    try:
        from src.services.lsh_index import get_lsh_index

        lsh = await get_lsh_index()
        if lsh.available:
            return await lsh.remove_template(template_id)
        return False
    except Exception as e:
        logger.warning("lsh_unindex_template_failed", error=str(e))
        return False
