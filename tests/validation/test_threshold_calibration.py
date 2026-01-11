"""Threshold calibration analysis using real document data.

This module analyzes the similarity distribution of real documents
to validate and potentially adjust our matching thresholds.

Current thresholds:
- MATCH: >= 0.85
- REVIEW: 0.50 - 0.85
- NEW: < 0.50
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.services.template_matcher import (
    _cosine_similarity,
    _extract_feature_vector,
)


@dataclass
class CalibrationResult:
    """Result of threshold calibration analysis."""

    dataset: str
    sample_count: int
    pair_count: int
    similarity_stats: dict
    distribution: dict
    recommended_thresholds: dict
    current_thresholds: dict


class TestThresholdCalibration:
    """Analyze optimal thresholds using real data."""

    @pytest.mark.validation
    def test_generate_calibration_report(self, funsd_samples):
        """Generate a threshold calibration report from FUNSD data."""
        import random

        random.seed(42)

        # Compute all pairwise similarities (sample for large datasets)
        n = len(funsd_samples)
        max_pairs = 2000

        similarities = []

        if n * (n - 1) / 2 <= max_pairs:
            # Compute all pairs
            for i in range(n):
                vec_i = _extract_feature_vector(funsd_samples[i].features)
                for j in range(i + 1, n):
                    vec_j = _extract_feature_vector(funsd_samples[j].features)
                    sim = _cosine_similarity(vec_i, vec_j)
                    similarities.append(sim)
        else:
            # Sample pairs randomly
            indices = list(range(n))
            for _ in range(max_pairs):
                i, j = random.sample(indices, 2)
                vec_i = _extract_feature_vector(funsd_samples[i].features)
                vec_j = _extract_feature_vector(funsd_samples[j].features)
                sim = _cosine_similarity(vec_i, vec_j)
                similarities.append(sim)

        # Calculate statistics
        similarities.sort()
        stats = {
            "min": similarities[0],
            "max": similarities[-1],
            "mean": sum(similarities) / len(similarities),
            "median": similarities[len(similarities) // 2],
            "p10": similarities[int(len(similarities) * 0.10)],
            "p25": similarities[int(len(similarities) * 0.25)],
            "p75": similarities[int(len(similarities) * 0.75)],
            "p90": similarities[int(len(similarities) * 0.90)],
            "p95": similarities[int(len(similarities) * 0.95)],
        }

        # Distribution buckets (10% intervals)
        buckets = defaultdict(int)
        for sim in similarities:
            bucket = int(sim * 10) / 10  # Round down to nearest 0.1
            buckets[f"{bucket:.1f}-{bucket + 0.1:.1f}"] += 1

        # Calculate percentages
        distribution = {
            k: {"count": v, "percent": v / len(similarities) * 100}
            for k, v in sorted(buckets.items())
        }

        # Recommend thresholds based on percentiles
        # MATCH threshold: where top ~20% of similarities start (p80)
        # REVIEW threshold: where bottom ~20% end (p20)
        recommended = {
            "match_threshold": round(stats["p75"], 2),  # Top 25% are matches
            "review_threshold": round(stats["p25"], 2),  # Bottom 25% are new
        }

        current = {
            "match_threshold": 0.85,
            "review_threshold": 0.50,
        }

        # Generate report
        result = CalibrationResult(
            dataset="funsd",
            sample_count=n,
            pair_count=len(similarities),
            similarity_stats=stats,
            distribution=distribution,
            recommended_thresholds=recommended,
            current_thresholds=current,
        )

        # Print report
        print("\n" + "=" * 60)
        print("THRESHOLD CALIBRATION REPORT")
        print("=" * 60)
        print(f"\nDataset: {result.dataset}")
        print(f"Samples: {result.sample_count}")
        print(f"Pairs analyzed: {result.pair_count}")

        print("\n--- Similarity Statistics ---")
        for key, value in result.similarity_stats.items():
            print(f"  {key}: {value:.4f}")

        print("\n--- Distribution ---")
        for bucket, data in result.distribution.items():
            bar = "#" * int(data["percent"] / 2)
            print(f"  {bucket}: {data['count']:4d} ({data['percent']:5.1f}%) {bar}")

        print("\n--- Threshold Comparison ---")
        print(f"  Current MATCH threshold:     {current['match_threshold']}")
        print(f"  Recommended MATCH threshold: {recommended['match_threshold']}")
        print(f"  Current REVIEW threshold:    {current['review_threshold']}")
        print(f"  Recommended REVIEW threshold: {recommended['review_threshold']}")

        # Analyze impact of current vs recommended thresholds
        current_match = sum(1 for s in similarities if s >= current["match_threshold"])
        current_review = sum(
            1 for s in similarities if current["review_threshold"] <= s < current["match_threshold"]
        )
        current_new = sum(1 for s in similarities if s < current["review_threshold"])

        rec_match = sum(1 for s in similarities if s >= recommended["match_threshold"])
        rec_review = sum(
            1
            for s in similarities
            if recommended["review_threshold"] <= s < recommended["match_threshold"]
        )
        rec_new = sum(1 for s in similarities if s < recommended["review_threshold"])

        print("\n--- Decision Distribution ---")
        print("  With CURRENT thresholds:")
        print(f"    MATCH:  {current_match:4d} ({current_match / len(similarities) * 100:5.1f}%)")
        print(f"    REVIEW: {current_review:4d} ({current_review / len(similarities) * 100:5.1f}%)")
        print(f"    NEW:    {current_new:4d} ({current_new / len(similarities) * 100:5.1f}%)")

        print("  With RECOMMENDED thresholds:")
        print(f"    MATCH:  {rec_match:4d} ({rec_match / len(similarities) * 100:5.1f}%)")
        print(f"    REVIEW: {rec_review:4d} ({rec_review / len(similarities) * 100:5.1f}%)")
        print(f"    NEW:    {rec_new:4d} ({rec_new / len(similarities) * 100:5.1f}%)")

        print("=" * 60)

        # Save report to file
        report_path = Path(__file__).parent.parent.parent / "threshold_calibration_report.json"
        report_data = {
            "dataset": result.dataset,
            "sample_count": result.sample_count,
            "pair_count": result.pair_count,
            "similarity_stats": result.similarity_stats,
            "distribution": {k: v["percent"] for k, v in result.distribution.items()},
            "current_thresholds": result.current_thresholds,
            "recommended_thresholds": result.recommended_thresholds,
            "decision_distribution": {
                "current": {
                    "match_percent": current_match / len(similarities) * 100,
                    "review_percent": current_review / len(similarities) * 100,
                    "new_percent": current_new / len(similarities) * 100,
                },
                "recommended": {
                    "match_percent": rec_match / len(similarities) * 100,
                    "review_percent": rec_review / len(similarities) * 100,
                    "new_percent": rec_new / len(similarities) * 100,
                },
            },
        }

        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\nReport saved to: {report_path}")

        # Assertions for validation
        assert stats["mean"] > 0.3, f"Mean similarity too low: {stats['mean']}"
        assert stats["max"] <= 1.0, f"Max similarity exceeds 1.0: {stats['max']}"
        assert stats["min"] >= 0.0, f"Min similarity below 0.0: {stats['min']}"

    @pytest.mark.validation
    def test_drift_score_sensitivity(self, funsd_samples):
        """Test drift detection sensitivity on real data."""
        from src.models import Template, TemplateStatus
        from src.services.drift_detector import compute_drift_score

        if len(funsd_samples) < 20:
            pytest.skip("Not enough samples for drift analysis")

        # Use first sample as baseline template
        baseline = funsd_samples[0]
        template = Template(
            tenant_id="00000000-0000-0000-0000-000000000000",
            template_id="baseline",
            version="1.0",
            fingerprint="a" * 64,
            structural_features=baseline.features.model_dump(),
            baseline_reliability=0.85,
            correction_rules=[],
            status=TemplateStatus.ACTIVE,
        )

        # Compute drift for other samples
        drift_scores = []
        for sample in funsd_samples[1:50]:
            import asyncio

            drift = asyncio.get_event_loop().run_until_complete(
                compute_drift_score(template, sample.features)
            )
            drift_scores.append(
                {
                    "sample_id": sample.id,
                    "drift_score": drift,
                }
            )

        # Analyze drift distribution
        drift_values = [d["drift_score"] for d in drift_scores]
        stats = {
            "min": min(drift_values),
            "max": max(drift_values),
            "mean": sum(drift_values) / len(drift_values),
        }

        # Count by drift severity
        low_drift = sum(1 for d in drift_values if d < 0.15)
        medium_drift = sum(1 for d in drift_values if 0.15 <= d < 0.30)
        high_drift = sum(1 for d in drift_values if d >= 0.30)

        print("\n--- Drift Score Analysis ---")
        print(f"  Samples analyzed: {len(drift_scores)}")
        print(f"  Min: {stats['min']:.4f}, Max: {stats['max']:.4f}, Mean: {stats['mean']:.4f}")
        print(f"  Low drift (<0.15):    {low_drift} ({low_drift / len(drift_scores) * 100:.1f}%)")
        print(
            f"  Medium drift (0.15-0.30): {medium_drift} ({medium_drift / len(drift_scores) * 100:.1f}%)"
        )
        print(f"  High drift (>=0.30):  {high_drift} ({high_drift / len(drift_scores) * 100:.1f}%)")

        # Most forms should show some drift (they're different documents)
        assert stats["max"] > 0.1, "No significant drift detected between forms"
