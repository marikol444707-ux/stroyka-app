import unittest

from fastapi import HTTPException

from backend.features.projects.routes import ProjectModel, register_projects_module


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


def build(cursor, actors=None, audit_calls=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    audit_log = audit_calls if audit_calls is not None else []
    actor_list = actors if actors is not None else [{"companyId": 3, "role": "директор", "name": "Тест"}]
    register_projects_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "require_roles": lambda *roles: (lambda: None),
        "leadership_roles": ("директор",),
        "project_card_write_roles": ("директор",),
        "worker_execution_roles": ("мастер",),
        "project_public_select": 'COALESCE(public_show_on_site,false) as "publicShowOnSite"',
        "project_access_helpers": lambda: (
            lambda actors, roles: ("p.company_id=%s", [3]),
            lambda actor, company_id: None,
            lambda actors, roles: actor_list[0],
        ),
        "resolve_work_company_context": lambda cur, user, claimed, mode, **kw: {"mode": "company", "companyId": 3},
        "effective_company_actors": lambda user, ctx: list(actor_list),
        "require_project_access": lambda user, project: None,
        "log_audit": lambda **kw: audit_log.append(kw),
    })
    return app, connection


ROW = {"id": 1, "companyId": 3, "name": "Объект", "client": "Клиент", "status": "В работе",
       "budget": 1000000, "deadline": "", "progress": 40, "tasks": [], "pricelistId": 5,
       "floors": 2, "liters": "", "warrantyStartDate": "2026-01-01", "warrantyEndDate": "2027-01-01",
       "warrantyContact": "+7", "archived": False, "archivedAt": None, "publicShowOnSite": False}


class ProjectsRoutesTest(unittest.TestCase):
    def test_all_urls_registered(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/projects"), ("POST", "/projects"),
                    ("PUT", "/projects/{id}"), ("DELETE", "/projects/{id}")]:
            self.assertIn(key, app.routes)

    def test_worker_sees_no_budget_or_warranty(self):
        cursor = FakeCursor(rows=[dict(ROW)])
        app, _conn = build(cursor, actors=[{"companyId": 3, "role": "мастер"}])
        result = app.routes[("GET", "/projects")](
            x_company_id="3", x_company_mode="company", current_user={"role": "мастер"}
        )
        self.assertEqual(result[0]["budget"], 0)
        self.assertIsNone(result[0]["pricelistId"])
        self.assertEqual(result[0]["warrantyContact"], "")

    def test_director_sees_full_card(self):
        cursor = FakeCursor(rows=[dict(ROW)])
        app, _conn = build(cursor)
        result = app.routes[("GET", "/projects")](
            x_company_id="3", x_company_mode="company", current_user={"role": "директор"}
        )
        self.assertEqual(result[0]["budget"], 1000000)

    def test_archive_via_update_is_forbidden(self):
        app, _conn = build(FakeCursor())
        for payload in ({"archived": True}, {"status": "Завершён"}):
            with self.assertRaises(HTTPException) as ctx:
                app.routes[("PUT", "/projects/{id}")](
                    id=1, data=dict(payload), x_company_id="3", x_company_mode="company", current_user={}
                )
            self.assertEqual(ctx.exception.status_code, 403)

    def test_create_binds_actor_company_and_audits(self):
        audit = []
        cursor = FakeCursor(fetchone_results=[dict(ROW)])
        app, connection = build(cursor, audit_calls=audit)
        result = app.routes[("POST", "/projects")](
            ProjectModel(name="Объект"), x_company_id="3", x_company_mode="company", current_user={}
        )
        self.assertEqual(result["companyId"], 3)
        insert = cursor.calls[0]
        self.assertEqual(insert[1][0], 3)
        self.assertEqual(audit[0]["entity_type"], "project")
        self.assertTrue(connection.committed)

    def test_delete_is_disabled(self):
        app, _conn = build(FakeCursor())
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("DELETE", "/projects/{id}")](id=1, current_user={})
        self.assertEqual(ctx.exception.status_code, 405)


if __name__ == "__main__":
    unittest.main()
