"""Make project-launch and supplier-document ownership explicit."""

from alembic import op


revision = "0086_counterparty_doc_owners"
down_revision = "0085_supplier_contract_indexes"
branch_labels = None
depends_on = None


PROJECT_TABLES = ("counterparties", "project_contract_terms", "project_launch_drafts")


def upgrade():
    for table in PROJECT_TABLES:
        op.execute(f"ALTER TABLE public.{table} ALTER COLUMN company_id DROP DEFAULT")
        op.execute(f"ALTER TABLE public.{table} ALTER COLUMN company_id SET NOT NULL")
        op.execute(f"""DO $owner_fk$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint
                WHERE conname='fk_{table}_company'
                  AND conrelid='public.{table}'::regclass) THEN
                ALTER TABLE public.{table} ADD CONSTRAINT fk_{table}_company
                FOREIGN KEY (company_id) REFERENCES public.companies(id);
            END IF;
        END $owner_fk$""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_project_contract_terms_company ON public.project_contract_terms(company_id,project_id,id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_project_launch_drafts_company ON public.project_launch_drafts(company_id,project_id,id)")

    op.execute("ALTER TABLE public.supplier_documents ADD COLUMN IF NOT EXISTS owner_scope VARCHAR(20)")
    op.execute("""UPDATE public.supplier_documents
        SET owner_scope=CASE WHEN company_id IS NOT NULL THEN 'company' ELSE 'supplier' END
        WHERE owner_scope IS NULL AND supplier_id IS NOT NULL""")
    op.execute("ALTER TABLE public.supplier_documents ALTER COLUMN owner_scope SET NOT NULL")
    op.execute("""DO $owner_check$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint
            WHERE conname='ck_supplier_documents_owner'
              AND conrelid='public.supplier_documents'::regclass) THEN
            ALTER TABLE public.supplier_documents
            ADD CONSTRAINT ck_supplier_documents_owner CHECK (
                (owner_scope='company' AND company_id IS NOT NULL AND supplier_id IS NOT NULL)
                OR (owner_scope='supplier' AND company_id IS NULL AND supplier_id IS NOT NULL)
            );
        END IF;
    END $owner_check$""")
    op.execute("""DO $supplier_fk$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint
            WHERE conname='fk_supplier_documents_supplier'
              AND conrelid='public.supplier_documents'::regclass) THEN
            ALTER TABLE public.supplier_documents
            ADD CONSTRAINT fk_supplier_documents_supplier
            FOREIGN KEY (supplier_id) REFERENCES public.suppliers(id);
        END IF;
    END $supplier_fk$""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_supplier_documents_supplier_active ON public.supplier_documents(supplier_id,created_at DESC) WHERE owner_scope='supplier' AND archived_at IS NULL")


def downgrade():
    op.execute("DROP INDEX public.idx_supplier_documents_supplier_active")
    op.execute("ALTER TABLE public.supplier_documents DROP CONSTRAINT fk_supplier_documents_supplier")
    op.execute("ALTER TABLE public.supplier_documents DROP CONSTRAINT ck_supplier_documents_owner")
    op.execute("ALTER TABLE public.supplier_documents DROP COLUMN owner_scope")
    op.execute("DROP INDEX public.idx_project_launch_drafts_company")
    op.execute("DROP INDEX public.idx_project_contract_terms_company")
    for table in reversed(PROJECT_TABLES):
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT fk_{table}_company")
        op.execute(f"ALTER TABLE public.{table} ALTER COLUMN company_id DROP NOT NULL")
        op.execute(f"ALTER TABLE public.{table} ALTER COLUMN company_id SET DEFAULT 1")
