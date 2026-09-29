"""Physical returns of rejected goods and replacement shipments on one claim."""
from alembic import op

revision = '0054_supply_claim_fulfilment'
down_revision = '0053_supplier_receipt_exceptions'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE supply_claim_events DROP CONSTRAINT supply_claim_events_action_check")
    op.execute("ALTER TABLE supply_claim_events ADD CONSTRAINT supply_claim_events_action_check CHECK(action IN ('start','comment','reply','resolve','reopen','return','replace'))")
    op.execute('''CREATE TABLE supply_claim_fulfilments (
        id BIGSERIAL PRIMARY KEY,
        event_id BIGINT NOT NULL UNIQUE REFERENCES supply_claim_events(id),
        claim_id INTEGER NOT NULL REFERENCES supply_claims(id),
        company_id INTEGER NOT NULL REFERENCES companies(id),
        action TEXT NOT NULL CHECK(action IN ('return','replace')),
        quantity NUMERIC NOT NULL CHECK(quantity>0 AND quantity<10000000000 AND quantity=trunc(quantity,4)),
        replacement_delivery_id INTEGER UNIQUE REFERENCES supply_deliveries(id),
        CHECK((action='replace')=(replacement_delivery_id IS NOT NULL)),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )''')
    op.execute('CREATE INDEX supply_claim_fulfilment_owner ON supply_claim_fulfilments(company_id,claim_id)')
    op.execute('''CREATE FUNCTION validate_claim_fulfilment() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE d supply_deliveries; child supply_deliveries; budget NUMERIC; used NUMERIC;
        BEGIN
        PERFORM supplier_allocation_lock(NEW.company_id);
        SELECT delivery.* INTO d FROM supply_claims c JOIN supply_deliveries delivery ON delivery.id=c.delivery_id
            WHERE c.id=NEW.claim_id AND delivery.company_id=NEW.company_id FOR UPDATE OF c;
        IF NOT FOUND OR d.claim_id IS DISTINCT FROM NEW.claim_id OR d.received_at IS NULL
            OR NOT EXISTS(SELECT 1 FROM supply_claim_events e WHERE e.id=NEW.event_id
                AND e.claim_id=NEW.claim_id AND e.company_id=NEW.company_id AND e.action=NEW.action)
            OR NOT (EXISTS(SELECT 1 FROM supplier_receipt_exceptions e WHERE e.delivery_id=d.id AND e.company_id=NEW.company_id)
                OR EXISTS(SELECT 1 FROM supplier_receipt_line_proofs p JOIN supplier_payment_receipt_relations r
                    ON r.id=p.receipt_relation_id WHERE r.source_delivery_id=d.id AND r.company_id=NEW.company_id)) THEN
            RAISE EXCEPTION 'Claim receipt evidence is required' USING ERRCODE='23514'; END IF;
        budget:=CASE WHEN d.quality_status IN ('Брак','Несоответствие') THEN d.received_quantity ELSE 0 END;
        IF NEW.action='replace' THEN budget:=budget+d.shortage_quantity; END IF;
        SELECT COALESCE(sum(quantity),0) INTO used FROM supply_claim_fulfilments
            WHERE claim_id=NEW.claim_id AND action=NEW.action;
        IF budget IS NULL OR NEW.quantity+used>budget THEN
            RAISE EXCEPTION 'Claim quantity exceeded' USING ERRCODE='23514'; END IF;
        IF NEW.action='replace' THEN
            SELECT * INTO child FROM supply_deliveries WHERE id=NEW.replacement_delivery_id;
            IF NOT FOUND OR child.id=d.id OR child.status IS DISTINCT FROM 'В пути' OR child.received_at IS NOT NULL
                OR child.shipped_quantity IS DISTINCT FROM NEW.quantity
                OR (child.company_id,child.request_id,child.offer_id,child.supplier_id,child.project,
                    child.work_package,child.material_name,child.unit,child.price_per_unit,
                    child.contract_version_id,child.source_supplier_invoice_id) IS DISTINCT FROM
                   (d.company_id,d.request_id,d.offer_id,d.supplier_id,d.project,d.work_package,
                    d.material_name,d.unit,d.price_per_unit,d.contract_version_id,d.source_supplier_invoice_id) THEN
                RAISE EXCEPTION 'Replacement source mismatch' USING ERRCODE='23514'; END IF;
        END IF;
        RETURN NEW;
        END $$''')
    op.execute('CREATE TRIGGER claim_fulfilment_validate BEFORE INSERT ON supply_claim_fulfilments FOR EACH ROW EXECUTE FUNCTION validate_claim_fulfilment()')
    for operations, level in (('UPDATE OR DELETE','ROW'), ('TRUNCATE','STATEMENT')):
        suffix = 'immutable' if level=='ROW' else 'no_truncate'
        op.execute(f'CREATE TRIGGER claim_fulfilment_{suffix} BEFORE {operations} ON supply_claim_fulfilments FOR EACH {level} EXECUTE FUNCTION supplier_payment_immutable()')
    op.execute('''CREATE FUNCTION freeze_replacement_identity() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF EXISTS(SELECT 1 FROM supply_claim_fulfilments WHERE replacement_delivery_id=OLD.id) AND
            (NEW.company_id,NEW.request_id,NEW.offer_id,NEW.supplier_id,NEW.project,NEW.work_package,
             NEW.material_name,NEW.unit,NEW.shipped_quantity,NEW.price_per_unit,
             NEW.contract_version_id,NEW.source_supplier_invoice_id) IS DISTINCT FROM
            (OLD.company_id,OLD.request_id,OLD.offer_id,OLD.supplier_id,OLD.project,OLD.work_package,
             OLD.material_name,OLD.unit,OLD.shipped_quantity,OLD.price_per_unit,
             OLD.contract_version_id,OLD.source_supplier_invoice_id) THEN
            RAISE EXCEPTION 'Replacement identity is immutable' USING ERRCODE='23514'; END IF;
        RETURN NEW;
        END $$''')
    op.execute('CREATE TRIGGER replacement_identity BEFORE UPDATE ON supply_deliveries FOR EACH ROW EXECUTE FUNCTION freeze_replacement_identity()')


def downgrade():
    op.execute('LOCK TABLE supply_claim_fulfilments,supply_claim_events IN ACCESS EXCLUSIVE MODE')
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM supply_claim_fulfilments) OR EXISTS(SELECT 1 FROM supply_claim_events WHERE action IN ('return','replace')) THEN RAISE EXCEPTION 'Cannot discard claim fulfilment'; END IF; END $$")
    op.execute('DROP TRIGGER replacement_identity ON supply_deliveries')
    op.execute('DROP FUNCTION freeze_replacement_identity()')
    op.execute('DROP TABLE supply_claim_fulfilments')
    op.execute('DROP FUNCTION validate_claim_fulfilment()')
    op.execute('ALTER TABLE supply_claim_events DROP CONSTRAINT supply_claim_events_action_check')
    op.execute("ALTER TABLE supply_claim_events ADD CONSTRAINT supply_claim_events_action_check CHECK(action IN ('start','comment','reply','resolve','reopen'))")
