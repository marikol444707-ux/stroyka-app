"""Explicit supplier team membership and assignment scope."""
from alembic import op
revision = '0035_supplier_team_policy'
down_revision = '0034_supplier_response_due'
branch_labels = None
depends_on = None


SCHEMA_SQL = '''
CREATE TABLE IF NOT EXISTS supplier_team_members (
    id BIGSERIAL PRIMARY KEY,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    role TEXT NOT NULL CHECK (role IN ('leader','manager')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version>0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (supplier_id,user_id),
    UNIQUE (id,supplier_id)
);
CREATE INDEX IF NOT EXISTS supplier_team_members_user_idx ON supplier_team_members(user_id,supplier_id);
CREATE TABLE IF NOT EXISTS supplier_offer_assignments (
    offer_id INTEGER PRIMARY KEY REFERENCES supplier_offers(id),
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    member_id BIGINT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version>0),
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (member_id,supplier_id) REFERENCES supplier_team_members(id,supplier_id)
);
'''


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    op.execute('LOCK TABLE supplier_offer_assignments,supplier_team_members IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN IF EXISTS(SELECT 1 FROM supplier_team_members)
        OR EXISTS(SELECT 1 FROM supplier_offer_assignments) THEN
        RAISE EXCEPTION 'Cannot discard recorded supplier team permissions';
        END IF; END $$''')
    op.execute('DROP TABLE supplier_offer_assignments')
    op.execute('DROP TABLE supplier_team_members')
