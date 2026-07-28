import unittest

from fastapi import HTTPException

from backend.features.brigade_access.payment_routes import register_brigade_payments_module


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


CONTRACT = {"id": 7, "companyId": 3, "projectName": "Объект", "brigadeName": "Бригада А", "actScanUrl": "/scan.pdf"}


def build(cursor, scope=("bc.company_id=%s", [3]), contract=None, resolve_error=None):
    app = FakeApp()
    connection = FakeConnection(cursor)

    def brigade_contract_read_scope(conn, user, roles, **kw):
        sql, params = scope
        return sql, list(params), []

    def resolve_brigade_contract_actor(cur, user, contract_id, roles, **kw):
        if resolve_error:
            raise resolve_error
        return dict(contract or CONTRACT), {"name": "Тест"}, None

    register_brigade_payments_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "finance_roles": ("директор",),
        "worker_execution_roles": ("мастер",),
        "brigade_contract_read_scope": brigade_contract_read_scope,
        "resolve_brigade_contract_actor": resolve_brigade_contract_actor,
        "row_get": row_get,
    })
    return app, connection


class BrigadePaymentRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/brigade-payments"), ("POST", "/brigade-payments"), ("DELETE", "/brigade-payments/{id}")]:
            self.assertIn(key, app.routes)

    def test_read_scope_false_returns_empty_without_query(self):
        cursor = FakeCursor()
        app, _conn = build(cursor, scope=("FALSE", []))
        result = app.routes[("GET", "/brigade-payments")](
            contract_id=None, x_company_id=None, x_company_mode=None, _current_user={}
        )
        self.assertEqual(result, [])
        self.assertEqual(cursor.calls, [])

    def test_payment_blocked_without_signed_act_scan(self):
        contract = dict(CONTRACT, actScanUrl="")
        cursor = FakeCursor(fetchone_results=[None, None])
        app, connection = build(cursor, contract=contract)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/brigade-payments")](
                {"contractId": 7, "amount": 100}, x_company_id="3", x_company_mode="company", _current_user={}
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("скан", ctx.exception.detail)
        self.assertTrue(connection.rolled_back)

    def test_payment_cannot_exceed_unpaid_done_amount(self):
        amounts = {"done_amount": 100, "paid_amount": 50}
        cursor = FakeCursor(fetchone_results=[None, None, amounts])
        app, connection = build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/brigade-payments")](
                {"contractId": 7, "amount": 200}, x_company_id="3", x_company_mode="company", _current_user={}
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("50.00", ctx.exception.detail)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_successful_payment_mirrors_into_project_payments(self):
        amounts = {"done_amount": 500, "paid_amount": 0}
        cursor = FakeCursor(fetchone_results=[None, None, amounts, (11,), (22,)])
        app, connection = build(cursor)
        result = app.routes[("POST", "/brigade-payments")](
            {"contractId": 7, "amount": 300, "paidBy": "Тест"},
            x_company_id="3", x_company_mode="company", _current_user={},
        )
        self.assertEqual(result, {"ok": True, "id": 11, "companyId": 3, "projectPaymentId": 22})
        self.assertTrue(connection.committed)
        inserts = [c[0] for c in cursor.calls if c[0].startswith("INSERT INTO")]
        self.assertEqual(len(inserts), 2)
        self.assertIn("INSERT INTO project_payments", inserts[1])

    def test_delete_missing_payment_is_noop_ok(self):
        cursor = FakeCursor(fetchone_results=[None])
        app, connection = build(cursor)
        result = app.routes[("DELETE", "/brigade-payments/{id}")](
            id=99, x_company_id=None, x_company_mode=None, _current_user={}
        )
        self.assertEqual(result, {"ok": True})
        self.assertFalse(connection.committed)


if __name__ == "__main__":
    unittest.main()
