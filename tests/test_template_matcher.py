"""Tests for template matching service."""

import pytest
import math

from src.services.template_matcher import (
    _extract_feature_vector,
    _cosine_similarity,
)
from src.models import StructuralFeatures


class TestFeatureVectorExtraction:
    """Tests for feature vector extraction."""

    def test_extract_feature_vector_basic(self, sample_structural_features):
        """Test basic feature vector extraction."""
        vector = _extract_feature_vector(sample_structural_features)

        assert len(vector) == 10
        assert all(0 <= v <= 1 for v in vector)

    def test_extract_feature_vector_normalization(self):
        """Test that counts are properly normalized."""
        features = StructuralFeatures(
            element_count=500,  # Half of max 1000
            table_count=25,  # Half of max 50
            text_block_count=100,  # Half of max 200
            image_count=50,  # Half of max 100
            page_count=250,  # Half of max 500
            text_density=0.5,
            layout_complexity=0.5,
            column_count=5,  # Half of max 10
            has_header=True,
            has_footer=False,
            bounding_boxes=[],
        )
        vector = _extract_feature_vector(features)

        # Check normalized values
        assert vector[0] == 0.5  # element_count
        assert vector[1] == 0.5  # table_count
        assert vector[2] == 0.5  # text_block_count
        assert vector[3] == 0.5  # image_count
        assert vector[4] == 0.5  # page_count
        assert vector[5] == 0.5  # text_density
        assert vector[6] == 0.5  # layout_complexity
        assert vector[7] == 0.5  # column_count
        assert vector[8] == 1.0  # has_header (True)
        assert vector[9] == 0.0  # has_footer (False)

    def test_extract_feature_vector_caps_at_one(self):
        """Test that values are capped at 1.0."""
        features = StructuralFeatures(
            element_count=5000,  # Way over max
            table_count=200,
            text_block_count=1000,
            image_count=500,
            page_count=2000,
            text_density=0.9,
            layout_complexity=0.9,
            column_count=50,
            has_header=True,
            has_footer=True,
            bounding_boxes=[],
        )
        vector = _extract_feature_vector(features)

        # All normalized counts should cap at 1.0
        assert vector[0] == 1.0  # element_count capped
        assert vector[1] == 1.0  # table_count capped
        assert vector[2] == 1.0  # text_block_count capped
        assert vector[3] == 1.0  # image_count capped
        assert vector[4] == 1.0  # page_count capped


class TestCosineSimilarity:
    """Tests for cosine similarity computation."""

    def test_identical_vectors(self):
        """Identical vectors should have similarity 1.0."""
        vec = [0.5, 0.3, 0.8, 0.2]
        assert _cosine_similarity(vec, vec) == pytest.approx(1.0, abs=0.0001)

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity 0.0."""
        vec_a = [1.0, 0.0]
        vec_b = [0.0, 1.0]
        assert _cosine_similarity(vec_a, vec_b) == pytest.approx(0.0, abs=0.0001)

    def test_similar_vectors(self):
        """Similar vectors should have high similarity."""
        vec_a = [0.5, 0.3, 0.8]
        vec_b = [0.52, 0.28, 0.82]
        similarity = _cosine_similarity(vec_a, vec_b)
        assert similarity > 0.99

    def test_different_length_vectors(self):
        """Different length vectors should return 0.0."""
        vec_a = [0.5, 0.3]
        vec_b = [0.5, 0.3, 0.8]
        assert _cosine_similarity(vec_a, vec_b) == 0.0

    def test_zero_vector(self):
        """Zero vector should return 0.0."""
        vec_a = [0.0, 0.0, 0.0]
        vec_b = [0.5, 0.3, 0.8]
        assert _cosine_similarity(vec_a, vec_b) == 0.0

    def test_negative_values(self):
        """Test with negative values (though not expected in practice)."""
        vec_a = [0.5, -0.3, 0.8]
        vec_b = [0.5, -0.3, 0.8]
        assert _cosine_similarity(vec_a, vec_b) == pytest.approx(1.0, abs=0.0001)


class TestFeatureSimilarity:
    """Integration tests for feature-based similarity."""

    def test_identical_features(self, sample_structural_features):
        """Identical features should have perfect similarity."""
        vec = _extract_feature_vector(sample_structural_features)
        assert _cosine_similarity(vec, vec) == pytest.approx(1.0, abs=0.0001)

    def test_different_features(
        self, sample_structural_features, high_drift_features
    ):
        """Very different features should have lower similarity."""
        vec_a = _extract_feature_vector(sample_structural_features)
        vec_b = _extract_feature_vector(high_drift_features)
        similarity = _cosine_similarity(vec_a, vec_b)

        # Should still have some similarity (not orthogonal)
        assert 0.5 < similarity < 0.95

    def test_minor_variations(self, sample_structural_features):
        """Minor variations should have high similarity."""
        # Create slightly modified features
        modified = StructuralFeatures(
            element_count=sample_structural_features.element_count + 2,
            table_count=sample_structural_features.table_count,
            text_block_count=sample_structural_features.text_block_count + 1,
            image_count=sample_structural_features.image_count,
            page_count=sample_structural_features.page_count,
            text_density=sample_structural_features.text_density + 0.02,
            layout_complexity=sample_structural_features.layout_complexity,
            column_count=sample_structural_features.column_count,
            has_header=sample_structural_features.has_header,
            has_footer=sample_structural_features.has_footer,
            bounding_boxes=[],
        )

        vec_a = _extract_feature_vector(sample_structural_features)
        vec_b = _extract_feature_vector(modified)
        similarity = _cosine_similarity(vec_a, vec_b)

        # Minor changes should keep high similarity
        assert similarity > 0.99
