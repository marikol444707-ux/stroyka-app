"""Explicit supplier publication of immutable contract versions; no backfill."""
from alembic import op
revision='0066_contract_publications'
down_revision='0065_contract_archive'
branch_labels=None
depends_on=None

def upgrade():
    op.execute('''CREATE TABLE public.supplier_contract_publications (
        contract_version_id BIGINT PRIMARY KEY,
        company_id INTEGER NOT NULL,
        snapshot_hash TEXT NOT NULL,
        published_by_id INTEGER NOT NULL,
        published_by TEXT NOT NULL,
        published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        FOREIGN KEY (contract_version_id,company_id) REFERENCES public.supplier_contract_versions(id,company_id)
    )''')

def downgrade():
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM public.supplier_contract_publications) THEN RAISE EXCEPTION 'Cannot remove contract publication history'; END IF; END $$")
    op.execute('DROP TABLE public.supplier_contract_publications')
