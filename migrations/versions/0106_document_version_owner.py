"""Freeze the owner of new document snapshots; legacy snapshots remain unassigned."""
from alembic import op
revision = '0106_document_version_owner'
down_revision = '0105_settlement_cash_guard'
branch_labels = None
depends_on = None

def upgrade():
    op.execute('ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS company_id INTEGER')
    op.execute('ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS project_id INTEGER')
    op.execute('ALTER TABLE document_versions ADD CONSTRAINT document_versions_owner_fk FOREIGN KEY(project_id,company_id) REFERENCES projects(id,company_id)')
    op.execute('ALTER TABLE document_versions ADD CONSTRAINT document_versions_owner_pair CHECK ((project_id IS NULL)=(company_id IS NULL))')
    op.execute('CREATE INDEX document_versions_exact_owner ON document_versions(company_id,project_id,document_type,document_id)')

def downgrade():
    raise RuntimeError('Snapshot ownership must be retained')
