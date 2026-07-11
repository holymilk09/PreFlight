"""Encrypt existing webhook signing secrets at rest.

Revision ID: 008_encrypt_webhook_secrets
Revises: 007_backfill_key_scopes
Create Date: 2026-06-10

Phase A security hardening encrypts WebhookEndpoint.secret at rest (Fernet, see
src/security.encrypt_secret). New rows are written encrypted by the application;
this migration encrypts any pre-existing plaintext rows in place. It is
idempotent: rows already carrying the ``enc:v1:`` prefix are skipped. The
encryption key is derived from jwt_secret (or webhook_enc_key if set), which is
present in the environment when migrations run.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from src.security import _WEBHOOK_ENC_PREFIX, decrypt_secret, encrypt_secret

# revision identifiers, used by Alembic.
revision: str = "008_encrypt_webhook_secrets"
down_revision: Union[str, None] = "007_backfill_key_scopes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Encrypted ciphertext is longer than the original 64-char plaintext, so
    # widen the column before re-encrypting existing rows.
    op.alter_column(
        "webhook_endpoints",
        "secret",
        type_=sa.String(length=512),
        existing_type=sa.String(length=128),
        existing_nullable=False,
    )

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, secret FROM webhook_endpoints")).fetchall()
    for row_id, secret in rows:
        if secret and not secret.startswith(_WEBHOOK_ENC_PREFIX):
            conn.execute(
                sa.text("UPDATE webhook_endpoints SET secret = :s WHERE id = :i"),
                {"s": encrypt_secret(secret), "i": row_id},
            )


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, secret FROM webhook_endpoints")).fetchall()
    for row_id, secret in rows:
        if secret and secret.startswith(_WEBHOOK_ENC_PREFIX):
            conn.execute(
                sa.text("UPDATE webhook_endpoints SET secret = :s WHERE id = :i"),
                {"s": decrypt_secret(secret), "i": row_id},
            )
    op.alter_column(
        "webhook_endpoints",
        "secret",
        type_=sa.String(length=128),
        existing_type=sa.String(length=512),
        existing_nullable=False,
    )
