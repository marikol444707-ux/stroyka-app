"""Explicit immutable legacy opening confirmations; no historical backfill."""
from alembic import op

revision = '0057_supplier_openings'
down_revision = '0056_supplier_receipt_vat'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE public.supplier_opening_confirmations (
        id BIGSERIAL PRIMARY KEY,
        company_id INTEGER NOT NULL REFERENCES public.companies(id),
        request_id UUID NOT NULL,
        fingerprint TEXT NOT NULL CHECK(fingerprint ~ '^[a-f0-9]{64}$'),
        document_record_id BIGINT NOT NULL UNIQUE,
        actor_id INTEGER NOT NULL REFERENCES public.users(id),
        actor_name TEXT NOT NULL CHECK(btrim(actor_name)<>''),
        reason TEXT NOT NULL CHECK(length(btrim(reason)) BETWEEN 1 AND 1000),
        source_snapshot JSONB NOT NULL CHECK(jsonb_typeof(source_snapshot)='object'),
        reviewed_hash TEXT NOT NULL CHECK(reviewed_hash ~ '^[a-f0-9]{64}$'),
        created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(company_id,request_id),
        FOREIGN KEY(document_record_id,company_id)
            REFERENCES public.supplier_payment_documents(id,company_id)
    )''')
    op.execute('''CREATE FUNCTION public.supplier_opening_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE d public.supplier_payment_documents; snap JSONB; born XID;
        BEGIN
        SELECT * INTO d FROM public.supplier_payment_documents WHERE id=NEW.document_record_id;
        SELECT xmin INTO born FROM public.supplier_payment_documents WHERE id=NEW.document_record_id;
        SELECT to_jsonb(i) INTO snap FROM public.supplier_invoices i
            WHERE i.id=d.document_id AND i.company_id=NEW.company_id;
        IF d.document_kind IS DISTINCT FROM 'invoice' OR snap IS NULL
            OR snap IS DISTINCT FROM NEW.source_snapshot
            OR born::text::numeric IS DISTINCT FROM mod(pg_current_xact_id()::text::numeric,4294967296)
            OR snap->>'paid_amount' IS NULL
            OR (snap->>'paid_amount')::numeric IS DISTINCT FROM d.opening_paid
            OR snap->>'warehouse_invoice_id' IS NOT NULL
            OR EXISTS(SELECT 1 FROM public.warehouse_invoices WHERE supplier_invoice_id=d.document_id)
            OR EXISTS(SELECT 1 FROM public.supplier_invoice_line_specs WHERE invoice_id=d.document_id)
            OR EXISTS(SELECT 1 FROM public.supplier_payment_impacts WHERE document_record_id=d.id) THEN
            RAISE EXCEPTION 'Opening confirmation requires a new exact standalone legacy baseline' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
        END; $$''')
    op.execute('''CREATE TRIGGER supplier_opening_insert BEFORE INSERT ON public.supplier_opening_confirmations
        FOR EACH ROW EXECUTE FUNCTION public.supplier_opening_guard()''')
    op.execute('''CREATE TRIGGER supplier_opening_immutable BEFORE UPDATE OR DELETE ON public.supplier_opening_confirmations
        FOR EACH ROW EXECUTE FUNCTION public.supplier_payment_immutable()''')
    op.execute('''CREATE TRIGGER supplier_opening_no_truncate BEFORE TRUNCATE ON public.supplier_opening_confirmations
        FOR EACH STATEMENT EXECUTE FUNCTION public.supplier_payment_immutable()''')


def downgrade():
    op.execute('''LOCK TABLE public.supplier_opening_confirmations IN ACCESS EXCLUSIVE MODE''')
    op.execute('''DO $$ BEGIN IF EXISTS(SELECT 1 FROM public.supplier_opening_confirmations) THEN
        RAISE EXCEPTION 'Cannot remove historical opening confirmations' USING ERRCODE='23514';
        END IF; END $$''')
    op.execute('DROP TABLE public.supplier_opening_confirmations')
    op.execute('DROP FUNCTION public.supplier_opening_guard()')
