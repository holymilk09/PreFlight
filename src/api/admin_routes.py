"""Admin API routes for tenant and API key management.

These endpoints require admin scope ('admin' or '*' in API key scopes).
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from src.api.auth import AuthenticatedTenant, validate_api_key
from src.audit import log_audit_event
from src.db import async_session_maker
from src.models import APIKey, AuditAction, AuditLog, Template, Tenant
from src.security import generate_api_key

router = APIRouter(prefix="/admin", tags=["Admin"])


# -----------------------------------------------------------------------------
# Admin Authorization
# -----------------------------------------------------------------------------


async def require_admin(
    tenant: Annotated[AuthenticatedTenant, Depends(validate_api_key)],
) -> AuthenticatedTenant:
    """Require admin scope for admin endpoints."""
    if not tenant.has_scope("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin scope required for this operation.",
        )
    return tenant


def check_tenant_access(admin: AuthenticatedTenant, target_tenant_id: UUID) -> None:
    """Verify admin has access to the target tenant.

    Raises 403 if admin doesn't have superadmin scope and is trying
    to access a different tenant's resources.
    """
    # Superadmin scope allows access to any tenant
    if admin.has_scope("superadmin"):
        return

    # Regular admins can only access their own tenant
    if admin.tenant_id != target_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access resources for your own tenant.",
        )


AdminTenant = Annotated[AuthenticatedTenant, Depends(require_admin)]


# -----------------------------------------------------------------------------
# Request/Response Schemas
# -----------------------------------------------------------------------------


class TenantCreate(BaseModel):
    """Request body for creating a tenant."""

    name: str = Field(min_length=1, max_length=255)
    settings: dict | None = Field(default=None)


class TenantUpdate(BaseModel):
    """Request body for updating a tenant."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    settings: dict | None = Field(default=None)


class TenantResponse(BaseModel):
    """Response body for tenant endpoints."""

    id: UUID
    name: str
    created_at: datetime
    settings: dict
    api_key_count: int = 0
    template_count: int = 0


class APIKeyCreate(BaseModel):
    """Request body for creating an API key."""

    name: str | None = Field(default=None, max_length=255)
    scopes: list[str] = Field(default_factory=list)
    rate_limit: int = Field(default=1000, ge=1, le=100000)


class APIKeyResponse(BaseModel):
    """Response body for API key endpoints (without the key itself)."""

    id: UUID
    tenant_id: UUID
    key_prefix: str
    name: str | None
    scopes: list[str]
    rate_limit: int
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    is_active: bool


class APIKeyCreateResponse(BaseModel):
    """Response body when creating an API key (includes the key once)."""

    id: UUID
    tenant_id: UUID
    key_prefix: str
    name: str | None
    scopes: list[str]
    rate_limit: int
    created_at: datetime
    api_key: str = Field(description="Full API key - only shown once!")


class APIKeyRotateResponse(BaseModel):
    """Response body when rotating an API key."""

    old_key_id: UUID
    new_key: APIKeyCreateResponse


class AuditLogResponse(BaseModel):
    """Response body for audit log entries."""

    id: int
    timestamp: datetime
    tenant_id: UUID | None
    actor_id: UUID | None
    action: str
    resource_type: str | None
    resource_id: UUID | None
    details: dict | None
    ip_address: str | None
    request_id: UUID | None


class AuditLogListResponse(BaseModel):
    """Response body for audit log list."""

    items: list[AuditLogResponse]
    total: int
    limit: int
    offset: int


# -----------------------------------------------------------------------------
# Tenant Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/tenants",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tenant",
)
async def create_tenant(
    request: Request,
    body: TenantCreate,
    admin: AdminTenant,
) -> TenantResponse:
    """Create a new tenant organization."""
    async with async_session_maker() as session:
        tenant = Tenant(
            name=body.name,
            settings=body.settings or {},
        )
        session.add(tenant)
        await session.commit()

        # Log audit event
        await log_audit_event(
            action=AuditAction.TENANT_CREATED,
            tenant_id=admin.tenant_id,
            actor_id=admin.api_key_id,
            resource_type="tenant",
            resource_id=tenant.id,
            details={"name": body.name},
            ip_address=request.client.host if request.client else None,
        )

        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            created_at=tenant.created_at,
            settings=tenant.settings,
            api_key_count=0,
            template_count=0,
        )


@router.get(
    "/tenants/{tenant_id}",
    response_model=TenantResponse,
    summary="Get tenant details",
)
async def get_tenant(
    tenant_id: UUID,
    admin: AdminTenant,
) -> TenantResponse:
    """Get details of a specific tenant."""
    check_tenant_access(admin, tenant_id)

    async with async_session_maker() as session:
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()

        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )

        # Count API keys and templates
        api_key_count = await session.scalar(
            select(func.count(APIKey.id)).where(APIKey.tenant_id == tenant_id)
        )
        template_count = await session.scalar(
            select(func.count(Template.id)).where(Template.tenant_id == tenant_id)
        )

        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            created_at=tenant.created_at,
            settings=tenant.settings,
            api_key_count=api_key_count or 0,
            template_count=template_count or 0,
        )


@router.patch(
    "/tenants/{tenant_id}",
    response_model=TenantResponse,
    summary="Update tenant",
)
async def update_tenant(
    request: Request,
    tenant_id: UUID,
    body: TenantUpdate,
    admin: AdminTenant,
) -> TenantResponse:
    """Update a tenant's details."""
    check_tenant_access(admin, tenant_id)

    async with async_session_maker() as session:
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()

        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )

        # Update fields
        if body.name is not None:
            tenant.name = body.name
        if body.settings is not None:
            tenant.settings = body.settings

        session.add(tenant)
        await session.commit()

        # Log audit event
        await log_audit_event(
            action=AuditAction.TENANT_UPDATED,
            tenant_id=admin.tenant_id,
            actor_id=admin.api_key_id,
            resource_type="tenant",
            resource_id=tenant.id,
            details={"updated_fields": body.model_dump(exclude_unset=True)},
            ip_address=request.client.host if request.client else None,
        )

        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            created_at=tenant.created_at,
            settings=tenant.settings,
            api_key_count=0,
            template_count=0,
        )


@router.delete(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tenant (soft delete)",
)
async def delete_tenant(
    request: Request,
    tenant_id: UUID,
    admin: AdminTenant,
) -> None:
    """Soft delete a tenant by revoking all API keys.

    This doesn't actually delete the tenant data, but makes it inaccessible
    by revoking all associated API keys.
    """
    check_tenant_access(admin, tenant_id)

    async with async_session_maker() as session:
        # Verify tenant exists
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()

        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )

        # Revoke all API keys for this tenant
        now = datetime.utcnow()
        api_keys_stmt = select(APIKey).where(
            APIKey.tenant_id == tenant_id,
            APIKey.revoked_at.is_(None),
        )
        api_keys_result = await session.execute(api_keys_stmt)
        api_keys = api_keys_result.scalars().all()

        for key in api_keys:
            key.revoked_at = now
            session.add(key)

        await session.commit()

        # Log audit event
        await log_audit_event(
            action=AuditAction.API_KEY_REVOKED,
            tenant_id=admin.tenant_id,
            actor_id=admin.api_key_id,
            resource_type="tenant",
            resource_id=tenant_id,
            details={"reason": "tenant_deleted", "keys_revoked": len(api_keys)},
            ip_address=request.client.host if request.client else None,
        )


# -----------------------------------------------------------------------------
# API Key Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/tenants/{tenant_id}/api-keys",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key for tenant",
)
async def create_api_key(
    request: Request,
    tenant_id: UUID,
    body: APIKeyCreate,
    admin: AdminTenant,
) -> APIKeyCreateResponse:
    """Create a new API key for a tenant.

    The full API key is returned only once in this response.
    Store it securely - it cannot be retrieved again.
    """
    check_tenant_access(admin, tenant_id)

    async with async_session_maker() as session:
        # Verify tenant exists
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()

        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )

        # Generate new API key
        key_components = generate_api_key()

        api_key = APIKey(
            tenant_id=tenant_id,
            key_hash=key_components.key_hash,
            key_prefix=key_components.key_prefix,
            name=body.name,
            scopes=body.scopes,
            rate_limit=body.rate_limit,
        )
        session.add(api_key)
        await session.commit()

        # Log audit event
        await log_audit_event(
            action=AuditAction.API_KEY_CREATED,
            tenant_id=admin.tenant_id,
            actor_id=admin.api_key_id,
            resource_type="api_key",
            resource_id=api_key.id,
            details={
                "target_tenant_id": str(tenant_id),
                "key_prefix": key_components.key_prefix,
                "name": body.name,
                "scopes": body.scopes,
            },
            ip_address=request.client.host if request.client else None,
        )

        return APIKeyCreateResponse(
            id=api_key.id,
            tenant_id=api_key.tenant_id,
            key_prefix=api_key.key_prefix,
            name=api_key.name,
            scopes=api_key.scopes,
            rate_limit=api_key.rate_limit,
            created_at=api_key.created_at,
            api_key=key_components.full_key,
        )


@router.get(
    "/tenants/{tenant_id}/api-keys",
    response_model=list[APIKeyResponse],
    summary="List API keys for tenant",
)
async def list_api_keys(
    tenant_id: UUID,
    admin: AdminTenant,
    include_revoked: bool = Query(default=False),
) -> list[APIKeyResponse]:
    """List all API keys for a tenant."""
    check_tenant_access(admin, tenant_id)

    async with async_session_maker() as session:
        stmt = select(APIKey).where(APIKey.tenant_id == tenant_id)

        if not include_revoked:
            stmt = stmt.where(APIKey.revoked_at.is_(None))

        stmt = stmt.order_by(APIKey.created_at.desc())

        result = await session.execute(stmt)
        api_keys = result.scalars().all()

        return [
            APIKeyResponse(
                id=key.id,
                tenant_id=key.tenant_id,
                key_prefix=key.key_prefix,
                name=key.name,
                scopes=key.scopes,
                rate_limit=key.rate_limit,
                created_at=key.created_at,
                last_used_at=key.last_used_at,
                revoked_at=key.revoked_at,
                is_active=key.is_active,
            )
            for key in api_keys
        ]


@router.delete(
    "/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke API key",
)
async def revoke_api_key(
    request: Request,
    key_id: UUID,
    admin: AdminTenant,
) -> None:
    """Revoke an API key."""
    async with async_session_maker() as session:
        stmt = select(APIKey).where(APIKey.id == key_id)
        result = await session.execute(stmt)
        api_key = result.scalar_one_or_none()

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found",
            )

        # Verify admin has access to this key's tenant
        check_tenant_access(admin, api_key.tenant_id)

        if api_key.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key is already revoked",
            )

        api_key.revoked_at = datetime.utcnow()
        session.add(api_key)
        await session.commit()

        # Log audit event
        await log_audit_event(
            action=AuditAction.API_KEY_REVOKED,
            tenant_id=admin.tenant_id,
            actor_id=admin.api_key_id,
            resource_type="api_key",
            resource_id=key_id,
            details={"key_prefix": api_key.key_prefix},
            ip_address=request.client.host if request.client else None,
        )


@router.post(
    "/api-keys/{key_id}/rotate",
    response_model=APIKeyRotateResponse,
    summary="Rotate API key",
)
async def rotate_api_key(
    request: Request,
    key_id: UUID,
    admin: AdminTenant,
) -> APIKeyRotateResponse:
    """Rotate an API key - creates new key and revokes old one.

    The new API key is returned only once in this response.
    """
    async with async_session_maker() as session:
        stmt = select(APIKey).where(APIKey.id == key_id)
        result = await session.execute(stmt)
        old_key = result.scalar_one_or_none()

        if not old_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found",
            )

        # Verify admin has access to this key's tenant
        check_tenant_access(admin, old_key.tenant_id)

        if old_key.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot rotate a revoked API key",
            )

        # Generate new key with same settings
        key_components = generate_api_key()

        new_key = APIKey(
            tenant_id=old_key.tenant_id,
            key_hash=key_components.key_hash,
            key_prefix=key_components.key_prefix,
            name=old_key.name,
            scopes=old_key.scopes,
            rate_limit=old_key.rate_limit,
        )
        session.add(new_key)

        # Revoke old key
        old_key.revoked_at = datetime.utcnow()
        session.add(old_key)

        await session.commit()

        # Log audit event
        await log_audit_event(
            action=AuditAction.API_KEY_ROTATED,
            tenant_id=admin.tenant_id,
            actor_id=admin.api_key_id,
            resource_type="api_key",
            resource_id=new_key.id,
            details={
                "old_key_id": str(key_id),
                "old_key_prefix": old_key.key_prefix,
                "new_key_prefix": key_components.key_prefix,
            },
            ip_address=request.client.host if request.client else None,
        )

        return APIKeyRotateResponse(
            old_key_id=key_id,
            new_key=APIKeyCreateResponse(
                id=new_key.id,
                tenant_id=new_key.tenant_id,
                key_prefix=new_key.key_prefix,
                name=new_key.name,
                scopes=new_key.scopes,
                rate_limit=new_key.rate_limit,
                created_at=new_key.created_at,
                api_key=key_components.full_key,
            ),
        )


# -----------------------------------------------------------------------------
# Audit Log Endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="Query audit logs",
)
async def list_audit_logs(
    admin: AdminTenant,
    tenant_id: UUID | None = Query(default=None),
    action: AuditAction | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> AuditLogListResponse:
    """Query audit logs with optional filters.

    Non-superadmins can only view their own tenant's logs.
    """
    # Non-superadmins can only view their own tenant's logs
    if not admin.has_scope("superadmin"):
        if tenant_id is None:
            # Default to their own tenant
            tenant_id = admin.tenant_id
        else:
            # Verify they're querying their own tenant
            check_tenant_access(admin, tenant_id)

    async with async_session_maker() as session:
        # Build query
        stmt = select(AuditLog)

        if tenant_id:
            stmt = stmt.where(AuditLog.tenant_id == tenant_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)

        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await session.scalar(count_stmt) or 0

        # Get paginated results
        stmt = stmt.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        logs = result.scalars().all()

        return AuditLogListResponse(
            items=[
                AuditLogResponse(
                    id=log.id,
                    timestamp=log.timestamp,
                    tenant_id=log.tenant_id,
                    actor_id=log.actor_id,
                    action=log.action.value,
                    resource_type=log.resource_type,
                    resource_id=log.resource_id,
                    details=log.details,
                    ip_address=log.ip_address,
                    request_id=log.request_id,
                )
                for log in logs
            ],
            total=total,
            limit=limit,
            offset=offset,
        )
