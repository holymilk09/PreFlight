"""Template matching service using LSH and cosine similarity.

Uses LSH (Locality-Sensitive Hashing) for O(1) candidate retrieval,
then refines with cosine similarity for accurate ranking.
Falls back to O(n) scan if LSH is unavailable.
"""

import math
from uuid import UUID

import structlog
from pydantic import ValidationError
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

    NOTE: no longer the production matching metric. On the ground-truth
    harness (tests/validation/test_decision_quality.py) cosine over these
    all-non-negative feature vectors is nearly degenerate: a never-registered
    document's best similarity against the pool averaged 0.995, making
    novelty detection a coin flip. Kept as a utility for analysis/tests.
    """
    if len(vec_a) != len(vec_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    magnitude_a = math.sqrt(sum(a * a for a in vec_a))
    magnitude_b = math.sqrt(sum(b * b for b in vec_b))

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


def _feature_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Gower-style similarity: 1 - mean absolute difference over [0,1] dims.

    Production matching metric. Chosen over cosine on the ground-truth
    harness (tests/validation/test_decision_quality.py, seed=1337): higher
    top-1 template identification at every perturbation level, higher
    same-vs-different AUC, and 77% vs 55% balanced accuracy at the optimal
    MATCH boundary. Unlike cosine it is sensitive to magnitude differences,
    which is what actually distinguishes templates in this feature space.
    """
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    return 1.0 - sum(abs(a - b) for a, b in zip(vec_a, vec_b, strict=False)) / len(vec_a)


# Spatial layout encoding: a 3x3 occupancy grid per element class, derived
# from the bounding boxes that every SDK request and registered template
# already carries. This is the signal that separates two same-genre sibling
# templates whose scalar counts are nearly identical ("table top-left" vs
# "table bottom-right"). 3x3 (not 4x4) keeps per-cell mass stable for the
# 10-100 boxes real documents carry; area-overlap assignment (not box-center)
# degrades smoothly under OCR jitter instead of flipping at cell boundaries.
_SPATIAL_GRID = 3
_SPATIAL_CHANNELS = ("text", "table", "image")


def _classify_element(element_type: str) -> str:
    """Map vendor element types onto the spatial channels (unknown -> text)."""
    t = element_type.lower()
    if t == "table":
        return "table"
    if t in ("image", "figure", "picture"):
        return "image"
    return "text"


def _extract_spatial_vector(features: StructuralFeatures) -> list[float] | None:
    """27-dim spatial occupancy vector, or None when no boxes are available.

    Per (channel, cell): summed box-cell intersection area / cell area,
    averaged over pages, clamped to [0, 1] — consistent with L1-Gower dims.
    """
    boxes = features.bounding_boxes
    if not boxes:
        return None

    grid_n = _SPATIAL_GRID
    cell = 1.0 / grid_n
    cell_area = cell * cell
    pages = max(1, features.page_count)
    occupancy = {ch: [0.0] * (grid_n * grid_n) for ch in _SPATIAL_CHANNELS}

    for box in boxes:
        channel = _classify_element(box.element_type)
        x0, y0 = box.x, box.y
        x1 = min(1.0, box.x + box.width)
        y1 = min(1.0, box.y + box.height)
        if x1 <= x0 or y1 <= y0:
            continue
        # Only visit the cells the box actually spans.
        ci0 = min(grid_n - 1, int(x0 / cell))
        ci1 = min(grid_n - 1, int((x1 - 1e-12) / cell))
        cj0 = min(grid_n - 1, int(y0 / cell))
        cj1 = min(grid_n - 1, int((y1 - 1e-12) / cell))
        for cj in range(cj0, cj1 + 1):
            cy0, cy1 = cj * cell, (cj + 1) * cell
            for ci in range(ci0, ci1 + 1):
                cx0, cx1 = ci * cell, (ci + 1) * cell
                overlap = max(0.0, min(x1, cx1) - max(x0, cx0)) * max(
                    0.0, min(y1, cy1) - max(y0, cy0)
                )
                occupancy[channel][cj * grid_n + ci] += overlap

    return [
        min(1.0, value / cell_area / pages)
        for channel in _SPATIAL_CHANNELS
        for value in occupancy[channel]
    ]


def _feature_vectors(features: StructuralFeatures) -> tuple[list[float], list[float] | None]:
    """Both representations used for matching: (scalar 10-dim, spatial 27-dim|None)."""
    return _extract_feature_vector(features), _extract_spatial_vector(features)


# Blockwise weight of the spatial term in the blended similarity. Selected on
# the ground-truth harness (seed 1337) from {0.3, 0.4, 0.5, 0.6, 0.7} by the
# pre-registered criterion (mean of top-1@0.15, balanced accuracy at the
# MATCH boundary, balanced accuracy at the NEW boundary): 0.7 scored highest
# (0.783 vs scalar 0.687) and was accepted on ALL held-out runs (seeds
# 2024/4242/9001 and a 10-per-category pool): within 5 points of the
# selection-run balanced accuracies and beating the scalar metric on every
# pre-declared number on every run. Blockwise (not concatenated) so 27
# near-zero spatial cells can't compress the raw range.
_W_SPATIAL = 0.7


def _blended_similarity(
    vecs_a: tuple[list[float], list[float] | None],
    vecs_b: tuple[list[float], list[float] | None],
) -> tuple[float, bool]:
    """Raw similarity for two (scalar, spatial) pairs.

    Returns (raw, used_spatial). Falls back to the scalar block alone when
    EITHER side lacks boxes: templates registered before this feature (or by
    older SDK clients) must not silently degrade to REVIEW.
    """
    scalar_a, spatial_a = vecs_a
    scalar_b, spatial_b = vecs_b
    scalar_sim = _feature_similarity(scalar_a, scalar_b)
    if spatial_a is None or spatial_b is None:
        return scalar_sim, False
    spatial_sim = _feature_similarity(spatial_a, spatial_b)
    return (1.0 - _W_SPATIAL) * scalar_sim + _W_SPATIAL * spatial_sim, True


# Calibration anchors measured on the ground-truth harness (seed=1337):
# raw similarities compress into ~[0.88, 1.0], so the documented decision
# thresholds (MATCH >= 0.85, NEW < 0.50) never fired — heavily redesigned and
# even never-registered documents auto-matched. The piecewise-linear remap
# below anchors the *measured* parent-vs-impostor boundary (raw 0.98) to
# confidence 0.85 and the "no plausibly-same layout" region (raw 0.90) to
# confidence 0.50, making the documented threshold semantics true.
_RAW_MATCH_ANCHOR = 0.98  # scalar path: raw similarity at the empirical MATCH boundary
_RAW_NEW_ANCHOR = 0.90  # scalar path: raw similarity at the empirical REVIEW/NEW boundary
_RAW_FLOOR = 0.60  # scalar path: raw similarity mapping to confidence 0.0

# Blended (scalar+spatial) path anchors. MATCH anchor = median empirical
# parent-vs-impostor threshold across the held-out runs (0.91/0.93/0.94/0.92
# -> 0.93). The measured known-vs-novel threshold (0.95) came out ABOVE the
# MATCH anchor — the two boundary populations overlap, making it unusable for
# a monotone calibration — so the NEW anchor uses a mechanical fallback
# documented here rather than a cherry-picked value: preserve the scalar
# path's MATCH-NEW gap (0.98-0.90 = 0.08), giving 0.93 - 0.08 = 0.85, and
# the same floor offset (-0.30). Consequence (verified on the harness):
# never-registered documents land in REVIEW, not NEW — novelty detection
# improved (58% -> ~63% balanced accuracy held-out) but remains the weakest
# signal; the pre-registered 0.70 target was NOT met and is documented in
# docs/SCORECARD.md.
_RAW_MATCH_ANCHOR_BLENDED = 0.93
_RAW_NEW_ANCHOR_BLENDED = 0.85
_RAW_FLOOR_BLENDED = 0.55


def _calibrate_confidence(
    raw: float,
    match_anchor: float = _RAW_MATCH_ANCHOR,
    new_anchor: float = _RAW_NEW_ANCHOR,
    floor: float = _RAW_FLOOR,
) -> float:
    """Map raw feature similarity onto the documented confidence scale."""
    if raw >= match_anchor:
        conf = 0.85 + 0.15 * (raw - match_anchor) / (1.0 - match_anchor)
    elif raw >= new_anchor:
        conf = 0.50 + 0.35 * (raw - new_anchor) / (match_anchor - new_anchor)
    else:
        conf = 0.50 * (raw - floor) / (new_anchor - floor)
    return max(0.0, min(1.0, conf))


def _match_confidence(
    vecs_a: tuple[list[float], list[float] | None],
    vecs_b: tuple[list[float], list[float] | None],
) -> float:
    """Calibrated matching confidence between two (scalar, spatial) pairs.

    Each path is calibrated with its own measured anchors so a confidence of
    0.85 means "empirical MATCH boundary" regardless of whether boxes were
    available.
    """
    raw, used_spatial = _blended_similarity(vecs_a, vecs_b)
    if used_spatial:
        return _calibrate_confidence(
            raw, _RAW_MATCH_ANCHOR_BLENDED, _RAW_NEW_ANCHOR_BLENDED, _RAW_FLOOR_BLENDED
        )
    return _calibrate_confidence(raw)


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

        # Refine with calibrated matching confidence
        input_vectors = _feature_vectors(features)
        best_match: Template | None = None
        best_similarity = 0.0

        for candidate in candidates:
            template = templates.get(candidate.template_id)
            if not template:
                continue

            try:
                template_features = StructuralFeatures.model_validate(template.structural_features)
            except ValidationError as e:
                logger.warning(
                    "invalid_template_features",
                    template_id=str(template.id),
                    error=str(e),
                )
                continue

            similarity = _match_confidence(input_vectors, _feature_vectors(template_features))

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

    # Extract feature vectors for input (scalar + spatial when boxes present)
    input_vectors = _feature_vectors(features)

    # Find best match
    best_match: Template | None = None
    best_similarity = 0.0

    for template in templates:
        # Extract template's feature vectors
        try:
            template_features = StructuralFeatures.model_validate(template.structural_features)
        except ValidationError as e:
            logger.warning(
                "invalid_template_features_in_scan",
                template_id=str(template.id),
                error=str(e),
            )
            continue

        # Compute calibrated matching confidence
        similarity = _match_confidence(input_vectors, _feature_vectors(template_features))

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
