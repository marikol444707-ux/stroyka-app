"""Freeze signed contractor-contract parties and protected originals."""

from alembic import op


revision = "0076_contractor_contract_parties"
down_revision = "0075_customer_contract_parties"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE master_profiles
            ADD COLUMN IF NOT EXISTS kpp VARCHAR(20),
            ADD COLUMN IF NOT EXISTS ogrn VARCHAR(20),
            ADD COLUMN IF NOT EXISTS legal_address TEXT,
            ADD COLUMN IF NOT EXISTS bank_bik VARCHAR(20),
            ADD COLUMN IF NOT EXISTS bank_corr VARCHAR(50),
            ADD COLUMN IF NOT EXISTS signatory_name VARCHAR(255),
            ADD COLUMN IF NOT EXISTS signatory_position VARCHAR(255),
            ADD COLUMN IF NOT EXISTS signatory_basis VARCHAR(255);
    """)
    op.execute("""
        ALTER TABLE brigade_contracts
            ADD COLUMN IF NOT EXISTS contract_scan_url TEXT,
            ADD COLUMN IF NOT EXISTS party_snapshot_json JSONB,
            ADD COLUMN IF NOT EXISTS party_snapshot_hash VARCHAR(64),
            ADD COLUMN IF NOT EXISTS party_snapshot_frozen_at TIMESTAMPTZ;
        ALTER TABLE brigade_contracts ADD CONSTRAINT brigade_contract_party_snapshot_pair CHECK (
            (party_snapshot_json IS NULL AND party_snapshot_hash IS NULL AND party_snapshot_frozen_at IS NULL)
            OR (party_snapshot_json IS NOT NULL AND party_snapshot_hash ~ '^[0-9a-f]{64}$'
                AND party_snapshot_frozen_at IS NOT NULL AND contract_scan_url IS NOT NULL)
        );
        CREATE INDEX brigade_contract_party_snapshot_idx
            ON brigade_contracts(company_id,project_id,contractor_id,id)
            WHERE party_snapshot_json IS NOT NULL;
    """)
    op.execute("""CREATE OR REPLACE FUNCTION public.contractor_contract_party_snapshot_guard()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.party_snapshot_json IS NOT NULL AND (
             NEW.party_snapshot_json IS DISTINCT FROM OLD.party_snapshot_json OR
             NEW.party_snapshot_hash IS DISTINCT FROM OLD.party_snapshot_hash OR
             NEW.party_snapshot_frozen_at IS DISTINCT FROM OLD.party_snapshot_frozen_at OR
             NEW.contract_scan_url IS DISTINCT FROM OLD.contract_scan_url OR
             NEW.company_id IS DISTINCT FROM OLD.company_id OR
             NEW.project_id IS DISTINCT FROM OLD.project_id OR
             NEW.project_name IS DISTINCT FROM OLD.project_name OR
             NEW.brigade_name IS DISTINCT FROM OLD.brigade_name OR
             NEW.contractor_type IS DISTINCT FROM OLD.contractor_type OR
             NEW.contractor_id IS DISTINCT FROM OLD.contractor_id OR
             NEW.status IS DISTINCT FROM OLD.status OR
             NEW.signed_at IS DISTINCT FROM OLD.signed_at
          ) THEN
            RAISE EXCEPTION 'Contractor contract party snapshot is immutable' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END;
        $$""")
    op.execute("""CREATE TRIGGER trg_contractor_contract_party_snapshot_guard
        BEFORE UPDATE ON brigade_contracts FOR EACH ROW
        EXECUTE FUNCTION public.contractor_contract_party_snapshot_guard()""")


def downgrade():
    op.execute("LOCK TABLE brigade_contracts,file_ownership IN ACCESS EXCLUSIVE MODE")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM brigade_contracts WHERE party_snapshot_json IS NOT NULL)
           OR EXISTS (SELECT 1 FROM file_ownership f JOIN brigade_contracts b
                ON b.contract_scan_url='/tenant-files/' || f.id || '/content'
                WHERE f.retained_at IS NOT NULL)
           OR EXISTS (SELECT 1 FROM master_profiles WHERE
                NULLIF(kpp,'') IS NOT NULL OR NULLIF(ogrn,'') IS NOT NULL OR
                NULLIF(legal_address,'') IS NOT NULL OR NULLIF(bank_bik,'') IS NOT NULL OR
                NULLIF(bank_corr,'') IS NOT NULL OR NULLIF(signatory_name,'') IS NOT NULL OR
                NULLIF(signatory_position,'') IS NOT NULL OR NULLIF(signatory_basis,'') IS NOT NULL) THEN
          RAISE EXCEPTION 'Cannot discard retained contractor contracts';
        END IF;
        END $$""")
    op.execute("DROP TRIGGER IF EXISTS trg_contractor_contract_party_snapshot_guard ON brigade_contracts")
    op.execute("DROP FUNCTION IF EXISTS public.contractor_contract_party_snapshot_guard()")
    op.execute("DROP INDEX IF EXISTS brigade_contract_party_snapshot_idx")
    op.execute("ALTER TABLE brigade_contracts DROP CONSTRAINT brigade_contract_party_snapshot_pair")
    op.execute("ALTER TABLE brigade_contracts DROP COLUMN party_snapshot_frozen_at,DROP COLUMN party_snapshot_hash,DROP COLUMN party_snapshot_json,DROP COLUMN contract_scan_url")
    op.execute("""ALTER TABLE master_profiles
        DROP COLUMN signatory_basis,DROP COLUMN signatory_position,DROP COLUMN signatory_name,
        DROP COLUMN bank_corr,DROP COLUMN bank_bik,DROP COLUMN legal_address,DROP COLUMN ogrn,DROP COLUMN kpp""")
