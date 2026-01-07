"""Document Extraction Control Plane - FastAPI Application."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.db import close_db, init_db
from src.security import generate_request_id


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan handler for startup/shutdown."""
    # Startup
    await init_db()
    yield
    # Shutdown
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
    import structlog

    logger = structlog.get_logger()
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
