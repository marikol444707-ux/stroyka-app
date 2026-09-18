"""Isolate customer supplier archives without guessing legacy ownership."""
from alembic import op

revision = '0008_supplier_doc_ownership'
down_revision = '0007_warehouse_vat_labels'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE public.supplier_documents ADD COLUMN IF NOT EXISTS company_id INTEGER')
    op.execute('ALTER TABLE public.supplier_documents ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP')
    op.execute('''DO $supplier_document_owner$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint
            WHERE conname='fk_supplier_documents_company'
              AND conrelid='public.supplier_documents'::regclass) THEN
            ALTER TABLE public.supplier_documents
            ADD CONSTRAINT fk_supplier_documents_company
            FOREIGN KEY (company_id) REFERENCES public.companies(id);
        END IF;
    END $supplier_document_owner$''')
    op.execute('''CREATE INDEX IF NOT EXISTS idx_supplier_documents_company_active
                  ON public.supplier_documents (company_id, supplier_id, created_at DESC)
                  WHERE archived_at IS NULL''')


def downgrade():
    op.execute('''DO $supplier_document_owner_guard$ BEGIN
        IF EXISTS (SELECT 1 FROM public.supplier_documents
                   WHERE company_id IS NOT NULL OR archived_at IS NOT NULL) THEN
            RAISE EXCEPTION 'Supplier document ownership/archive data must be preserved';
        END IF;
    END $supplier_document_owner_guard$''')
    op.execute('DROP INDEX IF EXISTS public.idx_supplier_documents_company_active')
    op.execute('ALTER TABLE public.supplier_documents DROP CONSTRAINT IF EXISTS fk_supplier_documents_company')
    op.execute('ALTER TABLE public.supplier_documents DROP COLUMN IF EXISTS archived_at')
    op.execute('ALTER TABLE public.supplier_documents DROP COLUMN IF EXISTS company_id')
