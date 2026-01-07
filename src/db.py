"""Database connection and Row-Level Security setup."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from src.config import settings

# Create async engine with connection pooling
engine = create_async_engine(
    settings.database_url,
    poolclass=AsyncAdaptedQueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.log_level == "DEBUG",
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session without tenant context.

    Use get_tenant_session() for tenant-scoped operations.
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_tenant_session(tenant_id: UUID) -> AsyncGenerator[AsyncSession, None]:
    """Get a database session with tenant context for RLS.

    This sets the app.tenant_id session variable that RLS policies use
    to filter rows to the current tenant only.

    Args:
        tenant_id: The tenant UUID to scope the session to.

    Yields:
        AsyncSession with tenant context set.
    """
    async with async_session_maker() as session:
        try:
            # Set tenant context for RLS policies
            await session.execute(
                text("SET LOCAL app.tenant_id = :tenant_id"),
                {"tenant_id": str(tenant_id)},
            )
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database connection and verify connectivity."""
    async with engine.begin() as conn:
        # Verify connection
        await conn.execute(text("SELECT 1"))


async def close_db() -> None:
    """Close database connection pool."""
    await engine.dispose()


# SQL for creating RLS policies (run via Alembic migration)
RLS_SETUP_SQL = """
-- Enable RLS on tenant-scoped tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluations ENABLE ROW LEVEL SECURITY;

-- Create policies for tenants table (tenants can only see themselves)
CREATE POLICY tenant_isolation_tenants ON tenants
    FOR ALL
    USING (id = current_setting('app.tenant_id', true)::uuid);

-- Create policies for api_keys table
CREATE POLICY tenant_isolation_api_keys ON api_keys
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- Create policies for templates table
CREATE POLICY tenant_isolation_templates ON templates
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- Create policies for evaluations table
CREATE POLICY tenant_isolation_evaluations ON evaluations
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- Audit log has NO RLS - only accessible to admins via separate connection
-- ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY; -- intentionally not enabled
"""

RLS_DROP_SQL = """
-- Drop RLS policies (for migration rollback)
DROP POLICY IF EXISTS tenant_isolation_tenants ON tenants;
DROP POLICY IF EXISTS tenant_isolation_api_keys ON api_keys;
DROP POLICY IF EXISTS tenant_isolation_templates ON templates;
DROP POLICY IF EXISTS tenant_isolation_evaluations ON evaluations;

ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys DISABLE ROW LEVEL SECURITY;
ALTER TABLE templates DISABLE ROW LEVEL SECURITY;
ALTER TABLE evaluations DISABLE ROW LEVEL SECURITY;
"""
