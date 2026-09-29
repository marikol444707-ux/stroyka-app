"""Durable RFQ email attempts, scoped to the original recipient and company."""
from alembic import op
revision='0039_supplier_email_history'
down_revision='0038_supplier_customer_team'
branch_labels=None
depends_on=None
SCHEMA_SQL='''
CREATE TABLE supplier_email_attempts (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL,
    outcome TEXT NOT NULL DEFAULT 'unconfirmed' CHECK(outcome IN ('unconfirmed','accepted','rejected')),
    code TEXT NOT NULL DEFAULT 'acknowledgement_unknown',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);
CREATE INDEX supplier_email_attempts_recipient_idx
    ON supplier_email_attempts(company_id,request_id,recipient_id,id DESC);
'''
def upgrade():
    op.execute(SCHEMA_SQL)
def downgrade():
    raise RuntimeError('Notification attempt evidence must not be dropped')
