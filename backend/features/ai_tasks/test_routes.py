import unittest

from fastapi import HTTPException

from backend.features.ai_tasks.routes import register_ai_tasks_module


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
        "name": "Тестовый пользователь",
        "assignedProjects": assigned or [],
    }


class AiTaskRouteTests(unittest.TestCase):
    def build_app(self, cursor, *, actors=None, mode="company", insert_id=30, insert_task=None):
        app = FakeApp()
        conn = FakeConnection(cursor)
        selected = list(actors or [actor()])

        def resolve_context(_cur, _user, _requested, action_mode, **_kwargs):
            return {
                "mode": mode,
                "companyId": selected[0]["companyId"] if selected else None,
                "actionMode": action_mode,
            }

        register_ai_tasks_module(app, {
            "get_db": lambda: conn,
            "get_current_user": lambda: {},
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, _context: selected,
            "read_roles": ("директор", "мастер"),
            "write_roles": ("директор", "мастер"),
            "update_roles": ("директор", "мастер"),
            "full_view_roles": ("директор",),
            "platform_task_roles": ("system_owner", "platform_admin", "platform_support"),
            "task_select": "SELECT id,project_name AS \"projectName\" FROM ai_tasks",
            "insert_task": insert_task or (lambda _cur, _payload, _actor, _owner: insert_id),
            "close_duplicates": lambda *_args, **_kwargs: None,
            "dedupe_key": lambda payload: payload.get("dedupeKey") or "",
            "system_project_name": "Система",
        })
        return app, conn

    def test_list_filters_by_stored_company_owner(self):
        cursor = FakeCursor([[{"id": 20, "projectName": "Объект A"}]])
        app, _conn = self.build_app(cursor)
        rows = app.routes[("GET", "/ai-tasks")](None, "4", "company", {"role": "директор"})
        self.assertEqual(rows[0]["id"], 20)
        self.assertIn("owner_scope='company'", cursor.calls[0][0])
        self.assertIn("company_id=%s", cursor.calls[0][0])
        self.assertNotIn("owner_scope='platform'", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], (4,))

    def test_list_rejects_all_companies_before_query(self):
        cursor = FakeCursor()
        app, _conn = self.build_app(cursor, mode="all_companies", actors=[actor(4), actor(8)])
        with self.assertRaises(HTTPException) as caught:
            app.routes[("GET", "/ai-tasks")](None, None, "all_companies", {"role": "директор"})
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(cursor.calls, [])

    def test_company_director_cannot_read_platform_tasks(self):
        cursor = FakeCursor()
        app, _conn = self.build_app(cursor)
        with self.assertRaises(HTTPException) as caught:
            app.routes[("GET", "/ai-tasks")]("Система", "4", "company", {"role": "директор"})
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(cursor.calls, [])

    def test_platform_role_reads_only_platform_scope(self):
        cursor = FakeCursor([[{"id": 99, "projectName": "Система"}]])
        app, _conn = self.build_app(cursor)
        rows = app.routes[("GET", "/ai-tasks")]("Система", None, None, {"role": "system_owner"})
        self.assertEqual(rows[0]["id"], 99)
        self.assertIn("owner_scope='platform'", cursor.calls[0][0])
        self.assertNotIn("company_id=%s", cursor.calls[0][0])

    def test_project_list_uses_stored_project_id(self):
        cursor = FakeCursor([
            [{"id": 10, "company_id": 4, "name": "Объект A"}],
            [{"id": 20, "projectName": "Объект A"}],
        ])
        app, _conn = self.build_app(cursor)
        app.routes[("GET", "/ai-tasks")]("Объект A", "4", "company", {"role": "директор"})
        self.assertIn("project_id=%s", cursor.calls[1][0])
        self.assertEqual(cursor.calls[1][1], (4, 10))

    def test_create_rejects_finding_owned_by_another_company(self):
        cursor = FakeCursor([
            {"company_id": 8, "project_id": 80, "project_name": "Объект B"},
            [{"id": 80, "company_id": 8, "name": "Объект B"}],
        ])
        app, conn = self.build_app(cursor)
        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/ai-tasks")](
                {"projectName": "Объект B", "findingId": 90, "title": "Чужая"},
                "4", "company", {"role": "директор"},
            )
        self.assertEqual(caught.exception.status_code, 404)
        self.assertTrue(conn.rolled_back)

    def test_create_passes_selected_owner_and_refetches_in_same_scope(self):
        captured = {}
        cursor = FakeCursor([
            [{"id": 10, "company_id": 4, "name": "Объект A"}],
            {"id": 30, "projectName": "Объект A", "title": "Проверить"},
        ])

        def insert_task(_cur, payload, selected_actor, owner):
            captured.update({"payload": payload, "actor": selected_actor, "owner": owner})
            return 30

        app, conn = self.build_app(cursor, insert_task=insert_task)
        result = app.routes[("POST", "/ai-tasks")](
            {"projectName": "Объект A", "title": "Проверить"},
            "4", "company", {"role": "директор"},
        )
        self.assertEqual(result["id"], 30)
        self.assertEqual(captured["owner"]["companyId"], 4)
        self.assertEqual(captured["owner"]["projectId"], 10)
        self.assertIn("owner_scope='company'", cursor.calls[1][0])
        self.assertEqual(cursor.calls[1][1], (30, 4, 10))
        self.assertTrue(conn.committed)

    def test_update_hides_task_owned_by_another_company(self):
        cursor = FakeCursor([None])
        app, conn = self.build_app(cursor)
        with self.assertRaises(HTTPException) as caught:
            app.routes[("PUT", "/ai-tasks/{id}")](
                20, {"status": "В работе"}, "4", "company", {"role": "директор"},
            )
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(cursor.calls[0][1], (20, 4))
        self.assertTrue(conn.rolled_back)

    def test_update_and_refetch_keep_complete_owner_filter(self):
        task = {
            "id": 20, "owner_scope": "company", "company_id": 4,
            "project_id": 10, "project_name": "Объект A",
        }
        cursor = FakeCursor([
            task,
            [{"id": 10, "company_id": 4, "name": "Объект A"}],
            None,
            {"id": 20, "projectName": "Объект A", "status": "В работе"},
        ])
        app, conn = self.build_app(cursor)
        result = app.routes[("PUT", "/ai-tasks/{id}")](
            20, {"status": "В работе"}, "4", "company", {"role": "директор", "name": "Директор"},
        )
        self.assertEqual(result["status"], "В работе")
        self.assertIn("owner_scope='company'", cursor.calls[2][0])
        self.assertEqual(cursor.calls[2][1][-3:], (4, 10, 20))
        self.assertIn("owner_scope='company'", cursor.calls[3][0])
        self.assertTrue(conn.committed)

    def test_platform_update_never_enters_company_scope(self):
        task = {
            "id": 99, "owner_scope": "platform", "company_id": None,
            "project_id": None, "project_name": "Система",
            "assigned_role": "директор", "assigned_to": "", "created_by": "system",
        }
        cursor = FakeCursor([
            task,
            None,
            {"id": 99, "projectName": "Система", "status": "Закрыто"},
        ])
        app, conn = self.build_app(cursor)
        result = app.routes[("PUT", "/ai-tasks/{id}")](
            99, {"status": "Закрыто"}, None, None, {"role": "system_owner", "name": "Владелец платформы"},
        )
        self.assertEqual(result["status"], "Закрыто")
        self.assertEqual(cursor.calls[0][1], (99,))
        self.assertIn("owner_scope='platform'", cursor.calls[1][0])
        self.assertNotIn("company_id=%s", cursor.calls[1][0])
        self.assertTrue(conn.committed)


if __name__ == "__main__":
    unittest.main()
