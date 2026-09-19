"""Customer responsibility and manager invitations, independent of buyer employment."""
from alembic import op
revision = '0038_supplier_customer_team'
down_revision = '0037_supplier_shipment_batches'
branch_labels = None
depends_on = None
SCHEMA_SQL = '''
ALTER TABLE users ADD COLUMN supplier_team_epoch BIGINT NOT NULL DEFAULT 0;
CREATE FUNCTION advance_supplier_team_epoch() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF COALESCE(OLD.active,TRUE) IS DISTINCT FROM COALESCE(NEW.active,TRUE) OR OLD.role IS DISTINCT FROM NEW.role THEN
        NEW.supplier_team_epoch := OLD.supplier_team_epoch + 1;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER supplier_team_epoch_change BEFORE UPDATE OF active,role ON users
FOR EACH ROW EXECUTE FUNCTION advance_supplier_team_epoch();
CREATE TABLE supplier_customer_assignments (
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    company_id INTEGER NOT NULL REFERENCES companies(id),
    member_id BIGINT,
    version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(supplier_id,company_id),
    FOREIGN KEY(member_id,supplier_id) REFERENCES supplier_team_members(id,supplier_id)
);
CREATE INDEX supplier_customer_assignments_member_idx ON supplier_customer_assignments(member_id,supplier_id);
CREATE TABLE supplier_team_invites (
    invite_id INTEGER PRIMARY KEY REFERENCES invite_codes(id),
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    issuer_user_epoch BIGINT NOT NULL,
    issuer_member_id BIGINT REFERENCES supplier_team_members(id),
    issuer_member_version INTEGER,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX supplier_team_invites_supplier_idx ON supplier_team_invites(supplier_id,invite_id);
CREATE TABLE supplier_team_operations (
    id BIGSERIAL PRIMARY KEY,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    actor_id INTEGER NOT NULL REFERENCES users(id),
    request_id UUID NOT NULL,
    payload_hash TEXT NOT NULL,
    action TEXT NOT NULL,
    details JSONB NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(supplier_id,request_id)
);
'''

def upgrade():
    op.execute(SCHEMA_SQL)

def downgrade():
    op.execute('LOCK TABLE supplier_customer_assignments,supplier_team_invites,supplier_team_operations IN ACCESS EXCLUSIVE MODE')
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM supplier_customer_assignments) OR EXISTS(SELECT 1 FROM supplier_team_invites) OR EXISTS(SELECT 1 FROM supplier_team_operations) THEN RAISE EXCEPTION 'Cannot discard supplier customer/team history'; END IF; END $$")
    op.execute('DROP TABLE supplier_team_operations,supplier_team_invites,supplier_customer_assignments')
    op.execute('DROP TRIGGER supplier_team_epoch_change ON users; DROP FUNCTION advance_supplier_team_epoch(); ALTER TABLE users DROP COLUMN supplier_team_epoch')
