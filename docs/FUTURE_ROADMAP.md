# Future Roadmap (Archived)

> These features are valuable but deferred until product-market fit is validated.
> Revisit after achieving: 100 signups, 20 active users, 3 paying customers.

---

## Phase 3: Webhooks for Drift Alerts

**Goal:** Allow tenants to receive real-time notifications when drift/reliability thresholds are exceeded.

### Database Models

```python
# src/models.py additions

class WebhookStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"

class WebhookEvent(str, Enum):
    DRIFT_HIGH = "drift_high"           # drift_score > 0.30
    RELIABILITY_LOW = "reliability_low"  # reliability_score < 0.80
    DECISION_REVIEW = "decision_review"  # needs human review
    TEMPLATE_NEW = "template_new"        # new template detected

class Webhook(SQLModel, table=True):
    __tablename__ = "webhooks"

    id: UUID = SQLField(default_factory=uuid7, primary_key=True)
    tenant_id: UUID = SQLField(foreign_key="tenants.id", nullable=False, index=True)
    url: str = SQLField(max_length=500, nullable=False)
    events: list[str] = SQLField(default_factory=list, sa_column=Column(JSONB))
    secret: str = SQLField(max_length=64, nullable=False)  # For HMAC-SHA256 signing
    status: WebhookStatus = SQLField(default=WebhookStatus.ACTIVE)
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)

class WebhookDelivery(SQLModel, table=True):
    __tablename__ = "webhook_deliveries"

    id: UUID = SQLField(default_factory=uuid7, primary_key=True)
    webhook_id: UUID = SQLField(foreign_key="webhooks.id", nullable=False, index=True)
    evaluation_id: UUID | None = SQLField(foreign_key="evaluations.id", default=None)
    event_type: str = SQLField(max_length=50, nullable=False)
    payload: dict[str, Any] = SQLField(sa_column=Column(JSONB, nullable=False))
    status_code: int | None = SQLField(default=None)
    response_body: str | None = SQLField(max_length=1000, default=None)  # Truncated
    retry_count: int = SQLField(default=0)
    next_retry_at: datetime | None = SQLField(default=None)
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
```

### API Endpoints

```
# src/api/webhook_routes.py

POST   /v1/webhooks                 # Create webhook
GET    /v1/webhooks                 # List webhooks
GET    /v1/webhooks/{id}            # Get webhook details
PATCH  /v1/webhooks/{id}            # Update webhook (url, events, status)
DELETE /v1/webhooks/{id}            # Delete webhook
POST   /v1/webhooks/{id}/test       # Send test event
GET    /v1/webhooks/{id}/deliveries # List recent deliveries
```

### Webhook Dispatcher

```python
# src/services/webhook_dispatcher.py

async def dispatch_webhook(webhook_id: UUID, event_type: str, payload: dict) -> UUID:
    """Queue a webhook delivery."""
    pass

def sign_payload(payload: dict, secret: str) -> str:
    """Generate HMAC-SHA256 signature."""
    import hmac
    import hashlib
    import json
    message = json.dumps(payload, sort_keys=True).encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

async def send_webhook(delivery_id: UUID) -> bool:
    """Send HTTP POST with retry logic."""
    pass

# Headers to include:
# X-Webhook-Signature: sha256=<signature>
# X-Webhook-Event: drift_high
# X-Webhook-Delivery-ID: <uuid>
```

### Integration Points

- Modify `src/api/routes.py:evaluate()` to check thresholds after evaluation
- If threshold exceeded, dispatch webhook asynchronously (fire-and-forget)
- Store delivery record for audit/retry

### Retry Logic

- Max 3 retries with exponential backoff: 1min, 5min, 30min
- Mark delivery as failed after 3 retries
- Optional: Use Temporal workflow for durable delivery

### Files to Create/Modify

```
New files:
├── src/api/webhook_routes.py       # Webhook CRUD endpoints
├── src/services/webhook_dispatcher.py  # Dispatch + signing logic
└── tests/unit/test_webhooks.py     # Unit tests

Modified files:
├── src/models.py                   # Add Webhook, WebhookDelivery models
├── src/api/main.py                 # Register webhook_routes
├── src/api/routes.py               # Trigger webhooks in evaluate()
└── migrations/versions/xxx_webhooks.py  # Alembic migration
```

### Verification

```bash
# Create webhook
curl -X POST /v1/webhooks -H "X-API-Key: ..." -d '{
  "url": "https://example.com/webhook",
  "events": ["drift_high", "reliability_low"]
}'

# Test webhook
curl -X POST /v1/webhooks/{id}/test -H "X-API-Key: ..."

# Trigger via evaluation with high drift
curl -X POST /v1/evaluate -d '{ ... high drift scenario ... }'

# Check delivery
curl /v1/webhooks/{id}/deliveries
```

---

## Phase 4: Prophet Predictive Drift

**Goal:** Use time-series forecasting to predict expected drift and alert on anomalies.

### Dependencies

```toml
# pyproject.toml
"prophet>=1.1.0",
```

### Database Schema

```sql
CREATE TABLE drift_history (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    template_id UUID NOT NULL REFERENCES templates(id),
    drift_score FLOAT NOT NULL,
    reliability_score FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_drift_history_lookup
    ON drift_history(tenant_id, template_id, created_at);
```

### Implementation

```
Files to create:
├── src/services/drift_forecaster.py
├── src/workflows/drift_training.py (daily batch)
└── tests/unit/test_drift_forecaster.py

Files to modify:
├── src/services/drift_detector.py (use forecasted baseline)
├── src/api/routes.py (store drift history)
```

### Algorithm

```python
# src/services/drift_forecaster.py

from prophet import Prophet
import pandas as pd

class DriftForecaster:
    def __init__(self, template_id: UUID):
        self.template_id = template_id
        self.model: Prophet | None = None

    async def train(self, history: list[dict]) -> None:
        """Train Prophet model on historical drift data."""
        df = pd.DataFrame(history)
        df = df.rename(columns={"created_at": "ds", "drift_score": "y"})

        self.model = Prophet(
            changepoint_prior_scale=0.05,
            seasonality_mode="multiplicative"
        )
        self.model.fit(df)

    def predict(self, days: int = 7) -> pd.DataFrame:
        """Predict expected drift for next N days."""
        future = self.model.make_future_dataframe(periods=days)
        return self.model.predict(future)

    def is_anomaly(self, actual_drift: float, date: datetime) -> bool:
        """Check if actual drift exceeds prediction + 2 sigma."""
        forecast = self.predict(1)
        predicted = forecast[forecast["ds"] == date]["yhat"].values[0]
        upper = forecast[forecast["ds"] == date]["yhat_upper"].values[0]
        return actual_drift > upper
```

### Training Schedule

- Train Prophet model per template (daily batch job)
- Predict expected drift for next 7 days
- Alert when actual drift exceeds prediction + 2 sigma
- Fallback to z-score for new templates (< 30 days data)

---

## Phase 5: Thompson Sampling for Extractor Selection

**Goal:** Learn optimal extractor per template using multi-armed bandit approach.

### Database Schema

```sql
CREATE TABLE extractor_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    template_id UUID NOT NULL REFERENCES templates(id),
    extractor_vendor VARCHAR(100) NOT NULL,
    extractor_model VARCHAR(100) NOT NULL,
    success_count INT DEFAULT 0,
    failure_count INT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, template_id, extractor_vendor, extractor_model)
);
```

### Implementation

```python
# src/services/thompson_sampler.py

import numpy as np
from scipy.stats import beta

class ThompsonSampler:
    """Multi-armed bandit for extractor selection using Thompson Sampling."""

    def __init__(self, alpha_prior: float = 1.0, beta_prior: float = 1.0):
        self.alpha_prior = alpha_prior
        self.beta_prior = beta_prior

    def sample(self, extractors: list[dict]) -> dict:
        """Sample from posterior to select best extractor."""
        samples = []
        for ext in extractors:
            alpha = self.alpha_prior + ext["success_count"]
            beta_param = self.beta_prior + ext["failure_count"]
            sample = beta.rvs(alpha, beta_param)
            samples.append((sample, ext))

        # Return extractor with highest sampled value
        return max(samples, key=lambda x: x[0])[1]

    def update(self, extractor_id: UUID, success: bool) -> None:
        """Update counts based on extraction outcome."""
        pass

    def get_recommendation(self, template_id: UUID) -> str:
        """Get recommended extractor for template."""
        pass
```

### Feedback Endpoint

```python
# Add to src/api/routes.py

@router.post("/v1/evaluations/{evaluation_id}/feedback")
async def submit_feedback(
    evaluation_id: UUID,
    feedback: FeedbackRequest,
    tenant: CurrentTenant,
) -> dict:
    """Submit extraction outcome feedback for learning."""
    # FeedbackRequest schema:
    # {
    #     "success": true,
    #     "fields_correct": 15,
    #     "fields_total": 16
    # }
    pass
```

### Files to Create/Modify

```
Files to create:
├── src/services/thompson_sampler.py
└── tests/unit/test_thompson_sampler.py

Files to modify:
├── src/api/routes.py (add feedback endpoint)
├── src/services/reliability_scorer.py (use sampled performance)
```

---

## Phase 6: Dashboard Backend

**Goal:** Provide analytics API for visualization dashboard.

### New Endpoints

```python
# src/api/dashboard_routes.py

@router.get("/v1/dashboard/overview")
async def get_overview(tenant: CurrentTenant) -> OverviewResponse:
    """Summary stats: total evaluations, avg drift, template count."""
    pass

@router.get("/v1/dashboard/templates")
async def get_template_performance(tenant: CurrentTenant) -> list[TemplateStats]:
    """Template performance: evaluations, avg drift, reliability by template."""
    pass

@router.get("/v1/dashboard/drift-trends")
async def get_drift_trends(
    tenant: CurrentTenant,
    template_id: UUID | None = None,
    days: int = 30,
) -> list[DriftDataPoint]:
    """Time-series drift data for charting."""
    pass

@router.get("/v1/dashboard/extractors")
async def get_extractor_comparison(tenant: CurrentTenant) -> list[ExtractorStats]:
    """Extractor comparison: reliability, usage by vendor/model."""
    pass

@router.get("/v1/dashboard/alerts")
async def get_recent_alerts(
    tenant: CurrentTenant,
    limit: int = 50,
) -> list[AlertEvent]:
    """Recent drift alerts and anomalies."""
    pass
```

### Aggregation Tables

```sql
-- Materialized view or table (updated daily via batch job)
CREATE TABLE evaluation_daily_stats (
    date DATE NOT NULL,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    template_id UUID REFERENCES templates(id),
    decision VARCHAR(20) NOT NULL,
    count INT NOT NULL,
    avg_drift FLOAT,
    avg_reliability FLOAT,
    PRIMARY KEY (date, tenant_id, template_id, decision)
);

-- Index for efficient dashboard queries
CREATE INDEX idx_daily_stats_tenant_date
    ON evaluation_daily_stats(tenant_id, date DESC);
```

### Response Schemas

```python
# Add to src/models.py

class OverviewResponse(SQLModel):
    total_evaluations: int
    evaluations_today: int
    avg_drift_score: float
    avg_reliability_score: float
    template_count: int
    alert_count: int

class TemplateStats(SQLModel):
    template_id: UUID
    template_name: str
    evaluation_count: int
    avg_drift: float
    avg_reliability: float
    last_evaluation: datetime

class DriftDataPoint(SQLModel):
    date: datetime
    drift_score: float
    reliability_score: float
    evaluation_count: int

class ExtractorStats(SQLModel):
    vendor: str
    model: str
    evaluation_count: int
    avg_reliability: float
    success_rate: float

class AlertEvent(SQLModel):
    id: UUID
    event_type: str
    template_id: UUID | None
    drift_score: float | None
    created_at: datetime
    resolved: bool
```

---

## Security Hardening (Deferred)

**Short-term items to revisit:**

- [ ] Implement audit log retention policy (90 days)
- [ ] Add admin IP whitelisting option
- [ ] Separate Temporal database from application
- [ ] Add request signing for webhooks
- [ ] Configure TLS certificates

---

## When to Implement

Revisit these phases when:

1. **Phase 3 (Webhooks)**: First paying customer requests real-time alerts
2. **Phase 4 (Prophet)**: 10+ customers with 30+ days of drift history
3. **Phase 5 (Thompson)**: Customers using multiple extractors per template
4. **Phase 6 (Dashboard)**: Demand for visual analytics (could be third-party like Metabase initially)

---

## Alternative Approaches

### Instead of Building Dashboard Backend

- Use Metabase/Superset connected directly to PostgreSQL
- Expose raw metrics via Prometheus + Grafana
- Build simple charts in frontend using existing API data

### Instead of Prophet

- Continue with z-score based detection (simpler, works well)
- Use simple moving average with confidence bands
- Alert on percentage change from 7-day average

### Instead of Thompson Sampling

- Manual extractor selection per template (current)
- Simple A/B testing with fixed exploration rate
- Weighted average based on historical success rate
