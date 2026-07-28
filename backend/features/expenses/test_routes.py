import unittest

from backend.features.expenses.routes import register_expenses_module


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
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def close(self):
        self.closed = True


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
    register_expenses_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "finance_roles": ("директор",),
    })
    return app, connection


class ExpensesRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor())
        self.assertIn(("GET", "/expenses"), app.routes)
        self.assertIn(("POST", "/expenses"), app.routes)

    def test_list_maps_fields_and_filters_by_project(self):
        cursor = FakeCursor(rows=[(1, "Объект", "materials", "150.5", "заметка", "2026-07-28", "Тест", None, "manual", "")])
        app, connection = build(cursor)
        rows = app.routes[("GET", "/expenses")](project="Объект", _current_user={})
        self.assertEqual(rows[0]["amount"], 150.5)
        self.assertEqual(rows[0]["project"], "Объект")
        self.assertEqual(rows[0]["addedBy"], "Тест")
        sql, params = cursor.calls[0]
        self.assertIn("WHERE project=%s", sql)
        self.assertEqual(params, ("Объект",))
        self.assertTrue(connection.closed)

    def test_create_inserts_and_commits(self):
        cursor = FakeCursor()
        app, connection = build(cursor)
        result = app.routes[("POST", "/expenses")](
            {"project": "Объект", "amount": 100, "photoUrl": "u"}, _current_user={}
        )
        self.assertEqual(result, {"ok": True})
        self.assertTrue(connection.committed)
        sql, params = cursor.calls[0]
        self.assertIn("INSERT INTO expenses", sql)
        self.assertEqual(params[0], "Объект")
        self.assertEqual(params[6], "u")


if __name__ == "__main__":
    unittest.main()
