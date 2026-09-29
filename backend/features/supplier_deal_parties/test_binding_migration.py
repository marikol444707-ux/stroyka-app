import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


def statements(method='upgrade'):
    path = Path(__file__).resolve().parents[3] / 'migrations/versions/0044_supplier_document_bindings.py'
    spec = importlib.util.spec_from_file_location('binding_migration', path)
    module = importlib.util.module_from_spec(spec)
    result = []
    fake = types.ModuleType('alembic')
    fake.op = types.SimpleNamespace(execute=result.append)
    with patch.dict(sys.modules, {'alembic': fake}):
        spec.loader.exec_module(module)
    getattr(module, method)()
    return result


class BindingMigrationTests(unittest.TestCase):
    def test_columns_are_nullable_without_historical_backfill(self):
        sql = '\n'.join(statements())
        self.assertIn('contract_version_id BIGINT', sql)
        self.assertIn('source_supplier_invoice_id INTEGER', sql)
        self.assertNotIn('UPDATE public.supplier_invoices SET', sql)
        self.assertNotIn('UPDATE public.supply_deliveries SET', sql)

    def test_constraints_protect_scope_and_reference_changes(self):
        sql = '\n'.join(statements())
        self.assertIn('FOREIGN KEY (contract_version_id, company_id, offer_id)', sql)
        self.assertIn('BEFORE UPDATE OR DELETE', sql)
        self.assertIn('source_supplier_invoice_id, company_id, offer_id, contract_version_id', sql)

    def test_downgrade_refuses_to_drop_document_history(self):
        sql = '\n'.join(statements('downgrade'))
        self.assertIn('RAISE EXCEPTION', sql)
        self.assertLess(sql.index('RAISE EXCEPTION'), sql.index('DROP COLUMN'))
