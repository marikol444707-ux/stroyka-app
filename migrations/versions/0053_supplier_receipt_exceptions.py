"""Preserve rejected/zero receipts separately from accepted invoice quantities."""
from alembic import op

revision = '0053_supplier_receipt_exceptions'
down_revision = '0052_supplier_receipt_lines'
branch_labels = None
depends_on = None

OLD_ACCEPTANCE = "OR COALESCE(delivery.status,'')<>'Принято' OR COALESCE(delivery.quality_status,'')<>'Принято'"
NEW_ACCEPTANCE = """OR NOT COALESCE((
                (delivery.status='Принято' AND delivery.quality_status='Принято') OR
                (delivery.status='Проблема' AND delivery.quality_status IN ('Принято','Недостача','Частично')
                 AND delivery.shortage_quantity>0
                 AND delivery.shortage_quantity=delivery.shipped_quantity-delivery.received_quantity
                 AND EXISTS(SELECT 1 FROM public.supply_claims c WHERE c.id=delivery.claim_id
                    AND c.delivery_id=delivery.id AND c.offer_id=delivery.offer_id
                    AND c.request_id=delivery.request_id AND c.supplier_id=delivery.supplier_id
                    AND c.project=delivery.project AND c.shortage_quantity=delivery.shortage_quantity
                    AND c.expected_quantity=delivery.shipped_quantity AND c.received_quantity=delivery.received_quantity))
            ), FALSE)"""


def replace_acceptance(old, new):
    # Preserve the rest of 0049's provenance/amount validation verbatim.
    old = old.replace("'", "''")
    new = new.replace("'", "''")
    op.execute(f"""DO $migration$ DECLARE body TEXT; BEGIN
        SELECT pg_get_functiondef('public.supplier_allocation_receipt(bigint,integer,integer,numeric)'::regprocedure) INTO body;
        IF strpos(body,'{old}')=0 THEN RAISE EXCEPTION 'Unexpected receipt validation function'; END IF;
        EXECUTE replace(body,'{old}','{new}');
    END $migration$""")


def upgrade():
    replace_acceptance(OLD_ACCEPTANCE, NEW_ACCEPTANCE)
    op.execute('''CREATE TABLE public.supplier_receipt_exceptions (
        delivery_id INTEGER PRIMARY KEY REFERENCES public.supply_deliveries(id),
        company_id INTEGER NOT NULL REFERENCES public.companies(id),
        invoice_id INTEGER NOT NULL REFERENCES public.supplier_invoices(id),
        invoice_line_id BIGINT NOT NULL REFERENCES public.supplier_invoice_lines(id),
        warehouse_invoice_id INTEGER UNIQUE REFERENCES public.warehouse_invoices(id),
        claim_id INTEGER NOT NULL REFERENCES public.supply_claims(id),
        received_quantity NUMERIC NOT NULL CHECK(received_quantity>=0 AND received_quantity=trunc(received_quantity,6)),
        rejected_quantity NUMERIC NOT NULL CHECK(rejected_quantity=received_quantity),
        shortage_quantity NUMERIC NOT NULL CHECK(shortage_quantity>=0 AND shortage_quantity=trunc(shortage_quantity,6)),
        quality_status TEXT NOT NULL,
        provenance JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
    )''')
    op.execute('CREATE INDEX supplier_receipt_exceptions_invoice ON public.supplier_receipt_exceptions(company_id,invoice_id)')
    op.execute('''CREATE FUNCTION public.supplier_receipt_exception_validate() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE d public.supply_deliveries; i public.supplier_invoices; w public.warehouse_invoices;
                l public.supplier_invoice_lines; root_id BIGINT; item JSONB;
        BEGIN
        PERFORM public.supplier_allocation_lock(NEW.company_id);
        SELECT id INTO root_id FROM public.supplier_payment_documents WHERE company_id=NEW.company_id
            AND document_kind='invoice' AND document_id=NEW.invoice_id;
        IF root_id IS NULL THEN RAISE EXCEPTION 'Receipt invoice is not registered' USING ERRCODE='23514'; END IF;
        PERFORM public.supplier_allocation_root(root_id,NEW.company_id);
        SELECT * INTO i FROM public.supplier_invoices WHERE id=NEW.invoice_id;
        SELECT * INTO d FROM public.supply_deliveries WHERE id=NEW.delivery_id FOR UPDATE;
        IF NOT FOUND OR (d.company_id,d.source_supplier_invoice_id,d.offer_id,d.request_id,d.supplier_id,
                         d.contract_version_id,d.project,COALESCE(d.work_package,'')) IS DISTINCT FROM
                        (NEW.company_id,i.id,i.offer_id,i.request_id,i.supplier_id,
                         i.contract_version_id,i.project_name,COALESCE(i.work_package,''))
            OR i.contract_version_id IS NULL OR d.received_at IS NULL OR d.status IS DISTINCT FROM 'Проблема'
            OR NOT EXISTS(SELECT 1 FROM public.projects p WHERE p.id=(to_jsonb(d)->>'project_id')::int
                AND p.company_id=NEW.company_id AND p.name=i.project_name)
            OR d.received_quantity IS NULL OR d.received_quantity<0 OR d.shipped_quantity IS NULL
            OR d.shipped_quantity<=0 OR d.received_quantity>d.shipped_quantity
            OR d.shortage_quantity IS DISTINCT FROM d.shipped_quantity-d.received_quantity
            OR NOT (d.quality_status IN ('Брак','Несоответствие') OR d.received_quantity=0)
            OR d.quality_status NOT IN ('Принято','Недостача','Частично','Брак','Несоответствие')
            OR EXISTS(SELECT 1 FROM public.supplier_payment_receipt_relations WHERE source_delivery_id=d.id)
            OR EXISTS(SELECT 1 FROM public.warehouse_history WHERE source_type='supply_delivery' AND source_id=d.id) THEN
            RAISE EXCEPTION 'Invalid rejected receipt source' USING ERRCODE='23514'; END IF;
        SELECT * INTO l FROM public.supplier_invoice_lines WHERE id=NEW.invoice_line_id FOR UPDATE;
        IF NOT FOUND OR l.company_id IS DISTINCT FROM NEW.company_id OR NOT EXISTS(
            SELECT 1 FROM public.supplier_invoice_line_specs s WHERE s.id=l.spec_id AND s.invoice_id=i.id AND s.company_id=NEW.company_id)
            OR (d.material_name,d.unit,COALESCE(d.work_package,''),d.price_per_unit) IS DISTINCT FROM
               (l.material_name,l.unit,l.work_package,l.unit_price)
            OR d.shipped_quantity>l.quantity THEN
            RAISE EXCEPTION 'Rejected receipt invoice line mismatch' USING ERRCODE='23514'; END IF;
        IF NEW.claim_id IS DISTINCT FROM d.claim_id OR NOT EXISTS(SELECT 1 FROM public.supply_claims c
            WHERE c.id=d.claim_id AND c.delivery_id=d.id AND c.offer_id=d.offer_id
                AND c.request_id=d.request_id AND c.supplier_id=d.supplier_id AND c.project=d.project
                AND c.expected_quantity=d.shipped_quantity AND c.received_quantity=d.received_quantity
                AND c.shortage_quantity=d.shortage_quantity) THEN
            RAISE EXCEPTION 'Rejected receipt claim mismatch' USING ERRCODE='23514'; END IF;
        IF d.received_quantity=0 THEN
            IF NEW.warehouse_invoice_id IS NOT NULL OR EXISTS(SELECT 1 FROM public.warehouse_invoices WHERE supply_delivery_id=d.id) THEN
                RAISE EXCEPTION 'Zero receipt must not create invoice' USING ERRCODE='23514'; END IF;
        ELSE
            SELECT * INTO w FROM public.warehouse_invoices WHERE id=NEW.warehouse_invoice_id FOR UPDATE;
            IF NOT FOUND OR (w.company_id,w.supplier_id,w.project,w.supply_delivery_id,w.source_type,w.source_id)
                IS DISTINCT FROM (NEW.company_id,i.supplier_id,i.project_name,d.id,'supply_delivery'::varchar,d.id::text)
                OR (to_jsonb(w)->>'project_id') IS DISTINCT FROM (to_jsonb(d)->>'project_id')
                OR w.supplier_invoice_id IS NOT NULL OR COALESCE(w.paid_amount,0)<>0 OR w.status IS DISTINCT FROM 'Принята'
                OR w.total_with_vat IS DISTINCT FROM d.received_quantity*l.unit_price
                OR w.total_base IS DISTINCT FROM w.total_with_vat OR w.total_vat IS DISTINCT FROM 0::NUMERIC
                OR EXISTS(SELECT 1 FROM public.supplier_invoices WHERE warehouse_invoice_id=w.id)
                OR EXISTS(SELECT 1 FROM public.supplier_payment_documents WHERE document_kind='warehouse' AND document_id=w.id)
                OR jsonb_array_length(w.items::jsonb)<>1 THEN
                RAISE EXCEPTION 'Rejected receipt warehouse mismatch' USING ERRCODE='23514'; END IF;
            item:=w.items::jsonb->0;
            IF (item->>'name',item->>'unit',COALESCE(item->>'workPackage',''),(item->>'quantity')::numeric,(item->>'price')::numeric)
                IS DISTINCT FROM (l.material_name,l.unit,l.work_package,d.received_quantity,l.unit_price) THEN
                RAISE EXCEPTION 'Rejected receipt material mismatch' USING ERRCODE='23514'; END IF;
        END IF;
        NEW.received_quantity:=d.received_quantity;
        NEW.rejected_quantity:=d.received_quantity;
        NEW.shortage_quantity:=d.shortage_quantity;
        NEW.quality_status:=d.quality_status;
        NEW.provenance:=jsonb_build_object('delivery',to_jsonb(d),'warehouse',to_jsonb(w));
        NEW.created_at:=clock_timestamp();
        RETURN NEW;
        END $$''')
    op.execute('''CREATE TRIGGER receipt_exception_validate BEFORE INSERT ON public.supplier_receipt_exceptions
        FOR EACH ROW EXECUTE FUNCTION public.supplier_receipt_exception_validate()''')
    for operation, level, suffix in (('UPDATE OR DELETE','ROW','immutable'),('TRUNCATE','STATEMENT','no_truncate')):
        op.execute(f'''CREATE TRIGGER receipt_exception_{suffix} BEFORE {operation} ON public.supplier_receipt_exceptions
            FOR EACH {level} EXECUTE FUNCTION public.supplier_payment_immutable()''')
    op.execute('''CREATE FUNCTION public.supplier_receipt_exception_freeze() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF TG_OP='TRUNCATE' THEN
            IF EXISTS(SELECT 1 FROM public.supplier_receipt_exceptions) THEN
                RAISE EXCEPTION 'Rejected receipt sources cannot be truncated' USING ERRCODE='23514'; END IF;
            RETURN NULL;
        END IF;
        IF (TG_TABLE_NAME='supply_deliveries' AND EXISTS(SELECT 1 FROM public.supplier_receipt_exceptions WHERE delivery_id=OLD.id))
            OR (TG_TABLE_NAME='warehouse_invoices' AND EXISTS(SELECT 1 FROM public.supplier_receipt_exceptions WHERE warehouse_invoice_id=OLD.id)) THEN
            IF TG_OP='DELETE' OR to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD) THEN
                RAISE EXCEPTION 'Rejected receipt source is immutable' USING ERRCODE='23514'; END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
        END $$''')
    for table in ('supply_deliveries','warehouse_invoices'):
        op.execute(f'''CREATE TRIGGER receipt_exception_freeze BEFORE UPDATE OR DELETE ON public.{table}
            FOR EACH ROW EXECUTE FUNCTION public.supplier_receipt_exception_freeze()''')
        op.execute(f'''CREATE TRIGGER receipt_exception_no_truncate BEFORE TRUNCATE ON public.{table}
            FOR EACH STATEMENT EXECUTE FUNCTION public.supplier_receipt_exception_freeze()''')


    op.execute("""CREATE FUNCTION public.supplier_receipt_exception_mode() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        PERFORM public.supplier_allocation_lock(NEW.company_id);
        IF NEW.document_kind='warehouse' AND EXISTS(SELECT 1 FROM public.supplier_receipt_exceptions
            WHERE warehouse_invoice_id=NEW.document_id) THEN
            RAISE EXCEPTION 'Rejected receipt is not an independent payable document' USING ERRCODE='23514'; END IF;
        RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER receipt_exception_mode BEFORE INSERT ON public.supplier_payment_documents
        FOR EACH ROW EXECUTE FUNCTION public.supplier_receipt_exception_mode()""")
    op.execute("""CREATE FUNCTION public.supplier_receipt_claim_identity() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE cid INTEGER;
        BEGIN
        IF TG_OP='TRUNCATE' THEN
            IF EXISTS(SELECT 1 FROM public.supplier_receipt_exceptions) OR EXISTS(
                SELECT 1 FROM public.supplier_payment_receipt_relations r JOIN public.supply_deliveries d
                    ON d.id=r.source_delivery_id WHERE d.claim_id IS NOT NULL) THEN
                RAISE EXCEPTION 'Receipt claims cannot be truncated' USING ERRCODE='23514'; END IF;
            RETURN NULL;
        END IF;
        SELECT company_id INTO cid FROM public.supply_deliveries WHERE id=OLD.delivery_id;
        IF cid IS NOT NULL THEN PERFORM public.supplier_allocation_lock(cid); END IF;
        IF EXISTS(SELECT 1 FROM public.supplier_receipt_exceptions WHERE claim_id=OLD.id)
            OR EXISTS(SELECT 1 FROM public.supplier_payment_receipt_relations r
                JOIN public.supply_deliveries d ON d.id=r.source_delivery_id WHERE d.claim_id=OLD.id) THEN
            IF TG_OP='DELETE' OR
                (NEW.delivery_id,NEW.offer_id,NEW.request_id,NEW.supplier_id,NEW.project,NEW.material_name,
                 NEW.expected_quantity,NEW.received_quantity,NEW.shortage_quantity) IS DISTINCT FROM
                (OLD.delivery_id,OLD.offer_id,OLD.request_id,OLD.supplier_id,OLD.project,OLD.material_name,
                 OLD.expected_quantity,OLD.received_quantity,OLD.shortage_quantity) THEN
                RAISE EXCEPTION 'Receipt claim identity is immutable' USING ERRCODE='23514'; END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER receipt_claim_no_truncate BEFORE TRUNCATE ON public.supply_claims
        FOR EACH STATEMENT EXECUTE FUNCTION public.supplier_receipt_claim_identity()""")
    op.execute("""CREATE TRIGGER receipt_claim_identity BEFORE UPDATE OR DELETE ON public.supply_claims
        FOR EACH ROW EXECUTE FUNCTION public.supplier_receipt_claim_identity()""")


def downgrade():
    op.execute('''LOCK TABLE public.supplier_receipt_exceptions,public.supplier_payment_receipt_relations,
        public.supply_deliveries IN ACCESS EXCLUSIVE MODE''')
    op.execute('''DO $$ BEGIN IF EXISTS(SELECT 1 FROM public.supplier_receipt_exceptions)
        OR EXISTS(SELECT 1 FROM public.supplier_payment_receipt_relations r JOIN public.supply_deliveries d
            ON d.id=r.source_delivery_id WHERE d.status='Проблема') THEN
        RAISE EXCEPTION 'Cannot discard exceptional receipt evidence'; END IF; END $$''')
    for table in ('supply_deliveries','warehouse_invoices'):
        op.execute(f'DROP TRIGGER receipt_exception_freeze ON public.{table}')
        op.execute(f'DROP TRIGGER receipt_exception_no_truncate ON public.{table}')
    op.execute('DROP TRIGGER receipt_exception_mode ON public.supplier_payment_documents')
    op.execute('DROP TRIGGER receipt_claim_identity ON public.supply_claims')
    op.execute('DROP TRIGGER receipt_claim_no_truncate ON public.supply_claims')
    op.execute('DROP FUNCTION public.supplier_receipt_claim_identity()')
    op.execute('DROP FUNCTION public.supplier_receipt_exception_mode()')
    op.execute('DROP TABLE public.supplier_receipt_exceptions')
    op.execute('DROP FUNCTION public.supplier_receipt_exception_freeze()')
    op.execute('DROP FUNCTION public.supplier_receipt_exception_validate()')
    replace_acceptance(NEW_ACCEPTANCE, OLD_ACCEPTANCE)
