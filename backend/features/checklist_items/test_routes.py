import unittest

from fastapi import HTTPException

from backend.features.checklist_items.routes import register_checklist_items_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def put(self, path):
        return self._register("PUT", path)

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


def build(cursor, access_calls, deny_id=None):
    app = FakeApp()
    connection = FakeConnection(cursor)

    def project_access(user, project):
        access_calls.append(("project", project))
        if deny_id is not None and project == "deny":
            raise HTTPException(status_code=403, detail="Нет доступа")

    def resolve(_cur, user, _requested, action, x_company_id=None, x_company_mode=None):
        return {
            "mode": "company", "companyId": int(x_company_id or 1), "companyIds": [int(x_company_id or 1)],
            "role": "директор", "effectiveRole": "директор", "active": True, "companyActive": True,
        }

    register_checklist_items_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "resolve_work_company_context": resolve,
        "effective_company_actors": lambda user, context: [{**user, "role": "директор", "companyId": context["companyId"], "active": True, "companyActive": True}],
        "can_see_all_company_data": lambda user: user.get("seeAll", True),
        "require_project_access": project_access,
        "project_document_roles": ("директор",),
        "project_write_roles": ("директор",),
        "check_roles": ("директор",),
    })
    return app, connection


class ChecklistItemsRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor(), [])
        for key in [("GET", "/checklist-items/{checklist_id}"), ("POST", "/checklist-items"), ("PUT", "/checklist-items/{id}")]:
            self.assertIn(key, app.routes)

    def test_list_checks_access_and_maps_rows(self):
        calls = []
        cursor = FakeCursor(rows=[(1, 4, "Проверка", True, "Тест", "2026-07-28", 1)])
        app, _conn = build(cursor, calls)
        cursor.row = (4, "Объект", "project", 1, 12)
        rows = app.routes[("GET", "/checklist-items/{checklist_id}")](
            checklist_id=4, _current_user={"role": "директор"}, x_company_id="1", x_company_mode="company",
        )
        self.assertIn("company_id=%s", cursor.calls[0][0])
        self.assertEqual(rows[0]["checklistId"], 4)
        self.assertEqual(rows[0]["checkedBy"], "Тест")

    def test_create_denied_before_insert_for_foreign_checklist(self):
        calls = []
        cursor = FakeCursor()
        app, _conn = build(cursor, calls, deny_id=9)
        with self.assertRaises(HTTPException):
            app.routes[("POST", "/checklist-items")](
                {"checklistId": 9, "name": "x"}, _current_user={"role": "директор"},
                x_company_id="1", x_company_mode="company",
            )
        self.assertTrue(cursor.calls)

    def test_update_toggles_checked_state(self):
        calls = []
        cursor = FakeCursor()
        app, connection = build(cursor, calls)
        cursor.row = (4, "Объект", "project", 1, 12)
        result = app.routes[("PUT", "/checklist-items/{id}")](
            id=3, data={"checked": True, "checkedBy": "Тест"},
            _current_user={"role": "директор"}, x_company_id="1", x_company_mode="company",
        )
        self.assertEqual(result, {"ok": True})
        self.assertTrue(connection.committed)
        self.assertTrue(any("UPDATE checklist_items SET checked=%s" in sql and "company_id=%s" in sql for sql, _params in cursor.calls))

    def test_company_scoped_checklist_items_skip_the_blank_project_check(self):
        calls = []
        cursor = FakeCursor(rows=[(1, 4, "Пункт", False, "", "", 0)])
        app, _conn = build(cursor, calls)
        cursor.row = (4, "", "company", 1, None)
        rows = app.routes[("GET", "/checklist-items/{checklist_id}")](
            checklist_id=4, _current_user={"role": "директор", "seeAll": False},
            x_company_id="1", x_company_mode="company",
        )
        self.assertEqual(rows[0]["name"], "Пункт")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
