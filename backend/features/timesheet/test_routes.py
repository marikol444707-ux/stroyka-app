import unittest

from backend.features.timesheet.routes import TimesheetModel, register_timesheet_module


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
        self.closed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def build(cursor, audit_calls):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_timesheet_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "staff_view_roles": ("директор",),
        "staff_manage_roles": ("директор",),
        "log_audit": lambda *args: audit_calls.append(args),
    })
    return app, connection


class TimesheetRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor(), [])
        for key in [("GET", "/timesheet/{staff_id}"), ("POST", "/timesheet"), ("GET", "/timesheet")]:
            self.assertIn(key, app.routes)

    def test_toggle_adds_day_and_writes_audit(self):
        cursor = FakeCursor(fetchone_results=[None, ("Мастер Тест", "Объект")])
        audit_calls = []
        app, connection = build(cursor, audit_calls)
        result = app.routes[("POST", "/timesheet")](
            TimesheetModel(staffId=5, day="2026-07-28"), _current_user={"name": "Тест", "role": "директор"}
        )
        self.assertEqual(result, {"ok": True})
        self.assertTrue(connection.committed)
        self.assertIn("INSERT INTO timesheet", cursor.calls[1][0])
        self.assertEqual(audit_calls[0][2], "timesheet_add")
        self.assertIn("Мастер Тест", audit_calls[0][5])

    def test_toggle_removes_existing_day(self):
        cursor = FakeCursor(fetchone_results=[(9,), ("Мастер Тест", "Объект")])
        audit_calls = []
        app, _conn = build(cursor, audit_calls)
        app.routes[("POST", "/timesheet")](
            TimesheetModel(staffId=5, day="2026-07-28"), _current_user={"name": "Тест", "role": "директор"}
        )
        self.assertIn("DELETE FROM timesheet", cursor.calls[1][0])
        self.assertEqual(audit_calls[0][2], "timesheet_remove")

    def test_staff_days_listing(self):
        app, _conn = build(FakeCursor(rows=[{"day": "2026-07-27"}, {"day": "2026-07-28"}]), [])
        result = app.routes[("GET", "/timesheet/{staff_id}")](staff_id=5, _current_user={})
        self.assertEqual(result, {"days": ["2026-07-27", "2026-07-28"]})


if __name__ == "__main__":
    unittest.main()
