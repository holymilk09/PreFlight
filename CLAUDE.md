# Document Extraction Control Plane

> **Purpose**: Metadata-only document extraction governance system for enterprise pipelines.

## Executive Summary

We are building a **document extraction control plane** — a B2B infrastructure SaaS that governs enterprise document extraction pipelines without ever touching the documents themselves.

**Core Value Proposition**: "We govern document extraction systems without touching documents."

| What We Receive | What We Never See | What We Return |
|-----------------|-------------------|----------------|
| Layout fingerprints | Document images | Template identity |
| Structural features | PDFs | Drift risk scores |
| Bounding box coordinates | Extracted text | Reliability scores |
| Element types | Field values | Correction rules |
| Extractor metadata | PII/PHI | Audit certificates |
| Confidence scores | Any content | Extractor recommendations |

---

## Architecture

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
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         API Gateway / Ingress                            │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  DECISION ENGINE: Template Matching │ Drift Detection │ Reliability     │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  EXTENDED: Extractor Arbitration │ Anomaly Detection │ Audit Certs      │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  DATA: PostgreSQL (Events) │ TimescaleDB (Metrics) │ Redis │ Trillian   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed component descriptions.

---

## Technology Stack

### Infrastructure
- **Workflow**: Temporal.io (durable execution, saga pattern, human-in-the-loop)
- **Events**: Apache Kafka (event sourcing, cross-service communication)
- **Gateway**: Kong or Envoy (rate limiting, auth, routing)

### Data Stores
- **PostgreSQL**: Event store with Row-Level Security (multi-tenant)
- **TimescaleDB**: Time-series metrics (drift, reliability, latency)
- **Trillian**: Merkle tree audit log (tamper-proof, RFC 3161)
- **Redis**: Thompson Sampling params, session cache, materialized views
- **Elasticsearch**: Template and document search

### ML/Decision Engine
- **Vowpal Wabbit**: Contextual bandits for extractor selection
- **Isolation Forest + VAE**: Anomaly detection
- **Prophet + PELT**: Time-series forecasting and changepoint detection

### Languages
- **Python 3.11+**: ML, data processing, Temporal workers, FastAPI
- **Rust**: Performance-critical fingerprinting and similarity computation

---

## Design Principles

1. **Metadata Only**: Never accept document content. All inputs must be structural.
2. **Event Sourced**: Every decision is an immutable event. Full audit trail by design.
3. **Tenant Isolated**: Row-level security in PostgreSQL. No data leakage between tenants.
4. **Deterministic When Possible**: Correction rules are deterministic. ML has reproducibility seeds.
5. **Fail Safe**: When uncertain, return REVIEW not MATCH. Prefer false positives.
6. **Privacy by Design**: Differential privacy for cross-customer analytics.
7. **Composable**: Each capability is independently usable via API.

---

## Critical Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| Template match confidence | ≥ 0.85 | MATCH decision |
| Template match confidence | 0.50 - 0.85 | REVIEW decision |
| Template match confidence | < 0.50 | NEW template |
| Drift score | < 0.15 | Stable (green) |
| Drift score | 0.15 - 0.30 | Watch (yellow) |
| Drift score | 0.30 - 0.50 | Review required (orange) |
| Drift score | > 0.50 | Critical drift (red) |
| Reliability score | ≥ 0.80 | Auto-process |
| Reliability score | < 0.80 | Review required |

---

## Project Structure

```
control-plane/
├── CLAUDE.md                    # This file
├── docs/
│   ├── ARCHITECTURE.md          # System architecture details
│   ├── SPEC.md                  # Algorithm specifications (14 capabilities)
│   ├── MODELS.md                # Pydantic model definitions
│   └── API.md                   # OpenAPI endpoint reference
├── pyproject.toml               # Python dependencies
├── docker-compose.yml           # Local dev stack
├── .env.example                 # Environment template
├── Makefile                     # Dev commands
└── src/
    ├── api/                     # FastAPI routes + middleware
    │   ├── routes/              # evaluate, templates, corrections, etc.
    │   └── middleware/          # auth, tenant, rate_limit
    ├── core/                    # models, events, config
    ├── engine/                  # Decision engine components
    │   ├── template_matcher.py
    │   ├── drift_detector.py
    │   ├── reliability_scorer.py
    │   ├── anomaly_detector.py
    │   └── extractor_arbitrator.py
    ├── workflows/               # Temporal workflows + activities
    ├── audit/                   # Certificate generation, Merkle tree
    ├── analytics/               # Seasonality, benchmarks
    ├── feedback/                # Correction processing
    ├── schema/                  # Schema evolution governance
    └── infrastructure/          # Database, Redis, Kafka clients
```

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Make

### Setup

```bash
# Clone and setup
git clone <repo>
cd control-plane

# Start infrastructure (PostgreSQL, TimescaleDB, Redis, Temporal, Kafka)
make setup
make up

# Install Python dependencies
make install

# Run database migrations
make migrate

# Start the API server (development mode)
make dev

# In another terminal, start Temporal worker
make worker
```

### Common Commands

```bash
make dev        # Start API server with hot reload
make test       # Run pytest with coverage
make lint       # Run ruff + mypy
make logs       # Tail docker-compose logs
make clean      # Stop containers, remove volumes
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/controlplane
TIMESCALE_URL=postgresql://user:pass@localhost:5433/metrics
REDIS_URL=redis://localhost:6379
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=controlplane
JWT_SECRET=your-secret-key
```

---

## Capabilities (14 Total)

| # | Capability | Purpose | See |
|---|------------|---------|-----|
| 1 | Template Matching | Identify documents by structural fingerprint | [SPEC.md#1](docs/SPEC.md#1-template-matching) |
| 2 | Drift Detection | Detect extraction behavior changes over time | [SPEC.md#2](docs/SPEC.md#2-drift-detection) |
| 3 | Reliability Scoring | Predict extraction accuracy | [SPEC.md#3](docs/SPEC.md#3-reliability-scoring) |
| 4 | Correction Governance | Deterministic post-processing rules | [SPEC.md#4](docs/SPEC.md#4-correction-governance) |
| 5 | Extractor Arbitration | Thompson Sampling for extractor selection | [SPEC.md#5](docs/SPEC.md#5-extractor-arbitration) |
| 6 | Cost-Aware Routing | Pareto-optimal cost/reliability routing | [SPEC.md#6](docs/SPEC.md#6-cost-aware-routing) |
| 7 | Anomaly Detection | Fraud and quality issue detection | [SPEC.md#7](docs/SPEC.md#7-anomaly-detection) |
| 8 | Predictive Drift | Forecast drift before thresholds crossed | [SPEC.md#8](docs/SPEC.md#8-predictive-drift-alerts) |
| 9 | Cross-Customer Benchmarks | Privacy-preserving industry comparisons | [SPEC.md#9](docs/SPEC.md#9-cross-customer-benchmarking) |
| 10 | Audit Certificates | Merkle proofs + RFC 3161 timestamps | [SPEC.md#10](docs/SPEC.md#10-audit-certificates) |
| 11 | Human Review | Skill-based routing with SLA management | [SPEC.md#11](docs/SPEC.md#11-human-review-orchestration) |
| 12 | Correction Feedback | Learn from corrections safely | [SPEC.md#12](docs/SPEC.md#12-correction-feedback-loop) |
| 13 | Schema Evolution | Safe template schema changes | [SPEC.md#13](docs/SPEC.md#13-schema-evolution-governance) |
| 14 | Seasonality Analysis | Capacity planning and forecasting | [SPEC.md#14](docs/SPEC.md#14-seasonality--capacity-signals) |

---

## API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/evaluate` | POST | Main evaluation endpoint |
| `/v1/templates` | GET/POST | List/register templates |
| `/v1/templates/{id}/drift` | GET | Get drift analysis |
| `/v1/corrections` | POST | Submit correction feedback |
| `/v1/reviews/{id}` | GET/POST | Review task management |
| `/v1/certificates/{id}` | GET | Get audit certificate |
| `/v1/benchmarks` | GET | Cross-customer benchmarks |
| `/v1/extractors/recommend` | POST | Get extractor recommendation |

See [docs/API.md](docs/API.md) for full specification.

---

## Success Metrics

- **Latency**: p99 < 100ms for `/v1/evaluate`
- **Throughput**: 10,000 evaluations/second per node
- **Accuracy**: Template matching > 95% precision/recall
- **Drift Detection**: 90% of drifts detected before customer reports
- **Uptime**: 99.9% availability

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System design and data flow
- [Specifications](docs/SPEC.md) - Algorithm implementations
- [Models](docs/MODELS.md) - Pydantic data models
- [API](docs/API.md) - REST endpoint reference
