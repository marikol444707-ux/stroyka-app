"""Allow checked supplier originals before an offer exists."""
from alembic import op
revision='0067_supplier_contract_originals'
down_revision='0066_contract_publications'
branch_labels=None
depends_on=None

def upgrade():
    op.execute('ALTER TABLE public.supplier_contract_versions ALTER COLUMN offer_id DROP NOT NULL')
    op.execute('ALTER TABLE public.supplier_contract_versions ALTER COLUMN party_version DROP NOT NULL')
    op.execute('ALTER TABLE public.supplier_contract_versions ADD CONSTRAINT contract_offer_pair CHECK ((offer_id IS NULL) = (party_version IS NULL))')
    op.execute('ALTER TABLE public.supplier_contract_versions ADD COLUMN request_id UUID')
    op.execute('CREATE UNIQUE INDEX supplier_contract_request ON public.supplier_contract_versions(company_id,request_id) WHERE request_id IS NOT NULL')

def downgrade():
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM public.supplier_contract_versions WHERE offer_id IS NULL OR request_id IS NOT NULL) THEN RAISE EXCEPTION 'Preserve supplier originals'; END IF; END $$")
    op.execute('DROP INDEX public.supplier_contract_request')
    op.execute('ALTER TABLE public.supplier_contract_versions DROP COLUMN request_id')
    op.execute('ALTER TABLE public.supplier_contract_versions DROP CONSTRAINT contract_offer_pair')
    op.execute('ALTER TABLE public.supplier_contract_versions ALTER COLUMN offer_id SET NOT NULL')
    op.execute('ALTER TABLE public.supplier_contract_versions ALTER COLUMN party_version SET NOT NULL')
