"""Add company-leading indexes to the work-material ownership chain."""

from alembic import op


revision = "0087_work_material_indexes"
down_revision = "0086_counterparty_doc_owners"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE INDEX IF NOT EXISTS work_material_account_project_owner
        ON public.work_material_accounts(company_id,project_id,journal_id)""")
    op.execute("""CREATE INDEX IF NOT EXISTS work_material_defect_item_owner
        ON public.work_material_defect_items(company_id,defect_id,entry_id)""")
    op.execute("""CREATE INDEX IF NOT EXISTS work_material_decision_owner
        ON public.work_material_defect_decisions(company_id,defect_id,id DESC)""")


def downgrade():
    op.execute("DROP INDEX IF EXISTS public.work_material_decision_owner")
    op.execute("DROP INDEX IF EXISTS public.work_material_defect_item_owner")
    op.execute("DROP INDEX IF EXISTS public.work_material_account_project_owner")
