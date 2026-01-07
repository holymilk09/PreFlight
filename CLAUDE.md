# Document Extraction Control Plane

> **Purpose**: Metadata-only document extraction governance system for enterprise pipelines.

## Executive Summary

A **document extraction control plane** — B2B infrastructure SaaS that governs enterprise document extraction pipelines without ever touching the documents themselves.

**Core Value Proposition**: "We govern document extraction systems without touching documents."

| What We Receive | What We Never See | What We Return |
|-----------------|-------------------|----------------|
| Layout fingerprints | Document images | Template identity |
| Structural features | PDFs | Drift risk scores |
| Bounding box coordinates | Extracted text | Reliability scores |
| Element types | Field values | Correction rules |
| Extractor metadata | PII/PHI | Audit trail |
| Confidence scores | Any content | |

---

## Project Structure (MVP)

```
control-plane/
├── CLAUDE.md               # This file
├── README.md               # Setup and API docs
├── pyproject.toml          # Python dependencies
├── docker-compose.yml      # Infrastructure (3 services)
├── .env.example            # Environment template
├── Makefile                # Dev commands
├── alembic.ini             # Migration config
├── migrations/             # Database migrations
│   └── versions/           # Migration files
├── src/
│   ├── __init__.py
│   ├── config.py           # pydantic-settings configuration
│   ├── db.py               # Database + RLS setup
│   ├── models.py           # SQLModel models + Pydantic schemas
│   ├── security.py         # API key hashing, validation
│   ├── audit.py            # Audit logging
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py         # FastAPI app + security middleware
│   │   ├── routes.py       # All MVP endpoints
│   │   ├── auth.py         # API key authentication
│   │   └── deps.py         # Dependencies (DB, tenant context)
│   └── services/
│       ├── __init__.py
│       ├── template_matcher.py    # Cosine similarity matching
│       ├── drift_detector.py      # Z-score drift detection
│       ├── reliability_scorer.py  # Weighted reliability scoring
│       └── correction_rules.py    # Deterministic rule selection
├── tests/                  # Test suite
└── docs/                   # Extended documentation
```

---

## Technology Stack (MVP)

### Infrastructure (3 Services)
- **PostgreSQL 16**: Event store with Row-Level Security (multi-tenant)
- **Redis 7**: Cache, rate limiting, session state
- **Temporal**: Workflow orchestration (durable execution)

### Application
- **FastAPI**: Async API with automatic OpenAPI
- **SQLModel**: SQLAlchemy + Pydantic combined
- **pydantic-settings**: Validated configuration

### Security
- API key authentication (SHA256 hashed)
- Row-Level Security for tenant isolation
- Audit logging for all sensitive operations
- Security headers middleware

---

## Design Principles

1. **Metadata Only**: Never accept document content
2. **Tenant Isolated**: PostgreSQL RLS enforces data separation
3. **Fail Safe**: When uncertain, return REVIEW not MATCH
4. **Audit Everything**: All operations logged for compliance
5. **Simple First**: Start simple, optimize when needed

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
| Reliability score | < 0.80 | Enhanced validation |

---

## Quick Start

```bash
# Initial setup
make setup

# IMPORTANT: Generate secure secrets in .env
openssl rand -hex 32

# Start infrastructure
make up

# Run migrations
make migrate

# Start API server
make dev
```

### Common Commands

```bash
make dev        # Start API server with hot reload
make test       # Run pytest with coverage
make lint       # Run ruff + mypy
make logs       # Tail docker-compose logs
make db-shell   # Open PostgreSQL shell
make clean      # Stop containers, remove volumes
```

---

## API Overview

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Health check |
| `/v1/status` | GET | Yes | Detailed status |
| `/v1/evaluate` | POST | Yes | Evaluate document metadata |
| `/v1/templates` | GET | Yes | List templates |
| `/v1/templates` | POST | Yes | Register template |
| `/v1/templates/{id}` | GET | Yes | Get template details |

Authentication: Include `X-API-Key: cp_xxxxx` header.

---

## MVP Services

### 1. Template Matching
Cosine similarity on structural feature vectors.
- Quick fingerprint lookup for exact matches
- Vector similarity for fuzzy matching

### 2. Drift Detection
Z-score based deviation from template baseline.
- Compares current features to stored baseline
- Weighted combination of metric-specific drifts

### 3. Reliability Scoring
Weighted average of factors:
- Template baseline reliability (40%)
- Extractor confidence (35%)
- Drift penalty (25%)

### 4. Correction Rules
Deterministic rule selection:
- Template-defined rules first
- Reliability-based rules added when needed
- Enhanced validation for low reliability

---

## Security Implementation

### API Key Authentication
- Keys format: `cp_<32 hex chars>`
- Stored as SHA256(salt + key)
- Prefix stored for identification
- last_used_at tracking

### Row-Level Security
```sql
ALTER TABLE templates ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON templates
    USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

### Audit Logging
All logged:
- API key creation/rotation/revocation
- Template creation/modification
- Evaluation requests (metadata only)
- Failed authentication attempts
- Rate limit violations

---

## Future Enhancements (Not in MVP)

After MVP validation:
- LSH for O(1) template lookup
- Prophet for predictive drift
- Thompson Sampling for extractor selection
- Kafka for event streaming
- TimescaleDB for time-series metrics
- Trillian for Merkle tree audit certificates

---

## Documentation

- [README.md](README.md) - Setup and usage
- [docs/SPEC.md](docs/SPEC.md) - Full algorithm specifications
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design
- [docs/MODELS.md](docs/MODELS.md) - Data models
- [docs/API.md](docs/API.md) - API reference
