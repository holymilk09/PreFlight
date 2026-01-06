# Document Extraction Control Plane — Build Specification

> **Purpose**: This document serves as the complete specification for building a metadata-only document extraction governance system. Paste this into Claude Code to begin implementation.

-----

## Executive Summary

We are building a **document extraction control plane** — a B2B infrastructure SaaS that governs enterprise document extraction pipelines without ever touching the documents themselves.

**Core Value Proposition**: "We govern document extraction systems without touching documents."

**What We Receive**: Layout fingerprints, structural features, bounding box coordinates, element types, extractor metadata, confidence scores, document hashes.

**What We Never See**: Document images, PDFs, extracted text, field values, PII, PHI, or any actual content.

**What We Return**: Template identity, drift risk scores, reliability scores, correction rules, replay lineage, audit certificates, extractor recommendations, cost optimizations.

-----

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CUSTOMER ENVIRONMENT (Their Network)                  │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────────────────┐ │
│  │   PDFs /    │───▶│ Local Extraction │───▶│    Results Database         │ │
│  │  Documents  │    │ (NVIDIA/OCR/VLM) │    │    (Their Storage)          │ │
│  └─────────────┘    └────────┬─────────┘    └─────────────────────────────┘ │
│                              │                           ▲                   │
│                              │ Metadata Only             │ Decisions + Rules │
└──────────────────────────────┼───────────────────────────┼───────────────────┘
                               │                           │
                               ▼                           │
┌──────────────────────────────────────────────────────────┴───────────────────┐
│                           CONTROL PLANE (Our Service)                         │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         API Gateway / Ingress                            │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                        │
│                                      ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                      DECISION ENGINE CORE                                │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐│ │
│  │  │  Template   │ │    Drift    │ │ Reliability │ │    Correction       ││ │
│  │  │  Matching   │ │  Detection  │ │   Scoring   │ │    Governance       ││ │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘│ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                        │
│                                      ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                      EXTENDED CAPABILITIES                               │ │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌─────────────┐  │ │
│  │  │   Extractor   │ │  Cost-Aware   │ │   Anomaly     │ │ Predictive  │  │ │
│  │  │  Arbitration  │ │   Routing     │ │  Detection    │ │   Drift     │  │ │
│  │  └───────────────┘ └───────────────┘ └───────────────┘ └─────────────┘  │ │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌─────────────┐  │ │
│  │  │  Cross-Cust   │ │    Audit      │ │    Schema     │ │   Human     │  │ │
│  │  │  Benchmarks   │ │ Certificates  │ │  Evolution    │ │   Review    │  │ │
│  │  └───────────────┘ └───────────────┘ └───────────────┘ └─────────────┘  │ │
│  │  ┌───────────────┐ ┌───────────────┐                                    │ │
│  │  │  Correction   │ │  Seasonality  │                                    │ │
│  │  │   Feedback    │ │  & Capacity   │                                    │ │
│  │  └───────────────┘ └───────────────┘                                    │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                        │
│                                      ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        DATA STORES                                       │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────┐  │ │
│  │  │  PostgreSQL  │ │ TimescaleDB  │ │   Trillian   │ │     Redis      │  │ │
│  │  │ Event Store  │ │   Metrics    │ │  Audit Log   │ │  Performance   │  │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────┘
```

-----

## Technology Stack

### Core Infrastructure

- **Workflow Orchestration**: Temporal.io (durable execution, saga pattern, human-in-the-loop support)
- **Event Streaming**: Apache Kafka (event sourcing backbone, cross-service communication)
- **API Gateway**: Kong or Envoy (rate limiting, auth, routing)

### Data Stores

- **Event Store**: PostgreSQL with Row-Level Security (multi-tenant OLTP, event sourcing)
- **Time-Series Metrics**: TimescaleDB (drift scores, reliability trends, performance tracking)
- **Audit Log**: Trillian (Merkle tree, tamper-proof, cryptographic proofs)
- **Real-Time Cache**: Redis (Thompson Sampling parameters, session state, materialized views)
- **Search**: Elasticsearch (template search, document search)

### ML/Decision Engine

- **Contextual Bandits**: Vowpal Wabbit with `--cb_explore_adf` (extractor selection)
- **Anomaly Detection**: Isolation Forest (real-time), VAE (batch verification)
- **Time-Series Forecasting**: Prophet (seasonality), PELT (changepoint detection)
- **Federated Learning**: TensorFlow Federated (privacy-preserving corrections)

### Languages

- **Primary**: Python 3.11+ (ML, data processing, Temporal workers)
- **Performance-Critical**: Rust (fingerprinting, hot path processing)
- **API Layer**: FastAPI (async, OpenAPI spec generation)

-----

## Core Data Models

### Layout Fingerprint (Input from Customer)

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

class ExtractorMetadata(BaseModel):
    vendor: str  # "nvidia", "abbyy", "tesseract", "custom"
    model: str  # "nemotron-parse-1.2"
    version: str
    confidence: float
    latency_ms: int
    cost_usd: Optional[float]

class EvaluateRequest(BaseModel):
    layout_fingerprint: str  # Hash of structural features
    structural_features: StructuralFeatures
    extractor_metadata: ExtractorMetadata
    client_doc_hash: str  # SHA256 of document (we never see content)
    client_correlation_id: str
    tenant_id: str
    pipeline_id: str
```

### Decision Response (Output to Customer)

```python
class Decision(str, Enum):
    MATCH = "MATCH"  # Matches known template, high confidence
    REVIEW = "REVIEW"  # Needs human review
    NEW = "NEW"  # New template detected
    REJECT = "REJECT"  # Anomaly detected, potential fraud

class CorrectionRule(BaseModel):
    field: str
    rule: str  # "sum_line_items", "iso8601_normalize", "currency_standardize"
    parameters: Optional[dict]

class AuditLineage(BaseModel):
    matched_at: str  # ISO8601
    template_version_history: List[str]
    last_drift_check: str
    merkle_proof: str  # Inclusion proof in audit log
    certificate_hash: str

class ExtractorRecommendation(BaseModel):
    recommended_extractor: str
    expected_reliability: float
    expected_cost_usd: float
    reasoning: str

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

### Template Registry

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

### Event Sourcing Events

```python
class DocumentEvent(BaseModel):
    event_id: str  # UUID v7 (time-ordered)
    event_type: str
    aggregate_id: str  # Document correlation ID
    tenant_id: str
    timestamp: str
    payload: dict
    metadata: dict

# Event Types:
# - DocumentSubmitted
# - LayoutAnalyzed
# - TemplateMatched
# - DriftDetected
# - AnomalyDetected
# - ReviewRequested
# - ReviewCompleted
# - CorrectionApplied
# - CertificateGenerated
# - DocumentFinalized
```

-----

## Capability Specifications

### 1. Template Matching

**Purpose**: Identify which known template a document matches based on structural features.

**Algorithm**:

1. Compute layout fingerprint hash from structural features
1. LSH (Locality-Sensitive Hashing) lookup for candidate templates
1. Tree edit distance refinement for top-k candidates
1. Return best match with confidence score

**Data Structures**:

- MinHash signatures for O(1) similarity lookup
- Interval encoding for fixed-length structural vectors
- Template registry with versioned fingerprints

```python
async def match_template(
    fingerprint: str,
    features: StructuralFeatures,
    tenant_id: str
) -> tuple[Optional[TemplateVersion], float]:
    """
    Returns (matched_template, confidence) or (None, 0.0) if no match.
    Confidence threshold for MATCH: 0.85
    Confidence threshold for REVIEW: 0.50
    Below 0.50: NEW template
    """
    # 1. LSH lookup
    candidates = await lsh_index.query(fingerprint, k=10)

    # 2. Tree edit distance refinement
    scored = []
    for candidate in candidates:
        distance = tree_edit_distance(features, candidate.features)
        similarity = 1.0 - (distance / max_distance)
        scored.append((candidate, similarity))

    # 3. Return best match
    scored.sort(key=lambda x: x[1], reverse=True)
    if scored and scored[0][1] >= 0.50:
        return scored[0]
    return None, 0.0
```

### 2. Drift Detection

**Purpose**: Detect when extraction behavior is changing over time for a template.

**Algorithm**:

1. Maintain rolling statistics per template (mean, variance of reliability, field confidence)
1. CUSUM charts for small persistent shifts
1. PELT changepoint detection for regime changes
1. Alert when drift score exceeds threshold

**Drift Score Computation**:

```python
def compute_drift_score(
    template_id: str,
    current_features: StructuralFeatures,
    current_reliability: float,
    window_days: int = 14
) -> float:
    """
    Returns drift score 0.0 (no drift) to 1.0 (severe drift).

    Components:
    - Structural drift: How much layout has changed from baseline
    - Reliability drift: How much extraction quality has changed
    - Confidence drift: How much extractor confidence has changed
    """
    baseline = get_template_baseline(template_id)
    recent_stats = get_rolling_stats(template_id, window_days)

    # Structural drift (Jaccard distance of element types)
    structural_drift = 1.0 - jaccard_similarity(
        current_features.element_types,
        baseline.element_types
    )

    # Reliability drift (z-score from baseline)
    reliability_zscore = abs(
        current_reliability - baseline.reliability
    ) / baseline.reliability_std
    reliability_drift = min(1.0, reliability_zscore / 3.0)

    # Trend drift (slope of recent reliability)
    trend_drift = max(0.0, -recent_stats.reliability_slope * 10)

    # Weighted combination
    drift_score = (
        0.3 * structural_drift +
        0.4 * reliability_drift +
        0.3 * trend_drift
    )

    return min(1.0, drift_score)
```

**Thresholds**:

- `< 0.15`: Stable (green)
- `0.15 - 0.30`: Watch (yellow)
- `0.30 - 0.50`: Review required (orange)
- `> 0.50`: Critical drift (red)

### 3. Reliability Scoring

**Purpose**: Predict how reliable the extraction results are likely to be.

**Algorithm**:

```python
def compute_reliability_score(
    template: TemplateVersion,
    extractor: ExtractorMetadata,
    features: StructuralFeatures,
    drift_score: float
) -> float:
    """
    Returns reliability score 0.0 to 1.0.

    Factors:
    - Historical extractor performance on this template
    - Current extractor confidence
    - Drift penalty
    - Document quality signals
    """
    # Base: historical performance
    historical = template.extractor_performance.get(
        extractor.vendor,
        0.85  # Default for unknown extractors
    )

    # Confidence adjustment
    confidence_factor = extractor.confidence

    # Drift penalty (exponential decay)
    drift_penalty = math.exp(-2.0 * drift_score)

    # Document quality (from structural features)
    quality_factor = compute_quality_factor(features)

    reliability = (
        historical * 0.4 +
        confidence_factor * 0.3 +
        drift_penalty * 0.2 +
        quality_factor * 0.1
    )

    return min(1.0, max(0.0, reliability))
```

### 4. Correction Governance

**Purpose**: Provide deterministic rules for post-processing extraction results.

**Rule Types**:

```python
CORRECTION_RULES = {
    "sum_line_items": {
        "description": "Total should equal sum of line items",
        "validation": "total == sum(line_items.amount)",
        "correction": "total = sum(line_items.amount)"
    },
    "iso8601_normalize": {
        "description": "Normalize date to ISO8601",
        "validation": "date matches ISO8601",
        "correction": "parse and reformat to YYYY-MM-DD"
    },
    "currency_standardize": {
        "description": "Standardize currency format",
        "validation": "amount matches currency pattern",
        "correction": "convert to decimal with 2 places"
    },
    "address_normalize": {
        "description": "Normalize address format",
        "validation": "address components present",
        "correction": "apply USPS standardization"
    },
    "name_case_normalize": {
        "description": "Normalize name casing",
        "validation": "name is proper case",
        "correction": "apply title case rules"
    }
}
```

**Rule Selection**:

```python
def select_correction_rules(
    template: TemplateVersion,
    features: StructuralFeatures,
    reliability_score: float
) -> List[CorrectionRule]:
    """
    Returns ordered list of correction rules to apply.

    Logic:
    1. Always apply template-defined rules
    2. Add reliability-based rules when score < 0.95
    3. Add field-specific rules based on detected issues
    """
    rules = list(template.correction_rules)

    if reliability_score < 0.95:
        # Add validation rules
        rules.append(CorrectionRule(
            field="*",
            rule="cross_field_validation",
            parameters={"strict": reliability_score < 0.80}
        ))

    return rules
```

### 5. Extractor Arbitration

**Purpose**: Recommend which extractor to use based on document characteristics.

**Algorithm**: Thompson Sampling contextual bandit

```python
class ExtractorArbitrator:
    """
    Contextual bandit for extractor selection.
    Uses Thompson Sampling with Beta distributions per (template, extractor) pair.
    """

    def __init__(self):
        self.redis = Redis()  # Stores Beta parameters

    async def recommend(
        self,
        template_id: str,
        features: StructuralFeatures,
        available_extractors: List[str],
        optimization_profile: str = "balanced"  # "cost", "quality", "latency"
    ) -> ExtractorRecommendation:
        """
        Returns recommended extractor with expected performance.
        """
        scores = []

        for extractor in available_extractors:
            # Get Beta distribution parameters
            alpha, beta = await self.get_params(template_id, extractor)

            # Thompson sample
            sampled_reliability = np.random.beta(alpha, beta)

            # Get cost estimate
            cost = await self.get_cost(extractor, features)

            # Compute score based on optimization profile
            if optimization_profile == "cost":
                score = sampled_reliability / (cost + 0.001)
            elif optimization_profile == "quality":
                score = sampled_reliability
            else:  # balanced
                score = sampled_reliability * 0.7 + (1.0 / (cost + 0.01)) * 0.3

            scores.append((extractor, sampled_reliability, cost, score))

        # Select best
        scores.sort(key=lambda x: x[3], reverse=True)
        best = scores[0]

        return ExtractorRecommendation(
            recommended_extractor=best[0],
            expected_reliability=best[1],
            expected_cost_usd=best[2],
            reasoning=f"Thompson Sampling selection, profile={optimization_profile}"
        )

    async def record_outcome(
        self,
        template_id: str,
        extractor: str,
        success: bool
    ):
        """
        Update Beta parameters based on extraction outcome.
        """
        key = f"arbitrator:{template_id}:{extractor}"
        if success:
            await self.redis.hincrby(key, "alpha", 1)
        else:
            await self.redis.hincrby(key, "beta", 1)
```

### 6. Cost-Aware Routing

**Purpose**: Optimize extractor selection for cost while meeting reliability thresholds.

```python
class CostAwareRouter:
    """
    Pareto-optimal routing based on cost-reliability tradeoffs.
    """

    PROFILES = {
        "cost_first": {"cost": 0.70, "reliability": 0.20, "latency": 0.10},
        "quality_first": {"cost": 0.10, "reliability": 0.80, "latency": 0.10},
        "balanced": {"cost": 0.33, "reliability": 0.33, "latency": 0.34},
        "latency_sensitive": {"cost": 0.20, "reliability": 0.30, "latency": 0.50}
    }

    async def route(
        self,
        template_id: str,
        features: StructuralFeatures,
        reliability_threshold: float,
        profile: str = "balanced"
    ) -> tuple[str, float, float]:
        """
        Returns (extractor, expected_cost, expected_reliability).
        Only considers extractors meeting reliability_threshold.
        """
        weights = self.PROFILES[profile]
        candidates = []

        for extractor in await self.get_available_extractors():
            reliability = await self.get_expected_reliability(
                template_id, extractor
            )

            if reliability < reliability_threshold:
                continue

            cost = await self.get_cost(extractor, features)
            latency = await self.get_latency(extractor)

            # Normalize and score
            score = (
                weights["cost"] * (1.0 - cost / self.max_cost) +
                weights["reliability"] * reliability +
                weights["latency"] * (1.0 - latency / self.max_latency)
            )

            candidates.append((extractor, cost, reliability, score))

        if not candidates:
            raise NoExtractorMeetsThreshold(reliability_threshold)

        candidates.sort(key=lambda x: x[3], reverse=True)
        best = candidates[0]

        return best[0], best[1], best[2]
```

### 7. Anomaly Detection

**Purpose**: Detect unknown layouts, potential fraud, and format drift.

```python
class AnomalyDetector:
    """
    Hybrid detection: Isolation Forest (fast) + VAE (precise).
    """

    def __init__(self):
        self.isolation_forest = IsolationForest(
            contamination=0.05,
            random_state=42
        )
        self.vae = load_trained_vae()  # Trained on known templates

    async def detect(
        self,
        features: StructuralFeatures,
        tenant_id: str
    ) -> tuple[bool, str, float]:
        """
        Returns (is_anomaly, anomaly_type, confidence).

        Anomaly types:
        - "new_vendor": Legitimate new template
        - "format_drift": Gradual template evolution
        - "potential_fraud": Suspicious manipulation
        - "quality_issue": Document quality problems
        """
        # Extract feature vector
        feature_vector = self.featurize(features)

        # Fast check with Isolation Forest
        if_score = self.isolation_forest.score_samples([feature_vector])[0]

        if if_score > -0.3:  # Not anomalous
            return False, None, 1.0 - abs(if_score)

        # Detailed analysis with VAE
        reconstruction_error = self.vae.reconstruction_error(feature_vector)

        # Classify anomaly type
        anomaly_type, confidence = self.classify_anomaly(
            features, if_score, reconstruction_error
        )

        return True, anomaly_type, confidence

    def classify_anomaly(
        self,
        features: StructuralFeatures,
        if_score: float,
        reconstruction_error: float
    ) -> tuple[str, float]:
        """
        Distinguish between anomaly types based on patterns.
        """
        # Check for fraud signals
        fraud_signals = self.check_fraud_signals(features)
        if fraud_signals > 0.7:
            return "potential_fraud", fraud_signals

        # Check for quality issues
        quality_score = self.assess_quality(features)
        if quality_score < 0.5:
            return "quality_issue", 1.0 - quality_score

        # Check for gradual drift (requires historical data)
        drift_pattern = self.check_drift_pattern(features)
        if drift_pattern > 0.6:
            return "format_drift", drift_pattern

        # Default: new vendor
        return "new_vendor", 0.8
```

### 8. Predictive Drift Alerts

**Purpose**: Predict when drift will exceed thresholds before it happens.

```python
class PredictiveDriftAlerter:
    """
    Time-series forecasting for proactive drift alerts.
    Uses Prophet for trend forecasting + PELT for changepoint detection.
    """

    async def forecast_drift(
        self,
        template_id: str,
        horizon_days: int = 14
    ) -> dict:
        """
        Returns drift forecast with alerts.
        """
        # Get historical drift scores
        history = await self.get_drift_history(template_id, days=90)

        if len(history) < 14:
            return {"status": "insufficient_data"}

        # Prophet forecast
        model = Prophet(
            changepoint_prior_scale=0.05,
            seasonality_mode='multiplicative'
        )
        model.fit(history)

        future = model.make_future_dataframe(periods=horizon_days)
        forecast = model.predict(future)

        # Check for threshold crossing
        threshold = 0.30  # Review threshold
        crossing_date = None

        for _, row in forecast.tail(horizon_days).iterrows():
            if row['yhat'] > threshold:
                crossing_date = row['ds']
                break

        # PELT changepoint detection for recent shifts
        changepoints = self.detect_changepoints(history['drift_score'].values)

        return {
            "current_drift": history['drift_score'].iloc[-1],
            "forecast_14d": forecast['yhat'].iloc[-1],
            "threshold_crossing_date": crossing_date,
            "recent_changepoints": changepoints,
            "alert_level": self.determine_alert_level(
                forecast['yhat'].iloc[-1],
                crossing_date
            )
        }

    def detect_changepoints(self, series: np.ndarray) -> List[int]:
        """
        PELT algorithm for changepoint detection.
        """
        algo = rpt.Pelt(model="rbf").fit(series)
        changepoints = algo.predict(pen=10)
        return changepoints
```

### 9. Cross-Customer Benchmarking

**Purpose**: Privacy-preserving aggregate statistics across customers.

```python
class PrivacyPreservingBenchmarks:
    """
    Differential privacy + secure aggregation for cross-customer stats.
    """

    EPSILON = 2.0  # Privacy budget per query
    MIN_CUSTOMERS = 100  # k-anonymity threshold

    async def get_benchmark(
        self,
        metric: str,
        segment: str,
        tenant_id: str
    ) -> dict:
        """
        Returns anonymized benchmark with DP guarantees.
        """
        # Get tenant's value
        tenant_value = await self.get_tenant_metric(tenant_id, metric)

        # Get aggregate (only if >= MIN_CUSTOMERS)
        segment_count = await self.get_segment_count(segment)
        if segment_count < self.MIN_CUSTOMERS:
            return {"status": "insufficient_peers"}

        # Compute DP aggregate
        raw_aggregate = await self.get_raw_aggregate(metric, segment)

        # Add Laplace noise
        sensitivity = self.get_sensitivity(metric)
        noise = np.random.laplace(0, sensitivity / self.EPSILON)
        dp_aggregate = raw_aggregate + noise

        # Compute percentile (approximate)
        percentile = await self.get_approximate_percentile(
            tenant_value, metric, segment
        )

        return {
            "tenant_value": tenant_value,
            "segment_median": dp_aggregate,
            "percentile": percentile,
            "segment_size": segment_count,
            "privacy_guarantee": f"ε={self.EPSILON}-differential privacy"
        }
```

### 10. Audit Certificates

**Purpose**: Cryptographic proof of extraction decisions for compliance.

```python
class AuditCertificateGenerator:
    """
    Merkle tree audit log with RFC 3161 timestamping.
    Uses Google Trillian for append-only log.
    """

    async def generate_certificate(
        self,
        decision: EvaluateResponse,
        request: EvaluateRequest
    ) -> AuditCertificate:
        """
        Generate tamper-proof audit certificate.
        """
        # Create certificate content
        certificate_content = {
            "decision_id": str(uuid7()),
            "timestamp": datetime.utcnow().isoformat(),
            "tenant_id": request.tenant_id,
            "document_hash": request.client_doc_hash,
            "template_matched": decision.template_version_id,
            "decision": decision.decision.value,
            "drift_score": decision.drift_score,
            "reliability_score": decision.reliability_score,
            "extractor": {
                "vendor": request.extractor_metadata.vendor,
                "model": request.extractor_metadata.model,
                "version": request.extractor_metadata.version
            },
            "correction_rules_applied": [
                r.model_dump() for r in decision.correction_rules
            ]
        }

        # Hash content
        content_hash = hashlib.sha256(
            json.dumps(certificate_content, sort_keys=True).encode()
        ).hexdigest()

        # Append to Merkle tree
        leaf_index = await self.trillian_client.append_leaf(content_hash)

        # Get inclusion proof
        inclusion_proof = await self.trillian_client.get_inclusion_proof(
            leaf_index
        )

        # Get RFC 3161 timestamp
        timestamp_token = await self.get_rfc3161_timestamp(content_hash)

        return AuditCertificate(
            certificate_id=certificate_content["decision_id"],
            content_hash=content_hash,
            merkle_leaf_index=leaf_index,
            merkle_root=inclusion_proof.root_hash,
            inclusion_proof=inclusion_proof.proof_hashes,
            rfc3161_timestamp=timestamp_token,
            certificate_content=certificate_content
        )

    async def verify_certificate(
        self,
        certificate: AuditCertificate
    ) -> bool:
        """
        Verify certificate integrity and inclusion.
        """
        # Verify content hash
        computed_hash = hashlib.sha256(
            json.dumps(certificate.certificate_content, sort_keys=True).encode()
        ).hexdigest()

        if computed_hash != certificate.content_hash:
            return False

        # Verify Merkle inclusion
        is_included = verify_merkle_proof(
            certificate.content_hash,
            certificate.merkle_leaf_index,
            certificate.inclusion_proof,
            certificate.merkle_root
        )

        if not is_included:
            return False

        # Verify RFC 3161 timestamp
        is_timestamped = verify_rfc3161(
            certificate.content_hash,
            certificate.rfc3161_timestamp
        )

        return is_timestamped
```

### 11. Human Review Orchestration

**Purpose**: Route documents needing review to appropriate reviewers.

```python
class ReviewOrchestrator:
    """
    Skill-based routing with SLA management.
    """

    async def route_for_review(
        self,
        document_id: str,
        template_id: str,
        review_reason: str,
        tenant_id: str
    ) -> ReviewTask:
        """
        Create and route review task.
        """
        # Determine required skills
        required_skills = await self.get_required_skills(
            template_id, review_reason
        )

        # Find available reviewers
        reviewers = await self.get_available_reviewers(
            tenant_id, required_skills
        )

        # Score and select
        scored = []
        for reviewer in reviewers:
            skill_score = self.compute_skill_score(
                reviewer.skills, required_skills
            )
            workload_score = 1.0 - (reviewer.current_tasks / reviewer.capacity)

            score = skill_score * 0.6 + workload_score * 0.4
            scored.append((reviewer, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        assigned_reviewer = scored[0][0] if scored else None

        # Compute SLA
        sla = await self.compute_sla(template_id, review_reason)

        # Create task
        task = ReviewTask(
            task_id=str(uuid7()),
            document_id=document_id,
            template_id=template_id,
            review_reason=review_reason,
            assigned_reviewer=assigned_reviewer.id if assigned_reviewer else None,
            required_skills=required_skills,
            sla_deadline=datetime.utcnow() + sla,
            priority=self.compute_priority(review_reason, template_id),
            status="pending"
        )

        await self.task_queue.enqueue(task)

        return task
```

### 12. Correction Feedback Loop

**Purpose**: Learn from corrections to improve future decisions.

```python
class CorrectionFeedbackProcessor:
    """
    Safe incorporation of user corrections with outlier detection.
    """

    async def process_correction(
        self,
        correction: CorrectionSubmission
    ) -> FeedbackResult:
        """
        Process and potentially incorporate correction.
        """
        # Outlier detection
        is_outlier, outlier_reason = await self.detect_outlier(correction)

        if is_outlier:
            return FeedbackResult(
                accepted=False,
                reason=f"Outlier detected: {outlier_reason}",
                action="manual_review_required"
            )

        # Validate correction
        is_valid, validation_errors = await self.validate_correction(correction)

        if not is_valid:
            return FeedbackResult(
                accepted=False,
                reason=f"Validation failed: {validation_errors}",
                action="correction_rejected"
            )

        # Compute confidence weight
        weight = await self.compute_correction_weight(correction)

        # Store for batch aggregation
        await self.correction_store.add(correction, weight)

        # Update real-time metrics
        await self.update_metrics(correction)

        return FeedbackResult(
            accepted=True,
            weight=weight,
            action="incorporated_pending_batch"
        )

    async def detect_outlier(
        self,
        correction: CorrectionSubmission
    ) -> tuple[bool, Optional[str]]:
        """
        Detect potentially adversarial or erroneous corrections.
        """
        # Feature extraction
        features = self.extract_correction_features(correction)

        # Isolation Forest check
        score = self.outlier_detector.score_samples([features])[0]

        if score < -0.5:
            return True, "statistical_outlier"

        # Label flip detection
        if await self.is_label_flip(correction):
            return True, "potential_label_flip"

        # Velocity check (too many corrections too fast)
        if await self.exceeds_correction_velocity(correction.user_id):
            return True, "correction_velocity_exceeded"

        return False, None
```

### 13. Schema Evolution Governance

**Purpose**: Manage template schema changes safely.

```python
class SchemaEvolutionManager:
    """
    Confluent Schema Registry-style compatibility checking.
    """

    COMPATIBILITY_MODES = {
        "BACKWARD": "New schema can read old data",
        "FORWARD": "Old schema can read new data",
        "FULL": "Both backward and forward compatible",
        "NONE": "No compatibility checking"
    }

    async def register_schema_version(
        self,
        template_id: str,
        new_schema: TemplateSchema,
        compatibility_mode: str = "BACKWARD"
    ) -> SchemaRegistrationResult:
        """
        Register new schema version with compatibility check.
        """
        # Get existing versions
        existing_versions = await self.get_schema_versions(template_id)

        if not existing_versions:
            # First version, auto-approve
            return await self.store_schema(template_id, new_schema, "v1")

        # Check compatibility
        latest = existing_versions[-1]
        is_compatible, violations = self.check_compatibility(
            latest.schema,
            new_schema,
            compatibility_mode
        )

        if not is_compatible:
            return SchemaRegistrationResult(
                success=False,
                violations=violations,
                recommendation=self.generate_migration_guide(
                    latest.schema, new_schema
                )
            )

        # Check downstream impact
        impacted = await self.get_downstream_consumers(template_id)

        # Register new version
        new_version = f"v{len(existing_versions) + 1}"
        await self.store_schema(template_id, new_schema, new_version)

        # Notify consumers
        await self.notify_consumers(impacted, template_id, new_version)

        return SchemaRegistrationResult(
            success=True,
            version=new_version,
            impacted_consumers=impacted
        )

    def check_compatibility(
        self,
        old_schema: TemplateSchema,
        new_schema: TemplateSchema,
        mode: str
    ) -> tuple[bool, List[str]]:
        """
        Check schema compatibility based on mode.
        """
        violations = []

        if mode in ["BACKWARD", "FULL"]:
            # New schema must be able to read old data
            # = Can only add optional fields, not remove or modify
            for field in old_schema.fields:
                if field.name not in [f.name for f in new_schema.fields]:
                    if field.required:
                        violations.append(
                            f"Removed required field: {field.name}"
                        )

        if mode in ["FORWARD", "FULL"]:
            # Old schema must be able to read new data
            # = New required fields must have defaults
            for field in new_schema.fields:
                if field.name not in [f.name for f in old_schema.fields]:
                    if field.required and field.default is None:
                        violations.append(
                            f"New required field without default: {field.name}"
                        )

        return len(violations) == 0, violations
```

### 14. Seasonality & Capacity Signals

**Purpose**: Detect patterns and predict capacity needs.

```python
class SeasonalityAnalyzer:
    """
    MSTL decomposition + capacity planning.
    """

    async def analyze_patterns(
        self,
        tenant_id: str,
        metric: str = "document_volume"
    ) -> SeasonalityReport:
        """
        Decompose time series and identify patterns.
        """
        # Get historical data
        data = await self.get_metric_history(tenant_id, metric, days=90)

        # MSTL decomposition
        mstl = MSTL(
            data['value'],
            periods=[24, 24*7, 24*30],  # Daily, weekly, monthly
            windows=None,
            lmbda="auto"
        )
        result = mstl.fit()

        # Extract components
        trend = result.trend
        seasonal_daily = result.seasonal['seasonal_24']
        seasonal_weekly = result.seasonal['seasonal_168']
        seasonal_monthly = result.seasonal['seasonal_720']
        residual = result.resid

        # Forecast next 7 days
        forecast = self.forecast(data, horizon_hours=168)

        # Capacity recommendations
        capacity_recs = self.generate_capacity_recommendations(
            forecast, current_capacity=await self.get_current_capacity(tenant_id)
        )

        return SeasonalityReport(
            patterns={
                "daily_peak_hour": self.find_peak(seasonal_daily),
                "weekly_peak_day": self.find_peak(seasonal_weekly),
                "monthly_trend": "increasing" if trend.iloc[-1] > trend.iloc[0] else "decreasing"
            },
            forecast_7d=forecast,
            capacity_recommendations=capacity_recs,
            anomalies=self.detect_residual_anomalies(residual)
        )
```

-----

## Workflow Orchestration (Temporal.io)

### Main Document Processing Workflow

```python
from temporalio import workflow, activity
from datetime import timedelta

@workflow.defn
class DocumentProcessingWorkflow:
    """
    Main saga for document evaluation with human-in-the-loop support.
    """

    @workflow.run
    async def run(self, request: EvaluateRequest) -> EvaluateResponse:
        # Step 1: Analyze layout and detect anomalies
        anomaly_result = await workflow.execute_activity(
            detect_anomalies,
            request.structural_features,
            start_to_close_timeout=timedelta(seconds=30)
        )

        if anomaly_result.is_anomaly and anomaly_result.type == "potential_fraud":
            return EvaluateResponse(
                decision=Decision.REJECT,
                drift_score=1.0,
                reliability_score=0.0,
                correction_rules=[],
                replay_hash=await self.generate_replay_hash(),
                alerts=["Potential fraud detected"]
            )

        # Step 2: Match template
        template, match_confidence = await workflow.execute_activity(
            match_template,
            request.layout_fingerprint,
            request.structural_features,
            request.tenant_id,
            start_to_close_timeout=timedelta(seconds=30)
        )

        # Step 3: Compute drift and reliability
        if template:
            drift_score = await workflow.execute_activity(
                compute_drift_score,
                template.template_id,
                request.structural_features,
                start_to_close_timeout=timedelta(seconds=30)
            )

            reliability_score = await workflow.execute_activity(
                compute_reliability_score,
                template,
                request.extractor_metadata,
                request.structural_features,
                drift_score,
                start_to_close_timeout=timedelta(seconds=30)
            )
        else:
            drift_score = 0.0
            reliability_score = 0.0

        # Step 4: Determine decision
        if template is None or match_confidence < 0.50:
            decision = Decision.NEW
        elif match_confidence < 0.85 or reliability_score < 0.80:
            decision = Decision.REVIEW
        else:
            decision = Decision.MATCH

        # Step 5: Handle REVIEW decision (human-in-the-loop)
        if decision == Decision.REVIEW:
            review_task = await workflow.execute_activity(
                create_review_task,
                request.client_correlation_id,
                template.template_id if template else None,
                "low_confidence",
                request.tenant_id,
                start_to_close_timeout=timedelta(seconds=60)
            )

            # Wait for human review (can take hours/days)
            review_result = await workflow.wait_signal("human_review_completed")

            # Update based on review
            if review_result.approved:
                decision = Decision.MATCH
                template = review_result.confirmed_template
            else:
                decision = Decision.REJECT

        # Step 6: Get correction rules
        correction_rules = []
        if template:
            correction_rules = await workflow.execute_activity(
                select_correction_rules,
                template,
                request.structural_features,
                reliability_score,
                start_to_close_timeout=timedelta(seconds=30)
            )

        # Step 7: Get extractor recommendation
        extractor_rec = await workflow.execute_activity(
            get_extractor_recommendation,
            template.template_id if template else None,
            request.structural_features,
            start_to_close_timeout=timedelta(seconds=30)
        )

        # Step 8: Generate audit certificate
        response = EvaluateResponse(
            decision=decision,
            template_version_id=template.version_id if template else None,
            drift_score=drift_score,
            reliability_score=reliability_score,
            correction_rules=correction_rules,
            replay_hash=await self.generate_replay_hash(),
            audit_lineage=AuditLineage(
                matched_at=workflow.now().isoformat(),
                template_version_history=template.version_history if template else [],
                last_drift_check=workflow.now().isoformat(),
                merkle_proof="",  # Filled by certificate generator
                certificate_hash=""
            ),
            extractor_recommendation=extractor_rec,
            alerts=[]
        )

        # Step 9: Generate and attach audit certificate
        certificate = await workflow.execute_activity(
            generate_audit_certificate,
            response,
            request,
            start_to_close_timeout=timedelta(seconds=60)
        )

        response.audit_lineage.merkle_proof = certificate.merkle_proof
        response.audit_lineage.certificate_hash = certificate.certificate_hash

        # Step 10: Record metrics and update arbitrator
        await workflow.execute_activity(
            record_decision_metrics,
            request,
            response,
            start_to_close_timeout=timedelta(seconds=30)
        )

        return response
```

-----

## API Design

### OpenAPI Endpoints

```yaml
openapi: 3.1.0
info:
  title: Document Extraction Control Plane API
  version: 1.0.0

paths:
  /v1/evaluate:
    post:
      summary: Evaluate document extraction metadata
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/EvaluateRequest'
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/EvaluateResponse'

  /v1/templates:
    get:
      summary: List templates for tenant
    post:
      summary: Register new template

  /v1/templates/{template_id}/versions:
    get:
      summary: Get version history
    post:
      summary: Register new version

  /v1/templates/{template_id}/drift:
    get:
      summary: Get drift analysis and forecast

  /v1/corrections:
    post:
      summary: Submit correction feedback

  /v1/reviews/{task_id}:
    get:
      summary: Get review task status
    post:
      summary: Submit review decision

  /v1/certificates/{certificate_id}:
    get:
      summary: Get audit certificate
    post:
      summary: Verify audit certificate

  /v1/benchmarks:
    get:
      summary: Get anonymized cross-customer benchmarks

  /v1/extractors/recommend:
    post:
      summary: Get extractor recommendation

  /v1/analytics/seasonality:
    get:
      summary: Get seasonality analysis
```

-----

## Project Structure

```
control-plane/
├── CLAUDE.md                    # This file - project context
├── docker-compose.yml           # Local development stack
├── pyproject.toml              # Python dependencies
├── Cargo.toml                  # Rust dependencies (fingerprinting)
│
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app
│   │   ├── routes/
│   │   │   ├── evaluate.py
│   │   │   ├── templates.py
│   │   │   ├── corrections.py
│   │   │   ├── reviews.py
│   │   │   ├── certificates.py
│   │   │   └── analytics.py
│   │   └── middleware/
│   │       ├── auth.py
│   │       ├── tenant.py
│   │       └── rate_limit.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py           # Pydantic models
│   │   ├── events.py           # Event definitions
│   │   └── config.py           # Configuration
│   │
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── template_matcher.py
│   │   ├── drift_detector.py
│   │   ├── reliability_scorer.py
│   │   ├── correction_governor.py
│   │   ├── anomaly_detector.py
│   │   ├── extractor_arbitrator.py
│   │   ├── cost_router.py
│   │   └── predictive_alerts.py
│   │
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── document_processing.py
│   │   ├── review_orchestration.py
│   │   ├── correction_processing.py
│   │   └── activities.py
│   │
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── certificate_generator.py
│   │   ├── merkle_tree.py
│   │   └── timestamp_service.py
│   │
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── seasonality.py
│   │   ├── benchmarks.py
│   │   └── capacity_planner.py
│   │
│   ├── feedback/
│   │   ├── __init__.py
│   │   ├── correction_processor.py
│   │   ├── outlier_detector.py
│   │   └── federated_learning.py
│   │
│   ├── schema/
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── compatibility.py
│   │   └── migration.py
│   │
│   └── infrastructure/
│       ├── __init__.py
│       ├── database.py         # PostgreSQL
│       ├── timescale.py        # TimescaleDB
│       ├── redis_client.py     # Redis
│       ├── kafka_client.py     # Kafka
│       ├── trillian_client.py  # Merkle tree
│       └── temporal_client.py  # Workflow engine
│
├── rust/
│   └── fingerprint/
│       ├── Cargo.toml
│       └── src/
│           ├── lib.rs
│           ├── layout.rs       # Layout fingerprinting
│           ├── similarity.rs   # Tree edit distance
│           └── hash.rs         # MinHash/LSH
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── migrations/
│   └── postgresql/
│
└── deploy/
    ├── kubernetes/
    └── terraform/
```

-----

## Implementation Order

### Phase 1: Core Pipeline (Weeks 1-4)

1. Set up project structure and Docker Compose
1. Implement core data models (Pydantic)
1. PostgreSQL event store with basic CRUD
1. Template matching (LSH + simple similarity)
1. Basic drift detection (rolling statistics)
1. Reliability scoring
1. FastAPI endpoints for /evaluate
1. Basic Temporal workflow

### Phase 2: Decision Engine (Weeks 5-8)

1. Rust fingerprinting module (performance critical)
1. Anomaly detection (Isolation Forest)
1. Correction governance rules engine
1. Extractor arbitration (Thompson Sampling)
1. Cost-aware routing
1. TimescaleDB metrics storage
1. Drift forecasting (Prophet)

### Phase 3: Compliance & Intelligence (Weeks 9-12)

1. Trillian Merkle tree integration
1. Audit certificate generation
1. RFC 3161 timestamping
1. Human review orchestration
1. Schema evolution governance
1. Correction feedback loop
1. Cross-customer benchmarks (with DP)
1. Seasonality analysis

### Phase 4: Production Hardening (Weeks 13-16)

1. Kubernetes deployment configs
1. Comprehensive test suite
1. Monitoring and alerting
1. Documentation
1. SDK generation (Python, Java, Go)
1. Performance optimization

-----

## Key Design Principles

1. **Metadata Only**: Never accept document content. All inputs must be structural.
1. **Event Sourced**: Every decision is an immutable event. Full audit trail by design.
1. **Tenant Isolated**: Row-level security in PostgreSQL. No data leakage between tenants.
1. **Deterministic When Possible**: Correction rules are deterministic. ML components have reproducibility seeds.
1. **Fail Safe**: When uncertain, return REVIEW not MATCH. Prefer false positives over false negatives.
1. **Privacy by Design**: Differential privacy for cross-customer analytics. No raw data aggregation.
1. **Composable**: Each capability is independently usable via API. Customers can adopt incrementally.

-----

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/controlplane
TIMESCALE_URL=postgresql://user:pass@localhost:5433/metrics
REDIS_URL=redis://localhost:6379

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Temporal
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=controlplane

# Trillian
TRILLIAN_LOG_SERVER=localhost:8090

# Auth
JWT_SECRET=your-secret-key
API_KEY_SALT=your-salt

# Feature Flags
ENABLE_FEDERATED_LEARNING=false
ENABLE_CROSS_CUSTOMER_BENCHMARKS=false
```

-----

## Getting Started

```bash
# Start infrastructure
docker-compose up -d

# Install Python dependencies
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start Temporal worker
python -m src.workflows.worker

# Start API server
uvicorn src.api.main:app --reload

# Run tests
pytest tests/
```

-----

## Success Metrics

- **Latency**: p99 < 100ms for /evaluate endpoint
- **Throughput**: 10,000 evaluations/second per node
- **Accuracy**: Template matching > 95% precision/recall
- **Drift Detection**: Detect 90% of drifts before customer reports
- **Uptime**: 99.9% availability

-----

*This specification is the source of truth for the Document Extraction Control Plane. When in doubt, refer back to this document.*
