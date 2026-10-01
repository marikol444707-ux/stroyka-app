"""Company-owned customers and frozen parties of customer contracts."""

from alembic import op


revision = "0075_customer_contract_parties"
down_revision = "0074_offer_party_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE clients
            ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES companies(id),
            ADD COLUMN IF NOT EXISTS inn VARCHAR(12) DEFAULT '',
            ADD COLUMN IF NOT EXISTS kpp VARCHAR(9) DEFAULT '',
            ADD COLUMN IF NOT EXISTS ogrn VARCHAR(15) DEFAULT '',
            ADD COLUMN IF NOT EXISTS legal_address TEXT DEFAULT '',
            ADD COLUMN IF NOT EXISTS actual_address TEXT DEFAULT '',
            ADD COLUMN IF NOT EXISTS director_name VARCHAR(255) DEFAULT '',
            ADD COLUMN IF NOT EXISTS director_position VARCHAR(255) DEFAULT '',
            ADD COLUMN IF NOT EXISTS basis TEXT DEFAULT '',
            ADD COLUMN IF NOT EXISTS bank_name VARCHAR(255) DEFAULT '',
            ADD COLUMN IF NOT EXISTS bik VARCHAR(9) DEFAULT '',
            ADD COLUMN IF NOT EXISTS rs VARCHAR(20) DEFAULT '',
            ADD COLUMN IF NOT EXISTS ks VARCHAR(20) DEFAULT '';
        ALTER TABLE clients ADD CONSTRAINT clients_id_company_unique UNIQUE(id,company_id);
        CREATE INDEX clients_company_name_idx ON clients(company_id,name,id);

        ALTER TABLE projects ADD COLUMN IF NOT EXISTS client_id INTEGER;
        ALTER TABLE projects ADD CONSTRAINT projects_client_company_fk
            FOREIGN KEY (client_id,company_id) REFERENCES clients(id,company_id);
        CREATE INDEX projects_company_client_idx ON projects(company_id,client_id,id);

        ALTER TABLE project_documents
            ADD COLUMN IF NOT EXISTS customer_client_id INTEGER,
            ADD COLUMN IF NOT EXISTS party_snapshot_json JSONB,
            ADD COLUMN IF NOT EXISTS party_snapshot_hash VARCHAR(64),
            ADD COLUMN IF NOT EXISTS party_snapshot_frozen_at TIMESTAMPTZ;
        ALTER TABLE project_documents ADD CONSTRAINT project_documents_customer_company_fk
            FOREIGN KEY (customer_client_id,company_id) REFERENCES clients(id,company_id);
        ALTER TABLE project_documents ADD CONSTRAINT project_documents_party_snapshot_pair CHECK (
            (party_snapshot_json IS NULL AND party_snapshot_hash IS NULL AND party_snapshot_frozen_at IS NULL)
            OR
            (party_snapshot_json IS NOT NULL AND party_snapshot_hash ~ '^[0-9a-f]{64}$'
             AND party_snapshot_frozen_at IS NOT NULL AND customer_client_id IS NOT NULL)
        );
        CREATE INDEX project_documents_customer_contract_idx
            ON project_documents(company_id,customer_client_id,project_id,id);
    """)
    op.execute("""CREATE OR REPLACE FUNCTION public.customer_contract_party_snapshot_guard()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.party_snapshot_json IS NOT NULL AND (
             NEW.party_snapshot_json IS DISTINCT FROM OLD.party_snapshot_json OR
             NEW.party_snapshot_hash IS DISTINCT FROM OLD.party_snapshot_hash OR
             NEW.party_snapshot_frozen_at IS DISTINCT FROM OLD.party_snapshot_frozen_at OR
             NEW.customer_client_id IS DISTINCT FROM OLD.customer_client_id OR
             NEW.company_id IS DISTINCT FROM OLD.company_id OR
             NEW.project_id IS DISTINCT FROM OLD.project_id OR
             NEW.side IS DISTINCT FROM OLD.side OR
             NEW.doc_type IS DISTINCT FROM OLD.doc_type OR
             NEW.number IS DISTINCT FROM OLD.number OR
             NEW.doc_date IS DISTINCT FROM OLD.doc_date OR
             NEW.counterparty IS DISTINCT FROM OLD.counterparty OR
             NEW.sign_status IS DISTINCT FROM OLD.sign_status OR
             NEW.scan_url IS DISTINCT FROM OLD.scan_url
          ) THEN
            RAISE EXCEPTION 'Customer contract party snapshot is immutable' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END;
        $$""")
    op.execute("""CREATE TRIGGER trg_customer_contract_party_snapshot_guard
        BEFORE UPDATE ON project_documents FOR EACH ROW
        EXECUTE FUNCTION public.customer_contract_party_snapshot_guard()""")


def downgrade():
    op.execute("LOCK TABLE clients,projects,project_documents IN ACCESS EXCLUSIVE MODE")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM clients WHERE company_id IS NOT NULL)
           OR EXISTS (SELECT 1 FROM projects WHERE client_id IS NOT NULL)
           OR EXISTS (SELECT 1 FROM project_documents WHERE party_snapshot_json IS NOT NULL) THEN
          RAISE EXCEPTION 'Cannot discard customer ownership or contract party snapshots';
        END IF;
        END $$""")
    op.execute("DROP TRIGGER IF EXISTS trg_customer_contract_party_snapshot_guard ON project_documents")
    op.execute("DROP FUNCTION IF EXISTS public.customer_contract_party_snapshot_guard()")
    op.execute("ALTER TABLE project_documents DROP CONSTRAINT project_documents_party_snapshot_pair")
    op.execute("ALTER TABLE project_documents DROP CONSTRAINT project_documents_customer_company_fk")
    op.execute("DROP INDEX IF EXISTS project_documents_customer_contract_idx")
    op.execute("ALTER TABLE project_documents DROP COLUMN party_snapshot_frozen_at, DROP COLUMN party_snapshot_hash, DROP COLUMN party_snapshot_json, DROP COLUMN customer_client_id")
    op.execute("ALTER TABLE projects DROP CONSTRAINT projects_client_company_fk")
    op.execute("DROP INDEX IF EXISTS projects_company_client_idx")
    op.execute("ALTER TABLE projects DROP COLUMN client_id")
    op.execute("ALTER TABLE clients DROP CONSTRAINT clients_id_company_unique")
    op.execute("DROP INDEX IF EXISTS clients_company_name_idx")
    op.execute("""ALTER TABLE clients DROP COLUMN company_id,DROP COLUMN inn,DROP COLUMN kpp,
        DROP COLUMN ogrn,DROP COLUMN legal_address,DROP COLUMN actual_address,DROP COLUMN director_name,
        DROP COLUMN director_position,DROP COLUMN basis,DROP COLUMN bank_name,DROP COLUMN bik,
        DROP COLUMN rs,DROP COLUMN ks""")
