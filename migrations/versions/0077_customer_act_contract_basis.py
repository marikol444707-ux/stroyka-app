"""Bind signed customer KS acts to one frozen customer contract."""

from alembic import op


revision = "0077_customer_act_contract_basis"
down_revision = "0076_contractor_contract_parties"
branch_labels = None
depends_on = None


GUARD_SQL = """CREATE OR REPLACE FUNCTION public.customer_contract_party_snapshot_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.party_snapshot_json IS NOT NULL AND (
     NEW.party_snapshot_json IS DISTINCT FROM OLD.party_snapshot_json OR
     NEW.party_snapshot_hash IS DISTINCT FROM OLD.party_snapshot_hash OR
     NEW.party_snapshot_frozen_at IS DISTINCT FROM OLD.party_snapshot_frozen_at OR
     NEW.customer_client_id IS DISTINCT FROM OLD.customer_client_id OR
     NEW.contract_version IS DISTINCT FROM OLD.contract_version OR
     NEW.revises_document_id IS DISTINCT FROM OLD.revises_document_id OR
     NEW.basis_contract_document_id IS DISTINCT FROM OLD.basis_contract_document_id OR
     NEW.company_id IS DISTINCT FROM OLD.company_id OR
     NEW.project_id IS DISTINCT FROM OLD.project_id OR
     NEW.side IS DISTINCT FROM OLD.side OR
     NEW.doc_type IS DISTINCT FROM OLD.doc_type OR
     NEW.number IS DISTINCT FROM OLD.number OR
     NEW.doc_date IS DISTINCT FROM OLD.doc_date OR
     NEW.counterparty IS DISTINCT FROM OLD.counterparty OR
     NEW.amount IS DISTINCT FROM OLD.amount OR
     NEW.sign_status IS DISTINCT FROM OLD.sign_status OR
     NEW.scan_url IS DISTINCT FROM OLD.scan_url
  ) THEN
    RAISE EXCEPTION 'Customer document party snapshot is immutable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END;
$$"""


OLD_GUARD_SQL = GUARD_SQL.replace(
    "     NEW.basis_contract_document_id IS DISTINCT FROM OLD.basis_contract_document_id OR\n",
    "",
).replace("Customer document party snapshot", "Customer contract party snapshot")


def upgrade():
    op.execute("""
        ALTER TABLE project_documents
            ADD COLUMN IF NOT EXISTS basis_contract_document_id INTEGER;
        ALTER TABLE project_documents
            ADD CONSTRAINT project_documents_id_company_project_unique
            UNIQUE(id,company_id,project_id);
        ALTER TABLE project_documents
            ADD CONSTRAINT project_documents_basis_contract_company_fk
            FOREIGN KEY (basis_contract_document_id,company_id,project_id)
            REFERENCES project_documents(id,company_id,project_id);
        ALTER TABLE project_documents
            ADD CONSTRAINT project_documents_basis_contract_not_self
            CHECK (basis_contract_document_id IS NULL OR basis_contract_document_id<>id);
        CREATE INDEX project_documents_basis_contract_idx
            ON project_documents(company_id,project_id,basis_contract_document_id)
            WHERE basis_contract_document_id IS NOT NULL;
    """)
    op.execute(GUARD_SQL)


def downgrade():
    op.execute("LOCK TABLE project_documents IN ACCESS EXCLUSIVE MODE")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM project_documents WHERE basis_contract_document_id IS NOT NULL) THEN
          RAISE EXCEPTION 'Cannot discard signed customer act contract links';
        END IF;
        END $$""")
    op.execute(OLD_GUARD_SQL)
    op.execute("DROP INDEX IF EXISTS project_documents_basis_contract_idx")
    op.execute("ALTER TABLE project_documents DROP CONSTRAINT project_documents_basis_contract_not_self")
    op.execute("ALTER TABLE project_documents DROP CONSTRAINT project_documents_basis_contract_company_fk")
    op.execute("ALTER TABLE project_documents DROP CONSTRAINT project_documents_id_company_project_unique")
    op.execute("ALTER TABLE project_documents DROP COLUMN basis_contract_document_id")
