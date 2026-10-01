"""Freeze organization and responsible parties in signed M-15 issues."""

from alembic import op


revision = "0078_material_transfer_parties"
down_revision = "0077_customer_act_contract_basis"
branch_labels = None
depends_on = None


GUARD_SQL = r"""CREATE OR REPLACE FUNCTION public.material_transfer_document_snapshot_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.issue_party_snapshot_json IS NOT NULL AND (
     NEW.company_id IS DISTINCT FROM OLD.company_id OR
     NEW.project_id IS DISTINCT FROM OLD.project_id OR
     NEW.project_name IS DISTINCT FROM OLD.project_name OR
     NEW.from_location IS DISTINCT FROM OLD.from_location OR
     NEW.to_user_id IS DISTINCT FROM OLD.to_user_id OR
     NEW.to_person IS DISTINCT FROM OLD.to_person OR
     NEW.to_person_role IS DISTINCT FROM OLD.to_person_role OR
     NEW.work_package IS DISTINCT FROM OLD.work_package OR
     NEW.material_name IS DISTINCT FROM OLD.material_name OR
     NEW.quantity IS DISTINCT FROM OLD.quantity OR
     NEW.unit IS DISTINCT FROM OLD.unit OR
     NEW.transfer_date IS DISTINCT FROM OLD.transfer_date OR
     NEW.notes IS DISTINCT FROM OLD.notes OR
     NEW.created_by IS DISTINCT FROM OLD.created_by OR
     NEW.invoice_id IS DISTINCT FROM OLD.invoice_id OR
     NEW.invoice_line_key IS DISTINCT FROM OLD.invoice_line_key OR
     NEW.invoice_line_index IS DISTINCT FROM OLD.invoice_line_index OR
     NEW.invoice_number IS DISTINCT FROM OLD.invoice_number OR
     NEW.issue_party_snapshot_json IS DISTINCT FROM OLD.issue_party_snapshot_json OR
     NEW.issue_party_snapshot_hash IS DISTINCT FROM OLD.issue_party_snapshot_hash OR
     NEW.issue_party_snapshot_frozen_at IS DISTINCT FROM OLD.issue_party_snapshot_frozen_at
  ) THEN
    RAISE EXCEPTION 'Material issue snapshot is immutable' USING ERRCODE='23514';
  END IF;
  IF OLD.receipt_party_snapshot_json IS NOT NULL AND (
     NEW.signed IS DISTINCT FROM OLD.signed OR
     NEW.signed_at IS DISTINCT FROM OLD.signed_at OR
     NEW.status IS DISTINCT FROM OLD.status OR
     NEW.cancelled_at IS DISTINCT FROM OLD.cancelled_at OR
     NEW.cancelled_by IS DISTINCT FROM OLD.cancelled_by OR
     NEW.cancel_reason IS DISTINCT FROM OLD.cancel_reason OR
     NEW.receipt_party_snapshot_json IS DISTINCT FROM OLD.receipt_party_snapshot_json OR
     NEW.receipt_party_snapshot_hash IS DISTINCT FROM OLD.receipt_party_snapshot_hash OR
     NEW.receipt_party_snapshot_frozen_at IS DISTINCT FROM OLD.receipt_party_snapshot_frozen_at
  ) THEN
    RAISE EXCEPTION 'Signed material receipt snapshot is immutable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END;
$$"""


def upgrade():
    op.execute(r"""
        ALTER TABLE material_transfers
            ADD COLUMN IF NOT EXISTS issue_party_snapshot_json JSONB,
            ADD COLUMN IF NOT EXISTS issue_party_snapshot_hash CHAR(64),
            ADD COLUMN IF NOT EXISTS issue_party_snapshot_frozen_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS receipt_party_snapshot_json JSONB,
            ADD COLUMN IF NOT EXISTS receipt_party_snapshot_hash CHAR(64),
            ADD COLUMN IF NOT EXISTS receipt_party_snapshot_frozen_at TIMESTAMPTZ;
        ALTER TABLE material_transfers
            ADD CONSTRAINT material_transfer_issue_snapshot_complete CHECK (
              (issue_party_snapshot_json IS NULL AND issue_party_snapshot_hash IS NULL AND issue_party_snapshot_frozen_at IS NULL)
              OR (jsonb_typeof(issue_party_snapshot_json)='object' AND issue_party_snapshot_hash ~ '^[0-9a-f]{64}$' AND issue_party_snapshot_frozen_at IS NOT NULL)
            ),
            ADD CONSTRAINT material_transfer_receipt_snapshot_complete CHECK (
              (receipt_party_snapshot_json IS NULL AND receipt_party_snapshot_hash IS NULL AND receipt_party_snapshot_frozen_at IS NULL)
              OR (signed=TRUE AND jsonb_typeof(receipt_party_snapshot_json)='object' AND receipt_party_snapshot_hash ~ '^[0-9a-f]{64}$' AND receipt_party_snapshot_frozen_at IS NOT NULL)
            );
    """)
    op.execute(GUARD_SQL)
    op.execute("""CREATE TRIGGER material_transfer_document_snapshot_guard
        BEFORE UPDATE ON material_transfers FOR EACH ROW
        EXECUTE FUNCTION public.material_transfer_document_snapshot_guard()""")


def downgrade():
    op.execute("LOCK TABLE material_transfers IN ACCESS EXCLUSIVE MODE")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM material_transfers
                   WHERE issue_party_snapshot_json IS NOT NULL OR receipt_party_snapshot_json IS NOT NULL) THEN
          RAISE EXCEPTION 'Cannot discard frozen material transfer documents';
        END IF;
        END $$""")
    op.execute("DROP TRIGGER material_transfer_document_snapshot_guard ON material_transfers")
    op.execute("DROP FUNCTION public.material_transfer_document_snapshot_guard()")
    op.execute("ALTER TABLE material_transfers DROP CONSTRAINT material_transfer_receipt_snapshot_complete")
    op.execute("ALTER TABLE material_transfers DROP CONSTRAINT material_transfer_issue_snapshot_complete")
    op.execute("""ALTER TABLE material_transfers
        DROP COLUMN receipt_party_snapshot_frozen_at,
        DROP COLUMN receipt_party_snapshot_hash,
        DROP COLUMN receipt_party_snapshot_json,
        DROP COLUMN issue_party_snapshot_frozen_at,
        DROP COLUMN issue_party_snapshot_hash,
        DROP COLUMN issue_party_snapshot_json""")
