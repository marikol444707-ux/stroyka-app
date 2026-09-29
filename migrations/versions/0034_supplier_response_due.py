"""Persist response deadlines for newly dispatched supplier quotes."""
from alembic import op
revision = '0034_supplier_response_due'
down_revision = '0033_supply_claim_cases'
branch_labels = None
depends_on = None

def upgrade():
    op.execute('ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS response_due_at TIMESTAMPTZ')

def downgrade():
    op.execute('LOCK TABLE supplier_offers IN ACCESS EXCLUSIVE MODE')
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM supplier_offers WHERE response_due_at IS NOT NULL) THEN
        RAISE EXCEPTION 'Cannot discard recorded response deadlines'; END IF; END $$""")
    op.execute('ALTER TABLE supplier_offers DROP COLUMN response_due_at')
