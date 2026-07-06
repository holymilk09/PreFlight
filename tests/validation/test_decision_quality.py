"""Ground-truth decision-quality harness (unbiased, synthetic).

Real datasets (FUNSD/SROIE) are unreachable in sandboxed environments, so this
harness builds its own ground truth: registered templates with *known* identity,
then perturbed variants at controlled magnitudes. Because the generator knows
which template each variant came from, we can measure — against the actual
production scoring code — how often the system identifies the right template,
how well similarity separates same-template from different-template pairs, and
whether drift scores respond monotonically to real perturbation.

The perturbation model and pass-thresholds were fixed BEFORE results were
observed (see PERTURBATION_LEVELS and the assertions). Assertions are
deliberately weak sanity floors; the point of this module is the printed
scorecard and decision_quality_report.json, not green checkmarks.

Perturbation semantics:
- 0.05 -> same document through OCR jitter (should MATCH its template)
- 0.15 -> mild template revision (MATCH or REVIEW)
- 0.30 -> significant revision (REVIEW expected)
- 0.50 -> major redesign (should trend away from MATCH)
"""

import json
import random
from dataclasses import dataclass

import pytest
from uuid_extensions import uuid7

from src.models import StructuralFeatures, Template, TemplateStatus
from src.services.drift_detector import compute_drift_score
from src.services.template_matcher import (
    _cosine_similarity,
    _extract_feature_vector,
    _match_confidence,
)
from tests.fixtures.datasets.synthetic_documents import (
    DOCUMENT_PROFILES,
    SyntheticDocumentGenerator,
)

SEED = 1337
PERTURBATION_LEVELS = [0.05, 0.15, 0.30, 0.50]
TEMPLATES_PER_CATEGORY = 5
VARIANTS_PER_TEMPLATE = 10
REPORT_PATH = "decision_quality_report.json"


def perturb(features: StructuralFeatures, level: float, rng: random.Random) -> StructuralFeatures:
    """Perturb features by a controlled magnitude (defined a priori)."""

    def jitter_count(value: int, floor: int = 0) -> int:
        return max(floor, round(value * (1.0 + rng.gauss(0.0, level))))

    def jitter_unit(value: float) -> float:
        return min(1.0, max(0.0, value + rng.uniform(-level, level)))

    table_count = features.table_count
    if rng.random() < level:
        table_count = max(0, table_count + rng.choice([-1, 1]))

    page_count = features.page_count
    if rng.random() < level / 2:
        page_count += 1

    column_count = features.column_count
    if rng.random() < level / 4:
        column_count = min(4, max(1, column_count + rng.choice([-1, 1])))

    return StructuralFeatures(
        element_count=jitter_count(features.element_count, floor=1),
        table_count=table_count,
        text_block_count=jitter_count(features.text_block_count, floor=1),
        image_count=jitter_count(features.image_count),
        page_count=page_count,
        text_density=jitter_unit(features.text_density),
        layout_complexity=jitter_unit(features.layout_complexity),
        column_count=column_count,
        has_header=(not features.has_header) if rng.random() < level / 2 else features.has_header,
        has_footer=(not features.has_footer) if rng.random() < level / 2 else features.has_footer,
        bounding_boxes=[],
    )


@dataclass
class Case:
    """One ground-truth trial: a variant of a known parent template."""

    parent_idx: int
    level: float
    features: StructuralFeatures


@pytest.fixture(scope="module")
def ground_truth():
    """Build the template pool and perturbed variants (seeded, deterministic)."""
    gen = SyntheticDocumentGenerator(seed=SEED)
    rng = random.Random(SEED)

    pool: list[StructuralFeatures] = []
    categories: list[str] = []
    for category in DOCUMENT_PROFILES:
        for sample in gen.generate(category, TEMPLATES_PER_CATEGORY):
            pool.append(sample.features)
            categories.append(category)

    cases: list[Case] = []
    for parent_idx, base in enumerate(pool):
        for level in PERTURBATION_LEVELS:
            for _ in range(VARIANTS_PER_TEMPLATE):
                cases.append(Case(parent_idx, level, perturb(base, level, rng)))

    # Novel documents: same categories, different seed, never registered.
    # Their best-similarity against the pool defines where NEW should start.
    novel_gen = SyntheticDocumentGenerator(seed=SEED + 1)
    novel: list[StructuralFeatures] = []
    for category in DOCUMENT_PROFILES:
        for sample in novel_gen.generate(category, TEMPLATES_PER_CATEGORY * 2):
            novel.append(sample.features)

    return pool, categories, cases, novel


def _rank_auc(positives: list[float], negatives: list[float]) -> float:
    """Rank-based ROC-AUC: P(random positive > random negative)."""
    wins = ties = 0
    for p in positives:
        for n in negatives:
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    total = len(positives) * len(negatives)
    return (wins + 0.5 * ties) / total if total else 0.0


def _l1_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Gower-style similarity: 1 - mean absolute difference over [0,1] dims."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    return 1.0 - sum(abs(a - b) for a, b in zip(vec_a, vec_b, strict=True)) / len(vec_a)


METRICS = {
    "cosine": _cosine_similarity,
    "l1_gower": _l1_similarity,
    # The actual production path: L1-Gower + calibration remap. Decision
    # mixes for this row reflect what /v1/evaluate would really decide.
    "production": _match_confidence,
}


def _evaluate_metric(metric, pool_vectors, cases):
    """Run identification/separation stats for one similarity metric."""
    top1 = {lvl: [] for lvl in PERTURBATION_LEVELS}
    parent_sims = {lvl: [] for lvl in PERTURBATION_LEVELS}
    best_other_sims = {lvl: [] for lvl in PERTURBATION_LEVELS}
    decisions = {lvl: {"MATCH": 0, "REVIEW": 0, "NEW": 0} for lvl in PERTURBATION_LEVELS}

    for case in cases:
        vec = _extract_feature_vector(case.features)
        sims = [metric(vec, pv) for pv in pool_vectors]
        best_idx = max(range(len(sims)), key=lambda i: sims[i])
        best_sim = sims[best_idx]

        top1[case.level].append(best_idx == case.parent_idx)
        parent_sims[case.level].append(sims[case.parent_idx])
        best_other_sims[case.level].append(
            max(s for i, s in enumerate(sims) if i != case.parent_idx)
        )
        bucket = "MATCH" if best_sim >= 0.85 else "REVIEW" if best_sim >= 0.50 else "NEW"
        decisions[case.level][bucket] += 1

    auc = {lvl: _rank_auc(parent_sims[lvl], best_other_sims[lvl]) for lvl in PERTURBATION_LEVELS}
    return top1, parent_sims, best_other_sims, decisions, auc


def _best_threshold(positives: list[float], negatives: list[float]) -> tuple[float, float]:
    """Threshold maximizing balanced accuracy for 'same template' detection."""
    best_t, best_score = 0.0, 0.0
    for i in range(101):
        t = i / 100
        tpr = sum(1 for p in positives if p >= t) / len(positives)
        tnr = sum(1 for n in negatives if n < t) / len(negatives)
        score = (tpr + tnr) / 2
        if score > best_score:
            best_score, best_t = score, t
    return best_t, best_score


class TestDecisionQuality:
    @pytest.mark.validation
    def test_scorecard(self, ground_truth):
        """Measure identification accuracy, separation, and drift response."""
        pool, categories, cases, novel = ground_truth
        pool_vectors = [_extract_feature_vector(f) for f in pool]

        results = {name: _evaluate_metric(fn, pool_vectors, cases) for name, fn in METRICS.items()}

        # Best similarity of never-registered documents against the pool.
        novel_best: dict[str, list[float]] = {}
        for name, fn in METRICS.items():
            novel_best[name] = [
                max(fn(_extract_feature_vector(f), pv) for pv in pool_vectors) for f in novel
            ]

        # --- 3. Drift response (production drift scorer, real Template) -----
        drift_by_level: dict[float, list[float]] = {lvl: [] for lvl in PERTURBATION_LEVELS}
        import asyncio

        async def _drift(base: StructuralFeatures, variant: StructuralFeatures) -> float:
            template = Template(
                id=uuid7(),
                tenant_id=uuid7(),
                template_id="gt",
                version="1",
                fingerprint="0" * 64,
                structural_features=base.model_dump(),
                baseline_reliability=0.9,
                correction_rules=[],
                status=TemplateStatus.ACTIVE,
            )
            return await compute_drift_score(template, variant)

        async def _all_drifts() -> None:
            for case in cases:
                drift_by_level[case.level].append(
                    await _drift(pool[case.parent_idx], case.features)
                )

        asyncio.get_event_loop().run_until_complete(_all_drifts())

        # --- Scorecard -------------------------------------------------------
        def mean(xs):
            return sum(xs) / len(xs) if xs else 0.0

        report = {"seed": SEED, "pool_size": len(pool), "cases": len(cases), "metrics": {}}
        print(f"\n{'=' * 78}")
        print(
            f"DECISION QUALITY SCORECARD  (pool={len(pool)} templates across "
            f"{len(DOCUMENT_PROFILES)} categories, {len(cases)} trials, seed={SEED})"
        )
        print(f"{'=' * 78}")

        for name, (top1, parent_sims, best_other_sims, decisions, auc) in results.items():
            print(f"\n--- metric: {name} ---")
            print(
                f"{'perturb':>8} {'top1_acc':>9} {'sim(parent)':>12} {'sim(other)':>11} "
                f"{'AUC':>6} {'drift':>6}  decision mix @0.85/0.50"
            )
            metric_report = {"levels": {}}
            for lvl in PERTURBATION_LEVELS:
                n = len(top1[lvl])
                acc = sum(top1[lvl]) / n
                d = decisions[lvl]
                mix = f"M:{d['MATCH'] / n:.0%} R:{d['REVIEW'] / n:.0%} N:{d['NEW'] / n:.0%}"
                print(
                    f"{lvl:>8.2f} {acc:>9.1%} {mean(parent_sims[lvl]):>12.3f} "
                    f"{mean(best_other_sims[lvl]):>11.3f} {auc[lvl]:>6.3f} "
                    f"{mean(drift_by_level[lvl]):>6.3f}  {mix}"
                )
                metric_report["levels"][str(lvl)] = {
                    "top1_accuracy": acc,
                    "mean_parent_similarity": mean(parent_sims[lvl]),
                    "mean_best_other_similarity": mean(best_other_sims[lvl]),
                    "auc": auc[lvl],
                    "mean_drift": mean(drift_by_level[lvl]),
                    "decision_mix": {k: v / n for k, v in d.items()},
                }

            # Empirical MATCH threshold: "should MATCH" population (5-15%
            # perturbation) vs impostors, chosen by balanced accuracy.
            positives = parent_sims[0.05] + parent_sims[0.15]
            negatives = best_other_sims[0.05] + best_other_sims[0.15]
            t_match, bal_acc = _best_threshold(positives, negatives)

            # Empirical NEW threshold: known-template variants (any level) vs
            # never-registered documents' best similarity.
            known = [s for lvl in PERTURBATION_LEVELS for s in parent_sims[lvl]]
            t_new, new_bal_acc = _best_threshold(known, novel_best[name])
            novel_mean = mean(novel_best[name])
            print(
                f"  empirical MATCH threshold: {t_match:.2f} (balanced acc {bal_acc:.1%}) | "
                f"NEW threshold: {t_new:.2f} (balanced acc {new_bal_acc:.1%}, "
                f"novel best-sim mean {novel_mean:.3f})"
            )
            metric_report["empirical_match_threshold"] = t_match
            metric_report["balanced_accuracy_at_match_threshold"] = bal_acc
            metric_report["empirical_new_threshold"] = t_new
            metric_report["balanced_accuracy_at_new_threshold"] = new_bal_acc
            metric_report["novel_best_similarity_mean"] = novel_mean
            report["metrics"][name] = metric_report

        with open(REPORT_PATH, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport written to {REPORT_PATH}")

        # --- Weak sanity floors (fixed a priori) -----------------------------
        # Chance top-1 accuracy is 1/pool_size (~3%). The production metric
        # must beat chance decisively at low perturbation.
        prod_top1 = results["production"][0]
        assert sum(prod_top1[0.05]) / len(prod_top1[0.05]) > 0.5, (
            "top-1 at 5% perturbation below 50%"
        )
        # Drift must respond to perturbation on average (monotone means).
        drift_means = [mean(drift_by_level[lvl]) for lvl in PERTURBATION_LEVELS]
        assert all(b >= a - 0.02 for a, b in zip(drift_means[:-1], drift_means[1:], strict=True)), (
            f"drift means not increasing: {drift_means}"
        )
        # Separation must beat a coin flip for the production metric.
        prod_auc = results["production"][4]
        assert prod_auc[0.05] > 0.6, f"AUC at 5% perturbation is {prod_auc[0.05]:.3f}"
        # Fail-safe: barely-perturbed known docs must mostly auto-MATCH...
        prod_decisions = results["production"][3]
        n05 = sum(prod_decisions[0.05].values())
        assert prod_decisions[0.05]["MATCH"] / n05 > 0.7, "5%-perturbed docs not matching"
        # ...while heavily-redesigned docs must NOT sail through as MATCH.
        n50 = sum(prod_decisions[0.50].values())
        match_rate_50 = prod_decisions[0.50]["MATCH"] / n50
        assert match_rate_50 < 0.5, (
            f"{match_rate_50:.0%} of 50%-redesigned docs still auto-MATCH (fail-safe violated)"
        )
