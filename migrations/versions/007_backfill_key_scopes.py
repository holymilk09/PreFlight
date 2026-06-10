"""Backfill API key scopes to wildcard for backwards-compatible scope enforcement.

Revision ID: 007_backfill_key_scopes
Revises: 006_analytics_index
Create Date: 2026-06-10

Phase A security hardening introduces per-endpoint API-key scope enforcement
(see src/api/auth.py require_scope). Existing keys were created before scopes
were enforced and may have an empty scope list, which would now deny every
request. Backfill any key with no scopes to the "*" wildcard so existing
integrations keep working unchanged; newly created keys get least-privilege
defaults at creation time.

Note: RLS on the `users` table was considered here but intentionally deferred.
Login looks up a user by email *before* any tenant context exists, so a blanket
`tenant_id = current_setting('app.tenant_id')` policy would hide the row from a
restricted role and break authentication. Isolating `users` needs a dedicated
system-role/login path, tracked separately.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007_backfill_key_scopes"
down_revision: Union[str, None] = "006_analytics_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Grant the wildcard scope to any pre-existing key that has none, so scope
    # enforcement is backwards compatible. JSONB comparison handles NULL/[].
    op.execute(
        """
        UPDATE api_keys
        SET scopes = '["*"]'::jsonb
        WHERE scopes IS NULL OR scopes = '[]'::jsonb
        """
    )


def downgrade() -> None:
    # Data backfill is not safely reversible (we cannot distinguish keys that
    # were originally "*" from those backfilled). No-op downgrade.
    pass
