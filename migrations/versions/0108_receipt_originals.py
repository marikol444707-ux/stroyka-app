"""Preserve ordered originals even when a receipt accepts zero stock."""
from alembic import op
from backend.features.warehouse_receipts.receipt_originals_schema import SCHEMA_SQL

revision = '0108_receipt_originals'
down_revision = '0107_estimate_revisions'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    # Older code ignores this nullable column. Keep evidence and its safeguards.
    pass
