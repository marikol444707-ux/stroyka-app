"""Empty, owner-addressed buyer connection requests; no ownership backfill."""
from alembic import op
from backend.features.participant_support.connection_schema import SCHEMA_SQL

revision = '0095_supplier_buyer_connections'
down_revision = '0094_participant_access_support'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    op.execute('LOCK TABLE supplier_buyer_connection_requests IN ACCESS EXCLUSIVE MODE')
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM supplier_buyer_connection_requests) THEN
        RAISE EXCEPTION 'Connection history exists: disable the feature and preserve records';
      END IF;
    END $$""")
    op.execute('DROP TABLE supplier_buyer_connection_requests; DROP FUNCTION supplier_buyer_connection_guard()')
    op.execute('DROP TRIGGER supplier_participant_owner_change ON suppliers; DROP FUNCTION supplier_participant_owner_epoch(); ALTER TABLE suppliers DROP COLUMN participant_owner_epoch')
