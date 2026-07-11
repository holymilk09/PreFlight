# PreFlight

**Know when your OCR is drifting before your customers complain.**

PreFlight is a metadata-only governance layer for document extraction pipelines. We detect template drift and predict extraction reliability - without ever seeing your documents.

## The Problem

You're running document extraction with AWS Textract, Azure Doc Intelligence, or similar. Things work great... until they don't:

- A vendor changes their invoice format
- OCR accuracy silently degrades
- New document types slip through
- You find out from customer complaints

## The Solution

PreFlight monitors your extraction pipeline by analyzing **structural metadata only**:

```python
# After your normal Textract/Azure extraction:
result = preflight.evaluate(
    structural_features=extract_features(textract_response),
    extractor_metadata={"vendor": "aws", "model": "textract", ...}
)

if result.decision == "REVIEW":
    # Flag for human review - drift detected
    print(f"Drift score: {result.drift_score}")
```

## What We See vs. Don't See

| We Receive | We Never See |
|------------|--------------|
| Bounding box coordinates | Document images/PDFs |
| Element counts (tables, text blocks) | Extracted text or values |
| Layout complexity metrics | PII, PHI, or any content |
| Extractor confidence scores | Your documents |

**Privacy-first by design**: We can't leak what we never have.

## Quick Start

### 1. Install the SDK

```bash
pip install ./sdk    # preflight-sdk: adapters for Textract, Azure DI, Google DocAI, Upstage
```

### 2. Evaluate After Extraction (3 lines)

```python
from preflight_sdk import PreFlight
from preflight_sdk.adapters import textract  # or azure, google, upstage

# Your normal extraction
textract_response = textract_client.analyze_document(...)

# Reduce to structural metadata locally — content never leaves your environment
features = textract.extract_features(textract_response)

client = PreFlight(api_key="cp_your_key", base_url="https://your-deploy")
result = client.evaluate(
    features,
    vendor="aws", model="textract", version="2023-01", confidence=0.95,
    doc_hash="sha256_of_your_doc", correlation_id="invoice-123",
)

print(result["decision"])           # MATCH, REVIEW, NEW, or REJECT
print(result["drift_score"])        # 0.0 to 1.0
print(result["reliability_score"])  # 0.0 to 1.0
```

### 3. Close the loop (calibrates scores, proves ROI)

```python
client.submit_feedback(result["evaluation_id"], "corrected", field_error_count=2)
client.get_calibration()  # errors caught vs missed, accuracy per score band
```

### 4. Handle the Decision

| Decision | Meaning | Action |
|----------|---------|--------|
| `MATCH` | High confidence (>=85%) | Auto-process |
| `REVIEW` | Medium confidence (50-85%) | Human review |
| `NEW` | Unknown template (<50%) | Register or investigate |
| `REJECT` | Anomaly detected | Investigate |

## Self-Hosting

### Deploy to Railway (Recommended)

```bash
# One-click deploy
railway up

# Or manually:
railway init
railway add --template postgres
railway add --template redis
railway up
```

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/preflight)

### Deploy to Render

Connect your repo at [render.com/blueprints](https://render.com/blueprints) — Render
auto-detects `render.yaml` and stands up the full stack with no manual env setup:

- Provisions the managed **PostgreSQL** and **Redis** and wires their connection
  strings in (the `postgres://` scheme is normalized to `asyncpg` automatically).
- **Generates** the required `JWT_SECRET` and `API_KEY_SALT` secrets.
- Runs `alembic upgrade head` on every deploy via `preDeployCommand`, before the
  new image goes live.
- Boots fail-closed (`SECURITY_FAIL_CLOSED=true`) with API docs disabled.

`SENTRY_DSN` is the only optional value to set by hand in the dashboard.

### Local Development

```bash
git clone https://github.com/your-org/preflight.git
cd preflight

# Setup
cp .env.example .env
# Edit .env with secrets: openssl rand -hex 32

# Start infrastructure
docker compose -f docker-compose.simple.yml up -d

# Install and run
pip install -e ".[dev]"
alembic upgrade head
uvicorn src.api.main:app --reload
```

## Pricing

| Tier | Price | Evaluations |
|------|-------|-------------|
| Free | $0 | 1,000/month |
| Developer | $49/mo | 10,000/month |
| Team | $199/mo | 100,000/month |
| Enterprise | Custom | Unlimited + SLA |

## Examples

- [AWS Textract Integration](examples/python_textract.py)
- [Azure Document Intelligence](examples/python_azure.py)

## Documentation

- [Quickstart Guide](docs/QUICKSTART.md) - 5-minute integration
- [API Reference](docs/API.md) - Full endpoint docs
- [Architecture](docs/ARCHITECTURE.md) - System design
- [Business Model & GTM](docs/GTM.md) - What we sell, to whom, and how
- [Scorecard](docs/SCORECARD.md) - Measured algorithm quality, honest limits
- [How It Works](docs/HOW_IT_WORKS.md) - Plain-English explanation (the sales script)
- [Operator Runbook](docs/RUNBOOK.md) - Ship, monitor, support, and onboard a client

## Why Metadata-Only?

1. **Zero compliance burden**: We can't leak PII we don't have
2. **Universal compatibility**: Works with any extractor
3. **Fast evaluation**: No document transfer, just lightweight metadata
4. **Trust**: "We don't have your data" beats "trust our encryption"

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (public) |
| `/v1/evaluate` | POST | Evaluate document metadata |
| `/v1/templates` | GET | List templates |
| `/v1/templates` | POST | Register template |
| `/v1/templates/{id}` | GET/PATCH/DELETE | Template CRUD |

## Support

- Issues: [GitHub Issues](https://github.com/your-org/preflight/issues)
- Email: support@preflight.dev
- Slack: [MLOps Community](https://mlops.community) #preflight

## License

Proprietary - [Contact us](mailto:hello@preflight.dev) for licensing options.
