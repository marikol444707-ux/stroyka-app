import unittest

from fastapi import HTTPException

from backend.features.brigade_access.act_routes import register_brigade_acts_module
from backend.features.inspection_orders.routes import register_inspection_orders_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def put(self, path):
        return self._register("PUT", path)

    def delete(self, path):
        return self._register("DELETE", path)

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator


class FakeCursor:
    def __init__(self, rows=(), fetchone_results=()):
        self.rows = list(rows)
        self.fetchone_results = list(fetchone_results)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.fetchone_results.pop(0) if self.fetchone_results else None

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.autocommit = True

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def row_get(row, key, index=None, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    if row is None:
        return default
    if index is not None:
        try:
            return row[index]
        except Exception:
            return default
    return default


CONTRACT = {"id": 7, "companyId": 3, "projectName": "Объект", "brigadeName": "Бригада А", "workPackage": "Основная"}


def inspection_build(cursor):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_inspection_orders_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "read_roles": ("директор",),
        "write_roles": ("директор",),
        "visible_project_names": lambda user: None,
        "require_project_access": lambda user, project: None,
        "require_row_project_access": lambda cur, table, row_id, user, col: None,
    })
    return app, connection


def brigade_build(cursor, scope=("bc.company_id=%s", [3])):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_brigade_acts_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "finance_roles": ("директор",),
        "brigade_contract_read_scope": lambda conn, user, roles, **kw: (scope[0], list(scope[1]), []),
        "resolve_brigade_contract_actor": lambda cur, user, cid, roles, **kw: (dict(CONTRACT), {"name": "Тест"}, {"id": 9}),
        "has_package_access": lambda user, pkg: True,
        "row_get": row_get,
    })
    return app, connection


class InspectionAndBrigadeActsTest(unittest.TestCase):
    def test_all_urls_registered(self):
        iapp, _c = inspection_build(FakeCursor())
        bapp, _b = brigade_build(FakeCursor())
        for key in [("GET", "/inspection-orders"), ("POST", "/inspection-orders"),
                    ("PUT", "/inspection-orders/{id}"), ("DELETE", "/inspection-orders/{id}")]:
            self.assertIn(key, iapp.routes)
        for key in [("GET", "/brigade-acts"), ("POST", "/brigade-acts")]:
            self.assertIn(key, bapp.routes)

    def test_inspection_list_hides_cancelled(self):
        cursor = FakeCursor(rows=[])
        app, _conn = inspection_build(cursor)
        app.routes[("GET", "/inspection-orders")](project_name=None, current_user={})
        self.assertIn("<> 'Аннулировано'", cursor.calls[0][0])

    def test_inspection_update_normalizes_empty_response_date(self):
        cursor = FakeCursor()
        app, _conn = inspection_build(cursor)
        app.routes[("PUT", "/inspection-orders/{id}")](
            id=4, data={"responseDate": "", "status": "Исполнено"}, current_user={}
        )
        sql, vals = cursor.calls[0]
        self.assertIn("response_date=%s", sql)
        self.assertIsNone(vals[list(vals).index(None)])

    def test_inspection_delete_is_soft(self):
        cursor = FakeCursor()
        app, connection = inspection_build(cursor)
        result = app.routes[("DELETE", "/inspection-orders/{id}")](id=4, current_user={})
        self.assertEqual(result, {"ok": True})
        self.assertIn("SET status='Аннулировано'", cursor.calls[0][0])
        self.assertTrue(connection.committed)

    def test_brigade_act_scope_false_short_circuits(self):
        cursor = FakeCursor()
        app, _conn = brigade_build(cursor, scope=("FALSE", []))
        result = app.routes[("GET", "/brigade-acts")](
            contract_id=None, x_company_id=None, x_company_mode=None, current_user={}
        )
        self.assertEqual(result, [])
        self.assertEqual(cursor.calls, [])

    def test_brigade_act_cannot_exceed_unacted_amount(self):
        totals = {"done_amount": 300, "acted_amount": 250}
        cursor = FakeCursor(fetchone_results=[totals])
        app, connection = brigade_build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/brigade-acts")](
                {"contractId": 7, "totalAmount": 100}, x_company_id="3", x_company_mode="company", current_user={}
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("50.00", ctx.exception.detail)
        self.assertTrue(connection.rolled_back)

    def test_brigade_act_creates_within_ceiling(self):
        totals = {"done_amount": 300, "acted_amount": 100}
        cursor = FakeCursor(fetchone_results=[totals, {"id": 15}])
        app, connection = brigade_build(cursor)
        result = app.routes[("POST", "/brigade-acts")](
            {"contractId": 7, "totalAmount": 200}, x_company_id="3", x_company_mode="company", current_user={}
        )
        self.assertEqual(result["id"], 15)
        self.assertEqual(result["companyId"], 3)
        self.assertTrue(connection.committed)


if __name__ == "__main__":
    unittest.main()
