"""Empty correction plans; retain business records and accepted consent history."""
from alembic import op
from backend.features.participant_support.correction_schema import SCHEMA_SQL

revision = '0099_supplier_corrections'
down_revision = '0098_participant_support_denials'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    op.execute('LOCK TABLE supplier_connection_correction_plans IN ACCESS EXCLUSIVE MODE')
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM supplier_connection_correction_plans) THEN RAISE EXCEPTION 'Preserve correction history'; END IF; END $$")
    op.execute('DROP TABLE supplier_connection_correction_plans; DROP FUNCTION supplier_connection_correction_guard()')
