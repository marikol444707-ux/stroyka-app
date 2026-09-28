"""Confirm reciprocal legacy invoice/receipt openings without cash or relinking."""
from alembic import op
revision = '0058_supplier_paired_openings'
down_revision = '0057_supplier_opening_confirmations'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE public.supplier_paired_opening_guard_version AS
        SELECT pg_get_functiondef('public.supplier_opening_guard()'::regprocedure) AS definition''')
    op.execute('''ALTER TABLE public.supplier_opening_confirmations
        ADD COLUMN warehouse_record_id BIGINT UNIQUE,
        ADD COLUMN warehouse_snapshot JSONB,
        ADD CONSTRAINT opening_warehouse_company FOREIGN KEY(warehouse_record_id,company_id)
            REFERENCES public.supplier_payment_documents(id,company_id),
        ADD CONSTRAINT opening_warehouse_evidence CHECK(
            (warehouse_record_id IS NULL AND warehouse_snapshot IS NULL) OR
            (warehouse_record_id IS NOT NULL AND warehouse_snapshot IS NOT NULL AND jsonb_typeof(warehouse_snapshot)='object'))''')
    op.execute('''CREATE OR REPLACE FUNCTION public.supplier_opening_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE d public.supplier_payment_documents; w public.supplier_payment_documents;
                snap JSONB; wsnap JSONB; born XID; wborn XID;
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
            OR EXISTS(SELECT 1 FROM public.supplier_invoice_line_specs WHERE invoice_id=d.document_id)
            OR EXISTS(SELECT 1 FROM public.supplier_payment_impacts WHERE document_record_id=d.id) THEN
            RAISE EXCEPTION 'Opening requires a new exact legacy baseline' USING ERRCODE='23514';
        END IF;
        IF NEW.warehouse_record_id IS NULL THEN
            IF snap->>'warehouse_invoice_id' IS NOT NULL
                OR EXISTS(SELECT 1 FROM public.warehouse_invoices WHERE supplier_invoice_id=d.document_id) THEN
                RAISE EXCEPTION 'Linked opening requires both documents' USING ERRCODE='23514';
            END IF;
        ELSE
            SELECT * INTO w FROM public.supplier_payment_documents WHERE id=NEW.warehouse_record_id;
            SELECT xmin INTO wborn FROM public.supplier_payment_documents WHERE id=NEW.warehouse_record_id;
            SELECT to_jsonb(i) INTO wsnap FROM public.warehouse_invoices i
                WHERE i.id=w.document_id AND i.company_id=NEW.company_id;
            IF w.document_kind IS DISTINCT FROM 'warehouse' OR wsnap IS NULL
                OR wsnap IS DISTINCT FROM NEW.warehouse_snapshot
                OR wborn::text::numeric IS DISTINCT FROM mod(pg_current_xact_id()::text::numeric,4294967296)
                OR (w.company_id,w.payer_company_id,w.supplier_id,w.project_name,w.work_package,w.amount,w.opening_paid)
                    IS DISTINCT FROM (d.company_id,d.payer_company_id,d.supplier_id,d.project_name,d.work_package,d.amount,d.opening_paid)
                OR wsnap->>'paid_amount' IS NULL
                OR (wsnap->>'paid_amount')::numeric IS DISTINCT FROM w.opening_paid
                OR (snap->>'warehouse_invoice_id')::int IS DISTINCT FROM w.document_id
                OR (wsnap->>'supplier_invoice_id')::int IS DISTINCT FROM d.document_id
                OR EXISTS(SELECT 1 FROM public.warehouse_invoices WHERE supplier_invoice_id=d.document_id AND id<>w.document_id)
                OR EXISTS(SELECT 1 FROM public.supplier_invoices WHERE warehouse_invoice_id=w.document_id AND id<>d.document_id)
                OR EXISTS(SELECT 1 FROM public.supplier_payment_impacts WHERE document_record_id=w.id) THEN
                RAISE EXCEPTION 'Opening pair requires exact reciprocal unregistered documents' USING ERRCODE='23514';
            END IF;
        END IF;
        RETURN NEW;
        END; $$''')


def downgrade():
    op.execute('LOCK TABLE public.supplier_opening_confirmations IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM public.supplier_opening_confirmations WHERE warehouse_record_id IS NOT NULL) THEN
            RAISE EXCEPTION 'Cannot discard paired opening history' USING ERRCODE='23514';
        END IF;
        EXECUTE (SELECT definition FROM public.supplier_paired_opening_guard_version);
        END $$''')
    op.execute('ALTER TABLE public.supplier_opening_confirmations DROP COLUMN warehouse_record_id, DROP COLUMN warehouse_snapshot')
    op.execute('DROP TABLE public.supplier_paired_opening_guard_version')
