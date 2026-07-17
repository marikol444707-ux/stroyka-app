import unittest

from backend.features.timesheet.models import TimesheetModel
from backend.features.timesheet.routes import register_timesheet_module


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


class FakeCursor:
    def __init__(self, rows=None, fetchone_values=None):
        self.rows = list(rows or [])
        self.fetchone_values = list(fetchone_values or [])
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.fetchone_values.pop(0) if self.fetchone_values else None

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.commits = 0
        self.closed = False

    def cursor(self, **_kwargs):
        return self.fake_cursor

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


class TimesheetRouteTests(unittest.TestCase):
    def build_app(self, cursor):
        app = FakeApp()
        connection = FakeConnection(cursor)
        audit_calls = []

        def require_roles(*_roles):
            return lambda: {}

        register_timesheet_module(app, {
            "get_db": lambda: connection,
            "require_roles": require_roles,
            "staff_view_roles": ("директор", "бухгалтер"),
            "staff_manage_roles": ("директор",),
            "log_audit": lambda *args: audit_calls.append(args),
        })
        return app, connection, audit_calls

    def test_registers_original_route_contract(self):
        app, _connection, _audit = self.build_app(FakeCursor())
        self.assertEqual(set(app.routes), {
            ("GET", "/timesheet/{staff_id}"),
            ("POST", "/timesheet"),
            ("GET", "/timesheet"),
        })

    def test_get_staff_timesheet_keeps_days_shape(self):
        cursor = FakeCursor(rows=[{"day": "2026-07-01"}, {"day": "2026-07-02"}])
        app, connection, _audit = self.build_app(cursor)
        result = app.routes[("GET", "/timesheet/{staff_id}")](5, _current_user={"role": "директор"})
        self.assertEqual(result, {"days": ["2026-07-01", "2026-07-02"]})
        self.assertEqual(cursor.calls[0][1], (5,))
        self.assertTrue(connection.closed)

    def test_toggle_adds_missing_day_and_writes_audit(self):
        cursor = FakeCursor(fetchone_values=[None, ("Иванов", "Объект")])
        app, connection, audit_calls = self.build_app(cursor)
        user = {"name": "Директор", "role": "директор"}
        result = app.routes[("POST", "/timesheet")](
            TimesheetModel(staffId=5, day="2026-07-01"),
            _current_user=user,
        )
        self.assertIn("INSERT INTO timesheet", cursor.calls[1][0])
        self.assertEqual(cursor.calls[1][1], (5, "2026-07-01"))
        self.assertEqual(audit_calls[0][2], "timesheet_add")
        self.assertEqual(audit_calls[0][6], "Объект")
        self.assertEqual(connection.commits, 1)
        self.assertEqual(result, {"ok": True})

    def test_toggle_removes_existing_day_and_writes_audit(self):
        cursor = FakeCursor(fetchone_values=[(7,), ("Иванов", "Объект")])
        app, connection, audit_calls = self.build_app(cursor)
        result = app.routes[("POST", "/timesheet")](
            TimesheetModel(staffId=5, day="2026-07-01"),
            _current_user={"name": "Прораб", "role": "прораб"},
        )
        self.assertIn("DELETE FROM timesheet", cursor.calls[1][0])
        self.assertEqual(audit_calls[0][2], "timesheet_remove")
        self.assertEqual(connection.commits, 1)
        self.assertEqual(result, {"ok": True})

    def test_get_all_keeps_list_shape(self):
        cursor = FakeCursor(rows=[(5, "2026-07-01")])
        app, connection, _audit = self.build_app(cursor)
        result = app.routes[("GET", "/timesheet")](_current_user={"role": "директор"})
        self.assertEqual(result, [{"staffId": 5, "day": "2026-07-01"}])
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
