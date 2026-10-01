"""Freeze buyer and supplier identities on the first sent quotation."""

from alembic import op


revision = "0074_offer_party_snapshots"
down_revision = "0073_rfq_requester_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS party_snapshot_json JSONB")
    op.execute("""CREATE OR REPLACE FUNCTION public.supplier_offer_party_snapshot_guard()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.party_snapshot_json IS NOT NULL AND
             (NEW.party_snapshot_json IS DISTINCT FROM OLD.party_snapshot_json OR
              NEW.company_id IS DISTINCT FROM OLD.company_id OR
              NEW.request_id IS DISTINCT FROM OLD.request_id OR
              NEW.supplier_id IS DISTINCT FROM OLD.supplier_id) THEN
            RAISE EXCEPTION 'Supplier offer party snapshot is immutable' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END;
        $$""")
    op.execute("""CREATE TRIGGER trg_supplier_offer_party_snapshot_guard
        BEFORE UPDATE ON supplier_offers FOR EACH ROW
        EXECUTE FUNCTION public.supplier_offer_party_snapshot_guard()""")


def downgrade():
    op.execute("LOCK TABLE supplier_offers IN ACCESS EXCLUSIVE MODE")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM supplier_offers WHERE party_snapshot_json IS NOT NULL) THEN
          RAISE EXCEPTION 'Cannot discard supplier offer party snapshots';
        END IF;
        END $$""")
    op.execute("DROP TRIGGER IF EXISTS trg_supplier_offer_party_snapshot_guard ON supplier_offers")
    op.execute("DROP FUNCTION IF EXISTS public.supplier_offer_party_snapshot_guard()")
    op.execute("ALTER TABLE supplier_offers DROP COLUMN party_snapshot_json")
