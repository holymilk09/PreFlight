"""User authentication routes for signup, login, and user info."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.audit import log_audit_event
from src.config import settings
from src.db import async_session_maker
from src.models import (
    AuditAction,
    AuthResponse,
    LoginRequest,
    SignupRequest,
    Tenant,
    User,
    UserResponse,
)
from src.security import (
    TokenData,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Bearer token scheme
bearer_scheme = HTTPBearer(auto_error=False)


# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> TokenData:
    """Validate bearer token and return current user data.

    Raises:
        HTTPException 401: If token is missing or invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = decode_access_token(credentials.credentials)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


CurrentUser = Annotated[TokenData, Depends(get_current_user)]


# -----------------------------------------------------------------------------
# Auth Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
async def signup(
    request: Request,
    body: SignupRequest,
) -> AuthResponse:
    """Create a new user account and tenant.

    This endpoint:
    1. Validates email is not already registered
    2. Creates a new tenant for the user
    3. Creates the user with hashed password
    4. Returns a JWT access token

    The user becomes the admin of their new tenant.
    """
    async with async_session_maker() as session:
        # Check if email already exists
        stmt = select(User).where(User.email == body.email.lower())
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        # Create tenant for new user
        tenant = Tenant(
            name=f"{body.email.split('@')[0]}'s Organization",
            settings={"plan": "free"},
        )
        session.add(tenant)
        await session.flush()  # Get tenant ID

        # Create user
        user = User(
            tenant_id=tenant.id,
            email=body.email.lower(),
            password_hash=hash_password(body.password),
            role="admin",  # First user is admin
        )
        session.add(user)
        await session.commit()

        # Log audit event
        await log_audit_event(
            action=AuditAction.USER_SIGNUP,
            tenant_id=tenant.id,
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            details={"email": user.email},
            ip_address=request.client.host if request.client else None,
        )

        # Create access token
        access_token = create_access_token(
            user_id=user.id,
            tenant_id=tenant.id,
            email=user.email,
            role=user.role,
        )

        return AuthResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.jwt_expire_minutes * 60,
        )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login with email and password",
)
async def login(
    request: Request,
    body: LoginRequest,
) -> AuthResponse:
    """Authenticate user and return access token.

    This endpoint:
    1. Validates email and password
    2. Updates last_login_at timestamp
    3. Returns a JWT access token
    """
    async with async_session_maker() as session:
        # Find user by email
        stmt = (
            select(User, Tenant)
            .join(Tenant, User.tenant_id == Tenant.id)
            .where(User.email == body.email.lower())
        )
        result = await session.execute(stmt)
        row = result.first()

        if not row:
            # Log failed attempt
            await log_audit_event(
                action=AuditAction.AUTH_FAILED,
                details={"email": body.email, "reason": "user_not_found"},
                ip_address=request.client.host if request.client else None,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        user, tenant = row

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled",
            )

        # Verify password
        if not verify_password(body.password, user.password_hash):
            await log_audit_event(
                action=AuditAction.AUTH_FAILED,
                tenant_id=tenant.id,
                actor_id=user.id,
                details={"email": body.email, "reason": "invalid_password"},
                ip_address=request.client.host if request.client else None,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Update last login
        user.last_login_at = datetime.utcnow()
        session.add(user)
        await session.commit()

        # Log successful login
        await log_audit_event(
            action=AuditAction.USER_LOGIN,
            tenant_id=tenant.id,
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            details={"email": user.email},
            ip_address=request.client.host if request.client else None,
        )

        # Create access token
        access_token = create_access_token(
            user_id=user.id,
            tenant_id=tenant.id,
            email=user.email,
            role=user.role,
        )

        return AuthResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.jwt_expire_minutes * 60,
        )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user info",
)
async def get_me(
    current_user: CurrentUser,
) -> UserResponse:
    """Get the current authenticated user's information."""
    async with async_session_maker() as session:
        # Get user with tenant
        stmt = (
            select(User, Tenant)
            .join(Tenant, User.tenant_id == Tenant.id)
            .where(User.id == current_user.user_id)
        )
        result = await session.execute(stmt)
        row = result.first()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        user, tenant = row

        return UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            created_at=user.created_at,
        )
