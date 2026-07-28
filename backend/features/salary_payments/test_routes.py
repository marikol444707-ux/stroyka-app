import unittest

from backend.features.salary_payments.routes import register_salary_payments_module


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

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def build(cursor):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_salary_payments_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "finance_roles": ("директор",),
    })
    return app, connection


class SalaryPaymentsRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/salary-payments"), ("POST", "/salary-payments"), ("DELETE", "/salary-payments/{id}")]:
            self.assertIn(key, app.routes)

    def test_list_maps_fields(self):
        cursor = FakeCursor(rows=[(1, 5, "Мастер", "2026-07", "40000", "Тест", "2026-07-28", "", "2026-07-28")])
        app, _conn = build(cursor)
        rows = app.routes[("GET", "/salary-payments")](_current_user={})
        self.assertEqual(rows[0]["amount"], 40000.0)
        self.assertEqual(rows[0]["staffName"], "Мастер")

    def test_create_and_delete_commit(self):
        cursor = FakeCursor(row=(3,))
        app, connection = build(cursor)
        created = app.routes[("POST", "/salary-payments")]({"staffId": 5, "amount": 100}, _current_user={})
        self.assertEqual(created, {"ok": True, "id": 3})
        self.assertTrue(connection.committed)
        deleted = app.routes[("DELETE", "/salary-payments/{id}")](id=3, _current_user={})
        self.assertEqual(deleted, {"ok": True})
        self.assertIn("DELETE FROM salary_payments WHERE id=%s", cursor.calls[-1][0])


if __name__ == "__main__":
    unittest.main()
