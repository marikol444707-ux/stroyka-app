"""Freeze exact sender and recipient of addressed outgoing customer letters."""

from alembic import op


revision = "0080_outgoing_letter_parties"
down_revision = "0079_warehouse_movement_document"
branch_labels = None
depends_on = None


UPGRADE_SQL = """ALTER TABLE project_letters
        ADD COLUMN IF NOT EXISTS party_snapshot_json JSONB,
        ADD COLUMN IF NOT EXISTS party_snapshot_hash CHAR(64),
        ADD COLUMN IF NOT EXISTS party_snapshot_frozen_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS customer_client_id INTEGER;
        ALTER TABLE project_letters ADD CONSTRAINT project_letter_party_snapshot_complete CHECK (
          (party_snapshot_json IS NULL AND party_snapshot_hash IS NULL
           AND party_snapshot_frozen_at IS NULL AND customer_client_id IS NULL)
          OR (jsonb_typeof(party_snapshot_json)='object'
              AND party_snapshot_hash ~ '^[0-9a-f]{64}$'
              AND party_snapshot_frozen_at IS NOT NULL AND customer_client_id IS NOT NULL)
        );
        CREATE OR REPLACE FUNCTION public.project_letter_party_snapshot_guard()
        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
          IF OLD.party_snapshot_json IS NOT NULL AND (
             NEW.project_name IS DISTINCT FROM OLD.project_name OR
             NEW.company_id IS DISTINCT FROM OLD.company_id OR NEW.project_id IS DISTINCT FROM OLD.project_id OR
             NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id OR
             NEW.side IS DISTINCT FROM OLD.side OR NEW.direction IS DISTINCT FROM OLD.direction OR
             NEW.subject IS DISTINCT FROM OLD.subject OR NEW.body IS DISTINCT FROM OLD.body OR
             NEW.counterparty IS DISTINCT FROM OLD.counterparty OR NEW.letter_date IS DISTINCT FROM OLD.letter_date OR
             NEW.file_url IS DISTINCT FROM OLD.file_url OR NEW.author IS DISTINCT FROM OLD.author OR
             NEW.status IS DISTINCT FROM OLD.status OR NEW.delivery_status IS DISTINCT FROM OLD.delivery_status OR
             NEW.published_at IS DISTINCT FROM OLD.published_at OR
             NEW.published_by_id IS DISTINCT FROM OLD.published_by_id OR
             NEW.published_by_name IS DISTINCT FROM OLD.published_by_name OR
             NEW.client_request_id IS DISTINCT FROM OLD.client_request_id OR
             NEW.customer_client_id IS DISTINCT FROM OLD.customer_client_id OR
             NEW.party_snapshot_json IS DISTINCT FROM OLD.party_snapshot_json OR
             NEW.party_snapshot_hash IS DISTINCT FROM OLD.party_snapshot_hash OR
             NEW.party_snapshot_frozen_at IS DISTINCT FROM OLD.party_snapshot_frozen_at
          ) THEN RAISE EXCEPTION 'Published customer letter parties are immutable' USING ERRCODE='23514'; END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER project_letter_party_snapshot_guard BEFORE UPDATE ON project_letters
        FOR EACH ROW EXECUTE FUNCTION public.project_letter_party_snapshot_guard();"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    op.execute("LOCK TABLE project_letters IN ACCESS EXCLUSIVE MODE")
    op.execute("""DO $$ BEGIN IF EXISTS (
        SELECT 1 FROM project_letters WHERE party_snapshot_json IS NOT NULL
    ) THEN RAISE EXCEPTION 'Cannot discard frozen outgoing letter parties'; END IF; END $$""")
    op.execute("DROP TRIGGER project_letter_party_snapshot_guard ON project_letters")
    op.execute("DROP FUNCTION public.project_letter_party_snapshot_guard()")
    op.execute("ALTER TABLE project_letters DROP CONSTRAINT project_letter_party_snapshot_complete")
    op.execute("""ALTER TABLE project_letters DROP COLUMN customer_client_id,
        DROP COLUMN party_snapshot_frozen_at,DROP COLUMN party_snapshot_hash,DROP COLUMN party_snapshot_json""")
