"""Snapshot stocktaking, immutable decisions and exact stock adjustments; no backfill."""
from alembic import op

revision = '0030_inventory_reconciliation'
down_revision = '0029_tool_custody'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE UNIQUE INDEX inventory_owner_identity ON inventory(id,company_id)')
    op.execute('''CREATE TABLE inventory_reconciliations (
        inventory_id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL,
        project_id INTEGER REFERENCES projects(id), stock_scope TEXT NOT NULL CHECK(stock_scope IN ('main','project')),
        state TEXT NOT NULL CHECK(state IN ('draft','submitted','approved','cancelled')),
        version BIGINT NOT NULL DEFAULT 1, snapshot JSONB NOT NULL, counts JSONB NOT NULL DEFAULT '{}',
        actor_id INTEGER NOT NULL REFERENCES users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(inventory_id,company_id),
        CHECK((stock_scope='main' AND project_id IS NULL) OR (stock_scope='project' AND project_id IS NOT NULL)),
        FOREIGN KEY(inventory_id,company_id) REFERENCES inventory(id,company_id))''')
    op.execute('''CREATE TABLE inventory_reconciliation_events (
        id BIGSERIAL PRIMARY KEY, inventory_id INTEGER NOT NULL, company_id INTEGER NOT NULL,
        operation_id BIGINT NOT NULL UNIQUE, actor_id INTEGER NOT NULL REFERENCES users(id),
        actor_name TEXT NOT NULL, action TEXT NOT NULL CHECK(action IN ('create','save','submit','return','cancel','approve')),
        reason TEXT NOT NULL, state TEXT NOT NULL, counts JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(id,company_id),
        FOREIGN KEY(inventory_id,company_id) REFERENCES inventory_reconciliations(inventory_id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    op.execute('CREATE INDEX inventory_reconciliation_history ON inventory_reconciliation_events(company_id,inventory_id,id)')
    op.execute('''CREATE TABLE inventory_stock_adjustments (
        id BIGSERIAL PRIMARY KEY, inventory_id INTEGER NOT NULL, company_id INTEGER NOT NULL,
        event_id BIGINT NOT NULL, row_key TEXT NOT NULL, stock_table TEXT NOT NULL CHECK(stock_table IN ('materials','warehouse_main')),
        stock_id INTEGER NOT NULL, before_quantity NUMERIC(14,6) NOT NULL CHECK(before_quantity>=0),
        after_quantity NUMERIC(14,6) NOT NULL CHECK(after_quantity>=0), reason TEXT NOT NULL CHECK(length(trim(reason))>0),
        lot_changes JSONB NOT NULL, history_id INTEGER NOT NULL REFERENCES warehouse_history(id),
        movement_id INTEGER NOT NULL REFERENCES warehouse_movements(id),
        UNIQUE(inventory_id,row_key), UNIQUE(id,company_id),
        FOREIGN KEY(event_id,company_id) REFERENCES inventory_reconciliation_events(id,company_id),
        FOREIGN KEY(inventory_id,company_id) REFERENCES inventory_reconciliations(inventory_id,company_id))''')
    op.execute('''CREATE FUNCTION guard_inventory_event_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Inventory events and adjustments are immutable'; END $$''')
    for table in ('inventory_reconciliation_events', 'inventory_stock_adjustments'):
        op.execute(f'''CREATE TRIGGER inventory_reconciliation_immutable BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_inventory_event_immutable()''')
    op.execute('''CREATE FUNCTION guard_inventory_reconciliation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF TG_TABLE_NAME='inventory_reconciliations' THEN
            IF TG_OP='DELETE' OR OLD.state IN ('approved','cancelled') OR
                (to_jsonb(NEW)-ARRAY['counts','state','version'])<>(to_jsonb(OLD)-ARRAY['counts','state','version'])
                OR NEW.version<>OLD.version+1 THEN
                RAISE EXCEPTION 'Inventory reconciliation history is protected';
            END IF;
        ELSIF TG_TABLE_NAME='inventory' THEN
            IF EXISTS(SELECT 1 FROM inventory_reconciliations WHERE inventory_id=OLD.id) AND
               (TG_OP='DELETE' OR (to_jsonb(NEW)-'status')<>(to_jsonb(OLD)-'status')) THEN
                RAISE EXCEPTION 'Inventory identity is protected';
            END IF;
        ELSIF TG_TABLE_NAME='warehouse_movements' THEN
            IF EXISTS(SELECT 1 FROM inventory_stock_adjustments WHERE movement_id=OLD.id) THEN
                RAISE EXCEPTION 'Inventory adjustment movement is protected';
            END IF;
        ELSIF EXISTS(SELECT 1 FROM inventory_stock_adjustments WHERE history_id=OLD.id) THEN
            RAISE EXCEPTION 'Inventory adjustment history is protected';
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
        END $$''')
    for table in ('inventory_reconciliations', 'inventory', 'warehouse_history', 'warehouse_movements'):
        op.execute(f'''CREATE TRIGGER {table}_reconciliation_guard BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_inventory_reconciliation()''')


def downgrade():
    op.execute('LOCK TABLE inventory_reconciliations,inventory_reconciliation_events,inventory_stock_adjustments IN ACCESS EXCLUSIVE MODE')
    op.execute("""DO $$ BEGIN IF current_setting('transaction_isolation')<>'read committed'
        OR EXISTS(SELECT 1 FROM inventory_reconciliations) THEN
        RAISE EXCEPTION 'Cannot downgrade recorded inventory reconciliations'; END IF; END $$""")
    for table in ('inventory_reconciliations', 'inventory', 'warehouse_history', 'warehouse_movements'):
        op.execute(f'DROP TRIGGER {table}_reconciliation_guard ON {table}')
    op.execute('DROP FUNCTION guard_inventory_reconciliation()')
    for table in ('inventory_stock_adjustments', 'inventory_reconciliation_events', 'inventory_reconciliations'):
        op.execute(f'DROP TABLE {table}')
    op.execute('DROP FUNCTION guard_inventory_event_immutable()')
    op.execute('DROP INDEX inventory_owner_identity')
