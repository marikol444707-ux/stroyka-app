import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.features.assignments.routes import register_assignments_module


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
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.current = None
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self.current = self.responses.pop(0) if self.responses else None

    def fetchall(self):
        return list(self.current or [])

    def fetchone(self):
        if isinstance(self.current, list):
            return self.current[0] if self.current else None
        return self.current

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def actor(company_id=4, role="директор", assigned=None):
    return {
        "companyId": company_id,
        "company_id": company_id,
        "role": role,
        "name": "Директор",
        "assignedProjects": assigned or [],
    }


class AssignmentTenantRouteTests(unittest.TestCase):
    def build_app(self, cursor, *, actors=None, mode="company"):
        app = FakeApp()
        conn = FakeConnection(cursor)
        selected = list(actors or [actor()])

        def resolve_context(_cur, _user, _requested, action_mode, **_kwargs):
            return {
                "mode": mode,
                "companyId": selected[0]["companyId"] if selected else None,
                "actionMode": action_mode,
            }

        with patch("backend.features.assignments.routes.ensure_assignments_schema"):
            register_assignments_module(app, {
                "get_db": lambda: conn,
                "get_current_user": lambda: {},
                "resolve_work_company_context": resolve_context,
                "effective_company_actors": lambda _user, _context: selected,
                "require_project_access": lambda _user, _project: None,
                "leadership_roles": ("директор", "зам_директора"),
                "full_view_roles": ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик"),
                "platform_task_roles": ("system_owner", "platform_admin", "platform_support"),
                "assignment_roles": ("директор", "мастер"),
            })
        return app, conn

    def test_list_filters_by_stored_company_owner(self):
        cursor = FakeCursor([[{"id": 20, "projectName": "Объект A"}], []])
        app, _conn = self.build_app(cursor)
        rows = app.routes[("GET", "/assignments")](
            None, None, False, False, "4", "company", {"role": "директор"},
        )
        self.assertEqual(rows[0]["id"], 20)
        self.assertIn("owner_scope='company'", cursor.calls[0][0])
        self.assertIn("company_id=%s", cursor.calls[0][0])
        self.assertNotIn("owner_scope='platform'", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], (4,))

    def test_list_rejects_all_companies_before_query(self):
        cursor = FakeCursor()
        app, _conn = self.build_app(cursor, actors=[actor(4), actor(8)], mode="all_companies")
        with self.assertRaises(HTTPException) as caught:
            app.routes[("GET", "/assignments")](
                None, None, False, False, None, "all_companies", {"role": "директор"},
            )
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(cursor.calls, [])

    def test_worker_list_uses_project_and_assignment_scope(self):
        cursor = FakeCursor([
            [{"id": 10, "company_id": 4, "name": "Объект A"}],
            [{"id": 20, "projectName": "Объект A", "assignedRole": "мастер"}],
            [],
        ])
        app, _conn = self.build_app(cursor, actors=[actor(4, "мастер", ["Объект A"])])
        rows = app.routes[("GET", "/assignments")](
            None, None, False, False, "4", "company", {"role": "директор"},
        )
        self.assertEqual(rows[0]["id"], 20)
        self.assertIn("project_id=ANY(%s)", cursor.calls[1][0])
        self.assertIn("assigned_role = %s", cursor.calls[1][0])
        self.assertIn("мастер", cursor.calls[1][1])

    def test_accept_hides_task_owned_by_another_company(self):
        cursor = FakeCursor([None])
        app, conn = self.build_app(cursor)
        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/ai-tasks/{task_id}/accept")](
                20, {"status": "В работе"}, "4", "company", {"role": "директор"},
            )
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(cursor.calls[0][1], (20, 4))
        self.assertTrue(conn.rolled_back)

    def test_accept_update_and_refetch_keep_complete_owner(self):
        task = {
            "id": 20, "ownerScope": "company", "companyId": 4, "projectId": 10,
            "projectName": "Объект A", "assignedRole": "мастер", "assignedTo": "",
            "createdBy": "Директор", "systemGenerated": False,
        }
        cursor = FakeCursor([
            task,
            [{"id": 10, "company_id": 4, "name": "Объект A"}],
            task,
            None,
            task,
        ])
        app, conn = self.build_app(cursor)
        result = app.routes[("POST", "/ai-tasks/{task_id}/accept")](
            20, {"status": "В работе"}, "4", "company", {"role": "директор", "name": "Директор"},
        )
        self.assertEqual(result["id"], 20)
        self.assertIn("FOR UPDATE", cursor.calls[2][0])
        self.assertIn("owner_scope='company'", cursor.calls[3][0])
        self.assertEqual(cursor.calls[3][1][-3:], (4, 10, 20))
        self.assertIn("owner_scope='company'", cursor.calls[4][0])
        self.assertTrue(conn.committed)

    def test_platform_accept_uses_only_platform_owner(self):
        task = {
            "id": 99, "ownerScope": "platform", "companyId": None, "projectId": None,
            "projectName": "Система", "assignedRole": "директор", "assignedTo": "",
            "createdBy": "system", "systemGenerated": False,
        }
        cursor = FakeCursor([task, task, None, task])
        app, conn = self.build_app(cursor)
        result = app.routes[("POST", "/ai-tasks/{task_id}/accept")](
            99, {"status": "В работе"}, None, None,
            {"role": "system_owner", "name": "Владелец платформы"},
        )
        self.assertEqual(result["id"], 99)
        self.assertEqual(cursor.calls[0][1], (99,))
        self.assertIn("owner_scope='platform'", cursor.calls[2][0])
        self.assertNotIn("company_id=%s", cursor.calls[2][0])
        self.assertTrue(conn.committed)


if __name__ == "__main__":
    unittest.main()
