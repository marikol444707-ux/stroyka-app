"""Isolate OCR templates; legacy owners cannot be inferred from supplier names."""
from alembic import op

revision = '0117_invoice_template_owners'
down_revision = '0116_tool_deductions'
branch_labels = None
depends_on = None

SCHEMA_SQL = '''
ALTER TABLE supplier_invoice_templates ADD COLUMN company_id INTEGER REFERENCES companies(id);
-- Existing NULL owners are quarantined; new/updated rows must have an owner.
ALTER TABLE supplier_invoice_templates ADD CONSTRAINT invoice_template_owner_required
 CHECK(company_id IS NOT NULL) NOT VALID;
ALTER TABLE supplier_invoice_templates ADD CONSTRAINT invoice_template_supplier_owner
 FOREIGN KEY(company_id,supplier_id) REFERENCES company_supplier_links(company_id,supplier_id) NOT VALID;
CREATE UNIQUE INDEX invoice_template_company_key
 ON supplier_invoice_templates(company_id,supplier_key,COALESCE(document_type,'')) WHERE active=TRUE;
'''

def upgrade():
    op.execute(SCHEMA_SQL)

def downgrade():
    raise RuntimeError('Removing OCR ownership would expose company documents; use a reviewed forward fix')
