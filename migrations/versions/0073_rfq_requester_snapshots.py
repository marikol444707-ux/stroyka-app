"""Freeze requester identity and delivery data when an RFQ is dispatched."""

from alembic import op


revision = "0073_rfq_requester_snapshots"
down_revision = "0072_payment_date_guard"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS delivery_address TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS requester_snapshot_json JSONB")
    op.execute("""ALTER TABLE supply_requests
        ADD CONSTRAINT ck_supply_request_delivery_address_length
        CHECK (char_length(delivery_address) <= 2000) NOT VALID""")
    op.execute("ALTER TABLE supply_requests VALIDATE CONSTRAINT ck_supply_request_delivery_address_length")
    op.execute("""CREATE OR REPLACE FUNCTION public.supply_request_requester_snapshot_guard()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.requester_snapshot_json IS NOT NULL AND
             (NEW.requester_snapshot_json IS DISTINCT FROM OLD.requester_snapshot_json OR
              NEW.company_id IS DISTINCT FROM OLD.company_id OR
              NEW.project IS DISTINCT FROM OLD.project OR
              NEW.delivery_address IS DISTINCT FROM OLD.delivery_address) THEN
            RAISE EXCEPTION 'RFQ requester snapshot is immutable' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END;
        $$""")
    op.execute("""CREATE TRIGGER trg_supply_request_requester_snapshot_guard
        BEFORE UPDATE ON supply_requests FOR EACH ROW
        EXECUTE FUNCTION public.supply_request_requester_snapshot_guard()""")


def downgrade():
    op.execute("LOCK TABLE supply_requests IN ACCESS EXCLUSIVE MODE")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM supply_requests
                    WHERE requester_snapshot_json IS NOT NULL
                       OR BTRIM(COALESCE(delivery_address,'')) <> '') THEN
          RAISE EXCEPTION 'Cannot discard RFQ requester snapshots or delivery addresses';
        END IF;
        END $$""")
    op.execute("DROP TRIGGER IF EXISTS trg_supply_request_requester_snapshot_guard ON supply_requests")
    op.execute("DROP FUNCTION IF EXISTS public.supply_request_requester_snapshot_guard()")
    op.execute("ALTER TABLE supply_requests DROP CONSTRAINT IF EXISTS ck_supply_request_delivery_address_length")
    op.execute("ALTER TABLE supply_requests DROP COLUMN requester_snapshot_json")
    op.execute("ALTER TABLE supply_requests DROP COLUMN delivery_address")
