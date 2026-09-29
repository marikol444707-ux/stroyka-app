"""Keep the extracted worker inside its caller's transaction."""
import ast
import unittest
from pathlib import Path


class SyncTransactionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse((Path(__file__).resolve().parents[2] / 'main.py').read_text())
        cls.functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    def test_worker_does_not_own_lifecycle_schema_or_external_effects(self):
        node = self.functions['_sync_supplier_invoice_from_warehouse_in_transaction']
        for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
            if isinstance(call.func, ast.Attribute):
                self.assertNotIn(call.func.attr, ('commit', 'rollback', 'close'))
            if isinstance(call.func, ast.Name):
                self.assertNotIn(call.func.id, ('get_db', '_ensure_invoice_document_link_columns',
                    '_ensure_warehouse_invoice_accounting_columns', '_run_project_ai_control_safely'))

    def test_receipt_sync_precedes_commit_and_postcommit_ai(self):
        source = ast.unparse(self.functions['_create_warehouse_invoice_record'])
        self.assertLess(source.index('_sync_supplier_invoice_from_warehouse_in_transaction('), source.index('conn.commit()'))
        self.assertLess(source.index('conn.commit()'), source.index('_run_project_ai_control_safely('))
        self.assertNotIn('accountingWarning', source)
        self.assertNotIn('_sync_supplier_invoice_from_warehouse(', source)

    def test_wrapper_commits_worker_once(self):
        source = ast.unparse(self.functions['_sync_supplier_invoice_from_warehouse'])
        self.assertEqual(source.count('conn.commit()'), 1)
        self.assertIn('conn.rollback()', source)
        self.assertIn('conn.close()', source)
