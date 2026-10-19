"""Persist exact issue source; no guessing/backfill of historical rows."""
from alembic import op

revision = '0104_transfer_source_stock'
down_revision = '0103_movement_pending_drafts'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS source_stock_id INT')


def downgrade():
    raise RuntimeError('Retain issue source identities; use a forward migration.')
