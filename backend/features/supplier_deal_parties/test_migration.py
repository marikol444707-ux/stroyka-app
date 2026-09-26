import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def migration_statements(method):
    path = Path(__file__).resolve().parents[3] / 'migrations/versions/0042_supplier_deal_parties.py'
    spec = importlib.util.spec_from_file_location('deal_parties_migration', path)
    module = importlib.util.module_from_spec(spec)
    statements = []
    fake = types.ModuleType('alembic')
    fake.op = types.SimpleNamespace(execute=statements.append)
    with patch.dict(sys.modules, {'alembic': fake}):
        spec.loader.exec_module(module)
    getattr(module, method)()
    return statements


class PartiesMigrationTest(unittest.TestCase):
    def test_schema_preserves_source_identity_and_unique_versions(self):
        sql = '\n'.join(migration_statements('upgrade'))
        self.assertIn('UNIQUE (offer_id, version)', sql)
        self.assertIn('FOREIGN KEY (offer_id, company_id, request_id, supplier_id)', sql)
        self.assertIn('REFERENCES public.supplier_offers (id, company_id, request_id, supplier_id)', sql)
        self.assertIn('payer_company_id INTEGER NOT NULL REFERENCES public.companies(id)', sql)
        self.assertNotIn('UPDATE public.supplier_invoices', sql)
        self.assertNotIn('DEFAULT 1', sql)

    def test_downgrade_will_not_erase_party_history(self):
        sql = migration_statements('downgrade')
        self.assertIn('RAISE EXCEPTION', sql[0])
        self.assertIn('supplier_deal_parties', sql[0])
