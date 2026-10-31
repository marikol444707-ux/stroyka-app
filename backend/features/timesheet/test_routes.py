import unittest
from contextlib import contextmanager
from fastapi import HTTPException

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
    class Scope:
        visible_project_names = staticmethod(lambda actor: None)
        @contextmanager
        def transaction(self, user, request, roles, write=False):
            yield cursor, [{'companyId': 2, 'role': 'директор', 'name': 'Тест'}]
            if write:
                connection.commit()
    register_timesheet_module(app, {
        'record_scope': Scope(), 'get_current_user': lambda: {},
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
        cursor = FakeCursor(fetchone_results=[("Мастер Тест", "Объект"), None])
        audit_calls = []
        app, connection = build(cursor, audit_calls)
        result = app.routes[("POST", "/timesheet")](
            TimesheetModel(staffId=5, day="2026-07-28"), request=None, current_user={"name": "Тест", "role": "директор"}
        )
        self.assertEqual(result, {"ok": True})
        self.assertTrue(connection.committed)
        self.assertIn("INSERT INTO timesheet", cursor.calls[2][0])
        self.assertEqual(audit_calls[0][2], "timesheet_add")
        self.assertIn("Мастер Тест", audit_calls[0][5])

    def test_toggle_removes_existing_day(self):
        cursor = FakeCursor(fetchone_results=[("Мастер Тест", "Объект"), (9,)])
        audit_calls = []
        app, _conn = build(cursor, audit_calls)
        app.routes[("POST", "/timesheet")](
            TimesheetModel(staffId=5, day="2026-07-28"), request=None, current_user={"name": "Тест", "role": "директор"}
        )
        self.assertIn("DELETE FROM timesheet", cursor.calls[2][0])
        self.assertEqual(audit_calls[0][2], "timesheet_remove")

    def test_staff_days_listing(self):
        app, _conn = build(FakeCursor(rows=[("2026-07-27",), ("2026-07-28",)], fetchone_results=[(5,)]), [])
        result = app.routes[("GET", "/timesheet/{staff_id}")](staff_id=5, request=None, current_user={})
        self.assertEqual(result, {"days": ["2026-07-27", "2026-07-28"]})

    def test_missing_owned_staff_does_not_toggle(self):
        cursor = FakeCursor()
        app, connection = build(cursor, [])
        with self.assertRaises(HTTPException) as error:
            app.routes[('POST', '/timesheet')](TimesheetModel(staffId=5, day='2026-07-28'), request=None, current_user={})
        self.assertEqual(error.exception.status_code, 404)
        self.assertFalse(connection.committed)
        self.assertEqual(len(cursor.calls), 1)
        self.assertIn('s.company_id=%s', cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], (5, 2))


if __name__ == "__main__":
    unittest.main()
