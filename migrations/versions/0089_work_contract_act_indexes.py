"""Add company-leading indexes to the work-contract act chain."""

from alembic import op


revision = "0089_work_contract_act_indexes"
down_revision = "0088_work_acceptance_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE INDEX IF NOT EXISTS work_contract_act_owner
        ON public.work_contract_acts(company_id,contract_id,act_id)""")
    op.execute("""CREATE INDEX IF NOT EXISTS work_contract_act_item_owner
        ON public.work_contract_act_items(company_id,act_id,journal_id)""")
    op.execute("""CREATE INDEX IF NOT EXISTS work_contract_fine_owner
        ON public.work_contract_fine_allocations(company_id,act_id,defect_id)""")
    op.execute("""CREATE INDEX IF NOT EXISTS work_contract_signature_owner
        ON public.work_contract_act_signatures(company_id,act_id,operation_id)""")
    op.execute("""CREATE INDEX IF NOT EXISTS work_contract_payment_owner
        ON public.work_contract_act_payments(company_id,act_id,payment_id)""")


def downgrade():
    op.execute("DROP INDEX IF EXISTS public.work_contract_payment_owner")
    op.execute("DROP INDEX IF EXISTS public.work_contract_signature_owner")
    op.execute("DROP INDEX IF EXISTS public.work_contract_fine_owner")
    op.execute("DROP INDEX IF EXISTS public.work_contract_act_item_owner")
    op.execute("DROP INDEX IF EXISTS public.work_contract_act_owner")
