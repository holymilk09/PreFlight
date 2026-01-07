"""Tests for drift detection service."""

import pytest

from src.services.drift_detector import compute_drift_score, get_drift_details
from src.models import StructuralFeatures


class TestComputeDriftScore:
    """Tests for drift score computation."""

    @pytest.mark.asyncio
    async def test_no_drift_identical_features(
        self, sample_template, sample_structural_features
    ):
        """Identical features should have zero drift."""
        drift = await compute_drift_score(sample_template, sample_structural_features)
        assert drift == pytest.approx(0.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_high_drift_different_features(
        self, sample_template, high_drift_features
    ):
        """Very different features should have high drift."""
        drift = await compute_drift_score(sample_template, high_drift_features)
        # Should trigger critical drift (> 0.50)
        assert drift > 0.30

    @pytest.mark.asyncio
    async def test_moderate_drift(self, sample_template):
        """Moderate changes should produce moderate drift."""
        moderate_features = StructuralFeatures(
            element_count=50,  # Slight increase from 45
            table_count=2,  # Same
            text_block_count=35,  # Slight increase
            image_count=4,  # Slight increase
            page_count=1,  # Same
            text_density=0.50,  # Slight increase from 0.45
            layout_complexity=0.35,  # Slight increase
            column_count=2,  # Same
            has_header=True,  # Same
            has_footer=True,  # Same
            bounding_boxes=[],
        )
        drift = await compute_drift_score(sample_template, moderate_features)
        # Should be in the "watch" or "review" range
        assert 0.05 < drift < 0.40

    @pytest.mark.asyncio
    async def test_page_count_drift(self, sample_template):
        """Different page count should contribute to drift."""
        features = StructuralFeatures(
            element_count=45,
            table_count=2,
            text_block_count=30,
            image_count=3,
            page_count=5,  # Changed from 1 to 5
            text_density=0.45,
            layout_complexity=0.32,
            column_count=2,
            has_header=True,
            has_footer=True,
            bounding_boxes=[],
        )
        drift = await compute_drift_score(sample_template, features)
        assert drift > 0.1  # Page count difference should register

    @pytest.mark.asyncio
    async def test_column_count_drift(self, sample_template):
        """Different column count should contribute to drift."""
        features = StructuralFeatures(
            element_count=45,
            table_count=2,
            text_block_count=30,
            image_count=3,
            page_count=1,
            text_density=0.45,
            layout_complexity=0.32,
            column_count=4,  # Changed from 2 to 4
            has_header=True,
            has_footer=True,
            bounding_boxes=[],
        )
        drift = await compute_drift_score(sample_template, features)
        assert drift > 0.05  # Column change is significant

    @pytest.mark.asyncio
    async def test_header_footer_drift(self, sample_template):
        """Missing header/footer should contribute to drift."""
        features = StructuralFeatures(
            element_count=45,
            table_count=2,
            text_block_count=30,
            image_count=3,
            page_count=1,
            text_density=0.45,
            layout_complexity=0.32,
            column_count=2,
            has_header=False,  # Changed
            has_footer=False,  # Changed
            bounding_boxes=[],
        )
        drift = await compute_drift_score(sample_template, features)
        assert drift > 0.03  # Header/footer changes should register

    @pytest.mark.asyncio
    async def test_drift_score_bounds(self, sample_template, high_drift_features):
        """Drift score should always be between 0 and 1."""
        drift = await compute_drift_score(sample_template, high_drift_features)
        assert 0.0 <= drift <= 1.0


class TestGetDriftDetails:
    """Tests for drift details breakdown."""

    def test_drift_details_structure(self, sample_template, sample_structural_features):
        """Verify drift details has expected structure."""
        details = get_drift_details(sample_template, sample_structural_features)

        expected_keys = [
            "element_count",
            "table_count",
            "page_count",
            "text_density",
            "layout_complexity",
            "column_count",
            "has_header",
            "has_footer",
        ]
        for key in expected_keys:
            assert key in details

    def test_drift_details_values(self, sample_template, sample_structural_features):
        """Verify drift details shows correct values."""
        details = get_drift_details(sample_template, sample_structural_features)

        assert details["element_count"]["baseline"] == 45
        assert details["element_count"]["current"] == 45
        assert details["element_count"]["delta"] == 0

        assert details["has_header"]["match"] is True
        assert details["has_footer"]["match"] is True

    def test_drift_details_with_changes(self, sample_template, high_drift_features):
        """Verify drift details captures differences."""
        details = get_drift_details(sample_template, high_drift_features)

        # Element count delta should be positive
        assert details["element_count"]["delta"] > 0
        assert details["element_count"]["current"] == 100
        assert details["element_count"]["baseline"] == 45

        # Boolean fields should show mismatch
        assert details["has_header"]["match"] is False
        assert details["column_count"]["match"] is False
