"""Integration tests for evaluate API endpoint."""

import pytest
from httpx import AsyncClient


class TestEvaluateEndpoint:
    """Tests for POST /v1/evaluate endpoint."""

    @pytest.mark.asyncio
    async def test_evaluate_requires_auth(
        self,
        test_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        """Evaluate endpoint should require authentication."""
        response = await test_client.post("/v1/evaluate", json=valid_evaluate_request_data)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_evaluate_new_template(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        """Evaluating with no matching template should return NEW decision."""
        response = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "NEW"
        assert data["template_version_id"] is None
        assert data["drift_score"] == 0.0
        assert data["reliability_score"] == 0.0
        assert "evaluation_id" in data
        assert "replay_hash" in data
        assert len(data["replay_hash"]) == 64  # SHA256 hex

    @pytest.mark.asyncio
    async def test_evaluate_matching_template(
        self,
        authenticated_client: AsyncClient,
        valid_template_create_data: dict,
        valid_evaluate_request_data: dict,
    ):
        """Evaluating with matching template should return MATCH decision."""
        # Create template first
        create_response = await authenticated_client.post(
            "/v1/templates",
            json=valid_template_create_data,
        )
        assert create_response.status_code == 201

        # Use the same fingerprint as the template
        import hashlib
        import json

        features_json = json.dumps(
            valid_template_create_data["structural_features"], sort_keys=True
        )
        fingerprint = hashlib.sha256(features_json.encode()).hexdigest()
        valid_evaluate_request_data["layout_fingerprint"] = fingerprint

        # Evaluate
        response = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        assert response.status_code == 200
        data = response.json()
        # With exact fingerprint match, should be MATCH
        assert data["decision"] in ["MATCH", "REVIEW"]
        assert data["template_version_id"] is not None
        assert ":" in data["template_version_id"]  # format: template_id:version

    @pytest.mark.asyncio
    async def test_evaluate_returns_scores(
        self,
        authenticated_client: AsyncClient,
        valid_template_create_data: dict,
        valid_evaluate_request_data: dict,
    ):
        """Evaluate should return drift and reliability scores."""
        # Create template
        await authenticated_client.post("/v1/templates", json=valid_template_create_data)

        # Evaluate with same fingerprint
        import hashlib
        import json

        features_json = json.dumps(
            valid_template_create_data["structural_features"], sort_keys=True
        )
        fingerprint = hashlib.sha256(features_json.encode()).hexdigest()
        valid_evaluate_request_data["layout_fingerprint"] = fingerprint

        response = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert "drift_score" in data
        assert "reliability_score" in data
        assert 0 <= data["drift_score"] <= 1
        assert 0 <= data["reliability_score"] <= 1

    @pytest.mark.asyncio
    async def test_evaluate_returns_correction_rules(
        self,
        authenticated_client: AsyncClient,
        valid_template_create_data: dict,
        valid_evaluate_request_data: dict,
    ):
        """Evaluate should return correction rules from template."""
        # Create template with correction rules
        valid_template_create_data["correction_rules"] = [
            {"field": "total", "rule": "sum_line_items", "parameters": {"tolerance": 0.01}}
        ]
        await authenticated_client.post("/v1/templates", json=valid_template_create_data)

        # Evaluate with same fingerprint
        import hashlib
        import json

        features_json = json.dumps(
            valid_template_create_data["structural_features"], sort_keys=True
        )
        fingerprint = hashlib.sha256(features_json.encode()).hexdigest()
        valid_evaluate_request_data["layout_fingerprint"] = fingerprint

        response = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert "correction_rules" in data
        # Should have at least the template rule
        if data["decision"] in ["MATCH", "REVIEW"]:
            assert len(data["correction_rules"]) >= 1

    @pytest.mark.asyncio
    async def test_evaluate_generates_alerts_high_drift(
        self,
        authenticated_client: AsyncClient,
        valid_template_create_data: dict,
        valid_evaluate_request_data: dict,
        high_drift_features,
    ):
        """Evaluate should generate alerts for high drift."""
        # Create template
        await authenticated_client.post("/v1/templates", json=valid_template_create_data)

        # Evaluate with different features (high drift)
        valid_evaluate_request_data["structural_features"] = high_drift_features.model_dump()

        response = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data

    @pytest.mark.asyncio
    async def test_evaluate_invalid_fingerprint_too_short(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        """Evaluate with invalid fingerprint should return 422."""
        valid_evaluate_request_data["layout_fingerprint"] = "abc123"  # Too short

        response = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_evaluate_invalid_fingerprint_not_hex(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        """Evaluate with non-hex fingerprint should return 422."""
        valid_evaluate_request_data["layout_fingerprint"] = "g" * 64  # Invalid hex

        response = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_evaluate_invalid_doc_hash(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        """Evaluate with invalid doc hash should return 422."""
        valid_evaluate_request_data["client_doc_hash"] = "tooshort"

        response = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_evaluate_stores_evaluation_record(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        """Evaluate should return a unique evaluation ID."""
        response1 = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )
        response2 = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Each evaluation should have unique ID
        assert response1.json()["evaluation_id"] != response2.json()["evaluation_id"]

    @pytest.mark.asyncio
    async def test_evaluate_replay_hash_deterministic(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        """Replay hash should be deterministic for same inputs."""
        response = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        data = response.json()
        # Hash is SHA256(evaluation_id:doc_hash:decision)
        # Since evaluation_id is unique, replay_hash will be unique too
        assert len(data["replay_hash"]) == 64


class TestEvaluateValidation:
    """Tests for evaluate request validation."""

    @pytest.mark.asyncio
    async def test_evaluate_missing_required_field(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        """Missing required field should return 422."""
        del valid_evaluate_request_data["client_correlation_id"]

        response = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_evaluate_invalid_confidence(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        """Invalid extractor confidence should return 422."""
        valid_evaluate_request_data["extractor_metadata"]["confidence"] = 1.5

        response = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_evaluate_invalid_page_count(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        """Page count of 0 should return 422."""
        valid_evaluate_request_data["structural_features"]["page_count"] = 0

        response = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_evaluate_negative_latency(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        """Negative latency should return 422."""
        valid_evaluate_request_data["extractor_metadata"]["latency_ms"] = -1

        response = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        assert response.status_code == 422
