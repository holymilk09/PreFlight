"""Add alerting tables (alert_rules, webhook_endpoints, alert_events) with RLS.

Revision ID: 005_alerting
Revises: 004_eval_indexes
Create Date: 2026-05-29

Phase 1 alerting engine: tenant-defined alert rules, webhook delivery
endpoints, and persisted alert events. All three tables are tenant-scoped
and protected by Row-Level Security policies keyed on app.tenant_id.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "005_alerting"
down_revision: Union[str, None] = "004_eval_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- alert_rules ---------------------------------------------------------
    op.create_table(
        "alert_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("metric", sa.String(40), nullable=False),
        sa.Column("comparator", sa.String(4), nullable=False, server_default="gt"),
        sa.Column("threshold", sa.Float, nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # --- webhook_endpoints ---------------------------------------------------
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("secret", sa.String(128), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # --- alert_events --------------------------------------------------------
    op.create_table(
        "alert_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "evaluation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluations.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "rule_id",
            UUID(as_uuid=True),
            sa.ForeignKey("alert_rules.id"),
            nullable=True,
        ),
        sa.Column("metric", sa.String(40), nullable=False),
        sa.Column("value", sa.Float, nullable=True),
        sa.Column("threshold", sa.Float, nullable=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("delivery_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("delivery_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_alert_events_created_at", "alert_events", ["created_at"])

    # --- Row-Level Security --------------------------------------------------
    op.execute("ALTER TABLE alert_rules ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE webhook_endpoints ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE alert_events ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY tenant_isolation_alert_rules ON alert_rules
            FOR ALL
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_webhook_endpoints ON webhook_endpoints
            FOR ALL
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_alert_events ON alert_events
            FOR ALL
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    # Drop policies first
    op.execute("DROP POLICY IF EXISTS tenant_isolation_alert_events ON alert_events")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_webhook_endpoints ON webhook_endpoints")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_alert_rules ON alert_rules")

    op.execute("ALTER TABLE alert_events DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE webhook_endpoints DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE alert_rules DISABLE ROW LEVEL SECURITY")

    # Drop tables (alert_events references alert_rules, so drop it first)
    op.drop_index("ix_alert_events_created_at", table_name="alert_events")
    op.drop_table("alert_events")
    op.drop_table("webhook_endpoints")
    op.drop_table("alert_rules")
