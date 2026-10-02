"""Explicit intercompany warehouse transfers with immutable paired evidence."""

from alembic import op


revision = "0082_intercompany_transfers"
down_revision = "0081_supply_project_id"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE intercompany_warehouse_transfers (
        id BIGSERIAL PRIMARY KEY,
        request_id UUID NOT NULL,
        source_company_id INTEGER NOT NULL REFERENCES companies(id),
        destination_company_id INTEGER NOT NULL REFERENCES companies(id),
        source_stock_id INTEGER NOT NULL,
        source_location TEXT NOT NULL DEFAULT 'Основной склад',
        destination_location TEXT NOT NULL DEFAULT 'Основной склад',
        material_name TEXT NOT NULL,
        unit TEXT NOT NULL,
        quantity NUMERIC(18,6) NOT NULL CHECK(quantity>0),
        unit_price NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK(unit_price>=0),
        category TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending','accepted','rejected','cancelled')),
        created_by_user_id INTEGER NOT NULL REFERENCES users(id),
        created_by_name TEXT NOT NULL,
        source_approved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        decision_company_id INTEGER REFERENCES companies(id),
        decided_by_user_id INTEGER REFERENCES users(id),
        decided_by_name TEXT,
        decided_at TIMESTAMPTZ,
        decision_reason TEXT,
        source_movement_id INTEGER,
        destination_movement_id INTEGER,
        source_document_json JSONB NOT NULL,
        destination_document_json JSONB NOT NULL,
        source_document_hash CHAR(64) NOT NULL,
        destination_document_hash CHAR(64) NOT NULL,
        version BIGINT NOT NULL DEFAULT 1 CHECK(version>0),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK(source_company_id<>destination_company_id),
        CHECK(
          (status='pending' AND decision_company_id IS NULL AND decided_by_user_id IS NULL
            AND decided_at IS NULL AND source_movement_id IS NULL AND destination_movement_id IS NULL)
          OR
          (status='accepted' AND decision_company_id=destination_company_id
            AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL
            AND source_movement_id IS NOT NULL AND destination_movement_id IS NOT NULL)
          OR
          (status='rejected' AND decision_company_id=destination_company_id
            AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL
            AND length(btrim(decision_reason))>0
            AND source_movement_id IS NULL AND destination_movement_id IS NULL)
          OR
          (status='cancelled' AND decision_company_id=source_company_id
            AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL
            AND length(btrim(decision_reason))>0
            AND source_movement_id IS NULL AND destination_movement_id IS NULL)
        ),
        UNIQUE(source_company_id,request_id)
    )""")
    op.execute("CREATE INDEX intercompany_transfer_source_feed ON intercompany_warehouse_transfers(source_company_id,id DESC)")
    op.execute("CREATE INDEX intercompany_transfer_destination_feed ON intercompany_warehouse_transfers(destination_company_id,id DESC)")
    op.execute("""CREATE TABLE intercompany_warehouse_transfer_events (
        id BIGSERIAL PRIMARY KEY,
        transfer_id BIGINT NOT NULL REFERENCES intercompany_warehouse_transfers(id),
        company_id INTEGER NOT NULL REFERENCES companies(id),
        actor_id INTEGER NOT NULL REFERENCES users(id),
        actor_name TEXT NOT NULL,
        action TEXT NOT NULL CHECK(action IN
            ('source_approved','destination_accepted','destination_rejected','source_cancelled')),
        details JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")
    op.execute("CREATE INDEX intercompany_transfer_event_history ON intercompany_warehouse_transfer_events(transfer_id,id)")
    op.execute("""CREATE FUNCTION guard_intercompany_warehouse_transfer() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF TG_TABLE_NAME='intercompany_warehouse_transfer_events' OR TG_OP='DELETE' THEN
            RAISE EXCEPTION 'Intercompany warehouse transfers and events cannot be deleted or rewritten';
        END IF;
        IF NEW.id<>OLD.id OR NEW.request_id<>OLD.request_id
          OR NEW.source_company_id<>OLD.source_company_id
          OR NEW.destination_company_id<>OLD.destination_company_id
          OR NEW.source_stock_id<>OLD.source_stock_id
          OR NEW.source_location<>OLD.source_location
          OR NEW.destination_location<>OLD.destination_location
          OR NEW.material_name<>OLD.material_name OR NEW.unit<>OLD.unit
          OR NEW.quantity<>OLD.quantity OR NEW.unit_price<>OLD.unit_price
          OR NEW.category<>OLD.category OR NEW.reason<>OLD.reason
          OR NEW.created_by_user_id<>OLD.created_by_user_id
          OR NEW.created_by_name<>OLD.created_by_name
          OR NEW.source_approved_at<>OLD.source_approved_at
          OR NEW.source_document_json<>OLD.source_document_json
          OR NEW.destination_document_json<>OLD.destination_document_json
          OR NEW.source_document_hash<>OLD.source_document_hash
          OR NEW.destination_document_hash<>OLD.destination_document_hash
          OR OLD.status<>'pending' OR NEW.status NOT IN ('accepted','rejected','cancelled')
          OR NEW.version<>OLD.version+1 THEN
            RAISE EXCEPTION 'Intercompany warehouse transfer identity, payload and terminal decision are protected';
        END IF;
        RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER intercompany_warehouse_transfer_guard
        BEFORE UPDATE OR DELETE ON intercompany_warehouse_transfers
        FOR EACH ROW EXECUTE FUNCTION guard_intercompany_warehouse_transfer()""")
    op.execute("""CREATE TRIGGER intercompany_warehouse_transfer_event_guard
        BEFORE UPDATE OR DELETE ON intercompany_warehouse_transfer_events
        FOR EACH ROW EXECUTE FUNCTION guard_intercompany_warehouse_transfer()""")


def downgrade():
    op.execute("LOCK TABLE intercompany_warehouse_transfers,intercompany_warehouse_transfer_events IN ACCESS EXCLUSIVE MODE")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM intercompany_warehouse_transfers) THEN
        RAISE EXCEPTION 'Cannot discard intercompany warehouse transfer history'; END IF; END $$""")
    op.execute("DROP TRIGGER intercompany_warehouse_transfer_event_guard ON intercompany_warehouse_transfer_events")
    op.execute("DROP TRIGGER intercompany_warehouse_transfer_guard ON intercompany_warehouse_transfers")
    op.execute("DROP TABLE intercompany_warehouse_transfer_events")
    op.execute("DROP TABLE intercompany_warehouse_transfers")
    op.execute("DROP FUNCTION guard_intercompany_warehouse_transfer()")
