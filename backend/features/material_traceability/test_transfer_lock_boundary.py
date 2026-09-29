"""Execute legacy entry points without importing main/config or opening a DB.

Only the early transaction/authorization/locking boundary is exercised here.
Real PostgreSQL lock interleavings are covered separately.
"""
import ast
import math
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import psycopg2.extras
from fastapi import HTTPException


ROUTES = ('create_material_transfer', 'return_material_from_master', 'delete_material_transfer')


def load_route(name, namespace):
    path = Path(__file__).resolve().parents[2] / 'main.py'
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    for arg in node.args.args:
        arg.annotation = None
    node.args.defaults = [ast.Constant(None)] * len(node.args.defaults)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 str(path), 'exec'), namespace)
    return namespace[name]


class TransferLockBoundaryTests(unittest.TestCase):
    def invoke(self, name, *, role='директор', fail_lock=False, schema_present=True):
        events = []
        conn, cur = Mock(), Mock()
        conn.autocommit = True
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {'present': schema_present}

        def execute(sql, params=()):
            self.assertFalse(conn.autocommit)
            if sql.startswith('LOCK TABLE'):
                events.append('stock_lock')
                if fail_lock:
                    raise HTTPException(409, 'Synthetic lock conflict')
        cur.execute.side_effect = execute

        def parent(*args, **kwargs):
            events.append('parent')
            raise HTTPException(409, 'Synthetic stop before business writes')

        namespace = dict(
            get_db=lambda: conn, psycopg2=psycopg2, math=math, HTTPException=HTTPException,
            _norm_base_unit=lambda value: value,
            _resolve_work_company_context=lambda *a, **k: {},
            effective_company_actors=lambda user, context: [user],
            WAREHOUSE_ROLES=('директор',), SUPPLY_INTERNAL_ROLES=('директор',),
            WORKER_EXECUTION_ROLES=('мастер',),
        )
        route = load_route(name, namespace)
        target = ('backend.features.material_transfer_access.service.resolve_material_transfer_parent'
                  if name == 'delete_material_transfer'
                  else 'backend.features.project_access.service.resolve_project_parent')
        data = dict(materialName='Cement', quantity=1, unit='кг', projectName='Alpha',
                    fromLocation='Alpha', workPackage='Основная', toPersonRole='мастер')
        user = dict(id=1, companyId=2, role=role)
        with patch(target, side_effect=parent), self.assertRaises(HTTPException) as error:
            route(1 if name == 'delete_material_transfer' else data, current_user=user)
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()
        cur.close.assert_called_once()
        conn.close.assert_called_once()
        return events, error.exception

    def test_stock_lock_precedes_parent_and_row_access(self):
        for name in ROUTES:
            with self.subTest(route=name):
                events, error = self.invoke(name)
                self.assertEqual(error.status_code, 409)
                self.assertEqual(events, ['stock_lock', 'parent'])

    def test_denied_company_role_does_not_acquire_global_stock_lock(self):
        for name in ROUTES:
            with self.subTest(route=name):
                events, error = self.invoke(name, role='поставщик')
                self.assertEqual(error.status_code, 403)
                self.assertEqual(events, [])

    def test_lock_failure_rolls_back_before_parent_access(self):
        for name in ROUTES:
            with self.subTest(route=name):
                events, error = self.invoke(name, fail_lock=True)
                self.assertEqual(error.detail, 'Synthetic lock conflict')
                self.assertEqual(events, ['stock_lock'])

    def test_without_distribution_schema_no_table_lock_is_added(self):
        for name in ROUTES:
            with self.subTest(route=name):
                events, error = self.invoke(name, schema_present=False)
                self.assertEqual(error.detail, 'Synthetic stop before business writes')
                self.assertEqual(events, ['parent'])
