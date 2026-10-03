"""Add company-leading indexes to the tool-responsibility chain."""

from alembic import op


revision = "0090_tool_responsibility_idx"
down_revision = "0089_work_contract_act_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE INDEX IF NOT EXISTS tool_incident_owner
        ON public.tool_incidents(company_id,tool_id,id)""")
    op.execute("""CREATE INDEX IF NOT EXISTS tool_incident_decision_owner
        ON public.tool_incident_decisions(company_id,incident_id,id DESC)""")
    op.execute("""CREATE INDEX IF NOT EXISTS tool_fine_allocation_owner
        ON public.tool_fine_allocations(company_id,act_id,incident_id)""")


def downgrade():
    op.execute("DROP INDEX IF EXISTS public.tool_fine_allocation_owner")
    op.execute("DROP INDEX IF EXISTS public.tool_incident_decision_owner")
    op.execute("DROP INDEX IF EXISTS public.tool_incident_owner")
