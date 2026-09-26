"""Versioned party proposals anchored to an exact supplier offer."""
from alembic import op

revision = '0042_supplier_deal_parties'
down_revision = '0041_platform_payment_commands'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_offers_deal_identity
                  ON public.supplier_offers (id, company_id, request_id, supplier_id)''')
    op.execute('''CREATE TABLE IF NOT EXISTS public.supplier_deal_parties (
        id BIGSERIAL PRIMARY KEY,
        offer_id INTEGER NOT NULL,
        company_id INTEGER NOT NULL REFERENCES public.companies(id),
        request_id INTEGER NOT NULL,
        supplier_id INTEGER NOT NULL,
        buyer_company_id INTEGER NOT NULL REFERENCES public.companies(id),
        payer_company_id INTEGER NOT NULL REFERENCES public.companies(id),
        version INTEGER NOT NULL CHECK (version > 0),
        reason TEXT NOT NULL CHECK (length(trim(reason)) BETWEEN 1 AND 1000),
        created_by_id INTEGER NOT NULL,
        created_by TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_supplier_deal_parties_version UNIQUE (offer_id, version),
        CONSTRAINT fk_supplier_deal_parties_offer
            FOREIGN KEY (offer_id, company_id, request_id, supplier_id)
            REFERENCES public.supplier_offers (id, company_id, request_id, supplier_id)
    )''')
    op.execute('''CREATE INDEX IF NOT EXISTS idx_supplier_deal_parties_owner
                  ON public.supplier_deal_parties (company_id, supplier_id, offer_id)''')


def downgrade():
    op.execute('''DO $supplier_deal_parties_guard$ BEGIN
        IF EXISTS (SELECT 1 FROM public.supplier_deal_parties LIMIT 1) THEN
            RAISE EXCEPTION 'Cannot remove supplier deal party history';
        END IF;
    END $supplier_deal_parties_guard$''')
    op.execute('DROP TABLE IF EXISTS public.supplier_deal_parties')
    op.execute('DROP INDEX IF EXISTS public.uq_supplier_offers_deal_identity')
