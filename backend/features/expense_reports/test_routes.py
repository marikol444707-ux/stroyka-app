import unittest

from fastapi import HTTPException

from backend.features.expense_reports.routes import register_expense_reports_module
from backend.features.invite_codes.routes import register_invite_codes_module


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
        self.rolled_back = False
        self.autocommit = True

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def reports_build(cursor):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_expense_reports_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "finance_roles": ("директор",),
        "require_project_access": lambda user, project: None,
    })
    return app, connection


def codes_build(cursor):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_invite_codes_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "admin_roles": ("директор",),
        "prepare_user_access_scope": lambda cur, role, project, projects, packages: (projects or [project] if project else [], packages or []),
    })
    return app, connection


class ExpenseReportsAndInviteCodesTest(unittest.TestCase):
    def test_all_urls_registered(self):
        rapp, _r = reports_build(FakeCursor())
        capp, _c = codes_build(FakeCursor())
        for key in [("GET", "/expense-reports"), ("POST", "/expense-reports"),
                    ("PUT", "/expense-reports/{id}"), ("DELETE", "/expense-reports/{id}")]:
            self.assertIn(key, rapp.routes)
        for key in [("GET", "/invite-codes"), ("POST", "/invite-codes"),
                    ("DELETE", "/invite-codes/{id}"), ("GET", "/invite-codes/{code}/info")]:
            self.assertIn(key, capp.routes)

    def test_report_list_parses_items_json(self):
        row = (1, 5, "Мастер", "Объект", "Авансовый отчёт", "цель", 1000, 800, 700, 100,
               '[{"name":"бензин"}]', "", None, None, "На утверждении", "", None, "2026-07-28")
        app, _conn = reports_build(FakeCursor(rows=[row]))
        out = app.routes[("GET", "/expense-reports")](employee_id=None, project_name=None, current_user={})
        self.assertEqual(out[0]["items"][0]["name"], "бензин")
        self.assertEqual(out[0]["balance"], 100.0)

    def test_report_cancel_is_soft_and_idempotent(self):
        cursor = FakeCursor(fetchone_results=[("Объект", "На утверждении", "цель")])
        app, connection = reports_build(cursor)
        result = app.routes[("DELETE", "/expense-reports/{id}")](id=4, _current_user={"name": "Тест"})
        self.assertEqual(result, {"ok": True, "cancelled": True})
        update = [c for c in cursor.calls if c[0].startswith("UPDATE expense_reports")][0]
        self.assertEqual(update[1][0], "Аннулирован")
        self.assertIn("Аннулировано без физического удаления", update[1][1])
        already = FakeCursor(fetchone_results=[("Объект", "Аннулирован", "цель")])
        app2, conn2 = reports_build(already)
        result2 = app2.routes[("DELETE", "/expense-reports/{id}")](id=4, _current_user={"name": "Тест"})
        self.assertTrue(result2["alreadyCancelled"])
        self.assertFalse(conn2.committed)

    def test_invite_code_requires_role(self):
        app, _conn = codes_build(FakeCursor())
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/invite-codes")]({}, _current_user={})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_invite_code_resolves_platform_account_from_company(self):
        cursor = FakeCursor(fetchone_results=[{"platform_account_id": 77}, {"id": 1, "code": "ABC", "role": "мастер"}])
        app, _conn = codes_build(cursor)
        result = app.routes[("POST", "/invite-codes")](
            {"role": "мастер", "companyId": "3", "projectName": "Объект"}, _current_user={}
        )
        self.assertEqual(result["code"], "ABC")
        insert = [c for c in cursor.calls if c[0].startswith("INSERT INTO invite_codes")][0]
        self.assertEqual(insert[1][10], 3)
        self.assertEqual(insert[1][11], 77)

    def test_invite_info_rejects_used_code(self):
        cursor = FakeCursor(fetchone_results=[{"used": True, "role": "мастер"}])
        app, _conn = codes_build(cursor)
        result = app.routes[("GET", "/invite-codes/{code}/info")](code="abc")
        self.assertFalse(result["valid"])
        self.assertIn("использован", result["error"])
        lookup = cursor.calls[0]
        self.assertEqual(lookup[1], ("ABC",))


if __name__ == "__main__":
    unittest.main()
