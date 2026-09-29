"""Explicit append-only evidence for the first contract binding of unused invoices."""
from alembic import op

revision = '0062_supplier_legacy_binding'
down_revision = '0061_supplier_mixed_bindings'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE public.supplier_legacy_contract_bindings (
        invoice_id INTEGER PRIMARY KEY REFERENCES public.supplier_invoices(id),
        company_id INTEGER NOT NULL, offer_id INTEGER NOT NULL,
        contract_version_id BIGINT NOT NULL,
        request_id UUID NOT NULL UNIQUE, reason TEXT NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 1000),
        actor_id INTEGER NOT NULL REFERENCES public.users(id), actor_name TEXT NOT NULL CHECK (length(btrim(actor_name))>0),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        FOREIGN KEY (contract_version_id,company_id,offer_id)
            REFERENCES public.supplier_contract_versions(id,company_id,offer_id)
    )''')
    op.execute('''CREATE TRIGGER supplier_legacy_binding_immutable BEFORE UPDATE OR DELETE
        ON public.supplier_legacy_contract_bindings FOR EACH ROW
        EXECUTE FUNCTION public.guard_saved_supplier_contract()''')
    op.execute('''CREATE FUNCTION public.guard_supplier_legacy_binding_insert() RETURNS trigger
        LANGUAGE plpgsql AS $$ DECLARE i RECORD; BEGIN
        SELECT * INTO i FROM public.supplier_invoices WHERE id=NEW.invoice_id FOR UPDATE;
        IF NOT FOUND OR i.contract_version_id IS NOT NULL OR
           i.company_id IS DISTINCT FROM NEW.company_id OR i.offer_id IS DISTINCT FROM NEW.offer_id THEN
            RAISE EXCEPTION 'Legacy binding evidence requires an unbound invoice of this deal';
        END IF;
        RETURN NEW;
        END $$''')
    op.execute('''CREATE TRIGGER supplier_legacy_binding_insert BEFORE INSERT
        ON public.supplier_legacy_contract_bindings FOR EACH ROW
        EXECUTE FUNCTION public.guard_supplier_legacy_binding_insert()''')
    op.execute('''CREATE FUNCTION public.validate_supplier_legacy_binding() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM public.supplier_invoices i
            WHERE i.id=NEW.invoice_id AND i.company_id=NEW.company_id
              AND i.offer_id=NEW.offer_id AND i.contract_version_id=NEW.contract_version_id) THEN
            RAISE EXCEPTION 'Legacy contract binding must match its invoice at commit';
        END IF;
        RETURN NEW;
        END $$''')
    op.execute('''CREATE CONSTRAINT TRIGGER supplier_legacy_binding_complete
        AFTER INSERT ON public.supplier_legacy_contract_bindings DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION public.validate_supplier_legacy_binding()''')
    op.execute('''CREATE OR REPLACE FUNCTION public.guard_supplier_document_contract() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE legacy_allowed BOOLEAN := FALSE;
        BEGIN
        IF TG_OP='DELETE' THEN
            IF OLD.contract_version_id IS NOT NULL THEN
                RAISE EXCEPTION 'Bound supplier documents cannot be deleted';
            END IF;
            RETURN OLD;
        END IF;
        IF TG_OP='UPDATE' THEN
            IF TG_TABLE_NAME='supplier_invoices' AND OLD.contract_version_id IS NULL
               AND NEW.contract_version_id IS NOT NULL THEN
                SELECT EXISTS (
                    SELECT 1 FROM public.supplier_legacy_contract_bindings b
                    JOIN public.supplier_offers o ON o.id=b.offer_id AND o.company_id=b.company_id
                    JOIN public.supply_requests r ON r.id=o.request_id AND r.company_id=o.company_id
                    JOIN public.supplier_contract_versions v ON v.id=b.contract_version_id
                    JOIN public.supplier_deal_parties p ON p.offer_id=o.id AND p.company_id=o.company_id
                        AND p.version=v.party_version
                    WHERE b.invoice_id=NEW.id AND b.company_id=NEW.company_id AND b.offer_id=NEW.offer_id
                      AND b.contract_version_id=NEW.contract_version_id
                      AND o.status='Утверждено' AND OLD.status='На утверждении'
                      AND o.supplier_id=OLD.supplier_id AND o.request_id=OLD.request_id
                      AND r.project=OLD.project_name AND r.work_package=OLD.work_package
                      AND p.request_id=OLD.request_id AND p.supplier_id=OLD.supplier_id
                      AND v.reviewed_at IS NOT NULL AND length(btrim(v.reviewed_by))>0
                      AND v.id=(SELECT id FROM public.supplier_contract_versions WHERE offer_id=o.id ORDER BY version DESC LIMIT 1)
                      AND p.version=(SELECT MAX(version) FROM public.supplier_deal_parties WHERE offer_id=o.id)
                      AND OLD.paid_amount=0 AND OLD.amount>0 AND OLD.amount::text NOT IN ('NaN','Infinity')
                      AND OLD.warehouse_invoice_id IS NULL
                      AND (to_jsonb(OLD)-'contract_version_id')=(to_jsonb(NEW)-'contract_version_id')
                      AND NOT EXISTS(SELECT 1 FROM public.warehouse_invoices WHERE supplier_invoice_id=OLD.id)
                      AND NOT EXISTS(SELECT 1 FROM public.supply_deliveries WHERE source_supplier_invoice_id=OLD.id OR offer_id=OLD.offer_id)
                      AND NOT EXISTS(SELECT 1 FROM public.supplier_payment_documents WHERE document_kind='invoice' AND document_id=OLD.id)
                      AND NOT EXISTS(SELECT 1 FROM public.supplier_invoice_line_specs WHERE invoice_id=OLD.id)
                ) INTO legacy_allowed;
            END IF;
            IF (OLD.contract_version_id IS DISTINCT FROM NEW.contract_version_id AND NOT legacy_allowed) OR
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
        ) THEN RAISE EXCEPTION 'Contract does not match document identity'; END IF;
        RETURN NEW;
        END $$''')


def downgrade():
    # Removing the audit would erase the basis of previously immutable identities.
    raise RuntimeError('Legacy contract binding evidence cannot be downgraded automatically')
