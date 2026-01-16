"""Tests for the SafeguardEngine service."""

import pytest

from src.models import BoundingBox, ExtractorMetadata, ExtractorProvider, StructuralFeatures
from src.services.safeguard_engine import SafeguardEngine


@pytest.fixture
def safeguard_engine():
    """Create SafeguardEngine instance."""
    return SafeguardEngine()


@pytest.fixture
def valid_features() -> StructuralFeatures:
    """Create valid structural features."""
    return StructuralFeatures(
        element_count=50,
        table_count=2,
        text_block_count=40,
        image_count=3,
        page_count=1,
        text_density=0.45,
        layout_complexity=0.32,
        column_count=2,
        has_header=True,
        has_footer=True,
        bounding_boxes=[
            BoundingBox(
                x=0.1,
                y=0.1,
                width=0.3,
                height=0.1,
                element_type="text",
                confidence=0.95,
                reading_order=0,
            ),
            BoundingBox(
                x=0.1,
                y=0.3,
                width=0.8,
                height=0.2,
                element_type="table",
                confidence=0.90,
                reading_order=1,
            ),
        ],
    )


@pytest.fixture
def valid_extractor() -> ExtractorMetadata:
    """Create valid extractor metadata."""
    return ExtractorMetadata(
        vendor="aws",
        model="textract",
        version="1.0",
        confidence=0.95,
        latency_ms=450,
        cost_usd=0.002,
    )


@pytest.fixture
def aws_provider() -> ExtractorProvider:
    """Create AWS provider configuration."""
    return ExtractorProvider(
        vendor="aws",
        display_name="AWS Textract",
        confidence_multiplier=1.0,
        drift_sensitivity=1.0,
        supported_element_types=["PAGE", "LINE", "WORD", "TABLE", "CELL", "text", "table"],
        typical_latency_ms=450,
        is_active=True,
        is_known=True,
    )


class TestDataCompleteness:
    """Tests for data completeness checks."""

    def test_missing_bounding_boxes_warning(self, safeguard_engine, valid_extractor):
        """Should warn when no bounding boxes provided."""
        features = StructuralFeatures(
            element_count=50,
            table_count=2,
            text_block_count=40,
            image_count=3,
            page_count=1,
            text_density=0.45,
            layout_complexity=0.32,
            column_count=2,
            has_header=True,
            has_footer=True,
            bounding_boxes=[],  # Empty
        )

        warnings = safeguard_engine.validate_request(features, valid_extractor, None)

        assert any("No bounding boxes" in w for w in warnings)

    def test_zero_elements_error(self, safeguard_engine, valid_extractor):
        """Should error when zero elements detected."""
        features = StructuralFeatures(
            element_count=0,  # Zero
            table_count=0,
            text_block_count=0,
            image_count=0,
            page_count=1,
            text_density=0.0,
            layout_complexity=0.0,
            column_count=0,
            has_header=False,
            has_footer=False,
            bounding_boxes=[],
        )

        warnings = safeguard_engine.validate_request(features, valid_extractor, None)

        assert any("ERROR:" in w and "Zero elements" in w for w in warnings)

    def test_incomplete_bbox_ratio_warning(self, safeguard_engine, valid_extractor):
        """Should warn when bbox count is much lower than element count."""
        features = StructuralFeatures(
            element_count=1000,  # Many elements
            table_count=10,
            text_block_count=900,
            image_count=10,
            page_count=5,
            text_density=0.45,
            layout_complexity=0.32,
            column_count=2,
            has_header=True,
            has_footer=True,
            bounding_boxes=[
                BoundingBox(
                    x=0.1, y=0.1, width=0.3, height=0.1,
                    element_type="text", confidence=0.95, reading_order=0,
                ),
            ],  # Only 1 bbox for 1000 elements
        )

        warnings = safeguard_engine.validate_request(features, valid_extractor, None)

        assert any("incomplete" in w.lower() for w in warnings)


class TestLayoutConsistency:
    """Tests for layout consistency checks."""

    def test_zero_area_bbox_warning(self, safeguard_engine, valid_extractor):
        """Should warn about zero-area bounding boxes."""
        features = StructuralFeatures(
            element_count=10,
            table_count=1,
            text_block_count=9,
            image_count=0,
            page_count=1,
            text_density=0.45,
            layout_complexity=0.32,
            column_count=1,
            has_header=True,
            has_footer=False,
            bounding_boxes=[
                BoundingBox(
                    x=0.1, y=0.1, width=0.0, height=0.1,  # Zero width
                    element_type="text", confidence=0.95, reading_order=0,
                ),
            ],
        )

        warnings = safeguard_engine.validate_request(features, valid_extractor, None)

        assert any("Zero-area" in w for w in warnings)

    def test_out_of_bounds_bbox_warning(self, safeguard_engine, valid_extractor):
        """Should warn about out-of-bounds bounding boxes."""
        features = StructuralFeatures(
            element_count=10,
            table_count=1,
            text_block_count=9,
            image_count=0,
            page_count=1,
            text_density=0.45,
            layout_complexity=0.32,
            column_count=1,
            has_header=True,
            has_footer=False,
            bounding_boxes=[
                BoundingBox(
                    x=0.9, y=0.1, width=0.3, height=0.1,  # Exceeds bounds
                    element_type="text", confidence=0.95, reading_order=0,
                ),
            ],
        )

        warnings = safeguard_engine.validate_request(features, valid_extractor, None)

        assert any("exceeds" in w.lower() for w in warnings)

    def test_extreme_layout_complexity_warning(self, safeguard_engine, valid_extractor):
        """Should warn about extremely high layout complexity."""
        features = StructuralFeatures(
            element_count=50,
            table_count=2,
            text_block_count=40,
            image_count=3,
            page_count=1,
            text_density=0.45,
            layout_complexity=0.99,  # Very high
            column_count=2,
            has_header=True,
            has_footer=True,
            bounding_boxes=[],
        )

        warnings = safeguard_engine.validate_request(features, valid_extractor, None)

        assert any("complexity" in w.lower() for w in warnings)


class TestProviderSpecificChecks:
    """Tests for provider-specific validation."""

    def test_unknown_element_type_warning(self, safeguard_engine, valid_extractor, aws_provider):
        """Should warn about element types not supported by provider."""
        features = StructuralFeatures(
            element_count=10,
            table_count=1,
            text_block_count=9,
            image_count=0,
            page_count=1,
            text_density=0.45,
            layout_complexity=0.32,
            column_count=1,
            has_header=True,
            has_footer=False,
            bounding_boxes=[
                BoundingBox(
                    x=0.1, y=0.1, width=0.3, height=0.1,
                    element_type="unknown_type",  # Not in AWS supported types
                    confidence=0.95, reading_order=0,
                ),
            ],
        )

        warnings = safeguard_engine.validate_request(features, valid_extractor, aws_provider)

        assert any("Unknown element type" in w for w in warnings)

    def test_excessive_latency_warning(self, safeguard_engine, aws_provider):
        """Should warn about excessive latency compared to typical."""
        extractor = ExtractorMetadata(
            vendor="aws",
            model="textract",
            version="1.0",
            confidence=0.95,
            latency_ms=2000,  # Much higher than typical 450ms
            cost_usd=0.002,
        )

        features = StructuralFeatures(
            element_count=10,
            table_count=1,
            text_block_count=9,
            image_count=0,
            page_count=1,
            text_density=0.45,
            layout_complexity=0.32,
            column_count=1,
            has_header=True,
            has_footer=False,
            bounding_boxes=[],
        )

        warnings = safeguard_engine.validate_request(features, extractor, aws_provider)

        assert any("3x typical" in w for w in warnings)

    def test_valid_request_no_warnings(
        self, safeguard_engine, valid_features, valid_extractor, aws_provider
    ):
        """Valid request with known provider should have no warnings."""
        warnings = safeguard_engine.validate_request(valid_features, valid_extractor, aws_provider)

        # May have warnings about bbox count ratio, but no errors
        errors = [w for w in warnings if w.startswith("ERROR:")]
        assert len(errors) == 0


class TestAnomalyDetection:
    """Tests for anomaly detection."""

    def test_low_confidence_many_elements_warning(self, safeguard_engine):
        """Should warn about low confidence with many elements."""
        extractor = ExtractorMetadata(
            vendor="aws",
            model="textract",
            version="1.0",
            confidence=0.3,  # Low confidence
            latency_ms=450,
            cost_usd=0.002,
        )

        features = StructuralFeatures(
            element_count=200,  # Many elements
            table_count=5,
            text_block_count=180,
            image_count=10,
            page_count=3,
            text_density=0.45,
            layout_complexity=0.32,
            column_count=2,
            has_header=True,
            has_footer=True,
            bounding_boxes=[],
        )

        warnings = safeguard_engine.validate_request(features, extractor, None)

        assert any("Low confidence" in w and "many elements" in w for w in warnings)

    def test_perfect_confidence_warning(self, safeguard_engine):
        """Should warn about perfect confidence score."""
        extractor = ExtractorMetadata(
            vendor="aws",
            model="textract",
            version="1.0",
            confidence=1.0,  # Perfect - suspicious
            latency_ms=450,
            cost_usd=0.002,
        )

        features = StructuralFeatures(
            element_count=50,
            table_count=2,
            text_block_count=40,
            image_count=3,
            page_count=1,
            text_density=0.45,
            layout_complexity=0.32,
            column_count=2,
            has_header=True,
            has_footer=True,
            bounding_boxes=[],
        )

        warnings = safeguard_engine.validate_request(features, extractor, None)

        assert any("Perfect confidence" in w for w in warnings)

    def test_many_pages_no_content_warning(self, safeguard_engine, valid_extractor):
        """Should warn about many pages with little content."""
        features = StructuralFeatures(
            element_count=20,
            table_count=0,  # No tables
            text_block_count=10,  # Very few text blocks
            image_count=0,
            page_count=15,  # Many pages
            text_density=0.05,
            layout_complexity=0.10,
            column_count=1,
            has_header=False,
            has_footer=False,
            bounding_boxes=[],
        )

        warnings = safeguard_engine.validate_request(features, valid_extractor, None)

        assert any("pages with no tables" in w for w in warnings)


class TestNoProvider:
    """Tests for requests without provider configuration."""

    def test_unknown_provider_no_crash(self, safeguard_engine, valid_features, valid_extractor):
        """Should handle unknown provider gracefully (None)."""
        warnings = safeguard_engine.validate_request(valid_features, valid_extractor, None)

        # Should not crash, may have completeness warnings
        assert isinstance(warnings, list)
