"""Add company lookup indexes to supplier-contract and archive tables."""

from alembic import op


revision = "0085_supplier_contract_indexes"
down_revision = "0084_supplier_ledger_indexes"
branch_labels = None
depends_on = None


INDEXES = (
    ("idx_company_documents_company", "company_documents", "company_id,id"),
    ("idx_supplier_contract_publications_company", "supplier_contract_publications", "company_id,contract_version_id"),
    ("idx_supplier_contract_registry_company", "supplier_contract_registry", "company_id,supplier_id,id"),
    ("idx_supplier_contract_registry_events_company", "supplier_contract_registry_events", "company_id,registry_id,version"),
    ("idx_supplier_contract_registry_versions_company", "supplier_contract_registry_versions", "company_id,registry_id,contract_version_id"),
    ("idx_supplier_contract_versions_company", "supplier_contract_versions", "company_id,id"),
)


def upgrade():
    for name, table, columns in INDEXES:
        op.execute(f"CREATE INDEX {name} ON public.{table}({columns})")


def downgrade():
    for name, _table, _columns in reversed(INDEXES):
        op.execute(f"DROP INDEX public.{name}")
