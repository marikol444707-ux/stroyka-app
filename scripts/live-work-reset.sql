\set ON_ERROR_STOP on

SELECT set_config('stroyka.reset_uploads', :'reset_uploads', false);

\echo '--- Live-work reset preview ---'
DO $$
DECLARE
  table_name text;
  row_count bigint;
  reset_tables text[] := ARRAY[
    'materials',
    'warehouse_main',
    'warehouse_history',
    'warehouse_movements',
    'warehouse_invoices',
    'warehouses',
    'work_journal',
    'piecework',
    'room_works',
    'room_windows',
    'room_doors',
    'rooms',
    'project_measurements',
    'measurement_room_drafts',
    'project_documents',
    'project_letters',
    'messages',
    'project_chat',
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
    'brigade_contract_items',
    'brigade_contracts',
    'brigade_payments',
    'brigade_acts',
    'brigade_act_items',
    'interim_acts',
    'contracts',
    'master_profiles',
    'timesheet',
    'salary_payments',
    'staff_documents',
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
    'demo_requests',
    'company_payments',
    'project_ai_summary',
    'ai_findings',
    'ai_tasks',
    'material_norm_suggestions',
    'estimate_chat_messages',
    'audit_log',
    'api_errors',
    'invite_codes',
    'document_versions'
  ];
  preserved_tables text[] := ARRAY[
    'projects',
    'clients',
    'users',
    'staff',
    'estimates',
    'estimate_versions',
    'pricelists',
    'pricelist_items',
    'material_norms',
    'material_aliases',
    'material_norm_overrides',
    'companies',
    'company_requisites',
    'company_documents'
  ];
BEGIN
  RAISE NOTICE 'Preserved base tables:';
  FOREACH table_name IN ARRAY preserved_tables LOOP
    IF to_regclass(table_name) IS NOT NULL THEN
      EXECUTE format('SELECT count(*) FROM %I', table_name) INTO row_count;
      RAISE NOTICE '  keep %: % rows', table_name, row_count;
    END IF;
  END LOOP;

  RAISE NOTICE 'Operational tables selected for reset:';
  FOREACH table_name IN ARRAY reset_tables LOOP
    IF to_regclass(table_name) IS NOT NULL THEN
      EXECUTE format('SELECT count(*) FROM %I', table_name) INTO row_count;
      RAISE NOTICE '  reset %: % rows', table_name, row_count;
    ELSE
      RAISE NOTICE '  skip missing table %', table_name;
    END IF;
  END LOOP;

  RAISE NOTICE 'Uploads mode: %', current_setting('stroyka.reset_uploads');
END $$;

\if :dry_run
\echo '--- DRY_RUN=1: no data was changed ---'
\quit
\endif

\if :confirmed
\else
\echo 'ERROR: set CONFIRM=LIVE_WORK_RESET to run destructive cleanup.'
\quit 1
\endif

\echo '--- Destructive live-work reset started ---'
DO $$
DECLARE
  table_name text;
  existing_tables text[] := ARRAY[]::text[];
  existing_table_names text[] := ARRAY[]::text[];
  child_table text;
  preserved_child text;
  reset_tables text[] := ARRAY[
    'materials',
    'warehouse_main',
    'warehouse_history',
    'warehouse_movements',
    'warehouse_invoices',
    'warehouses',
    'work_journal',
    'piecework',
    'room_works',
    'room_windows',
    'room_doors',
    'rooms',
    'project_measurements',
    'measurement_room_drafts',
    'project_documents',
    'project_letters',
    'messages',
    'project_chat',
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
    'brigade_contract_items',
    'brigade_contracts',
    'brigade_payments',
    'brigade_acts',
    'brigade_act_items',
    'interim_acts',
    'contracts',
    'master_profiles',
    'timesheet',
    'salary_payments',
    'staff_documents',
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
    'demo_requests',
    'company_payments',
    'project_ai_summary',
    'ai_findings',
    'ai_tasks',
    'material_norm_suggestions',
    'estimate_chat_messages',
    'audit_log',
    'api_errors',
    'invite_codes',
    'document_versions'
  ];
  preserved_tables text[] := ARRAY[
    'projects',
    'clients',
    'users',
    'staff',
    'estimates',
    'estimate_versions',
    'pricelists',
    'pricelist_items',
    'material_norms',
    'material_aliases',
    'material_norm_overrides',
    'companies',
    'company_requisites',
    'company_documents'
  ];
BEGIN
  FOREACH table_name IN ARRAY reset_tables LOOP
    IF to_regclass(table_name) IS NOT NULL THEN
      existing_table_names := existing_table_names || table_name;
    END IF;
  END LOOP;

  LOOP
    child_table := NULL;
    SELECT child.relname INTO child_table
      FROM pg_constraint con
      JOIN pg_class parent ON parent.oid = con.confrelid
      JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
      JOIN pg_class child ON child.oid = con.conrelid
      JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
     WHERE con.contype = 'f'
       AND parent_ns.nspname = 'public'
       AND child_ns.nspname = 'public'
       AND parent.relname = ANY(existing_table_names)
       AND child.relname <> ALL(existing_table_names)
     ORDER BY child.relname
     LIMIT 1;

    EXIT WHEN child_table IS NULL;

    IF child_table = ANY(preserved_tables) THEN
      preserved_child := child_table;
      EXIT;
    END IF;

    existing_table_names := existing_table_names || child_table;
    RAISE NOTICE 'auto include FK child table %', child_table;
  END LOOP;

  IF preserved_child IS NOT NULL THEN
    RAISE EXCEPTION 'Refusing reset: preserved table % references a reset table', preserved_child;
  END IF;

  IF array_length(existing_table_names, 1) IS NULL THEN
    RAISE NOTICE 'No reset tables exist, nothing to truncate.';
    RETURN;
  END IF;

  SELECT array_agg(format('%I', item)) INTO existing_tables
    FROM unnest(existing_table_names) AS item;

  EXECUTE 'TRUNCATE TABLE ' || array_to_string(existing_tables, ', ') || ' RESTART IDENTITY';

  FOREACH table_name IN ARRAY existing_table_names LOOP
    RAISE NOTICE 'reset %', table_name;
  END LOOP;
END $$;

\echo '--- Live-work reset done ---'
