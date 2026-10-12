"""Safe support refusal history; no business backfill."""
from alembic import op
from backend.features.participant_support.security_schema import SCHEMA_SQL

revision = '0098_participant_support_denials'
down_revision = '0097_participant_support_access'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    op.execute('LOCK TABLE participant_support_denials IN ACCESS EXCLUSIVE MODE')
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM participant_support_denials) THEN RAISE EXCEPTION 'Preserve support refusal history'; END IF; END $$")
    op.execute('DROP TABLE participant_support_denials; DROP FUNCTION participant_support_denial_guard()')
