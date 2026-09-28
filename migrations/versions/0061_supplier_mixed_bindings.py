"""Atomic binding of exact mixed review evidence to paired opening records."""
from alembic import op
revision = '0061_supplier_mixed_bindings'
down_revision = '0060_supplier_mixed_scopes'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('LOCK TABLE public.supplier_payment_documents IN ACCESS EXCLUSIVE MODE')
    op.execute("""CREATE TABLE public.supplier_mixed_binding_guard_version AS
        SELECT pg_get_functiondef('public.supplier_payment_document_guard()'::regprocedure) AS definition""")
    op.execute("""CREATE TABLE public.supplier_mixed_opening_bindings (
        review_id BIGINT PRIMARY KEY REFERENCES public.supplier_mixed_scope_reviews(id),
        company_id INTEGER NOT NULL REFERENCES public.companies(id),
        invoice_record_id BIGINT NOT NULL UNIQUE,
        warehouse_record_id BIGINT NOT NULL UNIQUE,
        confirmation_id BIGINT NOT NULL UNIQUE REFERENCES public.supplier_opening_confirmations(id)
            DEFERRABLE INITIALLY DEFERRED,
        creation_xid XID8 NOT NULL DEFAULT pg_current_xact_id(),
        CHECK(invoice_record_id<>warehouse_record_id),
        FOREIGN KEY(invoice_record_id,company_id) REFERENCES public.supplier_payment_documents(id,company_id)
            DEFERRABLE INITIALLY DEFERRED,
        FOREIGN KEY(warehouse_record_id,company_id) REFERENCES public.supplier_payment_documents(id,company_id)
            DEFERRABLE INITIALLY DEFERRED
    )""")
    op.execute("""CREATE FUNCTION public.supplier_mixed_binding_insert_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE r public.supplier_mixed_scope_reviews; i public.supplier_invoices; w public.warehouse_invoices;
        BEGIN
        PERFORM public.supplier_allocation_lock(NEW.company_id);
        NEW.creation_xid:=pg_current_xact_id();
        SELECT * INTO r FROM public.supplier_mixed_scope_reviews WHERE id=NEW.review_id;
        SELECT * INTO i FROM public.supplier_invoices WHERE id=r.invoice_id FOR UPDATE;
        SELECT * INTO w FROM public.warehouse_invoices WHERE id=r.warehouse_id FOR UPDATE;
        IF r.id IS NULL OR r.company_id IS DISTINCT FROM NEW.company_id
            OR i.company_id IS DISTINCT FROM NEW.company_id OR w.company_id IS DISTINCT FROM NEW.company_id
            OR r.invoice_snapshot IS DISTINCT FROM to_jsonb(i)
            OR r.warehouse_snapshot IS DISTINCT FROM to_jsonb(w)
            OR r.package_scope IS DISTINCT FROM public.supplier_mixed_package_scope(w.items::text,i.work_package)
            OR EXISTS(SELECT 1 FROM public.supplier_payment_documents WHERE
                (document_kind='invoice' AND document_id=i.id) OR (document_kind='warehouse' AND document_id=w.id))
            OR EXISTS(SELECT 1 FROM public.supplier_invoice_line_specs WHERE invoice_id=i.id) THEN
            RAISE EXCEPTION 'Mixed opening requires current unregistered review evidence' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER supplier_mixed_binding_insert BEFORE INSERT ON public.supplier_mixed_opening_bindings
        FOR EACH ROW EXECUTE FUNCTION public.supplier_mixed_binding_insert_guard()""")
    op.execute("""CREATE TRIGGER supplier_mixed_binding_immutable BEFORE UPDATE OR DELETE ON public.supplier_mixed_opening_bindings
        FOR EACH ROW EXECUTE FUNCTION public.supplier_payment_immutable()""")
    op.execute("""CREATE TRIGGER supplier_mixed_binding_no_truncate BEFORE TRUNCATE ON public.supplier_mixed_opening_bindings
        FOR EACH STATEMENT EXECUTE FUNCTION public.supplier_payment_immutable()""")
    op.execute("""CREATE FUNCTION public.supplier_mixed_binding_complete_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE r public.supplier_mixed_scope_reviews; c public.supplier_opening_confirmations;
                i public.supplier_payment_documents; w public.supplier_payment_documents;
        BEGIN
        SELECT * INTO r FROM public.supplier_mixed_scope_reviews WHERE id=NEW.review_id;
        SELECT * INTO c FROM public.supplier_opening_confirmations WHERE id=NEW.confirmation_id;
        SELECT * INTO i FROM public.supplier_payment_documents WHERE id=NEW.invoice_record_id;
        SELECT * INTO w FROM public.supplier_payment_documents WHERE id=NEW.warehouse_record_id;
        IF c.id IS NULL OR i.id IS NULL OR w.id IS NULL
            OR (c.company_id,c.document_record_id,c.warehouse_record_id)
                IS DISTINCT FROM (NEW.company_id,i.id,w.id)
            OR (i.document_kind,i.document_id) IS DISTINCT FROM ('invoice'::text,r.invoice_id)
            OR (w.document_kind,w.document_id) IS DISTINCT FROM ('warehouse'::text,r.warehouse_id)
            OR r.invoice_snapshot IS DISTINCT FROM (
                SELECT to_jsonb(source) FROM public.supplier_invoices source WHERE source.id=r.invoice_id)
            OR r.warehouse_snapshot IS DISTINCT FROM (
                SELECT to_jsonb(source) FROM public.warehouse_invoices source WHERE source.id=r.warehouse_id)
            OR c.source_snapshot IS DISTINCT FROM r.invoice_snapshot
            OR c.warehouse_snapshot IS DISTINCT FROM r.warehouse_snapshot
            OR EXISTS(SELECT 1 FROM public.supplier_payment_impacts
                WHERE document_record_id IN (i.id,w.id)) THEN
            RAISE EXCEPTION 'Mixed binding requires complete paired opening without cash impacts' USING ERRCODE='23514';
        END IF;
        RETURN NULL;
        END $$""")
    op.execute("""CREATE CONSTRAINT TRIGGER supplier_mixed_binding_complete
        AFTER INSERT ON public.supplier_mixed_opening_bindings DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION public.supplier_mixed_binding_complete_guard()""")
    op.execute("""CREATE FUNCTION public.supplier_payment_warehouse_package_bound(target_warehouse_id INTEGER, items_text TEXT)
        RETURNS TEXT LANGUAGE plpgsql AS $$
        DECLARE b public.supplier_mixed_opening_bindings; r public.supplier_mixed_scope_reviews;
                live_snapshot JSONB;
        BEGIN
        SELECT binding.* INTO b FROM public.supplier_mixed_opening_bindings binding
            JOIN public.supplier_mixed_scope_reviews evidence ON evidence.id=binding.review_id
            WHERE evidence.warehouse_id=target_warehouse_id;
        IF b.review_id IS NULL THEN
            RETURN public.supplier_payment_warehouse_package(items_text);
        END IF;
        SELECT * INTO r FROM public.supplier_mixed_scope_reviews WHERE id=b.review_id;
        SELECT to_jsonb(w) INTO live_snapshot FROM public.warehouse_invoices w WHERE w.id=target_warehouse_id;
        IF b.creation_xid IS DISTINCT FROM pg_current_xact_id()
            OR live_snapshot IS DISTINCT FROM r.warehouse_snapshot THEN
            RAISE EXCEPTION 'Mixed baseline requires same-transaction exact review binding' USING ERRCODE='23514';
        END IF;
        RETURN r.invoice_snapshot->>'work_package';
        END $$""")
    op.execute("""DO $$ DECLARE definition TEXT; old TEXT:='public.supplier_payment_warehouse_package(items)';
        BEGIN
        SELECT v.definition INTO definition FROM public.supplier_mixed_binding_guard_version v;
        IF position(old IN definition)=0 THEN RAISE EXCEPTION 'Unexpected baseline guard'; END IF;
        EXECUTE replace(definition,old,'public.supplier_payment_warehouse_package_bound(id,items::text)');
        END $$""")


def downgrade():
    op.execute('LOCK TABLE public.supplier_mixed_opening_bindings, public.supplier_payment_documents IN ACCESS EXCLUSIVE MODE')
    op.execute("""DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM public.supplier_mixed_opening_bindings) THEN
            RAISE EXCEPTION 'Cannot discard mixed opening bindings' USING ERRCODE='23514';
        END IF;
        EXECUTE (SELECT definition FROM public.supplier_mixed_binding_guard_version);
        END $$""")
    op.execute('DROP TABLE public.supplier_mixed_opening_bindings')
    op.execute('DROP FUNCTION public.supplier_payment_warehouse_package_bound(INTEGER,TEXT)')
    op.execute('DROP FUNCTION public.supplier_mixed_binding_insert_guard()')
    op.execute('DROP FUNCTION public.supplier_mixed_binding_complete_guard()')
    op.execute('DROP TABLE public.supplier_mixed_binding_guard_version')
