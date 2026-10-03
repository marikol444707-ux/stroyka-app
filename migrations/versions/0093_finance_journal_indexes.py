"""Add missing owner lookup indexes to finance journals."""

from alembic import op


revision = "0093_finance_journal_indexes"
down_revision = "0092_warehouse_operations_idx"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE INDEX IF NOT EXISTS company_payments_owner
        ON public.company_payments(company_id,id)""")
    op.execute("""CREATE INDEX IF NOT EXISTS brigade_acts_contract_lookup
        ON public.brigade_acts(contract_id,id)""")


def downgrade():
    op.execute("DROP INDEX IF EXISTS public.brigade_acts_contract_lookup")
    op.execute("DROP INDEX IF EXISTS public.company_payments_owner")
