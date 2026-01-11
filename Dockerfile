# -----------------------------------------------------------------------------
# Stage 1: Builder
# Installs dependencies and builds the application
# -----------------------------------------------------------------------------
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install pip and build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel hatch

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini ./

# Build wheel
RUN pip wheel --no-cache-dir --wheel-dir /wheels -e .

# Install dependencies to a specific directory for copying later
RUN pip install --no-cache-dir --target=/install -e .

# -----------------------------------------------------------------------------
# Stage 2: Runtime
# Minimal image with only runtime dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim as runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    # Default port
    PORT=8000

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 preflight \
    && useradd --uid 1000 --gid preflight --shell /bin/bash --create-home preflight

# Copy installed packages from builder
COPY --from=builder /install /usr/local/lib/python3.11/site-packages/

# Copy application code
COPY --chown=preflight:preflight src/ ./src/
COPY --chown=preflight:preflight migrations/ ./migrations/
COPY --chown=preflight:preflight alembic.ini ./

# Switch to non-root user
USER preflight

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE ${PORT}

# Run the application with uvicorn
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
