"""Source-level guard for additive projection in the legacy main routes."""
import ast
from pathlib import Path
import unittest


class MovementProjectionTest(unittest.TestCase):
    def test_read_and_create_return_stored_company_identity(self):
        main_tree = ast.parse((Path(__file__).resolve().parents[2] / 'main.py').read_text())
        movement_tree = ast.parse((Path(__file__).resolve().parents[1] / 'warehouse_movements' / 'routes.py').read_text())
        for tree, name in ((movement_tree, 'get_warehouse_movements'), (main_tree, '_apply_warehouse_movement')):
            functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
            self.assertEqual(len(functions), 1, name)
            sql = '\n'.join(node.value for node in ast.walk(functions[0])
                            if isinstance(node, ast.Constant) and isinstance(node.value, str))
            self.assertRegex(sql, r'company_id as "companyId"', name)


if __name__ == '__main__':
    unittest.main()
