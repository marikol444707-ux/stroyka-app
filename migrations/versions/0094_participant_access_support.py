"""Add empty organization-owned diagnostic and support records; no backfill."""
from alembic import op
from backend.features.participant_support.schema import SCHEMA_SQL

revision = '0094_participant_access_support'
down_revision = '0093_finance_journal_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    # Never silently erase support history, including observed access failures.
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM participant_access_ticket_events)
         OR EXISTS(SELECT 1 FROM participant_access_tickets)
         OR EXISTS(SELECT 1 FROM participant_access_diagnostics) THEN
        RAISE EXCEPTION 'Support history exists: preserve tables and disable the feature';
      END IF;
    END $$""")
    op.execute('DROP TABLE participant_access_ticket_events,participant_access_tickets,participant_access_diagnostics')
    op.execute('DROP FUNCTION participant_access_history_guard()')
