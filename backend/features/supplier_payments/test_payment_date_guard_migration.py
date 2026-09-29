import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / 'migrations/versions/0072_supplier_payment_date_guard.py'


class SupplierPaymentDateGuardMigrationTests(unittest.TestCase):
    def test_revision_replaces_text_comparison_with_date_comparison(self):
        tree = ast.parse(MIGRATION.read_text(encoding='utf-8'))
        statements = []
        namespace = {'op': SimpleNamespace(execute=statements.append)}
        exec(compile(ast.Module(body=[node for node in tree.body
            if isinstance(node, (ast.Assign, ast.FunctionDef))], type_ignores=[]), str(MIGRATION), 'exec'), namespace)

        self.assertEqual(namespace['revision'], '0072_payment_date_guard')
        self.assertEqual(namespace['down_revision'], '0071_approved_legacy_lines')
        namespace['upgrade']()
        sql = '\n'.join(statements)
        self.assertIn('CREATE OR REPLACE FUNCTION public.supplier_payment_operation_guard()', sql)
        self.assertIn('payment.date::DATE', sql)
        self.assertIn('NEW.payment_date)', sql)
        self.assertNotIn('NEW.payment_date::TEXT', sql)


if __name__ == '__main__':
    unittest.main()
