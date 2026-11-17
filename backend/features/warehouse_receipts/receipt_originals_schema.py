"""Migration-only schema for immutable evidence on every receipt outcome."""

SCHEMA_SQL = r'''
ALTER TABLE supply_deliveries ADD COLUMN IF NOT EXISTS receipt_original_urls JSONB;

CREATE OR REPLACE FUNCTION receipt_original_urls_valid(originals JSONB)
RETURNS BOOLEAN LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE item JSONB; url TEXT; seen TEXT[] := ARRAY[]::TEXT[];
BEGIN
    -- NULL preserves the distinction between legacy unknown and a saved list.
    IF originals IS NULL THEN RETURN TRUE; END IF;
    IF jsonb_typeof(originals) <> 'array' THEN RETURN FALSE; END IF;
    IF jsonb_array_length(originals) NOT BETWEEN 1 AND 30 THEN RETURN FALSE; END IF;
    FOR item IN SELECT value FROM jsonb_array_elements(originals) LOOP
        IF jsonb_typeof(item) <> 'string' THEN RETURN FALSE; END IF;
        url := item #>> '{}';
        IF url !~ '^/tenant-files/[1-9][0-9]*/content$' OR url = ANY(seen) THEN
            RETURN FALSE;
        END IF;
        seen := array_append(seen, url);
    END LOOP;
    RETURN TRUE;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
        WHERE conrelid=to_regclass('supply_deliveries')
          AND conname='supply_delivery_receipt_originals_shape') THEN
        ALTER TABLE supply_deliveries ADD CONSTRAINT supply_delivery_receipt_originals_shape
            CHECK (receipt_original_urls_valid(receipt_original_urls));
    END IF;
END $$;

CREATE OR REPLACE FUNCTION preserve_receipt_original_urls()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.receipt_original_urls IS NOT NULL
       AND (NEW.receipt_original_urls IS DISTINCT FROM OLD.receipt_original_urls
         OR (NEW.id,NEW.company_id,NEW.supplier_id,NEW.offer_id,NEW.request_id,
             NEW.project,NEW.work_package,NEW.waybill_number,NEW.waybill_date)
            IS DISTINCT FROM
            (OLD.id,OLD.company_id,OLD.supplier_id,OLD.offer_id,OLD.request_id,
             OLD.project,OLD.work_package,OLD.waybill_number,OLD.waybill_date)
         OR to_jsonb(NEW)->'source_supplier_invoice_id' IS DISTINCT FROM to_jsonb(OLD)->'source_supplier_invoice_id'
         OR to_jsonb(NEW)->'contract_version_id' IS DISTINCT FROM to_jsonb(OLD)->'contract_version_id') THEN
        RAISE EXCEPTION 'Receipt originals and source are immutable' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS supply_delivery_receipt_originals_immutable ON supply_deliveries;
CREATE TRIGGER supply_delivery_receipt_originals_immutable
BEFORE UPDATE ON supply_deliveries
FOR EACH ROW EXECUTE FUNCTION preserve_receipt_original_urls();
'''
