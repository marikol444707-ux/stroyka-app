\set ON_ERROR_STOP on

SELECT set_config('stroyka.keep_email', :'keep_email', false);
SELECT set_config('stroyka.reset_pricelists', :'reset_pricelists', false);

\echo '--- Prelaunch cleanup preview ---'
DO $$
DECLARE
  keep_email text := current_setting('stroyka.keep_email');
  table_name text;
  row_count bigint;
  tables text[] := ARRAY[
    'users',
    'projects',
    'clients',
    'staff',
    'materials',
    'warehouse_main',
    'warehouse_history',
    'warehouse_movements',
    'warehouse_invoices',
    'warehouses',
    'work_journal',
    'piecework',
    'messages',
    'project_chat',
    'rooms',
    'room_works',
    'room_windows',
    'room_doors',
    'project_measurements',
    'measurement_room_drafts',
    'project_documents',
    'project_letters',
    'estimates',
    'estimate_versions',
    'estimate_chat_messages',
    'hidden_works_acts',
    'material_inspection_journal',
    'cable_journal',
    'supervisor_acts',
    'prescriptions',
    'inspection_orders',
    'tb_journal',
    'unexpected_works',
    'project_stages',
    'project_checklists',
    'checklist_items',
    'brigade_contracts',
    'brigade_contract_items',
    'brigade_payments',
    'brigade_acts',
    'interim_acts',
    'contracts',
    'master_profiles',
    'timesheet',
    'salary_payments',
    'expenses',
    'project_payments',
    'accountable_payments',
    'accountable_expenses',
    'own_expenses',
    'expense_reports',
    'supply_requests',
    'supplier_offers',
    'supplier_invoices',
    'supply_deliveries',
    'supply_claims',
    'supply_history',
    'suppliers',
    'supplier_documents',
    'company_supplier_links',
    'supplier_subscriptions',
    'supplier_catalog',
    'supply_request_templates',
    'material_transfers',
    'tools',
    'tool_history',
    'inventory',
    'inventory_items',
    'pd_consents',
    'warranty_defects',
    'crm_leads',
    'project_ai_summary',
    'ai_findings',
    'ai_tasks',
    'material_norm_suggestions',
    'material_norm_overrides',
    'audit_log',
    'api_errors',
    'invite_codes'
  ];
BEGIN
  IF NOT EXISTS (SELECT 1 FROM users WHERE lower(email) = lower(keep_email)) THEN
    RAISE EXCEPTION 'Keep user with email % was not found. Stop cleanup.', keep_email;
  END IF;

  RAISE NOTICE 'Will keep active director: %', keep_email;
  FOREACH table_name IN ARRAY tables LOOP
    IF to_regclass(table_name) IS NOT NULL THEN
      EXECUTE format('SELECT count(*) FROM %I', table_name) INTO row_count;
      RAISE NOTICE '%: %', table_name, row_count;
    END IF;
  END LOOP;

  IF current_setting('stroyka.reset_pricelists') = '1' THEN
    FOREACH table_name IN ARRAY ARRAY['pricelist_items', 'pricelists'] LOOP
      IF to_regclass(table_name) IS NOT NULL THEN
        EXECUTE format('SELECT count(*) FROM %I', table_name) INTO row_count;
        RAISE NOTICE '%: % (will be reset because RESET_PRICELISTS=1)', table_name, row_count;
      END IF;
    END LOOP;
  ELSE
    RAISE NOTICE 'pricelists/pricelist_items: preserved (set RESET_PRICELISTS=1 to delete)';
  END IF;

  RAISE NOTICE 'material_norms/material_aliases: preserved';
  RAISE NOTICE 'companies/company_requisites/company_documents: preserved';
END $$;

\if :dry_run
\echo '--- DRY_RUN=1: no data was changed ---'
\quit
\endif

\echo '--- Destructive prelaunch cleanup is disabled ---'
DO $$
BEGIN
  RAISE EXCEPTION 'Destructive prelaunch cleanup is disabled. Use manual, reviewed archive/restore procedures instead.';
END $$;
