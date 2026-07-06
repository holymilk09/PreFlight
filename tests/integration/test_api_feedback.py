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
