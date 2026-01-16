"""Reliability scoring service.

MVP implementation: Weighted average of factors with provider-aware calibration.
Future: Thompson Sampling, historical performance tracking.
"""

import math

from src.models import ExtractorMetadata, ExtractorProvider, Template


async def compute_reliability_score(
    template: Template | None,
    extractor: ExtractorMetadata,
    drift_score: float,
    provider: ExtractorProvider | None = None,
) -> float:
    """Compute reliability score for the extraction with provider-aware calibration.

    MVP algorithm:
    1. Start with template's baseline reliability (or default 0.85)
    2. Calibrate extractor confidence based on provider characteristics
    3. Apply drift penalty with provider-specific sensitivity
    4. Apply adjustments for unknown providers, high drift, etc.

    Args:
        template: The matched template with baseline reliability (None for NEW).
        extractor: Metadata about the extractor used.
        drift_score: Current drift score (0-1).
        provider: Provider configuration from DB (None if unknown vendor).

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

    # 1. Template baseline reliability (use default if no template)
    baseline = template.baseline_reliability if template else 0.85

    # 2. Calibrate extractor confidence based on provider
    extractor_confidence = extractor.confidence
    if provider and provider.confidence_multiplier != 1.0:
        extractor_confidence = min(1.0, extractor_confidence * provider.confidence_multiplier)

    # 3. Drift penalty with provider-specific sensitivity
    effective_drift = drift_score
    if provider and provider.drift_sensitivity != 1.0:
        effective_drift = drift_score * provider.drift_sensitivity

    # Exponential decay for drift factor
    drift_factor = math.exp(-2.0 * effective_drift)

    # Weighted combination
    reliability = (
        baseline * BASELINE_WEIGHT
        + extractor_confidence * CONFIDENCE_WEIGHT
        + drift_factor * DRIFT_WEIGHT
    )

    # Apply additional penalties for specific conditions

    # Penalty for unknown/inactive providers
    if provider is None or not provider.is_known:
        reliability *= 0.90  # 10% penalty for unknown provider

    # Penalty for very high effective drift
    if effective_drift > 0.50:
        reliability *= 0.85  # Additional 15% penalty for critical drift

    # Bonus for high calibrated confidence
    if extractor_confidence > 0.95:
        reliability = min(1.0, reliability * 1.05)  # 5% bonus

    # Clamp to [0, 1] and round to 4 decimal places
    return round(max(0.0, min(1.0, reliability)), 4)


def get_reliability_breakdown(
    template: Template | None,
    extractor: ExtractorMetadata,
    drift_score: float,
    provider: ExtractorProvider | None = None,
) -> dict:
    """Get detailed reliability breakdown for debugging/analysis.

    Returns component scores, calibrations, and their contributions.
    """
    baseline = template.baseline_reliability if template else 0.85
    raw_confidence = extractor.confidence

    # Apply provider calibration
    calibrated_confidence = raw_confidence
    confidence_multiplier = 1.0
    if provider and provider.confidence_multiplier != 1.0:
        confidence_multiplier = provider.confidence_multiplier
        calibrated_confidence = min(1.0, raw_confidence * confidence_multiplier)

    # Apply drift sensitivity
    drift_sensitivity = 1.0
    if provider:
        drift_sensitivity = provider.drift_sensitivity
    effective_drift = drift_score * drift_sensitivity
    drift_factor = math.exp(-2.0 * effective_drift)

    is_known_provider = provider is not None and provider.is_known

    return {
        "components": {
            "baseline_reliability": {
                "value": baseline,
                "weight": 0.40,
                "contribution": baseline * 0.40,
            },
            "extractor_confidence": {
                "raw_value": raw_confidence,
                "calibrated_value": calibrated_confidence,
                "multiplier": confidence_multiplier,
                "weight": 0.35,
                "contribution": calibrated_confidence * 0.35,
            },
            "drift_factor": {
                "value": drift_factor,
                "weight": 0.25,
                "contribution": drift_factor * 0.25,
                "raw_drift": drift_score,
                "effective_drift": effective_drift,
                "sensitivity": drift_sensitivity,
            },
        },
        "adjustments": {
            "unknown_provider_penalty": not is_known_provider,
            "high_drift_penalty": effective_drift > 0.50,
            "high_confidence_bonus": calibrated_confidence > 0.95,
        },
        "provider": {
            "vendor": extractor.vendor,
            "model": extractor.model,
            "version": extractor.version,
            "is_known": is_known_provider,
            "display_name": provider.display_name if provider else None,
            "confidence_multiplier": confidence_multiplier,
            "drift_sensitivity": drift_sensitivity,
        },
    }
