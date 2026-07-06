# PreFlight Scorecard

*Unbiased self-assessment, July 2026. Every algorithm claim below is backed by
the ground-truth harness (`tests/validation/test_decision_quality.py`,
seed 1337, 30 templates x 6 categories, 1200 perturbed trials + 60 novel
documents; report: `decision_quality_report.json`). Real datasets
(FUNSD/SROIE) are wired but were network-blocked in this environment; the
harness is deliberately adversarial instead: perturbation model and pass
criteria were fixed before results were observed.*

## Ratings

| Dimension | Score | Evidence |
|---|---|---|
| Drift detection | **8/10** | Monotone response to perturbation (0.07 → 0.20 → 0.33 → 0.41), crosses the 0.30 review threshold at the 30%-revision level — thresholds genuinely calibrated. Rolling EWMA baselines now prevent the gradual-evolution false alarm (simulation: static baseline ends ≥ 0.30 permanent alarm, rolling stays < 0.15). |
| Template matching (after fix) | **7/10** | Was 2/10: cosine over the all-positive feature vector let 90% of heavily-redesigned docs auto-MATCH and made novelty detection a coin flip (novel best-sim 0.995). Now L1-Gower + measured calibration: 97% top-1 at low perturbation, redesign auto-MATCH 90% → 3%, novel docs land in REVIEW not MATCH. Remaining honest limit: top-1 falls to 72% at 15% perturbation among same-category siblings — 10 coarse features can't fully separate two structurally similar invoices. |
| Novelty (NEW) detection | **5/10** | Known-vs-novel balanced accuracy only 59.7% even with the better metric. Calibration makes the failure mode safe (novel → REVIEW, mean confidence 0.834 < 0.85) but not smart. Needs richer features (spatial-histogram of boxes) or tenant feedback data. |
| Reliability scoring | **4/10 (unvalidated)** | It is a weighted blend of template baseline + vendor confidence + drift penalty. Mathematically sane, but no ground truth says it predicts extraction errors. The feedback loop + `/v1/analytics/calibration` exist precisely to validate or kill it with customer data. Do not sell accuracy claims until a design partner's calibration report supports them. |
| Security/compliance posture | **9/10** | API-key scopes, tenant RLS, fail-closed Redis posture, append-only audit trail (DB trigger), login lockout, webhook secrets encrypted at rest, quota metering. This is the sellable compliance artifact. |
| Operability | **8/10** | 2 infrastructure services (Postgres, Redis — dead Temporal stack removed), one-click Render blueprint with migrations, SDK with 3 vendor adapters whose outputs are validated against the server's own schema, fingerprint byte-parity tested. |
| Test depth | **8/10** | 449 unit/service tests + 7 validation + integration suites in CI; the validation harness scores the algorithms rather than just exercising them. |
| Product-market proof | **2/10** | Zero external users. Everything above is necessary, none of it is sufficient. The only next milestone that matters: 2–3 design partners running real metadata, and their calibration reports. |

## What changed in this pass (before → after)

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
