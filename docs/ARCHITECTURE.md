# System Architecture

## Overview

The Document Extraction Control Plane is a metadata-only governance system that sits between customer extraction pipelines and their results databases. We receive structural metadata about documents and return governance decisions—never touching actual document content.

## Architecture Diagram

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

## Component Descriptions

### API Gateway Layer
- **Kong/Envoy**: Rate limiting, JWT validation, tenant routing, request/response logging

### Decision Engine Core
- **Template Matching**: LSH + tree edit distance to identify document templates from structural fingerprints
- **Drift Detection**: CUSUM charts + PELT changepoint detection for extraction behavior changes
- **Reliability Scoring**: Predicts extraction accuracy based on historical performance and drift
- **Correction Governance**: Deterministic post-processing rules (sum validation, date normalization, etc.)

### Extended Capabilities
- **Extractor Arbitration**: Thompson Sampling bandit for optimal extractor selection
- **Cost-Aware Routing**: Pareto-optimal routing based on cost/reliability/latency profiles
- **Anomaly Detection**: Isolation Forest (fast) + VAE (precise) for fraud and quality issues
- **Predictive Drift**: Prophet forecasting + PELT for proactive drift alerts
- **Cross-Customer Benchmarks**: Differential privacy aggregates for industry comparison
- **Audit Certificates**: Merkle tree proofs + RFC 3161 timestamps for compliance
- **Schema Evolution**: Confluent-style compatibility checking for template changes
- **Human Review**: Skill-based routing with SLA management
- **Correction Feedback**: Outlier-resistant learning from human corrections
- **Seasonality Analysis**: MSTL decomposition for capacity planning

### Data Stores
- **PostgreSQL**: Event-sourced decision store with row-level security per tenant
- **TimescaleDB**: Time-series metrics (drift scores, reliability trends, latencies)
- **Trillian**: Merkle tree append-only audit log (tamper-proof)
- **Redis**: Thompson Sampling parameters, session cache, materialized views

## Data Flow

### Evaluation Request Flow
1. Customer sends `EvaluateRequest` with layout fingerprint + structural features
2. API Gateway validates JWT, extracts tenant_id, applies rate limits
3. Temporal workflow orchestrates decision pipeline:
   - Anomaly detection (reject fraud early)
   - Template matching (LSH lookup → tree edit distance refinement)
   - Drift computation (compare to baseline)
   - Reliability scoring (historical + drift penalty)
   - Correction rule selection
   - Extractor recommendation
4. Audit certificate generated (Merkle proof + timestamp)
5. `EvaluateResponse` returned with decision, scores, rules, and certificate

### Event Sourcing
All decisions are stored as immutable events:
- `DocumentSubmitted` → `LayoutAnalyzed` → `TemplateMatched` → `DriftDetected` → ...
- Events enable full replay, audit trails, and debugging
- PostgreSQL with JSONB payload for flexible event schemas

### Human Review Flow
1. Decision engine returns `REVIEW` decision (confidence < 0.85)
2. `ReviewRequested` event triggers Temporal workflow
3. Skill-based routing assigns reviewer
4. Workflow waits for `human_review_completed` signal
5. Final decision recorded, certificate updated

## Multi-Tenancy

- Row-Level Security (RLS) in PostgreSQL isolates tenant data
- Tenant ID extracted from JWT and propagated through all queries
- Redis keys namespaced by tenant
- Kafka topics partitioned by tenant for ordered processing

## Deployment Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  API Pods   │  │  Worker     │  │  Temporal Server    │  │
│  │  (FastAPI)  │  │  Pods       │  │  (Managed/Self)     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Managed Data Services                       ││
│  │  PostgreSQL | TimescaleDB | Redis | Kafka | Trillian    ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```
