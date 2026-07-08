"""Tests for reliability self-calibration from feedback outcomes."""

from unittest.mock import patch

import pytest
from uuid_extensions import uuid7

from src.config import settings
from src.models import FeedbackOutcome, Template, TemplateStatus
from src.services.reliability_feedback import OUTCOME_TARGET, apply_reliability_feedback


def _template(baseline: float = 0.85) -> Template:
    return Template(
        id=uuid7(),
        tenant_id=uuid7(),
        template_id="tpl",
        version="1",
        fingerprint="0" * 64,
        structural_features={},
        baseline_reliability=baseline,
        correction_rules=[],
        status=TemplateStatus.ACTIVE,
    )


class TestApplyReliabilityFeedback:
    def test_correct_moves_baseline_up(self):
        template = _template(0.80)
        with patch.object(settings, "reliability_learning_rate", 0.1):
            assert apply_reliability_feedback(template, FeedbackOutcome.CORRECT) is True
        assert template.baseline_reliability == pytest.approx(0.82)  # 0.9*0.8 + 0.1*1.0

    def test_rejected_moves_baseline_down(self):
        template = _template(0.80)
        with patch.object(settings, "reliability_learning_rate", 0.1):
            apply_reliability_feedback(template, FeedbackOutcome.REJECTED)
        assert template.baseline_reliability == pytest.approx(0.72)  # 0.9*0.8 + 0.1*0.0

    def test_corrected_targets_half(self):
        template = _template(0.50)
        with patch.object(settings, "reliability_learning_rate", 0.2):
            apply_reliability_feedback(template, FeedbackOutcome.CORRECTED)
        assert template.baseline_reliability == pytest.approx(0.50)  # already at target

    def test_clamped_to_unit_interval(self):
        template = _template(1.0)
        with patch.object(settings, "reliability_learning_rate", 0.5):
            apply_reliability_feedback(template, FeedbackOutcome.CORRECT)
        assert template.baseline_reliability <= 1.0
        template = _template(0.0)
        with patch.object(settings, "reliability_learning_rate", 0.5):
            apply_reliability_feedback(template, FeedbackOutcome.REJECTED)
        assert template.baseline_reliability >= 0.0

    def test_zero_rate_disables(self):
        template = _template(0.85)
        with patch.object(settings, "reliability_learning_rate", 0.0):
            assert apply_reliability_feedback(template, FeedbackOutcome.REJECTED) is False
        assert template.baseline_reliability == 0.85

    def test_targets_cover_every_outcome(self):
        assert set(OUTCOME_TARGET) == set(FeedbackOutcome)
