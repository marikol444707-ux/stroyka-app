import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.features.project_payment_access.routes import register_project_payments_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def delete(self, path):
        return self._register("DELETE", path)

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator


class FakeCursor:
    def __init__(self, rows=(), fetchone_results=(), ledger_operation=None, ledger_exists=False):
        self.rows = list(rows)
        self.fetchone_results = list(fetchone_results)
        self.calls = []
        self.ledger_operation = ledger_operation
        self.ledger_exists = ledger_exists or ledger_operation is not None

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        if 'to_regclass' in self.calls[-1][0]:
            return {'ledger_exists': self.ledger_exists}
        if 'FROM supplier_payment_operations' in self.calls[-1][0]:
            return self.ledger_operation
        return self.fetchone_results.pop(0) if self.fetchone_results else None

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def build(cursor, visibility=("pp.company_id=%s", [3])):
    app = FakeApp()
    connection = FakeConnection(cursor)

    def fake_visibility(actors, roles, **kwargs):
        sql, params = visibility
        return sql, list(params)

    deps = {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "finance_roles": ("директор",),
        "platform_staff_roles": ("system_owner",),
        "client_account_roles": ("account_owner",),
        "resolve_work_company_context": lambda cur, user, project, mode, **kw: {"mode": "company", "companyId": 3},
        "effective_company_actors": lambda user, ctx: [{"companyId": 3, "role": "директор", "name": "Тест"}],
        "resolve_project_payment_actor": lambda cur, user, project, pkg, **kw: (3, {"name": "Тест"}),
        "positive_int_or_none": lambda v: int(v) if v else None,
        "require_project_access": lambda user, project: None,
        "has_package_access": lambda user, pkg: True,
    }
    with patch("backend.features.project_payment_access.routes.project_payment_visibility_filter", fake_visibility):
        register_project_payments_module(app, deps)
    # visibility filter is resolved at call time inside handlers, keep patch active per-test
    return app, connection, fake_visibility


class ProjectPaymentRoutesTest(unittest.TestCase):
    def test_ledger_payment_cannot_be_reversed_through_legacy_endpoint(self):
        row = {'company_id': 3, 'project_name': 'Объект', 'work_package': '', 'amount': 500}
        cursor = FakeCursor(fetchone_results=[row, None, {'id': 88}], ledger_operation={'id': 12})
        app, connection, _ = build(cursor)
        with patch('backend.features.project_payment_access.routes.resolve_resource_company_actor',
                   lambda *a, **kw: ({}, {'name': 'Тест', 'role': 'директор'})):
            with self.assertRaises(HTTPException) as error:
                app.routes[('DELETE', '/project-payments/{id}')](
                    id=5, x_company_id='3', x_company_mode='company', _current_user={})
        self.assertEqual(error.exception.status_code, 409)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertFalse(any(sql.startswith('INSERT') for sql, _ in cursor.calls))

    def test_registers_same_urls(self):
        app, _conn, _v = build(FakeCursor())
        for key in [("GET", "/project-payments"), ("POST", "/project-payments"), ("DELETE", "/project-payments/{id}")]:
            self.assertIn(key, app.routes)

    def test_read_scope_false_returns_empty(self):
        cursor = FakeCursor()
        app, _conn, fake = build(cursor, visibility=("FALSE", []))
        with patch("backend.features.project_payment_access.routes.project_payment_visibility_filter", fake):
            result = app.routes[("GET", "/project-payments")](
                project_name="", x_company_id=None, x_company_mode=None, current_user={}
            )
        self.assertEqual(result, [])
        self.assertEqual(cursor.calls, [])

    def test_create_with_note_short_circuits_duplicate(self):
        cursor = FakeCursor(fetchone_results=[{"id": 77}])
        app, connection, _v = build(cursor)
        result = app.routes[("POST", "/project-payments")](
            {"projectName": "Объект", "amount": 100, "note": "оплата"},
            x_company_id="3", x_company_mode="company", _current_user={},
        )
        self.assertEqual(result, {"id": 77, "companyId": 3, "ok": True, "duplicate": True})
        self.assertFalse(connection.committed)

    def test_delete_missing_payment_404(self):
        cursor = FakeCursor(fetchone_results=[None])
        app, connection, _v = build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("DELETE", "/project-payments/{id}")](
                id=99, x_company_id=None, x_company_mode=None, _current_user={}
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertTrue(connection.rolled_back)

    def test_delete_creates_negative_reversal(self):
        row = {"company_id": 3, "project_name": "Объект", "work_package": "",
               "amount": 500, "note": "оплата", "date": "2026-07-28", "added_by": "Тест"}
        cursor = FakeCursor(fetchone_results=[row, None, {"id": 88}], ledger_exists=True)
        app, connection, _v = build(cursor)
        with patch("backend.features.project_payment_access.routes.resolve_resource_company_actor",
                   lambda *a, **kw: ({"mode": "company", "companyId": 3}, {"name": "Тест", "role": "директор"})):
            result = app.routes[("DELETE", "/project-payments/{id}")](
                id=5, x_company_id="3", x_company_mode="company", _current_user={}
            )
        self.assertEqual(result["reversalId"], 88)
        self.assertTrue(result["reversed"])
        self.assertTrue(connection.committed)
        insert = [c for c in cursor.calls if c[0].startswith("INSERT INTO project_payments")][0]
        self.assertEqual(insert[1][3], -500)
        self.assertIn("Сторно платежа #5", insert[1][4])

    def test_denied_actor_is_not_told_whether_payment_is_managed(self):
        row = {'company_id': 3, 'project_name': 'Объект', 'work_package': '', 'amount': 500}
        cursor = FakeCursor(fetchone_results=[row], ledger_operation={'id': 12})
        app, connection, _ = build(cursor)
        with patch('backend.features.project_payment_access.routes.resolve_resource_company_actor',
                   side_effect=HTTPException(403, 'Denied')):
            with self.assertRaises(HTTPException) as error:
                app.routes[('DELETE', '/project-payments/{id}')](
                    id=5, x_company_id='3', x_company_mode='company', _current_user={})
        self.assertEqual(error.exception.status_code, 403)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(any('supplier_payment_operations' in sql for sql, _ in cursor.calls))

    def test_delete_already_reversed_is_idempotent(self):
        row = {"company_id": 3, "project_name": "Объект", "work_package": "",
               "amount": 500, "note": "", "date": "2026-07-28", "added_by": "Тест"}
        cursor = FakeCursor(fetchone_results=[row, {"id": 88}])
        app, connection, _v = build(cursor)
        with patch("backend.features.project_payment_access.routes.resolve_resource_company_actor",
                   lambda *a, **kw: ({"mode": "company", "companyId": 3}, {"name": "Тест", "role": "директор"})):
            result = app.routes[("DELETE", "/project-payments/{id}")](
                id=5, x_company_id="3", x_company_mode="company", _current_user={}
            )
        self.assertTrue(result["alreadyReversed"])
        self.assertFalse(connection.committed)


if __name__ == "__main__":
    unittest.main()
