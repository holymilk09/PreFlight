# How PreFlight Works — in plain English

*If you can't explain it simply, you can't sell it. This is the script.*

## The one-liner

> **PreFlight is a smoke detector for document AI.** When a company uses AI to
> read invoices, claims, or forms, that AI quietly gets worse over time — a
> supplier changes their layout, a vendor updates their model — and nobody
> notices until money or an auditor finds the mistake. PreFlight watches for
> that and raises its hand *before* the bad data lands in your systems.

That's the whole pitch. Everything below is detail you pull out only if asked.

## The analogy that makes it click

A smoke detector doesn't put out fires, cook your food, or inspect your wiring.
It does **one boring, valuable thing**: it notices when something's changed for
the worse and makes noise so a human checks. You'd never run a building without
one — but you'd also never confuse it with the kitchen.

- **The kitchen** = the AI that reads documents (AWS Textract, Azure, Google,
  Upstage). That's where the cooking happens.
- **PreFlight** = the smoke detector. We don't read your documents. We watch the
  *shape* of what comes out and notice when it drifts.

## What we actually look at (and why it's safe)

Every time an AI reads a document, it produces a "shape": how many tables, where
the text sits on the page, how dense it is, how many columns. Think of it as the
**skeleton** of the page, not the words on it.

- We receive: the skeleton (counts, box positions) — numbers, basically.
- We **never** receive: the document image, the text, names, dollar amounts, any
  private information.

That's the killer feature for regulated buyers: *"We can't leak your data because
we never have it."* No legal review of what we store. No compliance nightmare.

## What we do with the skeleton

Three simple jobs:

1. **"Have I seen this shape before?"** (template matching) — On day one you show
   us a clean example of each document type. After that, every new document is
   compared to those. A close match = normal. A shape we've never seen = flag it.
2. **"Is this shape changing?"** (drift detection) — We keep a running picture of
   "normal" for each document type. When new documents start looking different —
   a supplier redesigned their invoice — we measure how far off they are and, past
   a threshold, raise the alarm.
3. **"How much should you trust this one?"** (reliability score) — A single 0-to-1
   number so your pipeline can decide: auto-process the confident ones, send the
   shaky ones to a human.

## What the customer does with our answer

For every document, we return one of four verdicts:

| We say | Plain meaning | What they do |
|--------|---------------|--------------|
| **MATCH** | "Looks normal, high confidence" | Auto-process it |
| **REVIEW** | "Something's off — a person should look" | Route to human review |
| **NEW** | "Never seen this shape" | Register it or investigate |
| **REJECT** | "This extraction is broken" | Don't use it |

**We advise; their pipeline decides.** We're the smoke detector, not the sprinkler.

## Why they'd pay for it

Human review of documents costs real money ($0.50–$5 each) and is the biggest
cost dial in any document-processing team. Trust our score and they safely
auto-process more (cheaper) without letting errors through (safer). We turn
"review everything to be safe" into "review only the ones that actually look
wrong."

## The honest limit (say it out loud)

We see the document's *shape*, not its *content*. Two invoices that look
identical could still be read wrong in a way we can't see. So we don't claim "we
catch every extraction error." We claim: **"we catch layout drift and mis-routed
review volume,"** and we prove it on the customer's own data via the feedback
loop (they tell us which ones turned out right; we show them how well our score
predicted it).

## The 30-second version to say out loud

> "You use AI to read documents. That AI silently degrades — layouts change,
> models update — and you find out too late. PreFlight is a privacy-safe smoke
> detector that watches the shape of your extractions, flags the ones that drift,
> and tells you which to trust. We never see your actual documents. It means you
> auto-process more with less risk, and you get an audit trail proving you had
> controls on your AI."

## See it for yourself

Run `python scripts/demo_incident.py`. It simulates a quarter of invoices where
one supplier redesigns their form, and shows PreFlight catching it the day it
happens — using the exact scoring code the real product runs.
