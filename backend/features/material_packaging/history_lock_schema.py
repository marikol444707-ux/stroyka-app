"""DB-side supplier keys for packaging DML, including non-HTTP writers."""
from .history_lock import PACKAGING_HISTORY_NAMESPACE


GUARD_SQL = f'''
CREATE OR REPLACE FUNCTION public.material_packaging_history_writer_guard()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE
    supplier_keys integer[];
    selected_supplier integer;
BEGIN
    IF TG_OP='INSERT' THEN
        supplier_keys := ARRAY[NEW.supplier_id];
    ELSIF TG_OP='DELETE' THEN
        supplier_keys := ARRAY[OLD.supplier_id];
    ELSE
        supplier_keys := ARRAY[OLD.supplier_id,NEW.supplier_id];
    END IF;
    FOR selected_supplier IN
        SELECT DISTINCT key_value FROM pg_catalog.unnest(supplier_keys) AS keys(key_value)
         WHERE key_value IS NOT NULL ORDER BY key_value
    LOOP
        PERFORM pg_catalog.pg_advisory_xact_lock_shared({PACKAGING_HISTORY_NAMESPACE},selected_supplier);
    END LOOP;
    IF TG_OP='DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS material_packaging_history_writer_guard ON public.material_packaging_rules;
CREATE TRIGGER material_packaging_history_writer_guard
    BEFORE INSERT OR UPDATE OR DELETE ON public.material_packaging_rules
    FOR EACH ROW EXECUTE FUNCTION public.material_packaging_history_writer_guard();
ALTER TABLE public.material_packaging_rules ENABLE ALWAYS TRIGGER material_packaging_history_writer_guard;
'''


DROP_GUARD_SQL = '''
DROP TRIGGER material_packaging_history_writer_guard ON public.material_packaging_rules;
DROP FUNCTION public.material_packaging_history_writer_guard();
'''
