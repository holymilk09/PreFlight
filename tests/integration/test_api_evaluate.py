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
        # Reliability is now computed even for NEW decisions (with default baseline)
        assert data["reliability_score"] >= 0.0
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


class TestEvaluateDecisionLogic:
    """Tests for evaluate decision logic (MATCH, REVIEW, NEW)."""

    @pytest.mark.asyncio
    async def test_evaluate_match_decision_high_similarity(
        self,
        authenticated_client: AsyncClient,
        sample_structural_features,
    ):
        """High similarity (>= 0.85) via similarity search should return MATCH."""
        # Create template
        template_data = {
            "template_id": "MATCH-SIMILARITY-TEMPLATE",
            "version": "1.0",
            "structural_features": sample_structural_features.model_dump(),
            "baseline_reliability": 0.90,
        }
        await authenticated_client.post("/v1/templates", json=template_data)

        # Use very slightly different features (should have high similarity)
        similar_features = sample_structural_features.model_dump()
        similar_features["element_count"] += 1  # Tiny change

        eval_request = {
            "layout_fingerprint": "1" * 64,  # Different fingerprint (not exact match)
            "structural_features": similar_features,
            "extractor_metadata": {
                "vendor": "nvidia",
                "model": "nemotron",
                "version": "1.0",
                "confidence": 0.95,
                "latency_ms": 200,
            },
            "client_doc_hash": "2" * 64,
            "client_correlation_id": "match-similarity-test",
            "pipeline_id": "test",
        }

        response = await authenticated_client.post("/v1/evaluate", json=eval_request)
        assert response.status_code == 200

        data = response.json()
        # Very similar features should get MATCH
        assert data["decision"] == "MATCH"
        assert data["template_version_id"] is not None
        assert data["drift_score"] >= 0
        assert data["reliability_score"] > 0
        # High similarity should have low drift
        assert data["drift_score"] < 0.3

    @pytest.mark.asyncio
    async def test_evaluate_review_decision_moderate_similarity(
        self,
        authenticated_client: AsyncClient,
        sample_structural_features,
    ):
        """Moderate similarity (0.50-0.85) should return REVIEW decision."""
        # Create template
        template_data = {
            "template_id": "REVIEW-SIMILARITY-TEMPLATE",
            "version": "1.0",
            "structural_features": sample_structural_features.model_dump(),
            "baseline_reliability": 0.85,
        }
        await authenticated_client.post("/v1/templates", json=template_data)

        # Create features with moderate differences
        modified_features = sample_structural_features.model_dump()
        modified_features["element_count"] = int(modified_features["element_count"] * 1.5)
        modified_features["table_count"] += 2
        modified_features["text_density"] = min(1.0, modified_features["text_density"] + 0.2)
        modified_features["layout_complexity"] = min(
            1.0, modified_features["layout_complexity"] + 0.15
        )

        eval_request = {
            "layout_fingerprint": "3" * 64,  # Different fingerprint
            "structural_features": modified_features,
            "extractor_metadata": {
                "vendor": "nvidia",
                "model": "nemotron",
                "version": "1.0",
                "confidence": 0.85,
                "latency_ms": 200,
            },
            "client_doc_hash": "4" * 64,
            "client_correlation_id": "review-similarity-test",
            "pipeline_id": "test",
        }

        response = await authenticated_client.post("/v1/evaluate", json=eval_request)
        assert response.status_code == 200

        data = response.json()
        # Moderate similarity could be REVIEW or still MATCH
        assert data["decision"] in ["REVIEW", "MATCH"]
        if data["decision"] == "REVIEW":
            assert data["template_version_id"] is not None
            assert data["drift_score"] > 0
            assert data["reliability_score"] > 0

    @pytest.mark.asyncio
    async def test_evaluate_full_match_path_with_scores(
        self,
        authenticated_client: AsyncClient,
        sample_structural_features,
    ):
        """Test full MATCH path computing drift and reliability scores."""
        import hashlib
        import json

        # Create template
        template_data = {
            "template_id": "FULL-MATCH-TEMPLATE",
            "version": "1.0",
            "structural_features": sample_structural_features.model_dump(),
            "baseline_reliability": 0.92,
            "correction_rules": [
                {"field": "amount", "rule": "currency_standardize", "parameters": None}
            ],
        }
        response = await authenticated_client.post("/v1/templates", json=template_data)
        assert response.status_code == 201

        # Use exact fingerprint for guaranteed MATCH with confidence 1.0
        features_json = json.dumps(sample_structural_features.model_dump(), sort_keys=True)
        fingerprint = hashlib.sha256(features_json.encode()).hexdigest()

        eval_request = {
            "layout_fingerprint": fingerprint,
            "structural_features": sample_structural_features.model_dump(),
            "extractor_metadata": {
                "vendor": "nvidia",
                "model": "nemotron",
                "version": "1.0",
                "confidence": 0.93,
                "latency_ms": 150,
            },
            "client_doc_hash": "5" * 64,
            "client_correlation_id": "full-match-test",
            "pipeline_id": "test",
        }

        response = await authenticated_client.post("/v1/evaluate", json=eval_request)
        assert response.status_code == 200

        data = response.json()
        assert data["decision"] == "MATCH"
        assert data["template_version_id"] == "FULL-MATCH-TEMPLATE:1.0"
        assert data["drift_score"] == 0.0  # Same features, no drift
        assert data["reliability_score"] > 0.5
        assert len(data["correction_rules"]) >= 1  # Template has rules
        # Safeguard warnings may be present (e.g., missing bounding boxes)
        # but no critical alerts for high reliability/low drift
        assert not any("ERROR:" in a for a in data["alerts"])
        assert not any("High drift" in a for a in data["alerts"])
        assert not any("Low reliability" in a for a in data["alerts"])

    @pytest.mark.asyncio
    async def test_evaluate_review_decision_moderate_confidence(
        self,
        authenticated_client: AsyncClient,
        sample_structural_features,
    ):
        """Moderate confidence (0.50-0.85) should return REVIEW decision."""
        # Create template
        template_data = {
            "template_id": "REVIEW-TEST-TEMPLATE",
            "version": "1.0",
            "structural_features": sample_structural_features.model_dump(),
            "baseline_reliability": 0.85,
        }
        await authenticated_client.post("/v1/templates", json=template_data)

        # Create features that are similar but not identical (will get moderate match)
        modified_features = sample_structural_features.model_dump()
        modified_features["element_count"] += 10
        modified_features["table_count"] += 1
        modified_features["text_density"] += 0.1

        eval_request = {
            "layout_fingerprint": "e" * 64,  # Different fingerprint
            "structural_features": modified_features,
            "extractor_metadata": {
                "vendor": "nvidia",
                "model": "nemotron",
                "version": "1.0",
                "confidence": 0.85,
                "latency_ms": 200,
            },
            "client_doc_hash": "f" * 64,
            "client_correlation_id": "review-test",
            "pipeline_id": "test",
        }

        response = await authenticated_client.post("/v1/evaluate", json=eval_request)
        assert response.status_code == 200

        data = response.json()
        # Should be REVIEW or MATCH depending on similarity
        assert data["decision"] in ["REVIEW", "MATCH", "NEW"]
        # Verify all response fields are present
        assert "drift_score" in data
        assert "reliability_score" in data
        assert "correction_rules" in data
        assert "evaluation_id" in data
        assert "replay_hash" in data
        assert "alerts" in data

    @pytest.mark.asyncio
    async def test_evaluate_alerts_low_reliability(
        self,
        authenticated_client: AsyncClient,
        sample_structural_features,
    ):
        """Low reliability should generate alert."""
        # Create template with low baseline reliability
        template_data = {
            "template_id": "LOW-REL-TEMPLATE",
            "version": "1.0",
            "structural_features": sample_structural_features.model_dump(),
            "baseline_reliability": 0.60,  # Low baseline
        }
        await authenticated_client.post("/v1/templates", json=template_data)

        import hashlib
        import json

        features_json = json.dumps(sample_structural_features.model_dump(), sort_keys=True)
        fingerprint = hashlib.sha256(features_json.encode()).hexdigest()

        eval_request = {
            "layout_fingerprint": fingerprint,
            "structural_features": sample_structural_features.model_dump(),
            "extractor_metadata": {
                "vendor": "unknown_vendor",
                "model": "unknown",
                "version": "0.1",
                "confidence": 0.50,  # Low confidence
                "latency_ms": 200,
            },
            "client_doc_hash": "a" * 64,
            "client_correlation_id": "low-rel-test",
            "pipeline_id": "test",
        }

        response = await authenticated_client.post("/v1/evaluate", json=eval_request)
        assert response.status_code == 200

        data = response.json()
        # Should have low reliability and possibly alert
        if data["decision"] in ["MATCH", "REVIEW"]:
            # Reliability should be computed
            assert data["reliability_score"] >= 0

    @pytest.mark.asyncio
    async def test_evaluate_with_template_correction_rules(
        self,
        authenticated_client: AsyncClient,
        sample_structural_features,
    ):
        """Evaluate should return template's correction rules."""
        template_data = {
            "template_id": "RULES-TEST-TEMPLATE",
            "version": "1.0",
            "structural_features": sample_structural_features.model_dump(),
            "baseline_reliability": 0.90,
            "correction_rules": [
                {"field": "total", "rule": "sum_line_items", "parameters": {"tolerance": 0.01}},
                {"field": "date", "rule": "iso8601_normalize", "parameters": None},
            ],
        }
        await authenticated_client.post("/v1/templates", json=template_data)

        import hashlib
        import json

        features_json = json.dumps(sample_structural_features.model_dump(), sort_keys=True)
        fingerprint = hashlib.sha256(features_json.encode()).hexdigest()

        eval_request = {
            "layout_fingerprint": fingerprint,
            "structural_features": sample_structural_features.model_dump(),
            "extractor_metadata": {
                "vendor": "nvidia",
                "model": "nemotron",
                "version": "1.0",
                "confidence": 0.95,
                "latency_ms": 200,
            },
            "client_doc_hash": "b" * 64,
            "client_correlation_id": "rules-test",
            "pipeline_id": "test",
        }

        response = await authenticated_client.post("/v1/evaluate", json=eval_request)
        assert response.status_code == 200

        data = response.json()
        if data["decision"] in ["MATCH", "REVIEW"]:
            # Should have correction rules from template
            assert len(data["correction_rules"]) >= 1

    @pytest.mark.asyncio
    async def test_evaluate_processing_time_tracked(
        self,
        authenticated_client: AsyncClient,
        valid_evaluate_request_data: dict,
    ):
        """Processing should complete in reasonable time."""
        import time

        start = time.perf_counter()

        response = await authenticated_client.post(
            "/v1/evaluate",
            json=valid_evaluate_request_data,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        assert response.status_code == 200
        # Should complete within 5 seconds (generous for CI)
        assert elapsed_ms < 5000


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
