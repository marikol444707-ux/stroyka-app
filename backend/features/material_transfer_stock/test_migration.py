"""Prepared additive migration contract, no database execution."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class SourceMigrationTests(unittest.TestCase):
    def test_additive_column_no_backfill(self):
        p=Path(__file__).resolve().parents[3]/'migrations/versions/0104_material_transfer_source_stock.py'
        tree=ast.parse(p.read_text());calls=[];ns={'op':SimpleNamespace(execute=calls.append)}
        exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,(ast.Assign,ast.FunctionDef))],type_ignores=[]),str(p),'exec'),ns)
        self.assertEqual(ns['revision'],'0104_transfer_source_stock')
        self.assertEqual(ns['down_revision'],'0103_movement_pending_drafts')
        ns['upgrade']();self.assertEqual(calls,['ALTER TABLE material_transfers ADD COLUMN IF NOT EXISTS source_stock_id INT'])
        with self.assertRaises(RuntimeError):ns['downgrade']()
