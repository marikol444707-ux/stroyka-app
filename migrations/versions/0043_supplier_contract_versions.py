"""Reviewed contract snapshots and retention of their source files."""
from alembic import op

revision = '0043_supplier_contract_versions'
down_revision = '0042_supplier_deal_parties'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE public.file_ownership ADD COLUMN IF NOT EXISTS retained_at TIMESTAMPTZ')
    op.execute('''CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_parties_contract_identity
                  ON public.supplier_deal_parties (offer_id, version, company_id)''')
    op.execute('''CREATE UNIQUE INDEX IF NOT EXISTS uq_file_ownership_contract_identity
                  ON public.file_ownership (id, company_id)''')
    op.execute('''CREATE TABLE public.supplier_contract_versions (
        id BIGSERIAL PRIMARY KEY,
        offer_id INTEGER NOT NULL,
        company_id INTEGER NOT NULL,
        party_version INTEGER NOT NULL,
        version INTEGER NOT NULL CHECK (version > 0),
        source_file_id INTEGER NOT NULL,
        snapshot_json JSONB NOT NULL CHECK (jsonb_typeof(snapshot_json) = 'object'),
        snapshot_hash VARCHAR(64) NOT NULL CHECK (snapshot_hash ~ '^[0-9a-f]{64}$'),
        reason TEXT NOT NULL CHECK (length(trim(reason)) BETWEEN 1 AND 1000),
        reviewed_by_id INTEGER NOT NULL,
        reviewed_by TEXT NOT NULL,
        reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (offer_id, version),
        FOREIGN KEY (offer_id, party_version, company_id)
            REFERENCES public.supplier_deal_parties (offer_id, version, company_id),
        FOREIGN KEY (source_file_id, company_id)
            REFERENCES public.file_ownership (id, company_id)
    )''')


def downgrade():
    op.execute('''DO $contract_history_guard$ BEGIN
        IF EXISTS (SELECT 1 FROM public.supplier_contract_versions LIMIT 1)
           OR EXISTS (SELECT 1 FROM public.file_ownership WHERE retained_at IS NOT NULL LIMIT 1) THEN
            RAISE EXCEPTION 'Cannot remove contract history or retained files';
        END IF;
    END $contract_history_guard$''')
    op.execute('DROP TABLE public.supplier_contract_versions')
    op.execute('DROP INDEX public.uq_supplier_parties_contract_identity')
    op.execute('DROP INDEX public.uq_file_ownership_contract_identity')
    op.execute('ALTER TABLE public.file_ownership DROP COLUMN retained_at')
