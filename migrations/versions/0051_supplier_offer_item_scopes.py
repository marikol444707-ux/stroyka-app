"""Addressed RFQ lines and immutable awarded order lines."""
from alembic import op

revision = '0051_supplier_offer_item_scopes'
down_revision = '0050_supplier_invoice_line_specs'
branch_labels = None
depends_on = None

SCHEMA_SQL = '''
ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS requested_items_json TEXT;
ALTER TABLE supplier_offers ADD COLUMN IF NOT EXISTS awarded_items_json TEXT;
'''

def upgrade():
    op.execute(SCHEMA_SQL)

def downgrade():
    op.execute('''DO $$ BEGIN IF EXISTS(SELECT 1 FROM supplier_offers
        WHERE requested_items_json IS NOT NULL OR awarded_items_json IS NOT NULL) THEN
        RAISE EXCEPTION 'Cannot discard recorded RFQ line assignments'; END IF; END $$''')
    op.execute('ALTER TABLE supplier_offers DROP COLUMN awarded_items_json, DROP COLUMN requested_items_json')
