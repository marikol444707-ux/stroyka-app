import unittest

from fastapi import HTTPException

from backend.features.ai_findings.routes import register_ai_findings_module


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
    return {"companyId": company_id, "role": role, "assignedProjects": assigned or []}


class AiFindingsRouteTests(unittest.TestCase):
    def build_app(self, cursor, *, actors=None, mode="company", upsert_result=20):
        app = FakeApp()
        conn = FakeConnection(cursor)
        selected = list(actors or [actor()])

        def resolve_context(_cur, _user, _requested, action_mode, **_kwargs):
            return {"mode": mode, "companyId": selected[0]["companyId"] if selected else None, "actionMode": action_mode}

        register_ai_findings_module(app, {
            "get_db": lambda: conn,
            "get_current_user": lambda: {},
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, _context: selected,
            "read_roles": ("директор", "мастер"),
            "write_roles": ("директор", "мастер"),
            "update_roles": ("директор", "мастер"),
            "full_view_roles": ("директор",),
            "finding_select": "SELECT id,project_name AS \"projectName\" FROM ai_findings",
            "upsert_finding": lambda _cur, _payload, _actor, project: upsert_result,
        })
        return app, conn

    def test_list_filters_by_stored_company_owner(self):
        cursor = FakeCursor([[{"id": 20, "projectName": "Объект A"}]])
        app, _conn = self.build_app(cursor)
        rows = app.routes[("GET", "/ai-findings")](None, "4", "company", {"role": "директор"})
        self.assertEqual(rows[0]["id"], 20)
        self.assertIn("company_id=%s", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], (4,))

    def test_list_rejects_all_companies_before_query(self):
        cursor = FakeCursor()
        app, _conn = self.build_app(cursor, mode="all_companies", actors=[actor(4), actor(8)])
        with self.assertRaises(HTTPException) as caught:
            app.routes[("GET", "/ai-findings")](None, None, "all_companies", {"role": "директор"})
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(cursor.calls, [])

    def test_assigned_role_list_uses_resolved_project_ids(self):
        cursor = FakeCursor([[
            {"id": 10, "company_id": 4, "name": "Объект A"},
        ], [{"id": 20, "projectName": "Объект A"}]])
        app, _conn = self.build_app(cursor, actors=[actor(4, "мастер", ["Объект A"])])
        app.routes[("GET", "/ai-findings")](None, "4", "company", {"role": "директор"})
        self.assertIn("project_id = ANY(%s)", cursor.calls[1][0])
        self.assertEqual(cursor.calls[1][1], (4, [10]))

    def test_update_hides_finding_owned_by_another_company(self):
        cursor = FakeCursor([None])
        app, conn = self.build_app(cursor)
        with self.assertRaises(HTTPException) as caught:
            app.routes[("PUT", "/ai-findings/{id}")](20, {"status": "Закрыто"}, "4", "company", {"role": "директор"})
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(cursor.calls[0][1], (20, 4))
        self.assertTrue(conn.rolled_back)

    def test_update_locks_project_before_refetching_finding(self):
        finding = {
            "id": 20, "company_id": 4, "project_id": 10, "project_name": "Объект A",
            "linked_entity_type": "", "linked_entity_id": "",
        }
        cursor = FakeCursor([
            finding,
            [{"id": 10, "company_id": 4, "name": "Объект A"}],
            finding,
            None,
            None,
            {"id": 20, "projectName": "Объект A", "status": "Закрыто"},
        ])
        app, conn = self.build_app(cursor)
        result = app.routes[("PUT", "/ai-findings/{id}")](
            20, {"status": "Закрыто"}, "4", "company", {"role": "директор"}
        )
        self.assertEqual(result["status"], "Закрыто")
        self.assertNotIn("FOR UPDATE", cursor.calls[0][0])
        self.assertIn("FROM projects", cursor.calls[1][0])
        self.assertIn("FOR UPDATE", cursor.calls[1][0])
        self.assertIn("FOR UPDATE", cursor.calls[2][0])
        self.assertEqual(cursor.calls[3][1][-3:], (20, 4, 10))
        self.assertTrue(conn.committed)

    def test_create_passes_selected_project_owner_to_upsert(self):
        cursor = FakeCursor([[
            {"id": 10, "company_id": 4, "name": "Объект A"},
        ], {"id": 20, "projectName": "Объект A"}])
        captured = {}
        app = FakeApp()
        conn = FakeConnection(cursor)

        def upsert(_cur, payload, selected_actor, project):
            captured.update({"payload": payload, "actor": selected_actor, "project": project})
            return 20

        register_ai_findings_module(app, {
            "get_db": lambda: conn,
            "get_current_user": lambda: {},
            "resolve_work_company_context": lambda *_args, **_kwargs: {"mode": "company", "companyId": 4},
            "effective_company_actors": lambda *_args: [actor()],
            "read_roles": ("директор",),
            "write_roles": ("директор",),
            "update_roles": ("директор",),
            "full_view_roles": ("директор",),
            "finding_select": "SELECT id,project_name AS \"projectName\" FROM ai_findings",
            "upsert_finding": upsert,
        })
        result = app.routes[("POST", "/ai-findings")](
            {"projectName": "Объект A", "title": "Проверить"}, "4", "company", {"role": "директор"}
        )
        self.assertEqual(result["id"], 20)
        self.assertEqual(captured["project"]["id"], 10)
        self.assertTrue(conn.committed)


if __name__ == "__main__":
    unittest.main()
