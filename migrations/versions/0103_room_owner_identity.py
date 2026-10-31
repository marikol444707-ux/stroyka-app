"""Store exact room ownership; do not infer owners of legacy measurements from names."""
from alembic import op

revision = '0103_room_owner_identity'
# Integration continuation for the deployed server lineage, not the older
# published audit-only lineage. Do not apply this tree to an audit-migrated DB.
down_revision = '0104_jev_search_run_history'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE rooms ADD COLUMN IF NOT EXISTS company_id INTEGER')
    op.execute('ALTER TABLE rooms ADD COLUMN IF NOT EXISTS project_id INTEGER')
    op.execute('CREATE INDEX IF NOT EXISTS ix_rooms_owner ON rooms(company_id,project_id,id)')
    op.execute('ALTER TABLE rooms ADD CONSTRAINT rooms_exact_project_owner '
               'FOREIGN KEY (project_id,company_id) REFERENCES projects(id,company_id)')
    op.execute('ALTER TABLE rooms ADD CONSTRAINT rooms_owner_pair '
               'CHECK ((project_id IS NULL) = (company_id IS NULL))')


def downgrade():
    # Retain ownership data even when rolling back the application release.
    op.execute('ALTER TABLE rooms DROP CONSTRAINT IF EXISTS rooms_owner_pair')
    op.execute('ALTER TABLE rooms DROP CONSTRAINT IF EXISTS rooms_exact_project_owner')
    op.execute('DROP INDEX IF EXISTS ix_rooms_owner')
