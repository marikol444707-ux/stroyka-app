"""Prevent dangling supplier/warehouse invoice links.

Revision ID: 0003_accounting_link_integrity
Revises: 0002_ops_error_logging
Create Date: 2026-08-27
"""

from alembic import op


revision = "0003_accounting_link_integrity"
down_revision = "0002_ops_error_logging"
branch_labels = None
depends_on = None


_SUPPLIER_INVOICE_CONSTRAINT = """
DO $a11_link_supplier_invoices$ BEGIN
IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conname='fk_a11_supplier_invoices_warehouse_invoice'
      AND conrelid='public.supplier_invoices'::regclass
) THEN
    ALTER TABLE public.supplier_invoices
    ADD CONSTRAINT fk_a11_supplier_invoices_warehouse_invoice
    FOREIGN KEY (warehouse_invoice_id)
    REFERENCES public.warehouse_invoices(id)
    ON DELETE SET NULL DEFERRABLE INITIALLY IMMEDIATE;
END IF;
END $a11_link_supplier_invoices$
"""

_WAREHOUSE_INVOICE_CONSTRAINT = """
DO $a11_link_warehouse_invoices$ BEGIN
IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint
    WHERE conname='fk_a11_warehouse_invoices_supplier_invoice'
      AND conrelid='public.warehouse_invoices'::regclass
) THEN
    ALTER TABLE public.warehouse_invoices
    ADD CONSTRAINT fk_a11_warehouse_invoices_supplier_invoice
    FOREIGN KEY (supplier_invoice_id)
    REFERENCES public.supplier_invoices(id)
    ON DELETE SET NULL DEFERRABLE INITIALLY IMMEDIATE;
END IF;
END $a11_link_warehouse_invoices$
"""


def upgrade() -> None:
    op.execute(_SUPPLIER_INVOICE_CONSTRAINT)
    op.execute(_WAREHOUSE_INVOICE_CONSTRAINT)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.warehouse_invoices "
        "DROP CONSTRAINT IF EXISTS "
        "fk_a11_warehouse_invoices_supplier_invoice"
    )
    op.execute(
        "ALTER TABLE public.supplier_invoices "
        "DROP CONSTRAINT IF EXISTS "
        "fk_a11_supplier_invoices_warehouse_invoice"
    )
