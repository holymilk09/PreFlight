"""Validation tests for template matching accuracy on real data.

These tests use the FUNSD dataset to validate that our cosine similarity
based template matching works correctly on real form documents.
"""

import pytest
from collections import defaultdict

from src.services.template_matcher import (
    _extract_feature_vector,
    _cosine_similarity,
)


class TestFeatureExtractionOnRealData:
    """Test feature extraction on real FUNSD documents."""

    @pytest.mark.validation
    def test_feature_vectors_are_valid(self, funsd_samples):
        """All FUNSD samples should produce valid feature vectors."""
        for sample in funsd_samples:
            vector = _extract_feature_vector(sample.features)

            # Vector should have 10 elements
            assert len(vector) == 10, f"Sample {sample.id} has wrong vector length"

            # All values should be in [0, 1]
            for i, v in enumerate(vector):
                assert 0.0 <= v <= 1.0, (
                    f"Sample {sample.id} has out-of-range value {v} at index {i}"
                )

    @pytest.mark.validation
    def test_feature_distribution(self, funsd_samples):
        """Feature values should have reasonable distribution."""
        # Collect all feature vectors
        vectors = [_extract_feature_vector(s.features) for s in funsd_samples]

        # Check each feature dimension
        feature_names = [
            "element_count", "table_count", "text_block_count", "image_count",
            "page_count", "text_density", "layout_complexity", "column_count",
            "has_header", "has_footer"
        ]

        stats = {}
        for i, name in enumerate(feature_names):
            values = [v[i] for v in vectors]
            stats[name] = {
                "min": min(values),
                "max": max(values),
                "mean": sum(values) / len(values),
            }

        # element_count should vary (forms have different complexity)
        assert stats["element_count"]["max"] > stats["element_count"]["min"], (
            "element_count has no variation"
        )

        # text_density should be > 0 for most forms
        assert stats["text_density"]["mean"] > 0.1, (
            f"text_density mean too low: {stats['text_density']['mean']}"
        )

        # Print stats for manual inspection
        print("\nFeature Distribution Statistics:")
        for name, s in stats.items():
            print(f"  {name}: min={s['min']:.3f}, max={s['max']:.3f}, mean={s['mean']:.3f}")


class TestSimilarityOnRealData:
    """Test cosine similarity on real FUNSD documents."""

    @pytest.mark.validation
    def test_self_similarity_is_one(self, funsd_samples):
        """Each document should have similarity 1.0 with itself."""
        for sample in funsd_samples[:50]:  # Test first 50
            vector = _extract_feature_vector(sample.features)
            similarity = _cosine_similarity(vector, vector)
            assert similarity == pytest.approx(1.0, abs=0.0001), (
                f"Sample {sample.id} self-similarity is {similarity}"
            )

    @pytest.mark.validation
    def test_similarity_distribution(self, funsd_samples):
        """Similarity between forms should follow expected distribution."""
        import random
        random.seed(42)

        # Sample pairs randomly
        similarities = []
        n = min(100, len(funsd_samples))
        indices = list(range(len(funsd_samples)))

        for _ in range(500):  # 500 random pairs
            i, j = random.sample(indices[:n], 2)
            vec_a = _extract_feature_vector(funsd_samples[i].features)
            vec_b = _extract_feature_vector(funsd_samples[j].features)
            sim = _cosine_similarity(vec_a, vec_b)
            similarities.append(sim)

        # Calculate statistics
        mean_sim = sum(similarities) / len(similarities)
        min_sim = min(similarities)
        max_sim = max(similarities)

        # Distribution buckets
        buckets = defaultdict(int)
        for sim in similarities:
            if sim >= 0.95:
                buckets["0.95-1.00"] += 1
            elif sim >= 0.85:
                buckets["0.85-0.95"] += 1
            elif sim >= 0.50:
                buckets["0.50-0.85"] += 1
            else:
                buckets["0.00-0.50"] += 1

        print(f"\nSimilarity Distribution (n={len(similarities)} pairs):")
        print(f"  Min: {min_sim:.3f}, Max: {max_sim:.3f}, Mean: {mean_sim:.3f}")
        print(f"  Buckets:")
        for bucket, count in sorted(buckets.items()):
            pct = count / len(similarities) * 100
            print(f"    {bucket}: {count} ({pct:.1f}%)")

        # Forms should generally be similar (same document type)
        # But not identical (different form layouts)
        assert mean_sim > 0.5, f"Mean similarity too low: {mean_sim}"
        assert mean_sim < 0.99, f"Mean similarity too high (no variation): {mean_sim}"

    @pytest.mark.validation
    def test_threshold_effectiveness(self, funsd_samples):
        """Test if current thresholds (0.50, 0.85) make sense for FUNSD."""
        import random
        random.seed(42)

        # Sample pairs
        n = min(100, len(funsd_samples))
        similarities = []

        for i in range(n):
            for j in range(i + 1, min(i + 10, n)):  # Compare nearby samples
                vec_a = _extract_feature_vector(funsd_samples[i].features)
                vec_b = _extract_feature_vector(funsd_samples[j].features)
                sim = _cosine_similarity(vec_a, vec_b)
                similarities.append({
                    "sample_a": funsd_samples[i].id,
                    "sample_b": funsd_samples[j].id,
                    "similarity": sim,
                })

        # Count decisions at current thresholds
        match_count = sum(1 for s in similarities if s["similarity"] >= 0.85)
        review_count = sum(1 for s in similarities if 0.50 <= s["similarity"] < 0.85)
        new_count = sum(1 for s in similarities if s["similarity"] < 0.50)

        total = len(similarities)
        print(f"\nThreshold Analysis (current thresholds: MATCH>=0.85, REVIEW>=0.50):")
        print(f"  MATCH (>=0.85): {match_count} ({match_count/total*100:.1f}%)")
        print(f"  REVIEW (0.50-0.85): {review_count} ({review_count/total*100:.1f}%)")
        print(f"  NEW (<0.50): {new_count} ({new_count/total*100:.1f}%)")

        # Since all samples are forms, we expect:
        # - Some high similarity (similar form structures)
        # - Very few completely dissimilar (< 0.50)
        assert new_count / total < 0.3, (
            f"Too many NEW decisions ({new_count/total*100:.1f}%) for same document type"
        )


class TestMatchingAccuracy:
    """End-to-end matching accuracy tests."""

    @pytest.mark.validation
    def test_similar_forms_match(self, funsd_train_samples, funsd_test_samples):
        """Forms from same dataset should have reasonable similarity."""
        if len(funsd_train_samples) < 10 or len(funsd_test_samples) < 5:
            pytest.skip("Not enough samples for matching test")

        # Use first 10 train samples as "templates"
        templates = funsd_train_samples[:10]
        template_vectors = [_extract_feature_vector(t.features) for t in templates]

        # Try to match test samples
        match_results = []
        for test_sample in funsd_test_samples[:20]:
            test_vector = _extract_feature_vector(test_sample.features)

            # Find best match
            best_sim = 0.0
            best_template = None
            for i, template_vec in enumerate(template_vectors):
                sim = _cosine_similarity(test_vector, template_vec)
                if sim > best_sim:
                    best_sim = sim
                    best_template = templates[i]

            match_results.append({
                "test_id": test_sample.id,
                "best_match": best_template.id if best_template else None,
                "similarity": best_sim,
                "decision": (
                    "MATCH" if best_sim >= 0.85 else
                    "REVIEW" if best_sim >= 0.50 else
                    "NEW"
                ),
            })

        # Analyze results
        decisions = defaultdict(int)
        for r in match_results:
            decisions[r["decision"]] += 1

        print(f"\nMatching Results (10 templates vs 20 test forms):")
        for decision, count in sorted(decisions.items()):
            print(f"  {decision}: {count}")

        # Most test forms should match or need review (same document type)
        match_or_review = decisions["MATCH"] + decisions["REVIEW"]
        assert match_or_review >= len(match_results) * 0.7, (
            f"Too few matches/reviews: {match_or_review}/{len(match_results)}"
        )
