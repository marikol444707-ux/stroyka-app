"""Personal, revisioned warehouse batch drafts; no stock movement or backfill."""
from alembic import op
revision='0111_warehouse_batch_drafts'
down_revision='0110_tb_journal_owner'
branch_labels=None
depends_on=None
SCHEMA_SQL='''CREATE TABLE warehouse_batch_drafts (
 company_id INTEGER NOT NULL REFERENCES companies(id),
 user_id INTEGER NOT NULL REFERENCES users(id),
 revision BIGINT NOT NULL DEFAULT 0 CHECK(revision>=0),
 document JSONB NOT NULL CHECK(jsonb_typeof(document)='object'),
 last_save_request_id UUID,
 last_operation_id BIGINT,
 last_issue_request_id UUID,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(company_id,user_id),
 FOREIGN KEY(last_operation_id,company_id) REFERENCES warehouse_distribution_operations(id,company_id)
)'''
def upgrade():op.execute(SCHEMA_SQL)
def downgrade():raise RuntimeError('Saved warehouse drafts must not be discarded automatically')
