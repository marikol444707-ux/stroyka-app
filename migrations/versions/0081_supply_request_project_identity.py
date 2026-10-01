"""Store the exact project identity on supply requests."""

from alembic import op


revision = "0081_supply_project_id"
down_revision = "0080_outgoing_letter_parties"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE supply_requests ADD COLUMN IF NOT EXISTS project_id INTEGER")
    op.execute(
        "CREATE INDEX IF NOT EXISTS supply_requests_company_project_idx "
        "ON supply_requests(company_id,project_id,id)"
    )
    op.execute(
        "ALTER TABLE supply_requests ADD CONSTRAINT supply_requests_project_owner_fk "
        "FOREIGN KEY(project_id,company_id) REFERENCES projects(id,company_id)"
    )


def downgrade():
    op.execute("LOCK TABLE supply_requests IN ACCESS EXCLUSIVE MODE")
    op.execute("""DO $$ BEGIN IF EXISTS (
        SELECT 1 FROM supply_requests WHERE project_id IS NOT NULL
    ) THEN RAISE EXCEPTION 'Cannot discard stored supply request project identity'; END IF; END $$""")
    op.execute("ALTER TABLE supply_requests DROP CONSTRAINT supply_requests_project_owner_fk")
    op.execute("DROP INDEX supply_requests_company_project_idx")
    op.execute("ALTER TABLE supply_requests DROP COLUMN project_id")
