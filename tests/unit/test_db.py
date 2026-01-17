"""Tests for database connection and utilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid_extensions import uuid7


class TestGetSession:
    """Tests for get_session function."""

    @pytest.mark.asyncio
    async def test_get_session_yields_session(self):
        """Should yield a database session."""
        from src.db import get_session

        mock_session = AsyncMock()

        with patch("src.db.async_session_maker") as mock_maker:
            mock_maker.return_value.__aenter__.return_value = mock_session

            async for session in get_session():
                assert session == mock_session

            mock_session.close.assert_called_once()


class TestGetTenantSession:
    """Tests for get_tenant_session context manager."""

    @pytest.mark.asyncio
    async def test_get_tenant_session_sets_context(self):
        """Should set tenant context for RLS."""
        from sqlalchemy import text
        from src.db import get_tenant_session

        tenant_id = uuid7()
        mock_session = AsyncMock()

        with patch("src.db.async_session_maker") as mock_maker:
            mock_maker.return_value.__aenter__.return_value = mock_session

            async with get_tenant_session(tenant_id) as session:
                assert session == mock_session

            # Verify execute was called with proper SQL and params
            mock_session.execute.assert_called_once()
            call_args = mock_session.execute.call_args
            # First positional argument is the text clause
            text_clause = call_args[0][0]
            # Check that it contains the right SQL
            assert "SET LOCAL app.tenant_id" in str(text_clause)
            # Check that tenant_id was passed as parameter
            params = call_args[0][1]
            assert params["tenant_id"] == str(tenant_id)
            mock_session.close.assert_called_once()


class TestInitDb:
    """Tests for init_db function."""

    @pytest.mark.asyncio
    async def test_init_db_verifies_connection(self):
        """Should verify database connectivity."""
        from src.db import init_db

        mock_conn = AsyncMock()

        with patch("src.db.engine") as mock_engine:
            mock_engine.begin.return_value.__aenter__.return_value = mock_conn

            await init_db()

            mock_conn.execute.assert_called_once()


class TestCloseDb:
    """Tests for close_db function."""

    @pytest.mark.asyncio
    async def test_close_db_disposes_engine(self):
        """Should dispose the database engine."""
        from src.db import close_db

        with patch("src.db.engine") as mock_engine:
            mock_engine.dispose = AsyncMock()

            await close_db()

            mock_engine.dispose.assert_called_once()
