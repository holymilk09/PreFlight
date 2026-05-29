"""Add composite (tenant_id, created_at) index on evaluations for analytics.

Revision ID: 006_analytics_index
Revises: 005_alerting
Create Date: 2026-05-29

The analytics endpoints (summary/timeseries/extractors) and the /v1/evaluations
listing all filter evaluations by tenant_id (equality, via RLS) and created_at
(range / ordering). A composite index on (tenant_id, created_at) lets PostgreSQL
locate exactly the tenant's rows in the time window in one access path, instead
of scanning all of a tenant's history (or the whole window across tenants) and
filtering. Measured ~2x fewer heap blocks / lower latency on a 188k-row, 300-
tenant dataset, widening as a tenant's history grows.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_analytics_index"
down_revision: Union[str, None] = "005_alerting"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_evaluations_tenant_created",
        "evaluations",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_evaluations_tenant_created", table_name="evaluations")
