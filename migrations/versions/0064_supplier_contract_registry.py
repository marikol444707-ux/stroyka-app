"""Explicit contract identity across reviewed offer versions; no inferred backfill."""
from alembic import op

revision = '0064_supplier_contract_registry'
down_revision = '0063_supplier_legacy_lines'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE UNIQUE INDEX IF NOT EXISTS uq_contract_registry_version_owner
                  ON public.supplier_contract_versions (id,company_id)''')
    op.execute('''CREATE TABLE public.supplier_contract_registry (
        id BIGSERIAL PRIMARY KEY,
        company_id INTEGER NOT NULL REFERENCES public.companies(id),
        supplier_id INTEGER NOT NULL REFERENCES public.suppliers(id),
        buyer_company_id INTEGER NOT NULL REFERENCES public.companies(id),
        payer_company_id INTEGER NOT NULL REFERENCES public.companies(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (id,company_id)
    )''')
    op.execute('''CREATE TABLE public.supplier_contract_registry_versions (
        contract_version_id BIGINT PRIMARY KEY,
        registry_id BIGINT NOT NULL,
        company_id INTEGER NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        FOREIGN KEY (contract_version_id,company_id)
            REFERENCES public.supplier_contract_versions(id,company_id),
        FOREIGN KEY (registry_id,company_id)
            REFERENCES public.supplier_contract_registry(id,company_id)
    )''')
    op.execute('''CREATE INDEX ix_contract_registry_members
                  ON public.supplier_contract_registry_versions(registry_id,company_id,contract_version_id)''')


def downgrade():
    op.execute('''DO $registry_guard$ BEGIN
        IF EXISTS (SELECT 1 FROM public.supplier_contract_registry LIMIT 1) THEN
            RAISE EXCEPTION 'Cannot remove recorded contract registry';
        END IF;
    END $registry_guard$''')
    op.execute('DROP TABLE public.supplier_contract_registry_versions')
    op.execute('DROP TABLE public.supplier_contract_registry')
    op.execute('DROP INDEX public.uq_contract_registry_version_owner')
