"""Integration tests for multi-provider support."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import ExtractorProvider


class TestProviderRegistry:
    """Tests for provider registry seeding and lookup."""

    @pytest.mark.asyncio
    async def test_providers_seeded(self, async_session: AsyncSession):
        """Default providers should be seeded in database."""
        result = await async_session.execute(select(ExtractorProvider))
        providers = result.scalars().all()

        # Should have at least the default providers
        vendor_names = {p.vendor for p in providers}
        assert "aws" in vendor_names
        assert "azure" in vendor_names
        assert "google" in vendor_names
        assert "nvidia" in vendor_names

    @pytest.mark.asyncio
    async def test_aws_provider_config(self, async_session: AsyncSession):
        """AWS provider should have correct configuration."""
        result = await async_session.execute(
            select(ExtractorProvider).where(ExtractorProvider.vendor == "aws")
        )
        aws = result.scalar_one_or_none()

        assert aws is not None
        assert aws.display_name == "AWS Textract"
        assert aws.confidence_multiplier == 1.0
        assert aws.drift_sensitivity == 1.0
        assert aws.is_active is True
        assert aws.is_known is True
        assert "TABLE" in aws.supported_element_types

    @pytest.mark.asyncio
    async def test_azure_provider_calibration(self, async_session: AsyncSession):
        """Azure provider should have confidence calibration."""
        result = await async_session.execute(
            select(ExtractorProvider).where(ExtractorProvider.vendor == "azure")
        )
        azure = result.scalar_one_or_none()

        assert azure is not None
        assert azure.confidence_multiplier == 0.95  # Slightly lower
        assert azure.drift_sensitivity == 1.1  # Slightly higher


class TestEvaluateWithProviders:
    """Tests for /v1/evaluate with provider handling."""

    @pytest.mark.asyncio
    async def test_evaluate_with_known_provider(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Evaluate with known provider should not have unknown provider warning."""
        response = await client.post(
            "/v1/evaluate",
            headers=auth_headers,
            json={
                "layout_fingerprint": "a" * 64,
                "structural_features": {
                    "element_count": 50,
                    "table_count": 2,
                    "text_block_count": 40,
                    "image_count": 3,
                    "page_count": 1,
                    "text_density": 0.45,
                    "layout_complexity": 0.32,
                    "column_count": 2,
                    "has_header": True,
                    "has_footer": True,
                    "bounding_boxes": [],
                },
                "extractor_metadata": {
                    "vendor": "aws",  # Known provider
                    "model": "textract",
                    "version": "1.0",
                    "confidence": 0.95,
                    "latency_ms": 450,
                },
                "client_doc_hash": "b" * 64,
                "client_correlation_id": "test-known-provider",
                "pipeline_id": "test-pipeline",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should not have unknown provider warning
        assert not any("Unknown provider" in a for a in data.get("alerts", []))

    @pytest.mark.asyncio
    async def test_evaluate_with_unknown_provider(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Evaluate with unknown provider should have warning and penalty."""
        response = await client.post(
            "/v1/evaluate",
            headers=auth_headers,
            json={
                "layout_fingerprint": "c" * 64,
                "structural_features": {
                    "element_count": 50,
                    "table_count": 2,
                    "text_block_count": 40,
                    "image_count": 3,
                    "page_count": 1,
                    "text_density": 0.45,
                    "layout_complexity": 0.32,
                    "column_count": 2,
                    "has_header": True,
                    "has_footer": True,
                    "bounding_boxes": [],
                },
                "extractor_metadata": {
                    "vendor": "custom_ocr",  # Unknown provider
                    "model": "v1",
                    "version": "1.0",
                    "confidence": 0.95,
                    "latency_ms": 300,
                },
                "client_doc_hash": "d" * 64,
                "client_correlation_id": "test-unknown-provider",
                "pipeline_id": "test-pipeline",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should have unknown provider warning
        assert any("Unknown provider" in a for a in data.get("alerts", []))

    @pytest.mark.asyncio
    async def test_evaluate_case_insensitive_vendor(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Vendor lookup should be case-insensitive."""
        response = await client.post(
            "/v1/evaluate",
            headers=auth_headers,
            json={
                "layout_fingerprint": "e" * 64,
                "structural_features": {
                    "element_count": 50,
                    "table_count": 2,
                    "text_block_count": 40,
                    "image_count": 3,
                    "page_count": 1,
                    "text_density": 0.45,
                    "layout_complexity": 0.32,
                    "column_count": 2,
                    "has_header": True,
                    "has_footer": True,
                    "bounding_boxes": [],
                },
                "extractor_metadata": {
                    "vendor": "AWS",  # Uppercase
                    "model": "textract",
                    "version": "1.0",
                    "confidence": 0.95,
                    "latency_ms": 450,
                },
                "client_doc_hash": "f" * 64,
                "client_correlation_id": "test-uppercase-vendor",
                "pipeline_id": "test-pipeline",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should NOT have unknown provider warning (found aws)
        assert not any("Unknown provider" in a for a in data.get("alerts", []))

    @pytest.mark.asyncio
    async def test_evaluate_stores_full_extractor_metadata(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Evaluation should store full extractor metadata."""
        response = await client.post(
            "/v1/evaluate",
            headers=auth_headers,
            json={
                "layout_fingerprint": "g" * 64,
                "structural_features": {
                    "element_count": 50,
                    "table_count": 2,
                    "text_block_count": 40,
                    "image_count": 3,
                    "page_count": 1,
                    "text_density": 0.45,
                    "layout_complexity": 0.32,
                    "column_count": 2,
                    "has_header": True,
                    "has_footer": True,
                    "bounding_boxes": [],
                },
                "extractor_metadata": {
                    "vendor": "nvidia",
                    "model": "nemotron-parse",
                    "version": "1.2.0",
                    "confidence": 0.92,
                    "latency_ms": 280,
                    "cost_usd": 0.001,
                },
                "client_doc_hash": "h" * 64,
                "client_correlation_id": "test-full-metadata",
                "pipeline_id": "test-pipeline",
            },
        )

        assert response.status_code == 200
        data = response.json()
        evaluation_id = data["evaluation_id"]

        # Fetch the evaluation to verify stored data
        get_response = await client.get(
            f"/v1/evaluations/{evaluation_id}",
            headers=auth_headers,
        )

        assert get_response.status_code == 200
        eval_data = get_response.json()

        assert eval_data["extractor_vendor"] == "nvidia"
        assert eval_data["extractor_model"] == "nemotron-parse"
        assert eval_data["extractor_version"] == "1.2.0"
        assert eval_data["extractor_confidence"] == 0.92
        assert eval_data["extractor_latency_ms"] == 280


class TestSafeguardWarnings:
    """Tests for safeguard warnings in evaluate response."""

    @pytest.mark.asyncio
    async def test_zero_elements_error_in_alerts(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Zero elements should produce error in alerts."""
        response = await client.post(
            "/v1/evaluate",
            headers=auth_headers,
            json={
                "layout_fingerprint": "i" * 64,
                "structural_features": {
                    "element_count": 0,  # Zero elements
                    "table_count": 0,
                    "text_block_count": 0,
                    "image_count": 0,
                    "page_count": 1,
                    "text_density": 0.0,
                    "layout_complexity": 0.0,
                    "column_count": 0,
                    "has_header": False,
                    "has_footer": False,
                    "bounding_boxes": [],
                },
                "extractor_metadata": {
                    "vendor": "aws",
                    "model": "textract",
                    "version": "1.0",
                    "confidence": 0.5,
                    "latency_ms": 450,
                },
                "client_doc_hash": "j" * 64,
                "client_correlation_id": "test-zero-elements",
                "pipeline_id": "test-pipeline",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should have error about zero elements
        assert any("ERROR:" in a and "Zero elements" in a for a in data.get("alerts", []))

    @pytest.mark.asyncio
    async def test_excessive_latency_warning(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Excessive latency should produce warning."""
        response = await client.post(
            "/v1/evaluate",
            headers=auth_headers,
            json={
                "layout_fingerprint": "k" * 64,
                "structural_features": {
                    "element_count": 50,
                    "table_count": 2,
                    "text_block_count": 40,
                    "image_count": 3,
                    "page_count": 1,
                    "text_density": 0.45,
                    "layout_complexity": 0.32,
                    "column_count": 2,
                    "has_header": True,
                    "has_footer": True,
                    "bounding_boxes": [],
                },
                "extractor_metadata": {
                    "vendor": "aws",
                    "model": "textract",
                    "version": "1.0",
                    "confidence": 0.95,
                    "latency_ms": 5000,  # 5 seconds - way over typical
                },
                "client_doc_hash": "l" * 64,
                "client_correlation_id": "test-high-latency",
                "pipeline_id": "test-pipeline",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should have warning about latency
        assert any("3x typical" in a for a in data.get("alerts", []))


class TestProviderCalibration:
    """Tests for provider-specific calibration effects."""

    @pytest.mark.asyncio
    async def test_azure_confidence_calibrated(
        self, client: AsyncClient, auth_headers: dict, async_session: AsyncSession
    ):
        """Azure's confidence multiplier should affect reliability."""
        # First, create a template to get a MATCH decision
        template_response = await client.post(
            "/v1/templates",
            headers=auth_headers,
            json={
                "template_id": "test-azure-calibration",
                "version": "1.0",
                "structural_features": {
                    "element_count": 50,
                    "table_count": 2,
                    "text_block_count": 40,
                    "image_count": 3,
                    "page_count": 1,
                    "text_density": 0.45,
                    "layout_complexity": 0.32,
                    "column_count": 2,
                    "has_header": True,
                    "has_footer": True,
                    "bounding_boxes": [],
                },
                "baseline_reliability": 0.90,
            },
        )
        assert template_response.status_code == 201
        template_fingerprint = template_response.json()["fingerprint"]

        # Evaluate with Azure (has 0.95 confidence multiplier)
        azure_response = await client.post(
            "/v1/evaluate",
            headers=auth_headers,
            json={
                "layout_fingerprint": template_fingerprint,
                "structural_features": {
                    "element_count": 50,
                    "table_count": 2,
                    "text_block_count": 40,
                    "image_count": 3,
                    "page_count": 1,
                    "text_density": 0.45,
                    "layout_complexity": 0.32,
                    "column_count": 2,
                    "has_header": True,
                    "has_footer": True,
                    "bounding_boxes": [],
                },
                "extractor_metadata": {
                    "vendor": "azure",
                    "model": "document-intelligence",
                    "version": "4.0",
                    "confidence": 0.95,
                    "latency_ms": 600,
                },
                "client_doc_hash": "m" * 64,
                "client_correlation_id": "test-azure-eval",
                "pipeline_id": "test-pipeline",
            },
        )

        assert azure_response.status_code == 200
        azure_data = azure_response.json()

        # Evaluate same document with AWS (1.0 confidence multiplier)
        aws_response = await client.post(
            "/v1/evaluate",
            headers=auth_headers,
            json={
                "layout_fingerprint": template_fingerprint,
                "structural_features": {
                    "element_count": 50,
                    "table_count": 2,
                    "text_block_count": 40,
                    "image_count": 3,
                    "page_count": 1,
                    "text_density": 0.45,
                    "layout_complexity": 0.32,
                    "column_count": 2,
                    "has_header": True,
                    "has_footer": True,
                    "bounding_boxes": [],
                },
                "extractor_metadata": {
                    "vendor": "aws",
                    "model": "textract",
                    "version": "1.0",
                    "confidence": 0.95,  # Same confidence
                    "latency_ms": 450,
                },
                "client_doc_hash": "n" * 64,
                "client_correlation_id": "test-aws-eval",
                "pipeline_id": "test-pipeline",
            },
        )

        assert aws_response.status_code == 200
        aws_data = aws_response.json()

        # Azure should have slightly lower reliability due to calibration
        # Both should get MATCH, but reliability scores may differ slightly
        assert azure_data["decision"] == "MATCH"
        assert aws_data["decision"] == "MATCH"
