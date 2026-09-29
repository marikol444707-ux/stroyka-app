"""Add opt-in immutable supplier payment evidence; never backfill customer data."""
from alembic import op

revision = '0045_supplier_payment_ledger'
down_revision = '0044_supplier_document_bindings'
branch_labels = None
depends_on = None
TABLES = ('supplier_payment_documents', 'supplier_payment_operations', 'supplier_payment_impacts')


def upgrade():
    op.execute('''CREATE TABLE public.supplier_payment_documents (
        id BIGSERIAL PRIMARY KEY,
        company_id INTEGER NOT NULL REFERENCES public.companies(id),
        document_kind TEXT NOT NULL CHECK(document_kind IN ('invoice','warehouse')),
        document_id INTEGER NOT NULL CHECK(document_id>0),
        payer_company_id INTEGER NOT NULL REFERENCES public.companies(id),
        supplier_id INTEGER NOT NULL REFERENCES public.suppliers(id),
        project_name TEXT NOT NULL,
        work_package TEXT NOT NULL DEFAULT '',
        amount NUMERIC(14,2) NOT NULL CHECK(amount>0 AND amount<=999999999999.99),
        opening_paid NUMERIC(14,2) NOT NULL CHECK(opening_paid>=0 AND opening_paid<=amount),
        created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(company_id,document_kind,document_id), UNIQUE(id,company_id)
    )''')
    op.execute('''CREATE TABLE public.supplier_payment_operations (
        id BIGSERIAL PRIMARY KEY,
        company_id INTEGER NOT NULL REFERENCES public.companies(id),
        request_id UUID NOT NULL,
        fingerprint TEXT NOT NULL CHECK(btrim(fingerprint)<>''),
        document_kind TEXT NOT NULL CHECK(document_kind IN ('invoice','warehouse')),
        document_id INTEGER NOT NULL CHECK(document_id>0),
        kind TEXT NOT NULL CHECK(kind IN ('payment','reversal')),
        amount NUMERIC(14,2) NOT NULL CHECK(amount>0 AND amount<=999999999999.99),
        payer_company_id INTEGER NOT NULL REFERENCES public.companies(id),
        supplier_id INTEGER NOT NULL REFERENCES public.suppliers(id),
        project_payment_id INTEGER NOT NULL UNIQUE REFERENCES public.project_payments(id),
        reverses_id BIGINT UNIQUE,
        actor_id INTEGER NOT NULL REFERENCES public.users(id),
        actor_name TEXT NOT NULL,
        reason TEXT NOT NULL CHECK(btrim(reason)<>''),
        payment_date DATE NOT NULL,
        creation_xid XID8 NOT NULL DEFAULT pg_current_xact_id(),
        created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(company_id,request_id), UNIQUE(id,company_id),
        FOREIGN KEY(reverses_id,company_id) REFERENCES public.supplier_payment_operations(id,company_id),
        CHECK((kind='payment' AND reverses_id IS NULL) OR (kind='reversal' AND reverses_id IS NOT NULL)),
        CHECK(reverses_id IS NULL OR reverses_id<>id)
    )''')
    op.execute('''CREATE TABLE public.supplier_payment_impacts (
        operation_id BIGINT NOT NULL,
        document_record_id BIGINT NOT NULL,
        company_id INTEGER NOT NULL,
        delta NUMERIC(14,2) NOT NULL CHECK(delta<>0 AND delta BETWEEN -999999999999.99 AND 999999999999.99),
        PRIMARY KEY(operation_id,document_record_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES public.supplier_payment_operations(id,company_id),
        FOREIGN KEY(document_record_id,company_id) REFERENCES public.supplier_payment_documents(id,company_id)
    )''')
    op.execute('''CREATE INDEX supplier_payment_document_history
        ON public.supplier_payment_impacts(document_record_id,operation_id)''')
    op.execute('''CREATE FUNCTION public.supplier_payment_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Supplier payment evidence is immutable' USING ERRCODE='23514'; END;
    $$''')
    for table in TABLES:
        op.execute(f'''CREATE TRIGGER supplier_payment_immutable BEFORE UPDATE OR DELETE ON public.{table}
            FOR EACH ROW EXECUTE FUNCTION public.supplier_payment_immutable()''')
        op.execute(f'''CREATE TRIGGER supplier_payment_no_truncate BEFORE TRUNCATE ON public.{table}
            FOR EACH STATEMENT EXECUTE FUNCTION public.supplier_payment_immutable()''')
    # Warehouse rows have no work_package column: this first slice supports only
    # the empty package. A future adapter must derive an authoritative package
    # or fail closed before activation; it must not guess from display text.
    op.execute('''CREATE FUNCTION public.supplier_payment_document_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE source_company INTEGER; source_supplier INTEGER; source_amount NUMERIC;
                source_paid NUMERIC; source_project TEXT; source_package TEXT;
        BEGIN
        IF NEW.document_kind='invoice' THEN
            SELECT company_id,supplier_id,amount,COALESCE(paid_amount,0),
                   COALESCE(project_name,''),COALESCE(work_package,'')
              INTO source_company,source_supplier,source_amount,source_paid,source_project,source_package
              FROM public.supplier_invoices WHERE id=NEW.document_id FOR UPDATE;
        ELSIF NEW.document_kind='warehouse' THEN
            SELECT company_id,supplier_id,COALESCE(NULLIF(total_with_vat,0),total_base),
                   COALESCE(paid_amount,0),COALESCE(NULLIF(project,''),location,''),''::TEXT
              INTO source_company,source_supplier,source_amount,source_paid,source_project,source_package
              FROM public.warehouse_invoices WHERE id=NEW.document_id FOR UPDATE;
        ELSE
            RAISE EXCEPTION 'Unknown supplier payment document' USING ERRCODE='23514';
        END IF;
        IF NOT FOUND OR (source_company,source_supplier,source_amount,source_paid,source_project,source_package)
            IS DISTINCT FROM (NEW.company_id,NEW.supplier_id,NEW.amount,NEW.opening_paid,NEW.project_name,NEW.work_package) THEN
            RAISE EXCEPTION 'Supplier payment baseline does not match document' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
        END;
    $$''')
    op.execute('''CREATE TRIGGER supplier_payment_document_insert BEFORE INSERT ON public.supplier_payment_documents
        FOR EACH ROW EXECUTE FUNCTION public.supplier_payment_document_guard()''')
    op.execute('''CREATE FUNCTION public.supplier_payment_operation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE payment public.project_payments; original public.supplier_payment_operations; signed_amount NUMERIC;
        BEGIN
        -- Database-owned top-level transaction identity, including savepoints.
        -- Override explicit input; callers cannot keep an operation open for a future transaction.
        NEW.creation_xid := pg_current_xact_id();
        signed_amount := CASE WHEN NEW.kind='reversal' THEN -NEW.amount ELSE NEW.amount END;
        SELECT * INTO payment FROM public.project_payments WHERE id=NEW.project_payment_id FOR SHARE;
        IF NOT FOUND OR (payment.company_id,payment.amount,payment.added_by,payment.date)
            IS DISTINCT FROM (NEW.company_id,signed_amount,NEW.actor_name,NEW.payment_date::TEXT) THEN
            RAISE EXCEPTION 'Supplier operation does not match project payment' USING ERRCODE='23514';
        END IF;
        IF NEW.kind='reversal' THEN
            SELECT * INTO original FROM public.supplier_payment_operations
              WHERE id=NEW.reverses_id AND company_id=NEW.company_id FOR SHARE;
            IF NOT FOUND OR original.kind<>'payment' OR
                (original.amount,original.payer_company_id,original.supplier_id,original.document_kind,original.document_id)
                IS DISTINCT FROM (NEW.amount,NEW.payer_company_id,NEW.supplier_id,NEW.document_kind,NEW.document_id) THEN
                RAISE EXCEPTION 'Invalid full supplier payment reversal' USING ERRCODE='23514';
            END IF;
        END IF;
        RETURN NEW;
        END;
    $$''')
    op.execute('''CREATE TRIGGER supplier_payment_operation_insert BEFORE INSERT ON public.supplier_payment_operations
        FOR EACH ROW EXECUTE FUNCTION public.supplier_payment_operation_guard()''')
    op.execute('''CREATE FUNCTION public.supplier_payment_impact_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE operation public.supplier_payment_operations; document public.supplier_payment_documents;
                payment public.project_payments;
        BEGIN
        SELECT * INTO operation FROM public.supplier_payment_operations
          WHERE id=NEW.operation_id AND company_id=NEW.company_id FOR SHARE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Missing supplier operation' USING ERRCODE='23514'; END IF;
        IF operation.creation_xid IS DISTINCT FROM pg_current_xact_id() THEN
            RAISE EXCEPTION 'Committed supplier operation impacts are sealed' USING ERRCODE='23514';
        END IF;
        SELECT * INTO document FROM public.supplier_payment_documents
          WHERE id=NEW.document_record_id AND company_id=NEW.company_id FOR SHARE;
        IF NOT FOUND OR (document.payer_company_id,document.supplier_id)
            IS DISTINCT FROM (operation.payer_company_id,operation.supplier_id)
            OR NEW.delta IS DISTINCT FROM (CASE WHEN operation.kind='reversal' THEN -operation.amount ELSE operation.amount END) THEN
            RAISE EXCEPTION 'Invalid supplier payment impact' USING ERRCODE='23514';
        END IF;
        SELECT * INTO payment FROM public.project_payments WHERE id=operation.project_payment_id FOR SHARE;
        IF NOT FOUND OR (payment.project_name,COALESCE(payment.work_package,''))
            IS DISTINCT FROM (document.project_name,document.work_package) THEN
            RAISE EXCEPTION 'Supplier impact project mismatch' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
        END;
    $$''')
    op.execute('''CREATE TRIGGER supplier_payment_impact_insert BEFORE INSERT ON public.supplier_payment_impacts
        FOR EACH ROW EXECUTE FUNCTION public.supplier_payment_impact_guard()''')
    op.execute('''CREATE FUNCTION public.supplier_payment_complete_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE operation public.supplier_payment_operations;
        BEGIN
        IF TG_TABLE_NAME='supplier_payment_operations' THEN
            operation := NEW;
        ELSE
            SELECT * INTO operation FROM public.supplier_payment_operations WHERE id=NEW.operation_id;
        END IF;
        IF NOT EXISTS(SELECT 1 FROM public.supplier_payment_impacts i
            JOIN public.supplier_payment_documents d ON d.id=i.document_record_id AND d.company_id=i.company_id
            WHERE i.operation_id=operation.id AND i.company_id=operation.company_id
              AND d.document_kind=operation.document_kind AND d.document_id=operation.document_id) THEN
            RAISE EXCEPTION 'Supplier operation requires its canonical document impact' USING ERRCODE='23514';
        END IF;
        IF operation.kind='reversal' AND (EXISTS(
            SELECT document_record_id,delta FROM public.supplier_payment_impacts WHERE operation_id=operation.id
            EXCEPT SELECT document_record_id,-delta FROM public.supplier_payment_impacts WHERE operation_id=operation.reverses_id
        ) OR EXISTS(
            SELECT document_record_id,-delta FROM public.supplier_payment_impacts WHERE operation_id=operation.reverses_id
            EXCEPT SELECT document_record_id,delta FROM public.supplier_payment_impacts WHERE operation_id=operation.id
        )) THEN
            RAISE EXCEPTION 'Reversal must mirror all original impacts' USING ERRCODE='23514';
        END IF;
        RETURN NULL;
        END;
    $$''')
    for table in ('supplier_payment_operations', 'supplier_payment_impacts'):
        op.execute(f'''CREATE CONSTRAINT TRIGGER supplier_payment_complete AFTER INSERT ON public.{table}
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.supplier_payment_complete_guard()''')


def downgrade():
    op.execute('LOCK TABLE ' + ','.join('public.' + table for table in TABLES) + ' IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN
        IF current_setting('transaction_isolation')<>'read committed' THEN
            RAISE EXCEPTION 'Supplier payment downgrade requires READ COMMITTED';
        END IF;
        IF EXISTS(SELECT 1 FROM public.supplier_payment_documents)
           OR EXISTS(SELECT 1 FROM public.supplier_payment_operations)
           OR EXISTS(SELECT 1 FROM public.supplier_payment_impacts) THEN
            RAISE EXCEPTION 'Cannot remove supplier payment evidence';
        END IF;
    END $$''')
    for table in reversed(TABLES):
        op.execute('DROP TABLE public.' + table)
    for function in ('supplier_payment_complete_guard', 'supplier_payment_impact_guard',
                     'supplier_payment_operation_guard', 'supplier_payment_document_guard', 'supplier_payment_immutable'):
        op.execute('DROP FUNCTION public.' + function + '()')
