"""Exact cumulative receipt quantities against immutable invoice lines.

Additive, no historical backfill and no runtime activation. Legacy groups without
proofs stay legacy. Once a group contains proof, all its receipts require proof
by commit. Existing physical receipt/line immutability remains in force.
"""
from alembic import op
revision = '0052_supplier_receipt_lines'
down_revision = '0051_supplier_offer_item_scopes'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE public.supplier_receipt_line_proofs (
        receipt_relation_id BIGINT PRIMARY KEY REFERENCES public.supplier_payment_receipt_relations(id),
        invoice_line_id BIGINT NOT NULL REFERENCES public.supplier_invoice_lines(id),
        company_id INTEGER NOT NULL REFERENCES public.companies(id),
        quantity NUMERIC NOT NULL CHECK(quantity>0 AND quantity=trunc(quantity,6)),
        amount NUMERIC NOT NULL CHECK(amount>0 AND amount=trunc(amount,2)),
        created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
    )''')
    op.execute('CREATE INDEX supplier_receipt_line_consumption ON public.supplier_receipt_line_proofs(invoice_line_id)')
    op.execute('''CREATE FUNCTION public.supplier_receipt_line_validate() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE r public.supplier_payment_receipt_relations; l public.supplier_invoice_lines;
                source_invoice_id INTEGER; snap JSONB; used_qty NUMERIC; used_amount NUMERIC;
        BEGIN
        PERFORM public.supplier_allocation_lock(NEW.company_id);
        SELECT * INTO r FROM public.supplier_payment_receipt_relations WHERE id=NEW.receipt_relation_id;
        IF NOT FOUND OR r.company_id IS DISTINCT FROM NEW.company_id THEN
            RAISE EXCEPTION 'Receipt proof company mismatch' USING ERRCODE='23514'; END IF;
        SELECT d.document_id INTO source_invoice_id FROM public.supplier_payment_allocation_groups g
            JOIN public.supplier_payment_documents d ON d.id=g.invoice_record_id
            WHERE g.id=r.group_id AND g.company_id=NEW.company_id AND d.document_kind='invoice';
        SELECT * INTO l FROM public.supplier_invoice_lines WHERE id=NEW.invoice_line_id FOR UPDATE;
        IF NOT FOUND OR l.company_id IS DISTINCT FROM NEW.company_id OR NOT EXISTS(
            SELECT 1 FROM public.supplier_invoice_line_specs s WHERE s.id=l.spec_id AND s.invoice_id=source_invoice_id
            AND s.company_id=NEW.company_id) THEN
            RAISE EXCEPTION 'Receipt proof invoice line mismatch' USING ERRCODE='23514'; END IF;
        snap := public.supplier_allocation_receipt(r.group_id,r.company_id,r.warehouse_invoice_id,r.amount);
        IF snap IS DISTINCT FROM r.provenance OR
            (snap->'delivery'->>'material_name',snap->'delivery'->>'unit',snap->'delivery'->>'work_package',
             (snap->'delivery'->>'price_per_unit')::NUMERIC)
            IS DISTINCT FROM (l.material_name,l.unit,l.work_package,l.unit_price)
            OR NEW.quantity IS DISTINCT FROM (snap->'delivery'->>'received_quantity')::NUMERIC
            OR NEW.amount IS DISTINCT FROM r.amount OR NEW.amount IS DISTINCT FROM NEW.quantity*l.unit_price THEN
            RAISE EXCEPTION 'Receipt proof composition mismatch' USING ERRCODE='23514'; END IF;
        SELECT COALESCE(SUM(quantity),0),COALESCE(SUM(amount),0) INTO used_qty,used_amount
            FROM public.supplier_receipt_line_proofs WHERE invoice_line_id=l.id;
        IF used_qty+NEW.quantity>l.quantity OR used_amount+NEW.amount>l.amount THEN
            RAISE EXCEPTION 'Receipt quantity exceeds invoice line' USING ERRCODE='23514'; END IF;
        NEW.created_at := clock_timestamp();
        RETURN NEW;
        END; $$''')
    op.execute('''CREATE TRIGGER receipt_line_validate BEFORE INSERT ON public.supplier_receipt_line_proofs
        FOR EACH ROW EXECUTE FUNCTION public.supplier_receipt_line_validate()''')
    op.execute('''CREATE TRIGGER receipt_line_immutable BEFORE UPDATE OR DELETE ON public.supplier_receipt_line_proofs
        FOR EACH ROW EXECUTE FUNCTION public.supplier_payment_immutable()''')
    op.execute('''CREATE TRIGGER receipt_line_no_truncate BEFORE TRUNCATE ON public.supplier_receipt_line_proofs
        FOR EACH STATEMENT EXECUTE FUNCTION public.supplier_payment_immutable()''')
    op.execute('''CREATE FUNCTION public.supplier_receipt_line_complete() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE gid BIGINT; cid INTEGER;
        BEGIN
        IF TG_TABLE_NAME='supplier_receipt_line_proofs' THEN
            SELECT group_id,company_id INTO gid,cid FROM public.supplier_payment_receipt_relations
                WHERE id=NEW.receipt_relation_id;
        ELSE gid:=NEW.group_id; cid:=NEW.company_id; END IF;
        PERFORM public.supplier_allocation_lock(cid);
        IF EXISTS(SELECT 1 FROM public.supplier_receipt_line_proofs p
            JOIN public.supplier_payment_receipt_relations r ON r.id=p.receipt_relation_id WHERE r.group_id=gid)
            AND EXISTS(SELECT 1 FROM public.supplier_payment_receipt_relations r
                LEFT JOIN public.supplier_receipt_line_proofs p ON p.receipt_relation_id=r.id
                WHERE r.group_id=gid AND p.receipt_relation_id IS NULL) THEN
            RAISE EXCEPTION 'Receipt group has unproven lines' USING ERRCODE='23514'; END IF;
        RETURN NULL;
        END; $$''')
    for table in ('supplier_receipt_line_proofs', 'supplier_payment_receipt_relations'):
        op.execute(f'''CREATE CONSTRAINT TRIGGER receipt_line_complete AFTER INSERT ON public.{table}
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.supplier_receipt_line_complete()''')


def downgrade():
    op.execute('''DO $$ BEGIN IF EXISTS(SELECT 1 FROM public.supplier_receipt_line_proofs) THEN
        RAISE EXCEPTION 'Cannot discard receipt line evidence'; END IF; END $$''')
    op.execute('DROP TRIGGER receipt_line_complete ON public.supplier_payment_receipt_relations')
    op.execute('DROP TABLE public.supplier_receipt_line_proofs')
    op.execute('DROP FUNCTION public.supplier_receipt_line_complete()')
    op.execute('DROP FUNCTION public.supplier_receipt_line_validate()')
