"""Add exact owners without assigning historical name-only records."""
from alembic import op

revision = '0023_quality_journal_owners'
down_revision = '0022_supplier_company_catalog'
branch_labels = None
depends_on = None

SOURCE_TABLES = ('supply_deliveries', 'warehouse_invoices', 'warehouse_history')
JOURNAL_TABLES = ('material_inspection_journal', 'cable_journal')
OWNER_TABLES = SOURCE_TABLES + JOURNAL_TABLES


def upgrade():
    op.execute("CREATE UNIQUE INDEX quality_projects_id_company_idx ON projects(id,company_id)")
    # An owned row must never silently change tenants or return to legacy scope.
    op.execute('''CREATE FUNCTION quality_owner_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        IF OLD.project_id IS NOT NULL AND
           (NEW.project_id IS DISTINCT FROM OLD.project_id OR
            NEW.company_id IS DISTINCT FROM OLD.company_id) THEN
            RAISE EXCEPTION 'Exact document owner is immutable' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
    END $$''')
    for table in OWNER_TABLES:
        if table in JOURNAL_TABLES:
            op.execute(f'ALTER TABLE {table} ADD COLUMN company_id INTEGER')
        op.execute(f'ALTER TABLE {table} ADD COLUMN project_id INTEGER')
        op.execute(f'''ALTER TABLE {table} ADD CONSTRAINT {table}_quality_owner_pair
            CHECK(project_id IS NULL OR (project_id>0 AND company_id IS NOT NULL AND company_id>0))''')
        if table in JOURNAL_TABLES:
            op.execute(f'''ALTER TABLE {table} ADD CONSTRAINT {table}_quality_owner_complete
                CHECK((company_id IS NULL) = (project_id IS NULL))''')
        # Referenced owner index belongs to this independent release migration.
        op.execute(f'''ALTER TABLE {table} ADD CONSTRAINT {table}_quality_project_fk
            FOREIGN KEY(project_id,company_id) REFERENCES projects(id,company_id)''')
        op.execute(f'''CREATE INDEX {table}_quality_owner_idx
            ON {table}(company_id,project_id,id) WHERE project_id IS NOT NULL''')
        op.execute(f'''CREATE TRIGGER quality_owner_immutable BEFORE UPDATE OF company_id,project_id
            ON {table} FOR EACH ROW EXECUTE FUNCTION quality_owner_immutable()''')
    op.execute('''CREATE TABLE quality_owner_bootstraps (
        plan_digest TEXT PRIMARY KEY CHECK(plan_digest ~ '^[0-9a-f]{64}$'),
        company_id INTEGER NOT NULL,
        project_id INTEGER NOT NULL,
        plan JSONB NOT NULL CHECK(jsonb_typeof(plan)='object'),
        result JSONB NOT NULL CHECK(jsonb_typeof(result)='object'),
        applied_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        FOREIGN KEY(project_id,company_id) REFERENCES projects(id,company_id)
    )''')
    op.execute('''CREATE FUNCTION quality_bootstrap_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Journal ownership audit is append-only' USING ERRCODE='23514'; END;
    $$''')
    op.execute('''CREATE TRIGGER quality_bootstrap_immutable BEFORE UPDATE OR DELETE
        ON quality_owner_bootstraps FOR EACH ROW EXECUTE FUNCTION quality_bootstrap_append_only()''')
    op.execute('''CREATE TRIGGER quality_bootstrap_no_truncate BEFORE TRUNCATE
        ON quality_owner_bootstraps FOR EACH STATEMENT EXECUTE FUNCTION quality_bootstrap_append_only()''')


def downgrade():
    # Keep the locks until transaction completion; inspect a fresh committed view
    # after waiting for any concurrent writer, never a stale repeatable snapshot.
    op.execute('LOCK TABLE quality_owner_bootstraps,' + ','.join(OWNER_TABLES) + ' IN ACCESS EXCLUSIVE MODE')
    checks = ' OR '.join(f'EXISTS(SELECT 1 FROM {table} WHERE project_id IS NOT NULL LIMIT 1)'
                         for table in OWNER_TABLES)
    op.execute(f'''DO $$ BEGIN
        IF current_setting('transaction_isolation') <> 'read committed' THEN
            RAISE EXCEPTION 'Quality owner downgrade requires READ COMMITTED isolation';
        END IF;
        IF {checks} OR EXISTS(SELECT 1 FROM quality_owner_bootstraps) THEN
            RAISE EXCEPTION 'Cannot downgrade: exact document owners contain data';
        END IF;
    END $$''')
    op.execute('DROP TABLE quality_owner_bootstraps')
    op.execute('DROP FUNCTION quality_bootstrap_append_only()')
    for table in reversed(OWNER_TABLES):
        op.execute(f'DROP TRIGGER quality_owner_immutable ON {table}')
        op.execute(f'ALTER TABLE {table} DROP COLUMN project_id')
        if table in JOURNAL_TABLES:
            op.execute(f'ALTER TABLE {table} DROP COLUMN company_id')
    op.execute('DROP FUNCTION quality_owner_immutable()')
    op.execute("DROP INDEX quality_projects_id_company_idx")
