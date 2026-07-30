import unittest

from backend.features.warranty_defects.routes import register_warranty_defects_module


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

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def build(cursor, visible=None, projects=("Объект",)):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_warranty_defects_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "read_roles": ("директор",),
        "write_roles": ("директор",),
        "leadership_roles": ("директор",),
        "visible_project_names": lambda user: visible,
        "user_project_names": lambda user: list(projects),
        "require_project_access": lambda user, project: None,
        "require_row_project_access": lambda cur, table, row_id, user, col: None,
    })
    return app, connection


class WarrantyDefectsTest(unittest.TestCase):
    def test_all_urls_registered(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/warranty-defects"), ("POST", "/warranty-defects"),
                    ("PUT", "/warranty-defects/{id}"), ("DELETE", "/warranty-defects/{id}")]:
            self.assertIn(key, app.routes)

    def test_list_scopes_to_projects_when_limited(self):
        cursor = FakeCursor(rows=[])
        app, _conn = build(cursor, visible=["Объект"])
        app.routes[("GET", "/warranty-defects")](project_name=None, current_user={})
        self.assertIn("WHERE project_name = ANY(%s)", cursor.calls[0][0])

    def test_update_normalizes_empty_fixed_at(self):
        cursor = FakeCursor()
        app, connection = build(cursor)
        result = app.routes[("PUT", "/warranty-defects/{id}")](
            id=4, data={"fixedAt": "", "status": "Устранён"}, current_user={}
        )
        self.assertEqual(result, {"ok": True})
        sql, vals = cursor.calls[0]
        self.assertIn("fixed_at=%s", sql)
        self.assertIsNone(vals[list(vals).index(None)])
        self.assertTrue(connection.committed)

    def test_create_returns_new_id(self):
        cursor = FakeCursor(fetchone_results=[(7,)])
        app, _conn = build(cursor)
        result = app.routes[("POST", "/warranty-defects")](
            {"projectName": "Объект", "description": "Трещина"}, current_user={}
        )
        self.assertEqual(result, {"id": 7, "ok": True})


if __name__ == "__main__":
    unittest.main()
