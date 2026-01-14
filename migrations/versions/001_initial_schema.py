"""Initial schema with Row-Level Security.

Revision ID: 001_initial
Revises:
Create Date: 2024-01-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types first
    op.execute("CREATE TYPE templatestatus AS ENUM ('ACTIVE', 'DEPRECATED', 'REVIEW')")
    op.execute("CREATE TYPE decision AS ENUM ('MATCH', 'REVIEW', 'NEW', 'REJECT')")

    # Create tenants table
    op.create_table(
        "tenants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("settings", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("scopes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("rate_limit", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])

    # Create templates table
    op.create_table(
        "templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("template_id", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("structural_features", postgresql.JSONB(), nullable=False),
        sa.Column("baseline_reliability", sa.Float(), nullable=False, server_default="0.85"),
        sa.Column("correction_rules", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", postgresql.ENUM('ACTIVE', 'DEPRECATED', 'REVIEW', name='templatestatus', create_type=False), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "template_id", "version", name="uq_template_version"),
    )
    op.create_index("ix_templates_tenant_id", "templates", ["tenant_id"])
    op.create_index("ix_templates_fingerprint", "templates", ["fingerprint"])

    # Create evaluations table
    op.create_table(
        "evaluations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.Column("document_hash", sa.String(length=64), nullable=False),
        sa.Column("template_id", sa.UUID(), nullable=True),
        sa.Column("decision", postgresql.ENUM('MATCH', 'REVIEW', 'NEW', 'REJECT', name='decision', create_type=False), nullable=False),
        sa.Column("match_confidence", sa.Float(), nullable=True),
        sa.Column("drift_score", sa.Float(), nullable=True),
        sa.Column("reliability_score", sa.Float(), nullable=True),
        sa.Column("correction_rules", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("extractor_vendor", sa.String(length=100), nullable=True),
        sa.Column("extractor_model", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluations_tenant_id", "evaluations", ["tenant_id"])
    op.create_index("ix_evaluations_correlation_id", "evaluations", ["correlation_id"])
    op.create_index("ix_evaluations_created_at", "evaluations", ["created_at"])

    # Create audit_log table (NO RLS - admin access only)
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("request_id", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_tenant_id", "audit_log", ["tenant_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])

    # Enable Row-Level Security on tenant-scoped tables
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE templates ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE evaluations ENABLE ROW LEVEL SECURITY")

    # Create RLS policies
    # Tenants can only see themselves
    op.execute("""
        CREATE POLICY tenant_isolation_tenants ON tenants
            FOR ALL
            USING (id = current_setting('app.tenant_id', true)::uuid)
    """)

    # API keys are scoped to tenant
    op.execute("""
        CREATE POLICY tenant_isolation_api_keys ON api_keys
            FOR ALL
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)

    # Templates are scoped to tenant
    op.execute("""
        CREATE POLICY tenant_isolation_templates ON templates
            FOR ALL
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)

    # Evaluations are scoped to tenant
    op.execute("""
        CREATE POLICY tenant_isolation_evaluations ON evaluations
            FOR ALL
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)

    # Note: audit_log has NO RLS - it's only accessible via admin connections


def downgrade() -> None:
    # Drop RLS policies first
    op.execute("DROP POLICY IF EXISTS tenant_isolation_tenants ON tenants")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_api_keys ON api_keys")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_templates ON templates")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_evaluations ON evaluations")

    # Disable RLS
    op.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE api_keys DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE templates DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE evaluations DISABLE ROW LEVEL SECURITY")

    # Drop tables in reverse order
    op.drop_table("audit_log")
    op.drop_table("evaluations")
    op.drop_table("templates")
    op.drop_table("api_keys")
    op.drop_table("tenants")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS decision")
    op.execute("DROP TYPE IF EXISTS templatestatus")
