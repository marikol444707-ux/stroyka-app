"""Company-private supplier profile; no copy from legacy global commercial fields."""
from alembic import op

revision = '0022_supplier_company_catalog'
down_revision = '0008_supplier_doc_ownership'
branch_labels = ('supplier_catalog',)
depends_on = None


def upgrade():
    # This branch deliberately has no payment-chain dependency. Legacy tables
    # are bootstrap-owned; an Alembic stamp alone does not prove readiness.
    op.execute('''DO $$ DECLARE missing text; BEGIN
        SELECT string_agg(required.table_name || '.' || required.column_name, ', ')
          INTO missing FROM (VALUES
            ('companies','id'),('companies','platform_account_id'),('suppliers','id'),
            ('company_supplier_links','id'),('company_supplier_links','company_id'),
            ('company_supplier_links','supplier_id'),('company_supplier_links','platform_account_id'),
            ('company_supplier_links','local_category'),('company_supplier_links','source_type'),
            ('company_supplier_links','source_detail'),('company_supplier_links','contract_url'),
            ('company_supplier_links','contract_number'),('company_supplier_links','contract_date'),
            ('company_supplier_links','rating'),('company_supplier_links','status')
          ) required(table_name,column_name)
          WHERE NOT EXISTS(SELECT 1 FROM information_schema.columns c
            WHERE c.table_schema='public' AND c.table_name=required.table_name
              AND c.column_name=required.column_name);
        IF missing IS NOT NULL THEN
            RAISE EXCEPTION 'Supplier catalog requires existing application bootstrap: %', missing;
        END IF;
    END $$''')
    # Ownership comes from the link's existing company, never from supplier name,
    # email, invoice history or a guessed default tenant. Stop on ambiguity.
    op.execute('''DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM public.company_supplier_links l
                  LEFT JOIN public.companies c ON c.id=l.company_id
                  LEFT JOIN public.suppliers s ON s.id=l.supplier_id
                  WHERE c.platform_account_id IS NULL OR s.id IS NULL
                     OR (l.platform_account_id IS NOT NULL AND l.platform_account_id<>c.platform_account_id)) THEN
            RAISE EXCEPTION 'Supplier relationship ownership requires reconciliation before catalog migration';
        END IF;
    END $$''')
    op.execute('''UPDATE public.company_supplier_links l SET platform_account_id=c.platform_account_id
                  FROM public.companies c WHERE c.id=l.company_id AND l.platform_account_id IS NULL''')
    op.execute('ALTER TABLE public.company_supplier_links ALTER COLUMN platform_account_id SET NOT NULL')
    op.execute('ALTER TABLE public.companies ADD CONSTRAINT supplier_catalog_company_account_key UNIQUE(id,platform_account_id)')
    op.execute('''ALTER TABLE public.company_supplier_links
                  ADD CONSTRAINT supplier_catalog_company_account_fk FOREIGN KEY(company_id,platform_account_id)
                    REFERENCES public.companies(id,platform_account_id),
                  ADD CONSTRAINT supplier_catalog_supplier_fk FOREIGN KEY(supplier_id) REFERENCES public.suppliers(id)''')
    op.execute("ALTER TABLE public.company_supplier_links ADD COLUMN profile JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute('ALTER TABLE public.company_supplier_links ADD COLUMN version INTEGER NOT NULL DEFAULT 1 CHECK(version>0)')
    op.execute("ALTER TABLE public.company_supplier_links ADD CONSTRAINT supplier_link_profile_object CHECK(jsonb_typeof(profile)='object')")


def downgrade():
    op.execute('ALTER TABLE public.company_supplier_links DROP CONSTRAINT supplier_link_profile_object')
    op.execute('ALTER TABLE public.company_supplier_links DROP COLUMN version, DROP COLUMN profile')
    op.execute('ALTER TABLE public.company_supplier_links DROP CONSTRAINT supplier_catalog_company_account_fk, DROP CONSTRAINT supplier_catalog_supplier_fk')
    op.execute('ALTER TABLE public.companies DROP CONSTRAINT supplier_catalog_company_account_key')
    op.execute('ALTER TABLE public.company_supplier_links ALTER COLUMN platform_account_id DROP NOT NULL')
