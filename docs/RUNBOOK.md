# Operator Runbook — shipping, watching, supporting a first client

*Everything you need to take one design partner from "yes" to "it's running and
I can see it working." Written for a solo operator, not an ops team.*

---

## Part 1 — How to ship it to your first client

You have two ways to give a client PreFlight. Start with the first.

### Option A (recommended for design partners): you host, they call your API

1. **Deploy once** (yours, shared or one instance per partner):
   `render.yaml` → connect the repo at render.com/blueprints. It provisions
   Postgres + Redis, generates secrets, runs migrations, and boots. ~15 minutes,
   no ops.
2. **Create the client a tenant + API key.** Each customer is a "tenant"
   (isolated data). Use the admin flow / `POST` an API key for them — they get a
   key like `cp_xxxx`. That key is their whole login to the API.
3. **Give them the SDK + key.** `pip install ./sdk`, their key, your URL. Their
   integration is the 3 lines in the SDK README.

You never touch their documents. They compute the metadata locally with the SDK
and send only that. This is the entire reason procurement is fast — lead with it.

### Option B: they self-host

Same Render blueprint, on their infra. Use this only if a security team insists.
More support burden for you; avoid for the first partner.

### The "first-run checklist" (do this WITH them on a call)

- [ ] They can reach `GET /health` on your deployment (returns `{"status":"ok"}`).
- [ ] Their API key works: `GET /v1/status` returns 200 with database + redis healthy.
- [ ] They register one template per document type (a clean sample) — `register_template`.
- [ ] They send 10 real documents' *metadata* through `evaluate` and see decisions.
- [ ] They can see those 10 in their dashboard (Evaluations page).

If all five pass, you've shipped. That's the bar.

---

## Part 2 — How to know it's working (once they're live)

You need two views: **"is the service up?"** and **"is it doing something useful?"**

### Is the service up? (health)

| Check | Endpoint / place | Healthy looks like |
|---|---|---|
| Public liveness | `GET /health` | `{"status": "ok"}` |
| Full status (auth) | `GET /v1/status` | database + redis both `healthy` |
| Admin dashboard | `admin/health` page | all green |

Put a free uptime monitor (e.g. a cron hitting `/health`) so you find out before
the client does. If `/health` is up but `/v1/status` shows redis unhealthy, the
service is in **fail-closed** mode — it's rejecting to be safe, not silently
wrong. That's by design; fix Redis and it recovers.

### Is it doing something useful? (value)

This is the important one — a client cares that it's *catching things*, not that
the server is up. Three places, in order of what a client asks for:

1. **`GET /v1/usage`** — "Are documents actually flowing?" Shows evaluations this
   month. If this is climbing, they're using it. If it's flat, integration broke.
2. **Evaluations + trends dashboard** — the decision mix (how many MATCH / REVIEW /
   NEW / REJECT) and drift/reliability over time. A healthy pipeline is mostly
   MATCH with occasional REVIEW spikes — and a spike *is the product working*.
3. **`GET /v1/analytics/calibration`** — THE proof number, once they send feedback.
   "Of the documents we flagged, how many were actually bad?" (review catch rate),
   and "errors caught vs. missed." This is your renewal slide. It only populates
   once they report outcomes via `submit_feedback` — so make feedback part of
   onboarding (Part 4).

**Your weekly ritual (5 min per client):** open `/v1/usage` (flowing?) and
`/v1/analytics/calibration` (catching?). If usage is up and catch rate is
reasonable, you're winning. Screenshot it and send it to them monthly — that's
retention.

---

## Part 3 — Troubleshooting & the questions they'll ask

Every problem leaves a trace in one of three places: the **API response** (an
error code + message), the **`/v1/status`** endpoint (dependencies), or the
**audit log** (who did what — it's append-only, so it's also their compliance
record).

### Common issues → what it means → fix

| Symptom | Almost always means | Fix |
|---|---|---|
| `401 Invalid API key` | Wrong/missing `X-API-Key` header | Re-issue key; check they used `cp_...` |
| `403 requires the 'X' scope` | Their key lacks a permission | Issue a key with the needed scope (evaluate/read/…) |
| `422` on evaluate | Payload missing a field (e.g. `pipeline_id`) | The SDK handles this — make sure they're on the SDK, not hand-rolling |
| `429 QUOTA_EXCEEDED` | They hit their plan's monthly limit | Raise their limit or upgrade tier |
| `503` on requests | Redis down, fail-closed posture | Check `/v1/status`; restart Redis |
| Everything returns `NEW` | No templates registered yet | Register a template per doc type first |
| Everything returns `REVIEW`/high drift | Real drift, OR baseline registered from a bad sample | Check the sample; re-register from a clean doc |

### FAQ a client will actually ask (and the honest answer)

- **"Do you see our documents / PII?"** No. Only structural metadata — counts and
  box positions. It's checkable in the API schema; invite them to audit it.
- **"How is this different from our extractor's own dashboard?"** Their extractor
  grades its own homework and only watches itself. PreFlight is neutral and works
  across every vendor they use.
- **"Does it catch *wrong values*?"** No — we catch layout/shape drift and route
  review volume. We prove our score predicts real errors via your feedback. (Don't
  overclaim here; it's the fastest way to lose trust.)
- **"What if it flags too much?"** The thresholds are tunable, and the reliability
  score self-calibrates from their feedback over time. Show them the calibration
  report to set expectations.
- **"What happens if PreFlight goes down?"** Their pipeline keeps running — we
  advise, we don't gate. Worst case they lose the smoke detector temporarily, not
  the kitchen.

### Your debugging order (when a client says "something's wrong")

1. `GET /health` and `GET /v1/status` — is it up?
2. `GET /v1/usage` — are their docs arriving at all?
3. Look at a specific evaluation (`GET /v1/evaluations/{id}`) — what did we decide
   and why (drift, confidence)?
4. Audit log — what actually happened, in order.

---

## Part 4 — Onboarding a client (the script you run)

Aim: from zero to "first flagged document" in one call. ~45 minutes.

**Before the call**
- Create their tenant + an API key (evaluate + read scopes).
- Ask them to pick **one** high-volume document type to start (not ten).
- Ask for one clean sample of that type already run through their extractor.

**On the call (share your screen)**
1. **Explain it in 30 seconds** using `HOW_IT_WORKS.md`. Don't go deeper unless asked.
2. **Install:** `pip install ./sdk`, set their key + your URL.
3. **Register the template** from their clean sample (`register_template`). Now
   PreFlight knows what "normal" looks like for that type.
4. **Send a batch** of recent documents' metadata (`evaluate`). Watch decisions
   appear in their Evaluations dashboard live. This is the "aha."
5. **Show a flag:** if any came back REVIEW/NEW, open it — "here's one PreFlight
   thinks you should look at, and why." If none did, take a document, change it a
   bit, and watch it flag. Seeing it catch something is what closes them.
6. **Set up the feedback loop:** show `submit_feedback`. Make it a habit — after
   their humans review a flagged doc, they report correct/corrected/rejected. This
   is what powers the calibration/ROI number and their renewal case. **No feedback =
   no proof number**, so this step is non-negotiable.

**After the call**
- Send them: the `HOW_IT_WORKS.md` one-pager, their key, and the 3-line snippet.
- Book a 2-week check-in to review their first `/v1/analytics/calibration`.

**The retroactive demo (your strongest onboarding move):** if they have archived
extractor outputs, ask them to run 60–90 days of that *metadata* through
`evaluate` (documents never move). Then show the drift chart catching an incident
they already remember. Proof beats promises.

---

## The one metric that means you're succeeding

Not uptime. Not test coverage. **Feedback coverage** on `/v1/analytics/calibration`
climbing, with a review catch rate a client finds credible. That single number —
on their data — is the difference between "a demo" and "a business."
