"""Durable retry identities for append-only supplier shipment batches."""
from alembic import op
revision = '0037_supplier_shipment_batches'
down_revision = '0036_supplier_invite_company'
branch_labels = None
depends_on = None
SCHEMA_SQL = '''
CREATE TABLE supplier_shipment_batches (
    id BIGSERIAL PRIMARY KEY,
    offer_id INTEGER NOT NULL REFERENCES supplier_offers(id),
    company_id INTEGER NOT NULL REFERENCES companies(id),
    request_key VARCHAR(80) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    delivery_ids INTEGER[] NOT NULL,
    created_by_user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (offer_id, request_key),
    CHECK (cardinality(delivery_ids) > 0)
);
'''

def upgrade():
    op.execute(SCHEMA_SQL)

def downgrade():
    op.execute('LOCK TABLE supplier_shipment_batches IN ACCESS EXCLUSIVE MODE')
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM supplier_shipment_batches) THEN RAISE EXCEPTION 'Cannot discard shipment retry identities'; END IF; END $$")
    op.execute('DROP TABLE supplier_shipment_batches')
