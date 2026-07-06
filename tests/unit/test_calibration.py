"""Tests for calibration metric derivation (outcome-feedback loop)."""

from src.api.analytics_routes import summarize_calibration
from src.models import FeedbackOutcome


class TestSummarizeCalibration:
    """Tests for headline metrics from decision × outcome counts."""

    def test_empty_counts(self):
        """No feedback at all -> null rates, zero errors."""
        precision, catch_rate, caught, missed = summarize_calibration({})
        assert precision is None
        assert catch_rate is None
        assert caught == 0
        assert missed == 0

    def test_auto_process_precision(self):
        """Precision is the fraction of MATCH decisions that were correct."""
        counts = {"MATCH": {"correct": 90, "corrected": 8, "rejected": 2}}
        precision, catch_rate, caught, missed = summarize_calibration(counts)
        assert precision == 0.9
        assert catch_rate is None  # nothing was flagged
        assert caught == 0
        assert missed == 10  # 8 corrected + 2 rejected slipped through auto-process

    def test_review_catch_rate(self):
        """Catch rate is the fraction of flagged (non-MATCH) docs that were bad."""
        counts = {
            "REVIEW": {"correct": 4, "corrected": 5, "rejected": 1},
            "NEW": {"corrected": 2},
        }
        precision, catch_rate, caught, missed = summarize_calibration(counts)
        assert precision is None  # no MATCH feedback
        assert catch_rate == 8 / 12  # (5 + 1 + 2) bad of 12 flagged
        assert caught == 8
        assert missed == 0

    def test_combined(self):
        """MATCH and flagged populations are scored independently."""
        counts = {
            "MATCH": {"correct": 97, "corrected": 3},
            "REVIEW": {"correct": 10, "corrected": 30},
            "REJECT": {"rejected": 10},
        }
        precision, catch_rate, caught, missed = summarize_calibration(counts)
        assert precision == 0.97
        assert catch_rate == 40 / 50
        assert caught == 40
        assert missed == 3

    def test_outcome_values_match_enum(self):
        """The metric derivation keys on the FeedbackOutcome enum values."""
        assert FeedbackOutcome.CORRECT.value == "correct"
        assert FeedbackOutcome.CORRECTED.value == "corrected"
        assert FeedbackOutcome.REJECTED.value == "rejected"
