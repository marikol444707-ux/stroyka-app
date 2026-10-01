"""Freeze exact parties and contents of M-11 warehouse movements."""

from alembic import op


revision = "0079_warehouse_movement_document"
down_revision = "0078_material_transfer_parties"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE warehouse_movements
        ADD COLUMN IF NOT EXISTS document_snapshot_json JSONB,
        ADD COLUMN IF NOT EXISTS document_snapshot_hash CHAR(64),
        ADD COLUMN IF NOT EXISTS document_snapshot_frozen_at TIMESTAMPTZ;
        ALTER TABLE warehouse_movements ADD CONSTRAINT warehouse_movement_document_snapshot_complete CHECK (
          (document_snapshot_json IS NULL AND document_snapshot_hash IS NULL AND document_snapshot_frozen_at IS NULL)
          OR (jsonb_typeof(document_snapshot_json)='object' AND document_snapshot_hash ~ '^[0-9a-f]{64}$' AND document_snapshot_frozen_at IS NOT NULL)
        );
        CREATE OR REPLACE FUNCTION public.warehouse_movement_document_snapshot_guard()
        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
          IF OLD.document_snapshot_json IS NOT NULL AND (
             NEW.company_id IS DISTINCT FROM OLD.company_id OR NEW.material_name IS DISTINCT FROM OLD.material_name OR
             NEW.from_location IS DISTINCT FROM OLD.from_location OR NEW.to_location IS DISTINCT FROM OLD.to_location OR
             NEW.quantity IS DISTINCT FROM OLD.quantity OR NEW.unit IS DISTINCT FROM OLD.unit OR
             NEW.work_package IS DISTINCT FROM OLD.work_package OR NEW.date IS DISTINCT FROM OLD.date OR
             NEW.created_by IS DISTINCT FROM OLD.created_by OR NEW.notes IS DISTINCT FROM OLD.notes OR
             NEW.source_invoice_id IS DISTINCT FROM OLD.source_invoice_id OR
             NEW.source_invoice_line_index IS DISTINCT FROM OLD.source_invoice_line_index OR
             NEW.document_snapshot_json IS DISTINCT FROM OLD.document_snapshot_json OR
             NEW.document_snapshot_hash IS DISTINCT FROM OLD.document_snapshot_hash OR
             NEW.document_snapshot_frozen_at IS DISTINCT FROM OLD.document_snapshot_frozen_at
          ) THEN RAISE EXCEPTION 'Warehouse movement document is immutable' USING ERRCODE='23514'; END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER warehouse_movement_document_snapshot_guard BEFORE UPDATE ON warehouse_movements
        FOR EACH ROW EXECUTE FUNCTION public.warehouse_movement_document_snapshot_guard();""")


def downgrade():
    op.execute("LOCK TABLE warehouse_movements IN ACCESS EXCLUSIVE MODE")
    op.execute("""DO $$ BEGIN IF EXISTS (SELECT 1 FROM warehouse_movements WHERE document_snapshot_json IS NOT NULL)
        THEN RAISE EXCEPTION 'Cannot discard frozen M-11 documents'; END IF; END $$""")
    op.execute("DROP TRIGGER warehouse_movement_document_snapshot_guard ON warehouse_movements")
    op.execute("DROP FUNCTION public.warehouse_movement_document_snapshot_guard()")
    op.execute("ALTER TABLE warehouse_movements DROP CONSTRAINT warehouse_movement_document_snapshot_complete")
    op.execute("""ALTER TABLE warehouse_movements DROP COLUMN document_snapshot_frozen_at,
        DROP COLUMN document_snapshot_hash,DROP COLUMN document_snapshot_json""")
