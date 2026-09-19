"""Append-only supplier claim discussions and versioned director decisions."""
from alembic import op

revision = '0033_supply_claim_cases'
down_revision = '0032_supply_templates'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''ALTER TABLE supply_claims
        ADD COLUMN version BIGINT NOT NULL DEFAULT 1 CHECK(version>0),
        ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now()''')
    op.execute('CREATE UNIQUE INDEX supply_claim_delivery_identity ON supply_claims(id,delivery_id)')
    op.execute('CREATE UNIQUE INDEX supply_claim_delivery_owner ON supply_deliveries(id,company_id)')
    op.execute('''CREATE TABLE supply_claim_events (
        id BIGSERIAL PRIMARY KEY, claim_id INTEGER NOT NULL, delivery_id INTEGER NOT NULL,
        company_id INTEGER NOT NULL REFERENCES companies(id), operation_id BIGINT NOT NULL UNIQUE,
        actor_id INTEGER NOT NULL REFERENCES users(id), actor_name TEXT NOT NULL,
        action TEXT NOT NULL CHECK(action IN ('start','comment','reply','resolve','reopen')),
        text TEXT NOT NULL CHECK(length(trim(text)) BETWEEN 1 AND 4000),
        before_state JSONB NOT NULL, after_state JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        FOREIGN KEY(claim_id,delivery_id) REFERENCES supply_claims(id,delivery_id),
        FOREIGN KEY(delivery_id,company_id) REFERENCES supply_deliveries(id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    op.execute('CREATE INDEX supply_claim_history ON supply_claim_events(company_id,claim_id,id)')
    op.execute('''CREATE FUNCTION guard_supply_claim_case() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF TG_TABLE_NAME='supply_claim_events' OR TG_OP='DELETE' THEN
            RAISE EXCEPTION 'Claim records and history cannot be deleted or rewritten';
        END IF;
        IF (to_jsonb(NEW)-ARRAY['status','resolution','resolved_at','version','updated_at'])
            IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','resolution','resolved_at','version','updated_at'])
            OR NEW.version<>OLD.version+1 THEN
            RAISE EXCEPTION 'Claim facts, identity and version are protected';
        END IF;
        RETURN NEW;
        END $$''')
    for table in ('supply_claims', 'supply_claim_events'):
        op.execute(f'''CREATE TRIGGER {table}_guard BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_supply_claim_case()''')


def downgrade():
    op.execute('LOCK TABLE supply_claims,supply_claim_events IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN IF current_setting('transaction_isolation')<>'read committed'
        OR EXISTS(SELECT 1 FROM supply_claim_events)
        OR EXISTS(SELECT 1 FROM supply_claims WHERE version<>1) THEN
        RAISE EXCEPTION 'Cannot discard claim decisions or recorded history'; END IF; END $$''')
    op.execute('DROP TRIGGER supply_claims_guard ON supply_claims')
    op.execute('DROP TABLE supply_claim_events')
    op.execute('DROP FUNCTION guard_supply_claim_case()')
    op.execute('DROP INDEX supply_claim_delivery_identity')
    op.execute('DROP INDEX supply_claim_delivery_owner')
    op.execute('ALTER TABLE supply_claims DROP COLUMN version,DROP COLUMN updated_at')
