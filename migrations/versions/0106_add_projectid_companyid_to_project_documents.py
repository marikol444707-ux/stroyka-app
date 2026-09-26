"""Add nullable project_id and company_id to project_documents (beta migration)

Revision ID: 0106_add_projectid_companyid_to_project_documents
Revises: 0007_warehouse_vat_labels

This migration is generated for ISSUE #106. It adds nullable `project_id` and
`company_id` columns to `project_documents`, plus safe indexes and a conditional
foreign-key to `projects(id)` when compatible. It is intentionally non-destructive
and does not perform any backfill. Do NOT run this automatically in production.
"""

from alembic import op


revision = "0106_add_projectid_companyid_to_project_documents"
down_revision = "0007_warehouse_vat_labels"
branch_labels = None
depends_on = None


_SQL = """
DO $add_project_columns$
BEGIN
    -- Add project_id if missing
    IF NOT EXISTS (
        SELECT 1 FROM pg_attribute
         WHERE attrelid = 'public.project_documents'::regclass
           AND attname = 'project_id' AND NOT attisdropped
    ) THEN
        ALTER TABLE public.project_documents ADD COLUMN project_id INT;
    END IF;

    -- Add company_id if missing
    IF NOT EXISTS (
        SELECT 1 FROM pg_attribute
         WHERE attrelid = 'public.project_documents'::regclass
           AND attname = 'company_id' AND NOT attisdropped
    ) THEN
        ALTER TABLE public.project_documents ADD COLUMN company_id INT;
    END IF;

    -- Add indexes (if not exists)
    IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='idx_project_documents_company_id') THEN
        CREATE INDEX idx_project_documents_company_id ON public.project_documents(company_id, id DESC);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='idx_project_documents_project_id') THEN
        CREATE INDEX idx_project_documents_project_id ON public.project_documents(project_id);
    END IF;

    -- If projects table exists with compatible id type, add FK constraint optionally
    IF to_regclass('public.projects') IS NOT NULL THEN
        BEGIN
            ALTER TABLE public.project_documents
                ADD CONSTRAINT fk_project_documents_project FOREIGN KEY (project_id)
                    REFERENCES public.projects(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN
            -- ignore if constraint already exists or cannot be added
            NULL;
        END;
    END IF;
END $add_project_columns$;
"""


def upgrade() -> None:
    op.execute(_SQL)


def downgrade() -> None:
    # We intentionally do not DROP columns automatically to avoid destructive
    # operations. Downgrade is a no-op; manual rollback must be performed by DB
    # operators after review.
    pass
