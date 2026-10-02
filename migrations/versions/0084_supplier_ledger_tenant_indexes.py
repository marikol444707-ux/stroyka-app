"""Add company lookup indexes to supplier-ledger child tables."""

from alembic import op


revision = "0084_supplier_ledger_indexes"
down_revision = "0083_intercompany_lot_lineage"
branch_labels = None
depends_on = None


INDEXES = (
    ("idx_supplier_payment_allocation_rows_company", "supplier_payment_allocation_rows", "company_id,revision_id"),
    ("idx_supplier_payment_impacts_company", "supplier_payment_impacts", "company_id,operation_id"),
    ("idx_supplier_payment_refund_links_company", "supplier_payment_refund_links", "company_id,group_id"),
    ("idx_supplier_mixed_opening_bindings_company", "supplier_mixed_opening_bindings", "company_id,review_id"),
    ("idx_supplier_invoice_lines_company", "supplier_invoice_lines", "company_id,spec_id"),
    ("idx_supplier_legacy_contract_bindings_company", "supplier_legacy_contract_bindings", "company_id,invoice_id"),
    ("idx_supplier_receipt_line_proofs_company", "supplier_receipt_line_proofs", "company_id,receipt_relation_id"),
)


def upgrade():
    for name, table, columns in INDEXES:
        op.execute(f"CREATE INDEX {name} ON public.{table}({columns})")


def downgrade():
    for name, _table, _columns in reversed(INDEXES):
        op.execute(f"DROP INDEX public.{name}")
