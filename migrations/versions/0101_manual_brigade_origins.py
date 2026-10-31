"""Record new manual contract origins without changing historical contracts."""
from alembic import op
from backend.features.contractor_identity.manual_schema import SCHEMA_SQL, DOWNGRADE_SQL

revision = '0101_manual_brigade_origins'
down_revision = '0100_packaging_history_guard'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    op.execute(DOWNGRADE_SQL)
