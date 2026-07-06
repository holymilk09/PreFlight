"""Add evaluation_feedback table (outcome loop for score calibration).

Revision ID: 011_evaluation_feedback
Revises: 010_user_login_lockout
Create Date: 2026-07-06

Product gap fix: the platform scored documents but never learned whether a
score was right. This table stores the reported downstream outcome per
evaluation (correct / corrected / rejected — metadata only, never content),
which calibrates reliability scores against reality and powers the ROI
analytics (/v1/analytics/calibration: errors caught vs missed).

One row per evaluation (unique constraint); resubmission updates in place.
Tenant-scoped with the same RLS policy shape as other tables.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011_evaluation_feedback"
down_revision: Union[str, None] = "010_user_login_lockout"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_feedback",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("evaluation_id", sa.UUID(), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("field_error_count", sa.Integer(), nullable=True),
        sa.Column("review_seconds", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_id", name="uq_feedback_evaluation_id"),
    )
    op.create_index("ix_evaluation_feedback_tenant_id", "evaluation_feedback", ["tenant_id"])
    op.create_index(
        "ix_feedback_tenant_created", "evaluation_feedback", ["tenant_id", "created_at"]
    )

    op.execute("ALTER TABLE evaluation_feedback ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_evaluation_feedback ON evaluation_feedback
            FOR ALL
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_evaluation_feedback ON evaluation_feedback")
    op.execute("ALTER TABLE evaluation_feedback DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_feedback_tenant_created", table_name="evaluation_feedback")
    op.drop_index("ix_evaluation_feedback_tenant_id", table_name="evaluation_feedback")
    op.drop_table("evaluation_feedback")
