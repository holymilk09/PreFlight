"""Tests for API response mappers."""

from datetime import datetime

import pytest
from uuid_extensions import uuid7

from src.api.mappers import create_evaluation, evaluation_to_record, template_to_response
from src.models import (
    CorrectionRule,
    Decision,
    Evaluation,
    EvaluationRecord,
    ExtractorMetadata,
    ExtractorProvider,
    Template,
    TemplateResponse,
    TemplateStatus,
)


class TestEvaluationToRecord:
    """Tests for evaluation_to_record mapper."""

    @pytest.fixture
    def sample_evaluation(self) -> Evaluation:
        """Create a sample Evaluation model."""
        return Evaluation(
            id=uuid7(),
            tenant_id=uuid7(),
            correlation_id="test-corr-123",
            document_hash="a" * 64,
            template_id=uuid7(),
            decision=Decision.MATCH,
            match_confidence=0.92,
            drift_score=0.12,
            reliability_score=0.88,
            correction_rules=[
                {"field": "total", "rule": "validate_sum", "parameters": None}
            ],
            extractor_vendor="nvidia",
            extractor_model="nemotron-parse",
            extractor_version="1.2.0",
            extractor_confidence=0.95,
            extractor_latency_ms=234,
            extractor_cost_usd=0.002,
            validation_warnings=["Warning: high drift area"],
            processing_time_ms=45,
            created_at=datetime.utcnow(),
        )

    def test_basic_mapping(self, sample_evaluation: Evaluation):
        """Test basic field mapping."""
        record = evaluation_to_record(sample_evaluation)

        assert isinstance(record, EvaluationRecord)
        assert record.id == sample_evaluation.id
        assert record.correlation_id == sample_evaluation.correlation_id
        assert record.document_hash == sample_evaluation.document_hash
        assert record.template_id == sample_evaluation.template_id
        assert record.decision == sample_evaluation.decision
        assert record.match_confidence == sample_evaluation.match_confidence
        assert record.drift_score == sample_evaluation.drift_score
        assert record.reliability_score == sample_evaluation.reliability_score
        assert record.extractor_vendor == sample_evaluation.extractor_vendor
        assert record.extractor_model == sample_evaluation.extractor_model
        assert record.extractor_version == sample_evaluation.extractor_version
        assert record.extractor_confidence == sample_evaluation.extractor_confidence
        assert record.extractor_latency_ms == sample_evaluation.extractor_latency_ms
        assert record.processing_time_ms == sample_evaluation.processing_time_ms
        assert record.created_at == sample_evaluation.created_at

    def test_template_version_id_included(self, sample_evaluation: Evaluation):
        """Test that template_version_id is included when provided."""
        template_version = "invoice-v1:2.0"
        record = evaluation_to_record(sample_evaluation, template_version)

        assert record.template_version_id == template_version

    def test_template_version_id_none(self, sample_evaluation: Evaluation):
        """Test that template_version_id is None when not provided."""
        record = evaluation_to_record(sample_evaluation)

        assert record.template_version_id is None

    def test_correction_rules_converted(self, sample_evaluation: Evaluation):
        """Test that correction_rules are converted to CorrectionRule models."""
        record = evaluation_to_record(sample_evaluation)

        assert len(record.correction_rules) == 1
        assert isinstance(record.correction_rules[0], CorrectionRule)
        assert record.correction_rules[0].field == "total"
        assert record.correction_rules[0].rule == "validate_sum"

    def test_empty_correction_rules(self, sample_evaluation: Evaluation):
        """Test handling of empty correction_rules."""
        sample_evaluation.correction_rules = []
        record = evaluation_to_record(sample_evaluation)

        assert record.correction_rules == []

    def test_none_correction_rules(self, sample_evaluation: Evaluation):
        """Test handling of None correction_rules."""
        sample_evaluation.correction_rules = None  # type: ignore
        record = evaluation_to_record(sample_evaluation)

        assert record.correction_rules == []

    def test_validation_warnings_preserved(self, sample_evaluation: Evaluation):
        """Test that validation_warnings are preserved."""
        record = evaluation_to_record(sample_evaluation)

        assert record.validation_warnings == sample_evaluation.validation_warnings

    def test_empty_validation_warnings(self, sample_evaluation: Evaluation):
        """Test handling of empty validation_warnings."""
        sample_evaluation.validation_warnings = []
        record = evaluation_to_record(sample_evaluation)

        assert record.validation_warnings == []

    def test_none_validation_warnings(self, sample_evaluation: Evaluation):
        """Test handling of None validation_warnings."""
        sample_evaluation.validation_warnings = None  # type: ignore
        record = evaluation_to_record(sample_evaluation)

        assert record.validation_warnings == []


class TestTemplateToResponse:
    """Tests for template_to_response mapper."""

    @pytest.fixture
    def sample_template(self) -> Template:
        """Create a sample Template model."""
        return Template(
            id=uuid7(),
            tenant_id=uuid7(),
            template_id="INV-ACME-001",
            version="2.0",
            fingerprint="b" * 64,
            structural_features={"element_count": 45},
            baseline_reliability=0.88,
            correction_rules=[
                {"field": "total", "rule": "validate_sum", "parameters": None},
                {"field": "date", "rule": "iso8601_format", "parameters": {"format": "YYYY-MM-DD"}},
            ],
            status=TemplateStatus.ACTIVE,
            created_at=datetime.utcnow(),
            created_by=uuid7(),
        )

    def test_basic_mapping(self, sample_template: Template):
        """Test basic field mapping."""
        response = template_to_response(sample_template)

        assert isinstance(response, TemplateResponse)
        assert response.id == sample_template.id
        assert response.template_id == sample_template.template_id
        assert response.version == sample_template.version
        assert response.fingerprint == sample_template.fingerprint
        assert response.baseline_reliability == sample_template.baseline_reliability
        assert response.status == sample_template.status
        assert response.created_at == sample_template.created_at

    def test_include_rules_false(self, sample_template: Template):
        """Test that correction_rules are empty when include_rules=False."""
        response = template_to_response(sample_template, include_rules=False)

        assert response.correction_rules == []

    def test_include_rules_true(self, sample_template: Template):
        """Test that correction_rules are included when include_rules=True."""
        response = template_to_response(sample_template, include_rules=True)

        assert len(response.correction_rules) == 2
        assert isinstance(response.correction_rules[0], CorrectionRule)
        assert response.correction_rules[0].field == "total"
        assert response.correction_rules[1].field == "date"
        assert response.correction_rules[1].parameters == {"format": "YYYY-MM-DD"}

    def test_empty_correction_rules_with_include(self, sample_template: Template):
        """Test handling of empty correction_rules when include_rules=True."""
        sample_template.correction_rules = []
        response = template_to_response(sample_template, include_rules=True)

        assert response.correction_rules == []

    def test_none_correction_rules_with_include(self, sample_template: Template):
        """Test handling of None correction_rules when include_rules=True."""
        sample_template.correction_rules = None  # type: ignore
        response = template_to_response(sample_template, include_rules=True)

        assert response.correction_rules == []

    def test_default_include_rules_is_false(self, sample_template: Template):
        """Test that include_rules defaults to False."""
        response = template_to_response(sample_template)

        assert response.correction_rules == []


class TestCreateEvaluation:
    """Tests for create_evaluation factory."""

    @pytest.fixture
    def extractor_metadata(self) -> ExtractorMetadata:
        """Create sample extractor metadata."""
        return ExtractorMetadata(
            vendor="nvidia",
            model="nemotron-parse",
            version="1.2.0",
            confidence=0.95,
            latency_ms=234,
            cost_usd=0.002,
        )

    @pytest.fixture
    def provider(self) -> ExtractorProvider:
        """Create sample provider."""
        return ExtractorProvider(
            id=uuid7(),
            vendor="nvidia",
            display_name="NVIDIA Nemotron",
            confidence_multiplier=1.0,
            drift_sensitivity=1.0,
            supported_element_types=["text", "table"],
            typical_latency_ms=250,
            is_active=True,
            is_known=True,
        )

    @pytest.fixture
    def correction_rules(self) -> list[CorrectionRule]:
        """Create sample correction rules."""
        return [
            CorrectionRule(field="total", rule="validate_sum", parameters=None),
        ]

    def test_basic_creation(
        self,
        extractor_metadata: ExtractorMetadata,
        provider: ExtractorProvider,
        correction_rules: list[CorrectionRule],
    ):
        """Test basic Evaluation creation."""
        eval_id = uuid7()
        tenant_id = uuid7()
        template_id = uuid7()

        evaluation = create_evaluation(
            evaluation_id=eval_id,
            tenant_id=tenant_id,
            correlation_id="test-corr-123",
            document_hash="a" * 64,
            template_id=template_id,
            decision=Decision.MATCH,
            match_confidence=0.92,
            drift_score=0.12,
            reliability_score=0.88,
            correction_rules=correction_rules,
            extractor=extractor_metadata,
            provider=provider,
            validation_warnings=["test warning"],
            processing_time_ms=45,
        )

        assert isinstance(evaluation, Evaluation)
        assert evaluation.id == eval_id
        assert evaluation.tenant_id == tenant_id
        assert evaluation.correlation_id == "test-corr-123"
        assert evaluation.document_hash == "a" * 64
        assert evaluation.template_id == template_id
        assert evaluation.decision == Decision.MATCH
        assert evaluation.match_confidence == 0.92
        assert evaluation.drift_score == 0.12
        assert evaluation.reliability_score == 0.88
        assert evaluation.extractor_vendor == "nvidia"
        assert evaluation.extractor_model == "nemotron-parse"
        assert evaluation.extractor_version == "1.2.0"
        assert evaluation.extractor_confidence == 0.95
        assert evaluation.extractor_latency_ms == 234
        assert evaluation.extractor_cost_usd == 0.002
        assert evaluation.provider_id == provider.id
        assert evaluation.validation_warnings == ["test warning"]
        assert evaluation.processing_time_ms == 45

    def test_correction_rules_serialized(
        self,
        extractor_metadata: ExtractorMetadata,
        provider: ExtractorProvider,
        correction_rules: list[CorrectionRule],
    ):
        """Test that correction_rules are serialized to dicts."""
        evaluation = create_evaluation(
            evaluation_id=uuid7(),
            tenant_id=uuid7(),
            correlation_id="test",
            document_hash="a" * 64,
            template_id=None,
            decision=Decision.NEW,
            match_confidence=None,
            drift_score=0.0,
            reliability_score=0.75,
            correction_rules=correction_rules,
            extractor=extractor_metadata,
            provider=provider,
            validation_warnings=[],
            processing_time_ms=30,
        )

        assert len(evaluation.correction_rules) == 1
        assert isinstance(evaluation.correction_rules[0], dict)
        assert evaluation.correction_rules[0]["field"] == "total"
        assert evaluation.correction_rules[0]["rule"] == "validate_sum"

    def test_no_provider(
        self,
        extractor_metadata: ExtractorMetadata,
        correction_rules: list[CorrectionRule],
    ):
        """Test creation without provider (unknown vendor)."""
        evaluation = create_evaluation(
            evaluation_id=uuid7(),
            tenant_id=uuid7(),
            correlation_id="test",
            document_hash="a" * 64,
            template_id=None,
            decision=Decision.NEW,
            match_confidence=None,
            drift_score=0.0,
            reliability_score=0.65,
            correction_rules=[],
            extractor=extractor_metadata,
            provider=None,
            validation_warnings=["Unknown provider"],
            processing_time_ms=25,
        )

        assert evaluation.provider_id is None

    def test_no_template(
        self,
        extractor_metadata: ExtractorMetadata,
        provider: ExtractorProvider,
    ):
        """Test creation for NEW decision (no template)."""
        evaluation = create_evaluation(
            evaluation_id=uuid7(),
            tenant_id=uuid7(),
            correlation_id="test",
            document_hash="a" * 64,
            template_id=None,
            decision=Decision.NEW,
            match_confidence=None,
            drift_score=0.0,
            reliability_score=0.70,
            correction_rules=[],
            extractor=extractor_metadata,
            provider=provider,
            validation_warnings=[],
            processing_time_ms=20,
        )

        assert evaluation.template_id is None
        assert evaluation.match_confidence is None
        assert evaluation.decision == Decision.NEW
