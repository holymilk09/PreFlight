"""Tests for API dependencies."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


class TestGetDbSession:
    """Tests for get_db_session dependency."""

    @pytest.mark.asyncio
    async def test_get_db_session_yields_session(self):
        """Should yield a database session."""
        from src.api.deps import get_db_session

        mock_session = AsyncMock()

        with patch("src.api.deps.async_session_maker") as mock_maker:
            mock_maker.return_value.__aenter__.return_value = mock_session
            mock_maker.return_value.__aexit__.return_value = None

            async for session in get_db_session():
                assert session == mock_session

            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_db_session_closes_on_exception(self):
        """Should close session even if exception occurs."""
        from src.api.deps import get_db_session

        mock_session = AsyncMock()
        mock_session.close = AsyncMock()

        with patch("src.api.deps.async_session_maker") as mock_maker:
            # Set up the context manager to return our mock session
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_session
            mock_cm.__aexit__.return_value = None
            mock_maker.return_value = mock_cm

            gen = get_db_session()
            session = await gen.__anext__()
            assert session == mock_session

            # Simulate exception by closing the generator
            try:
                await gen.athrow(ValueError("Test error"))
            except ValueError:
                pass

            mock_session.close.assert_called_once()


class TestGetTenantDb:
    """Tests for get_tenant_db dependency."""

    @pytest.mark.asyncio
    async def test_get_tenant_db_sets_context(self):
        """Should set tenant context for RLS."""
        from src.api.auth import AuthenticatedTenant
        from src.api.deps import get_tenant_db

        tenant_id = uuid4()
        mock_tenant = AuthenticatedTenant(
            tenant_id=tenant_id,
            tenant_name="Test Tenant",
            api_key_id=uuid4(),
            api_key_name="test-key",
            scopes=["*"],
            rate_limit=1000,
        )

        mock_session = AsyncMock()
        mock_session.close = AsyncMock()

        with patch("src.api.deps.async_session_maker") as mock_maker:
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_session
            mock_cm.__aexit__.return_value = None
            mock_maker.return_value = mock_cm

            gen = get_tenant_db(mock_tenant)
            session = await gen.__anext__()
            assert session == mock_session

            # Verify SET LOCAL was called
            mock_session.execute.assert_called_once()
            call_args = mock_session.execute.call_args
            # Get the text clause from the first positional argument
            text_clause = call_args[0][0]
            assert "SET LOCAL app.tenant_id" in str(text_clause.text)

            # Close generator properly
            await gen.aclose()

            mock_session.close.assert_called_once()


class TestGetRequestContext:
    """Tests for get_request_context dependency."""

    @pytest.mark.asyncio
    async def test_get_request_context_returns_context(self):
        """Should return request context dictionary."""
        from src.api.auth import AuthenticatedTenant
        from src.api.deps import get_request_context

        tenant_id = uuid4()
        api_key_id = uuid4()
        mock_tenant = AuthenticatedTenant(
            tenant_id=tenant_id,
            tenant_name="Test Tenant",
            api_key_id=api_key_id,
            api_key_name="test-key",
            scopes=["*"],
            rate_limit=1000,
        )

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "test-request-id"
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/v1/status"
        mock_request.method = "GET"

        context = await get_request_context(mock_request, mock_tenant)

        assert context["tenant_id"] == str(tenant_id)
        assert context["tenant_name"] == "Test Tenant"
        assert context["api_key_id"] == str(api_key_id)
        assert context["request_id"] == "test-request-id"
        assert context["client_ip"] == "127.0.0.1"
        assert context["path"] == "/v1/status"
        assert context["method"] == "GET"

    @pytest.mark.asyncio
    async def test_get_request_context_no_client(self):
        """Should handle missing client (None)."""
        from src.api.auth import AuthenticatedTenant
        from src.api.deps import get_request_context

        mock_tenant = AuthenticatedTenant(
            tenant_id=uuid4(),
            tenant_name="Test Tenant",
            api_key_id=uuid4(),
            api_key_name="test-key",
            scopes=["*"],
            rate_limit=1000,
        )

        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client = None  # No client
        mock_request.url.path = "/v1/status"
        mock_request.method = "GET"

        context = await get_request_context(mock_request, mock_tenant)

        assert context["client_ip"] is None
        assert context["request_id"] is None
