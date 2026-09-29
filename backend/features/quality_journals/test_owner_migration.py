import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import patch


def load_migration(revision='0023_quality_journal_owners'):
    path = Path(__file__).resolve().parents[3] / 'migrations' / 'versions' / (revision + '.py')
    spec = importlib.util.spec_from_file_location(revision, path)
    module = importlib.util.module_from_spec(spec)
    alembic = ModuleType('alembic')
    alembic.op = None
    with patch.dict(sys.modules, {'alembic': alembic}):
        spec.loader.exec_module(module)
    return module


class OwnerMigrationTests(unittest.TestCase):
    def test_upgrade_has_no_data_backfill_or_owner_default(self):
        migration = load_migration()
        statements = []
        with patch.object(migration, 'op', SimpleNamespace(execute=statements.append)):
            migration.upgrade()
        self.assertEqual(migration.down_revision, '0022_supplier_company_catalog')
        self.assertFalse(any(sql.strip().upper().startswith(('UPDATE ', 'INSERT ', 'DELETE ')) for sql in statements))
        added = [sql.upper() for sql in statements if 'ADD COLUMN' in sql.upper()]
        self.assertTrue(added)
        self.assertFalse(any('DEFAULT' in sql for sql in added))

    def test_downgrade_locks_every_owner_table_before_check_or_drop(self):
        migration = load_migration()
        statements = []
        with patch.object(migration, 'op', SimpleNamespace(execute=statements.append)):
            migration.downgrade()
        self.assertTrue(statements[0].startswith('LOCK TABLE '))
        for table in migration.OWNER_TABLES:
            self.assertIn(table, statements[0])
        self.assertIn('read committed', statements[1])
        self.assertIn('RAISE EXCEPTION', statements[1])
