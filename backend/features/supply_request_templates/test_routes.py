import unittest

from fastapi import HTTPException

from backend.features.supply_request_templates.routes import register_supply_request_templates_module


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
    register_supply_request_templates_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "supply_roles": ("снабженец",),
    })
    return app, connection


class SupplyRequestTemplatesRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/supply-request-templates"), ("POST", "/supply-request-templates"),
                    ("DELETE", "/supply-request-templates/{id}")]:
            self.assertIn(key, app.routes)

    def test_list_parses_items_json(self):
        cursor = FakeCursor(rows=[(1, "Черновая", "стены", '[{"materialName":"цемент","quantity":5}]', "Тест", 42, "2026-07-28")])
        app, _conn = build(cursor)
        rows = app.routes[("GET", "/supply-request-templates")](_current_user={})
        self.assertEqual(rows[0]["items"][0]["materialName"], "цемент")
        self.assertEqual(rows[0]["name"], "Черновая")

    def test_create_rejects_empty_items(self):
        app, _conn = build(FakeCursor())
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/supply-request-templates")]({"name": "Пустой", "items": []}, _current_user={})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_create_normalizes_items_and_commits(self):
        cursor = FakeCursor(row=(7,))
        app, connection = build(cursor)
        result = app.routes[("POST", "/supply-request-templates")](
            {"name": "Черновая", "items": [
                {"materialName": "цемент", "quantity": "5", "unit": "мешок"},
                {"materialName": "", "quantity": 3},
            ]},
            _current_user={},
        )
        self.assertEqual(result, {"id": 7, "ok": True})
        self.assertTrue(connection.committed)
        sql, params = cursor.calls[0]
        self.assertIn('"quantity": 5.0', params[2])
        self.assertNotIn('""', params[2])


if __name__ == "__main__":
    unittest.main()
