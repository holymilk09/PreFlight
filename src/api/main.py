"""Document Extraction Control Plane - FastAPI Application."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.db import async_session_maker, close_db, init_db
from src.models import AuditAction, AuditLog
from src.security import generate_request_id, hash_api_key
from src.services.rate_limiter import check_rate_limit, close_redis_client, get_redis_client

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan handler for startup/shutdown."""
    # Startup
    await init_db()
    await get_redis_client()  # Initialize Redis connection
    yield
    # Shutdown
    await close_redis_client()
    await close_db()


# Create FastAPI application
app = FastAPI(
    title="Document Extraction Control Plane",
    description="Metadata-only governance for enterprise document extraction pipelines",
    version="0.1.0",
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
    lifespan=lifespan,
)


# -----------------------------------------------------------------------------
# Middleware
# -----------------------------------------------------------------------------


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next: Any) -> Response:
    """Add security headers to all responses."""
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"

    # HSTS hint (actual enforcement should be at load balancer/proxy level)
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    return response


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Any) -> Response:
    """Add request ID for tracing."""
    # Use client-provided ID or generate one
    request_id = request.headers.get("X-Request-ID") or generate_request_id()

    # Store in request state for access in route handlers
    request.state.request_id = request_id

    response = await call_next(request)

    # Include in response for client tracing
    response.headers["X-Request-ID"] = request_id

    return response


def _get_client_ip(request: Request) -> str:
    """Extract client IP, handling proxies securely.

    Checks X-Forwarded-For header but only trusts the rightmost IP
    (closest to our infrastructure) to prevent spoofing.
    """
    # If behind a trusted proxy, use X-Forwarded-For
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the rightmost IP (added by our trusted proxy)
        # This prevents client spoofing via X-Forwarded-For header
        ips = [ip.strip() for ip in forwarded_for.split(",")]
        if ips:
            return ips[-1]

    # Fallback to direct connection IP
    return request.client.host if request.client else "unknown"


async def _log_rate_limit_exceeded(
    identifier: str,
    client_ip: str,
    path: str,
    method: str,
    limit: int,
) -> None:
    """Log rate limit violation asynchronously (fire-and-forget)."""
    try:
        async with async_session_maker() as session:
            audit_entry = AuditLog(
                action=AuditAction.RATE_LIMIT_EXCEEDED,
                details={
                    "identifier": identifier[:50],
                    "path": path,
                    "method": method,
                    "limit": limit,
                },
                ip_address=client_ip,
            )
            session.add(audit_entry)
            await session.commit()
    except Exception:
        # Don't let audit logging failure affect the response
        logger.warning("audit_log_failed", action="rate_limit_exceeded")


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next: Any) -> Response:
    """Apply rate limiting based on API key or IP address.

    - Authenticated requests: Use per-API-key limit from database
    - Unauthenticated requests: Use IP-based limit from config
    - Skip rate limiting for health endpoints
    """
    # Skip rate limiting for health endpoints
    if request.url.path in ("/health", "/"):
        return await call_next(request)

    # Get client identifier and limit
    api_key = request.headers.get("X-API-Key")
    client_ip = _get_client_ip(request)

    if api_key and api_key.startswith("cp_") and len(api_key) == 35:
        # Authenticated request - use full API key hash as identifier
        identifier = f"key:{hash_api_key(api_key)}"
        limit = settings.rate_limit_per_minute
    else:
        # Unauthenticated request - use IP address
        identifier = f"ip:{client_ip}"
        limit = settings.rate_limit_unauthenticated

    # Check rate limit
    try:
        result = await check_rate_limit(identifier, limit)
    except (ConnectionError, TimeoutError, OSError) as e:
        # Redis connection issues - fail open but log
        logger.warning(
            "rate_limit_redis_unavailable",
            identifier=identifier[:30],
            error=str(e),
        )
        return await call_next(request)

    # Add rate limit headers
    if result.allowed:
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_after_seconds)
        return response
    else:
        # Rate limit exceeded - log asynchronously (don't block response)
        asyncio.create_task(
            _log_rate_limit_exceeded(
                identifier=identifier,
                client_ip=client_ip,
                path=str(request.url.path),
                method=request.method,
                limit=limit,
            )
        )

        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded. Please retry later.",
                "retry_after": result.reset_after_seconds,
            },
            headers={
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(result.reset_after_seconds),
                "Retry-After": str(result.reset_after_seconds),
            },
        )


# CORS middleware - only add if origins are configured
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )


# -----------------------------------------------------------------------------
# Exception Handlers
# -----------------------------------------------------------------------------


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions without leaking details."""
    logger.exception(
        "unhandled_exception",
        request_id=getattr(request.state, "request_id", None),
        path=str(request.url.path),
        method=request.method,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# -----------------------------------------------------------------------------
# Health Endpoints (Public)
# -----------------------------------------------------------------------------


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint for load balancers.

    This endpoint is public and does not require authentication.
    Returns a simple status indicating the service is running.
    """
    return {"status": "healthy"}


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Root endpoint with service information."""
    return {
        "service": "Document Extraction Control Plane",
        "version": "0.1.0",
        "docs": "/docs" if settings.enable_docs else "disabled",
    }


# -----------------------------------------------------------------------------
# Import Routes
# -----------------------------------------------------------------------------

# Import routes after app is created to avoid circular imports
from src.api.routes import router as api_router  # noqa: E402

app.include_router(api_router, prefix="/v1")


# -----------------------------------------------------------------------------
# Development Server
# -----------------------------------------------------------------------------


def run() -> None:
    """Run the API server (development only)."""
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    run()
