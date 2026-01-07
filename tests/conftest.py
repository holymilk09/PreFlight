"""Pytest configuration and shared fixtures."""

import pytest
from uuid import UUID
from uuid_extensions import uuid7

from src.models import (
    CorrectionRule,
    ExtractorMetadata,
    StructuralFeatures,
    Template,
    TemplateStatus,
)


@pytest.fixture
def sample_structural_features() -> StructuralFeatures:
    """Standard invoice-like structural features."""
    return StructuralFeatures(
        element_count=45,
        table_count=2,
        text_block_count=30,
        image_count=3,
        page_count=1,
        text_density=0.45,
        layout_complexity=0.32,
        column_count=2,
        has_header=True,
        has_footer=True,
        bounding_boxes=[],
    )


@pytest.fixture
def sample_extractor_metadata() -> ExtractorMetadata:
    """Standard NVIDIA extractor metadata."""
    return ExtractorMetadata(
        vendor="nvidia",
        model="nemotron-parse-1.2",
        version="1.2.0",
        confidence=0.95,
        latency_ms=234,
        cost_usd=0.002,
    )


@pytest.fixture
def sample_template(sample_structural_features: StructuralFeatures) -> Template:
    """Standard template for testing."""
    return Template(
        id=uuid7(),
        tenant_id=uuid7(),
        template_id="INV-ACME-001",
        version="1.0",
        fingerprint="abc123" * 10 + "abcd",  # 64 char hex
        structural_features=sample_structural_features.model_dump(),
        baseline_reliability=0.85,
        correction_rules=[
            {"field": "total", "rule": "sum_line_items", "parameters": None}
        ],
        status=TemplateStatus.ACTIVE,
    )


@pytest.fixture
def high_drift_features() -> StructuralFeatures:
    """Features with significant drift from standard template."""
    return StructuralFeatures(
        element_count=100,  # Much higher
        table_count=5,  # Different
        text_block_count=60,  # Higher
        image_count=10,  # Higher
        page_count=3,  # Different
        text_density=0.80,  # Much higher
        layout_complexity=0.70,  # Higher
        column_count=4,  # Different
        has_header=False,  # Different
        has_footer=False,  # Different
        bounding_boxes=[],
    )


@pytest.fixture
def low_confidence_extractor() -> ExtractorMetadata:
    """Extractor with low confidence."""
    return ExtractorMetadata(
        vendor="unknown_vendor",
        model="experimental",
        version="0.1.0",
        confidence=0.55,
        latency_ms=1500,
        cost_usd=0.01,
    )
