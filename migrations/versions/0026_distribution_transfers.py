"""Two-stage distribution custody, without synthetic main-warehouse returns."""
from alembic import op

revision = '0026_distribution_transfers'
down_revision = "0025_warehouse_distribution"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''ALTER TABLE warehouse_distribution_allocations
        ADD COLUMN transferred_quantity NUMERIC(14,6) NOT NULL DEFAULT 0,
        ADD CONSTRAINT distribution_entitlement CHECK
        (transferred_quantity>=0 AND returned_quantity+transferred_quantity<=quantity)''')
    op.execute('''ALTER TABLE warehouse_distribution_operations
        DROP CONSTRAINT warehouse_distribution_operations_kind_check,
        ADD CONSTRAINT warehouse_distribution_operations_kind_check
        CHECK(kind IN ('issue','return','dispatch','receipt'))''')
    op.execute('''CREATE OR REPLACE FUNCTION guard_warehouse_distribution_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        IF TG_TABLE_NAME='warehouse_distribution_allocations' AND TG_OP='UPDATE' THEN
            IF (to_jsonb(NEW)-'returned_quantity'-'transferred_quantity')=
               (to_jsonb(OLD)-'returned_quantity'-'transferred_quantity')
               AND NEW.returned_quantity>=OLD.returned_quantity
               AND NEW.transferred_quantity>=OLD.transferred_quantity THEN RETURN NEW; END IF;
        ELSIF TG_TABLE_NAME='warehouse_distribution_operations' AND TG_OP='UPDATE' THEN
            IF OLD.result IS NULL AND NEW.result IS NOT NULL
               AND (to_jsonb(NEW)-'result')=(to_jsonb(OLD)-'result') THEN RETURN NEW; END IF;
        END IF;
        RAISE EXCEPTION 'Warehouse distribution business records are immutable'; END $$''')
    op.execute('''CREATE TABLE warehouse_distribution_transfers (
        id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL,
        operation_id BIGINT NOT NULL UNIQUE,
        source_allocation_id BIGINT NOT NULL,
        to_project_id INTEGER NOT NULL REFERENCES projects(id), to_project_name TEXT NOT NULL,
        quantity NUMERIC(14,6) NOT NULL CHECK(quantity>0),
        stock_snapshot JSONB NOT NULL,
        movement_id INTEGER NOT NULL UNIQUE REFERENCES warehouse_movements(id),
        lot_movement_id INTEGER NOT NULL UNIQUE REFERENCES warehouse_lot_movements(id),
        history_id INTEGER NOT NULL UNIQUE REFERENCES warehouse_history(id),
        reason TEXT NOT NULL, created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(id,company_id),
        FOREIGN KEY(source_allocation_id,company_id) REFERENCES warehouse_distribution_allocations(id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES warehouse_distribution_operations(id,company_id))''')
    op.execute('''CREATE INDEX distribution_transfer_recent ON warehouse_distribution_transfers(company_id,id DESC)''')
    op.execute('''CREATE TABLE warehouse_distribution_transfer_receipts (
        id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL,
        transfer_id BIGINT NOT NULL, operation_id BIGINT NOT NULL UNIQUE,
        quantity NUMERIC(14,6) NOT NULL CHECK(quantity>=0),
        expected_quantity NUMERIC(14,6) NOT NULL CHECK(expected_quantity>0 AND expected_quantity>=quantity),
        allocation_id BIGINT UNIQUE,
        reason TEXT NOT NULL, created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK((quantity=0)=(allocation_id IS NULL)),
        FOREIGN KEY(transfer_id,company_id) REFERENCES warehouse_distribution_transfers(id,company_id),
        FOREIGN KEY(operation_id,company_id) REFERENCES warehouse_distribution_operations(id,company_id),
        FOREIGN KEY(allocation_id,company_id) REFERENCES warehouse_distribution_allocations(id,company_id))''')
    op.execute('''CREATE INDEX distribution_transfer_receipt_history
        ON warehouse_distribution_transfer_receipts(company_id,transfer_id,id)''')
    for table in ('transfers', 'transfer_receipts'):
        op.execute(f'''CREATE TRIGGER distribution_{table}_immutable BEFORE UPDATE OR DELETE
            ON warehouse_distribution_{table} FOR EACH ROW EXECUTE FUNCTION guard_warehouse_distribution_immutable()''')
    op.execute('''CREATE FUNCTION guard_distribution_transit() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE a warehouse_distribution_allocations; parent warehouse_distribution_allocations;
                t warehouse_distribution_transfers; accepted NUMERIC;
        BEGIN
        IF TG_TABLE_NAME='warehouse_distribution_transfers' THEN
            IF EXISTS(SELECT 1 FROM projects WHERE company_id=NEW.company_id
                AND lower(btrim(name))=lower('В пути')) THEN RAISE EXCEPTION 'Reserved transit location'; END IF;
            SELECT * INTO a FROM warehouse_distribution_allocations
                WHERE id=NEW.source_allocation_id AND company_id=NEW.company_id FOR UPDATE;
            IF NOT FOUND OR a.project_id=NEW.to_project_id OR NOT EXISTS
                (SELECT 1 FROM projects WHERE id=NEW.to_project_id AND company_id=NEW.company_id
                 AND name=NEW.to_project_name) THEN RAISE EXCEPTION 'Invalid transfer owner'; END IF;
            UPDATE warehouse_distribution_allocations SET transferred_quantity=transferred_quantity+NEW.quantity
                WHERE id=a.id;
        ELSE
            SELECT * INTO t FROM warehouse_distribution_transfers
                WHERE id=NEW.transfer_id AND company_id=NEW.company_id FOR UPDATE;
            IF NOT FOUND THEN RAISE EXCEPTION 'Invalid transfer'; END IF;
            SELECT coalesce(sum(quantity),0) INTO accepted FROM warehouse_distribution_transfer_receipts
                WHERE transfer_id=t.id AND company_id=t.company_id;
            IF NEW.expected_quantity>t.quantity-accepted THEN RAISE EXCEPTION 'Transit quantity exceeded'; END IF;
            IF NEW.allocation_id IS NOT NULL THEN
                SELECT * INTO parent FROM warehouse_distribution_allocations
                    WHERE id=t.source_allocation_id AND company_id=t.company_id FOR SHARE;
                IF NOT FOUND THEN RAISE EXCEPTION 'Invalid receipt allocation root'; END IF;
                SELECT * INTO a FROM warehouse_distribution_allocations WHERE id=NEW.allocation_id;
                IF NOT FOUND OR a.company_id<>t.company_id OR a.project_id<>t.to_project_id
                    OR a.project_name<>t.to_project_name OR a.quantity<>NEW.quantity
                    OR a.operation_id<>NEW.operation_id
                    OR (a.company_id,a.lot_id,a.receipt_id,a.receipt_number,a.invoice_line_index,
                        a.material_name,a.unit,a.work_package) IS DISTINCT FROM
                       (parent.company_id,parent.lot_id,parent.receipt_id,parent.receipt_number,parent.invoice_line_index,
                        parent.material_name,parent.unit,parent.work_package)
                    THEN RAISE EXCEPTION 'Invalid receipt allocation'; END IF;
            END IF;
        END IF;
        RETURN NEW; END $$''')
    for table in ('transfers', 'transfer_receipts'):
        op.execute(f'''CREATE TRIGGER distribution_{table}_insert BEFORE INSERT
            ON warehouse_distribution_{table} FOR EACH ROW EXECUTE FUNCTION guard_distribution_transit()''')
    # Destination identity is protected before the first accepted child exists, too.
    op.execute('''CREATE FUNCTION guard_distribution_transit_project() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF TG_OP<>'DELETE' AND lower(btrim(NEW.name))=lower('В пути') AND EXISTS
            (SELECT 1 FROM warehouse_distribution_transfers WHERE company_id=NEW.company_id) THEN
            RAISE EXCEPTION 'Reserved transit location'; END IF;
        IF TG_OP<>'DELETE' AND EXISTS(SELECT 1 FROM warehouse_distribution_transfers
            WHERE company_id=NEW.company_id AND to_project_id<>NEW.id
              AND lower(btrim(to_project_name))=lower(btrim(NEW.name))) THEN
            RAISE EXCEPTION 'Duplicate transit project identity'; END IF;
        IF TG_OP<>'INSERT' AND EXISTS(SELECT 1 FROM warehouse_distribution_transfers WHERE to_project_id=OLD.id)
            AND (TG_OP='DELETE' OR (OLD.name,OLD.company_id) IS DISTINCT FROM (NEW.name,NEW.company_id)) THEN
            RAISE EXCEPTION 'Transit project identity is protected'; END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW; END $$''')
    op.execute('''CREATE TRIGGER distribution_transit_project BEFORE INSERT OR UPDATE OR DELETE ON projects
        FOR EACH ROW EXECUTE FUNCTION guard_distribution_transit_project()''')
    install_identity_guard(transfers=True)


def install_identity_guard(*, transfers):
    """Keep 0012 identity rules; only receipt outstanding semantics are extended."""
    outstanding = 'quantity>returned_quantity'
    if transfers:
        outstanding = '''(quantity>returned_quantity+transferred_quantity OR EXISTS(
            SELECT 1 FROM warehouse_distribution_transfers t
            WHERE t.source_allocation_id=warehouse_distribution_allocations.id
              AND t.company_id=warehouse_distribution_allocations.company_id
              AND t.quantity>(SELECT coalesce(sum(r.quantity),0)
                  FROM warehouse_distribution_transfer_receipts r
                  WHERE r.transfer_id=t.id AND r.company_id=t.company_id)))'''
    op.execute(f'''CREATE OR REPLACE FUNCTION guard_warehouse_distribution_identity() RETURNS trigger
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
                      WHERE receipt_id=OLD.id AND {outstanding})
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


def downgrade():
    # A stale repeatable-read snapshot can miss a concurrent committed command.
    # Only READ COMMITTED sees it after the ACCESS EXCLUSIVE lock is acquired.
    op.execute("""DO $$ BEGIN
        IF current_setting('transaction_isolation') <> 'read committed' THEN
            RAISE EXCEPTION 'Distribution downgrade requires READ COMMITTED isolation';
        END IF;
    END $$""")
    op.execute('''LOCK TABLE warehouse_distribution_operations, warehouse_distribution_allocations,
        warehouse_distribution_transfers, warehouse_distribution_transfer_receipts IN ACCESS EXCLUSIVE MODE''')
    op.execute('''DO $$ BEGIN IF EXISTS(SELECT 1 FROM warehouse_distribution_transfers)
        OR EXISTS(SELECT 1 FROM warehouse_distribution_transfer_receipts)
        OR EXISTS(SELECT 1 FROM warehouse_distribution_operations WHERE kind IN ('dispatch','receipt'))
        OR EXISTS(SELECT 1 FROM warehouse_distribution_allocations WHERE transferred_quantity<>0)
        THEN RAISE EXCEPTION 'Cannot downgrade distribution transit with business data'; END IF; END $$''')
    install_identity_guard(transfers=False)
    op.execute('DROP TRIGGER distribution_transit_project ON projects')
    op.execute('DROP FUNCTION guard_distribution_transit_project()')
    op.execute('DROP TABLE warehouse_distribution_transfer_receipts, warehouse_distribution_transfers')
    op.execute('DROP FUNCTION guard_distribution_transit()')
    op.execute('ALTER TABLE warehouse_distribution_allocations DROP COLUMN transferred_quantity')
    op.execute('''ALTER TABLE warehouse_distribution_operations
        DROP CONSTRAINT warehouse_distribution_operations_kind_check,
        ADD CONSTRAINT warehouse_distribution_operations_kind_check CHECK(kind IN ('issue','return'))''')
    op.execute('''CREATE OR REPLACE FUNCTION guard_warehouse_distribution_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        IF TG_TABLE_NAME='warehouse_distribution_allocations' AND TG_OP='UPDATE' THEN
            IF (to_jsonb(NEW)-'returned_quantity')=(to_jsonb(OLD)-'returned_quantity')
               AND NEW.returned_quantity>=OLD.returned_quantity THEN RETURN NEW; END IF;
        ELSIF TG_TABLE_NAME='warehouse_distribution_operations' AND TG_OP='UPDATE' THEN
            IF OLD.result IS NULL AND NEW.result IS NOT NULL
               AND (to_jsonb(NEW)-'result')=(to_jsonb(OLD)-'result') THEN RETURN NEW; END IF;
        END IF;
        RAISE EXCEPTION 'Warehouse distribution business records are immutable'; END $$''')
