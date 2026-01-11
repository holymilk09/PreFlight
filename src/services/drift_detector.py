"""Drift detection service.

MVP implementation: Z-score from baseline.
Future: CUSUM charts, Prophet forecasting, PELT changepoint detection.
"""

from src.models import StructuralFeatures, Template


async def compute_drift_score(
    template: Template,
    current_features: StructuralFeatures,
) -> float:
    """Compute drift score comparing current features to template baseline.

    MVP algorithm:
    1. Compare key structural metrics to template's stored features
    2. Compute z-scores for deviations
    3. Return weighted average drift score

    Args:
        template: The matched template with baseline features.
        current_features: Current document's structural features.

    Returns:
        Drift score from 0.0 (no drift) to 1.0 (severe drift).

    Thresholds:
        - < 0.15: Stable (green)
        - 0.15 - 0.30: Watch (yellow)
        - 0.30 - 0.50: Review required (orange)
        - > 0.50: Critical drift (red)
    """
    # Get baseline features from template
    baseline = StructuralFeatures.model_validate(template.structural_features)

    # Compute individual metric drifts
    drifts = []

    # Element count drift (allow 20% variance)
    if baseline.element_count > 0:
        element_drift = abs(current_features.element_count - baseline.element_count) / max(
            baseline.element_count * 0.2, 1
        )
        drifts.append(("element_count", min(element_drift, 1.0), 0.15))

    # Table count drift (exact match expected)
    if baseline.table_count != current_features.table_count:
        table_drift = abs(current_features.table_count - baseline.table_count) / max(
            baseline.table_count, 1
        )
        drifts.append(("table_count", min(table_drift, 1.0), 0.20))
    else:
        drifts.append(("table_count", 0.0, 0.20))

    # Page count drift (should match exactly for same template)
    if baseline.page_count != current_features.page_count:
        page_drift = abs(current_features.page_count - baseline.page_count) / baseline.page_count
        drifts.append(("page_count", min(page_drift, 1.0), 0.15))
    else:
        drifts.append(("page_count", 0.0, 0.15))

    # Text density drift (allow 30% variance)
    if baseline.text_density > 0:
        density_drift = abs(current_features.text_density - baseline.text_density) / max(
            baseline.text_density * 0.3, 0.1
        )
        drifts.append(("text_density", min(density_drift, 1.0), 0.15))

    # Layout complexity drift
    complexity_drift = abs(current_features.layout_complexity - baseline.layout_complexity)
    drifts.append(("layout_complexity", min(complexity_drift, 1.0), 0.15))

    # Column count drift
    if baseline.column_count != current_features.column_count:
        col_drift = 1.0  # Different column layout is significant
        drifts.append(("column_count", col_drift, 0.10))
    else:
        drifts.append(("column_count", 0.0, 0.10))

    # Header/footer presence
    header_drift = 0.0 if baseline.has_header == current_features.has_header else 0.5
    footer_drift = 0.0 if baseline.has_footer == current_features.has_footer else 0.5
    drifts.append(("header_footer", (header_drift + footer_drift) / 2, 0.10))

    # Compute weighted average
    total_weight = sum(d[2] for d in drifts)
    if total_weight == 0:
        return 0.0

    weighted_sum = sum(d[1] * d[2] for d in drifts)
    drift_score = weighted_sum / total_weight

    # Clamp to [0, 1]
    return max(0.0, min(1.0, drift_score))


def get_drift_details(
    template: Template,
    current_features: StructuralFeatures,
) -> dict:
    """Get detailed drift breakdown for debugging/analysis.

    Returns a dictionary with per-metric drift values.
    """
    baseline = StructuralFeatures.model_validate(template.structural_features)

    return {
        "element_count": {
            "baseline": baseline.element_count,
            "current": current_features.element_count,
            "delta": current_features.element_count - baseline.element_count,
        },
        "table_count": {
            "baseline": baseline.table_count,
            "current": current_features.table_count,
            "delta": current_features.table_count - baseline.table_count,
        },
        "page_count": {
            "baseline": baseline.page_count,
            "current": current_features.page_count,
            "delta": current_features.page_count - baseline.page_count,
        },
        "text_density": {
            "baseline": baseline.text_density,
            "current": current_features.text_density,
            "delta": current_features.text_density - baseline.text_density,
        },
        "layout_complexity": {
            "baseline": baseline.layout_complexity,
            "current": current_features.layout_complexity,
            "delta": current_features.layout_complexity - baseline.layout_complexity,
        },
        "column_count": {
            "baseline": baseline.column_count,
            "current": current_features.column_count,
            "match": baseline.column_count == current_features.column_count,
        },
        "has_header": {
            "baseline": baseline.has_header,
            "current": current_features.has_header,
            "match": baseline.has_header == current_features.has_header,
        },
        "has_footer": {
            "baseline": baseline.has_footer,
            "current": current_features.has_footer,
            "match": baseline.has_footer == current_features.has_footer,
        },
    }
