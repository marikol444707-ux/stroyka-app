import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class SupplierDocumentMigrationTest(unittest.TestCase):
    def test_migration_keeps_legacy_ownership_unknown_and_guards_downgrade(self):
        path = Path(__file__).resolve().parents[3] / 'migrations/versions/0008_supplier_document_ownership.py'
        spec = importlib.util.spec_from_file_location('supplier_document_migration', path)
        module = importlib.util.module_from_spec(spec)
        statements = []
        fake = types.ModuleType('alembic')
        fake.op = types.SimpleNamespace(execute=statements.append)
        with patch.dict(sys.modules, {'alembic': fake}):
            spec.loader.exec_module(module)
        module.upgrade()
        sql = '\n'.join(statements)
        self.assertIn('company_id INTEGER', sql)
        self.assertIn('archived_at TIMESTAMP', sql)
        self.assertIn('REFERENCES public.companies(id)', sql)
        self.assertNotIn('DEFAULT 1', sql)
        self.assertNotIn('UPDATE supplier_documents', sql)
        statements.clear()
        module.downgrade()
        self.assertIn('RAISE EXCEPTION', statements[0])
        self.assertIn('company_id IS NOT NULL OR archived_at IS NOT NULL', statements[0])
