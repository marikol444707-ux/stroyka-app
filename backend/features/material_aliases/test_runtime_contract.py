"""Ensure every legacy alias consumer explicitly carries tenant ownership."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock, MagicMock, patch

from fastapi import HTTPException
from backend.features.material_aliases.runtime import owned_aliases_enabled, resolve_owned_alias


class AliasRuntimeContractTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertFalse(owned_aliases_enabled())

    def test_missing_owner_rejected_before_any_query(self):
        cur = Mock()
        with self.assertRaises(HTTPException) as error:
            resolve_owned_alias(cur, 'Object', 'Brand')
        self.assertEqual(error.exception.status_code, 409)
        cur.connection.cursor.assert_not_called()

    def test_every_alias_consumer_passes_company_explicitly(self):
        path = Path(__file__).resolve().parents[2] / 'main.py'
        tree = ast.parse(path.read_text())
        names = {'_material_control_key_resolved', '_resolve_material_alias', '_apply_material_alias_to_invoice_item'}
        missing = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Name) and node.func.id in names
                   and 'company_id' not in {kw.arg for kw in node.keywords}]
        self.assertEqual(missing, [])

    def test_invalid_project_never_falls_back_to_name(self):
        for project in (True, '7', 0, -1):
            cur = Mock()
            with self.assertRaises(HTTPException):
                resolve_owned_alias(cur, 'Object', 'Brand', company_id=2, project_id=project)
            cur.connection.cursor.assert_not_called()

    def test_reader_uses_same_connection_and_propagates_schema_error(self):
        cur = MagicMock()
        scoped_cursor = cur.connection.cursor.return_value.__enter__.return_value
        with patch('backend.features.material_aliases.runtime.resolve_alias', side_effect=RuntimeError('schema')) as resolver:
            with self.assertRaisesRegex(RuntimeError, 'schema'):
                resolve_owned_alias(cur, '', 'Brand', company_id=2)
            resolver.assert_called_once_with(scoped_cursor, company_id=2, project_id=None, name='Brand')
        cur.execute.assert_not_called()
        cur.connection.commit.assert_not_called()

    def test_owned_mode_blocks_all_legacy_editor_operations_before_sql(self):
        from backend.features.material_aliases.test_routes import build, FakeCursor
        from backend.features.material_aliases.routes import MaterialAliasModel
        cursor = FakeCursor()
        app, _ = build(cursor)
        calls = [('GET', '/material-aliases', {}),
                 ('POST', '/material-aliases', {'data': MaterialAliasModel(aliasName='A', canonicalName='B')}),
                 ('DELETE', '/material-aliases/{id}', {'id': 1})]
        with patch.dict('os.environ', {'COMPANY_MATERIAL_ALIASES_ENABLED': '1'}):
            for method, path, kwargs in calls:
                with self.assertRaises(HTTPException) as error:
                    app.routes[(method, path)](current_user={}, **kwargs)
                self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(cursor.calls, [])

    def test_journal_alias_failure_rolls_back_and_closes_locked_transaction(self):
        tree = ast.parse((Path(__file__).resolve().parents[2] / 'main.py').read_text())
        route = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_update_work_journal_with_connection')
        guarded = next(n for n in route.body if isinstance(n, ast.Try) and any(
            isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            and call.func.id == '_validate_work_material_norm_reasons' for call in ast.walk(n)))
        # Execute the actual transaction block, injecting only the validation fault.
        fn = ast.FunctionDef(name='run', args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                             body=[guarded], decorator_list=[])
        for failure in (HTTPException(409, 'Owner missing'), RuntimeError('Missing schema')):
            conn, cur = Mock(), Mock()
            ns = dict(conn=conn, cur=cur, HTTPException=HTTPException, new_materials=[{'name': 'A'}],
                      project_row={'company_id': 2}, project_name='Object', data={}, new_qty=1,
                      _current_user={'role': 'директор'},
                      _validate_work_material_norm_reasons=Mock(side_effect=failure))
            exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), '<journal-transaction>', 'exec'), ns)
            with self.assertRaises(HTTPException) as error:
                ns['run']()
            self.assertEqual(error.exception.status_code, 409 if isinstance(failure, HTTPException) else 500)
            conn.rollback.assert_called_once()
            conn.commit.assert_not_called()
            cur.close.assert_called_once()
            conn.close.assert_called_once()

    def test_journal_route_delegates_and_closes_early_helper_failures(self):
        tree = ast.parse((Path(__file__).resolve().parents[2] / 'main.py').read_text())
        route = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'update_work_journal')
        fn = ast.FunctionDef(
            name='run',
            args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=name) for name in
                ('id', 'data', 'x_company_id', 'x_company_mode', '_current_user')],
                kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=route.body, decorator_list=[],
        )
        for failure in (None, HTTPException(409, 'Owner missing'), RuntimeError('Missing schema')):
            with self.subTest(failure=type(failure).__name__):
                conn = Mock(closed=False)
                result = {'ok': True}
                helper = Mock(return_value=result, side_effect=failure)
                get_db = Mock(return_value=conn)
                ns = dict(get_db=get_db, _update_work_journal_with_connection=helper)
                exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                             '<journal-route>', 'exec'), ns)
                data, actor = {}, {'id': 9, 'role': 'директор'}
                if failure is None:
                    self.assertIs(ns['run'](4, data, '2', 'company', actor), result)
                    conn.rollback.assert_not_called()
                else:
                    with self.assertRaises(type(failure)) as error:
                        ns['run'](4, data, '2', 'company', actor)
                    self.assertIs(error.exception, failure)
                    conn.rollback.assert_called_once()
                get_db.assert_called_once_with()
                helper.assert_called_once_with(conn, 4, data, '2', 'company', actor)
                conn.commit.assert_not_called()
                conn.close.assert_called_once()

    def test_estimate_refresh_failure_rolls_back_and_closes_transaction(self):
        tree = ast.parse((Path(__file__).resolve().parents[2] / 'main.py').read_text())
        route = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_update_estimate_with_connection')
        guarded = next(n for n in route.body if isinstance(n, ast.Try) and any(
            isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            and call.func.id == '_refresh_open_supply_controls_for_estimate' for call in ast.walk(n)))
        fn = ast.FunctionDef(name='run', args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                             body=[guarded], decorator_list=[])
        for failure in (HTTPException(409, 'Owner missing'), RuntimeError('Missing schema')):
            conn, cur = Mock(), Mock()
            ns = dict(conn=conn, cur=cur, new_status='Активная', project_name='Object',
                      estimate_materials_changed=True, estimate_scope={'companyId': 2, 'projectId': 7},
                      _refresh_open_supply_controls_for_estimate=Mock(side_effect=failure))
            exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), '<estimate-transaction>', 'exec'), ns)
            with self.assertRaises(type(failure)):
                ns['run']()
            conn.rollback.assert_called_once()
            conn.commit.assert_not_called()
            cur.close.assert_called_once()
            conn.close.assert_called_once()
