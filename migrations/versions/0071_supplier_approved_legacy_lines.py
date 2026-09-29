"""Allow line review after approval while the invoice is still unused."""
from alembic import op

revision = '0071_approved_legacy_lines'
down_revision = '0070_approved_legacy_binding'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE OR REPLACE FUNCTION public.supplier_legacy_line_review_insert() RETURNS trigger LANGUAGE plpgsql AS $$
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


def downgrade():
    raise RuntimeError('Approved legacy line reviews may already exist and cannot be downgraded safely')
