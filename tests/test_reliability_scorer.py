"""Tests for reliability scoring service."""

import math

import pytest

from src.models import ExtractorMetadata, ExtractorProvider
from src.services.reliability_scorer import (
    compute_reliability_score,
    get_reliability_breakdown,
)


@pytest.fixture
def nvidia_provider() -> ExtractorProvider:
    """Create NVIDIA provider configuration."""
    return ExtractorProvider(
        vendor="nvidia",
        display_name="NVIDIA Nemotron",
        confidence_multiplier=1.05,
        drift_sensitivity=0.9,
        supported_element_types=["text", "table", "figure", "list", "title"],
        typical_latency_ms=300,
        is_active=True,
        is_known=True,
    )


class TestComputeReliabilityScore:
    """Tests for reliability score computation."""

    @pytest.mark.asyncio
    async def test_high_reliability_optimal_conditions(
        self, sample_template, sample_extractor_metadata, nvidia_provider
    ):
        """Optimal conditions should produce high reliability."""
        reliability = await compute_reliability_score(
            template=sample_template,
            extractor=sample_extractor_metadata,
            drift_score=0.0,
            provider=nvidia_provider,
        )
        # High baseline (0.85) + high confidence (0.95) + no drift + known provider = high score
        assert reliability > 0.85

    @pytest.mark.asyncio
    async def test_low_reliability_poor_conditions(self, sample_template, low_confidence_extractor):
        """Poor conditions should produce low reliability."""
        reliability = await compute_reliability_score(
            template=sample_template,
            extractor=low_confidence_extractor,
            drift_score=0.60,  # High drift
        )
        # Unknown extractor + low confidence + high drift = low score
        assert reliability < 0.60

    @pytest.mark.asyncio
    async def test_drift_penalty(self, sample_template, sample_extractor_metadata):
        """Higher drift should reduce reliability."""
        reliability_no_drift = await compute_reliability_score(
            template=sample_template,
            extractor=sample_extractor_metadata,
            drift_score=0.0,
        )
        reliability_high_drift = await compute_reliability_score(
            template=sample_template,
            extractor=sample_extractor_metadata,
            drift_score=0.50,
        )

        assert reliability_no_drift > reliability_high_drift
        # Critical drift (>0.50) should have significant impact
        assert reliability_no_drift - reliability_high_drift > 0.10

    @pytest.mark.asyncio
    async def test_unknown_extractor_penalty(self, sample_template, nvidia_provider):
        """Unknown extractor should reduce reliability."""
        known_extractor = ExtractorMetadata(
            vendor="nvidia",
            model="test",
            version="1.0",
            confidence=0.90,
            latency_ms=100,
        )
        unknown_extractor = ExtractorMetadata(
            vendor="mysterious_vendor",
            model="test",
            version="1.0",
            confidence=0.90,
            latency_ms=100,
        )

        reliability_known = await compute_reliability_score(
            template=sample_template,
            extractor=known_extractor,
            drift_score=0.1,
            provider=nvidia_provider,  # Known provider
        )
        reliability_unknown = await compute_reliability_score(
            template=sample_template,
            extractor=unknown_extractor,
            drift_score=0.1,
            provider=None,  # Unknown provider
        )

        # Unknown extractor gets 10% penalty
        assert reliability_known > reliability_unknown

    @pytest.mark.asyncio
    async def test_high_confidence_bonus(self, sample_template):
        """High extractor confidence (>0.95) should give bonus."""
        high_conf = ExtractorMetadata(
            vendor="nvidia",
            model="test",
            version="1.0",
            confidence=0.98,  # Very high
            latency_ms=100,
        )
        normal_conf = ExtractorMetadata(
            vendor="nvidia",
            model="test",
            version="1.0",
            confidence=0.90,  # Normal
            latency_ms=100,
        )

        reliability_high = await compute_reliability_score(
            template=sample_template,
            extractor=high_conf,
            drift_score=0.1,
        )
        reliability_normal = await compute_reliability_score(
            template=sample_template,
            extractor=normal_conf,
            drift_score=0.1,
        )

        assert reliability_high > reliability_normal

    @pytest.mark.asyncio
    async def test_reliability_bounds(self, sample_template, low_confidence_extractor):
        """Reliability should always be between 0 and 1."""
        # Test with worst case
        reliability = await compute_reliability_score(
            template=sample_template,
            extractor=low_confidence_extractor,
            drift_score=1.0,  # Maximum drift
        )
        assert 0.0 <= reliability <= 1.0

        # Test with best case
        best_extractor = ExtractorMetadata(
            vendor="nvidia",
            model="best",
            version="1.0",
            confidence=0.99,
            latency_ms=50,
        )
        reliability = await compute_reliability_score(
            template=sample_template,
            extractor=best_extractor,
            drift_score=0.0,
        )
        assert 0.0 <= reliability <= 1.0


class TestGetReliabilityBreakdown:
    """Tests for reliability breakdown details."""

    def test_breakdown_structure(self, sample_template, sample_extractor_metadata, nvidia_provider):
        """Verify breakdown has expected structure."""
        breakdown = get_reliability_breakdown(
            template=sample_template,
            extractor=sample_extractor_metadata,
            drift_score=0.1,
            provider=nvidia_provider,
        )

        assert "components" in breakdown
        assert "adjustments" in breakdown
        assert "provider" in breakdown

        assert "baseline_reliability" in breakdown["components"]
        assert "extractor_confidence" in breakdown["components"]
        assert "drift_factor" in breakdown["components"]

    def test_breakdown_weights(self, sample_template, sample_extractor_metadata):
        """Verify weights sum to 1.0."""
        breakdown = get_reliability_breakdown(
            template=sample_template,
            extractor=sample_extractor_metadata,
            drift_score=0.1,
        )

        total_weight = sum(c["weight"] for c in breakdown["components"].values())
        assert total_weight == pytest.approx(1.0, abs=0.01)

    def test_breakdown_known_extractor(self, sample_template, sample_extractor_metadata, nvidia_provider):
        """Verify known extractor is correctly identified."""
        breakdown = get_reliability_breakdown(
            template=sample_template,
            extractor=sample_extractor_metadata,
            drift_score=0.1,
            provider=nvidia_provider,
        )

        assert breakdown["provider"]["is_known"] is True
        assert breakdown["adjustments"]["unknown_provider_penalty"] is False

    def test_breakdown_drift_factor(self, sample_template, sample_extractor_metadata):
        """Verify drift factor uses exponential decay."""
        breakdown = get_reliability_breakdown(
            template=sample_template,
            extractor=sample_extractor_metadata,
            drift_score=0.5,
        )

        # e^(-2 * 0.5) = e^-1 ≈ 0.368
        expected_factor = math.exp(-2.0 * 0.5)
        assert breakdown["components"]["drift_factor"]["value"] == pytest.approx(
            expected_factor, abs=0.01
        )
