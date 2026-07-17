import unittest

from backend.features.warranty_defects.routes import register_warranty_defects_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def _route(self, method, path):
        def decorator(func):
            self.routes[(method, path)] = func
            return func

        return decorator

    def get(self, path):
        return self._route("GET", path)

    def post(self, path):
        return self._route("POST", path)

    def put(self, path):
        return self._route("PUT", path)

    def delete(self, path):
        return self._route("DELETE", path)


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
        self.commits = 0
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


class WarrantyDefectRouteTests(unittest.TestCase):
    def build_app(self, cursor, visible_projects=None, user_projects=None):
        app = FakeApp()
        connection = FakeConnection(cursor)
        access_checks = []
        row_access_checks = []

        def require_roles(*_roles):
            return lambda: {}

        register_warranty_defects_module(app, {
            "get_db": lambda: connection,
            "require_roles": require_roles,
            "project_document_roles": ("директор", "прораб"),
            "project_document_write_roles": ("директор",),
            "leadership_roles": ("директор", "зам_директора"),
            "require_project_access": lambda user, project: access_checks.append((user, project)),
            "require_row_project_access": lambda cur, table, row_id, user, column: row_access_checks.append(
                (cur, table, row_id, user, column)
            ),
            "visible_project_names": lambda _user: visible_projects,
            "user_project_names": lambda _user: list(user_projects or []),
        })
        return app, connection, access_checks, row_access_checks

    def test_registers_original_route_contract(self):
        app, _connection, _access, _row_access = self.build_app(FakeCursor())
        self.assertEqual(set(app.routes), {
            ("GET", "/warranty-defects"),
            ("POST", "/warranty-defects"),
            ("PUT", "/warranty-defects/{id}"),
            ("DELETE", "/warranty-defects/{id}"),
        })

    def test_list_for_explicit_project_keeps_access_check_and_response_shape(self):
        cursor = FakeCursor(rows=[(
            7, "Объект", "Трещина", "2026-07-17", "Заказчик", "+7000",
            "Открыт", "Прораб", "", None, "photo.jpg", "Высокая", "2026-07-17",
        )])
        app, connection, access_checks, _row_access = self.build_app(cursor)
        user = {"role": "директор"}
        result = app.routes[("GET", "/warranty-defects")]("Объект", current_user=user)
        self.assertEqual(access_checks, [(user, "Объект")])
        self.assertIn("WHERE project_name=%s", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], ("Объект",))
        self.assertEqual(result[0]["description"], "Трещина")
        self.assertEqual(result[0]["projectName"], "Объект")
        self.assertTrue(connection.closed)

    def test_list_scopes_restricted_user_to_visible_projects(self):
        cursor = FakeCursor(rows=[])
        app, connection, _access, _row_access = self.build_app(
            cursor,
            visible_projects=["Объект"],
            user_projects=["Объект"],
        )
        result = app.routes[("GET", "/warranty-defects")](None, current_user={"role": "прораб"})
        self.assertEqual(result, [])
        self.assertIn("project_name = ANY(%s)", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], (["Объект"],))
        self.assertTrue(connection.closed)

    def test_create_keeps_project_access_and_insert_contract(self):
        cursor = FakeCursor(row=(9,))
        app, connection, access_checks, _row_access = self.build_app(cursor)
        user = {"role": "директор"}
        result = app.routes[("POST", "/warranty-defects")](
            {"projectName": "Объект", "description": "Протечка"},
            current_user=user,
        )
        self.assertEqual(access_checks, [(user, "Объект")])
        self.assertIn("INSERT INTO warranty_defects", cursor.calls[0][0])
        self.assertEqual(result, {"id": 9, "ok": True})
        self.assertEqual(connection.commits, 1)

    def test_update_keeps_row_access_and_partial_field_mapping(self):
        cursor = FakeCursor()
        app, connection, _access, row_access_checks = self.build_app(cursor)
        user = {"role": "директор"}
        result = app.routes[("PUT", "/warranty-defects/{id}")](
            11,
            {"status": "Закрыт", "fixedAt": ""},
            current_user=user,
        )
        self.assertEqual(row_access_checks[0][1:], ("warranty_defects", 11, user, "project_name"))
        self.assertIn("UPDATE warranty_defects SET status=%s, fixed_at=%s WHERE id=%s", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], ("Закрыт", None, 11))
        self.assertEqual(result, {"ok": True})
        self.assertEqual(connection.commits, 1)

    def test_delete_keeps_row_access_and_delete_sql(self):
        cursor = FakeCursor()
        app, connection, _access, row_access_checks = self.build_app(cursor)
        user = {"role": "директор"}
        result = app.routes[("DELETE", "/warranty-defects/{id}")](11, current_user=user)
        self.assertEqual(row_access_checks[0][1:], ("warranty_defects", 11, user, "project_name"))
        self.assertEqual(cursor.calls[0][0], "DELETE FROM warranty_defects WHERE id=%s")
        self.assertEqual(cursor.calls[0][1], (11,))
        self.assertEqual(result, {"ok": True})
        self.assertEqual(connection.commits, 1)


if __name__ == "__main__":
    unittest.main()
