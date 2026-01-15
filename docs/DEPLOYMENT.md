# Deployment Guide

## Secrets Management

**CRITICAL**: Never commit secrets to version control.

### Development (Local)

For local development, use a `.env` file (already gitignored):

```bash
cp .env.example .env
# Edit .env with your local values
```

Generate secure secrets:
```bash
# JWT secret and API key salt
openssl rand -hex 32

# Database and Redis passwords
openssl rand -hex 16
```

### Production Deployment

**Do NOT use .env files in production.** Use environment variables directly.

#### Option 1: Platform Environment Variables (Recommended)

Most platforms (Railway, Render, Fly.io, Heroku) have built-in secrets management:

```bash
# Railway
railway variables set JWT_SECRET=<value>
railway variables set POSTGRES_PASSWORD=<value>

# Render
# Use the Render dashboard Environment section

# Fly.io
fly secrets set JWT_SECRET=<value>

# Heroku
heroku config:set JWT_SECRET=<value>
```

#### Option 2: Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: preflight-secrets
type: Opaque
stringData:
  JWT_SECRET: "your-secret-here"
  API_KEY_SALT: "your-salt-here"
  POSTGRES_PASSWORD: "your-password-here"
  REDIS_PASSWORD: "your-password-here"
```

Reference in deployment:
```yaml
envFrom:
  - secretRef:
      name: preflight-secrets
```

#### Option 3: AWS/GCP/Azure Secrets Manager

For enterprise deployments, use cloud-native secrets management:

- **AWS**: Secrets Manager or Parameter Store
- **GCP**: Secret Manager
- **Azure**: Key Vault

### Required Secrets

| Variable | Description | Generation |
|----------|-------------|------------|
| `JWT_SECRET` | JWT signing key (min 32 chars) | `openssl rand -hex 32` |
| `API_KEY_SALT` | API key hashing salt (min 32 chars) | `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | Database password | `openssl rand -hex 16` |
| `REDIS_PASSWORD` | Redis password | `openssl rand -hex 16` |

### Required Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | - | PostgreSQL connection string |
| `REDIS_URL` | - | Redis connection string |
| `API_HOST` | `0.0.0.0` | API bind address |
| `API_PORT` | `8000` | API port |

### Production Settings

```bash
# Disable API docs in production
ENABLE_DOCS=false

# Set appropriate CORS origins
ALLOWED_ORIGINS=https://app.yourdomain.com

# Configure Sentry for error tracking
SENTRY_DSN=https://key@sentry.io/project
SENTRY_ENVIRONMENT=production
```

## Docker Deployment

### Build

```bash
docker build -t preflight-api .
```

### Run with Environment Variables

```bash
docker run -d \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db" \
  -e REDIS_URL="redis://:pass@host:6379" \
  -e JWT_SECRET="$(openssl rand -hex 32)" \
  -e API_KEY_SALT="$(openssl rand -hex 32)" \
  preflight-api
```

### Docker Compose (Production)

```yaml
version: '3.8'
services:
  api:
    image: preflight-api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - JWT_SECRET=${JWT_SECRET}
      - API_KEY_SALT=${API_KEY_SALT}
    # Pass secrets from host environment, NOT .env file
```

## Health Checks

The API provides three health endpoints:

| Endpoint | Auth | Purpose | Use Case |
|----------|------|---------|----------|
| `/health` | No | Liveness probe | Is the process alive? |
| `/ready` | No | Readiness probe | Can it handle requests? (checks DB + Redis) |
| `/v1/status` | Yes | Detailed status | Monitoring dashboard |

### Kubernetes Probes

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  failureThreshold: 3
```

### Docker Health Check

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/ready || exit 1
```

### Readiness Response

When dependencies are healthy (200 OK):
```json
{
  "status": "ready",
  "services": {
    "database": {"healthy": true, "latency_ms": 1.23},
    "redis": {"healthy": true, "latency_ms": 0.45}
  }
}
```

When dependencies are down (503 Service Unavailable):
```json
{
  "status": "not_ready",
  "services": {
    "database": {"healthy": false},
    "redis": {"healthy": true, "latency_ms": 0.45}
  }
}
```

## Scaling Considerations

- **Stateless API**: Can scale horizontally
- **Database**: Single PostgreSQL instance (consider read replicas for high load)
- **Redis**: Used for rate limiting and caching (can cluster for HA)
- **Recommended**: Start with 2 replicas, scale based on P95 latency

## Monitoring

### Prometheus Metrics

Scrape `/metrics` endpoint:
```yaml
scrape_configs:
  - job_name: 'preflight'
    static_configs:
      - targets: ['preflight-api:8000']
```

### Key Metrics

- `request_count_total` - Request volume by endpoint/status
- `request_latency_seconds` - Request latency histogram
- `evaluation_latency_seconds` - Evaluation processing time
- `rate_limit_hits_total` - Rate limit violations

## Troubleshooting

### API Won't Start

1. Check required environment variables are set
2. Verify database is reachable
3. Check logs: `docker logs <container>`

### Connection Errors

1. Verify `DATABASE_URL` format: `postgresql+asyncpg://user:pass@host:port/db`
2. Ensure database allows connections from API host
3. Check Redis URL format: `redis://:password@host:port`

### Rate Limiting Issues

1. Check Redis connectivity
2. Rate limiter fails-open if Redis unavailable (logged)
3. Review `RATE_LIMIT_PER_MINUTE` setting
