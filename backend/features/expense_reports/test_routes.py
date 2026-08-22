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
    def __init__(self, effects=(), rows=(), fetchone_results=()):
        self.effects = list(effects)
        self.current = {}
        self.rows = list(rows)
        self.fetchone_results = list(fetchone_results)
        self.calls = []
        self.rowcount = -1
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params or ())))
        self.current = self.effects.pop(0) if self.effects else {}
        if self.current.get("error"):
            raise self.current["error"]
        self.rowcount = self.current.get("rowcount", -1)

    def fetchall(self):
        return list(self.current.get("rows", self.rows))

    def fetchone(self):
        if "row" in self.current:
            return self.current["row"]
        return self.fetchone_results.pop(0) if self.fetchone_results else None

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0
        self.rollbacks = 0
        self.autocommit = True
        self.closed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def reports_build(cursor, context=None, actors=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    selected_context = context or {"mode": "company", "companyId": 4}
    selected_actors = actors if actors is not None else [
        {"companyId": 4, "role": "директор", "name": "Системный директор"}
    ]

    def resolve_context(_cur, _user, _project, _action, **_headers):
        return selected_context

    register_expense_reports_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: None,
        "resolve_work_company_context": resolve_context,
        "effective_company_actors": lambda _user, _context: selected_actors,
        "finance_roles": ("директор",),
    })
    return app, connection


def report_call(handler, *args, **kwargs):
    return handler(
        *args,
        x_company_id="4",
        x_company_mode="company",
        current_user={"id": 9, "name": "Подмена из пользователя"},
        **kwargs,
    )


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
        row = (1, 5, "Мастер", "Объект", 19, "Авансовый отчёт", "цель", 1000, 800, 700, 100,
               '[{"name":"бензин"}]', "", None, None, "На утверждении", "", None, "2026-07-28")
        cursor = FakeCursor(effects=[{"rows": [row]}])
        app, conn = reports_build(cursor)
        out = report_call(
            app.routes[("GET", "/expense-reports")],
            employee_id=None,
            project_name=None,
        )
        self.assertEqual(out[0]["items"][0]["name"], "бензин")
        self.assertEqual(out[0]["balance"], 100.0)
        self.assertEqual(out[0]["projectId"], 19)
        sql, params = cursor.calls[-1]
        self.assertIn("company_id=%s", sql)
        self.assertIn("company_scope_verified IS TRUE", sql)
        self.assertEqual(params, (4,))
        self.assertTrue(conn.closed)

    def test_report_create_resolves_project_staff_and_ignores_forged_names(self):
        cursor = FakeCursor(effects=[
            {"rows": [{"id": 19, "name": "Точный объект"}]},
            {"row": {"id": 100, "name": "Точный сотрудник"}},
            {"row": {"id": 44}},
        ])
        app, conn = reports_build(cursor)
        result = report_call(app.routes[("POST", "/expense-reports")], data={
            "projectId": 19,
            "employeeId": 100,
            "employeeName": "ПОДМЕНА",
            "projectName": "ПОДМЕНА",
            "issuedAmount": 1000,
            "spentAmount": 300,
            "balance": -999,
            "approvedBy": "ПОДМЕНА",
            "purpose": "Материалы",
        })
        self.assertEqual(result, {"id": 44, "ok": True})
        self.assertEqual(conn.commits, 1)
        project_sql, project_params = cursor.calls[0]
        staff_sql, staff_params = cursor.calls[1]
        insert_sql, insert_params = cursor.calls[2]
        self.assertIn("FOR SHARE", project_sql)
        self.assertEqual(project_params, (19, 4))
        self.assertIn("company_scope_verified IS TRUE", staff_sql)
        self.assertIn("FOR SHARE", staff_sql)
        self.assertEqual(staff_params, (100, 4))
        self.assertIn("company_id", insert_sql)
        self.assertIn("project_id", insert_sql)
        self.assertIn("company_scope_verified", insert_sql)
        self.assertIn("Точный сотрудник", insert_params)
        self.assertIn("Точный объект", insert_params)
        self.assertNotIn("ПОДМЕНА", insert_params)
        self.assertIn(700, insert_params)

    def test_report_create_rejects_foreign_project_and_rolls_back(self):
        cursor = FakeCursor(effects=[{"rows": []}])
        app, conn = reports_build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            report_call(app.routes[("POST", "/expense-reports")], data={
                "projectId": 20,
                "employeeId": 100,
                "issuedAmount": 100,
            })
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(conn.commits, 0)
        self.assertEqual(conn.rollbacks, 1)

    def test_report_update_locks_verified_owner_and_derives_approval_actor(self):
        cursor = FakeCursor(effects=[
            {"row": {
                "id": 4,
                "company_id": 4,
                "project_id": 19,
                "project_name": "Точный объект",
                "status": "На утверждении",
                "purpose": "цель",
                "issued_amount": 1000,
            }},
            {"rowcount": 1},
        ])
        app, conn = reports_build(cursor)
        result = report_call(app.routes[("PUT", "/expense-reports/{id}")], id=4, data={
            "status": "Утверждён",
            "approvedBy": "ПОДМЕНА",
            "approvedAt": "2000-01-01",
            "spentAmount": 400,
            "balance": -1,
        })
        self.assertEqual(result, {"ok": True})
        lookup_sql, lookup_params = cursor.calls[0]
        update_sql, update_params = cursor.calls[1]
        self.assertIn("company_id=%s", lookup_sql)
        self.assertIn("company_scope_verified IS TRUE", lookup_sql)
        self.assertIn("FOR UPDATE", lookup_sql)
        self.assertEqual(lookup_params, (4, 4))
        self.assertIn("company_id=%s", update_sql)
        self.assertIn("company_scope_verified IS TRUE", update_sql)
        self.assertIn("Системный директор", update_params)
        self.assertNotIn("ПОДМЕНА", update_params)
        self.assertIn(600, update_params)
        self.assertEqual(conn.commits, 1)

    def test_report_cancel_is_soft_and_idempotent(self):
        row = {"id": 4, "company_id": 4, "project_id": 19,
               "project_name": "Объект", "status": "На утверждении",
               "purpose": "цель", "issued_amount": 1000}
        cursor = FakeCursor(effects=[{"row": row}, {"rowcount": 1}])
        app, connection = reports_build(cursor)
        result = report_call(app.routes[("DELETE", "/expense-reports/{id}")], id=4)
        self.assertEqual(result, {"ok": True, "cancelled": True})
        update = [c for c in cursor.calls if c[0].startswith("UPDATE public.expense_reports")][0]
        self.assertEqual(update[1][0], "Аннулирован")
        self.assertIn("Аннулировано без физического удаления", update[1][1])
        self.assertIn("Системный директор", update[1])
        self.assertIn("company_id=%s", update[0])
        already = FakeCursor(effects=[{"row": {**row, "status": "Аннулирован"}}])
        app2, conn2 = reports_build(already)
        result2 = report_call(app2.routes[("DELETE", "/expense-reports/{id}")], id=4)
        self.assertTrue(result2["alreadyCancelled"])
        self.assertEqual(conn2.commits, 0)
        self.assertEqual(conn2.rollbacks, 1)

    def test_aggregate_or_foreign_actor_is_rejected_before_report_read(self):
        aggregate = FakeCursor()
        app, _conn = reports_build(aggregate, context={"mode": "aggregate"})
        with self.assertRaises(HTTPException) as ctx:
            report_call(
                app.routes[("GET", "/expense-reports")],
                employee_id=None,
                project_name=None,
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(len(aggregate.calls), 0)

        foreign = FakeCursor()
        app2, _conn2 = reports_build(
            foreign,
            actors=[{"companyId": 5, "role": "директор", "name": "Чужой"}],
        )
        with self.assertRaises(HTTPException) as ctx2:
            report_call(
                app2.routes[("GET", "/expense-reports")],
                employee_id=None,
                project_name=None,
            )
        self.assertEqual(ctx2.exception.status_code, 409)
        self.assertEqual(len(foreign.calls), 0)

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
