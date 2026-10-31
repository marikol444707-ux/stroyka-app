"""Explicit ownership for legacy project records; no name-based backfill."""
from alembic import op
revision = '0104_legacy_project_owners'
down_revision = '0103_room_owner_identity'
branch_labels = None
depends_on = None
TABLES = ('inspection_orders', 'supervisor_acts', 'contracts', 'project_chat', 'tb_journal', 'interim_acts')

def upgrade():
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS company_id INTEGER')
        op.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS project_id INTEGER')
        op.execute(f'CREATE INDEX IF NOT EXISTS {table}_exact_owner ON {table}(company_id,project_id,id)')
        op.execute(f'ALTER TABLE {table} ADD CONSTRAINT {table}_owner_fk FOREIGN KEY(project_id,company_id) REFERENCES projects(id,company_id)')
        op.execute(f'ALTER TABLE {table} ADD CONSTRAINT {table}_owner_pair CHECK (project_id IS NULL OR company_id IS NOT NULL)')

def downgrade():
    raise RuntimeError('Owner identities must not be removed automatically')
