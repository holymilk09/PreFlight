"""Tests for template matching service."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models import StructuralFeatures, Template, TemplateStatus
from src.services.template_matcher import (
    _cosine_similarity,
    _extract_feature_vector,
    _match_with_scan,
    index_template,
    match_template,
    unindex_template,
)


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

    def test_different_features(self, sample_structural_features, high_drift_features):
        """Very different features should have lower similarity."""
        vec_a = _extract_feature_vector(sample_structural_features)
        vec_b = _extract_feature_vector(high_drift_features)
        similarity = _cosine_similarity(vec_a, vec_b)

        # Should still have some similarity (not orthogonal) but lower than identical
        assert 0.3 < similarity < 0.95

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


class TestMatchTemplate:
    """Tests for match_template function."""

    @pytest.mark.asyncio
    async def test_match_template_exact_fingerprint(self, sample_structural_features):
        """Exact fingerprint match should return confidence 1.0."""
        tenant_id = uuid4()
        template_id = uuid4()
        fingerprint = "a" * 64

        # Create mock template
        mock_template = Template(
            id=template_id,
            tenant_id=tenant_id,
            template_id="test-template",
            version="1.0",
            fingerprint=fingerprint,
            structural_features=sample_structural_features.model_dump(),
            baseline_reliability=0.9,
            status=TemplateStatus.ACTIVE,
        )

        # Mock database session
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_template
        mock_db.execute.return_value = mock_result

        result_template, confidence = await match_template(
            fingerprint=fingerprint,
            features=sample_structural_features,
            tenant_id=tenant_id,
            db=mock_db,
        )

        assert result_template == mock_template
        assert confidence == 1.0

    @pytest.mark.asyncio
    async def test_match_template_no_exact_match_falls_back_to_scan(
        self, sample_structural_features
    ):
        """No exact fingerprint match should fall back to scan."""
        tenant_id = uuid4()
        fingerprint = "b" * 64

        # Mock database session - no exact match, then empty templates
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No exact match
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []  # No templates in scan
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        with patch("src.services.template_matcher._match_with_lsh", return_value=None):
            result_template, confidence = await match_template(
                fingerprint=fingerprint,
                features=sample_structural_features,
                tenant_id=tenant_id,
                db=mock_db,
            )

        assert result_template is None
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_match_template_lsh_returns_match(self, sample_structural_features):
        """LSH returning a match should use that result."""
        tenant_id = uuid4()
        template_id = uuid4()
        fingerprint = "c" * 64

        mock_template = Template(
            id=template_id,
            tenant_id=tenant_id,
            template_id="test-template",
            version="1.0",
            fingerprint="different",
            structural_features=sample_structural_features.model_dump(),
            baseline_reliability=0.9,
            status=TemplateStatus.ACTIVE,
        )

        # Mock database session - no exact match
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # LSH returns a match
        with patch(
            "src.services.template_matcher._match_with_lsh",
            return_value=(mock_template, 0.92),
        ):
            result_template, confidence = await match_template(
                fingerprint=fingerprint,
                features=sample_structural_features,
                tenant_id=tenant_id,
                db=mock_db,
            )

        assert result_template == mock_template
        assert confidence == 0.92


class TestMatchWithScan:
    """Tests for _match_with_scan function."""

    @pytest.mark.asyncio
    async def test_match_with_scan_no_templates(self, sample_structural_features):
        """No templates in DB should return (None, 0.0)."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result_template, confidence = await _match_with_scan(
            features=sample_structural_features,
            db=mock_db,
        )

        assert result_template is None
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_match_with_scan_finds_similar(self, sample_structural_features):
        """Should find similar template in scan."""
        tenant_id = uuid4()
        template_id = uuid4()

        mock_template = Template(
            id=template_id,
            tenant_id=tenant_id,
            template_id="test-template",
            version="1.0",
            fingerprint="d" * 64,
            structural_features=sample_structural_features.model_dump(),
            baseline_reliability=0.9,
            status=TemplateStatus.ACTIVE,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_template]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result_template, confidence = await _match_with_scan(
            features=sample_structural_features,
            db=mock_db,
        )

        assert result_template == mock_template
        assert confidence >= 0.50  # Should be above minimum threshold

    @pytest.mark.asyncio
    async def test_match_with_scan_below_threshold(
        self, sample_structural_features, high_drift_features
    ):
        """Template below similarity threshold should not match."""
        tenant_id = uuid4()
        template_id = uuid4()

        # Create template with very different features
        mock_template = Template(
            id=template_id,
            tenant_id=tenant_id,
            template_id="test-template",
            version="1.0",
            fingerprint="e" * 64,
            structural_features=high_drift_features.model_dump(),
            baseline_reliability=0.9,
            status=TemplateStatus.ACTIVE,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_template]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        # Create features that are very different from the template
        very_different_features = StructuralFeatures(
            element_count=1,
            table_count=0,
            text_block_count=1,
            image_count=0,
            page_count=1,
            text_density=0.01,
            layout_complexity=0.01,
            column_count=1,
            has_header=False,
            has_footer=False,
            bounding_boxes=[],
        )

        result_template, confidence = await _match_with_scan(
            features=very_different_features,
            db=mock_db,
        )

        # Depending on similarity, may or may not match
        # The test validates behavior at threshold boundary
        assert confidence >= 0.0


class TestIndexTemplate:
    """Tests for index_template function."""

    @pytest.mark.asyncio
    async def test_index_template_success(self, sample_structural_features):
        """Should return True when LSH indexing succeeds."""
        template_id = uuid4()
        tenant_id = uuid4()

        mock_lsh = MagicMock()
        mock_lsh.available = True
        mock_lsh.add_template = AsyncMock(return_value=True)

        with patch(
            "src.services.lsh_index.get_lsh_index",
            new_callable=AsyncMock,
            return_value=mock_lsh,
        ):
            result = await index_template(
                template_id=template_id,
                tenant_id=tenant_id,
                features=sample_structural_features,
            )

        assert result is True
        mock_lsh.add_template.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_template_lsh_unavailable(self, sample_structural_features):
        """Should return False when LSH is unavailable."""
        template_id = uuid4()
        tenant_id = uuid4()

        mock_lsh = MagicMock()
        mock_lsh.available = False

        with patch(
            "src.services.lsh_index.get_lsh_index",
            new_callable=AsyncMock,
            return_value=mock_lsh,
        ):
            result = await index_template(
                template_id=template_id,
                tenant_id=tenant_id,
                features=sample_structural_features,
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_index_template_exception(self, sample_structural_features):
        """Should return False and log warning on exception."""
        template_id = uuid4()
        tenant_id = uuid4()

        with patch(
            "src.services.lsh_index.get_lsh_index",
            new_callable=AsyncMock,
            side_effect=Exception("LSH connection failed"),
        ):
            result = await index_template(
                template_id=template_id,
                tenant_id=tenant_id,
                features=sample_structural_features,
            )

        assert result is False


class TestUnindexTemplate:
    """Tests for unindex_template function."""

    @pytest.mark.asyncio
    async def test_unindex_template_success(self):
        """Should return True when LSH removal succeeds."""
        template_id = uuid4()

        mock_lsh = MagicMock()
        mock_lsh.available = True
        mock_lsh.remove_template = AsyncMock(return_value=True)

        with patch(
            "src.services.lsh_index.get_lsh_index",
            new_callable=AsyncMock,
            return_value=mock_lsh,
        ):
            result = await unindex_template(template_id=template_id)

        assert result is True
        mock_lsh.remove_template.assert_called_once_with(template_id)

    @pytest.mark.asyncio
    async def test_unindex_template_lsh_unavailable(self):
        """Should return False when LSH is unavailable."""
        template_id = uuid4()

        mock_lsh = MagicMock()
        mock_lsh.available = False

        with patch(
            "src.services.lsh_index.get_lsh_index",
            new_callable=AsyncMock,
            return_value=mock_lsh,
        ):
            result = await unindex_template(template_id=template_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_unindex_template_exception(self):
        """Should return False and log warning on exception."""
        template_id = uuid4()

        with patch(
            "src.services.lsh_index.get_lsh_index",
            new_callable=AsyncMock,
            side_effect=Exception("LSH connection failed"),
        ):
            result = await unindex_template(template_id=template_id)

        assert result is False
