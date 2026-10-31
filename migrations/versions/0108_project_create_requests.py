"""Persist project creation command identities in the same transaction as projects."""
from alembic import op
revision = '0108_project_create_requests'
down_revision = '0107_room_work_owner'
branch_labels = None
depends_on = None

def upgrade():
    op.execute('''CREATE TABLE project_create_requests (
        company_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        request_key UUID NOT NULL, request_hash TEXT NOT NULL, project_id INTEGER NOT NULL,
        PRIMARY KEY(company_id,user_id,request_key),
        FOREIGN KEY(project_id,company_id) REFERENCES projects(id,company_id)
    )''')

def downgrade():
    raise RuntimeError('Creation command identities must be retained')
