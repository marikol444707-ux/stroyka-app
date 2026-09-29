"""Add immutable warehouse mirrors of invoice payment roots; no data backfill."""
from alembic import op

revision = '0046_supplier_pay_attachments'
down_revision = '0045_supplier_payment_ledger'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE public.supplier_payment_attachments (
        id BIGSERIAL PRIMARY KEY,
        company_id INTEGER NOT NULL REFERENCES public.companies(id),
        request_id UUID NOT NULL,
        fingerprint TEXT NOT NULL CHECK(btrim(fingerprint)<>''),
        invoice_record_id BIGINT NOT NULL UNIQUE,
        warehouse_record_id BIGINT NOT NULL UNIQUE,
        mirrored_paid NUMERIC(14,2) NOT NULL CHECK(mirrored_paid BETWEEN 0 AND 999999999999.99),
        actor_id INTEGER NOT NULL REFERENCES public.users(id),
        actor_name TEXT NOT NULL CHECK(btrim(actor_name)<>''),
        reason TEXT NOT NULL CHECK(btrim(reason)<>''),
        created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(company_id,request_id),
        FOREIGN KEY(invoice_record_id,company_id) REFERENCES public.supplier_payment_documents(id,company_id),
        FOREIGN KEY(warehouse_record_id,company_id) REFERENCES public.supplier_payment_documents(id,company_id),
        CHECK(invoice_record_id<>warehouse_record_id)
    )''')
    op.execute('''CREATE TRIGGER supplier_payment_attachment_immutable
        BEFORE UPDATE OR DELETE ON public.supplier_payment_attachments
        FOR EACH ROW EXECUTE FUNCTION public.supplier_payment_immutable()''')
    op.execute('''CREATE TRIGGER supplier_payment_attachment_no_truncate
        BEFORE TRUNCATE ON public.supplier_payment_attachments
        FOR EACH STATEMENT EXECUTE FUNCTION public.supplier_payment_immutable()''')
    op.execute('''CREATE FUNCTION public.supplier_payment_attachment_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE source public.supplier_payment_documents; target public.supplier_payment_documents;
                invoice public.supplier_invoices; warehouse public.warehouse_invoices; computed_paid NUMERIC;
        BEGIN
        -- READ COMMITTED gives checks after lock acquisition a fresh snapshot.
        IF current_setting('transaction_isolation')<>'read committed' THEN
            RAISE EXCEPTION 'Attachment requires READ COMMITTED' USING ERRCODE='23514';
        END IF;
        SELECT * INTO source FROM public.supplier_payment_documents WHERE id=NEW.invoice_record_id;
        IF NOT FOUND OR source.document_kind<>'invoice' OR source.company_id<>NEW.company_id THEN
            RAISE EXCEPTION 'Invalid attachment invoice' USING ERRCODE='23514';
        END IF;
        SELECT * INTO target FROM public.supplier_payment_documents WHERE id=NEW.warehouse_record_id;
        IF NOT FOUND OR target.document_kind<>'warehouse' OR target.company_id<>NEW.company_id THEN
            RAISE EXCEPTION 'Invalid attachment warehouse' USING ERRCODE='23514';
        END IF;
        -- Physical rows first, matching baseline creation; immutable records next.
        SELECT * INTO invoice FROM public.supplier_invoices WHERE id=source.document_id FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Missing physical invoice' USING ERRCODE='23514'; END IF;
        SELECT * INTO warehouse FROM public.warehouse_invoices WHERE id=target.document_id FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Missing physical warehouse' USING ERRCODE='23514'; END IF;
        -- Conflicts with 0017 impact FOR SHARE, sealing the checked history.
        PERFORM id FROM public.supplier_payment_documents
            WHERE id IN (source.id,target.id) ORDER BY id FOR UPDATE;
        IF (source.company_id,source.payer_company_id,source.supplier_id,source.project_name,source.work_package,source.amount)
            IS DISTINCT FROM
           (target.company_id,target.payer_company_id,target.supplier_id,target.project_name,target.work_package,target.amount)
           OR (invoice.company_id,invoice.supplier_id,COALESCE(invoice.project_name,''),
               COALESCE(invoice.work_package,''),invoice.amount,invoice.warehouse_invoice_id)
            IS DISTINCT FROM
              (source.company_id,source.supplier_id,source.project_name,source.work_package,source.amount,target.document_id)
           OR (warehouse.company_id,warehouse.supplier_id,COALESCE(NULLIF(warehouse.project,''),warehouse.location,''),
               ''::TEXT,COALESCE(NULLIF(warehouse.total_with_vat,0),warehouse.total_base),warehouse.supplier_invoice_id)
            IS DISTINCT FROM
              (target.company_id,target.supplier_id,target.project_name,target.work_package,target.amount,source.document_id)
           OR COALESCE(invoice.status,'')='Аннулирован' OR COALESCE(warehouse.status,'')='Аннулирована' THEN
            RAISE EXCEPTION 'Attachment physical identity mismatch' USING ERRCODE='23514';
        END IF;
        IF EXISTS(SELECT 1 FROM public.supplier_payment_impacts WHERE document_record_id=target.id)
           OR EXISTS(SELECT 1 FROM public.supplier_payment_impacts i
               JOIN public.supplier_payment_operations o ON o.id=i.operation_id
               WHERE i.document_record_id=source.id AND (
                   o.document_kind<>'invoice' OR o.document_id<>source.document_id
                   OR EXISTS(SELECT 1 FROM public.supplier_payment_impacts sibling
                       WHERE sibling.operation_id=i.operation_id AND sibling.document_record_id<>source.id))) THEN
            RAISE EXCEPTION 'Attachment requires invoice-only history and unused warehouse' USING ERRCODE='23514';
        END IF;
        SELECT source.opening_paid+COALESCE(SUM(delta),0) INTO computed_paid
            FROM public.supplier_payment_impacts WHERE document_record_id=source.id;
        IF computed_paid IS DISTINCT FROM NEW.mirrored_paid OR computed_paid<0 OR computed_paid>source.amount
           OR COALESCE(invoice.paid_amount,0) IS DISTINCT FROM NEW.mirrored_paid
           OR (TG_WHEN='BEFORE' AND (
               target.opening_paid IS DISTINCT FROM COALESCE(warehouse.paid_amount,0)
               OR COALESCE(warehouse.paid_amount,0) NOT IN (0,NEW.mirrored_paid)))
           OR (TG_WHEN='AFTER' AND COALESCE(warehouse.paid_amount,0) IS DISTINCT FROM NEW.mirrored_paid) THEN
            RAISE EXCEPTION 'Attachment paid amounts mismatch' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
        END;
    $$''')
    op.execute('''CREATE TRIGGER supplier_payment_attachment_insert
        BEFORE INSERT ON public.supplier_payment_attachments
        FOR EACH ROW EXECUTE FUNCTION public.supplier_payment_attachment_guard()''')
    op.execute('''CREATE CONSTRAINT TRIGGER supplier_payment_attachment_complete
        AFTER INSERT ON public.supplier_payment_attachments DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION public.supplier_payment_attachment_guard()''')
    op.execute('''CREATE FUNCTION public.supplier_payment_attachment_impact_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        -- Row locks do not refresh a REPEATABLE READ/SERIALIZABLE snapshot:
        -- it could otherwise miss an attachment committed after that snapshot.
        IF current_setting('transaction_isolation')<>'read committed' THEN
            RAISE EXCEPTION 'Supplier payment impacts require READ COMMITTED' USING ERRCODE='23514';
        END IF;
        -- Serialize with attachment even when this INSERT started before its commit.
        PERFORM id FROM public.supplier_payment_documents WHERE id=NEW.document_record_id FOR SHARE;
        IF EXISTS(SELECT 1 FROM public.supplier_payment_attachments
                  WHERE warehouse_record_id=NEW.document_record_id) THEN
            RAISE EXCEPTION 'Attached warehouse is a derived payment mirror' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
        END;
    $$''')
    op.execute('''CREATE TRIGGER supplier_payment_attachment_impact_insert
        BEFORE INSERT ON public.supplier_payment_impacts
        FOR EACH ROW EXECUTE FUNCTION public.supplier_payment_attachment_impact_guard()''')


def downgrade():
    op.execute('LOCK TABLE public.supplier_payment_attachments IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN
        IF current_setting('transaction_isolation')<>'read committed' THEN
            RAISE EXCEPTION 'Attachment downgrade requires READ COMMITTED';
        END IF;
        IF EXISTS(SELECT 1 FROM public.supplier_payment_attachments) THEN
            RAISE EXCEPTION 'Cannot remove supplier payment attachments';
        END IF;
    END $$''')
    op.execute('DROP TRIGGER supplier_payment_attachment_impact_insert ON public.supplier_payment_impacts')
    op.execute('DROP FUNCTION public.supplier_payment_attachment_impact_guard()')
    op.execute('DROP TABLE public.supplier_payment_attachments')
    op.execute('DROP FUNCTION public.supplier_payment_attachment_guard()')
