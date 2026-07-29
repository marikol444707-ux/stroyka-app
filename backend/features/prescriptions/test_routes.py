import unittest

from fastapi import HTTPException

from backend.features.prescriptions.routes import register_prescriptions_module
from backend.features.supervisor_acts.routes import register_supervisor_acts_module


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


def deps_for(cursor, visible=None):
    connection = FakeConnection(cursor)
    return connection, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "read_roles": ("директор",),
        "write_roles": ("директор",),
        "worker_execution_roles": ("мастер",),
        "visible_project_names": lambda user: visible,
        "require_project_access": lambda user, project: None,
        "require_row_project_access": lambda cur, table, row_id, user, col: None,
    }


class PrescriptionsAndSupervisorActsTest(unittest.TestCase):
    def test_all_urls_registered(self):
        app = FakeApp()
        _conn, deps = deps_for(FakeCursor())
        register_prescriptions_module(app, deps)
        register_supervisor_acts_module(app, deps)
        for key in [("GET", "/prescriptions"), ("POST", "/prescriptions"),
                    ("PUT", "/prescriptions/{id}"), ("DELETE", "/prescriptions/{id}"),
                    ("GET", "/supervisor-acts"), ("POST", "/supervisor-acts"),
                    ("PUT", "/supervisor-acts/{id}"), ("DELETE", "/supervisor-acts/{id}")]:
            self.assertIn(key, app.routes)

    def test_customer_creation_stamps_own_identity(self):
        cursor = FakeCursor(fetchone_results=[(4,)])
        app = FakeApp()
        _conn, deps = deps_for(cursor)
        register_prescriptions_module(app, deps)
        app.routes[("POST", "/prescriptions")](
            {"projectName": "Объект", "issuedBy": "Чужой", "issuedByRole": "Прораб"},
            current_user={"name": "Клиент Тест", "role": "заказчик"},
        )
        sql, params = cursor.calls[0]
        self.assertEqual(params[2], "Клиент Тест")
        self.assertEqual(params[3], "Заказчик")

    def test_worker_can_only_send_to_review(self):
        cursor = FakeCursor()
        app = FakeApp()
        _conn, deps = deps_for(cursor)
        register_prescriptions_module(app, deps)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("PUT", "/prescriptions/{id}")](
                id=3, data={"status": "Закрыто"}, current_user={"role": "мастер"}
            )
        self.assertEqual(ctx.exception.status_code, 403)
        ok = app.routes[("PUT", "/prescriptions/{id}")](
            id=3, data={"status": "На проверке"}, current_user={"role": "мастер"}
        )
        self.assertEqual(ok, {"ok": True})

    def test_prescription_delete_is_soft(self):
        cursor = FakeCursor()
        app = FakeApp()
        connection, deps = deps_for(cursor)
        register_prescriptions_module(app, deps)
        result = app.routes[("DELETE", "/prescriptions/{id}")](id=3, current_user={})
        self.assertEqual(result, {"ok": True})
        self.assertIn("SET status='Аннулировано'", cursor.calls[0][0])
        self.assertTrue(connection.committed)

    def test_supervisor_act_update_maps_only_known_fields(self):
        cursor = FakeCursor()
        app = FakeApp()
        connection, deps = deps_for(cursor)
        register_supervisor_acts_module(app, deps)
        result = app.routes[("PUT", "/supervisor-acts/{id}")](
            id=5, data={"status": "Закрыт", "hack": "x"}, current_user={}
        )
        self.assertEqual(result, {"ok": True})
        sql, vals = cursor.calls[0]
        self.assertIn("SET status=%s WHERE id=%s", sql)
        self.assertEqual(vals, ("Закрыт", 5))

    def test_supervisor_act_autonumbers_when_missing(self):
        cursor = FakeCursor(fetchone_results=[(6,)])
        app = FakeApp()
        _conn, deps = deps_for(cursor)
        register_supervisor_acts_module(app, deps)
        app.routes[("POST", "/supervisor-acts")](
            {"projectName": "Объект"}, current_user={}
        )
        sql, params = cursor.calls[0]
        self.assertTrue(str(params[1]).startswith("САО-"))


if __name__ == "__main__":
    unittest.main()
