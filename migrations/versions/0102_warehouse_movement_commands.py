"""Durable company-scoped legacy warehouse movement retries.

Prepared only; follows the unified receipt evidence migration 0101.
Neither migration has been applied by this task.
"""
from alembic import op
from backend.features.warehouse_movements.idempotency import SCHEMA_SQL

revision = '0102_movement_commands'
down_revision = '0101_receipt_originals'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    # Command history prevents duplicate stock writes and cannot safely be erased.
    raise RuntimeError('Retain warehouse movement command history; use a forward migration.')
