"""Immutable review evidence only; does not admit mixed-package cash baselines."""
from alembic import op

revision = '0060_supplier_mixed_scopes'
down_revision = '0059_supplier_refund_allocations'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE FUNCTION public.supplier_mixed_package_scope(items_text TEXT, header_package TEXT)
        RETURNS JSONB LANGUAGE plpgsql IMMUTABLE AS $$
        DECLARE entries JSON; item JSON; packages TEXT[]:=ARRAY[]::TEXT[]; package TEXT; required JSONB;
        BEGIN
        IF header_package IS NULL OR header_package IS DISTINCT FROM btrim(header_package,E' \\t\\r\\n') THEN
            RAISE EXCEPTION 'Explicit invoice package required' USING ERRCODE='23514';
        END IF;
        IF items_text IS NULL OR octet_length(items_text)>1048576 THEN
            RAISE EXCEPTION 'Bounded original item JSON required' USING ERRCODE='23514';
        END IF;
        BEGIN entries:=items_text::JSON;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION 'Invalid item JSON' USING ERRCODE='23514';
        END;
        IF json_typeof(entries) IS DISTINCT FROM 'array' THEN
            RAISE EXCEPTION 'Item array required' USING ERRCODE='23514';
        END IF;
        IF json_array_length(entries) NOT BETWEEN 1 AND 2000 THEN
            RAISE EXCEPTION 'Bounded nonempty items required' USING ERRCODE='23514';
        END IF;
        FOR item IN SELECT value FROM json_array_elements(entries) LOOP
            package:=public.supplier_payment_warehouse_package('['||item::text||']');
            packages:=array_append(packages,package);
        END LOOP;
        IF (SELECT count(DISTINCT p) FROM unnest(packages) AS p)<2 THEN
            RAISE EXCEPTION 'Mixed receipt packages required' USING ERRCODE='23514';
        END IF;
        SELECT jsonb_agg(p ORDER BY p COLLATE "C") INTO required
            FROM (SELECT DISTINCT unnest(array_append(packages,header_package)) AS p) scopes;
        RETURN jsonb_build_object('requiredPackages',required,'linePackages',to_jsonb(packages));
        END $$''')
    op.execute('''CREATE TABLE public.supplier_mixed_scope_reviews (
        id BIGSERIAL PRIMARY KEY,
        company_id INTEGER NOT NULL REFERENCES companies(id),
        invoice_id INTEGER NOT NULL REFERENCES supplier_invoices(id),
        warehouse_id INTEGER NOT NULL REFERENCES warehouse_invoices(id),
        request_id UUID NOT NULL,
        actor_id INTEGER NOT NULL REFERENCES users(id),
        reason TEXT NOT NULL CHECK(length(btrim(reason)) BETWEEN 1 AND 1000),
        package_scope JSONB NOT NULL CHECK(jsonb_typeof(package_scope)='object'),
        invoice_snapshot JSONB NOT NULL CHECK(jsonb_typeof(invoice_snapshot)='object'),
        warehouse_snapshot JSONB NOT NULL CHECK(jsonb_typeof(warehouse_snapshot)='object'),
        created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(company_id,request_id)
    )''')
    op.execute('CREATE INDEX supplier_mixed_scope_invoice ON supplier_mixed_scope_reviews(company_id,invoice_id,id)')
    op.execute('''CREATE FUNCTION public.supplier_mixed_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE i public.supplier_invoices; w public.warehouse_invoices; expected JSONB;
        BEGIN
        IF TG_OP<>'INSERT' THEN
            RAISE EXCEPTION 'Mixed scope review evidence is immutable' USING ERRCODE='23514';
        END IF;
        PERFORM public.supplier_allocation_lock(NEW.company_id);
        SELECT * INTO i FROM public.supplier_invoices WHERE id=NEW.invoice_id FOR UPDATE;
        SELECT * INTO w FROM public.warehouse_invoices WHERE id=NEW.warehouse_id FOR UPDATE;
        IF i.id IS NULL OR w.id IS NULL OR i.company_id IS DISTINCT FROM NEW.company_id
            OR w.company_id IS DISTINCT FROM NEW.company_id
            OR i.warehouse_invoice_id IS DISTINCT FROM w.id OR w.supplier_invoice_id IS DISTINCT FROM i.id
            OR i.supplier_id IS NULL OR i.supplier_id IS DISTINCT FROM w.supplier_id
            OR COALESCE(i.project_name,'')='' OR i.project_name IS DISTINCT FROM COALESCE(NULLIF(w.project,''),w.location,'')
            OR i.amount IS NULL OR i.amount<=0 OR i.amount IS DISTINCT FROM COALESCE(NULLIF(w.total_with_vat,0),w.total_base)
            OR i.paid_amount IS NULL OR w.paid_amount IS NULL OR i.paid_amount<0 OR i.paid_amount>i.amount
            OR i.paid_amount IS DISTINCT FROM w.paid_amount
            OR to_jsonb(i) IS DISTINCT FROM NEW.invoice_snapshot
            OR to_jsonb(w) IS DISTINCT FROM NEW.warehouse_snapshot
            OR EXISTS(SELECT 1 FROM supplier_invoices WHERE warehouse_invoice_id=w.id AND id<>i.id)
            OR EXISTS(SELECT 1 FROM warehouse_invoices WHERE supplier_invoice_id=i.id AND id<>w.id)
            OR EXISTS(SELECT 1 FROM supplier_invoice_line_specs WHERE invoice_id=i.id)
            OR EXISTS(SELECT 1 FROM supplier_payment_documents WHERE
                (document_kind='invoice' AND document_id=i.id) OR (document_kind='warehouse' AND document_id=w.id)) THEN
            RAISE EXCEPTION 'Mixed review requires exact unregistered reciprocal legacy sources' USING ERRCODE='23514';
        END IF;
        expected:=public.supplier_mixed_package_scope(w.items::text,i.work_package);
        IF NEW.package_scope IS DISTINCT FROM expected THEN
            RAISE EXCEPTION 'Complete original package scope required' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
        END $$''')
    op.execute('''CREATE TRIGGER supplier_mixed_scope_insert BEFORE INSERT OR UPDATE OR DELETE
        ON supplier_mixed_scope_reviews FOR EACH ROW EXECUTE FUNCTION supplier_mixed_scope_guard()''')
    op.execute('''CREATE TRIGGER supplier_mixed_scope_no_truncate BEFORE TRUNCATE
        ON supplier_mixed_scope_reviews FOR EACH STATEMENT EXECUTE FUNCTION supplier_mixed_scope_guard()''')


def downgrade():
    op.execute('LOCK TABLE supplier_mixed_scope_reviews IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN IF EXISTS(SELECT 1 FROM supplier_mixed_scope_reviews) THEN
        RAISE EXCEPTION 'Cannot discard mixed scope review evidence' USING ERRCODE='23514';
        END IF; END $$''')
    op.execute('DROP TABLE supplier_mixed_scope_reviews')
    op.execute('DROP FUNCTION supplier_mixed_scope_guard()')
    op.execute('DROP FUNCTION supplier_mixed_package_scope(TEXT,TEXT)')
