# API Reference

OpenAPI 3.1 specification for the Document Extraction Control Plane.

---

## Base URL

```
https://api.controlplane.example.com/v1
```

---

## Authentication

All endpoints (except `/health`) require API key authentication:

```
X-API-Key: cp_<32 hex characters>
```

API keys are issued per-tenant and are hashed (SHA256) before storage. The tenant is identified from the API key lookup.

**Key Format**: `cp_` prefix followed by 32 hexadecimal characters (e.g., `cp_a1b2c3d4...`)

---

## MVP vs Future Endpoints

This document includes both **MVP endpoints** (currently implemented) and **future endpoints** (planned).

**MVP Endpoints** (available now):
- `GET /health` - Health check (no auth required)
- `POST /v1/evaluate` - Core evaluation endpoint
- `GET /v1/templates` - List templates
- `POST /v1/templates` - Register template
- `GET /v1/templates/{id}` - Get template details
- `GET /v1/status` - Authenticated status check

**Future Endpoints** (documented for planning, not yet implemented):
- Template versioning and drift analysis
- Correction feedback loop
- Human review workflows
- Audit certificates
- Cross-customer benchmarks
- Extractor recommendations
- Seasonality analytics

---

## Endpoints

### POST /v1/evaluate

Evaluate document extraction metadata and return governance decision.

**Request Body**: `EvaluateRequest`
```json
{
  "layout_fingerprint": "sha256:abc123...",
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
    "bounding_boxes": [...],
    "reading_order": [0, 1, 2, ...]
  },
  "extractor_metadata": {
    "vendor": "nvidia",
    "model": "nemotron-parse-1.2",
    "version": "1.2.0",
    "confidence": 0.95,
    "latency_ms": 234,
    "cost_usd": 0.002
  },
  "client_doc_hash": "sha256:def456...",
  "client_correlation_id": "uuid",
  "tenant_id": "tenant-123",
  "pipeline_id": "invoice-processing"
}
```

**Response**: `EvaluateResponse`
```json
{
  "decision": "MATCH",
  "template_version_id": "INV-ACME-001-v3.2",
  "drift_score": 0.12,
  "reliability_score": 0.94,
  "correction_rules": [
    {"field": "total", "rule": "sum_line_items", "parameters": null}
  ],
  "replay_hash": "sha256:...",
  "audit_lineage": {
    "matched_at": "2024-01-15T10:30:00Z",
    "template_version_history": ["v3.0", "v3.1", "v3.2"],
    "last_drift_check": "2024-01-15T10:30:00Z",
    "merkle_proof": "...",
    "certificate_hash": "sha256:..."
  },
  "extractor_recommendation": {
    "recommended_extractor": "nvidia",
    "expected_reliability": 0.96,
    "expected_cost_usd": 0.002,
    "reasoning": "Thompson Sampling selection, profile=balanced"
  },
  "alerts": []
}
```

---

### GET /v1/templates

List templates for the authenticated tenant.

**Query Parameters**:
- `status` (optional): Filter by status ("active", "deprecated", "review")
- `limit` (optional): Max results (default 100)
- `offset` (optional): Pagination offset

**Response**:
```json
{
  "templates": [
    {
      "template_id": "INV-ACME-001",
      "latest_version": "v3.2",
      "status": "active",
      "document_count": 15420
    }
  ],
  "total": 42,
  "limit": 100,
  "offset": 0
}
```

---

### POST /v1/templates

Register a new template.

**Request Body**:
```json
{
  "template_id": "INV-NEWCORP-001",
  "canonical_fingerprint": "sha256:...",
  "expected_fields": ["invoice_number", "date", "total", "line_items"],
  "correction_rules": []
}
```

---

### GET /v1/templates/{template_id}/versions

Get version history for a template.

---

### POST /v1/templates/{template_id}/versions

Register a new template version.

---

### GET /v1/templates/{template_id}/drift

Get drift analysis and forecast for a template.

**Response**:
```json
{
  "current_drift": 0.12,
  "forecast_14d": 0.18,
  "threshold_crossing_date": null,
  "recent_changepoints": [],
  "alert_level": "stable"
}
```

---

### POST /v1/corrections

Submit correction feedback.

**Request Body**:
```json
{
  "document_id": "uuid",
  "template_id": "INV-ACME-001",
  "field": "total",
  "original_value": "1,234.56",
  "corrected_value": "1234.56",
  "reason": "Currency formatting"
}
```

**Response**:
```json
{
  "accepted": true,
  "weight": 0.85,
  "action": "incorporated_pending_batch"
}
```

---

### GET /v1/reviews/{task_id}

Get review task status.

---

### POST /v1/reviews/{task_id}

Submit review decision.

**Request Body**:
```json
{
  "approved": true,
  "confirmed_template_id": "INV-ACME-001",
  "notes": "Confirmed match"
}
```

---

### GET /v1/certificates/{certificate_id}

Get audit certificate.

**Response**:
```json
{
  "certificate_id": "uuid",
  "content_hash": "sha256:...",
  "merkle_leaf_index": 12345,
  "merkle_root": "sha256:...",
  "inclusion_proof": ["sha256:...", "sha256:..."],
  "rfc3161_timestamp": "...",
  "certificate_content": {...}
}
```

---

### POST /v1/certificates/{certificate_id}/verify

Verify an audit certificate.

**Response**:
```json
{
  "valid": true,
  "content_hash_verified": true,
  "merkle_proof_verified": true,
  "timestamp_verified": true
}
```

---

### GET /v1/benchmarks

Get anonymized cross-customer benchmarks.

**Query Parameters**:
- `metric`: Metric to benchmark ("reliability", "drift", "cost")
- `segment`: Industry segment

**Response**:
```json
{
  "tenant_value": 0.94,
  "segment_median": 0.91,
  "percentile": 72,
  "segment_size": 156,
  "privacy_guarantee": "ε=2.0-differential privacy"
}
```

---

### POST /v1/extractors/recommend

Get extractor recommendation for document characteristics.

**Request Body**:
```json
{
  "template_id": "INV-ACME-001",
  "structural_features": {...},
  "available_extractors": ["nvidia", "abbyy", "tesseract"],
  "optimization_profile": "balanced"
}
```

---

### GET /v1/analytics/seasonality

Get seasonality analysis and capacity forecast.

**Response**:
```json
{
  "patterns": {
    "daily_peak_hour": 14,
    "weekly_peak_day": "Tuesday",
    "monthly_trend": "increasing"
  },
  "forecast_7d": [1200, 1350, 1500, ...],
  "capacity_recommendations": [
    "Scale up 20% before Tuesday peak"
  ],
  "anomalies": []
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "TEMPLATE_NOT_FOUND",
    "message": "Template INV-UNKNOWN-001 not found",
    "details": {}
  }
}
```

**Common Error Codes**:
- `UNAUTHORIZED`: Invalid or missing API key
- `FORBIDDEN`: Tenant access denied
- `TEMPLATE_NOT_FOUND`: Template does not exist
- `VALIDATION_ERROR`: Request validation failed
- `RATE_LIMITED`: Too many requests
- `INTERNAL_ERROR`: Server error
