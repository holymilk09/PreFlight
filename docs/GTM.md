# PreFlight — Business Model & Go-To-Market

*Honest working document. Last updated: July 2026.*

---

## 1. What we actually sell (one sentence)

**A vendor-neutral scorekeeper for document extraction pipelines: it tells you which
extracted documents to trust, which to send to a human, and when your extraction is
silently degrading — without ever seeing a document.**

Not "a control plane" (we don't control anything — the client's pipeline acts on our
decision). The accurate category is **extraction observability + review triage**.
Sell that; it's believable and testable.

## 2. The real problem (and who has it)

Enterprises running document extraction at scale (insurance claims, invoices, loan
files, medical records) have three chronic pains:

1. **Silent degradation.** A supplier redesigns their invoice, or the extraction
   vendor ships a model update, and field accuracy quietly drops. Nobody notices
   until reconciliation breaks or an auditor does. There is no smoke detector.
2. **Review triage is the money lever.** Human review costs $0.50–$5 per document;
   straight-through processing (STP) rate is *the* KPI of every document ops team.
   Route too much to humans → cost explodes. Route too little → errors reach the
   ERP. Vendor confidence scores are the only routing signal today, and they are
   neither calibrated nor comparable across vendors.
3. **Nobody neutral is keeping score.** The extraction vendor grades its own
   homework. Multi-vendor shops (very common after M&A) have no apples-to-apples
   quality comparison.

**ICP (first 10 customers):** Director/VP of Operations or Head of Intelligent
Document Processing at (a) P&C / health insurers, (b) BPOs processing documents for
clients, (c) lenders/mortgage servicers, (d) AP-automation-heavy enterprises.
Mid-market to enterprise, 100k+ documents/month, regulated, already burned by a
silent drift incident at least once. The economic buyer owns the review-labor
budget; the technical buyer is the platform/data engineering lead.

## 3. Our wedge (why us and not a feature of the IDP vendor)

- **Neutrality.** The extractor cannot credibly monitor itself. A third-party
  scorekeeper is the same structural role as Datadog vs AWS, or auditors vs CFOs.
- **Privacy = procurement speed.** We receive layout metadata only — no document
  images, no field values, no PII/PHI. That means: no BAA, no DPA on content, light
  security review, no data-residency fight. In regulated industries this converts
  a 9-month procurement into weeks. It is our single biggest sales asset — lead
  with it.
- **Cross-vendor benchmarking (the compounding asset).** Every evaluation teaches us
  how Textract/Azure/Google/Nemotron behave per document class. Anonymized,
  aggregated: "Azure DI is 11% less reliable than Textract on multi-page tabular
  invoices." No single tenant can build this; it gets better with every customer.
  This is the long-term moat — the algorithms are not (cosine similarity and
  z-scores are replicable in a week; the data and the compliance artifact are not).

## 4. Honest limits (what we don't claim)

- We detect **layout/structure drift**, not content errors. Two identical-looking
  documents can be extracted wrong in ways we can't see. The outcome-feedback loop
  (`POST /v1/evaluations/{id}/feedback`) is how we compensate: customers report
  correct/corrected/rejected, and `/v1/analytics/calibration` proves (or disproves)
  that our scores predict reality. **Never sell an accuracy claim we haven't
  calibrated on the customer's own feedback data.**
- The client's pipeline enforces decisions; we advise. Positioning: observability
  and decisioning, not enforcement.
- Integration requires the client to compute structural features from extractor
  output. Until the SDK exists (see §8), this is the #1 adoption tax.

## 5. What the client sees vs what we see

| | **Client sees** | **We (PreFlight) see** |
|---|---|---|
| **Surface** | Dashboard (Next.js app): evaluations, templates, drift/reliability trends, alerts, usage vs plan; REST API + webhooks | Admin console: tenants, health, errors, audit |
| **Data** | Only their own tenant's data (PostgreSQL RLS-enforced) | Cross-tenant **metadata** aggregates: per-vendor reliability curves, drift base rates, calibration quality |
| **Documents** | Their own documents — which never leave their environment | Nothing. Layout fingerprints and counts only. This is checkable in our API schema — let prospects audit it. |
| **Scores** | Decision (MATCH/REVIEW/NEW/REJECT), drift, reliability, correction rules, calibration report (their outcomes vs our scores) | Score-vs-outcome calibration across the fleet → model improvements every tenant benefits from |
| **Money** | Monthly plan + usage meter (`/v1/usage`) | Margin: our COGS is a Postgres + Redis + small API tier (~$50–500/mo serves thousands of tenants at MVP scale); gross margin >90% |
| **Compliance** | Append-only audit trail of every evaluation and decision — exportable evidence for auditors ("we had documented controls on automated extraction") | The same trail as a product: the compliance artifact is a thing customers pay for by itself |

## 6. How we make money

**Pricing (already wired into the product — `/v1/usage` meters it):**

| Tier | Price | Evaluations/mo | Who |
|------|-------|----------------|-----|
| Free | $0 | 1,000 | Developer trying it on one pipeline |
| Developer | $49/mo | 10,000 | Small team, one document type |
| Team | $199/mo | 100,000 | Ops team, several document types |
| Enterprise | Custom ($2k–$10k+/mo) | Unlimited + SLA, SSO, custom limits | The real revenue |

**Why enterprises will pay 4–5 figures monthly:** price against review labor, not
against software. A customer doing 500k docs/month at 20% review rate spends
~$100k–500k/month on humans. If calibrated scores let them safely cut the review
rate by 5 points, that's $25k–125k/month saved — a $5k/month fee is a rounding
error. The calibration endpoint exists precisely to compute this number *from the
customer's own data* and put it on the renewal slide.

**Secondary revenue (later):** anonymized industry benchmark reports
("State of Document Extraction Quality"), and per-vendor routing recommendations
(Thompson sampling — already on the roadmap).

**Unit economics:** evaluations are one indexed SQL round-trip plus arithmetic —
sub-cent COGS per thousand. The business is effectively all gross margin; spend
goes to distribution, not serving.

## 7. Sales motion

1. **Design partners first (now).** 3–5 partners from the ICP list, free enterprise
   tier for 6 months in exchange for feedback data and a case study. The goal is
   one number per partner: *"PreFlight caught N bad extractions before they hit
   our ERP / cut review volume by X% at the same error rate."* The calibration
   endpoint produces this automatically once they send feedback.
2. **Land** with the free/developer tier on one pipeline (self-serve: Render
   deploy or our hosted app + API key + SDK). Time-to-first-drift-alert is the
   activation metric; it must be under a day.
3. **Expand** by document type and department; **convert to enterprise** on the
   compliance artifact (audit trail, SSO, SLA) and quota needs. Usage metering
   makes expansion visible to us and to the champion.
4. **The demo:** replay a real historical incident. Ask the prospect for 90 days of
   extraction *metadata* (they can generate it with the SDK against archived
   outputs — documents never move). Show the drift chart catching the incident
   they already know about. Retroactive proof beats any slide.

## 8. Distribution

- **SDK on PyPI (`pip install preflight-sdk`) — the single highest-leverage build
  item remaining.** Vendor adapters (Textract, Azure DI, Google DocAI, Nemotron
  Parse) that turn raw extractor output into our feature vector in 3 lines. It
  kills the adoption tax AND standardizes feature computation, which the
  cross-tenant benchmark depends on. (The `examples/` scripts are the seed.)
- **Cloud marketplaces** (AWS, Azure): where the ICP already has budget; marketplace
  billing burns their committed cloud spend and skips procurement.
- **IDP consultants & SIs** as a channel: the people who install Textract/Azure DI
  pipelines get a monitoring line-item to resell (20–30% margin).
- **Content that only we can write:** vendor-neutral extraction quality benchmarks
  from aggregated metadata. Each report is lead gen the IDP vendors structurally
  cannot copy (they can't be neutral).
- **Open-core option (decide later):** self-hostable core (it already deploys via
  one Render blueprint / docker-compose) with hosted + benchmark + SSO as paid.
  Good for BPO/regulated buyers who insist on self-hosting anyway.

## 9. What must be true / 90-day priorities

1. ~~Outcome feedback loop~~ — **shipped** (`/v1/evaluations/{id}/feedback` +
   `/v1/analytics/calibration`). Without it, scores were unfalsifiable.
2. **Python SDK with vendor adapters** — kills the integration tax. (~1–2 weeks.)
3. **2–3 design partners** running real metadata through it. Everything else is
   downstream of this; it validates or kills the thesis cheaply.
4. **Baseline learning:** drift is currently measured against a static
   registration-time baseline; add rolling/EWMA baselines or a re-baseline
   endpoint, or long-lived templates will generate false alarms. (~1 week.)
5. **Wire the dashboard to the calibration + usage endpoints** so the buyer sees
   the ROI number, not JSON.

## 9a. Competitive note — bundled monitoring (Upstage Studio, July 2026)

Upstage launched **Studio**, an agentic document-processing platform (parse →
classify → extract → human review) with a bundled monitoring dashboard. This is
the "IDP platforms bundle monitoring" risk from the register, now concrete.
Why it does not wreck the wedge:

- **It's Layer 2 (extraction); we're Layer 3 (governance).** Studio is one more
  extractor — a `vendor=upstage` value, now a first-class SDK adapter and a
  known provider in the cross-vendor analytics. Every new extractor widens the
  population that needs a neutral scorekeeper.
- **Its dashboard grades its own homework.** It monitors only Upstage's own
  stack — no cross-vendor comparison, no drift-vs-baseline, no calibration of
  scores against reported outcomes. That single-vendor blind spot IS the
  neutrality pitch.
- **It's a rip-and-replace migration**, not an overlay on the Textract/Azure/
  multi-vendor pipelines our ICP already runs.

**Positioning line to use:** *"Your extractor's built-in dashboard grades its
own homework. PreFlight is the neutral scorekeeper across all of them —
including Upstage."*

**The real signal:** platforms shipping "good-enough" monitoring is the moat
eroding on schedule. It doesn't kill us today, but it shortens the window to
land design partners and start accumulating the cross-vendor calibration data
no bundled dashboard can replicate. Move on partners this quarter.

Supporting evidence (current research, not marketing): LLM extractors fail
*quieter* than OCR — confident hallucination instead of visible garbage — and
their confidence scores are badly calibrated (RLHF models overshoot empirical
accuracy by ~15 points; 12-18% hallucination on enterprise numeric fields).
That raises, not lowers, the value of an independent calibration loop.

## 10. Risks (clear-eyed)

- **Thin-wedge risk:** a competent team can rebuild the scoring in weeks. Defense:
  move fast on benchmark data + SDK distribution + the compliance artifact; the
  moat is accumulated data and trust, not math.
- **IDP platforms bundle "monitoring."** Defense: neutrality story + multi-vendor
  shops (a single-vendor monitor can't score the vendor's competitor).
- **Signal quality:** if layout drift turns out to poorly predict extraction errors
  on partner data, the product thesis fails. The calibration endpoint is our own
  kill-criterion — if `review_catch_rate` isn't meaningfully above the base error
  rate after 60 days of partner feedback, revisit the feature set (e.g., accept
  optional field-level *confidence* metadata, still content-free).
- **Integration friction:** unsolved until the SDK ships. Treat SDK as product,
  not docs.
