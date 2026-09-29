"""Optional immutable allocation maps; no financial mutation or data backfill.

Apply/downgrade only with writers quiesced. New triggers serialize admission
with existing engine company locks. Physical receipt/delivery rows are frozen
in this conservative slice, including metadata. Services must lock company
before physical rows and supply current authorization; DB actor IDs are NOT auth.
Reversals leave history intact: readers must exclude reversed payment IDs from
the latest full revision. A subsequent revision must omit those IDs entirely.
Receipt proof is single-line, exact zero-VAT delivery evidence with fixed
contract/offer/request IDs, not an immutable invoice-line allocation or a claim
that runtime contract authorization/receipt registration has been implemented.
"""
from alembic import op

revision = '0049_supplier_pay_allocations'
down_revision = '0048_supplier_pay_cancellations'
branch_labels = None
depends_on = None
TABLES = ('supplier_payment_allocation_groups', 'supplier_payment_receipt_relations',
          'supplier_payment_allocation_revisions', 'supplier_payment_allocation_rows')
OLD_TABLES = ('supplier_payment_documents', 'supplier_payment_operations',
              'supplier_payment_impacts', 'supplier_payment_attachments',
              'supplier_payment_request_cancellations')
PHYSICAL = ('supplier_invoices', 'warehouse_invoices', 'supply_deliveries')


def upgrade():
    # Prerequisite only: never invent/backfill legacy delivery source identity.
    op.execute('SELECT source_supplier_invoice_id,contract_version_id,offer_id,request_id FROM public.supply_deliveries LIMIT 0')
    op.execute('SELECT contract_version_id,offer_id,request_id FROM public.supplier_invoices LIMIT 0')
    op.execute('''CREATE TABLE public.supplier_payment_allocation_groups (
        id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES public.companies(id),
        invoice_record_id BIGINT NOT NULL UNIQUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(id,company_id),
        FOREIGN KEY(invoice_record_id,company_id) REFERENCES public.supplier_payment_documents(id,company_id)
    )''')
    op.execute('''CREATE TABLE public.supplier_payment_receipt_relations (
        id BIGSERIAL PRIMARY KEY, group_id BIGINT NOT NULL, company_id INTEGER NOT NULL,
        warehouse_invoice_id INTEGER NOT NULL UNIQUE REFERENCES public.warehouse_invoices(id),
        source_delivery_id INTEGER NOT NULL UNIQUE REFERENCES public.supply_deliveries(id),
        amount NUMERIC NOT NULL CHECK(amount>0 AND amount<=999999999999.99 AND amount=trunc(amount,2)),
        provenance JSONB NOT NULL CHECK(jsonb_typeof(provenance)='object'),
        created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(id,group_id,company_id),
        FOREIGN KEY(group_id,company_id) REFERENCES public.supplier_payment_allocation_groups(id,company_id)
    )''')
    op.execute('''CREATE TABLE public.supplier_payment_allocation_revisions (
        id BIGSERIAL PRIMARY KEY, group_id BIGINT NOT NULL, company_id INTEGER NOT NULL,
        version INTEGER NOT NULL CHECK(version>0), previous_revision_id BIGINT,
        request_id UUID NOT NULL, fingerprint TEXT NOT NULL CHECK(fingerprint ~ '^[0-9a-f]{64}$'),
        actor_id INTEGER NOT NULL REFERENCES public.users(id), reason TEXT NOT NULL CHECK(btrim(reason)<>''),
        row_count INTEGER NOT NULL CHECK(row_count BETWEEN 0 AND 2000),
        created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        creation_xid XID8 NOT NULL DEFAULT pg_current_xact_id(),
        UNIQUE(group_id,version), UNIQUE(company_id,request_id), UNIQUE(id,group_id,company_id),
        FOREIGN KEY(group_id,company_id) REFERENCES public.supplier_payment_allocation_groups(id,company_id),
        FOREIGN KEY(previous_revision_id,group_id,company_id)
            REFERENCES public.supplier_payment_allocation_revisions(id,group_id,company_id),
        CHECK(previous_revision_id IS NULL OR previous_revision_id<>id)
    )''')
    op.execute('''CREATE TABLE public.supplier_payment_allocation_rows (
        revision_id BIGINT NOT NULL, group_id BIGINT NOT NULL, company_id INTEGER NOT NULL,
        payment_operation_id BIGINT NOT NULL, receipt_relation_id BIGINT NOT NULL,
        amount NUMERIC NOT NULL CHECK(amount>0 AND amount<=999999999999.99 AND amount=trunc(amount,2)),
        PRIMARY KEY(revision_id,payment_operation_id,receipt_relation_id),
        FOREIGN KEY(revision_id,group_id,company_id)
            REFERENCES public.supplier_payment_allocation_revisions(id,group_id,company_id),
        FOREIGN KEY(receipt_relation_id,group_id,company_id)
            REFERENCES public.supplier_payment_receipt_relations(id,group_id,company_id),
        FOREIGN KEY(payment_operation_id,company_id) REFERENCES public.supplier_payment_operations(id,company_id)
    )''')
    for table in TABLES:
        op.execute(f'''CREATE TRIGGER allocation_immutable BEFORE UPDATE OR DELETE ON public.{table}
            FOR EACH ROW EXECUTE FUNCTION public.supplier_payment_immutable()''')
        op.execute(f'''CREATE TRIGGER allocation_no_truncate BEFORE TRUNCATE ON public.{table}
            FOR EACH STATEMENT EXECUTE FUNCTION public.supplier_payment_immutable()''')
    op.execute('''CREATE FUNCTION public.supplier_allocation_lock(cid INTEGER) RETURNS void LANGUAGE plpgsql AS $$
        BEGIN
        IF cid IS NULL OR current_setting('transaction_isolation')<>'read committed' THEN
            RAISE EXCEPTION 'Allocation requires company and READ COMMITTED' USING ERRCODE='23514';
        END IF;
        PERFORM pg_advisory_xact_lock(1735289201,cid);
        END;
    $$''')
    op.execute('''CREATE FUNCTION public.supplier_allocation_root(rid BIGINT,cid INTEGER)
        RETURNS public.supplier_payment_documents LANGUAGE plpgsql AS $$
        DECLARE d public.supplier_payment_documents; i public.supplier_invoices;
        BEGIN
        PERFORM public.supplier_allocation_lock(cid);
        SELECT * INTO d FROM public.supplier_payment_documents WHERE id=rid AND company_id=cid;
        IF NOT FOUND OR d.document_kind<>'invoice' THEN
            RAISE EXCEPTION 'Allocation root must be invoice' USING ERRCODE='23514'; END IF;
        SELECT * INTO i FROM public.supplier_invoices WHERE id=d.document_id FOR UPDATE;
        IF NOT FOUND OR (i.company_id,i.supplier_id,COALESCE(i.project_name,''),COALESCE(i.work_package,''),i.amount)
            IS DISTINCT FROM (d.company_id,d.supplier_id,d.project_name,d.work_package,d.amount)
            OR i.warehouse_invoice_id IS NOT NULL OR COALESCE(i.status,'')='Аннулирован'
            OR EXISTS(SELECT 1 FROM public.warehouse_invoices WHERE supplier_invoice_id=i.id)
            OR EXISTS(SELECT 1 FROM public.supplier_payment_attachments WHERE invoice_record_id=rid)
            OR EXISTS(SELECT 1 FROM public.supplier_payment_impacts x
                JOIN public.supplier_payment_operations o ON o.id=x.operation_id
                WHERE x.document_record_id=rid AND (o.document_kind<>'invoice' OR o.document_id<>d.document_id
                    OR EXISTS(SELECT 1 FROM public.supplier_payment_impacts s
                        WHERE s.operation_id=o.id AND s.document_record_id<>rid))) THEN
            RAISE EXCEPTION 'Allocation requires unchanged invoice-only root' USING ERRCODE='23514';
        END IF;
        RETURN d;
        END;
    $$''')
    op.execute('''CREATE FUNCTION public.supplier_allocation_receipt(gid BIGINT,cid INTEGER,wid INTEGER,expected NUMERIC)
        RETURNS JSONB LANGUAGE plpgsql AS $$
        DECLARE d public.supplier_payment_documents; w public.warehouse_invoices;
                delivery public.supply_deliveries; invoice public.supplier_invoices; rid BIGINT; item JSONB;
        BEGIN
        SELECT invoice_record_id INTO rid FROM public.supplier_payment_allocation_groups WHERE id=gid AND company_id=cid;
        d := public.supplier_allocation_root(rid,cid);
        SELECT * INTO w FROM public.warehouse_invoices WHERE id=wid FOR UPDATE;
        IF NOT FOUND OR (w.company_id,w.supplier_id,COALESCE(NULLIF(w.project,''),w.location,''),
             public.supplier_payment_warehouse_package(w.items),COALESCE(NULLIF(w.total_with_vat,0),w.total_base))
             IS DISTINCT FROM (cid,d.supplier_id,d.project_name,d.work_package,expected)
           OR COALESCE(w.status,'')<>'Принята' OR COALESCE(w.paid_amount,0)<>0
           OR w.supplier_invoice_id IS NOT NULL
           OR EXISTS(SELECT 1 FROM public.supplier_invoices WHERE warehouse_invoice_id=wid)
           OR EXISTS(SELECT 1 FROM public.supplier_payment_documents WHERE document_kind='warehouse' AND document_id=wid)
           OR w.supply_delivery_id IS NULL THEN
            RAISE EXCEPTION 'Invalid allocation receipt identity or mode' USING ERRCODE='23514'; END IF;
        SELECT * INTO delivery FROM public.supply_deliveries WHERE id=w.supply_delivery_id FOR UPDATE;
        IF NOT FOUND OR (delivery.company_id,delivery.supplier_id,COALESCE(delivery.project,''),
            COALESCE(delivery.work_package,''),delivery.source_supplier_invoice_id)
            IS DISTINCT FROM (cid,d.supplier_id,d.project_name,d.work_package,d.document_id)
            OR COALESCE(delivery.status,'')<>'Принято' OR COALESCE(delivery.quality_status,'')<>'Принято'
            OR delivery.received_at IS NULL OR COALESCE(delivery.received_quantity,0)<=0 THEN
            RAISE EXCEPTION 'Allocation receipt lacks accepted source delivery' USING ERRCODE='23514'; END IF;
        SELECT * INTO invoice FROM public.supplier_invoices WHERE id=d.document_id;
        IF invoice.contract_version_id IS NULL OR invoice.offer_id IS NULL OR invoice.request_id IS NULL
            OR (delivery.contract_version_id,delivery.offer_id,delivery.request_id)
            IS DISTINCT FROM (invoice.contract_version_id,invoice.offer_id,invoice.request_id) THEN
            RAISE EXCEPTION 'Allocation receipt invoice provenance mismatch' USING ERRCODE='23514'; END IF;
        -- Conservative physical adapter contract: one exact line, no VAT,
        -- no partial-line rounding or duplicate delivery evidence.
        IF delivery.received_quantity>999999999999 OR delivery.received_quantity>delivery.shipped_quantity
            OR delivery.shipped_quantity IS NULL OR delivery.shipped_quantity>delivery.planned_quantity
            OR delivery.planned_quantity IS NULL OR delivery.planned_quantity>999999999999
            OR delivery.price_per_unit IS NULL OR delivery.price_per_unit<=0 OR delivery.price_per_unit>999999999999.99
            OR expected IS DISTINCT FROM delivery.received_quantity*delivery.price_per_unit
            OR w.total_base IS DISTINCT FROM expected OR w.total_with_vat IS DISTINCT FROM expected
            OR w.total_vat IS DISTINCT FROM 0::NUMERIC
            OR w.source_type IS DISTINCT FROM 'supply_delivery' OR w.source_id IS DISTINCT FROM delivery.id::TEXT
            OR delivery.request_id IS NULL OR w.supply_request_id IS DISTINCT FROM delivery.request_id
            OR jsonb_array_length(w.items::JSONB)<>1 THEN
            RAISE EXCEPTION 'Unsupported allocation receipt amount or provenance' USING ERRCODE='23514'; END IF;
        item := w.items::JSONB->0;
        IF (item->>'quantity')::NUMERIC IS DISTINCT FROM delivery.received_quantity
            OR (item->>'price')::NUMERIC IS DISTINCT FROM delivery.price_per_unit
            OR item->>'name' IS DISTINCT FROM delivery.material_name
            OR item->>'unit' IS DISTINCT FROM delivery.unit
            OR COALESCE(delivery.material_name,'')='' OR COALESCE(delivery.unit,'')='' THEN
            RAISE EXCEPTION 'Allocation receipt line differs from delivery' USING ERRCODE='23514'; END IF;
        RETURN jsonb_build_object('deliveryId',delivery.id,'sourceSupplierInvoiceId',d.document_id,
            'warehouseInvoiceId',wid,'warehouse',to_jsonb(w),'delivery',to_jsonb(delivery));
        END;
    $$''')
    op.execute('''CREATE FUNCTION public.supplier_allocation_insert() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE d public.supplier_payment_documents; last_revision public.supplier_payment_allocation_revisions;
                header public.supplier_payment_allocation_revisions; snap JSONB; cap NUMERIC; rid BIGINT;
        BEGIN
        PERFORM public.supplier_allocation_lock(NEW.company_id);
        IF TG_TABLE_NAME<>'supplier_payment_allocation_rows' THEN NEW.created_at:=clock_timestamp(); END IF;
        IF TG_TABLE_NAME='supplier_payment_allocation_groups' THEN
            d := public.supplier_allocation_root(NEW.invoice_record_id,NEW.company_id);
        ELSIF TG_TABLE_NAME='supplier_payment_receipt_relations' THEN
            snap := public.supplier_allocation_receipt(NEW.group_id,NEW.company_id,NEW.warehouse_invoice_id,NEW.amount);
            IF NEW.provenance IS NOT NULL AND NEW.provenance IS DISTINCT FROM snap THEN
                RAISE EXCEPTION 'Forged receipt provenance' USING ERRCODE='23514'; END IF;
            NEW.provenance := snap;
            IF NEW.source_delivery_id IS NOT NULL AND NEW.source_delivery_id<>(snap->>'deliveryId')::INTEGER THEN
                RAISE EXCEPTION 'Forged delivery id' USING ERRCODE='23514'; END IF;
            NEW.source_delivery_id := (snap->>'deliveryId')::INTEGER;
            SELECT d0.amount INTO cap FROM public.supplier_payment_allocation_groups g
                JOIN public.supplier_payment_documents d0 ON d0.id=g.invoice_record_id WHERE g.id=NEW.group_id;
            IF NEW.amount+(SELECT COALESCE(SUM(amount),0) FROM public.supplier_payment_receipt_relations WHERE group_id=NEW.group_id)>cap THEN
                RAISE EXCEPTION 'Receipt total exceeds invoice' USING ERRCODE='23514'; END IF;
        ELSIF TG_TABLE_NAME='supplier_payment_allocation_revisions' THEN
            SELECT invoice_record_id INTO rid FROM public.supplier_payment_allocation_groups
                WHERE id=NEW.group_id AND company_id=NEW.company_id;
            d := public.supplier_allocation_root(rid,NEW.company_id);
            SELECT * INTO last_revision FROM public.supplier_payment_allocation_revisions
                WHERE group_id=NEW.group_id ORDER BY version DESC LIMIT 1;
            IF NEW.version<>COALESCE(last_revision.version,0)+1
                OR NEW.previous_revision_id IS DISTINCT FROM last_revision.id THEN
                RAISE EXCEPTION 'Stale allocation revision' USING ERRCODE='23514'; END IF;
            NEW.creation_xid := pg_current_xact_id();
            NEW.created_at := clock_timestamp();
        ELSE
            SELECT * INTO header FROM public.supplier_payment_allocation_revisions WHERE id=NEW.revision_id;
            IF NOT FOUND OR header.creation_xid IS DISTINCT FROM pg_current_xact_id() THEN
                RAISE EXCEPTION 'Allocation revision is sealed' USING ERRCODE='23514'; END IF;
        END IF;
        RETURN NEW;
        END;
    $$''')
    for table in TABLES:
        op.execute(f'''CREATE TRIGGER allocation_insert BEFORE INSERT ON public.{table}
            FOR EACH ROW EXECUTE FUNCTION public.supplier_allocation_insert()''')
    op.execute('''CREATE FUNCTION public.supplier_allocation_complete() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE h public.supplier_payment_allocation_revisions; rid BIGINT; snap JSONB;
        BEGIN
        PERFORM public.supplier_allocation_lock(NEW.company_id);
        IF TG_TABLE_NAME='supplier_payment_allocation_groups' THEN
            PERFORM public.supplier_allocation_root(NEW.invoice_record_id,NEW.company_id);
            RETURN NULL;
        ELSIF TG_TABLE_NAME='supplier_payment_receipt_relations' THEN
            snap := public.supplier_allocation_receipt(NEW.group_id,NEW.company_id,NEW.warehouse_invoice_id,NEW.amount);
            IF snap IS DISTINCT FROM NEW.provenance THEN
                RAISE EXCEPTION 'Receipt changed after allocation relation' USING ERRCODE='23514'; END IF;
            RETURN NULL;
        END IF;
        IF TG_TABLE_NAME='supplier_payment_allocation_revisions' THEN h:=NEW;
        ELSE SELECT * INTO h FROM public.supplier_payment_allocation_revisions WHERE id=NEW.revision_id; END IF;
        SELECT invoice_record_id INTO rid FROM public.supplier_payment_allocation_groups WHERE id=h.group_id;
        IF h.row_count<>(SELECT count(*) FROM public.supplier_payment_allocation_rows WHERE revision_id=h.id)
            OR EXISTS(SELECT 1 FROM public.supplier_payment_allocation_rows r
                JOIN public.supplier_payment_operations o ON o.id=r.payment_operation_id
                JOIN public.supplier_payment_documents d ON d.id=rid
                WHERE r.revision_id=h.id AND (o.kind<>'payment' OR o.document_kind<>'invoice'
                    OR o.document_id<>d.document_id OR o.company_id<>h.company_id
                    OR EXISTS(SELECT 1 FROM public.supplier_payment_operations rev WHERE rev.reverses_id=o.id)
                    OR NOT EXISTS(SELECT 1 FROM public.supplier_payment_impacts x
                        WHERE x.operation_id=o.id AND x.document_record_id=rid)
                    OR EXISTS(SELECT 1 FROM public.supplier_payment_impacts x
                        WHERE x.operation_id=o.id AND x.document_record_id<>rid)))
            OR EXISTS(SELECT 1 FROM public.supplier_payment_allocation_rows r
                JOIN public.supplier_payment_operations o ON o.id=r.payment_operation_id
                WHERE r.revision_id=h.id GROUP BY o.id,o.amount HAVING SUM(r.amount)>o.amount)
            OR EXISTS(SELECT 1 FROM public.supplier_payment_allocation_rows r
                JOIN public.supplier_payment_receipt_relations receipt ON receipt.id=r.receipt_relation_id
                WHERE r.revision_id=h.id GROUP BY receipt.id,receipt.amount HAVING SUM(r.amount)>receipt.amount) THEN
            RAISE EXCEPTION 'Incomplete or invalid allocation map' USING ERRCODE='23514';
        END IF;
        RETURN NULL;
        END;
    $$''')
    for table in TABLES:
        op.execute(f'''CREATE CONSTRAINT TRIGGER allocation_complete AFTER INSERT ON public.{table}
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.supplier_allocation_complete()''')
    op.execute('''CREATE FUNCTION public.supplier_allocation_namespace() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        PERFORM public.supplier_allocation_lock(NEW.company_id);
        IF TG_TABLE_NAME='supplier_payment_allocation_revisions' THEN
            IF EXISTS(SELECT 1 FROM public.supplier_payment_operations WHERE company_id=NEW.company_id AND request_id=NEW.request_id)
                OR EXISTS(SELECT 1 FROM public.supplier_payment_attachments WHERE company_id=NEW.company_id AND request_id=NEW.request_id)
                OR EXISTS(SELECT 1 FROM public.supplier_payment_request_cancellations WHERE company_id=NEW.company_id AND request_id=NEW.request_id) THEN
                RAISE EXCEPTION 'Allocation UUID already used' USING ERRCODE='23514'; END IF;
        ELSIF EXISTS(SELECT 1 FROM public.supplier_payment_allocation_revisions WHERE company_id=NEW.company_id AND request_id=NEW.request_id) THEN
            RAISE EXCEPTION 'UUID belongs to allocation revision' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
        END;
    $$''')
    for table in (TABLES[2], OLD_TABLES[1], OLD_TABLES[3], OLD_TABLES[4]):
        op.execute(f'''CREATE TRIGGER a_allocation_namespace BEFORE INSERT ON public.{table}
            FOR EACH ROW EXECUTE FUNCTION public.supplier_allocation_namespace()''')
    op.execute('''CREATE FUNCTION public.supplier_allocation_mode() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        PERFORM public.supplier_allocation_lock(NEW.company_id);
        IF TG_TABLE_NAME='supplier_payment_operations' THEN
            IF NEW.kind='reversal' AND EXISTS(SELECT 1 FROM public.supplier_payment_allocation_rows r
                JOIN public.supplier_payment_allocation_revisions h ON h.id=r.revision_id
                WHERE r.payment_operation_id=NEW.reverses_id AND h.creation_xid=pg_current_xact_id()) THEN
                RAISE EXCEPTION 'New allocation revision cannot include reversed payment' USING ERRCODE='23514'; END IF;
        ELSIF TG_TABLE_NAME='supplier_payment_documents' THEN
            IF NEW.document_kind='warehouse' AND EXISTS(SELECT 1 FROM public.supplier_payment_receipt_relations
                WHERE warehouse_invoice_id=NEW.document_id) THEN
                RAISE EXCEPTION 'Allocation receipt cannot be a financial baseline' USING ERRCODE='23514'; END IF;
        ELSIF TG_TABLE_NAME='supplier_payment_attachments' THEN
            IF EXISTS(SELECT 1 FROM public.supplier_payment_allocation_groups WHERE invoice_record_id=NEW.invoice_record_id) THEN
                RAISE EXCEPTION 'Allocation root cannot enter attachment mode' USING ERRCODE='23514'; END IF;
        ELSE
            IF EXISTS(SELECT 1 FROM public.supplier_payment_allocation_groups g
                JOIN public.supplier_payment_documents d ON d.id=g.invoice_record_id
                JOIN public.supplier_payment_operations o ON o.id=NEW.operation_id
                WHERE (g.invoice_record_id=NEW.document_record_id OR EXISTS(
                    SELECT 1 FROM public.supplier_payment_impacts x WHERE x.operation_id=NEW.operation_id AND x.document_record_id=g.invoice_record_id))
                AND (NEW.document_record_id<>g.invoice_record_id OR o.document_kind<>'invoice' OR o.document_id<>d.document_id
                    OR EXISTS(SELECT 1 FROM public.supplier_payment_impacts x WHERE x.operation_id=NEW.operation_id AND x.document_record_id<>g.invoice_record_id))) THEN
                RAISE EXCEPTION 'Allocation root requires invoice-only impacts' USING ERRCODE='23514'; END IF;
        END IF;
        RETURN NEW;
        END;
    $$''')
    for table in (OLD_TABLES[0], OLD_TABLES[1], OLD_TABLES[2], OLD_TABLES[3]):
        op.execute(f'''CREATE TRIGGER a_allocation_mode BEFORE INSERT ON public.{table}
            FOR EACH ROW EXECUTE FUNCTION public.supplier_allocation_mode()''')
    op.execute('''CREATE FUNCTION public.supplier_allocation_physical() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE root public.supplier_payment_documents; obj JSONB; oldobj JSONB; cid INTEGER;
        BEGIN
        IF TG_OP='TRUNCATE' THEN
            IF EXISTS(SELECT 1 FROM public.supplier_payment_allocation_groups) THEN
                RAISE EXCEPTION 'Allocation physical evidence cannot be truncated' USING ERRCODE='23514'; END IF;
            RETURN NULL;
        END IF;
        obj := CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
        oldobj := CASE WHEN TG_OP='INSERT' THEN obj ELSE to_jsonb(OLD) END;
        FOR cid IN SELECT DISTINCT v FROM unnest(ARRAY[(obj->>'company_id')::INTEGER,(oldobj->>'company_id')::INTEGER]) v
            WHERE v IS NOT NULL ORDER BY v LOOP
            PERFORM public.supplier_allocation_lock(cid);
        END LOOP;
        IF TG_TABLE_NAME='warehouse_invoices' THEN
            -- Invalid cross-company links are rejected even before a group
            -- exists; locking only the warehouse company cannot seal that race.
            IF (obj->>'supplier_invoice_id' IS NOT NULL AND NOT EXISTS(
                SELECT 1 FROM public.supplier_invoices i WHERE i.id=(obj->>'supplier_invoice_id')::INTEGER
                AND i.company_id=(obj->>'company_id')::INTEGER)) OR EXISTS(SELECT 1 FROM public.supplier_invoices i
                WHERE (i.id=(obj->>'supplier_invoice_id')::INTEGER OR i.warehouse_invoice_id=(obj->>'id')::INTEGER)
                AND i.company_id IS DISTINCT FROM (obj->>'company_id')::INTEGER) THEN
                RAISE EXCEPTION 'Cross-company warehouse invoice link' USING ERRCODE='23514'; END IF;
            IF EXISTS(SELECT 1 FROM public.supplier_payment_receipt_relations
                WHERE warehouse_invoice_id IN ((obj->>'id')::INTEGER,(oldobj->>'id')::INTEGER))
                OR EXISTS(SELECT 1 FROM public.supplier_payment_allocation_groups g
                    JOIN public.supplier_payment_documents d ON d.id=g.invoice_record_id
                    WHERE d.document_id=(obj->>'supplier_invoice_id')::INTEGER) THEN
                RAISE EXCEPTION 'Allocation warehouse is frozen and cannot have legacy links' USING ERRCODE='23514'; END IF;
        ELSIF TG_TABLE_NAME='supply_deliveries' THEN
            IF EXISTS(SELECT 1 FROM public.supplier_payment_receipt_relations
                WHERE source_delivery_id IN ((obj->>'id')::INTEGER,(oldobj->>'id')::INTEGER)) THEN
                RAISE EXCEPTION 'Allocation delivery provenance is frozen' USING ERRCODE='23514'; END IF;
        ELSE
            IF (obj->>'warehouse_invoice_id' IS NOT NULL AND NOT EXISTS(
                SELECT 1 FROM public.warehouse_invoices w WHERE w.id=(obj->>'warehouse_invoice_id')::INTEGER
                AND w.company_id=(obj->>'company_id')::INTEGER)) OR EXISTS(SELECT 1 FROM public.warehouse_invoices w
                WHERE (w.id=(obj->>'warehouse_invoice_id')::INTEGER OR w.supplier_invoice_id=(obj->>'id')::INTEGER)
                AND w.company_id IS DISTINCT FROM (obj->>'company_id')::INTEGER) THEN
                RAISE EXCEPTION 'Cross-company invoice warehouse link' USING ERRCODE='23514'; END IF;
            IF EXISTS(SELECT 1 FROM public.supplier_payment_receipt_relations WHERE warehouse_invoice_id=(obj->>'warehouse_invoice_id')::INTEGER) THEN
                RAISE EXCEPTION 'Allocation receipt cannot have invoice legacy link' USING ERRCODE='23514'; END IF;
            SELECT d.* INTO root FROM public.supplier_payment_allocation_groups g
                JOIN public.supplier_payment_documents d ON d.id=g.invoice_record_id
                WHERE d.document_id=(oldobj->>'id')::INTEGER;
            IF FOUND AND (obj->'contract_version_id',obj->'offer_id',obj->'request_id')
                IS DISTINCT FROM (oldobj->'contract_version_id',oldobj->'offer_id',oldobj->'request_id') THEN
                RAISE EXCEPTION 'Allocation invoice provenance is frozen' USING ERRCODE='23514'; END IF;
            IF FOUND AND (TG_OP='DELETE' OR (obj->>'id')::INTEGER<>root.document_id
                OR (obj->>'company_id')::INTEGER IS DISTINCT FROM root.company_id
                OR (obj->>'supplier_id')::INTEGER IS DISTINCT FROM root.supplier_id
                OR COALESCE(obj->>'project_name','')<>root.project_name
                OR COALESCE(obj->>'work_package','')<>root.work_package
                OR (obj->>'amount')::NUMERIC IS DISTINCT FROM root.amount
                OR obj->>'warehouse_invoice_id' IS NOT NULL) THEN
                RAISE EXCEPTION 'Allocation invoice identity is frozen' USING ERRCODE='23514'; END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
        END;
    $$''')
    for table in PHYSICAL:
        op.execute(f'''CREATE TRIGGER a_allocation_physical BEFORE INSERT OR UPDATE OR DELETE ON public.{table}
            FOR EACH ROW EXECUTE FUNCTION public.supplier_allocation_physical()''')
        op.execute(f'''CREATE TRIGGER allocation_physical_no_truncate BEFORE TRUNCATE ON public.{table}
            FOR EACH STATEMENT EXECUTE FUNCTION public.supplier_allocation_physical()''')


def downgrade():
    op.execute('LOCK TABLE ' + ','.join('public.' + table for table in TABLES + OLD_TABLES + PHYSICAL) + ' IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN
        IF current_setting('transaction_isolation')<>'read committed'
            OR EXISTS(SELECT 1 FROM public.supplier_payment_allocation_groups)
            OR EXISTS(SELECT 1 FROM public.supplier_payment_receipt_relations)
            OR EXISTS(SELECT 1 FROM public.supplier_payment_allocation_revisions)
            OR EXISTS(SELECT 1 FROM public.supplier_payment_allocation_rows) THEN
            RAISE EXCEPTION 'Cannot remove allocation evidence'; END IF;
    END $$''')
    for table in PHYSICAL:
        op.execute(f'DROP TRIGGER a_allocation_physical ON public.{table}')
        op.execute(f'DROP TRIGGER allocation_physical_no_truncate ON public.{table}')
    for table in (OLD_TABLES[0], OLD_TABLES[1], OLD_TABLES[2], OLD_TABLES[3]):
        op.execute(f'DROP TRIGGER a_allocation_mode ON public.{table}')
    for table in (OLD_TABLES[1], OLD_TABLES[3], OLD_TABLES[4]):
        op.execute(f'DROP TRIGGER a_allocation_namespace ON public.{table}')
    for table in reversed(TABLES):
        op.execute('DROP TABLE public.' + table)
    for signature in ('supplier_allocation_physical()', 'supplier_allocation_mode()', 'supplier_allocation_namespace()',
                      'supplier_allocation_complete()', 'supplier_allocation_insert()',
                      'supplier_allocation_receipt(BIGINT,INTEGER,INTEGER,NUMERIC)',
                      'supplier_allocation_root(BIGINT,INTEGER)', 'supplier_allocation_lock(INTEGER)'):
        op.execute('DROP FUNCTION public.' + signature)
