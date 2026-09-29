"""Audited line review for unused legacy invoices; no backfill or financial writes."""
from alembic import op

revision = '0063_supplier_legacy_lines'
down_revision = '0062_supplier_legacy_binding'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE public.supplier_legacy_line_reviews (
        id BIGSERIAL PRIMARY KEY,
        invoice_id INTEGER NOT NULL UNIQUE REFERENCES public.supplier_invoices(id),
        company_id INTEGER NOT NULL REFERENCES public.companies(id),
        request_id UUID NOT NULL UNIQUE,
        source_file_id INTEGER NOT NULL REFERENCES public.file_ownership(id),
        actor_id INTEGER NOT NULL REFERENCES public.users(id),
        reason TEXT NOT NULL CHECK(btrim(reason)<>''),
        command_json JSONB NOT NULL CHECK(jsonb_typeof(command_json)='object'),
        reviewed_payload JSONB NOT NULL CHECK(jsonb_typeof(reviewed_payload)='object'
            AND (reviewed_payload->>'provenance') IS NOT DISTINCT FROM 'legacy_original_review'),
        source_identity JSONB NOT NULL,
        creation_xid XID8 NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        UNIQUE(id,company_id,invoice_id)
    )''')
    op.execute('''ALTER TABLE public.supplier_invoice_line_specs
        ADD COLUMN legacy_review_id BIGINT UNIQUE REFERENCES public.supplier_legacy_line_reviews(id)''')
    op.execute('''CREATE FUNCTION public.supplier_legacy_line_review_insert() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE i public.supplier_invoices;
        BEGIN
        PERFORM public.supplier_allocation_lock(NEW.company_id);
        SELECT * INTO i FROM public.supplier_invoices WHERE id=NEW.invoice_id FOR UPDATE;
        IF NOT FOUND OR i.company_id IS DISTINCT FROM NEW.company_id
            OR i.status NOT IN ('На утверждении','Утверждён') OR i.paid_amount IS DISTINCT FROM 0::NUMERIC
            OR i.contract_version_id IS NULL OR i.warehouse_invoice_id IS NOT NULL
            OR i.vat_amount IS NULL
            OR EXISTS(SELECT 1 FROM public.supplier_payment_documents WHERE document_kind='invoice' AND document_id=i.id)
            OR EXISTS(SELECT 1 FROM public.warehouse_invoices WHERE supplier_invoice_id=i.id)
            OR EXISTS(SELECT 1 FROM public.supply_deliveries WHERE source_supplier_invoice_id=i.id OR offer_id=i.offer_id)
            OR EXISTS(SELECT 1 FROM public.supplier_invoice_line_specs WHERE invoice_id=i.id) THEN
            RAISE EXCEPTION 'Legacy line review requires an unused bound invoice' USING ERRCODE='23514'; END IF;
        PERFORM 1 FROM public.supplier_contract_versions c
            JOIN public.supplier_offers o ON o.id=c.offer_id AND o.company_id=c.company_id
            JOIN public.supply_requests q ON q.id=o.request_id AND q.company_id=o.company_id
            WHERE c.id=i.contract_version_id AND c.company_id=i.company_id AND o.id=i.offer_id
                AND q.id=i.request_id AND o.supplier_id=i.supplier_id AND q.project=i.project_name
                AND c.reviewed_at IS NOT NULL AND c.reviewed_by_id IS NOT NULL
            FOR SHARE OF c,o,q;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Legacy line review bound source differs' USING ERRCODE='23514'; END IF;
        PERFORM 1 FROM public.file_ownership WHERE id=NEW.source_file_id
            AND company_id=NEW.company_id AND deletion_status='active' FOR SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Legacy line review requires owned original' USING ERRCODE='23514'; END IF;
        NEW.source_identity:=public.supplier_invoice_line_identity(i);
        NEW.creation_xid:=pg_current_xact_id(); NEW.created_at:=clock_timestamp();
        RETURN NEW;
        END $$''')
    op.execute('''CREATE TRIGGER legacy_line_review_insert BEFORE INSERT ON public.supplier_legacy_line_reviews
        FOR EACH ROW EXECUTE FUNCTION public.supplier_legacy_line_review_insert()''')
    for action, level in (('UPDATE OR DELETE', 'ROW'), ('TRUNCATE', 'STATEMENT')):
        suffix='immutable' if level=='ROW' else 'no_truncate'
        op.execute(f'''CREATE TRIGGER legacy_line_review_{suffix} BEFORE {action} ON public.supplier_legacy_line_reviews
            FOR EACH {level} EXECUTE FUNCTION public.supplier_invoice_line_immutable()''')
    # Preserve the original birth-only function (including the VAT upgrade).
    # Only headers with a distinct, same-transaction review use the new guard.
    op.execute('DROP TRIGGER invoice_line_spec_insert ON public.supplier_invoice_line_specs')
    op.execute('''CREATE TRIGGER invoice_line_spec_insert BEFORE INSERT ON public.supplier_invoice_line_specs
        FOR EACH ROW WHEN (NEW.legacy_review_id IS NULL)
        EXECUTE FUNCTION public.supplier_invoice_line_insert()''')
    op.execute('''CREATE FUNCTION public.supplier_legacy_line_spec_insert() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE i public.supplier_invoices; r public.supplier_legacy_line_reviews;
        BEGIN
        PERFORM public.supplier_allocation_lock(NEW.company_id);
        SELECT * INTO r FROM public.supplier_legacy_line_reviews WHERE id=NEW.legacy_review_id;
        IF NOT FOUND OR r.creation_xid IS DISTINCT FROM pg_current_xact_id()
            OR r.invoice_id IS DISTINCT FROM NEW.invoice_id OR r.company_id IS DISTINCT FROM NEW.company_id
            OR r.reviewed_payload IS DISTINCT FROM NEW.source_payload THEN
            RAISE EXCEPTION 'Legacy specification requires current exact review' USING ERRCODE='23514'; END IF;
        SELECT * INTO i FROM public.supplier_invoices WHERE id=NEW.invoice_id FOR UPDATE;
        IF NOT FOUND OR public.supplier_invoice_line_identity(i) IS DISTINCT FROM r.source_identity
            OR NEW.amount IS DISTINCT FROM i.amount::NUMERIC
            OR NEW.amount IS DISTINCT FROM (r.reviewed_payload->>'amount')::NUMERIC
            OR i.vat_amount::NUMERIC IS DISTINCT FROM (r.reviewed_payload->>'vatAmount')::NUMERIC
            OR NEW.row_count IS DISTINCT FROM jsonb_array_length(r.reviewed_payload->'lines') THEN
            RAISE EXCEPTION 'Legacy specification identity differs' USING ERRCODE='23514'; END IF;
        NEW.creation_xid:=pg_current_xact_id(); NEW.created_at:=clock_timestamp();
        NEW.source_identity:=r.source_identity;
        RETURN NEW;
        END $$''')
    op.execute('''CREATE TRIGGER legacy_line_spec_insert BEFORE INSERT ON public.supplier_invoice_line_specs
        FOR EACH ROW WHEN (NEW.legacy_review_id IS NOT NULL)
        EXECUTE FUNCTION public.supplier_legacy_line_spec_insert()''')
    op.execute('''CREATE FUNCTION public.supplier_legacy_line_review_complete() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE h public.supplier_invoice_line_specs;
        BEGIN
        SELECT * INTO h FROM public.supplier_invoice_line_specs WHERE legacy_review_id=NEW.id;
        IF NOT FOUND OR h.invoice_id IS DISTINCT FROM NEW.invoice_id OR h.company_id IS DISTINCT FROM NEW.company_id
            OR h.source_payload IS DISTINCT FROM NEW.reviewed_payload THEN
            RAISE EXCEPTION 'Legacy review requires its sealed specification' USING ERRCODE='23514'; END IF;
        IF h.row_count IS DISTINCT FROM (SELECT count(DISTINCT (v->>'lineNo')::INT)
            FROM jsonb_array_elements(NEW.reviewed_payload->'lines') v) THEN
            RAISE EXCEPTION 'Legacy review line numbers differ' USING ERRCODE='23514'; END IF;
        IF EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.reviewed_payload->'lines') expected
            LEFT JOIN public.supplier_invoice_lines l ON l.spec_id=h.id AND l.line_no=(expected->>'lineNo')::INT
            WHERE l.id IS NULL OR l.source_request_position IS DISTINCT FROM (expected->>'sourceRequestPosition')::INT
                OR l.source_offer_position IS DISTINCT FROM (expected->>'sourceOfferPosition')::INT
                OR l.material_name IS DISTINCT FROM expected->>'materialName'
                OR l.unit IS DISTINCT FROM expected->>'unit' OR l.work_package IS DISTINCT FROM expected->>'workPackage'
                OR l.quantity IS DISTINCT FROM (expected->>'quantity')::NUMERIC
                OR l.unit_price IS DISTINCT FROM (expected->>'unitPrice')::NUMERIC
                OR l.amount IS DISTINCT FROM (expected->>'amount')::NUMERIC
                OR l.vat_amount IS DISTINCT FROM (expected->>'vatAmount')::NUMERIC) THEN
            RAISE EXCEPTION 'Legacy reviewed lines differ from specification' USING ERRCODE='23514'; END IF;
        RETURN NULL;
        END $$''')
    op.execute('''CREATE CONSTRAINT TRIGGER legacy_line_review_complete AFTER INSERT ON public.supplier_legacy_line_reviews
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.supplier_legacy_line_review_complete()''')


def downgrade():
    raise RuntimeError('Refuse automatic removal of original-document review evidence')
