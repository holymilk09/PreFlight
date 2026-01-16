"""Unit tests for API routes logic."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from uuid_extensions import uuid7

from src.models import (
    Decision,
    EvaluateRequest,
    ExtractorMetadata,
    Template,
    TemplateStatus,
)


class TestEvaluateDecisionLogic:
    """Unit tests for evaluate endpoint decision logic."""

    @pytest.fixture
    def mock_template(self, sample_structural_features):
        """Create a mock matched template."""
        return Template(
            id=uuid7(),
            tenant_id=uuid7(),
            template_id="TEST-TEMPLATE",
            version="1.0",
            fingerprint="a" * 64,
            structural_features=sample_structural_features.model_dump(),
            baseline_reliability=0.85,
            correction_rules=[{"field": "total", "rule": "sum_line_items", "parameters": None}],
            status=TemplateStatus.ACTIVE,
        )

    @pytest.fixture
    def mock_evaluate_request(self, sample_structural_features):
        """Create a mock evaluate request."""
        features_json = sample_structural_features.model_dump_json()
        fingerprint = hashlib.sha256(features_json.encode()).hexdigest()

        return EvaluateRequest(
            layout_fingerprint=fingerprint,
            structural_features=sample_structural_features,
            extractor_metadata=ExtractorMetadata(
                vendor="nvidia",
                model="nemotron",
                version="1.0",
                confidence=0.92,
                latency_ms=200,
            ),
            client_doc_hash="b" * 64,
            client_correlation_id="test-123",
            pipeline_id="test-pipeline",
        )

    @pytest.fixture
    def mock_db_with_provider(self):
        """Create a mock DB session that returns None for provider lookup."""
        mock_db = AsyncMock()
        # Mock execute to return a result with scalar_one_or_none returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        return mock_db

    @pytest.mark.asyncio
    async def test_new_decision_when_no_template_match(
        self,
        sample_structural_features,
        mock_evaluate_request,
        mock_db_with_provider,
    ):
        """Should return NEW decision when no template matches."""
        from src.api.auth import AuthenticatedTenant

        mock_tenant = AuthenticatedTenant(
            tenant_id=uuid7(),
            tenant_name="Test",
            api_key_id=uuid7(),
            api_key_name="test-key",
            scopes=["*"],
            rate_limit=1000,
        )

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.state.request_id = str(uuid7())

        with (
            patch("src.api.routes.match_template", return_value=(None, 0.0)) as mock_match,
            patch("src.api.routes.log_evaluation_requested", new_callable=AsyncMock) as mock_log,
        ):
            from src.api.routes import evaluate

            response = await evaluate(
                request=mock_request,
                body=mock_evaluate_request,
                tenant=mock_tenant,
                db=mock_db_with_provider,
            )

            assert response.decision == Decision.NEW
            assert response.template_version_id is None
            assert response.drift_score == 0.0
            # Reliability score is now computed even for NEW (with default baseline)
            assert response.correction_rules == []

    @pytest.mark.asyncio
    async def test_review_decision_when_moderate_confidence(
        self,
        sample_structural_features,
        mock_evaluate_request,
        mock_template,
        mock_db_with_provider,
    ):
        """Should return REVIEW decision when confidence is 0.50-0.85."""
        from src.api.auth import AuthenticatedTenant
        from src.models import CorrectionRule

        mock_tenant = AuthenticatedTenant(
            tenant_id=mock_template.tenant_id,
            tenant_name="Test",
            api_key_id=uuid7(),
            api_key_name="test-key",
            scopes=["*"],
            rate_limit=1000,
        )

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.state.request_id = str(uuid7())

        with (
            patch(
                "src.api.routes.match_template", return_value=(mock_template, 0.70)
            ) as mock_match,
            patch("src.api.routes.compute_drift_score", return_value=0.15) as mock_drift,
            patch(
                "src.api.routes.compute_reliability_score", return_value=0.82
            ) as mock_reliability,
            patch(
                "src.api.routes.select_correction_rules",
                return_value=[
                    CorrectionRule(field="total", rule="sum_line_items", parameters=None)
                ],
            ) as mock_rules,
            patch("src.api.routes.log_evaluation_requested", new_callable=AsyncMock) as mock_log,
        ):
            from src.api.routes import evaluate

            response = await evaluate(
                request=mock_request,
                body=mock_evaluate_request,
                tenant=mock_tenant,
                db=mock_db_with_provider,
            )

            assert response.decision == Decision.REVIEW
            assert (
                response.template_version_id
                == f"{mock_template.template_id}:{mock_template.version}"
            )
            assert response.drift_score == 0.15
            assert response.reliability_score == 0.82
            assert len(response.correction_rules) == 1

    @pytest.mark.asyncio
    async def test_match_decision_when_high_confidence(
        self,
        sample_structural_features,
        mock_evaluate_request,
        mock_template,
        mock_db_with_provider,
    ):
        """Should return MATCH decision when confidence >= 0.85."""
        from src.api.auth import AuthenticatedTenant
        from src.models import CorrectionRule

        mock_tenant = AuthenticatedTenant(
            tenant_id=mock_template.tenant_id,
            tenant_name="Test",
            api_key_id=uuid7(),
            api_key_name="test-key",
            scopes=["*"],
            rate_limit=1000,
        )

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.state.request_id = str(uuid7())

        with (
            patch(
                "src.api.routes.match_template", return_value=(mock_template, 0.95)
            ) as mock_match,
            patch("src.api.routes.compute_drift_score", return_value=0.05) as mock_drift,
            patch(
                "src.api.routes.compute_reliability_score", return_value=0.90
            ) as mock_reliability,
            patch(
                "src.api.routes.select_correction_rules",
                return_value=[
                    CorrectionRule(field="total", rule="sum_line_items", parameters=None)
                ],
            ) as mock_rules,
            patch("src.api.routes.log_evaluation_requested", new_callable=AsyncMock) as mock_log,
        ):
            from src.api.routes import evaluate

            response = await evaluate(
                request=mock_request,
                body=mock_evaluate_request,
                tenant=mock_tenant,
                db=mock_db_with_provider,
            )

            assert response.decision == Decision.MATCH
            assert (
                response.template_version_id
                == f"{mock_template.template_id}:{mock_template.version}"
            )
            assert response.drift_score == 0.05
            assert response.reliability_score == 0.90

    @pytest.mark.asyncio
    async def test_alerts_generated_for_high_drift(
        self,
        sample_structural_features,
        mock_evaluate_request,
        mock_template,
        mock_db_with_provider,
    ):
        """Should generate alert when drift score > 0.30."""
        from src.api.auth import AuthenticatedTenant

        mock_tenant = AuthenticatedTenant(
            tenant_id=mock_template.tenant_id,
            tenant_name="Test",
            api_key_id=uuid7(),
            api_key_name="test-key",
            scopes=["*"],
            rate_limit=1000,
        )

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.state.request_id = str(uuid7())

        with (
            patch(
                "src.api.routes.match_template", return_value=(mock_template, 0.90)
            ) as mock_match,
            patch("src.api.routes.compute_drift_score", return_value=0.45) as mock_drift,
            patch(
                "src.api.routes.compute_reliability_score", return_value=0.85
            ) as mock_reliability,
            patch("src.api.routes.select_correction_rules", return_value=[]) as mock_rules,
            patch("src.api.routes.log_evaluation_requested", new_callable=AsyncMock) as mock_log,
        ):
            from src.api.routes import evaluate

            response = await evaluate(
                request=mock_request,
                body=mock_evaluate_request,
                tenant=mock_tenant,
                db=mock_db_with_provider,
            )

            assert len(response.alerts) >= 1
            assert any("drift" in alert.lower() for alert in response.alerts)

    @pytest.mark.asyncio
    async def test_alerts_generated_for_low_reliability(
        self,
        sample_structural_features,
        mock_evaluate_request,
        mock_template,
        mock_db_with_provider,
    ):
        """Should generate alert when reliability score < 0.80."""
        from src.api.auth import AuthenticatedTenant

        mock_tenant = AuthenticatedTenant(
            tenant_id=mock_template.tenant_id,
            tenant_name="Test",
            api_key_id=uuid7(),
            api_key_name="test-key",
            scopes=["*"],
            rate_limit=1000,
        )

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.state.request_id = str(uuid7())

        with (
            patch(
                "src.api.routes.match_template", return_value=(mock_template, 0.90)
            ) as mock_match,
            patch("src.api.routes.compute_drift_score", return_value=0.10) as mock_drift,
            patch(
                "src.api.routes.compute_reliability_score", return_value=0.65
            ) as mock_reliability,
            patch("src.api.routes.select_correction_rules", return_value=[]) as mock_rules,
            patch("src.api.routes.log_evaluation_requested", new_callable=AsyncMock) as mock_log,
        ):
            from src.api.routes import evaluate

            response = await evaluate(
                request=mock_request,
                body=mock_evaluate_request,
                tenant=mock_tenant,
                db=mock_db_with_provider,
            )

            assert len(response.alerts) >= 1
            assert any("reliability" in alert.lower() for alert in response.alerts)

    @pytest.mark.asyncio
    async def test_evaluation_stored_in_database(
        self,
        sample_structural_features,
        mock_evaluate_request,
        mock_db_with_provider,
    ):
        """Should store evaluation record in database."""
        from src.api.auth import AuthenticatedTenant

        mock_tenant = AuthenticatedTenant(
            tenant_id=uuid7(),
            tenant_name="Test",
            api_key_id=uuid7(),
            api_key_name="test-key",
            scopes=["*"],
            rate_limit=1000,
        )

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.state.request_id = str(uuid7())

        with (
            patch("src.api.routes.match_template", return_value=(None, 0.0)) as mock_match,
            patch("src.api.routes.log_evaluation_requested", new_callable=AsyncMock) as mock_log,
        ):
            from src.api.routes import evaluate

            response = await evaluate(
                request=mock_request,
                body=mock_evaluate_request,
                tenant=mock_tenant,
                db=mock_db_with_provider,
            )

            # Verify db.add and db.commit were called
            mock_db_with_provider.add.assert_called_once()
            mock_db_with_provider.commit.assert_called_once()

            # Verify the evaluation record has correct data
            stored_eval = mock_db_with_provider.add.call_args[0][0]
            assert stored_eval.tenant_id == mock_tenant.tenant_id
            assert stored_eval.correlation_id == mock_evaluate_request.client_correlation_id
            assert stored_eval.decision == Decision.NEW

    @pytest.mark.asyncio
    async def test_replay_hash_is_deterministic(
        self,
        sample_structural_features,
        mock_evaluate_request,
        mock_db_with_provider,
    ):
        """Replay hash should be SHA256 of evaluation_id:doc_hash:decision."""
        from src.api.auth import AuthenticatedTenant

        mock_tenant = AuthenticatedTenant(
            tenant_id=uuid7(),
            tenant_name="Test",
            api_key_id=uuid7(),
            api_key_name="test-key",
            scopes=["*"],
            rate_limit=1000,
        )

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.state.request_id = str(uuid7())

        with (
            patch("src.api.routes.match_template", return_value=(None, 0.0)) as mock_match,
            patch("src.api.routes.log_evaluation_requested", new_callable=AsyncMock) as mock_log,
        ):
            from src.api.routes import evaluate

            response = await evaluate(
                request=mock_request,
                body=mock_evaluate_request,
                tenant=mock_tenant,
                db=mock_db_with_provider,
            )

            # Verify replay hash format (64 char hex)
            assert len(response.replay_hash) == 64
            assert all(c in "0123456789abcdef" for c in response.replay_hash)

            # Verify it's computed correctly
            expected_hash = hashlib.sha256(
                f"{response.evaluation_id}:{mock_evaluate_request.client_doc_hash}:{response.decision.value}".encode()
            ).hexdigest()
            assert response.replay_hash == expected_hash
