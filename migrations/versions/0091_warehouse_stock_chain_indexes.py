"""Add missing company-leading indexes to the warehouse stock chain."""

from alembic import op


revision = "0091_warehouse_stock_chain_idx"
down_revision = "0090_tool_responsibility_idx"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE INDEX IF NOT EXISTS warehouse_main_owner
        ON public.warehouse_main(company_id,id)""")
    op.execute("""CREATE INDEX IF NOT EXISTS warehouse_movement_owner
        ON public.warehouse_movements(company_id,id DESC)""")
    op.execute("""CREATE INDEX IF NOT EXISTS warehouse_receipt_lot_project_owner
        ON public.warehouse_receipt_lots(company_id,project_id,id)
        WHERE project_id IS NOT NULL""")


def downgrade():
    op.execute("DROP INDEX IF EXISTS public.warehouse_receipt_lot_project_owner")
    op.execute("DROP INDEX IF EXISTS public.warehouse_movement_owner")
    op.execute("DROP INDEX IF EXISTS public.warehouse_main_owner")
