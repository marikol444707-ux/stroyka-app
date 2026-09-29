"""Future-only immutable invoice lines; no consumption or runtime activation.

Quiescent migration only. Existing invoices retain NULL birth metadata. Sources
in source_payload are caller-supplied creation evidence, not SQL attestation of
mutable KP history. The server writer must authorize and validate those lines.
DB guards attest an original invoice INSERT, exact identity and arithmetic.
Writers must acquire the common company lock before physical/source row locks.
"""
from alembic import op

revision = '0050_supplier_invoice_line_specs'
down_revision = '0049_supplier_pay_allocations'
branch_labels = None
depends_on = None
TABLES = ('supplier_invoice_line_specs', 'supplier_invoice_lines')


def upgrade():
    op.execute('''ALTER TABLE public.supplier_invoices
        ADD COLUMN line_spec_insert_xid XID8,
        ADD COLUMN line_spec_insert_identity JSONB''')
    op.execute('''CREATE TABLE public.supplier_invoice_line_specs (
        id BIGSERIAL PRIMARY KEY,
        company_id INTEGER NOT NULL REFERENCES public.companies(id),
        invoice_id INTEGER NOT NULL UNIQUE REFERENCES public.supplier_invoices(id),
        creation_xid XID8 NOT NULL,
        row_count INTEGER NOT NULL CHECK(row_count BETWEEN 1 AND 2000),
        amount NUMERIC NOT NULL CHECK(amount>0 AND amount<=999999999999.99 AND amount=trunc(amount,2)),
        source_identity JSONB NOT NULL CHECK(jsonb_typeof(source_identity)='object'),
        source_payload JSONB NOT NULL CHECK(jsonb_typeof(source_payload)='object'),
        created_at TIMESTAMPTZ NOT NULL,
        UNIQUE(id,company_id)
    )''')
    op.execute('''CREATE TABLE public.supplier_invoice_lines (
        id BIGSERIAL PRIMARY KEY,
        spec_id BIGINT NOT NULL, company_id INTEGER NOT NULL,
        line_no INTEGER NOT NULL CHECK(line_no BETWEEN 1 AND 2000),
        source_request_position INTEGER NOT NULL CHECK(source_request_position BETWEEN 0 AND 1999),
        source_offer_position INTEGER NOT NULL CHECK(source_offer_position BETWEEN 0 AND 1999),
        material_name TEXT NOT NULL CHECK(btrim(material_name)<>''),
        unit TEXT NOT NULL CHECK(btrim(unit)<>''), work_package TEXT NOT NULL,
        quantity NUMERIC NOT NULL CHECK(quantity>0 AND quantity<=999999999999.999999 AND quantity=trunc(quantity,6)),
        unit_price NUMERIC NOT NULL CHECK(unit_price>0 AND unit_price<=999999999999.999999 AND unit_price=trunc(unit_price,6)),
        amount NUMERIC NOT NULL CHECK(amount>0 AND amount<=999999999999.99 AND amount=trunc(amount,2)),
        CHECK(amount=quantity*unit_price),
        UNIQUE(spec_id,line_no), UNIQUE(spec_id,source_request_position), UNIQUE(spec_id,source_offer_position),
        FOREIGN KEY(spec_id,company_id) REFERENCES public.supplier_invoice_line_specs(id,company_id)
    )''')
    op.execute('''CREATE FUNCTION public.supplier_invoice_line_identity(i public.supplier_invoices)
        RETURNS JSONB LANGUAGE sql IMMUTABLE AS $$
        SELECT jsonb_build_object('id',i.id,'company_id',i.company_id,'supplier_id',i.supplier_id,
            'project_name',i.project_name,'work_package',COALESCE(i.work_package,''),
            'contract_version_id',i.contract_version_id,'offer_id',i.offer_id,'request_id',i.request_id,
            'amount',i.amount::NUMERIC,'vat_amount',COALESCE(i.vat_amount,0)::NUMERIC,
            'invoice_number',i.invoice_number,'invoice_date',i.invoice_date)
    $$''')
    op.execute('''CREATE FUNCTION public.supplier_invoice_line_birth() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        NEW.line_spec_insert_xid := pg_current_xact_id();
        NEW.line_spec_insert_identity := public.supplier_invoice_line_identity(NEW);
        RETURN NEW;
        END;
    $$''')
    op.execute('''CREATE TRIGGER invoice_line_spec_birth BEFORE INSERT ON public.supplier_invoices
        FOR EACH ROW EXECUTE FUNCTION public.supplier_invoice_line_birth()''')
    op.execute('''CREATE FUNCTION public.supplier_invoice_line_physical() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF TG_OP='UPDATE' AND (NEW.line_spec_insert_xid IS DISTINCT FROM OLD.line_spec_insert_xid
            OR NEW.line_spec_insert_identity IS DISTINCT FROM OLD.line_spec_insert_identity) THEN
            RAISE EXCEPTION 'Invoice birth metadata is immutable' USING ERRCODE='23514'; END IF;
        -- A different transaction cannot retrofit a committed invoice. Thus an
        -- absent header needs no new lock on the legacy-only UPDATE/DELETE path.
        IF EXISTS(SELECT 1 FROM public.supplier_invoice_line_specs WHERE invoice_id=OLD.id) THEN
            PERFORM public.supplier_allocation_lock(OLD.company_id);
            IF TG_OP='DELETE' THEN
                RAISE EXCEPTION 'Invoice specification identity is immutable' USING ERRCODE='23514'; END IF;
            IF public.supplier_invoice_line_identity(NEW) IS DISTINCT FROM public.supplier_invoice_line_identity(OLD) THEN
                RAISE EXCEPTION 'Invoice specification identity is immutable' USING ERRCODE='23514'; END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
        END;
    $$''')
    op.execute('''CREATE TRIGGER invoice_line_spec_physical BEFORE UPDATE OR DELETE ON public.supplier_invoices
        FOR EACH ROW EXECUTE FUNCTION public.supplier_invoice_line_physical()''')
    op.execute('''CREATE FUNCTION public.supplier_invoice_line_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        RAISE EXCEPTION 'Invoice specification evidence is immutable' USING ERRCODE='23514';
        END;
    $$''')
    op.execute('''CREATE FUNCTION public.supplier_invoice_line_no_truncate() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF EXISTS(SELECT 1 FROM public.supplier_invoice_line_specs) THEN
            RAISE EXCEPTION 'Invoice specification evidence is immutable' USING ERRCODE='23514'; END IF;
        RETURN NULL;
        END;
    $$''')
    op.execute('''CREATE TRIGGER invoice_line_spec_no_truncate BEFORE TRUNCATE ON public.supplier_invoices
        FOR EACH STATEMENT EXECUTE FUNCTION public.supplier_invoice_line_no_truncate()''')
    op.execute('''CREATE FUNCTION public.supplier_invoice_line_insert() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE i public.supplier_invoices; h public.supplier_invoice_line_specs;
        BEGIN
        PERFORM public.supplier_allocation_lock(NEW.company_id);
        IF TG_TABLE_NAME='supplier_invoice_line_specs' THEN
            SELECT * INTO i FROM public.supplier_invoices WHERE id=NEW.invoice_id FOR UPDATE;
            IF NOT FOUND OR i.line_spec_insert_xid IS DISTINCT FROM pg_current_xact_id() THEN
                RAISE EXCEPTION 'Invoice specification requires original creation transaction' USING ERRCODE='23514'; END IF;
            IF i.company_id IS DISTINCT FROM NEW.company_id
                OR i.line_spec_insert_identity IS DISTINCT FROM public.supplier_invoice_line_identity(i) THEN
                RAISE EXCEPTION 'Invoice birth identity differs' USING ERRCODE='23514'; END IF;
            IF COALESCE(i.vat_amount,0)<>0 OR NEW.amount IS DISTINCT FROM i.amount::NUMERIC
                OR i.contract_version_id IS NULL OR i.offer_id IS NULL OR i.request_id IS NULL
                OR i.supplier_id IS NULL OR COALESCE(btrim(i.project_name),'')='' THEN
                RAISE EXCEPTION 'Invoice specification requires bound zero-VAT identity and exact amount' USING ERRCODE='23514'; END IF;
            PERFORM 1 FROM public.supplier_contract_versions c
                JOIN public.supplier_offers o ON o.id=c.offer_id AND o.company_id=c.company_id
                JOIN public.supply_requests r ON r.id=o.request_id AND r.company_id=o.company_id
                WHERE c.id=i.contract_version_id AND c.company_id=i.company_id AND o.id=i.offer_id
                  AND r.id=i.request_id AND o.supplier_id=i.supplier_id AND r.project=i.project_name
                  AND c.reviewed_at IS NOT NULL AND c.reviewed_by_id IS NOT NULL
                FOR SHARE OF c,o,r;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'Invoice specification bound source identity differs' USING ERRCODE='23514'; END IF;
            NEW.creation_xid := pg_current_xact_id();
            NEW.source_identity := i.line_spec_insert_identity;
            NEW.created_at := clock_timestamp();
        ELSE
            SELECT * INTO h FROM public.supplier_invoice_line_specs WHERE id=NEW.spec_id;
            IF NOT FOUND OR h.creation_xid IS DISTINCT FROM pg_current_xact_id() THEN
                RAISE EXCEPTION 'Invoice specification is sealed' USING ERRCODE='23514'; END IF;
            IF NEW.company_id IS DISTINCT FROM h.company_id
                OR NEW.work_package IS DISTINCT FROM h.source_identity->>'work_package' THEN
                RAISE EXCEPTION 'Invoice line scope or package differs' USING ERRCODE='23514'; END IF;
        END IF;
        RETURN NEW;
        END;
    $$''')
    op.execute('''CREATE FUNCTION public.supplier_invoice_line_complete() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE h public.supplier_invoice_line_specs; i public.supplier_invoices;
        BEGIN
        PERFORM public.supplier_allocation_lock(NEW.company_id);
        IF TG_TABLE_NAME='supplier_invoice_line_specs' THEN h:=NEW;
        ELSE SELECT * INTO h FROM public.supplier_invoice_line_specs WHERE id=NEW.spec_id; END IF;
        SELECT * INTO i FROM public.supplier_invoices WHERE id=h.invoice_id;
        IF NOT FOUND OR public.supplier_invoice_line_identity(i) IS DISTINCT FROM h.source_identity THEN
            RAISE EXCEPTION 'Invoice specification identity changed' USING ERRCODE='23514'; END IF;
        IF h.row_count<>(SELECT count(*) FROM public.supplier_invoice_lines WHERE spec_id=h.id)
            OR h.amount IS DISTINCT FROM (SELECT sum(amount) FROM public.supplier_invoice_lines WHERE spec_id=h.id)
            OR (SELECT min(line_no) FROM public.supplier_invoice_lines WHERE spec_id=h.id)<>1
            OR (SELECT max(line_no) FROM public.supplier_invoice_lines WHERE spec_id=h.id)<>h.row_count THEN
            RAISE EXCEPTION 'Incomplete invoice specification' USING ERRCODE='23514'; END IF;
        RETURN NULL;
        END;
    $$''')
    for table in TABLES:
        op.execute(f'''CREATE TRIGGER invoice_line_spec_insert BEFORE INSERT ON public.{table}
            FOR EACH ROW EXECUTE FUNCTION public.supplier_invoice_line_insert()''')
        op.execute(f'''CREATE CONSTRAINT TRIGGER invoice_line_spec_complete AFTER INSERT ON public.{table}
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.supplier_invoice_line_complete()''')
        op.execute(f'''CREATE TRIGGER invoice_line_spec_immutable BEFORE UPDATE OR DELETE ON public.{table}
            FOR EACH ROW EXECUTE FUNCTION public.supplier_invoice_line_immutable()''')
        op.execute(f'''CREATE TRIGGER invoice_line_spec_no_truncate BEFORE TRUNCATE ON public.{table}
            FOR EACH STATEMENT EXECUTE FUNCTION public.supplier_invoice_line_immutable()''')


def downgrade():
    # Birth markers without a specification are administrative admission data,
    # not business evidence; those markers alone do not prohibit downgrade.
    op.execute('''LOCK TABLE public.supplier_invoices,public.supplier_invoice_line_specs,
        public.supplier_invoice_lines IN ACCESS EXCLUSIVE MODE''')
    op.execute('''DO $$ BEGIN
        IF current_setting('transaction_isolation')<>'read committed' THEN
            RAISE EXCEPTION 'Invoice specification downgrade requires read committed'; END IF;
        IF EXISTS(SELECT 1 FROM public.supplier_invoice_line_specs)
            OR EXISTS(SELECT 1 FROM public.supplier_invoice_lines) THEN
            RAISE EXCEPTION 'Refuse to remove invoice specification evidence'; END IF;
        END $$''')
    for trigger in ('invoice_line_spec_birth','invoice_line_spec_physical','invoice_line_spec_no_truncate'):
        op.execute(f'DROP TRIGGER {trigger} ON public.supplier_invoices')
    op.execute('DROP TABLE public.supplier_invoice_lines,public.supplier_invoice_line_specs')
    for name in ('complete','insert','no_truncate','immutable','physical','birth'):
        op.execute(f'DROP FUNCTION public.supplier_invoice_line_{name}()')
    op.execute('DROP FUNCTION public.supplier_invoice_line_identity(public.supplier_invoices)')
    op.execute('''ALTER TABLE public.supplier_invoices DROP COLUMN line_spec_insert_xid,
        DROP COLUMN line_spec_insert_identity''')
