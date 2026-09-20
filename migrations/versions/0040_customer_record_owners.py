"""Exact ownership for customer-facing project records; no inferred backfill."""
from alembic import op

revision = '0040_customer_record_owners'
down_revision = '0039_supplier_email_history'
branch_labels = None
depends_on = None

TABLES = ('project_documents', 'project_letters', 'prescriptions', 'warranty_defects')
SCHEMA_SQL = '\n'.join(f'''
ALTER TABLE {table}
    ADD COLUMN company_id INTEGER,
    ADD COLUMN project_id INTEGER,
    ADD COLUMN created_by_user_id INTEGER REFERENCES users(id),
    ADD CONSTRAINT {table}_owner_pair CHECK (
        (company_id IS NULL AND project_id IS NULL) OR
        (company_id IS NOT NULL AND project_id IS NOT NULL)
    ),
    ADD CONSTRAINT {table}_project_owner_fk
        FOREIGN KEY(project_id,company_id) REFERENCES projects(id,company_id);
CREATE INDEX {table}_owner_idx ON {table}(company_id,project_id,id);
''' for table in TABLES) + '''
ALTER TABLE prescriptions ADD COLUMN IF NOT EXISTS fix_photo_url TEXT;
ALTER TABLE prescriptions ADD COLUMN IF NOT EXISTS fix_notes TEXT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS floors INTEGER DEFAULT 1;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS liters TEXT DEFAULT '';
'''


def upgrade():
    op.execute(SCHEMA_SQL)


def downgrade():
    raise RuntimeError('Verified record ownership must not be discarded')
