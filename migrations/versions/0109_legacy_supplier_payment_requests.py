"""Durable command results for atomic legacy invoice accounting. No balance backfill."""
from alembic import op
revision = '0109_legacy_payment_requests'
down_revision = '0108_project_create_requests'
branch_labels = None
depends_on = None


def upgrade():
    # IDs are immutable audit snapshots: existing document/expense deletion must not
    # erase command identities or become silently forbidden by new foreign keys.
    op.execute('''CREATE TABLE legacy_supplier_payment_requests (
        company_id INTEGER NOT NULL CHECK(company_id>0),
        request_id UUID NOT NULL,
        invoice_id INTEGER NOT NULL CHECK(invoice_id>0),
        actor_id INTEGER NOT NULL CHECK(actor_id>0),
        fingerprint TEXT NOT NULL CHECK(length(fingerprint)=64),
        project_payment_id INTEGER NOT NULL CHECK(project_payment_id>0),
        result JSONB NOT NULL CHECK(jsonb_typeof(result)='object'),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY(company_id,request_id)
    )''')
    op.execute('''CREATE FUNCTION legacy_supplier_payment_request_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Payment command identities must be retained'; END $$''')
    op.execute('''CREATE TRIGGER legacy_supplier_payment_request_immutable
        BEFORE UPDATE OR DELETE OR TRUNCATE ON legacy_supplier_payment_requests
        FOR EACH STATEMENT EXECUTE FUNCTION legacy_supplier_payment_request_immutable()''')


def downgrade():
    raise RuntimeError('Payment command identities must be retained')
