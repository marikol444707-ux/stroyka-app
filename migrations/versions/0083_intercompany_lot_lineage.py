"""Bind every intercompany transfer to exact receipt lots."""

from alembic import op


revision = "0083_intercompany_lot_lineage"
down_revision = "0082_intercompany_transfers"
branch_labels = None
depends_on = None


def upgrade():
    # The incomplete 0082 feature was never allowed to create production rows.
    # Refuse to invent lineage if another installation used it while disabled.
    op.execute("""DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM intercompany_warehouse_transfers) THEN
            RAISE EXCEPTION 'Cannot add exact lot lineage to existing intercompany transfers';
        END IF;
    END $$""")
    op.execute("""ALTER TABLE intercompany_warehouse_transfers
        ADD COLUMN source_lot_id INTEGER NOT NULL REFERENCES warehouse_receipt_lots(id),
        ADD COLUMN destination_receipt_id INTEGER REFERENCES warehouse_invoices(id),
        ADD COLUMN destination_lot_id INTEGER REFERENCES warehouse_receipt_lots(id)""")
    op.execute("""ALTER TABLE intercompany_warehouse_transfers
        ADD CONSTRAINT intercompany_transfer_destination_lineage CHECK(
          (status='accepted' AND destination_receipt_id IS NOT NULL AND destination_lot_id IS NOT NULL)
          OR (status<>'accepted' AND destination_receipt_id IS NULL AND destination_lot_id IS NULL)
        )""")
    op.execute("""CREATE UNIQUE INDEX intercompany_transfer_destination_receipt
        ON intercompany_warehouse_transfers(destination_receipt_id)
        WHERE destination_receipt_id IS NOT NULL""")
    op.execute("""CREATE UNIQUE INDEX intercompany_transfer_destination_lot
        ON intercompany_warehouse_transfers(destination_lot_id)
        WHERE destination_lot_id IS NOT NULL""")
    op.execute("""CREATE OR REPLACE FUNCTION guard_intercompany_warehouse_transfer()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        IF TG_TABLE_NAME='intercompany_warehouse_transfer_events' OR TG_OP='DELETE' THEN
            RAISE EXCEPTION 'Intercompany warehouse transfers and events cannot be deleted or rewritten';
        END IF;
        IF NEW.id<>OLD.id OR NEW.request_id<>OLD.request_id
          OR NEW.source_company_id<>OLD.source_company_id
          OR NEW.destination_company_id<>OLD.destination_company_id
          OR NEW.source_stock_id<>OLD.source_stock_id OR NEW.source_lot_id<>OLD.source_lot_id
          OR NEW.source_location<>OLD.source_location OR NEW.destination_location<>OLD.destination_location
          OR NEW.material_name<>OLD.material_name OR NEW.unit<>OLD.unit
          OR NEW.quantity<>OLD.quantity OR NEW.unit_price<>OLD.unit_price
          OR NEW.category<>OLD.category OR NEW.reason<>OLD.reason
          OR NEW.created_by_user_id<>OLD.created_by_user_id OR NEW.created_by_name<>OLD.created_by_name
          OR NEW.source_approved_at<>OLD.source_approved_at
          OR NEW.source_document_json<>OLD.source_document_json
          OR NEW.destination_document_json<>OLD.destination_document_json
          OR NEW.source_document_hash<>OLD.source_document_hash
          OR NEW.destination_document_hash<>OLD.destination_document_hash
          OR OLD.status<>'pending' OR NEW.status NOT IN ('accepted','rejected','cancelled')
          OR NEW.version<>OLD.version+1
          OR (NEW.status='accepted' AND
              (OLD.destination_receipt_id IS NOT NULL OR OLD.destination_lot_id IS NOT NULL
               OR NEW.destination_receipt_id IS NULL OR NEW.destination_lot_id IS NULL))
          OR (NEW.status<>'accepted' AND
              (NEW.destination_receipt_id IS NOT NULL OR NEW.destination_lot_id IS NOT NULL)) THEN
            RAISE EXCEPTION 'Intercompany warehouse transfer identity, payload and terminal decision are protected';
        END IF;
        RETURN NEW;
        END $$""")


def downgrade():
    op.execute("""LOCK TABLE intercompany_warehouse_transfers IN ACCESS EXCLUSIVE MODE""")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM intercompany_warehouse_transfers) THEN
        RAISE EXCEPTION 'Cannot discard intercompany lot lineage'; END IF; END $$""")
    op.execute("DROP INDEX intercompany_transfer_destination_lot")
    op.execute("DROP INDEX intercompany_transfer_destination_receipt")
    op.execute("ALTER TABLE intercompany_warehouse_transfers DROP CONSTRAINT intercompany_transfer_destination_lineage")
    op.execute("""ALTER TABLE intercompany_warehouse_transfers
        DROP COLUMN destination_lot_id,
        DROP COLUMN destination_receipt_id,
        DROP COLUMN source_lot_id""")
    op.execute("""CREATE OR REPLACE FUNCTION guard_intercompany_warehouse_transfer()
        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF TG_TABLE_NAME='intercompany_warehouse_transfer_events' OR TG_OP='DELETE' THEN
            RAISE EXCEPTION 'Intercompany warehouse transfers and events cannot be deleted or rewritten';
        END IF;
        IF NEW.id<>OLD.id OR NEW.request_id<>OLD.request_id
          OR NEW.source_company_id<>OLD.source_company_id OR NEW.destination_company_id<>OLD.destination_company_id
          OR NEW.source_stock_id<>OLD.source_stock_id OR NEW.source_location<>OLD.source_location
          OR NEW.destination_location<>OLD.destination_location OR NEW.material_name<>OLD.material_name
          OR NEW.unit<>OLD.unit OR NEW.quantity<>OLD.quantity OR NEW.unit_price<>OLD.unit_price
          OR NEW.category<>OLD.category OR NEW.reason<>OLD.reason
          OR NEW.created_by_user_id<>OLD.created_by_user_id OR NEW.created_by_name<>OLD.created_by_name
          OR NEW.source_approved_at<>OLD.source_approved_at OR NEW.source_document_json<>OLD.source_document_json
          OR NEW.destination_document_json<>OLD.destination_document_json
          OR NEW.source_document_hash<>OLD.source_document_hash
          OR NEW.destination_document_hash<>OLD.destination_document_hash
          OR OLD.status<>'pending' OR NEW.status NOT IN ('accepted','rejected','cancelled')
          OR NEW.version<>OLD.version+1 THEN
            RAISE EXCEPTION 'Intercompany warehouse transfer identity, payload and terminal decision are protected';
        END IF;
        RETURN NEW; END $$""")
