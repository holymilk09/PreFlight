"""Unit tests for Temporal workflows."""

import pytest
from uuid_extensions import uuid7

from src.models import Decision, TemplateStatus
from src.workflows.activities import (
    ComputeDriftInput,
    ComputeReliabilityInput,
    MatchTemplateInput,
    MatchTemplateOutput,
    SelectRulesInput,
    _dict_to_template,
    _template_to_dict,
)
from src.workflows.document_processing import (
    DocumentProcessingInput,
    DocumentProcessingOutput,
)
from src.workflows.worker import TASK_QUEUE


class TestActivityDataClasses:
    """Test activity input/output data classes."""

    def test_match_template_input(self):
        """MatchTemplateInput should serialize correctly."""
        input_data = MatchTemplateInput(
            fingerprint="a" * 64,
            features={"element_count": 10},
            tenant_id=str(uuid7()),
        )
        assert input_data.fingerprint == "a" * 64
        assert input_data.features["element_count"] == 10

    def test_match_template_output_matched(self):
        """MatchTemplateOutput should handle matched case."""
        output = MatchTemplateOutput(
            matched=True,
            template_id=str(uuid7()),
            template_data={"template_id": "TEST"},
            confidence=0.95,
        )
        assert output.matched is True
        assert output.confidence == 0.95

    def test_match_template_output_not_matched(self):
        """MatchTemplateOutput should handle not matched case."""
        output = MatchTemplateOutput(
            matched=False,
            template_id=None,
            template_data=None,
            confidence=0.0,
        )
        assert output.matched is False
        assert output.template_id is None

    def test_compute_drift_input(self):
        """ComputeDriftInput should serialize correctly."""
        input_data = ComputeDriftInput(
            template_data={"template_id": "TEST"},
            current_features={"element_count": 10},
        )
        assert input_data.template_data["template_id"] == "TEST"

    def test_compute_reliability_input(self):
        """ComputeReliabilityInput should serialize correctly."""
        input_data = ComputeReliabilityInput(
            template_data={"template_id": "TEST"},
            extractor={"vendor": "nvidia", "model": "nemotron"},
            drift_score=0.15,
        )
        assert input_data.drift_score == 0.15

    def test_select_rules_input(self):
        """SelectRulesInput should serialize correctly."""
        input_data = SelectRulesInput(
            template_data={"template_id": "TEST"},
            reliability_score=0.85,
        )
        assert input_data.reliability_score == 0.85


class TestTemplateConversion:
    """Test template serialization helpers."""

    @pytest.fixture
    def sample_template(self, sample_structural_features):
        """Create a sample template for testing."""
        from src.models import Template

        return Template(
            id=uuid7(),
            tenant_id=uuid7(),
            template_id="TEST-TEMPLATE",
            version="1.0",
            fingerprint="a" * 64,
            structural_features=sample_structural_features.model_dump(),
            baseline_reliability=0.85,
            correction_rules=[{"field": "total", "rule": "sum_line_items"}],
            status=TemplateStatus.ACTIVE,
        )

    def test_template_to_dict(self, sample_template):
        """_template_to_dict should serialize all fields."""
        result = _template_to_dict(sample_template)

        assert result["template_id"] == "TEST-TEMPLATE"
        assert result["version"] == "1.0"
        assert result["fingerprint"] == "a" * 64
        assert result["baseline_reliability"] == 0.85
        assert result["status"] == "active"
        assert "id" in result
        assert "tenant_id" in result

    def test_dict_to_template(self, sample_template):
        """_dict_to_template should deserialize back to Template."""
        data = _template_to_dict(sample_template)
        result = _dict_to_template(data)

        assert result.template_id == "TEST-TEMPLATE"
        assert result.version == "1.0"
        assert result.baseline_reliability == 0.85
        assert result.status == TemplateStatus.ACTIVE

    def test_roundtrip_conversion(self, sample_template):
        """Template should survive dict roundtrip."""
        data = _template_to_dict(sample_template)
        result = _dict_to_template(data)

        assert str(result.id) == str(sample_template.id)
        assert result.template_id == sample_template.template_id
        assert result.version == sample_template.version


class TestWorkflowInputOutput:
    """Test workflow input/output data classes."""

    def test_document_processing_input(self):
        """DocumentProcessingInput should serialize correctly."""
        input_data = DocumentProcessingInput(
            fingerprint="a" * 64,
            structural_features={"element_count": 10},
            extractor_metadata={"vendor": "nvidia"},
            tenant_id=str(uuid7()),
            client_doc_hash="b" * 64,
            client_correlation_id="test-123",
        )
        assert input_data.fingerprint == "a" * 64
        assert input_data.client_correlation_id == "test-123"

    def test_document_processing_output_match(self):
        """DocumentProcessingOutput should handle MATCH decision."""
        output = DocumentProcessingOutput(
            decision=Decision.MATCH.value,
            template_version_id="TEST:1.0",
            drift_score=0.10,
            reliability_score=0.92,
            correction_rules=[{"field": "total", "rule": "sum_line_items"}],
            replay_hash="c" * 64,
            alerts=[],
        )
        assert output.decision == "MATCH"
        assert output.template_version_id == "TEST:1.0"
        assert len(output.alerts) == 0

    def test_document_processing_output_new(self):
        """DocumentProcessingOutput should handle NEW decision."""
        output = DocumentProcessingOutput(
            decision=Decision.NEW.value,
            template_version_id=None,
            drift_score=0.0,
            reliability_score=0.0,
            correction_rules=[],
            replay_hash="c" * 64,
            alerts=[],
        )
        assert output.decision == "NEW"
        assert output.template_version_id is None

    def test_document_processing_output_with_alerts(self):
        """DocumentProcessingOutput should include alerts."""
        output = DocumentProcessingOutput(
            decision=Decision.REVIEW.value,
            template_version_id="TEST:1.0",
            drift_score=0.45,
            reliability_score=0.65,
            correction_rules=[],
            replay_hash="c" * 64,
            alerts=["High drift detected: 0.45", "Low reliability: 0.65"],
        )
        assert output.decision == "REVIEW"
        assert len(output.alerts) == 2


class TestWorkerConfiguration:
    """Test worker configuration."""

    def test_task_queue_name(self):
        """Task queue should be 'preflight-tasks'."""
        assert TASK_QUEUE == "preflight-tasks"

    def test_worker_imports(self):
        """Worker should import all required components."""
        from src.workflows.worker import (
            TASK_QUEUE,
            create_worker,
            run_worker,
        )

        # Verify all components are importable
        assert TASK_QUEUE == "preflight-tasks"
        assert callable(create_worker)
        assert callable(run_worker)


class TestWorkflowModuleExports:
    """Test module exports."""

    def test_init_exports(self):
        """__init__.py should export all public components."""
        from src.workflows import (
            DocumentProcessingWorkflow,
            compute_drift_activity,
            compute_reliability_activity,
            match_template_activity,
            select_rules_activity,
        )

        # Verify exports exist
        assert DocumentProcessingWorkflow is not None
        assert callable(match_template_activity)
        assert callable(compute_drift_activity)
        assert callable(compute_reliability_activity)
        assert callable(select_rules_activity)


class TestActivityDefinitions:
    """Test that activities are properly decorated."""

    def test_match_template_activity_is_activity(self):
        """match_template_activity should be a Temporal activity."""
        from src.workflows.activities import match_template_activity

        # Check it has the activity decorator applied
        assert hasattr(match_template_activity, "__temporal_activity_definition")

    def test_compute_drift_activity_is_activity(self):
        """compute_drift_activity should be a Temporal activity."""
        from src.workflows.activities import compute_drift_activity

        assert hasattr(compute_drift_activity, "__temporal_activity_definition")

    def test_compute_reliability_activity_is_activity(self):
        """compute_reliability_activity should be a Temporal activity."""
        from src.workflows.activities import compute_reliability_activity

        assert hasattr(compute_reliability_activity, "__temporal_activity_definition")

    def test_select_rules_activity_is_activity(self):
        """select_rules_activity should be a Temporal activity."""
        from src.workflows.activities import select_rules_activity

        assert hasattr(select_rules_activity, "__temporal_activity_definition")


class TestWorkflowDefinition:
    """Test workflow definition."""

    def test_document_processing_workflow_is_workflow(self):
        """DocumentProcessingWorkflow should be a Temporal workflow."""
        from src.workflows.document_processing import DocumentProcessingWorkflow

        # Check it has the workflow decorator applied
        assert hasattr(DocumentProcessingWorkflow, "__temporal_workflow_definition")

    def test_workflow_has_run_method(self):
        """DocumentProcessingWorkflow should have a run method."""
        from src.workflows.document_processing import DocumentProcessingWorkflow

        assert hasattr(DocumentProcessingWorkflow, "run")
