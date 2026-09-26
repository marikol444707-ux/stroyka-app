"""Permanent cancelled attempt UUIDs; no financial rows or customer backfill."""
from alembic import op

revision = '0048_supplier_pay_cancellations'
down_revision = '0047_supplier_payment_packages'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE public.supplier_payment_request_cancellations (
        id BIGSERIAL PRIMARY KEY,
        company_id INTEGER NOT NULL REFERENCES public.companies(id),
        request_id UUID NOT NULL,
        fingerprint TEXT NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
        actor_id INTEGER NOT NULL REFERENCES public.users(id),
        document_kind TEXT NOT NULL CHECK (document_kind IN ('invoice','warehouse')),
        document_id INTEGER NOT NULL CHECK (document_id>0),
        cancelled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(company_id,request_id)
    )''')
    op.execute('''CREATE TRIGGER supplier_payment_cancellation_immutable
        BEFORE UPDATE OR DELETE ON public.supplier_payment_request_cancellations
        FOR EACH ROW EXECUTE FUNCTION public.supplier_payment_immutable()''')
    op.execute('''CREATE TRIGGER supplier_payment_cancellation_no_truncate
        BEFORE TRUNCATE ON public.supplier_payment_request_cancellations
        FOR EACH STATEMENT EXECUTE FUNCTION public.supplier_payment_immutable()''')


def downgrade():
    op.execute('LOCK TABLE public.supplier_payment_request_cancellations IN ACCESS EXCLUSIVE MODE')
    op.execute('''DO $$ BEGIN
        IF current_setting('transaction_isolation') <> 'read committed' THEN
            RAISE EXCEPTION 'Cancellation downgrade requires READ COMMITTED';
        END IF;
        IF EXISTS(SELECT 1 FROM public.supplier_payment_request_cancellations) THEN
            RAISE EXCEPTION 'Cannot remove permanent cancelled request evidence';
        END IF;
    END $$''')
    op.execute('DROP TABLE public.supplier_payment_request_cancellations')
