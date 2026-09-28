"""
0008_project_documents_ownership

Add nullable company_id and project_id to project_documents, with safe
indexes and a FK to projects.id if present.

NOTE: This migration file is prepared but must NOT be executed by this
agent. It is intended to be reviewed and applied by DB migration tooling
in a controlled environment.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0008_project_documents_ownership'
down_revision = '0007_warehouse_invoice_vat_labels'
branch_labels = None
depends_on = None


def upgrade():
    # Add nullable company_id and project_id so we can backfill without
    # blocking runtime. Keep nullable to allow staged backfill.
    op.add_column('project_documents', sa.Column('company_id', sa.BigInteger(), nullable=True))
    op.add_column('project_documents', sa.Column('project_id', sa.BigInteger(), nullable=True))

    # Add indexes to support queries by company and (company,project)
    op.create_index('idx_project_documents_company_id', 'project_documents', ['company_id', 'id'], unique=False)
    op.create_index('idx_project_documents_company_project', 'project_documents', ['company_id', 'project_id'], unique=False)

    # Add FK to projects.id if that table exists and is compatible.
    # This is guarded and will not error if projects table has different type.
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'projects' in insp.get_table_names():
        try:
            op.create_foreign_key('fk_project_documents_project', 'project_documents', 'projects', ['project_id'], ['id'])
        except Exception:
            # If FK creation fails (schema mismatch), keep columns and indexes only.
            pass


def downgrade():
    try:
        op.drop_constraint('fk_project_documents_project', 'project_documents', type_='foreignkey')
    except Exception:
        pass
    op.drop_index('idx_project_documents_company_project', table_name='project_documents')
    op.drop_index('idx_project_documents_company_id', table_name='project_documents')
    op.drop_column('project_documents', 'project_id')
    op.drop_column('project_documents', 'company_id')
