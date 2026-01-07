# Data Models

This document contains all Pydantic models used in the Document Extraction Control Plane.

---

## Input Models (From Customer)

### BoundingBox

```python
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class BoundingBox(BaseModel):
    x: float  # Normalized 0-1
    y: float
    width: float
    height: float
    element_type: str  # "text", "table", "image", "header", "footer", etc.
    confidence: float
    reading_order: int
```

### StructuralFeatures

```python
class StructuralFeatures(BaseModel):
    element_count: int
    table_count: int
    text_block_count: int
    image_count: int
    page_count: int
    text_density: float  # Characters per normalized area
    layout_complexity: float  # Entropy of bounding box distribution
    column_count: int
    has_header: bool
    has_footer: bool
    bounding_boxes: List[BoundingBox]
    reading_order: List[int]
```

### ExtractorMetadata

```python
class ExtractorMetadata(BaseModel):
    vendor: str  # "nvidia", "abbyy", "tesseract", "custom"
    model: str  # "nemotron-parse-1.2"
    version: str
    confidence: float
    latency_ms: int
    cost_usd: Optional[float]
```

### EvaluateRequest

```python
class EvaluateRequest(BaseModel):
    layout_fingerprint: str  # Hash of structural features
    structural_features: StructuralFeatures
    extractor_metadata: ExtractorMetadata
    client_doc_hash: str  # SHA256 of document (we never see content)
    client_correlation_id: str
    tenant_id: str
    pipeline_id: str
```

---

## Output Models (To Customer)

### Decision Enum

```python
class Decision(str, Enum):
    MATCH = "MATCH"  # Matches known template, high confidence
    REVIEW = "REVIEW"  # Needs human review
    NEW = "NEW"  # New template detected
    REJECT = "REJECT"  # Anomaly detected, potential fraud
```

### CorrectionRule

```python
class CorrectionRule(BaseModel):
    field: str
    rule: str  # "sum_line_items", "iso8601_normalize", "currency_standardize"
    parameters: Optional[dict]
```

### AuditLineage

```python
class AuditLineage(BaseModel):
    matched_at: str  # ISO8601
    template_version_history: List[str]
    last_drift_check: str
    merkle_proof: str  # Inclusion proof in audit log
    certificate_hash: str
```

### ExtractorRecommendation

```python
class ExtractorRecommendation(BaseModel):
    recommended_extractor: str
    expected_reliability: float
    expected_cost_usd: float
    reasoning: str
```

### EvaluateResponse

```python
class EvaluateResponse(BaseModel):
    decision: Decision
    template_version_id: Optional[str]
    drift_score: float  # 0.0 (no drift) to 1.0 (severe drift)
    reliability_score: float  # 0.0 to 1.0
    correction_rules: List[CorrectionRule]
    replay_hash: str  # For audit replay
    audit_lineage: AuditLineage
    extractor_recommendation: Optional[ExtractorRecommendation]
    review_metadata: Optional[dict]  # If decision is REVIEW
    alerts: List[str]  # Any warnings or notifications
```

---

## Internal Models

### TemplateVersion

```python
class TemplateVersion(BaseModel):
    version_id: str  # "INV-ACME-001-v3.2"
    template_id: str  # "INV-ACME-001"
    version: str  # "v3.2"
    created_at: str
    created_by: str

    # Structural signature
    canonical_fingerprint: str
    element_count_range: tuple[int, int]
    table_count_range: tuple[int, int]
    expected_fields: List[str]

    # Performance baselines
    baseline_reliability: float
    baseline_drift_score: float
    extractor_performance: dict[str, float]  # extractor -> reliability

    # Correction rules
    correction_rules: List[CorrectionRule]

    # Schema
    output_schema_version: str

    # Status
    status: str  # "active", "deprecated", "review"
    deprecation_reason: Optional[str]
```

### DocumentEvent (Event Sourcing)

```python
class DocumentEvent(BaseModel):
    event_id: str  # UUID v7 (time-ordered)
    event_type: str
    aggregate_id: str  # Document correlation ID
    tenant_id: str
    timestamp: str
    payload: dict
    metadata: dict
```

**Event Types**:
- `DocumentSubmitted`
- `LayoutAnalyzed`
- `TemplateMatched`
- `DriftDetected`
- `AnomalyDetected`
- `ReviewRequested`
- `ReviewCompleted`
- `CorrectionApplied`
- `CertificateGenerated`
- `DocumentFinalized`

---

## Review Models

### ReviewTask

```python
class ReviewTask(BaseModel):
    task_id: str
    document_id: str
    template_id: Optional[str]
    review_reason: str
    assigned_reviewer: Optional[str]
    required_skills: List[str]
    sla_deadline: str  # ISO8601
    priority: int
    status: str  # "pending", "in_progress", "completed"
```

### CorrectionSubmission

```python
class CorrectionSubmission(BaseModel):
    document_id: str
    template_id: str
    field: str
    original_value: str
    corrected_value: str
    user_id: str
    reason: Optional[str]
```

### FeedbackResult

```python
class FeedbackResult(BaseModel):
    accepted: bool
    weight: Optional[float]
    reason: Optional[str]
    action: str  # "incorporated_pending_batch", "correction_rejected", "manual_review_required"
```

---

## Audit Models

### AuditCertificate

```python
class AuditCertificate(BaseModel):
    certificate_id: str
    content_hash: str
    merkle_leaf_index: int
    merkle_root: str
    inclusion_proof: List[str]
    rfc3161_timestamp: str
    certificate_content: dict
```

---

## Analytics Models

### SeasonalityReport

```python
class SeasonalityReport(BaseModel):
    patterns: dict  # daily_peak_hour, weekly_peak_day, monthly_trend
    forecast_7d: List[float]
    capacity_recommendations: List[str]
    anomalies: List[dict]
```

### SchemaRegistrationResult

```python
class SchemaRegistrationResult(BaseModel):
    success: bool
    version: Optional[str]
    violations: Optional[List[str]]
    recommendation: Optional[str]
    impacted_consumers: Optional[List[str]]
```
