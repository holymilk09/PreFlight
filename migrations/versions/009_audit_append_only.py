"""Make audit_log append-only via a BEFORE UPDATE OR DELETE trigger.

Revision ID: 009_audit_append_only
Revises: 008_encrypt_webhook_secrets
Create Date: 2026-06-10

Phase A hardening (item 4). The audit_log table was mutable, so a compromised
admin could alter or delete forensic records. A row-level trigger now rejects
any UPDATE or DELETE for every role, making the table tamper-evident (defensible
evidence for SR 26-2 / NAIC style requirements). INSERT, TRUNCATE and DROP are
unaffected. The same trigger is attached to create_all in src/models.py so the
test schema matches.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_audit_append_only"
down_revision: Union[str, None] = "008_encrypt_webhook_secrets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_no_mutate() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only; updates and deletes are not permitted';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log")
    op.execute(
        """
        CREATE TRIGGER audit_log_append_only
            BEFORE UPDATE OR DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_no_mutate()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_no_mutate()")
