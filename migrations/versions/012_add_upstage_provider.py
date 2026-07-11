"""Register Upstage Document Parse as a known extractor provider.

Revision ID: 012_add_upstage_provider
Revises: 011_evaluation_feedback
Create Date: 2026-07-08

Upstage launched Studio (agentic document processing) with a bundled
monitoring dashboard — but it only watches Upstage's own stack. PreFlight's
wedge is neutral, cross-vendor scoring, so Upstage is one more extractor to
support, not a competitor. Adding it as a known provider means:
- the unknown-provider reliability penalty (reliability_scorer) does not
  wrongly fire for Upstage users;
- /v1/analytics/extractors (the cross-vendor benchmarking surface) gets a
  first-class Upstage row.

Calibration multipliers are neutral (1.0/1.0): honest placeholders with no
measured basis yet — they should be tuned from real evaluation data, not
guessed. Idempotent: ON CONFLICT (vendor) DO NOTHING.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "012_add_upstage_provider"
down_revision: Union[str, None] = "011_evaluation_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO extractor_providers
            (id, vendor, display_name, confidence_multiplier, drift_sensitivity,
             supported_element_types, typical_latency_ms, is_active, is_known,
             created_at, updated_at)
        VALUES
            (gen_random_uuid(), 'upstage', 'Upstage Document Parse', 1.0, 1.0,
             '["paragraph", "table", "figure", "chart", "header", "footer", "caption", "equation", "heading1", "list", "index", "footnote"]',
             700, true, true, NOW(), NOW())
        ON CONFLICT (vendor) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM extractor_providers WHERE vendor = 'upstage'")
