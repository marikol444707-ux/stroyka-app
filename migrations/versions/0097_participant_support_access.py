"""Bounded diagnostic authority; no conversion of legacy support sessions."""
from alembic import op
from backend.features.participant_support.capability_schema import SCHEMA_SQL

revision = '0097_participant_support_access'
down_revision = '0096_supplier_history_merge_plans'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    op.execute('LOCK TABLE participant_support_access,participant_support_access_events IN ACCESS EXCLUSIVE MODE')
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM participant_support_access) THEN RAISE EXCEPTION 'Preserve support access history'; END IF; END $$")
    op.execute('DROP TABLE participant_support_access_events; DROP TABLE participant_support_access; DROP FUNCTION participant_support_access_guard(); DROP INDEX participant_ticket_exact_owner')
