# Document Extraction Control Plane

Metadata-only governance for enterprise document extraction pipelines.

## What We Do

We govern document extraction systems **without touching documents**:

| We Receive | We Never See |
|------------|--------------|
| Layout fingerprints | Document images/PDFs |
| Structural features | Extracted text |
| Bounding box coordinates | Field values |
| Extractor metadata | PII/PHI |
| Confidence scores | Any content |

| We Return |
|-----------|
| Template identity |
| Drift risk scores |
| Reliability scores |
| Correction rules |
| Audit certificates |

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Make

### Setup

```bash
# Clone and setup
git clone <repo>
cd control-plane

# Initial setup (creates venv, installs deps, copies .env)
make setup

# IMPORTANT: Generate secure secrets
# Edit .env and replace all GENERATE_* values with:
openssl rand -hex 32

# Start infrastructure
make up

# Run database migrations
make migrate

# Start API server
make dev
```

### Verify Installation

```bash
# Health check (no auth required)
curl http://127.0.0.1:8000/health

# Should return: {"status":"healthy"}
```

## API Overview

All endpoints except `/health` require authentication via `X-API-Key` header.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (public) |
| `/v1/status` | GET | Detailed status (auth required) |
| `/v1/evaluate` | POST | Evaluate document metadata |
| `/v1/templates` | GET | List templates |
| `/v1/templates` | POST | Register template |
| `/v1/templates/{id}` | GET | Get template details |

### Example: Evaluate Document

```bash
curl -X POST http://127.0.0.1:8000/v1/evaluate \
  -H "X-API-Key: cp_your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "layout_fingerprint": "a1b2c3d4e5f6...",
    "structural_features": {
      "element_count": 45,
      "table_count": 2,
      "text_block_count": 20,
      "image_count": 1,
      "page_count": 1,
      "text_density": 0.65,
      "layout_complexity": 0.4,
      "column_count": 1,
      "has_header": true,
      "has_footer": true,
      "bounding_boxes": []
    },
    "extractor_metadata": {
      "vendor": "nvidia",
      "model": "nemotron-parse",
      "version": "1.2",
      "confidence": 0.92,
      "latency_ms": 450
    },
    "client_doc_hash": "sha256_of_document...",
    "client_correlation_id": "order-12345",
    "pipeline_id": "invoices-prod"
  }'
```

## Development

```bash
# Run tests
make test

# Run linting
make lint

# Format code
make format

# View logs
make logs

# Open DB shell
make db-shell

# Open Redis CLI
make redis-cli
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      CUSTOMER ENVIRONMENT                    │
│   Documents → Local Extraction → Results Database            │
│                       │ Metadata Only                        │
└───────────────────────┼─────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                       CONTROL PLANE                          │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐  │
│   │                   FastAPI + Security                  │  │
│   │  • API Key Auth (SHA256 hashed)                      │  │
│   │  • Row-Level Security (tenant isolation)             │  │
│   │  • Security Headers                                  │  │
│   │  • Audit Logging                                     │  │
│   └──────────────────────────────────────────────────────┘  │
│                            │                                 │
│   ┌──────────────────────────────────────────────────────┐  │
│   │                   Decision Engine                     │  │
│   │  • Template Matching (cosine similarity)             │  │
│   │  • Drift Detection (z-score)                         │  │
│   │  • Reliability Scoring (weighted average)            │  │
│   │  • Correction Rules (deterministic)                  │  │
│   └──────────────────────────────────────────────────────┘  │
│                            │                                 │
│   ┌──────────────────────────────────────────────────────┐  │
│   │                   Data Stores                         │  │
│   │  PostgreSQL (RLS) │ Redis (Cache) │ Temporal (Flows) │  │
│   └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Security

This system is designed for B2B enterprise use with security as a priority:

- **API Key Authentication**: Keys stored as SHA256 hashes, never plaintext
- **Multi-Tenant Isolation**: PostgreSQL Row-Level Security policies
- **Audit Logging**: All sensitive operations logged
- **Security Headers**: XSS protection, frame denial, content-type enforcement
- **Input Validation**: Strict Pydantic models with constraints
- **Secrets Management**: Validated on startup, no placeholder values allowed

## Configuration

All configuration via environment variables (see `.env.example`):

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `POSTGRES_PASSWORD` | PostgreSQL password | Yes |
| `REDIS_PASSWORD` | Redis password | Yes |
| `JWT_SECRET` | JWT signing secret | Yes |
| `API_KEY_SALT` | Salt for API key hashing | Yes |
| `ALLOWED_ORIGINS` | CORS allowed origins | No |
| `ENABLE_DOCS` | Enable /docs endpoint | No |
| `LOG_LEVEL` | Logging level | No |

## License

Proprietary
