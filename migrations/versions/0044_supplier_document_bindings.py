"""Immutable contract references on invoices and their shipments; no backfill."""
from alembic import op

revision = '0044_supplier_document_bindings'
down_revision = '0043_supplier_contract_versions'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE UNIQUE INDEX uq_contract_document_identity
                  ON public.supplier_contract_versions(id, company_id, offer_id)''')
    for table in ('supplier_invoices', 'supply_deliveries'):
        op.execute(f'''ALTER TABLE public.{table} ADD COLUMN contract_version_id BIGINT,
            ADD CONSTRAINT {table}_contract_owner CHECK (contract_version_id IS NULL OR
                (company_id IS NOT NULL AND offer_id IS NOT NULL AND request_id IS NOT NULL AND supplier_id IS NOT NULL)),
            ADD CONSTRAINT {table}_contract_fk FOREIGN KEY (contract_version_id, company_id, offer_id)
                REFERENCES public.supplier_contract_versions(id, company_id, offer_id)''')
        op.execute(f'CREATE INDEX {table}_contract_idx ON public.{table}(contract_version_id)')
    op.execute('''CREATE UNIQUE INDEX uq_invoice_contract_identity
                  ON public.supplier_invoices(id, company_id, offer_id, contract_version_id)''')
    op.execute('''ALTER TABLE public.supply_deliveries ADD COLUMN source_supplier_invoice_id INTEGER,
        ADD CONSTRAINT delivery_invoice_contract_pair CHECK
            ((source_supplier_invoice_id IS NULL) = (contract_version_id IS NULL)),
        ADD CONSTRAINT delivery_invoice_contract_fk
            FOREIGN KEY (source_supplier_invoice_id, company_id, offer_id, contract_version_id)
            REFERENCES public.supplier_invoices(id, company_id, offer_id, contract_version_id)''')
    op.execute('''CREATE FUNCTION public.guard_supplier_document_contract() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        IF TG_OP='DELETE' THEN
            IF OLD.contract_version_id IS NOT NULL THEN
                RAISE EXCEPTION 'Bound supplier documents cannot be deleted';
            END IF;
            RETURN OLD;
        END IF;
        IF TG_OP='UPDATE' THEN
            IF OLD.contract_version_id IS DISTINCT FROM NEW.contract_version_id OR
               (OLD.contract_version_id IS NOT NULL AND
                (OLD.company_id,OLD.offer_id,OLD.request_id,OLD.supplier_id) IS DISTINCT FROM
                (NEW.company_id,NEW.offer_id,NEW.request_id,NEW.supplier_id)) THEN
                RAISE EXCEPTION 'Document contract identity is immutable';
            END IF;
            IF TG_TABLE_NAME='supply_deliveries' AND OLD.contract_version_id IS NOT NULL THEN
                IF OLD.source_supplier_invoice_id IS DISTINCT FROM NEW.source_supplier_invoice_id THEN
                    RAISE EXCEPTION 'Shipment source invoice is immutable';
                END IF;
            END IF;
        END IF;
        IF NEW.contract_version_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.supplier_contract_versions v JOIN public.supplier_deal_parties p
              ON p.offer_id=v.offer_id AND p.company_id=v.company_id AND p.version=v.party_version
            WHERE v.id=NEW.contract_version_id AND v.company_id=NEW.company_id
              AND v.offer_id=NEW.offer_id AND p.request_id=NEW.request_id AND p.supplier_id=NEW.supplier_id
        ) THEN
            RAISE EXCEPTION 'Contract does not match document identity';
        END IF;
        RETURN NEW;
        END $$''')
    for table in ('supplier_invoices', 'supply_deliveries'):
        op.execute(f'''CREATE TRIGGER {table}_contract_guard BEFORE INSERT OR UPDATE OR DELETE
            ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.guard_supplier_document_contract()''')
    op.execute('''CREATE FUNCTION public.guard_saved_supplier_contract() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
            RAISE EXCEPTION 'Saved contract versions are append-only';
        END $$''')
    op.execute('''CREATE TRIGGER supplier_contract_immutable BEFORE UPDATE OR DELETE
        ON public.supplier_contract_versions FOR EACH ROW EXECUTE FUNCTION public.guard_saved_supplier_contract()''')


def downgrade():
    op.execute('''DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM public.supplier_invoices WHERE contract_version_id IS NOT NULL)
           OR EXISTS (SELECT 1 FROM public.supply_deliveries WHERE contract_version_id IS NOT NULL) THEN
            RAISE EXCEPTION 'Cannot remove document contract bindings';
        END IF;
        END $$''')
    op.execute('DROP TRIGGER supplier_contract_immutable ON public.supplier_contract_versions')
    op.execute('DROP FUNCTION public.guard_saved_supplier_contract()')
    for table in ('supplier_invoices', 'supply_deliveries'):
        op.execute(f'DROP TRIGGER {table}_contract_guard ON public.{table}')
    op.execute('DROP FUNCTION public.guard_supplier_document_contract()')
    op.execute('''ALTER TABLE public.supply_deliveries DROP CONSTRAINT delivery_invoice_contract_fk,
        DROP CONSTRAINT delivery_invoice_contract_pair, DROP COLUMN source_supplier_invoice_id''')
    op.execute('DROP INDEX public.uq_invoice_contract_identity')
    for table in ('supplier_invoices', 'supply_deliveries'):
        op.execute(f'ALTER TABLE public.{table} DROP COLUMN contract_version_id')
    op.execute('DROP INDEX public.uq_contract_document_identity')
