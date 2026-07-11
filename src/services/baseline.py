"""Rolling template baselines (EWMA) to prevent drift false alarms.

Drift is measured against the template's stored baseline features. With a
static registration-time baseline, legitimate gradual evolution (a supplier
slowly adding invoice lines, marginal density shifts) accumulates until the
drift score crosses the review threshold and stays there — a permanent false
alarm on a healthy pipeline.

The fix: after a confident, healthy MATCH (high confidence AND low drift),
blend the observed features into the baseline with a small EWMA step. Two
deliberate safeguards keep this from masking real drift:

1. **Healthy-gate**: only evaluations with drift below the stable threshold
   (< 0.15, "green") update the baseline. A drifting document can never pull
   the baseline toward itself, so genuine drift still alarms.
2. **Identity fields stay frozen**: table_count, page_count, column_count and
   header/footer flags are structural identity — a change there is a real
   revision that SHOULD alarm, so they are never blended. Only the
   continuous/volume features (element/text-block/image counts, text density,
   layout complexity) evolve.
"""

from typing import Any

import structlog
from pydantic import ValidationError

from src.config import settings
from src.models import StructuralFeatures, Template

logger = structlog.get_logger()

# Only evaluations at least this confident update the baseline.
MIN_CONFIDENCE_FOR_UPDATE = 0.85
# Healthy-gate: only "stable" (green) drift updates the baseline.
MAX_DRIFT_FOR_UPDATE = 0.15

# Continuous/volume features that may evolve gradually. Identity-like fields
# (table_count, page_count, column_count, has_header, has_footer) are frozen.
_BLENDED_INT_FIELDS = ("element_count", "text_block_count", "image_count")
_BLENDED_FLOAT_FIELDS = ("text_density", "layout_complexity")


def update_baseline(
    template: Template,
    observed: StructuralFeatures,
    match_confidence: float,
    drift_score: float,
) -> bool:
    """Blend observed features into the template baseline (EWMA).

    Returns True when the baseline was updated. The caller owns persistence —
    this only mutates ``template.structural_features`` in memory, so the write
    commits atomically with the evaluation.
    """
    rate = settings.baseline_learning_rate
    if rate <= 0.0:
        return False
    if match_confidence < MIN_CONFIDENCE_FOR_UPDATE or drift_score >= MAX_DRIFT_FOR_UPDATE:
        return False

    try:
        baseline = StructuralFeatures.model_validate(template.structural_features)
    except ValidationError:
        logger.warning("baseline_update_invalid_features", template_id=str(template.id))
        return False

    updated: dict[str, Any] = dict(template.structural_features)
    for field in _BLENDED_INT_FIELDS:
        old = getattr(baseline, field)
        new = getattr(observed, field)
        gap = new - old
        if gap != 0:
            # Integer EWMA with a minimum step of 1 toward the observation:
            # a plain round(rate * gap) stalls in a dead zone (increments
            # < 0.5 round away), letting slow trends accumulate until drift
            # trips the healthy-gate and learning stops entirely.
            step = round(rate * gap)
            if step == 0:
                step = 1 if gap > 0 else -1
            # Never overshoot the observed value.
            step = min(abs(step), abs(gap)) * (1 if gap > 0 else -1)
            updated[field] = old + step
    for field in _BLENDED_FLOAT_FIELDS:
        old = getattr(baseline, field)
        new = getattr(observed, field)
        updated[field] = (1.0 - rate) * old + rate * new

    # JSONB columns need a new object assigned for SQLAlchemy change tracking.
    template.structural_features = updated
    return True
