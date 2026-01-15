# PreFlight API Reference

Complete API documentation for integrating PreFlight into your document extraction pipeline.

---

## Quick Start

```bash
# 1. Get your API key from the dashboard
# 2. Test the connection
curl -X GET https://api.preflight.dev/health

# 3. Make your first evaluation
curl -X POST https://api.preflight.dev/v1/evaluate \
  -H "X-API-Key: cp_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "layout_fingerprint": "a1b2c3d4e5f6...",
    "structural_features": {
      "element_count": 45,
      "table_count": 2,
      "text_block_count": 30,
      "image_count": 3,
      "page_count": 1,
      "text_density": 0.45,
      "layout_complexity": 0.32,
      "column_count": 2,
      "has_header": true,
      "has_footer": true,
      "bounding_boxes": []
    },
    "extractor_metadata": {
      "vendor": "aws_textract",
      "model": "analyze-document",
      "version": "1.0",
      "confidence": 0.95,
      "latency_ms": 450
    },
    "client_doc_hash": "xyz789...",
    "client_correlation_id": "invoice-12345",
    "pipeline_id": "invoice-processing"
  }'
```

---

## Base URL

```
Production: https://api.preflight.dev/v1
Local Dev:  http://localhost:8000/v1
```

---

## Authentication

All endpoints (except `/health` and `/ready`) require API key authentication.

**Header:**
```
X-API-Key: cp_<32 hex characters>
```

**Example:**
```bash
curl -H "X-API-Key: cp_a1b2c3d4e5f67890a1b2c3d4e5f67890" \
     https://api.preflight.dev/v1/status
```

**Key Format:** `cp_` prefix + 32 hex characters

---

## Endpoints Overview

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Liveness probe |
| `/ready` | GET | No | Readiness probe (checks DB + Redis) |
| `/v1/status` | GET | Yes | Detailed service status |
| `/v1/evaluate` | POST | Yes | **Core endpoint** - evaluate extraction |
| `/v1/evaluations` | GET | Yes | List evaluation history |
| `/v1/evaluations/{id}` | GET | Yes | Get single evaluation |
| `/v1/templates` | GET | Yes | List templates |
| `/v1/templates` | POST | Yes | Create template |
| `/v1/templates/{id}` | GET | Yes | Get template details |
| `/v1/templates/{id}` | PUT | Yes | Update template |
| `/v1/templates/{id}` | DELETE | Yes | Deprecate template |

---

## Core Endpoint: POST /v1/evaluate

This is the main endpoint you'll call for every document extraction.

### Request

```json
{
  "layout_fingerprint": "string (64 hex chars, SHA-256)",
  "structural_features": {
    "element_count": 45,
    "table_count": 2,
    "text_block_count": 30,
    "image_count": 3,
    "page_count": 1,
    "text_density": 0.45,
    "layout_complexity": 0.32,
    "column_count": 2,
    "has_header": true,
    "has_footer": true,
    "bounding_boxes": [
      {
        "x": 0.1,
        "y": 0.05,
        "width": 0.3,
        "height": 0.08,
        "element_type": "text",
        "confidence": 0.98,
        "reading_order": 0
      }
    ]
  },
  "extractor_metadata": {
    "vendor": "aws_textract",
    "model": "analyze-document",
    "version": "1.0",
    "confidence": 0.95,
    "latency_ms": 450,
    "cost_usd": 0.0015
  },
  "client_doc_hash": "string (64 hex chars)",
  "client_correlation_id": "your-tracking-id",
  "pipeline_id": "your-pipeline-name"
}
```

### Response

```json
{
  "decision": "MATCH",
  "template_version_id": "INV-ACME-001-v1.0",
  "drift_score": 0.03,
  "reliability_score": 0.94,
  "correction_rules": [
    {
      "field": "total",
      "rule": "sum_line_items",
      "parameters": null
    }
  ],
  "replay_hash": "abc123...",
  "evaluation_id": "550e8400-e29b-41d4-a716-446655440000",
  "alerts": []
}
```

### Decision Values

| Decision | Meaning | Recommended Action |
|----------|---------|-------------------|
| `MATCH` | High confidence match to known template | Auto-process |
| `REVIEW` | Medium confidence, needs verification | Send to review queue |
| `NEW` | Unknown template structure | Create new template |
| `REJECT` | Anomaly detected | Manual investigation |

### Python Example

```python
import requests
import hashlib
import json

API_KEY = "cp_your_api_key_here"
BASE_URL = "https://api.preflight.dev/v1"

def evaluate_extraction(extraction_result, document_bytes):
    """
    Call PreFlight after your OCR extraction.

    Args:
        extraction_result: Output from your extractor (Textract, etc.)
        document_bytes: Raw document for hashing (we never see this)
    """
    # Generate fingerprint from structural features
    features = extract_structural_features(extraction_result)
    fingerprint = hashlib.sha256(
        json.dumps(features, sort_keys=True).encode()
    ).hexdigest()

    # Hash your document (stays on your side)
    doc_hash = hashlib.sha256(document_bytes).hexdigest()

    response = requests.post(
        f"{BASE_URL}/evaluate",
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "layout_fingerprint": fingerprint,
            "structural_features": features,
            "extractor_metadata": {
                "vendor": "aws_textract",
                "model": "analyze-document",
                "version": "1.0",
                "confidence": extraction_result.get("confidence", 0.9),
                "latency_ms": 450
            },
            "client_doc_hash": doc_hash,
            "client_correlation_id": "invoice-12345",
            "pipeline_id": "invoice-processing"
        }
    )

    return response.json()

def extract_structural_features(extraction_result):
    """Convert extractor output to PreFlight structural features."""
    blocks = extraction_result.get("Blocks", [])

    tables = [b for b in blocks if b.get("BlockType") == "TABLE"]
    text_blocks = [b for b in blocks if b.get("BlockType") == "LINE"]

    return {
        "element_count": len(blocks),
        "table_count": len(tables),
        "text_block_count": len(text_blocks),
        "image_count": 0,  # From your extractor
        "page_count": 1,
        "text_density": 0.45,  # Calculate from layout
        "layout_complexity": 0.32,
        "column_count": 2,
        "has_header": True,
        "has_footer": True,
        "bounding_boxes": [
            {
                "x": b["Geometry"]["BoundingBox"]["Left"],
                "y": b["Geometry"]["BoundingBox"]["Top"],
                "width": b["Geometry"]["BoundingBox"]["Width"],
                "height": b["Geometry"]["BoundingBox"]["Height"],
                "element_type": b["BlockType"].lower(),
                "confidence": b.get("Confidence", 0.9) / 100,
                "reading_order": i
            }
            for i, b in enumerate(blocks[:100])  # Limit to 100 boxes
        ]
    }

# Usage
result = evaluate_extraction(textract_response, pdf_bytes)

if result["decision"] == "MATCH":
    # High confidence - auto-process
    process_document(extraction_result)
elif result["decision"] == "REVIEW":
    # Medium confidence - human review
    send_to_review_queue(extraction_result, result)
else:
    # NEW or REJECT - special handling
    handle_anomaly(extraction_result, result)
```

### Node.js Example

```javascript
const crypto = require('crypto');

const API_KEY = 'cp_your_api_key_here';
const BASE_URL = 'https://api.preflight.dev/v1';

async function evaluateExtraction(extractionResult, documentBuffer) {
  // Generate fingerprint
  const features = extractStructuralFeatures(extractionResult);
  const fingerprint = crypto
    .createHash('sha256')
    .update(JSON.stringify(features))
    .digest('hex');

  // Hash document (stays on your side)
  const docHash = crypto
    .createHash('sha256')
    .update(documentBuffer)
    .digest('hex');

  const response = await fetch(`${BASE_URL}/evaluate`, {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      layout_fingerprint: fingerprint,
      structural_features: features,
      extractor_metadata: {
        vendor: 'aws_textract',
        model: 'analyze-document',
        version: '1.0',
        confidence: extractionResult.confidence || 0.9,
        latency_ms: 450
      },
      client_doc_hash: docHash,
      client_correlation_id: 'invoice-12345',
      pipeline_id: 'invoice-processing'
    })
  });

  return response.json();
}

function extractStructuralFeatures(result) {
  const blocks = result.Blocks || [];
  const tables = blocks.filter(b => b.BlockType === 'TABLE');
  const textBlocks = blocks.filter(b => b.BlockType === 'LINE');

  return {
    element_count: blocks.length,
    table_count: tables.length,
    text_block_count: textBlocks.length,
    image_count: 0,
    page_count: 1,
    text_density: 0.45,
    layout_complexity: 0.32,
    column_count: 2,
    has_header: true,
    has_footer: true,
    bounding_boxes: blocks.slice(0, 100).map((b, i) => ({
      x: b.Geometry?.BoundingBox?.Left || 0,
      y: b.Geometry?.BoundingBox?.Top || 0,
      width: b.Geometry?.BoundingBox?.Width || 0,
      height: b.Geometry?.BoundingBox?.Height || 0,
      element_type: b.BlockType?.toLowerCase() || 'unknown',
      confidence: (b.Confidence || 90) / 100,
      reading_order: i
    }))
  };
}

// Usage
const result = await evaluateExtraction(textractResponse, pdfBuffer);

switch (result.decision) {
  case 'MATCH':
    await processDocument(extractionResult);
    break;
  case 'REVIEW':
    await sendToReviewQueue(extractionResult, result);
    break;
  default:
    await handleAnomaly(extractionResult, result);
}
```

---

## List Evaluations: GET /v1/evaluations

Query your evaluation history.

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `decision` | string | Filter by decision (MATCH, REVIEW, NEW, REJECT) |
| `correlation_id` | string | Filter by your correlation ID |
| `template_id` | uuid | Filter by template |
| `min_reliability` | float | Minimum reliability score |
| `max_drift` | float | Maximum drift score |
| `limit` | int | Results per page (default 100, max 1000) |
| `offset` | int | Pagination offset |

### Example

```bash
# Get recent REVIEW decisions
curl -X GET "https://api.preflight.dev/v1/evaluations?decision=REVIEW&limit=50" \
  -H "X-API-Key: cp_your_api_key_here"
```

### Response

```json
{
  "evaluations": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "correlation_id": "invoice-12345",
      "document_hash": "abc123...",
      "template_id": "550e8400-...",
      "template_version_id": "INV-ACME-001-v1.0",
      "decision": "REVIEW",
      "match_confidence": 0.72,
      "drift_score": 0.18,
      "reliability_score": 0.78,
      "correction_rules": [],
      "extractor_vendor": "aws_textract",
      "extractor_model": "analyze-document",
      "processing_time_ms": 11,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0,
  "has_more": true
}
```

---

## Templates

### List Templates: GET /v1/templates

```bash
curl -X GET "https://api.preflight.dev/v1/templates?status=active" \
  -H "X-API-Key: cp_your_api_key_here"
```

### Create Template: POST /v1/templates

```bash
curl -X POST https://api.preflight.dev/v1/templates \
  -H "X-API-Key: cp_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "INV-NEWCLIENT-001",
    "version": "1.0",
    "structural_features": {
      "element_count": 45,
      "table_count": 2,
      "text_block_count": 30,
      "image_count": 3,
      "page_count": 1,
      "text_density": 0.45,
      "layout_complexity": 0.32,
      "column_count": 2,
      "has_header": true,
      "has_footer": true,
      "bounding_boxes": []
    },
    "baseline_reliability": 0.85,
    "correction_rules": []
  }'
```

---

## Health Endpoints

### Liveness: GET /health

```bash
curl https://api.preflight.dev/health
# {"status": "healthy"}
```

### Readiness: GET /ready

```bash
curl https://api.preflight.dev/ready
# {"status": "ready", "services": {"database": {"healthy": true}, "redis": {"healthy": true}}}
```

### Detailed Status: GET /v1/status (requires auth)

```bash
curl -H "X-API-Key: cp_..." https://api.preflight.dev/v1/status
```

---

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message here"
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (success, no body) |
| 400 | Bad Request - validation error |
| 401 | Unauthorized - invalid/missing API key |
| 404 | Not Found |
| 409 | Conflict - resource already exists |
| 413 | Payload Too Large (>1MB) |
| 429 | Rate Limited |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

### Rate Limiting

- **Authenticated requests:** 1000/minute per API key
- **Unauthenticated requests:** 10/minute per IP

Rate limit headers are included in all responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 60
```

When rate limited (429), also includes:
```
Retry-After: 45
```

---

## Best Practices

### 1. Handle All Decision Types

```python
if result["decision"] == "MATCH":
    # ~70-85% of documents - auto-process
    process_document(data)
elif result["decision"] == "REVIEW":
    # ~10-20% - send to human review
    review_queue.add(data, result)
elif result["decision"] == "NEW":
    # ~5% - new template detected
    create_template_request(data, result)
else:  # REJECT
    # ~1% - anomaly
    alert_team(data, result)
```

### 2. Implement Fail-Open

```python
try:
    result = preflight.evaluate(extraction)
except (ConnectionError, Timeout):
    # PreFlight unreachable - process with logging
    logger.warning("PreFlight unavailable, processing without validation")
    result = {"decision": "UNKNOWN", "reliability_score": None}
    process_document(data)  # Continue pipeline
    audit_log.record(data, "preflight_unavailable")
```

### 3. Use Correlation IDs

Always pass your internal document ID as `client_correlation_id`:

```python
result = preflight.evaluate(
    ...,
    client_correlation_id=document.id  # Your ID
)
# Later, query by correlation_id to find evaluations
```

### 4. Monitor Drift Scores

Set up alerts when drift scores trend upward:

```python
if result["drift_score"] > 0.3:
    alert("High drift detected", result)
```

---

## Support

- **Documentation:** https://docs.preflight.dev
- **API Status:** https://status.preflight.dev
- **Email:** support@preflight.dev
