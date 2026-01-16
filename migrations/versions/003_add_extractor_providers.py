"""Add extractor_providers table and enhanced evaluation fields.

Revision ID: 003
Revises: 002_add_users_table
Create Date: 2025-01-15
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers
revision = "003_add_extractor_providers"
down_revision = "002_add_users_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create extractor_providers table
    op.create_table(
        "extractor_providers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("vendor", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("confidence_multiplier", sa.Float, nullable=False, default=1.0),
        sa.Column("drift_sensitivity", sa.Float, nullable=False, default=1.0),
        sa.Column("supported_element_types", JSONB, nullable=False, default=[]),
        sa.Column("typical_latency_ms", sa.Integer, nullable=False, default=500),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("is_known", sa.Boolean, nullable=False, default=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Seed default providers
    providers_table = sa.table(
        "extractor_providers",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("vendor", sa.String),
        sa.column("display_name", sa.String),
        sa.column("confidence_multiplier", sa.Float),
        sa.column("drift_sensitivity", sa.Float),
        sa.column("supported_element_types", JSONB),
        sa.column("typical_latency_ms", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("is_known", sa.Boolean),
    )

    op.bulk_insert(
        providers_table,
        [
            {
                "id": uuid4(),
                "vendor": "aws",
                "display_name": "AWS Textract",
                "confidence_multiplier": 1.0,
                "drift_sensitivity": 1.0,
                "supported_element_types": ["PAGE", "LINE", "WORD", "TABLE", "CELL", "KEY_VALUE_SET", "SELECTION_ELEMENT"],
                "typical_latency_ms": 450,
                "is_active": True,
                "is_known": True,
            },
            {
                "id": uuid4(),
                "vendor": "azure",
                "display_name": "Azure Document Intelligence",
                "confidence_multiplier": 0.95,
                "drift_sensitivity": 1.1,
                "supported_element_types": ["page", "paragraph", "table", "figure", "keyValuePair", "selectionMark"],
                "typical_latency_ms": 600,
                "is_active": True,
                "is_known": True,
            },
            {
                "id": uuid4(),
                "vendor": "google",
                "display_name": "Google Document AI",
                "confidence_multiplier": 1.0,
                "drift_sensitivity": 1.0,
                "supported_element_types": ["text_segment", "table", "form_field", "paragraph", "token", "block"],
                "typical_latency_ms": 550,
                "is_active": True,
                "is_known": True,
            },
            {
                "id": uuid4(),
                "vendor": "nvidia",
                "display_name": "NVIDIA Nemotron",
                "confidence_multiplier": 1.05,
                "drift_sensitivity": 0.9,
                "supported_element_types": ["text", "table", "figure", "list", "title", "paragraph", "caption"],
                "typical_latency_ms": 300,
                "is_active": True,
                "is_known": True,
            },
            {
                "id": uuid4(),
                "vendor": "abbyy",
                "display_name": "ABBYY FineReader",
                "confidence_multiplier": 1.0,
                "drift_sensitivity": 1.0,
                "supported_element_types": ["text", "table", "picture", "barcode", "separator"],
                "typical_latency_ms": 400,
                "is_active": True,
                "is_known": True,
            },
            {
                "id": uuid4(),
                "vendor": "tesseract",
                "display_name": "Tesseract OCR",
                "confidence_multiplier": 0.90,
                "drift_sensitivity": 1.2,
                "supported_element_types": ["text", "word", "line", "block"],
                "typical_latency_ms": 200,
                "is_active": True,
                "is_known": True,
            },
        ],
    )

    # Add new columns to evaluations table
    op.add_column("evaluations", sa.Column("extractor_version", sa.String(50), nullable=True))
    op.add_column("evaluations", sa.Column("extractor_confidence", sa.Float, nullable=True))
    op.add_column("evaluations", sa.Column("extractor_latency_ms", sa.Integer, nullable=True))
    op.add_column("evaluations", sa.Column("extractor_cost_usd", sa.Float, nullable=True))
    op.add_column(
        "evaluations",
        sa.Column("provider_id", UUID(as_uuid=True), sa.ForeignKey("extractor_providers.id"), nullable=True),
    )
    op.add_column("evaluations", sa.Column("validation_warnings", JSONB, nullable=False, server_default="[]"))

    # Create index on provider_id
    op.create_index("ix_evaluations_provider_id", "evaluations", ["provider_id"])


def downgrade() -> None:
    # Remove index
    op.drop_index("ix_evaluations_provider_id", table_name="evaluations")

    # Remove columns from evaluations
    op.drop_column("evaluations", "validation_warnings")
    op.drop_column("evaluations", "provider_id")
    op.drop_column("evaluations", "extractor_cost_usd")
    op.drop_column("evaluations", "extractor_latency_ms")
    op.drop_column("evaluations", "extractor_confidence")
    op.drop_column("evaluations", "extractor_version")

    # Drop extractor_providers table
    op.drop_table("extractor_providers")
