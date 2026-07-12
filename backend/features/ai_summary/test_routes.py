import unittest
from datetime import datetime

from fastapi import HTTPException

from backend.features.ai_summary.routes import register_ai_summary_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def _register(self, method, path):
        def decorator(func):
            self.routes[(method, path)] = func
            return func
        return decorator


class FakeCursor:
    def __init__(self, projects=None, summary=None):
        self.projects = list(projects or [])
        self.summary = summary
        self.calls = []
        self.current = None
        self.closed = False

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.calls.append((compact, tuple(params)))
        if "FROM projects" in compact:
            self.current = list(self.projects)
        elif compact.startswith("SELECT payload_hash"):
            self.current = self.summary
        else:
            self.current = None

    def fetchall(self):
        return list(self.current or [])

    def fetchone(self):
        return self.current

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, **_kwargs):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def actor(company_id=4, role="директор", assigned_projects=None):
    return {"companyId": company_id, "role": role, "assignedProjects": assigned_projects or []}


class AiSummaryRouteTests(unittest.TestCase):
    def build_app(self, *, cursor, actors=None, mode="company", context_error=None):
        app = FakeApp()
        connection = FakeConnection(cursor)
        selected_actors = list(actors or [actor()])

        def resolve_context(_cur, _user, _requested, action_mode, **kwargs):
            if context_error:
                raise context_error
            return {
                "mode": mode,
                "companyId": selected_actors[0].get("companyId") if mode == "company" else None,
                "actionMode": action_mode,
                "headers": kwargs,
                "actors": selected_actors,
            }

        register_ai_summary_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: {},
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, context: context["actors"],
            "project_document_roles": ("директор", "прораб", "мастер"),
            "full_view_roles": ("директор",),
        })
        return app, connection

    def test_get_reads_summary_by_stored_company_and_project_ids(self):
        cursor = FakeCursor(
            projects=[{"id": 10, "company_id": 4, "name": "Объект A "}],
            summary={"payload_hash": "hash", "summary": "Итог", "updated_at": datetime(2026, 7, 12, 10, 0)},
        )
        app, connection = self.build_app(cursor=cursor)
        result = app.routes[("GET", "/project-ai-summary/{project_name}")](
            "Объект A", x_company_id="4", x_company_mode="company", current_user={"role": "директор"}
        )
        self.assertEqual(result["payloadHash"], "hash")
        self.assertEqual(cursor.calls[1][1], (4, 10))
        self.assertNotIn("project_name=%s", cursor.calls[1][0])
        self.assertFalse(connection.committed)

    def test_get_rejects_all_companies_before_project_query(self):
        cursor = FakeCursor()
        app, _connection = self.build_app(cursor=cursor, mode="all_companies", actors=[actor(4), actor(8)])
        with self.assertRaises(HTTPException) as caught:
            app.routes[("GET", "/project-ai-summary/{project_name}")](
                "Объект A", x_company_id=None, x_company_mode="all_companies", current_user={"role": "директор"}
            )
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(cursor.calls, [])

    def test_effective_company_role_is_enforced(self):
        cursor = FakeCursor()
        app, _connection = self.build_app(cursor=cursor, actors=[actor(4, "поставщик")])
        with self.assertRaises(HTTPException) as caught:
            app.routes[("GET", "/project-ai-summary/{project_name}")](
                "Объект A", x_company_id="4", x_company_mode="company", current_user={"role": "директор"}
            )
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(cursor.calls, [])

    def test_duplicate_trimmed_project_names_fail_closed(self):
        cursor = FakeCursor(projects=[
            {"id": 10, "company_id": 4, "name": "Объект A"},
            {"id": 11, "company_id": 4, "name": "Объект A "},
        ])
        app, _connection = self.build_app(cursor=cursor)
        with self.assertRaises(HTTPException) as caught:
            app.routes[("GET", "/project-ai-summary/{project_name}")](
                "Объект A", x_company_id="4", x_company_mode="company", current_user={"role": "директор"}
            )
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(len(cursor.calls), 1)

    def test_assigned_role_cannot_open_unassigned_project(self):
        cursor = FakeCursor(projects=[{"id": 10, "company_id": 4, "name": "Объект A"}])
        app, _connection = self.build_app(cursor=cursor, actors=[actor(4, "мастер", ["Объект B"])])
        with self.assertRaises(HTTPException) as caught:
            app.routes[("GET", "/project-ai-summary/{project_name}")](
                "Объект A", x_company_id="4", x_company_mode="company", current_user={"role": "директор"}
            )
        self.assertEqual(caught.exception.status_code, 403)

    def test_post_upserts_by_stored_owner_and_commits(self):
        cursor = FakeCursor(projects=[{"id": 10, "company_id": 4, "name": "Объект A "}])
        app, connection = self.build_app(cursor=cursor)
        result = app.routes[("POST", "/project-ai-summary")](
            {"projectName": "Объект A", "payloadHash": "new", "summary": "Сводка"},
            x_company_id="4", x_company_mode="company", current_user={"role": "директор"},
        )
        self.assertEqual(result, {"ok": True})
        self.assertIn("FOR UPDATE", cursor.calls[0][0])
        self.assertIn("ON CONFLICT (company_id,project_id)", cursor.calls[1][0])
        self.assertEqual(cursor.calls[1][1], ("Объект A ", 4, 10, "new", "Сводка"))
        self.assertTrue(connection.committed)

    def test_post_rejects_all_companies_before_write(self):
        cursor = FakeCursor()
        app, connection = self.build_app(
            cursor=cursor,
            context_error=HTTPException(status_code=400, detail="Для изменения данных выберите конкретную компанию"),
        )
        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/project-ai-summary")](
                {"projectName": "Объект A"}, x_company_id=None, x_company_mode="all_companies", current_user={"role": "директор"}
            )
        self.assertEqual(caught.exception.status_code, 400)
        self.assertTrue(connection.rolled_back)
        self.assertEqual(cursor.calls, [])


if __name__ == "__main__":
    unittest.main()
