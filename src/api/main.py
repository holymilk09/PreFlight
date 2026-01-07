"""Document Extraction Control Plane - FastAPI Application."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Document Extraction Control Plane",
    description="Metadata-only governance for enterprise document extraction pipelines",
    version="0.1.0",
    docs_url="/docs" if os.getenv("ENABLE_DOCS", "false").lower() == "true" else None,
    redoc_url="/redoc" if os.getenv("ENABLE_DOCS", "false").lower() == "true" else None,
)

# CORS middleware - restrict origins in production
# SECURITY: Never use "*" in production. Configure ALLOWED_ORIGINS env var.
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
_allowed_origins = [origin.strip() for origin in _allowed_origins if origin.strip()]

if _allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "Document Extraction Control Plane",
        "version": "0.1.0",
    }


def run() -> None:
    """Run the API server (development only)."""
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="127.0.0.1",  # Bind to localhost only in dev
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    run()
