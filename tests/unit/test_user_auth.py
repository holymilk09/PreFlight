"""Tests for user authentication routes."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid_extensions import uuid7
from datetime import datetime

from src.security import TokenData


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_missing_credentials_raises_401(self):
        """Should raise 401 when no credentials provided."""
        from src.api.user_auth import get_current_user
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=None)

        assert exc_info.value.status_code == 401
        assert "Missing authentication token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        """Should raise 401 when token is invalid."""
        from src.api.user_auth import get_current_user
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid_token"
        )

        with patch("src.api.user_auth.decode_access_token", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials=mock_credentials)

            assert exc_info.value.status_code == 401
            assert "Invalid or expired token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_token_returns_token_data(self):
        """Should return token data when token is valid."""
        from src.api.user_auth import get_current_user
        from fastapi.security import HTTPAuthorizationCredentials

        user_id = uuid7()
        tenant_id = uuid7()
        expected_token_data = TokenData(
            user_id=user_id,
            tenant_id=tenant_id,
            email="test@example.com",
            role="admin",
            exp=datetime.utcnow(),
        )

        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_token"
        )

        with patch("src.api.user_auth.decode_access_token", return_value=expected_token_data):
            result = await get_current_user(credentials=mock_credentials)

            assert result == expected_token_data


class TestSignup:
    """Tests for POST /auth/signup endpoint."""

    @pytest.mark.asyncio
    async def test_signup_creates_user_and_tenant(self):
        """Should create new user and tenant on signup."""
        from src.api.user_auth import signup
        from src.models import SignupRequest

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing user
        mock_session.execute.return_value = mock_result

        body = SignupRequest(
            email="newuser@example.com",
            password="securepassword123"
        )

        with (
            patch("src.api.user_auth.async_session_maker") as mock_session_maker,
            patch("src.api.user_auth.log_audit_event", new_callable=AsyncMock),
            patch("src.api.user_auth.create_access_token", return_value="test_token"),
            patch("src.api.user_auth.hash_password", return_value="hashed_pw"),
        ):
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            response = await signup(request=mock_request, body=body)

            assert response.access_token == "test_token"
            assert response.token_type == "bearer"
            assert mock_session.add.call_count == 2  # Tenant + User
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_signup_rejects_duplicate_email(self):
        """Should return 409 when email already exists."""
        from src.api.user_auth import signup
        from src.models import SignupRequest, User
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        # Mock existing user
        existing_user = MagicMock(spec=User)
        existing_user.email = "existing@example.com"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_session.execute.return_value = mock_result

        body = SignupRequest(
            email="existing@example.com",
            password="password123"
        )

        with patch("src.api.user_auth.async_session_maker") as mock_session_maker:
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            with pytest.raises(HTTPException) as exc_info:
                await signup(request=mock_request, body=body)

            assert exc_info.value.status_code == 409
            assert "Email already registered" in exc_info.value.detail


class TestLogin:
    """Tests for POST /auth/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_user_not_found(self):
        """Should return 401 when user not found."""
        from src.api.user_auth import login
        from src.models import LoginRequest
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None  # No user found
        mock_session.execute.return_value = mock_result

        body = LoginRequest(
            email="nonexistent@example.com",
            password="password123"
        )

        with (
            patch("src.api.user_auth.async_session_maker") as mock_session_maker,
            patch("src.api.user_auth.log_audit_event", new_callable=AsyncMock),
        ):
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            with pytest.raises(HTTPException) as exc_info:
                await login(request=mock_request, body=body)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_inactive_user(self):
        """Should return 401 when user is inactive."""
        from src.api.user_auth import login
        from src.models import LoginRequest
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_user = MagicMock()
        mock_user.is_active = False
        mock_tenant = MagicMock()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (mock_user, mock_tenant)
        mock_session.execute.return_value = mock_result

        body = LoginRequest(
            email="inactive@example.com",
            password="password123"
        )

        with patch("src.api.user_auth.async_session_maker") as mock_session_maker:
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            with pytest.raises(HTTPException) as exc_info:
                await login(request=mock_request, body=body)

            assert exc_info.value.status_code == 401
            assert "Account is disabled" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_login_wrong_password(self):
        """Should return 401 when password is wrong."""
        from src.api.user_auth import login
        from src.models import LoginRequest
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.password_hash = "hashed"
        mock_user.id = uuid7()
        mock_tenant = MagicMock()
        mock_tenant.id = uuid7()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (mock_user, mock_tenant)
        mock_session.execute.return_value = mock_result

        body = LoginRequest(
            email="user@example.com",
            password="wrongpassword"
        )

        with (
            patch("src.api.user_auth.async_session_maker") as mock_session_maker,
            patch("src.api.user_auth.verify_password", return_value=False),
            patch("src.api.user_auth.log_audit_event", new_callable=AsyncMock),
        ):
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            with pytest.raises(HTTPException) as exc_info:
                await login(request=mock_request, body=body)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_success(self):
        """Should return token on successful login."""
        from src.api.user_auth import login
        from src.models import LoginRequest

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.password_hash = "hashed"
        mock_user.id = uuid7()
        mock_user.email = "user@example.com"
        mock_user.role = "user"
        mock_tenant = MagicMock()
        mock_tenant.id = uuid7()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (mock_user, mock_tenant)
        mock_session.execute.return_value = mock_result

        body = LoginRequest(
            email="user@example.com",
            password="correctpassword"
        )

        with (
            patch("src.api.user_auth.async_session_maker") as mock_session_maker,
            patch("src.api.user_auth.verify_password", return_value=True),
            patch("src.api.user_auth.log_audit_event", new_callable=AsyncMock),
            patch("src.api.user_auth.create_access_token", return_value="test_token"),
        ):
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            response = await login(request=mock_request, body=body)

            assert response.access_token == "test_token"
            assert response.token_type == "bearer"


class TestGetMe:
    """Tests for GET /auth/me endpoint."""

    @pytest.mark.asyncio
    async def test_get_me_user_not_found(self):
        """Should return 404 when user not found."""
        from src.api.user_auth import get_me
        from fastapi import HTTPException

        current_user = TokenData(
            user_id=uuid7(),
            tenant_id=uuid7(),
            email="test@example.com",
            role="user",
            exp=datetime.utcnow(),
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("src.api.user_auth.async_session_maker") as mock_session_maker:
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            with pytest.raises(HTTPException) as exc_info:
                await get_me(current_user=current_user)

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_me_success(self):
        """Should return user info when found."""
        from src.api.user_auth import get_me

        user_id = uuid7()
        tenant_id = uuid7()
        current_user = TokenData(
            user_id=user_id,
            tenant_id=tenant_id,
            email="test@example.com",
            role="user",
            exp=datetime.utcnow(),
        )

        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.email = "test@example.com"
        mock_user.role = "user"
        mock_user.created_at = datetime.utcnow()
        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.name = "Test Tenant"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (mock_user, mock_tenant)
        mock_session.execute.return_value = mock_result

        with patch("src.api.user_auth.async_session_maker") as mock_session_maker:
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            response = await get_me(current_user=current_user)

            assert response.email == "test@example.com"
            assert response.role == "user"


class TestLogout:
    """Tests for POST /auth/logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_logs_event(self):
        """Should log audit event on logout."""
        from src.api.user_auth import logout

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        current_user = TokenData(
            user_id=uuid7(),
            tenant_id=uuid7(),
            email="test@example.com",
            role="user",
            exp=datetime.utcnow(),
        )

        with patch("src.api.user_auth.log_audit_event", new_callable=AsyncMock) as mock_log:
            result = await logout(request=mock_request, current_user=current_user)

            assert result is None
            mock_log.assert_called_once()


class TestRefreshToken:
    """Tests for POST /auth/refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_returns_new_token(self):
        """Should return new token on refresh."""
        from src.api.user_auth import refresh_token

        current_user = TokenData(
            user_id=uuid7(),
            tenant_id=uuid7(),
            email="test@example.com",
            role="user",
            exp=datetime.utcnow(),
        )

        with patch("src.api.user_auth.create_access_token", return_value="new_token"):
            response = await refresh_token(current_user=current_user)

            assert response.access_token == "new_token"
            assert response.token_type == "bearer"


class TestChangePassword:
    """Tests for POST /auth/change-password endpoint."""

    @pytest.mark.asyncio
    async def test_change_password_user_not_found(self):
        """Should return 404 when user not found."""
        from src.api.user_auth import change_password, PasswordChangeRequest
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        current_user = TokenData(
            user_id=uuid7(),
            tenant_id=uuid7(),
            email="test@example.com",
            role="user",
            exp=datetime.utcnow(),
        )

        body = PasswordChangeRequest(
            current_password="oldpassword",
            new_password="newpassword123"
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("src.api.user_auth.async_session_maker") as mock_session_maker:
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            with pytest.raises(HTTPException) as exc_info:
                await change_password(
                    request=mock_request,
                    body=body,
                    current_user=current_user
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_change_password_wrong_current_password(self):
        """Should return 401 when current password is wrong."""
        from src.api.user_auth import change_password, PasswordChangeRequest
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        current_user = TokenData(
            user_id=uuid7(),
            tenant_id=uuid7(),
            email="test@example.com",
            role="user",
            exp=datetime.utcnow(),
        )

        body = PasswordChangeRequest(
            current_password="wrongpassword",
            new_password="newpassword123"
        )

        mock_user = MagicMock()
        mock_user.password_hash = "hashed"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        with (
            patch("src.api.user_auth.async_session_maker") as mock_session_maker,
            patch("src.api.user_auth.verify_password", return_value=False),
            patch("src.api.user_auth.log_audit_event", new_callable=AsyncMock),
        ):
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            with pytest.raises(HTTPException) as exc_info:
                await change_password(
                    request=mock_request,
                    body=body,
                    current_user=current_user
                )

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_change_password_success(self):
        """Should update password on success."""
        from src.api.user_auth import change_password, PasswordChangeRequest

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        current_user = TokenData(
            user_id=uuid7(),
            tenant_id=uuid7(),
            email="test@example.com",
            role="user",
            exp=datetime.utcnow(),
        )

        body = PasswordChangeRequest(
            current_password="correctpassword",
            new_password="newpassword123"
        )

        mock_user = MagicMock()
        mock_user.password_hash = "hashed"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        with (
            patch("src.api.user_auth.async_session_maker") as mock_session_maker,
            patch("src.api.user_auth.verify_password", return_value=True),
            patch("src.api.user_auth.hash_password", return_value="new_hashed"),
            patch("src.api.user_auth.log_audit_event", new_callable=AsyncMock),
        ):
            mock_session_maker.return_value.__aenter__.return_value = mock_session

            result = await change_password(
                request=mock_request,
                body=body,
                current_user=current_user
            )

            assert result is None
            assert mock_user.password_hash == "new_hashed"
            mock_session.commit.assert_called_once()
