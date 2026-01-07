"""FastAPI dependencies for database sessions and tenant context."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import AuthenticatedTenant, CurrentTenant
from src.db import async_session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session without tenant context.

    Use get_tenant_db for tenant-scoped operations with RLS.
    This is for admin/system operations only.
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_tenant_db(
    tenant: CurrentTenant,
) -> AsyncGenerator[AsyncSession, None]:
    """Get a database session with tenant context for RLS.

    This sets the app.tenant_id session variable that RLS policies use
    to filter rows to the current tenant only.

    Must be used with an authenticated request (CurrentTenant dependency).
    """
    async with async_session_maker() as session:
        try:
            # Set tenant context for RLS policies
            await session.execute(
                text("SET LOCAL app.tenant_id = :tenant_id"),
                {"tenant_id": str(tenant.tenant_id)},
            )
            yield session
        finally:
            await session.close()


async def get_request_context(
    request: Request,
    tenant: CurrentTenant,
) -> dict:
    """Get request context for audit logging and tracing.

    Returns common context fields for logging and auditing.
    """
    return {
        "tenant_id": str(tenant.tenant_id),
        "tenant_name": tenant.tenant_name,
        "api_key_id": str(tenant.api_key_id),
        "request_id": request.headers.get("X-Request-ID"),
        "client_ip": request.client.host if request.client else None,
        "path": str(request.url.path),
        "method": request.method,
    }


# Type aliases for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
TenantDbSession = Annotated[AsyncSession, Depends(get_tenant_db)]
RequestContext = Annotated[dict, Depends(get_request_context)]
