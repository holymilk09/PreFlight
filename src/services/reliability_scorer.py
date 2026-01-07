"""Reliability scoring service.

MVP implementation: Weighted average of factors.
Future: Thompson Sampling, historical performance tracking.
"""

import math

from src.models import ExtractorMetadata, Template


async def compute_reliability_score(
    template: Template,
    extractor: ExtractorMetadata,
    drift_score: float,
) -> float:
    """Compute reliability score for the extraction.

    MVP algorithm:
    1. Start with template's baseline reliability
    2. Factor in extractor confidence
    3. Apply drift penalty

    Args:
        template: The matched template with baseline reliability.
        extractor: Metadata about the extractor used.
        drift_score: Current drift score (0-1).

    Returns:
        Reliability score from 0.0 to 1.0.

    Score interpretation:
        - >= 0.95: High confidence, minimal corrections needed
        - 0.80 - 0.95: Good confidence, standard corrections
        - 0.60 - 0.80: Moderate confidence, enhanced validation
        - < 0.60: Low confidence, manual review recommended
    """
    # Component weights
    BASELINE_WEIGHT = 0.40
    CONFIDENCE_WEIGHT = 0.35
    DRIFT_WEIGHT = 0.25

    # 1. Template baseline reliability
    baseline = template.baseline_reliability

    # 2. Extractor confidence (already 0-1)
    extractor_confidence = extractor.confidence

    # 3. Drift penalty (exponential decay)
    # High drift significantly reduces reliability
    drift_factor = math.exp(-2.0 * drift_score)

    # Weighted combination
    reliability = (
        baseline * BASELINE_WEIGHT
        + extractor_confidence * CONFIDENCE_WEIGHT
        + drift_factor * DRIFT_WEIGHT
    )

    # Apply additional penalties for specific conditions

    # Penalty for unknown extractors (not in our performance database yet)
    known_extractors = {"nvidia", "abbyy", "tesseract", "azure", "google", "aws"}
    if extractor.vendor.lower() not in known_extractors:
        reliability *= 0.90  # 10% penalty for unknown extractor

    # Penalty for very high drift
    if drift_score > 0.50:
        reliability *= 0.85  # Additional 15% penalty for critical drift

    # Bonus for high extractor confidence
    if extractor_confidence > 0.95:
        reliability = min(1.0, reliability * 1.05)  # 5% bonus

    # Clamp to [0, 1]
    return max(0.0, min(1.0, reliability))


def get_reliability_breakdown(
    template: Template,
    extractor: ExtractorMetadata,
    drift_score: float,
) -> dict:
    """Get detailed reliability breakdown for debugging/analysis.

    Returns component scores and their contributions.
    """
    baseline = template.baseline_reliability
    extractor_confidence = extractor.confidence
    drift_factor = math.exp(-2.0 * drift_score)

    known_extractors = {"nvidia", "abbyy", "tesseract", "azure", "google", "aws"}
    is_known_extractor = extractor.vendor.lower() in known_extractors

    return {
        "components": {
            "baseline_reliability": {
                "value": baseline,
                "weight": 0.40,
                "contribution": baseline * 0.40,
            },
            "extractor_confidence": {
                "value": extractor_confidence,
                "weight": 0.35,
                "contribution": extractor_confidence * 0.35,
            },
            "drift_factor": {
                "value": drift_factor,
                "weight": 0.25,
                "contribution": drift_factor * 0.25,
                "drift_score": drift_score,
            },
        },
        "adjustments": {
            "unknown_extractor_penalty": not is_known_extractor,
            "high_drift_penalty": drift_score > 0.50,
            "high_confidence_bonus": extractor_confidence > 0.95,
        },
        "extractor": {
            "vendor": extractor.vendor,
            "model": extractor.model,
            "version": extractor.version,
            "is_known": is_known_extractor,
        },
    }
