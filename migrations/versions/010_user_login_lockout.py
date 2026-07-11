"""Add per-user login lockout state to the users table.

Revision ID: 010_user_login_lockout
Revises: 009_audit_append_only
Create Date: 2026-06-11

Phase A hardening (item 5). Adds brute-force protection for dashboard logins:
``failed_login_count`` tracks consecutive failed logins and ``locked_until``,
when set in the future, blocks authentication (even with a correct password)
until it elapses. See src/api/user_auth.login and the LOGIN_MAX_FAILED_ATTEMPTS /
LOGIN_LOCKOUT_MINUTES / LOGIN_LOCKOUT_REVEAL settings.

The counter column is NOT NULL with a server default of 0 so existing rows
backfill cleanly; locked_until is nullable (NULL == not locked).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010_user_login_lockout"
down_revision: Union[str, None] = "009_audit_append_only"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column("locked_until", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")
