# PreFlight Quickstart

Get drift detection for your OCR pipeline in 5 minutes.

## What is PreFlight?

PreFlight is a **metadata-only** governance layer for document extraction pipelines. We detect when your document templates drift and predict extraction reliability - without ever seeing your documents.

**You send us:**
- Layout fingerprints (bounding box coordinates)
- Structural features (element counts, text density)
- Extractor metadata (vendor, model, confidence)

**We never see:**
- Document images or PDFs
- Extracted text or field values
- Any PII or sensitive content

## Quick Start

### 1. Get Your API Key

```bash
# Sign up at https://preflight.dev (coming soon)
# Or self-host and create a key via admin API:
curl -X POST http://localhost:8000/v1/admin/tenants \
  -H "X-API-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Company"}'

curl -X POST http://localhost:8000/v1/admin/api-keys \
  -H "X-API-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "<tenant-id>", "name": "dev-key"}'
```

### 2. Extract Document with Your OCR

Use your existing extraction pipeline (AWS Textract, Azure Doc Intelligence, etc.):

```python
import boto3

textract = boto3.client('textract')

# Your normal extraction
response = textract.analyze_document(
    Document={'S3Object': {'Bucket': 'my-bucket', 'Name': 'invoice.pdf'}},
    FeatureTypes=['TABLES', 'FORMS']
)
```

### 3. Send Metadata to PreFlight

```python
import hashlib
import httpx

PREFLIGHT_URL = "http://localhost:8000"  # Or your deployed URL
API_KEY = "cp_your_api_key_here"

def extract_structural_features(textract_response):
    """Convert Textract response to PreFlight structural features."""
    blocks = textract_response.get('Blocks', [])

    # Count element types
    tables = [b for b in blocks if b['BlockType'] == 'TABLE']
    text_blocks = [b for b in blocks if b['BlockType'] == 'LINE']

    # Extract bounding boxes
    bounding_boxes = []
    for i, block in enumerate(blocks):
        if 'Geometry' in block:
            bbox = block['Geometry']['BoundingBox']
            bounding_boxes.append({
                "x": bbox['Left'],
                "y": bbox['Top'],
                "width": bbox['Width'],
                "height": bbox['Height'],
                "element_type": block['BlockType'].lower(),
                "confidence": block.get('Confidence', 0.9) / 100,
                "reading_order": i
            })

    return {
        "element_count": len(blocks),
        "table_count": len(tables),
        "text_block_count": len(text_blocks),
        "image_count": 0,
        "page_count": 1,
        "text_density": len(text_blocks) / max(1, len(blocks)),
        "layout_complexity": min(1.0, len(blocks) / 100),
        "column_count": 1,
        "has_header": True,
        "has_footer": True,
        "bounding_boxes": bounding_boxes[:100]  # Limit to 100
    }

def compute_fingerprint(features):
    """Hash structural features for quick lookup."""
    import json
    canonical = json.dumps(features, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()

# Extract features from Textract response
features = extract_structural_features(response)
fingerprint = compute_fingerprint(features)

# Send to PreFlight
result = httpx.post(
    f"{PREFLIGHT_URL}/v1/evaluate",
    headers={"X-API-Key": API_KEY},
    json={
        "layout_fingerprint": fingerprint,
        "structural_features": features,
        "extractor_metadata": {
            "vendor": "aws",
            "model": "textract",
            "version": "2023-01",
            "confidence": 0.95,
            "latency_ms": 1200,
            "cost_usd": 0.015
        },
        "client_doc_hash": hashlib.sha256(b"your-doc-bytes").hexdigest(),
        "client_correlation_id": "invoice-123",
        "pipeline_id": "invoice-processing-v1"
    }
).json()

print(f"Decision: {result['decision']}")
print(f"Drift Score: {result['drift_score']}")
print(f"Reliability Score: {result['reliability_score']}")
```

### 4. Handle the Response

```python
if result['decision'] == 'MATCH':
    # High confidence - proceed with extraction
    print("Template matched, extraction reliable")

elif result['decision'] == 'REVIEW':
    # Medium confidence - flag for human review
    print(f"Needs review: drift={result['drift_score']:.2f}")

elif result['decision'] == 'NEW':
    # New template detected - register it
    print("New document type detected")

elif result['decision'] == 'REJECT':
    # Anomaly detected - investigate
    print("Potential fraud or severe drift")

# Apply correction rules if any
for rule in result.get('correction_rules', []):
    print(f"Apply rule: {rule['rule']} to field {rule['field']}")
```

## Register a Template

When you encounter a new document type, register it as a template:

```python
template = httpx.post(
    f"{PREFLIGHT_URL}/v1/templates",
    headers={"X-API-Key": API_KEY},
    json={
        "template_id": "INV-ACME-001",
        "version": "1.0",
        "structural_features": features,
        "baseline_reliability": 0.92,
        "correction_rules": [
            {
                "field": "date",
                "rule": "normalize_date",
                "parameters": {"format": "YYYY-MM-DD"}
            }
        ]
    }
).json()

print(f"Registered template: {template['id']}")
```

## Understanding Results

### Decision Types

| Decision | Meaning | Action |
|----------|---------|--------|
| `MATCH` | Matches known template (confidence >= 0.85) | Auto-process |
| `REVIEW` | Partial match (0.50-0.85) | Human review |
| `NEW` | No matching template (< 0.50) | Register new template |
| `REJECT` | Anomaly detected | Investigate |

### Drift Score

| Score | Status | Meaning |
|-------|--------|---------|
| < 0.15 | Stable | Document matches template closely |
| 0.15-0.30 | Watch | Minor variations, monitor |
| 0.30-0.50 | Review | Significant drift, review recommended |
| > 0.50 | Critical | Major changes, likely template update |

### Reliability Score

| Score | Meaning |
|-------|---------|
| >= 0.80 | High confidence extraction |
| 0.60-0.80 | Medium confidence, some fields may need verification |
| < 0.60 | Low confidence, manual review recommended |

## Self-Hosting

### Deploy to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up

# Add PostgreSQL and Redis
railway add --name preflight-db --template postgres
railway add --name preflight-redis --template redis

# Set environment variables
railway variables set API_SECRET_KEY=$(openssl rand -hex 32)
railway variables set ADMIN_API_KEY=$(openssl rand -hex 32)
```

### Deploy to Render

```bash
# Push to GitHub, then:
# 1. Go to render.com/blueprints
# 2. Connect your repo
# 3. Render will auto-detect render.yaml
```

### Local Development

```bash
# Clone and setup
git clone https://github.com/your-org/preflight.git
cd preflight

# Copy environment template
cp .env.example .env
# Edit .env with:
# POSTGRES_PASSWORD=your-password
# REDIS_PASSWORD=your-password
# API_SECRET_KEY=$(openssl rand -hex 32)

# Start infrastructure
docker compose -f docker-compose.simple.yml up -d

# Install dependencies
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start API
uvicorn src.api.main:app --reload
```

## Next Steps

- [API Reference](API.md) - Full endpoint documentation
- [Architecture](ARCHITECTURE.md) - System design details
- [Examples](../examples/) - More integration examples

## Support

- GitHub Issues: [github.com/your-org/preflight/issues](https://github.com/your-org/preflight/issues)
- Email: support@preflight.dev
