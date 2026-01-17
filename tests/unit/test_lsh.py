"""Unit tests for LSH (Locality-Sensitive Hashing) implementation."""

import pytest
from uuid_extensions import uuid7

from src.models import StructuralFeatures
from src.services.lsh_utils import (
    NUM_HASHES,
    compute_minhash_signature,
    estimate_jaccard_similarity,
    features_to_shingles,
    minhash_signature,
    signature_to_bands,
)


class TestFeaturesToShingles:
    """Test shingle generation from structural features."""

    def test_features_to_shingles_returns_set(self, sample_structural_features):
        """Should return a set of integer shingles."""
        shingles = features_to_shingles(sample_structural_features)

        assert isinstance(shingles, set)
        assert len(shingles) > 0
        assert all(isinstance(s, int) for s in shingles)

    def test_same_features_same_shingles(self, sample_structural_features):
        """Same features should produce same shingles."""
        shingles1 = features_to_shingles(sample_structural_features)
        shingles2 = features_to_shingles(sample_structural_features)

        assert shingles1 == shingles2

    def test_different_features_different_shingles(self):
        """Different features should produce different shingles."""
        features1 = StructuralFeatures(
            element_count=10,
            table_count=1,
            text_block_count=5,
            image_count=0,
            page_count=1,
            text_density=0.5,
            layout_complexity=0.3,
            column_count=1,
            has_header=True,
            has_footer=False,
        )

        features2 = StructuralFeatures(
            element_count=100,
            table_count=5,
            text_block_count=50,
            image_count=10,
            page_count=5,
            text_density=0.8,
            layout_complexity=0.7,
            column_count=2,
            has_header=False,
            has_footer=True,
        )

        shingles1 = features_to_shingles(features1)
        shingles2 = features_to_shingles(features2)

        # Should have some different shingles
        assert shingles1 != shingles2

    def test_similar_features_overlap_shingles(self):
        """Similar features should have overlapping shingles."""
        features1 = StructuralFeatures(
            element_count=10,
            table_count=1,
            text_block_count=5,
            image_count=0,
            page_count=1,
            text_density=0.5,
            layout_complexity=0.3,
            column_count=1,
            has_header=True,
            has_footer=False,
        )

        # Very similar - only element_count differs slightly
        features2 = StructuralFeatures(
            element_count=12,  # Same bucket (10-19)
            table_count=1,
            text_block_count=5,
            image_count=0,
            page_count=1,
            text_density=0.5,
            layout_complexity=0.3,
            column_count=1,
            has_header=True,
            has_footer=False,
        )

        shingles1 = features_to_shingles(features1)
        shingles2 = features_to_shingles(features2)

        # Should have significant overlap
        intersection = shingles1 & shingles2
        assert len(intersection) > len(shingles1) * 0.5


class TestMinHashSignature:
    """Test MinHash signature computation."""

    def test_signature_length(self, sample_structural_features):
        """Signature should have NUM_HASHES elements."""
        sig = minhash_signature(sample_structural_features)

        assert len(sig) == NUM_HASHES

    def test_signature_is_tuple(self, sample_structural_features):
        """Signature should be a tuple of integers."""
        sig = minhash_signature(sample_structural_features)

        assert isinstance(sig, tuple)
        assert all(isinstance(v, int) for v in sig)

    def test_same_features_same_signature(self, sample_structural_features):
        """Same features should produce same signature."""
        sig1 = minhash_signature(sample_structural_features)
        sig2 = minhash_signature(sample_structural_features)

        assert sig1 == sig2

    def test_empty_shingles_signature(self):
        """Empty shingles should produce max-value signature."""
        sig = compute_minhash_signature(set())

        assert len(sig) == NUM_HASHES
        # All values should be PRIME (max value)
        assert all(v == sig[0] for v in sig)


class TestJaccardSimilarity:
    """Test Jaccard similarity estimation."""

    def test_identical_signatures_similarity_1(self, sample_structural_features):
        """Identical signatures should have similarity 1.0."""
        sig = minhash_signature(sample_structural_features)
        similarity = estimate_jaccard_similarity(sig, sig)

        assert similarity == 1.0

    def test_different_length_signatures_similarity_0(self):
        """Different length signatures should return 0.0."""
        sig1 = (1, 2, 3)
        sig2 = (1, 2)

        similarity = estimate_jaccard_similarity(sig1, sig2)
        assert similarity == 0.0

    def test_similar_features_high_similarity(self):
        """Similar features should have high estimated similarity."""
        features1 = StructuralFeatures(
            element_count=10,
            table_count=1,
            text_block_count=5,
            image_count=0,
            page_count=1,
            text_density=0.5,
            layout_complexity=0.3,
            column_count=1,
            has_header=True,
            has_footer=False,
        )

        features2 = StructuralFeatures(
            element_count=12,
            table_count=1,
            text_block_count=6,
            image_count=0,
            page_count=1,
            text_density=0.52,
            layout_complexity=0.32,
            column_count=1,
            has_header=True,
            has_footer=False,
        )

        sig1 = minhash_signature(features1)
        sig2 = minhash_signature(features2)

        similarity = estimate_jaccard_similarity(sig1, sig2)

        # Should be fairly similar
        assert similarity > 0.3

    def test_dissimilar_features_low_similarity(self):
        """Very different features should have low estimated similarity."""
        features1 = StructuralFeatures(
            element_count=5,
            table_count=0,
            text_block_count=5,
            image_count=0,
            page_count=1,
            text_density=0.2,
            layout_complexity=0.1,
            column_count=1,
            has_header=False,
            has_footer=False,
        )

        features2 = StructuralFeatures(
            element_count=200,
            table_count=10,
            text_block_count=100,
            image_count=20,
            page_count=10,
            text_density=0.9,
            layout_complexity=0.9,
            column_count=3,
            has_header=True,
            has_footer=True,
        )

        sig1 = minhash_signature(features1)
        sig2 = minhash_signature(features2)

        similarity = estimate_jaccard_similarity(sig1, sig2)

        # Should be quite different
        assert similarity < 0.5


class TestSignatureToBands:
    """Test band splitting for LSH."""

    def test_default_8_bands(self, sample_structural_features):
        """Default should split into 8 bands."""
        sig = minhash_signature(sample_structural_features)
        bands = signature_to_bands(sig)

        assert len(bands) == 8

    def test_custom_band_count(self, sample_structural_features):
        """Should support custom band count."""
        sig = minhash_signature(sample_structural_features)
        bands = signature_to_bands(sig, num_bands=4)

        assert len(bands) == 4

    def test_bands_are_tuples(self, sample_structural_features):
        """Each band should be a tuple."""
        sig = minhash_signature(sample_structural_features)
        bands = signature_to_bands(sig)

        for band in bands:
            assert isinstance(band, tuple)

    def test_bands_cover_full_signature(self, sample_structural_features):
        """Bands should cover the full signature."""
        sig = minhash_signature(sample_structural_features)
        bands = signature_to_bands(sig, num_bands=8)

        # 128 hashes / 8 bands = 16 per band
        assert all(len(band) == 16 for band in bands)

    def test_same_signature_same_bands(self, sample_structural_features):
        """Same signature should produce same bands."""
        sig = minhash_signature(sample_structural_features)
        bands1 = signature_to_bands(sig)
        bands2 = signature_to_bands(sig)

        assert bands1 == bands2


class TestLSHIndexDataClasses:
    """Test LSH index data structures."""

    def test_lsh_candidate_dataclass(self):
        """LSHCandidate should store template_id and similarity."""
        from src.services.lsh_index import LSHCandidate

        candidate = LSHCandidate(
            template_id=uuid7(),
            estimated_similarity=0.85,
        )

        assert candidate.estimated_similarity == 0.85


class TestLSHIndexHelpers:
    """Test LSH index helper functions."""

    def test_hash_band(self):
        """_hash_band should return consistent hash."""
        from src.services.lsh_index import _hash_band

        band = (1, 2, 3, 4, 5)
        hash1 = _hash_band(band)
        hash2 = _hash_band(band)

        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) == 16  # MD5 truncated to 16 chars

    def test_signature_bytes_roundtrip(self):
        """Signature should survive bytes roundtrip."""
        from src.services.lsh_index import _bytes_to_signature, _signature_to_bytes

        original = (1, 2, 3, 4, 5, 100, 1000, 10000)
        bytes_data = _signature_to_bytes(original)
        recovered = _bytes_to_signature(bytes_data)

        assert recovered == original


class TestMinHashLSHClass:
    """Test MinHashLSH class (without Redis)."""

    def test_lsh_init(self):
        """MinHashLSH should initialize with default bands."""
        from src.services.lsh_index import MinHashLSH

        lsh = MinHashLSH()
        assert lsh.num_bands == 8
        assert lsh.available is False  # Not initialized yet

    def test_lsh_custom_bands(self):
        """MinHashLSH should accept custom band count."""
        from src.services.lsh_index import MinHashLSH

        lsh = MinHashLSH(num_bands=16)
        assert lsh.num_bands == 16


class TestMinHashLSHWithMockedRedis:
    """Test MinHashLSH with mocked Redis."""

    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Should initialize successfully with Redis."""
        from unittest.mock import AsyncMock, patch
        from src.services.lsh_index import MinHashLSH

        lsh = MinHashLSH()
        mock_redis = AsyncMock()

        with patch("src.services.rate_limiter.get_redis_client", new_callable=AsyncMock, return_value=mock_redis):
            result = await lsh.initialize()

        assert result is True
        assert lsh.available is True
        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Should handle Redis connection failure gracefully."""
        from unittest.mock import AsyncMock, patch
        from src.services.lsh_index import MinHashLSH

        lsh = MinHashLSH()

        with patch("src.services.rate_limiter.get_redis_client", new_callable=AsyncMock, side_effect=Exception("Connection failed")):
            result = await lsh.initialize()

        assert result is False
        assert lsh.available is False

    @pytest.mark.asyncio
    async def test_add_template_when_unavailable(self, sample_structural_features):
        """Should return False when LSH is unavailable."""
        from src.services.lsh_index import MinHashLSH

        lsh = MinHashLSH()
        lsh._available = False

        result = await lsh.add_template(uuid7(), uuid7(), sample_structural_features)
        assert result is False

    @pytest.mark.asyncio
    async def test_query_when_unavailable(self, sample_structural_features):
        """Should return empty list when LSH is unavailable."""
        from src.services.lsh_index import MinHashLSH

        lsh = MinHashLSH()
        lsh._available = False

        candidates = await lsh.query(sample_structural_features, k=5)

        assert candidates == []

    @pytest.mark.asyncio
    async def test_remove_template_when_unavailable(self):
        """Should return False when LSH is unavailable."""
        from src.services.lsh_index import MinHashLSH

        lsh = MinHashLSH()
        lsh._available = False

        result = await lsh.remove_template(uuid7())
        assert result is False


class TestGetLshIndex:
    """Tests for get_lsh_index singleton function."""

    @pytest.mark.asyncio
    async def test_get_lsh_index_creates_instance(self):
        """Should create and initialize LSH index on first call."""
        from unittest.mock import AsyncMock, patch
        import src.services.lsh_index as lsh_module

        # Reset global state
        lsh_module._lsh_index = None

        mock_lsh = AsyncMock()
        mock_lsh.initialize = AsyncMock(return_value=True)

        with patch.object(lsh_module, "MinHashLSH", return_value=mock_lsh):
            result = await lsh_module.get_lsh_index()

        assert result == mock_lsh
        mock_lsh.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_lsh_index_returns_existing(self):
        """Should return existing instance on subsequent calls."""
        from unittest.mock import AsyncMock
        import src.services.lsh_index as lsh_module

        mock_lsh = AsyncMock()
        lsh_module._lsh_index = mock_lsh

        result = await lsh_module.get_lsh_index()

        assert result == mock_lsh


class TestTemplateMatcher:
    """Test template matcher integration with LSH."""

    def test_match_template_has_use_lsh_param(self):
        """match_template should have use_lsh parameter."""
        import inspect

        from src.services.template_matcher import match_template

        sig = inspect.signature(match_template)
        assert "use_lsh" in sig.parameters
        assert sig.parameters["use_lsh"].default is True

    def test_index_template_exists(self):
        """index_template function should exist."""
        from src.services.template_matcher import index_template

        assert callable(index_template)

    def test_unindex_template_exists(self):
        """unindex_template function should exist."""
        from src.services.template_matcher import unindex_template

        assert callable(unindex_template)
