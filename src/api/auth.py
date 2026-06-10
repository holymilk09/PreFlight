"""API key authentication for the Control Plane API."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import async_session_maker
from src.models import APIKey, AuditAction, Tenant
from src.security import hash_api_key

# API key header scheme
api_key_header = APIKeyHeader(
    name="X-API-Key",
    description="API key for authentication. Format: cp_<hex>",
    auto_error=False,
)


class AuthenticatedTenant:
    """Represents an authenticated tenant from API key validation."""

    def __init__(
        self,
        tenant_id: UUID,
        tenant_name: str,
        api_key_id: UUID,
        api_key_name: str | None,
        scopes: list[str],
        rate_limit: int,
    ):
        self.tenant_id = tenant_id
        self.tenant_name = tenant_name
        self.api_key_id = api_key_id
        self.api_key_name = api_key_name
        self.scopes = scopes
        self.rate_limit = rate_limit

    def has_scope(self, scope: str) -> bool:
        """Check if the API key has a specific scope."""
        return scope in self.scopes or "*" in self.scopes


async def validate_api_key(
    request: Request,
    api_key: Annotated[str | None, Depends(api_key_header)],
) -> AuthenticatedTenant:
    """Validate API key and return authenticated tenant.

    This dependency:
    1. Extracts API key from X-API-Key header
    2. Validates format (must start with cp_)
    3. Looks up key hash in database
    4. Verifies key is not revoked
    5. Updates last_used_at timestamp
    6. Returns AuthenticatedTenant with tenant context

    Raises:
        HTTPException 401: If key is missing, invalid, or revoked.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Validate format
    if not api_key.startswith("cp_") or len(api_key) != 35:  # cp_ + 32 hex chars
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Hash the key
    key_hash = hash_api_key(api_key)
    key_prefix = api_key[:8]

    # Look up in database
    async with async_session_maker() as session:
        # Query for matching key with tenant info
        stmt = (
            select(APIKey, Tenant)
            .join(Tenant, APIKey.tenant_id == Tenant.id)
            .where(APIKey.key_hash == key_hash)
            .where(APIKey.key_prefix == key_prefix)
        )
        result = await session.execute(stmt)
        row = result.first()

        if not row:
            # Log failed auth attempt
            await _log_failed_auth(session, request, key_prefix)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key.",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        api_key_record, tenant = row

        # Check if revoked
        if api_key_record.revoked_at is not None:
            await _log_failed_auth(session, request, key_prefix, "revoked")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has been revoked.",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        # Update last_used_at (fire and forget, don't block request)
        update_stmt = (
            update(APIKey)
            .where(APIKey.id == api_key_record.id)
            .values(last_used_at=datetime.utcnow())
        )
        await session.execute(update_stmt)
        await session.commit()

        return AuthenticatedTenant(
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            api_key_id=api_key_record.id,
            api_key_name=api_key_record.name,
            scopes=api_key_record.scopes or [],
            rate_limit=api_key_record.rate_limit,
        )


async def _log_failed_auth(
    session: AsyncSession,
    request: Request,
    key_prefix: str,
    reason: str = "invalid",
) -> None:
    """Log failed authentication attempt to audit log.

    This is a security measure to detect brute force or credential stuffing.
    """
    from src.models import AuditLog

    client_ip = request.client.host if request.client else None
    request_id = request.headers.get("X-Request-ID")

    audit_entry = AuditLog(
        action=AuditAction.AUTH_FAILED,
        details={
            "key_prefix": key_prefix,
            "reason": reason,
            "path": str(request.url.path),
            "method": request.method,
        },
        ip_address=client_ip,
        request_id=UUID(request_id) if request_id else None,
    )

    session.add(audit_entry)
    await session.commit()


# Type alias for dependency injection (authentication only, no scope check)
CurrentTenant = Annotated[AuthenticatedTenant, Depends(validate_api_key)]


# -----------------------------------------------------------------------------
# Scope enforcement
# -----------------------------------------------------------------------------

# Scope taxonomy. A key holding "*" satisfies every scope (see has_scope).
SCOPE_EVALUATE = "evaluate"  # submit metadata for evaluation
SCOPE_READ = "read"  # read evaluations, templates, alerts, analytics, status
SCOPE_MANAGE_TEMPLATES = "manage_templates"  # create/update/deprecate templates
SCOPE_MANAGE_ALERTS = "manage_alerts"  # manage alert rules and webhook endpoints
SCOPE_ADMIN = "admin"  # tenant/key administration (enforced in admin_routes)

# Sensible least-privilege default applied to newly created keys when the
# caller does not specify scopes (a typical API client needs to evaluate + read).
DEFAULT_KEY_SCOPES = [SCOPE_EVALUATE, SCOPE_READ]


def require_scope(scope: str) -> Callable[..., Awaitable[AuthenticatedTenant]]:
    """Build a dependency that authenticates the key AND requires ``scope``.

    Existing keys are backfilled with the "*" wildcard (migration 007), so this
    is backwards compatible; new keys are granted least-privilege scopes.
    """

    async def _require_scope(
        tenant: Annotated[AuthenticatedTenant, Depends(validate_api_key)],
    ) -> AuthenticatedTenant:
        if not tenant.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This operation requires the '{scope}' scope.",
            )
        return tenant

    return _require_scope


# Per-capability dependency aliases used by the route modules.
EvaluateTenant = Annotated[AuthenticatedTenant, Depends(require_scope(SCOPE_EVALUATE))]
ReadTenant = Annotated[AuthenticatedTenant, Depends(require_scope(SCOPE_READ))]
ManageTemplatesTenant = Annotated[
    AuthenticatedTenant, Depends(require_scope(SCOPE_MANAGE_TEMPLATES))
]
ManageAlertsTenant = Annotated[AuthenticatedTenant, Depends(require_scope(SCOPE_MANAGE_ALERTS))]
