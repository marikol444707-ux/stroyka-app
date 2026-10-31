"""Explicit owner for room-work rows, including work recorded without a room ID."""
from alembic import op
revision = '0107_room_work_owner'
down_revision = '0106_document_version_owner'
branch_labels = None
depends_on = None

def upgrade():
    op.execute('ALTER TABLE room_works ADD COLUMN IF NOT EXISTS company_id INTEGER')
    op.execute('ALTER TABLE room_works ADD COLUMN IF NOT EXISTS project_id INTEGER')
    op.execute('ALTER TABLE room_works ADD CONSTRAINT room_works_owner_fk FOREIGN KEY(project_id,company_id) REFERENCES projects(id,company_id)')
    op.execute('ALTER TABLE room_works ADD CONSTRAINT room_works_owner_pair CHECK ((project_id IS NULL)=(company_id IS NULL))')
    op.execute('CREATE INDEX room_works_exact_owner ON room_works(company_id,project_id,id)')

def downgrade():
    raise RuntimeError('Room-work ownership must be retained')
