"""Cash refunds and non-cash invoice credits in the immutable settlement journal."""
from alembic import op

revision = '0055_supplier_settlements'
down_revision = '0054_supply_claim_fulfilment'
branch_labels = None
depends_on = None


def upgrade():
    # Save exact previous guards for a safe empty downgrade; do not reconstruct 0045.
    op.execute('CREATE TABLE supplier_settlement_guard_versions(name TEXT PRIMARY KEY, definition TEXT NOT NULL)')
    for name in ('supplier_payment_operation_guard','supplier_payment_impact_guard'):
        op.execute(f"INSERT INTO supplier_settlement_guard_versions VALUES('{name}',pg_get_functiondef('{name}()'::regprocedure))")
    op.execute("ALTER TABLE supplier_payment_operations DROP CONSTRAINT supplier_payment_operations_kind_check")
    op.execute("ALTER TABLE supplier_payment_operations ADD CONSTRAINT supplier_payment_operations_kind_check CHECK(kind IN ('payment','reversal','refund','credit'))")
    op.execute('''DO $$ DECLARE cname TEXT; BEGIN
        SELECT conname INTO STRICT cname FROM pg_constraint WHERE conrelid='supplier_payment_operations'::regclass
            AND contype='c' AND pg_get_constraintdef(oid) LIKE '%kind%reverses_id IS NULL%';
        EXECUTE format('ALTER TABLE supplier_payment_operations DROP CONSTRAINT %I',cname);
    END $$''')
    op.execute("ALTER TABLE supplier_payment_operations ADD CONSTRAINT supplier_operation_reversal_shape CHECK((kind IN ('payment','refund','credit') AND reverses_id IS NULL) OR (kind='reversal' AND reverses_id IS NOT NULL))")
    op.execute('ALTER TABLE supplier_payment_operations ALTER COLUMN project_payment_id DROP NOT NULL')
    op.execute('ALTER TABLE supplier_payment_impacts DROP CONSTRAINT supplier_payment_impacts_delta_check')
    op.execute('ALTER TABLE supplier_payment_impacts ADD CONSTRAINT supplier_payment_impacts_delta_check CHECK(delta BETWEEN -999999999999.99 AND 999999999999.99)')
    op.execute('''CREATE FUNCTION supplier_settlement_cash(kind TEXT,amount NUMERIC,original_kind TEXT DEFAULT NULL)
        RETURNS NUMERIC LANGUAGE SQL IMMUTABLE AS $$ SELECT CASE
        WHEN kind='credit' OR (kind='reversal' AND original_kind='credit') THEN 0
        WHEN kind='refund' OR (kind='reversal' AND original_kind='payment') THEN -amount
        WHEN kind='payment' OR (kind='reversal' AND original_kind='refund') THEN amount
        ELSE NULL END $$''')
    op.execute('''CREATE FUNCTION supplier_invoice_credits(cid INTEGER,iid INTEGER) RETURNS NUMERIC LANGUAGE SQL STABLE AS $$
        SELECT COALESCE(sum(o.amount),0) FROM supplier_payment_operations o
        WHERE o.company_id=cid AND o.document_kind='invoice' AND o.document_id=iid AND o.kind='credit'
          AND NOT EXISTS(SELECT 1 FROM supplier_payment_operations r WHERE r.reverses_id=o.id)
    $$''')
    op.execute('''CREATE OR REPLACE FUNCTION supplier_payment_operation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE payment project_payments; original supplier_payment_operations; cash NUMERIC;
        BEGIN
        NEW.creation_xid:=pg_current_xact_id();
        IF NEW.kind='reversal' THEN
            SELECT * INTO original FROM supplier_payment_operations WHERE id=NEW.reverses_id AND company_id=NEW.company_id FOR SHARE;
            IF NOT FOUND OR original.kind NOT IN ('payment','refund','credit') OR
                (original.amount,original.payer_company_id,original.supplier_id,original.document_kind,original.document_id)
                IS DISTINCT FROM (NEW.amount,NEW.payer_company_id,NEW.supplier_id,NEW.document_kind,NEW.document_id) THEN
                RAISE EXCEPTION 'Invalid supplier operation reversal' USING ERRCODE='23514'; END IF;
        END IF;
        cash:=supplier_settlement_cash(NEW.kind,NEW.amount,original.kind);
        IF cash IS NULL THEN RAISE EXCEPTION 'Unknown settlement kind' USING ERRCODE='23514'; END IF;
        IF cash=0 THEN
            IF NEW.project_payment_id IS NOT NULL OR NEW.document_kind<>'invoice' THEN
                RAISE EXCEPTION 'Credit must not create cash' USING ERRCODE='23514'; END IF;
        ELSE
            SELECT * INTO payment FROM project_payments WHERE id=NEW.project_payment_id FOR SHARE;
            IF NOT FOUND OR (payment.company_id,payment.amount,payment.added_by,payment.date)
                IS DISTINCT FROM (NEW.company_id,cash,NEW.actor_name,NEW.payment_date::TEXT) THEN
                RAISE EXCEPTION 'Supplier operation does not match cash' USING ERRCODE='23514'; END IF;
        END IF;
        RETURN NEW;
        END $$''')
    op.execute('''CREATE OR REPLACE FUNCTION supplier_payment_impact_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE operation supplier_payment_operations; document supplier_payment_documents;
                payment project_payments; original_kind TEXT; cash NUMERIC; paid NUMERIC; effective NUMERIC;
        BEGIN
        PERFORM supplier_allocation_lock(NEW.company_id);
        SELECT * INTO operation FROM supplier_payment_operations WHERE id=NEW.operation_id AND company_id=NEW.company_id FOR SHARE;
        IF NOT FOUND OR operation.creation_xid IS DISTINCT FROM pg_current_xact_id() THEN
            RAISE EXCEPTION 'Missing or sealed supplier operation' USING ERRCODE='23514'; END IF;
        SELECT kind INTO original_kind FROM supplier_payment_operations WHERE id=operation.reverses_id;
        cash:=supplier_settlement_cash(operation.kind,operation.amount,original_kind);
        SELECT * INTO document FROM supplier_payment_documents WHERE id=NEW.document_record_id AND company_id=NEW.company_id FOR SHARE;
        IF NOT FOUND OR (document.payer_company_id,document.supplier_id)
            IS DISTINCT FROM (operation.payer_company_id,operation.supplier_id) OR NEW.delta IS DISTINCT FROM cash THEN
            RAISE EXCEPTION 'Invalid supplier impact' USING ERRCODE='23514'; END IF;
        IF operation.kind IN ('refund','credit') OR original_kind IN ('refund','credit') THEN
            PERFORM supplier_allocation_root(document.id,NEW.company_id);
            IF (operation.document_kind,operation.document_id) IS DISTINCT FROM (document.document_kind,document.document_id) THEN
                RAISE EXCEPTION 'Settlement requires invoice-only impact' USING ERRCODE='23514'; END IF;
        END IF;
        IF cash<>0 THEN
            SELECT * INTO payment FROM project_payments WHERE id=operation.project_payment_id FOR SHARE;
            IF NOT FOUND OR (payment.project_name,COALESCE(payment.work_package,''))
                IS DISTINCT FROM (document.project_name,document.work_package) THEN
                RAISE EXCEPTION 'Supplier impact project mismatch' USING ERRCODE='23514'; END IF;
        END IF;
        SELECT document.opening_paid+COALESCE(sum(delta),0)+NEW.delta INTO paid FROM supplier_payment_impacts
            WHERE document_record_id=document.id AND company_id=NEW.company_id;
        effective:=document.amount-CASE WHEN document.document_kind='invoice'
            THEN supplier_invoice_credits(NEW.company_id,document.document_id) ELSE 0 END;
        IF effective<0 OR paid<0 OR paid>document.amount OR (operation.kind='payment' AND paid>effective) THEN
            RAISE EXCEPTION 'Settlement balance exceeded' USING ERRCODE='23514'; END IF;
        IF operation.kind IN ('refund','credit') AND EXISTS(
            SELECT 1 FROM supplier_payment_allocation_groups g
            JOIN supplier_payment_allocation_revisions h ON h.group_id=g.id
            JOIN supplier_payment_allocation_rows r ON r.revision_id=h.id
            WHERE g.invoice_record_id=document.id AND h.id=(SELECT max(v.id) FROM supplier_payment_allocation_revisions v WHERE v.group_id=g.id)
                AND NOT EXISTS(SELECT 1 FROM supplier_payment_operations rev WHERE rev.reverses_id=r.payment_operation_id)
                AND r.amount>0) THEN
            RAISE EXCEPTION 'Release payment allocations before settlement adjustment' USING ERRCODE='23514'; END IF;
        RETURN NEW;
        END $$''')
    op.execute('''CREATE FUNCTION supplier_settlement_allocation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        PERFORM supplier_allocation_lock(NEW.company_id);
        IF EXISTS(SELECT 1 FROM supplier_payment_allocation_groups g JOIN supplier_payment_documents d ON d.id=g.invoice_record_id
            JOIN supplier_payment_operations o ON o.company_id=d.company_id AND o.document_kind='invoice' AND o.document_id=d.document_id
            WHERE g.id=NEW.group_id AND o.kind IN ('refund','credit')
              AND NOT EXISTS(SELECT 1 FROM supplier_payment_operations rev WHERE rev.reverses_id=o.id)) THEN
            RAISE EXCEPTION 'Allocation of adjusted settlements is not supported' USING ERRCODE='23514'; END IF;
        RETURN NEW;
        END $$''')
    op.execute('CREATE TRIGGER settlement_allocation BEFORE INSERT ON supplier_payment_allocation_revisions FOR EACH ROW EXECUTE FUNCTION supplier_settlement_allocation_guard()')
    op.execute('''CREATE FUNCTION supplier_settlement_attachment_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        PERFORM supplier_allocation_lock(NEW.company_id);
        IF EXISTS(SELECT 1 FROM supplier_payment_documents d JOIN supplier_payment_operations o
            ON o.company_id=d.company_id AND o.document_kind='invoice' AND o.document_id=d.document_id
            WHERE d.id=NEW.invoice_record_id AND o.kind IN ('refund','credit')
              AND NOT EXISTS(SELECT 1 FROM supplier_payment_operations rev WHERE rev.reverses_id=o.id)) THEN
            RAISE EXCEPTION 'Adjusted invoice cannot become a legacy mirror' USING ERRCODE='23514'; END IF;
        RETURN NEW;
        END $$''')
    op.execute('CREATE TRIGGER settlement_attachment BEFORE INSERT ON supplier_payment_attachments FOR EACH ROW EXECUTE FUNCTION supplier_settlement_attachment_guard()')


def downgrade():
    op.execute('LOCK TABLE supplier_payment_operations,supplier_payment_impacts IN ACCESS EXCLUSIVE MODE')
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM supplier_payment_operations WHERE kind IN ('refund','credit')) THEN RAISE EXCEPTION 'Cannot discard settlement evidence'; END IF; END $$")
    op.execute('DO $$ DECLARE r RECORD; BEGIN FOR r IN SELECT definition FROM supplier_settlement_guard_versions LOOP EXECUTE r.definition; END LOOP; END $$')
    op.execute('DROP TRIGGER settlement_allocation ON supplier_payment_allocation_revisions')
    op.execute('DROP FUNCTION supplier_settlement_allocation_guard()')
    op.execute('DROP TRIGGER settlement_attachment ON supplier_payment_attachments')
    op.execute('DROP FUNCTION supplier_settlement_attachment_guard()')
    op.execute('DROP FUNCTION supplier_invoice_credits(INTEGER,INTEGER)')
    op.execute('DROP FUNCTION supplier_settlement_cash(TEXT,NUMERIC,TEXT)')
    op.execute('DROP TABLE supplier_settlement_guard_versions')
    op.execute('ALTER TABLE supplier_payment_operations ALTER COLUMN project_payment_id SET NOT NULL')
    op.execute('ALTER TABLE supplier_payment_operations DROP CONSTRAINT supplier_payment_operations_kind_check')
    op.execute("ALTER TABLE supplier_payment_operations ADD CONSTRAINT supplier_payment_operations_kind_check CHECK(kind IN ('payment','reversal'))")
    op.execute('ALTER TABLE supplier_payment_operations DROP CONSTRAINT supplier_operation_reversal_shape')
    op.execute("ALTER TABLE supplier_payment_operations ADD CONSTRAINT supplier_payment_operations_check CHECK((kind='payment' AND reverses_id IS NULL) OR (kind='reversal' AND reverses_id IS NOT NULL))")
    op.execute('ALTER TABLE supplier_payment_impacts DROP CONSTRAINT supplier_payment_impacts_delta_check')
    op.execute('ALTER TABLE supplier_payment_impacts ADD CONSTRAINT supplier_payment_impacts_delta_check CHECK(delta<>0 AND delta BETWEEN -999999999999.99 AND 999999999999.99)')
