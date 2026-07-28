import unittest

from backend.features.accountable_payments.routes import register_accountable_payments_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator


class FakeCursor:
    def __init__(self, rows=(), row=None):
        self.rows = list(rows)
        self.row = row
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.row

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.closed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def build(cursor):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_accountable_payments_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "finance_roles": ("директор",),
    })
    return app, connection


class AccountablePaymentsRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/accountable-payments"), ("POST", "/accountable-payments"),
                    ("GET", "/accountable-expenses"), ("POST", "/accountable-expenses")]:
            self.assertIn(key, app.routes)

    def test_payment_list_maps_fields(self):
        cursor = FakeCursor(rows=[(1, "Объект", "Мастер", "5000", "Наличные", "материалы", "2026-07-28", "Тест", None, "1500")])
        app, _conn = build(cursor)
        rows = app.routes[("GET", "/accountable-payments")](project_name="Объект", _current_user={})
        self.assertEqual(rows[0]["amount"], 5000.0)
        self.assertEqual(rows[0]["status"], "Открыт")
        self.assertEqual(rows[0]["spentAmount"], 1500.0)
        self.assertIn("WHERE project_name=%s", cursor.calls[0][0])

    def test_expense_create_updates_spent_amount(self):
        cursor = FakeCursor(row=(9,))
        app, connection = build(cursor)
        result = app.routes[("POST", "/accountable-expenses")](
            {"paymentId": 4, "amount": 300, "description": "бензин"}, _current_user={}
        )
        self.assertEqual(result, {"ok": True})
        self.assertTrue(connection.committed)
        self.assertIn("INSERT INTO accountable_expenses", cursor.calls[0][0])
        update_sql, update_params = cursor.calls[1]
        self.assertIn("SET spent_amount=spent_amount+%s", update_sql)
        self.assertEqual(update_params, (300, 4))

    def test_payment_create_returns_new_id(self):
        cursor = FakeCursor(row=(7,))
        app, connection = build(cursor)
        result = app.routes[("POST", "/accountable-payments")](
            {"projectName": "Объект", "givenTo": "Мастер", "amount": 5000}, _current_user={}
        )
        self.assertEqual(result, {"id": 7, "ok": True})
        self.assertTrue(connection.committed)


if __name__ == "__main__":
    unittest.main()
