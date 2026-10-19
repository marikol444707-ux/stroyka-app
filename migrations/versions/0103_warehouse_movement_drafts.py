"""Immutable actor/company movement drafts; prepared only, not applied."""
from alembic import op
from backend.features.warehouse_movements.drafts import SCHEMA_SQL
revision = '0103_movement_pending_drafts'
down_revision = '0102_movement_commands'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    raise RuntimeError('Retain pending movement intents and history; use a forward migration.')
