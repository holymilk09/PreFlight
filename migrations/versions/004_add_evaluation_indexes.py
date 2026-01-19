"""Add indexes for evaluation filtering columns.

Revision ID: 004_eval_indexes
Revises: 003_extractor_providers
Create Date: 2026-01-19

These indexes improve query performance for common filter operations:
- Filtering by decision (MATCH, REVIEW, NEW, REJECT)
- Filtering by reliability_score threshold
- Filtering by drift_score threshold
- Filtering by template_id for template-specific queries
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_eval_indexes"
down_revision: Union[str, None] = "003_extractor_providers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Index on decision for filtering by evaluation outcome
    op.create_index(
        "ix_evaluations_decision",
        "evaluations",
        ["decision"],
    )

    # Index on reliability_score for threshold-based queries
    op.create_index(
        "ix_evaluations_reliability_score",
        "evaluations",
        ["reliability_score"],
    )

    # Index on drift_score for threshold-based queries
    op.create_index(
        "ix_evaluations_drift_score",
        "evaluations",
        ["drift_score"],
    )

    # Index on template_id for template-specific evaluation lookups
    op.create_index(
        "ix_evaluations_template_id",
        "evaluations",
        ["template_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_evaluations_template_id", table_name="evaluations")
    op.drop_index("ix_evaluations_drift_score", table_name="evaluations")
    op.drop_index("ix_evaluations_reliability_score", table_name="evaluations")
    op.drop_index("ix_evaluations_decision", table_name="evaluations")
