"""Reversible contract availability with an append-only decision history."""
from alembic import op
revision = '0065_contract_archive'
down_revision = '0064_supplier_contract_registry'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("ALTER TABLE public.supplier_contract_registry ADD COLUMN archived BOOLEAN NOT NULL DEFAULT FALSE, ADD COLUMN state_version INTEGER NOT NULL DEFAULT 0 CHECK (state_version >= 0)")
    op.execute('''CREATE TABLE public.supplier_contract_registry_events (
        registry_id BIGINT NOT NULL, company_id INTEGER NOT NULL,
        version INTEGER NOT NULL CHECK (version > 0), archived BOOLEAN NOT NULL,
        actor_id INTEGER NOT NULL, actor_name TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (registry_id,version),
        FOREIGN KEY (registry_id,company_id) REFERENCES public.supplier_contract_registry(id,company_id)
    )''')

def downgrade():
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM public.supplier_contract_registry_events) THEN RAISE EXCEPTION 'Cannot remove contract archival history'; END IF; END $$")
    op.execute('DROP TABLE public.supplier_contract_registry_events')
    op.execute('ALTER TABLE public.supplier_contract_registry DROP COLUMN archived, DROP COLUMN state_version')
