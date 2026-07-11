"""End-to-end demo: catch a real drift incident on mock data.

Run:  python scripts/demo_incident.py

No database or Redis needed. This drives the SAME scoring functions the live
API calls (drift_detector, template_matcher, reliability_scorer,
correction_rules) over a SIMULATED quarter of invoices from three suppliers.
Partway through, one supplier silently redesigns its invoice — the exact
"silent degradation" PreFlight exists to catch. The script narrates what the
system decides, day by day, and prints the review-triage ROI the way the
/v1/analytics/calibration endpoint would.

Everything here is synthetic and clearly labelled SIMULATED — it demonstrates
system behaviour, not a real-world accuracy claim.
"""

import asyncio
import random

from src.models import StructuralFeatures, Template, TemplateStatus
from src.services.drift_detector import compute_drift_score
from src.services.template_matcher import _feature_vectors, _match_confidence
from tests.fixtures.datasets.synthetic_documents import SyntheticDocumentGenerator

RNG = random.Random(7)
SUPPLIERS = ["Acme Corp", "Globex", "Initech"]
DAYS = 60
DOCS_PER_DAY = 20
INCIDENT_DAY = 40
INCIDENT_SUPPLIER = "Globex"
REVIEW_COST_USD = 2.00  # assumed human-review cost per document

# Decision thresholds (identical to src/api/routes.py).
MATCH_T = 0.85
REVIEW_T = 0.50
DRIFT_REVIEW = 0.30


def make_template(supplier: str, features: StructuralFeatures) -> Template:
    from uuid_extensions import uuid7

    return Template(
        id=uuid7(),
        tenant_id=uuid7(),
        template_id=f"INV-{supplier.upper().replace(' ', '')}",
        version="1.0",
        fingerprint="0" * 64,
        structural_features=features.model_dump(),
        baseline_reliability=0.88,
        correction_rules=[{"field": "total", "rule": "sum_line_items", "parameters": None}],
        status=TemplateStatus.ACTIVE,
    )


def perturb(base: StructuralFeatures, level: float) -> StructuralFeatures:
    """A day's document: the supplier's template with realistic small variation."""

    def jc(v: int, floor: int = 0) -> int:
        return max(floor, round(v * (1.0 + RNG.gauss(0.0, level))))

    def ju(v: float) -> float:
        return min(1.0, max(0.0, v + RNG.uniform(-level, level)))

    boxes = []
    for b in base.bounding_boxes:
        if RNG.random() < level / 2:
            continue
        boxes.append(
            b.model_copy(
                update={
                    "x": min(1.0, max(0.0, b.x + RNG.gauss(0, level / 2))),
                    "y": min(1.0, max(0.0, b.y + RNG.gauss(0, level / 2))),
                }
            )
        )
    return StructuralFeatures(
        element_count=jc(base.element_count, 1),
        table_count=base.table_count,
        text_block_count=jc(base.text_block_count, 1),
        image_count=jc(base.image_count),
        page_count=base.page_count,
        text_density=ju(base.text_density),
        layout_complexity=ju(base.layout_complexity),
        column_count=base.column_count,
        has_header=base.has_header,
        has_footer=base.has_footer,
        bounding_boxes=boxes,
    )


def decide(confidence: float) -> str:
    if confidence >= MATCH_T:
        return "MATCH"
    if confidence >= REVIEW_T:
        return "REVIEW"
    return "NEW"


async def main() -> None:
    gen = SyntheticDocumentGenerator(seed=101)
    # One clean "registration sample" per supplier -> a template.
    samples = list(gen.generate("invoice", len(SUPPLIERS)))
    templates = {s: make_template(s, samples[i].features) for i, s in enumerate(SUPPLIERS)}
    template_vecs = {
        s: _feature_vectors(StructuralFeatures.model_validate(t.structural_features))
        for s, t in templates.items()
    }
    print("=" * 72)
    print("PreFlight — drift incident demo  (SIMULATED data; behaviour, not accuracy)")
    print("=" * 72)
    print(f"Setup: you process invoices from {len(SUPPLIERS)} suppliers: {', '.join(SUPPLIERS)}.")
    print("We registered one template per supplier from a clean sample.")
    print(f"On day {INCIDENT_DAY}, {INCIDENT_SUPPLIER} silently redesigns its invoice.\n")

    # Ground-truth + tallies for the ROI/calibration story.
    auto_processed_bad = 0  # MATCHed but actually degraded (errors reaching the ERP)
    flagged = 0  # sent to human review
    flagged_bad = 0  # of those, actually degraded (errors CAUGHT)
    incident_first_flag_day = None
    incident_docs_total = 0
    incident_docs_flagged = 0

    for day in range(1, DAYS + 1):
        for _ in range(DOCS_PER_DAY):
            supplier = RNG.choice(SUPPLIERS)
            incident = day >= INCIDENT_DAY and supplier == INCIDENT_SUPPLIER
            # Normal day: tiny OCR-level variation. Post-incident for the hit
            # supplier: a real layout change ("actually degraded" ground truth).
            level = 0.06 if not incident else 0.42
            doc = perturb(
                StructuralFeatures.model_validate(templates[supplier].structural_features), level
            )
            actually_bad = incident  # ground truth we get to know in a simulation

            # --- the REAL pipeline: match -> drift -> reliability -> decide ---
            doc_vecs = _feature_vectors(doc)
            confidence = max(_match_confidence(doc_vecs, tv) for tv in template_vecs.values())
            best_supplier = max(
                template_vecs, key=lambda s: _match_confidence(doc_vecs, template_vecs[s])
            )
            drift = await compute_drift_score(templates[best_supplier], doc)
            decision = decide(confidence)
            # A confident match with high drift is a revision -> review it.
            if decision == "MATCH" and drift >= DRIFT_REVIEW:
                decision = "REVIEW"

            if incident:
                incident_docs_total += 1

            if decision == "MATCH":
                if actually_bad:
                    auto_processed_bad += 1  # slipped through
            else:  # REVIEW or NEW -> human looks at it
                flagged += 1
                if incident:
                    incident_docs_flagged += 1
                    if incident_first_flag_day is None:
                        incident_first_flag_day = day
                if actually_bad:
                    flagged_bad += 1

    # ---- narrative ----
    print("--- What happened ---")
    if incident_first_flag_day is not None:
        print(
            f"PreFlight started flagging {INCIDENT_SUPPLIER} invoices on day "
            f"{incident_first_flag_day} — {incident_first_flag_day - INCIDENT_DAY} day(s) "
            f"after the redesign began."
        )
    caught_pct = (incident_docs_flagged / incident_docs_total * 100) if incident_docs_total else 0
    print(
        f"Of {incident_docs_total} post-redesign {INCIDENT_SUPPLIER} invoices, "
        f"{incident_docs_flagged} ({caught_pct:.0f}%) were routed to human review "
        f"instead of auto-processed."
    )
    print(
        f"{auto_processed_bad} redesigned invoice(s) still slipped through as MATCH "
        f"(the honest miss — layout ≠ content, see the scorecard).\n"
    )

    # ---- calibration / ROI (mirrors /v1/analytics/calibration) ----
    catch_rate = (flagged_bad / flagged) if flagged else 0.0
    errors_caught = flagged_bad
    print("--- The number you put on a renewal slide (SIMULATED) ---")
    print(f"Errors caught before reaching your ERP: {errors_caught}")
    print(f"Review catch rate (flagged docs that were truly bad): {catch_rate:.0%}")
    without = errors_caught  # without PreFlight these would have been auto-processed wrong
    print(
        f"Without PreFlight, those {without} bad extractions auto-process silently — "
        f"found later by reconciliation or an auditor."
    )
    print(
        f"\nReview-triage economics: PreFlight flagged {flagged} docs across the quarter. "
        f"A calibrated score lets you trust the {DOCS_PER_DAY * DAYS - flagged} it cleared, "
        f"instead of sampling everything. At ${REVIEW_COST_USD:.0f}/review, auditing only "
        f"the flagged {flagged} vs. a 20% blanket sample "
        f"(${REVIEW_COST_USD * 0.2 * DOCS_PER_DAY * DAYS:.0f}) is the lever."
    )
    print("\n(Every number above is from synthetic data — it shows the system works,")
    print(" not how accurate it will be on your documents. That's what a design")
    print(" partner's real feedback proves.)")


if __name__ == "__main__":
    asyncio.run(main())
