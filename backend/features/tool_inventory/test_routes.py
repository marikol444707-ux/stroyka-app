import unittest

from backend.features.tool_inventory.routes import register_tool_inventory_module


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
        def decorator(func):
            self.routes[(method, path)] = func
            return func
        return decorator


class FakeCursor:
    def __init__(self, rows=None, row=None):
        self.rows = list(rows or [])
        self.row = row
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.closed = False

    def cursor(self, **_kwargs):
        return self.fake_cursor

    def close(self):
        self.closed = True


class ToolInventoryRouteTests(unittest.TestCase):
    def build_app(self, cursor):
        app = FakeApp()
        connection = FakeConnection(cursor)
        access_calls = []

        def require_roles(*_roles):
            return lambda: {}

        register_tool_inventory_module(app, {
            "get_db": lambda: connection,
            "require_roles": require_roles,
            "warehouse_roles": ("директор", "прораб", "кладовщик"),
            "project_document_roles": ("директор", "прораб", "мастер"),
            "worker_execution_roles": ("мастер",),
            "can_see_all_company_data": lambda user: user.get("role") == "директор",
            "user_project_names": lambda user: user.get("assignedProjects", []),
            "require_project_access": lambda user, project: access_calls.append(("project", user, project)),
            "require_tool_access": lambda cur, item_id, user: access_calls.append(("tool", cur, item_id, user)),
            "require_inventory_access": lambda cur, item_id, user: access_calls.append(("inventory", cur, item_id, user)),
        })
        return app, connection, access_calls

    def test_registers_original_route_contract(self):
        app, _connection, _access_calls = self.build_app(FakeCursor())
        self.assertEqual(set(app.routes), {
            ("GET", "/tools"),
            ("POST", "/tools"),
            ("PUT", "/tools/{id}"),
            ("DELETE", "/tools/{id}"),
            ("GET", "/tool-history"),
            ("POST", "/tool-history"),
            ("GET", "/inventory"),
            ("POST", "/inventory"),
            ("PUT", "/inventory/{id}"),
            ("DELETE", "/inventory/{id}"),
            ("GET", "/inventory/{id}/items"),
            ("POST", "/inventory-items"),
            ("POST", "/inventory/{id}/items"),
        })

    def test_foreman_tools_query_is_limited_to_assigned_projects(self):
        cursor = FakeCursor(rows=[{"id": 7, "name": "Перфоратор"}])
        app, connection, _access_calls = self.build_app(cursor)
        result = app.routes[("GET", "/tools")](
            current_user={"role": "прораб", "assignedProjects": ["Объект A"]},
        )
        self.assertEqual(result, [{"id": 7, "name": "Перфоратор"}])
        self.assertIn("project = ANY(%s)", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], (["Объект A"], ["Объект A"]))
        self.assertTrue(connection.closed)

    def test_worker_tool_history_is_limited_by_worker_name(self):
        cursor = FakeCursor(rows=[])
        app, _connection, _access_calls = self.build_app(cursor)
        app.routes[("GET", "/tool-history")](current_user={"role": "мастер", "name": "Иван"})
        self.assertIn("WHERE master_name=%s", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], ("Иван",))

    def test_foreman_inventory_create_checks_project_access(self):
        cursor = FakeCursor(row={"id": 3, "project": "Объект A"})
        app, connection, access_calls = self.build_app(cursor)
        model = app.routes[("POST", "/inventory")].__annotations__["inv"](
            project="Объект A", date="2026-07-17", createdBy="Прораб",
        )
        result = app.routes[("POST", "/inventory")](model, _current_user={"role": "прораб"})
        self.assertEqual(result["id"], 3)
        self.assertEqual(access_calls[0][0], "project")
        self.assertEqual(access_calls[0][2], "Объект A")
        self.assertTrue(connection.closed)

    def test_delete_tool_checks_access_and_deletes_history_first(self):
        cursor = FakeCursor()
        app, connection, access_calls = self.build_app(cursor)
        result = app.routes[("DELETE", "/tools/{id}")](9, _current_user={"role": "кладовщик"})
        self.assertEqual(result, {"ok": True})
        self.assertEqual(access_calls[0][0], "tool")
        self.assertIn("DELETE FROM tool_history", cursor.calls[0][0])
        self.assertIn("DELETE FROM tools", cursor.calls[1][0])
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
