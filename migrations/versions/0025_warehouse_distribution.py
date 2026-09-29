"""Exact lot allocations and immutable physical-return attestations; no backfill."""
from alembic import op

revision = '0025_warehouse_distribution'
down_revision = "0024_company_material_aliases"
branch_labels = None
depends_on = None


def upgrade():
    # Older installations create these lazily. Create prerequisites here, never
    # from feature requests, and preserve them on downgrade (shared legacy data).
    op.execute('''CREATE TABLE IF NOT EXISTS warehouse_receipt_lots (
        id SERIAL PRIMARY KEY, company_id INT NOT NULL, project_id INT,
        project_name VARCHAR(255), warehouse_location VARCHAR(255) NOT NULL,
        warehouse_target VARCHAR(30) NOT NULL, warehouse_invoice_id INT NOT NULL,
        invoice_line_index INT NOT NULL, material_name TEXT NOT NULL,
        document_quantity NUMERIC(14,6), document_unit VARCHAR(50),
        received_quantity NUMERIC(14,6) NOT NULL, unit VARCHAR(50) NOT NULL,
        available_quantity NUMERIC(14,6) NOT NULL,
        status VARCHAR(30) NOT NULL DEFAULT 'active', created_by VARCHAR(255),
        created_at TIMESTAMP DEFAULT NOW()
    )''')
    op.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_warehouse_receipt_lot_source
        ON warehouse_receipt_lots(company_id,warehouse_invoice_id,invoice_line_index)''')
    op.execute('''CREATE INDEX IF NOT EXISTS idx_warehouse_receipt_lot_available
        ON warehouse_receipt_lots(company_id,warehouse_location,material_name,unit) WHERE status='active' ''')
    op.execute('''CREATE TABLE IF NOT EXISTS warehouse_lot_movements (
        id SERIAL PRIMARY KEY, lot_id INT NOT NULL REFERENCES warehouse_receipt_lots(id),
        company_id INT NOT NULL, warehouse_movement_id INT NOT NULL,
        operation_type VARCHAR(50) NOT NULL, quantity NUMERIC(14,6) NOT NULL,
        unit VARCHAR(50) NOT NULL, from_location VARCHAR(255) NOT NULL,
        to_location VARCHAR(255) NOT NULL, created_by VARCHAR(255),
        reversal_of_id INT, created_at TIMESTAMP DEFAULT NOW()
    )''')
    op.execute('ALTER TABLE warehouse_lot_movements ADD COLUMN IF NOT EXISTS reversal_of_id INT')
    op.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_warehouse_lot_movement_operation
        ON warehouse_lot_movements(lot_id,warehouse_movement_id,operation_type)''')
    op.execute('''CREATE INDEX IF NOT EXISTS idx_warehouse_lot_movement_company
        ON warehouse_lot_movements(company_id,lot_id,created_at DESC)''')
    op.execute('''CREATE TABLE warehouse_distribution_operations (
        id BIGSERIAL PRIMARY KEY,
        company_id INTEGER NOT NULL REFERENCES companies(id),
        request_id UUID NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('issue','return')),
        payload_hash CHAR(64) NOT NULL,
        result JSONB,
        reason TEXT NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 1000),
        created_by_id INTEGER,
        created_by TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(company_id,request_id), UNIQUE(id,company_id)
    )''')
    op.execute('''CREATE TABLE warehouse_distribution_allocations (
        id BIGSERIAL PRIMARY KEY,
        company_id INTEGER NOT NULL REFERENCES companies(id),
        operation_id BIGINT NOT NULL,
        lot_id INTEGER NOT NULL REFERENCES warehouse_receipt_lots(id),
        receipt_id INTEGER NOT NULL REFERENCES warehouse_invoices(id),
        receipt_number TEXT NOT NULL,
        invoice_line_index INTEGER NOT NULL CHECK (invoice_line_index>=0),
        project_id INTEGER NOT NULL REFERENCES projects(id),
        project_name TEXT NOT NULL,
        material_name TEXT NOT NULL,
        unit TEXT NOT NULL,
        work_package TEXT NOT NULL,
        quantity NUMERIC(14,6) NOT NULL CHECK(quantity>0),
        returned_quantity NUMERIC(14,6) NOT NULL DEFAULT 0
            CHECK(returned_quantity>=0 AND returned_quantity<=quantity),
        movement_id INTEGER NOT NULL UNIQUE REFERENCES warehouse_movements(id),
        lot_movement_id INTEGER NOT NULL UNIQUE REFERENCES warehouse_lot_movements(id),
        movement_snapshot JSONB NOT NULL,
        reason TEXT NOT NULL,
        created_by TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES warehouse_distribution_operations(id,company_id)
    )''')
    op.execute('''CREATE INDEX warehouse_distribution_company_recent
        ON warehouse_distribution_allocations(company_id,id DESC)''')
    op.execute('''CREATE INDEX warehouse_distribution_project_identity
        ON warehouse_distribution_allocations(project_id)''')
    op.execute('''CREATE INDEX warehouse_distribution_receipt_outstanding
        ON warehouse_distribution_allocations(receipt_id) WHERE quantity>returned_quantity''')
    op.execute('''CREATE TABLE warehouse_distribution_returns (
        id BIGSERIAL PRIMARY KEY,
        company_id INTEGER NOT NULL,
        allocation_id BIGINT NOT NULL,
        operation_id BIGINT NOT NULL UNIQUE,
        quantity NUMERIC(14,6) NOT NULL CHECK(quantity>0),
        movement_id INTEGER NOT NULL UNIQUE REFERENCES warehouse_movements(id),
        lot_movement_id INTEGER NOT NULL UNIQUE REFERENCES warehouse_lot_movements(id),
        movement_snapshot JSONB NOT NULL,
        reason TEXT NOT NULL CHECK(length(btrim(reason)) BETWEEN 1 AND 1000),
        created_by TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        FOREIGN KEY(allocation_id,company_id) REFERENCES warehouse_distribution_allocations(id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES warehouse_distribution_operations(id,company_id)
    )''')
    op.execute('''CREATE INDEX warehouse_distribution_return_history
        ON warehouse_distribution_returns(company_id,allocation_id,id)''')
    op.execute('''CREATE FUNCTION guard_warehouse_distribution_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        IF TG_TABLE_NAME='warehouse_distribution_allocations' AND TG_OP='UPDATE' THEN
            IF (to_jsonb(NEW)-'returned_quantity')=(to_jsonb(OLD)-'returned_quantity')
               AND NEW.returned_quantity>=OLD.returned_quantity THEN RETURN NEW; END IF;
        ELSIF TG_TABLE_NAME='warehouse_distribution_operations' AND TG_OP='UPDATE' THEN
            IF OLD.result IS NULL AND NEW.result IS NOT NULL
               AND (to_jsonb(NEW)-'result')=(to_jsonb(OLD)-'result') THEN RETURN NEW; END IF;
        END IF;
        RAISE EXCEPTION 'Warehouse distribution business records are immutable';
        END $$''')
    for table in ('operations', 'allocations', 'returns'):
        op.execute(f'''CREATE TRIGGER warehouse_distribution_{table}_immutable
            BEFORE UPDATE OR DELETE ON warehouse_distribution_{table}
            FOR EACH ROW EXECUTE FUNCTION guard_warehouse_distribution_immutable()''')
    op.execute('''CREATE FUNCTION guard_warehouse_distribution_identity() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE old_row jsonb; new_row jsonb;
        BEGIN
        IF TG_TABLE_NAME='projects' AND TG_OP IN ('INSERT','UPDATE') THEN
            IF EXISTS(SELECT 1 FROM warehouse_distribution_allocations
                      WHERE company_id=NEW.company_id AND project_id<>NEW.id
                        AND lower(btrim(project_name))=lower(btrim(NEW.name))) THEN
                RAISE EXCEPTION 'Duplicate distributed project identity is protected';
            END IF;
            IF TG_OP='INSERT' THEN RETURN NEW; END IF;
        END IF;
        old_row := to_jsonb(OLD);
        IF TG_OP='UPDATE' THEN new_row := to_jsonb(NEW); END IF;
        IF TG_TABLE_NAME='projects' THEN
            IF EXISTS(SELECT 1 FROM warehouse_distribution_allocations WHERE project_id=OLD.id)
               AND (TG_OP='DELETE' OR
                    (OLD.name,OLD.company_id) IS DISTINCT FROM (NEW.name,NEW.company_id)) THEN
                RAISE EXCEPTION 'Distributed project identity is protected';
            END IF;
        ELSIF TG_TABLE_NAME='warehouse_invoices' THEN
            IF EXISTS(SELECT 1 FROM warehouse_distribution_allocations
                      WHERE receipt_id=OLD.id AND quantity>returned_quantity)
               AND (TG_OP='DELETE' OR
                    (old_row->'company_id',old_row->'items',old_row->'status',old_row->'project',
                     old_row->'location',old_row->'number',old_row->'date',old_row->'supplier_id',
                     old_row->'source_type',old_row->'source_id',old_row->'supplier_name',
                     old_row->'warehouse_target',old_row->'selected_action',old_row->'supplier_invoice_id',
                     old_row->'supply_delivery_id',old_row->'supply_request_id') IS DISTINCT FROM
                    (new_row->'company_id',new_row->'items',new_row->'status',new_row->'project',
                     new_row->'location',new_row->'number',new_row->'date',new_row->'supplier_id',
                     new_row->'source_type',new_row->'source_id',new_row->'supplier_name',
                     new_row->'warehouse_target',new_row->'selected_action',new_row->'supplier_invoice_id',
                     new_row->'supply_delivery_id',new_row->'supply_request_id')) THEN
                RAISE EXCEPTION 'Outstanding distribution receipt identity is protected';
            END IF;
        ELSIF TG_TABLE_NAME IN ('materials','warehouse_main') THEN
            IF (TG_OP='DELETE' OR
                (old_row->'name',old_row->'unit',old_row->'project',old_row->'work_package',old_row->'company_id')
                 IS DISTINCT FROM
                (new_row->'name',new_row->'unit',new_row->'project',new_row->'work_package',new_row->'company_id'))
               AND EXISTS(SELECT 1 FROM warehouse_distribution_allocations a,
                                 (VALUES(old_row),(new_row)) AS candidate(identity)
                   WHERE a.company_id=(candidate.identity->>'company_id')::integer
                     AND lower(a.material_name)=lower(candidate.identity->>'name')
                     AND lower(replace(replace(replace(replace(trim(a.unit),'²','2'),'³','3'),'.',''),' ',''))=
                         lower(replace(replace(replace(replace(trim(candidate.identity->>'unit'),'²','2'),'³','3'),'.',''),' ',''))
                     AND (TG_TABLE_NAME='warehouse_main' OR
                          (a.project_name=candidate.identity->>'project' AND a.work_package=
                           coalesce(nullif(candidate.identity->>'work_package',''),'Основная')))) THEN
                RAISE EXCEPTION 'Distributed stock identity is protected';
            END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
        END $$''')
    for table in ('projects', 'warehouse_invoices', 'materials', 'warehouse_main'):
        events = 'INSERT OR UPDATE OR DELETE' if table == 'projects' else 'UPDATE OR DELETE'
        op.execute(f'''CREATE TRIGGER {table}_distribution_identity
            BEFORE {events} ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_warehouse_distribution_identity()''')


def downgrade():
    # A stale repeatable-read snapshot can miss a concurrent committed command.
    # Only READ COMMITTED sees it after the ACCESS EXCLUSIVE lock is acquired.
    op.execute("""DO $$ BEGIN
        IF current_setting('transaction_isolation') <> 'read committed' THEN
            RAISE EXCEPTION 'Distribution downgrade requires READ COMMITTED isolation';
        END IF;
    END $$""")
    # The lock closes the check/drop race against in-flight business writes.
    op.execute('''LOCK TABLE warehouse_distribution_operations,
        warehouse_distribution_allocations, warehouse_distribution_returns IN ACCESS EXCLUSIVE MODE''')
    op.execute('''DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM warehouse_distribution_operations)
           OR EXISTS(SELECT 1 FROM warehouse_distribution_allocations)
           OR EXISTS(SELECT 1 FROM warehouse_distribution_returns) THEN
            RAISE EXCEPTION 'Cannot downgrade warehouse distribution with business data';
        END IF;
        END $$''')
    for table in ('projects', 'warehouse_invoices', 'materials', 'warehouse_main'):
        op.execute(f'DROP TRIGGER {table}_distribution_identity ON {table}')
    op.execute('DROP FUNCTION guard_warehouse_distribution_identity()')
    for table in ('returns', 'allocations', 'operations'):
        op.execute(f'DROP TABLE warehouse_distribution_{table}')
    op.execute('DROP FUNCTION guard_warehouse_distribution_immutable()')
