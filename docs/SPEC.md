# Capability Specifications

This document contains the detailed algorithm specifications and reference implementations for all 14 capabilities of the Document Extraction Control Plane.

---

## 1. Template Matching

**Purpose**: Identify which known template a document matches based on structural features.

**Algorithm**:
1. Compute layout fingerprint hash from structural features
2. LSH (Locality-Sensitive Hashing) lookup for candidate templates
3. Tree edit distance refinement for top-k candidates
4. Return best match with confidence score

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

---

## 2. Drift Detection

**Purpose**: Detect when extraction behavior is changing over time for a template.

**Algorithm**:
1. Maintain rolling statistics per template (mean, variance of reliability, field confidence)
2. CUSUM charts for small persistent shifts
3. PELT changepoint detection for regime changes
4. Alert when drift score exceeds threshold

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

---

## 3. Reliability Scoring

**Purpose**: Predict how reliable the extraction results are likely to be.

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

---

## 4. Correction Governance

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

---

## 5. Extractor Arbitration

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

---

## 6. Cost-Aware Routing

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

---

## 7. Anomaly Detection

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

---

## 8. Predictive Drift Alerts

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

---

## 9. Cross-Customer Benchmarking

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

---

## 10. Audit Certificates

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

---

## 11. Human Review Orchestration

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

---

## 12. Correction Feedback Loop

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

---

## 13. Schema Evolution Governance

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

---

## 14. Seasonality & Capacity Signals

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

---

## Temporal Workflow: Document Processing

Main saga for document evaluation with human-in-the-loop support.

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
