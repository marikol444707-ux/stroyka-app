"""Add missing company-leading indexes to warehouse operations."""

from alembic import op


revision = "0092_warehouse_operations_idx"
down_revision = "0091_warehouse_stock_chain_idx"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE INDEX IF NOT EXISTS inventory_reconciliation_owner
        ON public.inventory_reconciliations(company_id,inventory_id)""")
    op.execute("""CREATE INDEX IF NOT EXISTS inventory_reconciliation_project_owner
        ON public.inventory_reconciliations(company_id,project_id,inventory_id)
        WHERE project_id IS NOT NULL""")
    op.execute("""CREATE INDEX IF NOT EXISTS inventory_stock_adjustment_owner
        ON public.inventory_stock_adjustments(company_id,inventory_id,id)""")
    op.execute("""CREATE INDEX IF NOT EXISTS intercompany_transfer_event_owner
        ON public.intercompany_warehouse_transfer_events(company_id,transfer_id,id)""")


def downgrade():
    op.execute("DROP INDEX IF EXISTS public.intercompany_transfer_event_owner")
    op.execute("DROP INDEX IF EXISTS public.inventory_stock_adjustment_owner")
    op.execute("DROP INDEX IF EXISTS public.inventory_reconciliation_project_owner")
    op.execute("DROP INDEX IF EXISTS public.inventory_reconciliation_owner")
