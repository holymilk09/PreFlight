# PreFlight Scorecard

*Unbiased self-assessment, July 2026 (updated after the spatial-features
pass). Every algorithm claim below is backed by the ground-truth harness
(`tests/validation/test_decision_quality.py`, seed 1337, 30 templates x 6
categories, 1200 perturbed trials + 60 novel documents; report:
`decision_quality_report.json`; weight/anchor derivation with held-out seeds:
`docs/calibration_derivation.json`). Real datasets (FUNSD/SROIE) are wired
but network-blocked in this environment; the harness is deliberately
adversarial instead: perturbation models and pass criteria were fixed before
results were observed, weights were selected on one seed and accepted only
after beating the scalar metric on every held-out seed.*

## Ratings

| Dimension | Score | Evidence |
|---|---|---|
| Drift detection | **8/10** | Monotone response to perturbation (0.07 → 0.20 → 0.33 → 0.41), crosses the 0.30 review threshold at the 30%-revision level — thresholds genuinely calibrated. Rolling EWMA baselines now prevent the gradual-evolution false alarm (simulation: static baseline ends ≥ 0.30 permanent alarm, rolling stays < 0.15). |
| Template matching (after 2 fix passes) | **8/10** | Was 2/10 (cosine: 90% of redesigns auto-MATCHed, novelty a coin flip). Pass 1: L1-Gower + measured calibration. Pass 2: 3x3 spatial occupancy grid from the bounding boxes (previously unused by matching), blended 0.3/0.7, weight chosen on seed 1337 and accepted on held-out seeds 2024/4242/9001 + an alternate pool. Top-1 identification @15% perturbation 72.7% → **88.7%**, @30% 44.3% → **68.7%**; balanced accuracy at the MATCH boundary 75.6% → **82.4%**; OCR-jitter docs still auto-MATCH at 97%. Legacy templates without boxes keep the scalar path (no silent degradation). |
| Novelty (NEW) detection | **6/10** | Improved by the spatial signal: known-vs-novel balanced accuracy 59.7% → **64.3%** (held-out 61-64%), novel docs' mean confidence 0.707 — solidly REVIEW, far from auto-match. **The pre-registered 0.70 target was NOT met**; the harness floor is consciously set at 0.60. Still the weakest signal: the measured known-vs-novel threshold sat above the MATCH threshold (overlapping populations), so the NEW anchor uses a documented mechanical fallback. Real progress here likely needs tenant feedback data, not more geometry. |
| Reliability scoring | **6/10 (self-calibrating, unvalidated)** | The formula is unchanged (baseline 40% + vendor confidence 35% + drift 25%), but `baseline_reliability` is no longer frozen at its registration value: feedback outcomes now move it by EWMA (anti-ratchet: replayed feedback is a no-op), so scores converge on each template's real-world accuracy as feedback accumulates. Still zero external validation — `/v1/analytics/calibration` remains the proof mechanism and kill-criterion. No accuracy claims until a design partner's report supports them. |
| Security/compliance posture | **9/10** | API-key scopes, tenant RLS, fail-closed Redis posture, append-only audit trail (DB trigger), login lockout, webhook secrets encrypted at rest, quota metering. This is the sellable compliance artifact. |
| Operability | **8/10** | 2 infrastructure services (Postgres, Redis — dead Temporal stack removed), one-click Render blueprint with migrations, SDK with 3 vendor adapters whose outputs are validated against the server's own schema, fingerprint byte-parity tested. LSH candidate index now actually populated by the template lifecycle (was dormant — never called); REJECT decision now reachable (safeguard ERRORs previously computed then ignored). |
| Test depth | **8/10** | 449 unit/service tests + 7 validation + integration suites in CI; the validation harness scores the algorithms rather than just exercising them. |
| Product-market proof | **2/10** | Zero external users. Everything above is necessary, none of it is sufficient. The only next milestone that matters: 2–3 design partners running real metadata, and their calibration reports. |

## What changed in the spatial pass (harness production row, report B → C)

| Metric | Before (scalar) | After (blended) |
|---|---|---|
| Top-1 identification @15% perturbation | 72.7% | **88.7%** |
| Top-1 @30% | 44.3% | **68.7%** |
| Balanced accuracy at MATCH boundary | 75.6% | **82.4%** |
| Known-vs-novel balanced accuracy | 60.5% | **64.3%** (target 0.70 missed — documented) |
| Novel docs' mean confidence | 0.832 | 0.707 (deeper into REVIEW) |
| OCR-jitter (5%) MATCH rate | 96% | 97% |

Also in this pass: reliability self-calibration from feedback (EWMA on
`baseline_reliability`, anti-ratchet), REJECT wired to safeguard ERRORs
(garbage extractions no longer scored or matched), LSH index wired to the
template lifecycle, deterministic per-sample synthetic generation + an
a-priori box perturbation model in the harness.

## What changed in the first pass (before → after)

| Metric (harness, production path) | Before | After |
|---|---|---|
| 50%-redesigned docs auto-MATCHing | 90% | **3%** (76% REVIEW / 20% NEW) |
| 5%-perturbed docs auto-MATCHing (STP preserved) | 98% | 96% |
| Novel documents | auto-MATCH | REVIEW (mean conf 0.834) |
| Balanced accuracy at MATCH boundary | 55% (cosine) | 77% (L1-Gower, calibrated to 0.85) |
| Gradual-evolution drift false alarm | permanent ≥ 0.30 | stays < 0.15 (EWMA baseline) |
| Infra services required | 3 (incl. unused Temporal) | 2 |
| Integration | hand-rolled feature extraction | `pip install ./sdk`, 3 lines |

## Honest limitations (do not paper over in sales conversations)

1. **Layout ≠ correctness.** We detect structural change, not wrong field
   values. The feedback loop is the compensating control and the proof
   mechanism — lead with "we catch drift and mis-routed review volume," not
   "we catch every extraction error."
2. **Same-genre discrimination is hard.** Two structurally similar invoices
   from different vendors can confuse top-1 matching. Correction-rule
   consequences are usually mild (same doc class), but it's real.
3. **Synthetic validation.** The harness is adversarial and fixed a priori,
   but it is not customer data. First design partner's calibration report is
   the actual exam.

## Solo-founder guidance (no domain background, no sales team)

- **Do not diversify industries.** One wedge: document-extraction
  observability for document-heavy ops teams (insurance/BPO/AP automation are
  the same buyer muscle). Every "what about legal/medical/logistics?" idea is
  the same product sold worse. Multi-industry positioning requires domain
  credibility a solo founder without background can't fake; a single sharp
  wedge doesn't.
- **Sell with artifacts, not expertise.** You can't out-domain-talk a claims
  VP. You can hand them: the retroactive demo (their 90 days of metadata →
  the drift chart catching an incident they remember), the calibration/ROI
  report, and the security posture doc. All three now exist in the product.
- **Self-serve first.** Free tier + SDK + Render one-click keeps distribution
  async (content, marketplace listings, IDP consultants) instead of
  founder-led enterprise sales you don't have the hours or background for.
- **The moat you can actually build alone** is the cross-tenant benchmark
  dataset and the compliance artifact — both accumulate while you sleep.
  The algorithms (see ratings) are replicable; don't bet on them.
