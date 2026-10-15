"""Empty immutable history merge evidence, without business backfill."""
from alembic import op
from backend.features.participant_support.merge_schema import SCHEMA_SQL

revision='0096_supplier_history_merge'
down_revision='0095_supplier_buyer_connections'
branch_labels=None
depends_on=None

def upgrade():op.execute(SCHEMA_SQL)

def downgrade():
    op.execute('LOCK TABLE supplier_history_merge_plans IN ACCESS EXCLUSIVE MODE')
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM supplier_history_merge_plans) THEN RAISE EXCEPTION 'Preserve history merge plans'; END IF; END $$")
    op.execute('DROP TABLE supplier_history_merge_plans; DROP FUNCTION supplier_history_merge_guard()')
