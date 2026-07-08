"""Integration tests for the outcome-feedback loop and calibration analytics.

Require Postgres (run in CI). Exercises: evaluate -> feedback -> calibration.
The fixture request matches no template, so decisions are NEW (flagged), which
drives the review_catch_rate / errors_caught path.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient


async def _evaluate(client: AsyncClient, payload: dict) -> str:
    resp = await client.post("/v1/evaluate", json=payload)
    assert resp.status_code == 200
    return resp.json()["evaluation_id"]


class TestFeedbackAuth:
    @pytest.mark.asyncio
    async def test_feedback_requires_auth(self, test_client: AsyncClient):
        resp = await test_client.post(
            f"/v1/evaluations/{uuid4()}/feedback", json={"outcome": "correct"}
        )
        assert resp.status_code == 401


class TestFeedback:
    @pytest.mark.asyncio
    async def test_feedback_unknown_evaluation_404(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            f"/v1/evaluations/{uuid4()}/feedback", json={"outcome": "correct"}
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_feedback_invalid_outcome_rejected(
        self, authenticated_client: AsyncClient, valid_evaluate_request_data: dict
    ):
        evaluation_id = await _evaluate(authenticated_client, valid_evaluate_request_data)
        resp = await authenticated_client.post(
            f"/v1/evaluations/{evaluation_id}/feedback", json={"outcome": "banana"}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_feedback_recorded_and_updated(
        self, authenticated_client: AsyncClient, valid_evaluate_request_data: dict
    ):
        evaluation_id = await _evaluate(authenticated_client, valid_evaluate_request_data)

        # First submission records the outcome.
        resp = await authenticated_client.post(
            f"/v1/evaluations/{evaluation_id}/feedback",
            json={"outcome": "corrected", "field_error_count": 3, "source": "human_review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "corrected"
        assert data["field_error_count"] == 3
        assert data["updated_at"] is None

        # Resubmission updates in place (no duplicate row).
        resp = await authenticated_client.post(
            f"/v1/evaluations/{evaluation_id}/feedback",
            json={"outcome": "correct", "source": "reconciliation"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "correct"
        assert data["updated_at"] is not None


class TestCalibrationAnalytics:
    @pytest.mark.asyncio
    async def test_calibration_empty(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/v1/analytics/calibration")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_evaluations"] == 0
        assert data["feedback_count"] == 0
        assert data["feedback_coverage"] is None
        assert data["errors_caught"] == 0
        assert data["reliability_bands"] == []

    @pytest.mark.asyncio
    async def test_calibration_reflects_outcomes(
        self, authenticated_client: AsyncClient, valid_evaluate_request_data: dict
    ):
        # Three flagged (NEW) evaluations: two confirmed bad, one fine.
        ids = [await _evaluate(authenticated_client, valid_evaluate_request_data) for _ in range(3)]
        outcomes = ["corrected", "rejected", "correct"]
        for evaluation_id, outcome in zip(ids, outcomes, strict=True):
            resp = await authenticated_client.post(
                f"/v1/evaluations/{evaluation_id}/feedback", json={"outcome": outcome}
            )
            assert resp.status_code == 200

        resp = await authenticated_client.get("/v1/analytics/calibration")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_evaluations"] == 3
        assert data["feedback_count"] == 3
        assert data["feedback_coverage"] == 1.0
        # Fixture request matches no template -> all decisions are NEW (flagged).
        assert data["auto_process_precision"] is None
        assert data["review_catch_rate"] == pytest.approx(2 / 3)
        assert data["errors_caught"] == 2
        assert data["missed_errors"] == 0
        assert data["decision_outcomes"]["NEW"]["corrected"] == 1
        assert data["decision_outcomes"]["NEW"]["rejected"] == 1
        assert data["decision_outcomes"]["NEW"]["correct"] == 1
        # Reliability bands cover the three evaluations with feedback.
        assert sum(b["total"] for b in data["reliability_bands"]) == 3


class TestReliabilityLearning:
    """Feedback moves the matched template's baseline_reliability (EWMA)."""

    async def _register_and_match(
        self, client: AsyncClient, features: dict, template_id: str
    ) -> tuple[str, str]:
        """Register a template, then evaluate the same features (exact MATCH)."""
        import hashlib

        from src.models import StructuralFeatures

        resp = await client.post(
            "/v1/templates",
            json={
                "template_id": template_id,
                "version": "1.0",
                "structural_features": features,
                "baseline_reliability": 0.85,
                "correction_rules": [],
            },
        )
        assert resp.status_code in (200, 201), resp.text
        template_uuid = resp.json()["id"]

        # Server-side fingerprint: sha256 of the pydantic model JSON.
        fingerprint = hashlib.sha256(
            StructuralFeatures.model_validate(features).model_dump_json().encode()
        ).hexdigest()
        resp = await client.post(
            "/v1/evaluate",
            json={
                "layout_fingerprint": fingerprint,
                "structural_features": features,
                "extractor_metadata": {
                    "vendor": "aws",
                    "model": "textract",
                    "version": "1",
                    "confidence": 0.95,
                    "latency_ms": 100,
                    "cost_usd": 0.001,
                },
                "client_doc_hash": "b" * 64,
                "client_correlation_id": "rel-learn-1",
                "pipeline_id": "rel-learn-pipeline",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["decision"] == "MATCH"
        return data["evaluation_id"], template_uuid

    async def _baseline(self, client: AsyncClient, template_uuid: str) -> float:
        resp = await client.get(f"/v1/templates/{template_uuid}")
        assert resp.status_code == 200
        return resp.json()["baseline_reliability"]

    @pytest.mark.asyncio
    async def test_feedback_moves_baseline_and_replay_is_noop(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        features = valid_evaluate_request_data["structural_features"]
        evaluation_id, template_uuid = await self._register_and_match(
            authenticated_client, features, "REL-LEARN-001"
        )

        # First feedback (rejected) moves the baseline one EWMA step down.
        resp = await authenticated_client.post(
            f"/v1/evaluations/{evaluation_id}/feedback", json={"outcome": "rejected"}
        )
        assert resp.status_code == 200
        after_first = await self._baseline(authenticated_client, template_uuid)
        assert after_first == pytest.approx(0.85 * 0.95, abs=1e-4)  # rate 0.05, target 0.0

        # Identical resubmission is a no-op (anti-ratchet).
        resp = await authenticated_client.post(
            f"/v1/evaluations/{evaluation_id}/feedback", json={"outcome": "rejected"}
        )
        assert resp.status_code == 200
        assert await self._baseline(authenticated_client, template_uuid) == pytest.approx(
            after_first, abs=1e-6
        )

        # Changing the outcome applies exactly one step toward the new target.
        resp = await authenticated_client.post(
            f"/v1/evaluations/{evaluation_id}/feedback", json={"outcome": "correct"}
        )
        assert resp.status_code == 200
        after_change = await self._baseline(authenticated_client, template_uuid)
        assert after_change == pytest.approx(after_first * 0.95 + 0.05 * 1.0, abs=1e-4)

    @pytest.mark.asyncio
    async def test_unmatched_evaluation_feedback_is_noop_for_baselines(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        """NEW-decision evaluations (no template) accept feedback without error."""
        resp = await authenticated_client.post("/v1/evaluate", json=valid_evaluate_request_data)
        assert resp.status_code == 200
        assert resp.json()["decision"] == "NEW"
        evaluation_id = resp.json()["evaluation_id"]

        resp = await authenticated_client.post(
            f"/v1/evaluations/{evaluation_id}/feedback", json={"outcome": "rejected"}
        )
        assert resp.status_code == 200


class TestRejectDecision:
    """Safeguard ERROR strings drive the (previously unreachable) REJECT decision."""

    @pytest.mark.asyncio
    async def test_zero_elements_rejects(
        self, authenticated_client: AsyncClient, valid_evaluate_request_data: dict
    ):
        payload = dict(valid_evaluate_request_data)
        payload["structural_features"] = {
            **payload["structural_features"],
            "element_count": 0,
            "table_count": 0,
            "text_block_count": 0,
            "image_count": 0,
            "bounding_boxes": [],
        }

        resp = await authenticated_client.post("/v1/evaluate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "REJECT"
        assert data["drift_score"] == 0.0
        assert data["reliability_score"] == 0.0
        assert data["correction_rules"] == []
        assert any(a.startswith("ERROR:") for a in data["alerts"])

        # The rejected evaluation is persisted (audit trail is the product).
        resp = await authenticated_client.get(f"/v1/evaluations/{data['evaluation_id']}")
        assert resp.status_code == 200
        assert resp.json()["decision"] == "REJECT"
