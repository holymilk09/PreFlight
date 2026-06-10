"""Integration test: the audit_log table is append-only (tamper-evident).

The append-only trigger is attached to create_all in src/models.py, so the test
schema includes it (mirroring migration 009).
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.audit import log_audit_event
from src.models import AuditAction


@pytest.mark.asyncio
class TestAuditAppendOnly:
    async def _insert_one(self, test_engine) -> None:
        sm = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        async with sm() as s:
            await log_audit_event(action=AuditAction.AUTH_FAILED, session=s)
            await s.commit()

    async def test_insert_is_allowed(self, test_engine):
        await self._insert_one(test_engine)  # must not raise

    async def test_update_is_rejected(self, test_engine):
        await self._insert_one(test_engine)
        sm = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        with pytest.raises(Exception, match="append-only"):
            async with sm() as s:
                await s.execute(text("UPDATE audit_log SET action = 'tampered'"))
                await s.commit()

    async def test_delete_is_rejected(self, test_engine):
        await self._insert_one(test_engine)
        sm = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        with pytest.raises(Exception, match="append-only"):
            async with sm() as s:
                await s.execute(text("DELETE FROM audit_log"))
                await s.commit()
