-- Read-only check for the historical supplier-card merge lock audit.
-- Run with psql using the same database role as the application.
\set ON_ERROR_STOP on
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';

SELECT current_database() AS database_name,
       current_user AS database_role,
       current_setting('transaction_read_only') AS transaction_read_only;

WITH policy_tables(table_name) AS (
    VALUES ('supply_requests'), ('supply_request_recipients'), ('file_ownership'),
           ('supplier_invoices'), ('supplier_offers'), ('warehouse_invoices'),
           ('supply_deliveries'), ('supply_claims'), ('supplier_contract_versions'),
           ('supplier_contract_registry_versions'), ('supplier_team_members'),
           ('supplier_customer_assignments'), ('supplier_offer_assignments')
), inspected AS (
    SELECT table_name
      FROM information_schema.columns
     WHERE table_schema = 'public' AND column_name = 'supplier_id'
    UNION
    SELECT p.table_name
      FROM policy_tables p
     WHERE to_regclass('public.' || p.table_name) IS NOT NULL
)
SELECT i.table_name,
       EXISTS (
           SELECT 1 FROM information_schema.columns c
            WHERE c.table_schema = 'public' AND c.table_name = i.table_name
              AND c.column_name = 'supplier_id'
       ) AS has_supplier_id,
       EXISTS (
           SELECT 1 FROM information_schema.columns c
            WHERE c.table_schema = 'public' AND c.table_name = i.table_name
              AND c.column_name = 'company_id'
       ) AS has_company_id
  FROM inspected i
 ORDER BY i.table_name;

SELECT candidate.table_name,
       to_regclass('public.' || candidate.table_name) IS NOT NULL AS exists
  FROM (VALUES ('supplier_offer_assignments'), ('supplier_subscriptions')) AS candidate(table_name)
 ORDER BY candidate.table_name;

-- Dynamic read-only counts let the report continue when a candidate table is absent.
DO $$
DECLARE
    candidate text;
    row_total bigint;
BEGIN
    FOREACH candidate IN ARRAY ARRAY['supplier_offer_assignments', 'supplier_subscriptions'] LOOP
        IF to_regclass('public.' || candidate) IS NOT NULL THEN
            EXECUTE format('SELECT count(*) FROM public.%I', candidate) INTO row_total;
            RAISE NOTICE 'exact_row_count table=% row_count=%', candidate, row_total;
        ELSE
            RAISE NOTICE 'exact_row_count table=% absent=true', candidate;
        END IF;
    END LOOP;
END $$;

SELECT c.relname AS table_name,
       t.tgname AS trigger_name,
       t.tgenabled AS enabled,
       pg_get_triggerdef(t.oid, true) AS trigger_definition,
       p.oid::regprocedure AS trigger_function
  FROM pg_trigger t
  JOIN pg_class c ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_proc p ON p.oid = t.tgfoid
 WHERE n.nspname = 'public'
   AND c.relname IN ('supplier_offer_assignments', 'supplier_subscriptions')
   AND NOT t.tgisinternal
 ORDER BY c.relname, t.tgname;

SELECT current_user AS checked_role,
       table_name,
       has_table_privilege(current_user, 'public.' || table_name, 'SELECT') AS can_select,
       has_table_privilege(current_user, 'public.' || table_name, 'INSERT') AS can_insert,
       has_table_privilege(current_user, 'public.' || table_name, 'UPDATE') AS can_update,
       has_table_privilege(current_user, 'public.' || table_name, 'DELETE') AS can_delete,
       has_table_privilege(current_user, 'public.' || table_name, 'TRUNCATE') AS can_truncate
  FROM (VALUES ('supplier_offer_assignments'), ('supplier_subscriptions')) AS tables(table_name)
 WHERE to_regclass('public.' || table_name) IS NOT NULL
 ORDER BY table_name;

SELECT c.relname AS table_name,
       r.rolname AS role_name,
       r.rolsuper AS is_superuser,
       has_table_privilege(r.rolname, c.oid, 'INSERT') AS can_insert,
       has_table_privilege(r.rolname, c.oid, 'UPDATE') AS can_update,
       has_table_privilege(r.rolname, c.oid, 'DELETE') AS can_delete,
       has_table_privilege(r.rolname, c.oid, 'TRUNCATE') AS can_truncate
  FROM (VALUES ('supplier_offer_assignments'), ('supplier_subscriptions')) AS candidate(table_name)
  JOIN pg_class c ON c.oid = to_regclass('public.' || candidate.table_name)
 CROSS JOIN pg_roles r
 WHERE has_table_privilege(r.rolname, c.oid, 'INSERT')
    OR has_table_privilege(r.rolname, c.oid, 'UPDATE')
    OR has_table_privilege(r.rolname, c.oid, 'DELETE')
    OR has_table_privilege(r.rolname, c.oid, 'TRUNCATE')
 ORDER BY c.relname, r.rolname;

ROLLBACK;
