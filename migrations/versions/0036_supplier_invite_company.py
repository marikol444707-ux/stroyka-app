"""Verified buyer bindings for newly issued supplier invitations."""
from alembic import op

revision = '0036_supplier_invite_company'
down_revision = '0035_supplier_team_policy'
branch_labels = None
depends_on = None

SCHEMA_SQL = '''
CREATE TABLE IF NOT EXISTS supplier_invite_companies (
    invite_id INTEGER PRIMARY KEY REFERENCES invite_codes(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    platform_account_id INTEGER NOT NULL REFERENCES platform_accounts(id),
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS supplier_invite_companies_company_idx
    ON supplier_invite_companies(company_id);
'''


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    op.execute('LOCK TABLE supplier_invite_companies IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN IF EXISTS(SELECT 1 FROM supplier_invite_companies) THEN
        RAISE EXCEPTION 'Cannot discard recorded supplier invitations'; END IF; END $$''')
    op.execute('DROP TABLE supplier_invite_companies')
