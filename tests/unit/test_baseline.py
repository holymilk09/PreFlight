"""Tests for rolling template baselines (EWMA drift false-alarm prevention)."""

from unittest.mock import patch

import pytest
from uuid_extensions import uuid7

from src.config import settings
from src.models import StructuralFeatures, Template, TemplateStatus
from src.services.baseline import update_baseline
from src.services.drift_detector import compute_drift_score


def _features(**overrides) -> StructuralFeatures:
    base = {
        "element_count": 50,
        "table_count": 2,
        "text_block_count": 40,
        "image_count": 2,
        "page_count": 1,
        "text_density": 0.45,
        "layout_complexity": 0.40,
        "column_count": 2,
        "has_header": True,
        "has_footer": True,
        "bounding_boxes": [],
    }
    base.update(overrides)
    return StructuralFeatures(**base)


def _template(features: StructuralFeatures) -> Template:
    return Template(
        id=uuid7(),
        tenant_id=uuid7(),
        template_id="tpl",
        version="1",
        fingerprint="0" * 64,
        structural_features=features.model_dump(),
        baseline_reliability=0.9,
        correction_rules=[],
        status=TemplateStatus.ACTIVE,
    )


class TestUpdateBaseline:
    def test_healthy_match_blends_volume_features(self):
        """A confident, low-drift MATCH nudges volume features toward observed."""
        template = _template(_features())
        observed = _features(element_count=60, text_density=0.55)

        with patch.object(settings, "baseline_learning_rate", 0.1):
            updated = update_baseline(template, observed, match_confidence=0.9, drift_score=0.05)

        assert updated is True
        assert template.structural_features["element_count"] == 51  # 50 + 0.1*10
        assert template.structural_features["text_density"] == pytest.approx(0.46)

    def test_identity_fields_never_blend(self):
        """Tables/pages/columns/header/footer are identity — frozen."""
        template = _template(_features())
        observed = _features(
            table_count=5, page_count=3, column_count=1, has_header=False, has_footer=False
        )

        with patch.object(settings, "baseline_learning_rate", 0.5):
            updated = update_baseline(template, observed, match_confidence=0.95, drift_score=0.05)

        assert updated is True
        sf = template.structural_features
        assert sf["table_count"] == 2
        assert sf["page_count"] == 1
        assert sf["column_count"] == 2
        assert sf["has_header"] is True
        assert sf["has_footer"] is True

    def test_drifted_evaluation_does_not_update(self):
        """The healthy-gate: drifting documents cannot pull the baseline."""
        template = _template(_features())
        before = dict(template.structural_features)

        with patch.object(settings, "baseline_learning_rate", 0.1):
            updated = update_baseline(
                template, _features(element_count=90), match_confidence=0.9, drift_score=0.20
            )

        assert updated is False
        assert template.structural_features == before

    def test_low_confidence_does_not_update(self):
        template = _template(_features())
        before = dict(template.structural_features)

        with patch.object(settings, "baseline_learning_rate", 0.1):
            updated = update_baseline(
                template, _features(element_count=90), match_confidence=0.7, drift_score=0.05
            )

        assert updated is False
        assert template.structural_features == before

    def test_zero_rate_disables_learning(self):
        template = _template(_features())
        before = dict(template.structural_features)

        with patch.object(settings, "baseline_learning_rate", 0.0):
            updated = update_baseline(
                template, _features(element_count=60), match_confidence=0.95, drift_score=0.01
            )

        assert updated is False
        assert template.structural_features == before

    def test_invalid_stored_features_safe(self):
        template = _template(_features())
        template.structural_features = {"garbage": True}

        with patch.object(settings, "baseline_learning_rate", 0.1):
            updated = update_baseline(
                template, _features(), match_confidence=0.95, drift_score=0.01
            )

        assert updated is False


class TestGradualEvolutionSimulation:
    """The false-alarm scenario this feature exists to fix.

    A template evolves slowly (volume +0.4%/step, densities +0.002/step for
    150 steps — e.g. a supplier gradually adding invoice lines over a year).
    Against a static baseline the accumulated deviation ends above the 0.30
    review threshold: a permanent alarm on a healthy pipeline. With EWMA
    learning the baseline tracks the evolution and drift stays green.
    """

    @pytest.mark.asyncio
    async def test_ewma_prevents_false_alarm_static_does_not(self):
        steps = 150

        def evolved(step: int) -> StructuralFeatures:
            growth = 1.0 + 0.004 * step
            return _features(
                element_count=round(50 * growth),
                text_block_count=round(40 * growth),
                text_density=min(1.0, 0.45 + 0.002 * step),
                layout_complexity=min(1.0, 0.40 + 0.002 * step),
            )

        # Static baseline: never updated.
        static_template = _template(_features())
        static_final_drift = await compute_drift_score(static_template, evolved(steps))

        # Rolling baseline: healthy evaluations blend in as they arrive.
        rolling_template = _template(_features())
        rolling_final_drift = 0.0
        with patch.object(settings, "baseline_learning_rate", 0.05):
            for step in range(1, steps + 1):
                observed = evolved(step)
                rolling_final_drift = await compute_drift_score(rolling_template, observed)
                update_baseline(
                    rolling_template,
                    observed,
                    match_confidence=0.9,
                    drift_score=rolling_final_drift,
                )

        # Static baseline has walked into a permanent review-level alarm...
        assert static_final_drift >= 0.30, f"static drift only {static_final_drift:.3f}"
        # ...while the rolling baseline stayed green the whole way.
        assert rolling_final_drift < 0.15, f"rolling drift {rolling_final_drift:.3f} not green"
        assert rolling_final_drift < static_final_drift
