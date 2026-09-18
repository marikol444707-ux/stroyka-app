import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from fastapi import HTTPException


def load_route(namespace):
    tree = ast.parse((Path(__file__).resolve().parents[2] / 'main.py').read_text())
    node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'create_warehouse_movement')
    node.decorator_list = []
    node.returns = None
    for arg in node.args.args:
        arg.annotation = None
    node.args.defaults = [ast.Constant(None)] * len(node.args.defaults)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), '<route>', 'exec'), namespace)
    return namespace['create_warehouse_movement']


class MovementTransactionTest(unittest.TestCase):
    def test_legacy_writers_take_compatibility_lock_before_receipt_or_movement(self):
        tree = ast.parse((Path(__file__).resolve().parents[2] / 'main.py').read_text())
        for name, later in [('create_warehouse_movement', '_apply_warehouse_movement('),
                            ('delete_warehouse_invoice', '_ensure_invoice_document_link_columns(')]:
            node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            source = ast.unparse(node)
            self.assertLess(source.index('lock_distribution_compatible_stock(cur)'), source.index(later))

    def test_gross_source_sum_is_only_legacy_fallback_without_lot(self):
        tree = ast.parse((Path(__file__).resolve().parents[2] / 'main.py').read_text())
        worker = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_apply_warehouse_movement')
        fallback = [node for node in ast.walk(worker) if isinstance(node, ast.If)
                    and isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not)
                    and isinstance(node.test.operand, ast.Name) and node.test.operand.id == 'selected_receipt_lot']
        self.assertEqual(len(fallback), 1)
        self.assertIn('SUM(quantity)', ast.unparse(fallback[0]))

    def test_worker_has_no_transaction_lifecycle_or_postcommit_side_effects(self):
        tree = ast.parse((Path(__file__).resolve().parents[2] / 'main.py').read_text())
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_apply_warehouse_movement')
        calls = [part for part in ast.walk(node) if isinstance(part, ast.Call)]
        for call in calls:
            if isinstance(call.func, ast.Attribute):
                self.assertNotIn(call.func.attr, ('commit', 'rollback', 'close'))
            if isinstance(call.func, ast.Name):
                self.assertNotIn(call.func.id, ('get_db', '_run_project_ai_control_safely', '_sync_supplier_invoice_from_warehouse'))

    def test_route_commits_worker_and_rolls_back_failures(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                conn, cur = Mock(), Mock()
                conn.cursor.return_value = cur
                cur.fetchone.return_value = {'present': True}
                worker = Mock(side_effect=ValueError('reject') if fail else None, return_value={'id': 7})
                after = Mock(return_value={})
                namespace = {'get_db': lambda: conn, 'psycopg2': SimpleNamespace(extras=SimpleNamespace(RealDictCursor=object)),
                    # This test exercises the legacy transaction path, independent of host flags.
                    'os': SimpleNamespace(getenv=lambda *args: None),
                    'HTTPException': HTTPException, 'PACKAGE_LIMIT_ROLES': (), 'MAIN_WAREHOUSE_WRITE_ROLES': ('директор',),
                    'require_project_or_warehouse_access': Mock(), '_project_company_id': lambda *_: 2,
                    '_positive_int_or_none': lambda value: value, '_resolve_work_company_context': lambda *a, **k: {'companyId': 2},
                    '_apply_warehouse_movement': worker, '_create_warehouse_movement_review_task_safely': after,
                    '_run_project_ai_control_safely': Mock()}
                route = load_route(namespace)
                model = SimpleNamespace(materialName='Кабель', fromLocation='Основной склад', toLocation='Школа', workPackage='', quantity=5)
                if fail:
                    with self.assertRaises(ValueError):
                        route(model, _current_user={'role': 'директор'})
                    conn.rollback.assert_called_once()
                    conn.commit.assert_not_called()
                    after.assert_not_called()
                else:
                    self.assertEqual(route(model, _current_user={'role': 'директор'}), {'id': 7})
                    conn.commit.assert_called_once()
                    conn.rollback.assert_not_called()
                cur.close.assert_called_once()
                conn.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
