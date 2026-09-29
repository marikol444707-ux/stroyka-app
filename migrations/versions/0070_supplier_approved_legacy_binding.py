"""Allow safe first contract binding after an invoice is approved."""
from alembic import op

revision = '0070_approved_legacy_binding'
down_revision = '0069_customer_publications'
branch_labels = None
depends_on = None


def upgrade():
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
                      AND o.status='Утверждено' AND OLD.status IN ('На утверждении','Утверждён')
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
    raise RuntimeError('Approved legacy bindings may already exist and cannot be downgraded safely')
