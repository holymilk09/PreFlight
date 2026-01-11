"""Document processing workflow using Temporal.

This workflow orchestrates the document evaluation process with
durable execution and automatic retries.
"""

import hashlib
from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.models import Decision
    from src.workflows.activities import (
        ComputeDriftInput,
        ComputeReliabilityInput,
        MatchTemplateInput,
        MatchTemplateOutput,
        SelectRulesInput,
        compute_drift_activity,
        compute_reliability_activity,
        match_template_activity,
        select_rules_activity,
    )


# -----------------------------------------------------------------------------
# Workflow Input/Output
# -----------------------------------------------------------------------------


@dataclass
class DocumentProcessingInput:
    """Input for document processing workflow."""

    fingerprint: str
    structural_features: dict  # StructuralFeatures as dict
    extractor_metadata: dict  # ExtractorMetadata as dict
    tenant_id: str  # UUID as string
    client_doc_hash: str
    client_correlation_id: str


@dataclass
class DocumentProcessingOutput:
    """Output from document processing workflow."""

    decision: str  # Decision enum value
    template_version_id: str | None
    drift_score: float
    reliability_score: float
    correction_rules: list[dict]
    replay_hash: str
    alerts: list[str]


# -----------------------------------------------------------------------------
# Workflow Definition
# -----------------------------------------------------------------------------


@workflow.defn
class DocumentProcessingWorkflow:
    """Main workflow for document evaluation.

    This workflow orchestrates:
    1. Template matching
    2. Drift detection
    3. Reliability scoring
    4. Correction rule selection

    Each step is an activity with automatic retries and timeouts.
    """

    @workflow.run
    async def run(self, input: DocumentProcessingInput) -> DocumentProcessingOutput:
        """Execute the document processing workflow."""

        # Define retry policy for activities
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
        )

        # Step 1: Match template
        match_result: MatchTemplateOutput = await workflow.execute_activity(
            match_template_activity,
            MatchTemplateInput(
                fingerprint=input.fingerprint,
                features=input.structural_features,
                tenant_id=input.tenant_id,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        # Step 2: Determine decision based on match confidence
        if not match_result.matched or match_result.confidence < 0.50:
            # NEW: No template match found
            return DocumentProcessingOutput(
                decision=Decision.NEW.value,
                template_version_id=None,
                drift_score=0.0,
                reliability_score=0.0,
                correction_rules=[],
                replay_hash=self._generate_replay_hash(
                    input.client_doc_hash, Decision.NEW.value
                ),
                alerts=[],
            )

        # We have a template match - compute drift and reliability
        template_data = match_result.template_data

        # Step 3: Compute drift score
        drift_score: float = await workflow.execute_activity(
            compute_drift_activity,
            ComputeDriftInput(
                template_data=template_data,
                current_features=input.structural_features,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        # Step 4: Compute reliability score
        reliability_score: float = await workflow.execute_activity(
            compute_reliability_activity,
            ComputeReliabilityInput(
                template_data=template_data,
                extractor=input.extractor_metadata,
                drift_score=drift_score,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        # Step 5: Select correction rules
        correction_rules: list[dict] = await workflow.execute_activity(
            select_rules_activity,
            SelectRulesInput(
                template_data=template_data,
                reliability_score=reliability_score,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        # Step 6: Determine final decision
        if match_result.confidence >= 0.85:
            decision = Decision.MATCH
        else:
            decision = Decision.REVIEW

        # Build template version ID
        template_version_id = f"{template_data['template_id']}:{template_data['version']}"

        # Build alerts
        alerts = []
        if drift_score > 0.30:
            alerts.append(f"High drift detected: {drift_score:.2f}")
        if reliability_score < 0.80:
            alerts.append(f"Low reliability: {reliability_score:.2f}")

        return DocumentProcessingOutput(
            decision=decision.value,
            template_version_id=template_version_id,
            drift_score=drift_score,
            reliability_score=reliability_score,
            correction_rules=correction_rules,
            replay_hash=self._generate_replay_hash(
                input.client_doc_hash, decision.value
            ),
            alerts=alerts,
        )

    def _generate_replay_hash(self, doc_hash: str, decision: str) -> str:
        """Generate a deterministic replay hash."""
        # Use workflow info for unique but deterministic ID
        workflow_id = workflow.info().workflow_id
        return hashlib.sha256(
            f"{workflow_id}:{doc_hash}:{decision}".encode()
        ).hexdigest()
