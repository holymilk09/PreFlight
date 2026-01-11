"""Tests for model validation and constraints."""

import pytest
from pydantic import ValidationError

from src.models import (
    BoundingBox,
    CorrectionRule,
    Decision,
    EvaluateRequest,
    EvaluateResponse,
    ExtractorMetadata,
    StructuralFeatures,
    TemplateCreate,
    TemplateStatus,
)


class TestBoundingBox:
    """Tests for BoundingBox validation."""

    def test_valid_bounding_box(self):
        """Valid bounding box should be created."""
        bbox = BoundingBox(
            x=0.1,
            y=0.2,
            width=0.3,
            height=0.4,
            element_type="text",
            confidence=0.95,
            reading_order=0,
        )
        assert bbox.x == 0.1
        assert bbox.confidence == 0.95

    def test_bounding_box_coordinates_must_be_normalized(self):
        """Coordinates must be between 0 and 1."""
        with pytest.raises(ValidationError) as exc_info:
            BoundingBox(
                x=1.5,  # Invalid: > 1
                y=0.2,
                width=0.3,
                height=0.4,
                element_type="text",
                confidence=0.95,
                reading_order=0,
            )
        assert "x" in str(exc_info.value)

    def test_bounding_box_negative_coordinates(self):
        """Coordinates cannot be negative."""
        with pytest.raises(ValidationError) as exc_info:
            BoundingBox(
                x=-0.1,  # Invalid: < 0
                y=0.2,
                width=0.3,
                height=0.4,
                element_type="text",
                confidence=0.95,
                reading_order=0,
            )
        assert "x" in str(exc_info.value)

    def test_bounding_box_confidence_bounds(self):
        """Confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            BoundingBox(
                x=0.1,
                y=0.2,
                width=0.3,
                height=0.4,
                element_type="text",
                confidence=1.5,  # Invalid
                reading_order=0,
            )

    def test_bounding_box_negative_reading_order(self):
        """Reading order cannot be negative."""
        with pytest.raises(ValidationError):
            BoundingBox(
                x=0.1,
                y=0.2,
                width=0.3,
                height=0.4,
                element_type="text",
                confidence=0.95,
                reading_order=-1,  # Invalid
            )

    def test_bounding_box_element_type_max_length(self):
        """Element type has max length of 50."""
        with pytest.raises(ValidationError):
            BoundingBox(
                x=0.1,
                y=0.2,
                width=0.3,
                height=0.4,
                element_type="x" * 51,  # Too long
                confidence=0.95,
                reading_order=0,
            )


class TestStructuralFeatures:
    """Tests for StructuralFeatures validation."""

    def test_valid_structural_features(self):
        """Valid structural features should be created."""
        features = StructuralFeatures(
            element_count=45,
            table_count=2,
            text_block_count=30,
            image_count=3,
            page_count=1,
            text_density=0.45,
            layout_complexity=0.32,
            column_count=2,
            has_header=True,
            has_footer=True,
            bounding_boxes=[],
        )
        assert features.element_count == 45
        assert features.has_header is True

    def test_page_count_minimum(self):
        """Page count must be at least 1."""
        with pytest.raises(ValidationError) as exc_info:
            StructuralFeatures(
                element_count=45,
                table_count=2,
                text_block_count=30,
                image_count=3,
                page_count=0,  # Invalid: must be >= 1
                text_density=0.45,
                layout_complexity=0.32,
                column_count=2,
                has_header=True,
                has_footer=True,
                bounding_boxes=[],
            )
        assert "page_count" in str(exc_info.value)

    def test_negative_counts_rejected(self):
        """Counts cannot be negative."""
        with pytest.raises(ValidationError):
            StructuralFeatures(
                element_count=-1,  # Invalid
                table_count=2,
                text_block_count=30,
                image_count=3,
                page_count=1,
                text_density=0.45,
                layout_complexity=0.32,
                column_count=2,
                has_header=True,
                has_footer=True,
                bounding_boxes=[],
            )

    def test_layout_complexity_bounds(self):
        """Layout complexity must be between 0 and 1."""
        with pytest.raises(ValidationError):
            StructuralFeatures(
                element_count=45,
                table_count=2,
                text_block_count=30,
                image_count=3,
                page_count=1,
                text_density=0.45,
                layout_complexity=1.5,  # Invalid: > 1
                column_count=2,
                has_header=True,
                has_footer=True,
                bounding_boxes=[],
            )

    def test_text_density_non_negative(self):
        """Text density cannot be negative."""
        with pytest.raises(ValidationError):
            StructuralFeatures(
                element_count=45,
                table_count=2,
                text_block_count=30,
                image_count=3,
                page_count=1,
                text_density=-0.1,  # Invalid
                layout_complexity=0.32,
                column_count=2,
                has_header=True,
                has_footer=True,
                bounding_boxes=[],
            )

    def test_bounding_boxes_max_length(self):
        """Bounding boxes list has max length of 1000."""
        boxes = [
            BoundingBox(
                x=0.1,
                y=0.1,
                width=0.1,
                height=0.1,
                element_type="text",
                confidence=0.9,
                reading_order=i,
            )
            for i in range(1001)
        ]
        with pytest.raises(ValidationError) as exc_info:
            StructuralFeatures(
                element_count=45,
                table_count=2,
                text_block_count=30,
                image_count=3,
                page_count=1,
                text_density=0.45,
                layout_complexity=0.32,
                column_count=2,
                has_header=True,
                has_footer=True,
                bounding_boxes=boxes,  # Too many
            )
        assert "bounding_boxes" in str(exc_info.value)


class TestExtractorMetadata:
    """Tests for ExtractorMetadata validation."""

    def test_valid_extractor_metadata(self):
        """Valid extractor metadata should be created."""
        meta = ExtractorMetadata(
            vendor="nvidia",
            model="nemotron-parse-1.2",
            version="1.2.0",
            confidence=0.95,
            latency_ms=234,
            cost_usd=0.002,
        )
        assert meta.vendor == "nvidia"
        assert meta.confidence == 0.95

    def test_confidence_bounds(self):
        """Confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            ExtractorMetadata(
                vendor="nvidia",
                model="test",
                version="1.0",
                confidence=1.5,  # Invalid
                latency_ms=100,
            )

    def test_latency_non_negative(self):
        """Latency cannot be negative."""
        with pytest.raises(ValidationError):
            ExtractorMetadata(
                vendor="nvidia",
                model="test",
                version="1.0",
                confidence=0.9,
                latency_ms=-1,  # Invalid
            )

    def test_cost_optional_and_non_negative(self):
        """Cost is optional but must be non-negative if provided."""
        # Without cost
        meta = ExtractorMetadata(
            vendor="nvidia",
            model="test",
            version="1.0",
            confidence=0.9,
            latency_ms=100,
        )
        assert meta.cost_usd is None

        # With valid cost
        meta_with_cost = ExtractorMetadata(
            vendor="nvidia",
            model="test",
            version="1.0",
            confidence=0.9,
            latency_ms=100,
            cost_usd=0.01,
        )
        assert meta_with_cost.cost_usd == 0.01

        # With invalid cost
        with pytest.raises(ValidationError):
            ExtractorMetadata(
                vendor="nvidia",
                model="test",
                version="1.0",
                confidence=0.9,
                latency_ms=100,
                cost_usd=-0.01,  # Invalid
            )

    def test_vendor_max_length(self):
        """Vendor has max length of 100."""
        with pytest.raises(ValidationError):
            ExtractorMetadata(
                vendor="x" * 101,  # Too long
                model="test",
                version="1.0",
                confidence=0.9,
                latency_ms=100,
            )


class TestEvaluateRequest:
    """Tests for EvaluateRequest validation."""

    @pytest.fixture
    def valid_structural_features(self):
        """Create valid structural features."""
        return StructuralFeatures(
            element_count=45,
            table_count=2,
            text_block_count=30,
            image_count=3,
            page_count=1,
            text_density=0.45,
            layout_complexity=0.32,
            column_count=2,
            has_header=True,
            has_footer=True,
            bounding_boxes=[],
        )

    @pytest.fixture
    def valid_extractor_metadata(self):
        """Create valid extractor metadata."""
        return ExtractorMetadata(
            vendor="nvidia",
            model="test",
            version="1.0",
            confidence=0.9,
            latency_ms=100,
        )

    def test_valid_evaluate_request(self, valid_structural_features, valid_extractor_metadata):
        """Valid evaluate request should be created."""
        request = EvaluateRequest(
            layout_fingerprint="a" * 64,
            structural_features=valid_structural_features,
            extractor_metadata=valid_extractor_metadata,
            client_doc_hash="b" * 64,
            client_correlation_id="corr-123",
            pipeline_id="pipeline-1",
        )
        assert request.layout_fingerprint == "a" * 64

    def test_fingerprint_must_be_64_chars(
        self, valid_structural_features, valid_extractor_metadata
    ):
        """Layout fingerprint must be exactly 64 characters."""
        with pytest.raises(ValidationError) as exc_info:
            EvaluateRequest(
                layout_fingerprint="a" * 63,  # Too short
                structural_features=valid_structural_features,
                extractor_metadata=valid_extractor_metadata,
                client_doc_hash="b" * 64,
                client_correlation_id="corr-123",
                pipeline_id="pipeline-1",
            )
        assert "64" in str(exc_info.value)

    def test_fingerprint_must_be_hex(self, valid_structural_features, valid_extractor_metadata):
        """Layout fingerprint must be valid hexadecimal."""
        with pytest.raises(ValidationError) as exc_info:
            EvaluateRequest(
                layout_fingerprint="g" * 64,  # Invalid hex
                structural_features=valid_structural_features,
                extractor_metadata=valid_extractor_metadata,
                client_doc_hash="b" * 64,
                client_correlation_id="corr-123",
                pipeline_id="pipeline-1",
            )
        assert "hexadecimal" in str(exc_info.value).lower()

    def test_doc_hash_must_be_64_chars(self, valid_structural_features, valid_extractor_metadata):
        """Client doc hash must be exactly 64 characters."""
        with pytest.raises(ValidationError):
            EvaluateRequest(
                layout_fingerprint="a" * 64,
                structural_features=valid_structural_features,
                extractor_metadata=valid_extractor_metadata,
                client_doc_hash="b" * 32,  # Too short
                client_correlation_id="corr-123",
                pipeline_id="pipeline-1",
            )

    def test_fingerprint_normalized_to_lowercase(
        self, valid_structural_features, valid_extractor_metadata
    ):
        """Fingerprints should be normalized to lowercase."""
        request = EvaluateRequest(
            layout_fingerprint="A" * 64,  # Uppercase
            structural_features=valid_structural_features,
            extractor_metadata=valid_extractor_metadata,
            client_doc_hash="B" * 64,  # Uppercase
            client_correlation_id="corr-123",
            pipeline_id="pipeline-1",
        )
        assert request.layout_fingerprint == "a" * 64
        assert request.client_doc_hash == "b" * 64


class TestCorrectionRule:
    """Tests for CorrectionRule validation."""

    def test_valid_correction_rule(self):
        """Valid correction rule should be created."""
        rule = CorrectionRule(
            field="total",
            rule="sum_line_items",
            parameters={"tolerance": 0.01},
        )
        assert rule.field == "total"
        assert rule.rule == "sum_line_items"

    def test_parameters_optional(self):
        """Parameters should be optional."""
        rule = CorrectionRule(field="date", rule="iso8601_normalize")
        assert rule.parameters is None

    def test_wildcard_field(self):
        """Wildcard field should be allowed."""
        rule = CorrectionRule(field="*", rule="cross_field_validation")
        assert rule.field == "*"

    def test_field_max_length(self):
        """Field has max length of 100."""
        with pytest.raises(ValidationError):
            CorrectionRule(field="x" * 101, rule="test")


class TestEnums:
    """Tests for enum types."""

    def test_decision_enum_values(self):
        """Decision enum should have expected values."""
        assert Decision.MATCH.value == "MATCH"
        assert Decision.REVIEW.value == "REVIEW"
        assert Decision.NEW.value == "NEW"
        assert Decision.REJECT.value == "REJECT"

    def test_template_status_enum_values(self):
        """TemplateStatus enum should have expected values."""
        assert TemplateStatus.ACTIVE.value == "active"
        assert TemplateStatus.DEPRECATED.value == "deprecated"
        assert TemplateStatus.REVIEW.value == "review"


class TestTemplateCreate:
    """Tests for TemplateCreate validation."""

    @pytest.fixture
    def valid_structural_features(self):
        """Create valid structural features."""
        return StructuralFeatures(
            element_count=45,
            table_count=2,
            text_block_count=30,
            image_count=3,
            page_count=1,
            text_density=0.45,
            layout_complexity=0.32,
            column_count=2,
            has_header=True,
            has_footer=True,
            bounding_boxes=[],
        )

    def test_valid_template_create(self, valid_structural_features):
        """Valid template create should be created."""
        template = TemplateCreate(
            template_id="INV-ACME-001",
            version="1.0",
            structural_features=valid_structural_features,
        )
        assert template.template_id == "INV-ACME-001"
        assert template.baseline_reliability == 0.85  # Default

    def test_baseline_reliability_bounds(self, valid_structural_features):
        """Baseline reliability must be between 0 and 1."""
        with pytest.raises(ValidationError):
            TemplateCreate(
                template_id="test",
                version="1.0",
                structural_features=valid_structural_features,
                baseline_reliability=1.5,  # Invalid
            )

    def test_template_id_max_length(self, valid_structural_features):
        """Template ID has max length of 255."""
        with pytest.raises(ValidationError):
            TemplateCreate(
                template_id="x" * 256,  # Too long
                version="1.0",
                structural_features=valid_structural_features,
            )


class TestEvaluateResponse:
    """Tests for EvaluateResponse validation."""

    def test_valid_evaluate_response(self):
        """Valid evaluate response should be created."""
        from uuid_extensions import uuid7

        response = EvaluateResponse(
            decision=Decision.MATCH,
            template_version_id="tmpl-001:1.0",
            drift_score=0.15,
            reliability_score=0.88,
            correction_rules=[],
            replay_hash="abc123",
            evaluation_id=uuid7(),
            alerts=[],
        )
        assert response.decision == Decision.MATCH
        assert response.drift_score == 0.15

    def test_score_bounds(self):
        """Scores must be between 0 and 1."""
        from uuid_extensions import uuid7

        with pytest.raises(ValidationError):
            EvaluateResponse(
                decision=Decision.MATCH,
                drift_score=1.5,  # Invalid
                reliability_score=0.88,
                replay_hash="abc",
                evaluation_id=uuid7(),
            )
