"""Company-owned warehouse directory; preserve unowned legacy cards unchanged."""
from alembic import op

revision = '0031_company_warehouses'
down_revision = '0030_inventory_reconciliation'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''ALTER TABLE warehouses
        ADD COLUMN company_id INTEGER REFERENCES companies(id),
        ADD COLUMN name_key TEXT,
        ADD COLUMN archived BOOLEAN NOT NULL DEFAULT FALSE,
        ADD COLUMN version BIGINT NOT NULL DEFAULT 1 CHECK(version>0),
        ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        ADD CONSTRAINT warehouse_directory_owned_name CHECK(company_id IS NULL OR
            (name_key IS NOT NULL AND length(name_key)>0 AND name IS NOT NULL AND length(trim(name))>0))''')
    op.execute('CREATE UNIQUE INDEX warehouse_directory_identity ON warehouses(id,company_id)')
    op.execute('''CREATE UNIQUE INDEX warehouse_directory_active_name
        ON warehouses(company_id,name_key)
        WHERE company_id IS NOT NULL AND NOT archived''')
    op.execute('''CREATE TABLE warehouse_directory_events (
        id BIGSERIAL PRIMARY KEY, warehouse_id INTEGER NOT NULL, company_id INTEGER NOT NULL,
        operation_id BIGINT UNIQUE, actor_id INTEGER REFERENCES users(id), actor_name TEXT NOT NULL,
        action TEXT NOT NULL CHECK(action IN ('create','update','archive','restore','assign_owner')),
        reason TEXT NOT NULL, before_card JSONB, after_card JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK((action='assign_owner' AND operation_id IS NULL AND actor_id IS NULL AND length(trim(reason))>0)
           OR (action<>'assign_owner' AND operation_id IS NOT NULL AND actor_id IS NOT NULL)),
        FOREIGN KEY(warehouse_id,company_id) REFERENCES warehouses(id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES work_material_operations(id,company_id))''')
    op.execute('CREATE INDEX warehouse_directory_history ON warehouse_directory_events(company_id,warehouse_id,id)')
    op.execute('''CREATE FUNCTION guard_warehouse_directory() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF TG_TABLE_NAME='warehouse_directory_events' OR TG_OP='DELETE' THEN
            RAISE EXCEPTION 'Warehouse cards and their history cannot be deleted or rewritten';
        END IF;
        IF NEW.id<>OLD.id OR NEW.created_at IS DISTINCT FROM OLD.created_at
            OR (OLD.company_id IS NOT NULL AND NEW.company_id IS DISTINCT FROM OLD.company_id)
            OR NEW.version<>OLD.version+1 THEN
            RAISE EXCEPTION 'Warehouse owner and version are protected';
        END IF;
        RETURN NEW;
        END $$''')
    for table in ('warehouses', 'warehouse_directory_events'):
        op.execute(f'''CREATE TRIGGER {table}_directory_guard BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_warehouse_directory()''')


def downgrade():
    op.execute('LOCK TABLE warehouses,warehouse_directory_events IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN IF current_setting('transaction_isolation')<>'read committed'
        OR EXISTS(SELECT 1 FROM warehouse_directory_events)
        OR EXISTS(SELECT 1 FROM warehouses WHERE company_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Cannot discard warehouse ownership or recorded history'; END IF; END $$''')
    op.execute('DROP TRIGGER warehouses_directory_guard ON warehouses')
    op.execute('DROP TABLE warehouse_directory_events')
    op.execute('DROP FUNCTION guard_warehouse_directory()')
    op.execute('DROP INDEX warehouse_directory_active_name')
    op.execute('DROP INDEX warehouse_directory_identity')
    op.execute('ALTER TABLE warehouses DROP CONSTRAINT warehouse_directory_owned_name,DROP COLUMN company_id,DROP COLUMN name_key,DROP COLUMN archived,DROP COLUMN version,DROP COLUMN updated_at')
