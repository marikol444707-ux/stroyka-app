import unittest

from fastapi import HTTPException

from backend.features.ai_control.routes import register_ai_control_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def post(self, path):
        def decorator(func):
            self.routes[("POST", path)] = func
            return func
        return decorator


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.current = None
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self.current = self.rows.pop(0) if self.rows else None

    def fetchone(self):
        return self.current

    def fetchall(self):
        return list(self.current or [])

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.autocommit = True
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, **_kwargs):
        return self.cursor_value

    def close(self):
        self.closed = True

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def actor(company_id=4, role="директор"):
    return {
        "companyId": company_id,
        "company_id": company_id,
        "role": role,
        "name": "Директор",
        "assignedProjects": [],
    }


class AiControlRouteTests(unittest.TestCase):
    def build_app(self, cursor, *, mode="company", actors=None, runner=None, owner=None, extra_connections=None):
        app = FakeApp()
        connection = FakeConnection(cursor)
        connections = [connection, *(extra_connections or [])]
        selected = list(actors or [actor()])
        calls = []

        def resolve_context(_cur, _user, _requested, action_mode, **_kwargs):
            return {"mode": mode, "companyId": 4, "actionMode": action_mode}

        def resolve_owner(_cur, project_name, **kwargs):
            calls.append((project_name, kwargs))
            return owner or {"id": 10, "companyId": 4, "name": "Объект A"}

        def run(cur, project_name, current_user, reason="manual", project_owner=None):
            if runner:
                return runner(cur, project_name, current_user, reason, project_owner)
            return {
                "ok": True,
                "projectName": project_name,
                "companyId": project_owner["companyId"],
                "projectId": project_owner["id"],
            }

        register_ai_control_module(app, {
            "get_db": lambda: connections.pop(0),
            "get_current_user": lambda: {},
            "get_ai_control_runner": lambda: {},
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, _context: selected,
            "resolve_project_owner": resolve_owner,
            "require_project_access": lambda _actor, _project: None,
            "run_project_ai_control": run,
            "generate_roles": ("директор", "сметчик"),
            "run_roles": ("директор", "сметчик", "мастер"),
            "run_all_roles": ("директор", "сметчик"),
            "system_actor_for_project": lambda project: {
                "role": "директор", "name": "ИИ-контроль", "companyId": project["companyId"],
            },
        })
        return app, connection, calls

    def test_single_run_uses_selected_company_and_exact_project_owner(self):
        cursor = FakeCursor([{"company_count": 1, "project_count": 1}])
        app, connection, owner_calls = self.build_app(cursor)

        result = app.routes[("POST", "/ai-control/run")](
            {"projectName": "Объект A", "reason": "manual"},
            "4",
            "company",
            {"id": 7, "role": "директор"},
        )

        self.assertTrue(result["ok"])
        self.assertEqual((result["companyId"], result["projectId"]), (4, 10))
        self.assertEqual(owner_calls[0][1]["company_id"], 4)
        self.assertTrue(owner_calls[0][1]["for_update"])
        self.assertIn("COUNT(DISTINCT company_id)", cursor.calls[0][0])
        self.assertFalse(connection.autocommit)
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)

    def test_single_run_rejects_all_companies_before_owner_lookup(self):
        cursor = FakeCursor()
        app, _connection, owner_calls = self.build_app(cursor, mode="all_companies")

        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/ai-control/run")](
                {"projectName": "Объект A"}, None, "all_companies", {"role": "директор"},
            )

        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(owner_calls, [])

    def test_run_all_lists_only_selected_company_and_commits_each_project(self):
        list_cursor = FakeCursor([[{"id": 10, "company_id": 4, "name": "Объект A"}]])
        project_cursor = FakeCursor([{"company_count": 1, "project_count": 1}])
        project_connection = FakeConnection(project_cursor)
        app, list_connection, owner_calls = self.build_app(
            list_cursor,
            extra_connections=[project_connection],
        )

        result = app.routes[("POST", "/ai-control/run-all")](
            {"reason": "nightly"}, "4", "company", {"role": "директор"},
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["projects"], 1)
        self.assertIn("WHERE company_id=%s", list_cursor.calls[0][0])
        self.assertEqual(list_cursor.calls[0][1], (4,))
        self.assertEqual(owner_calls[0][1]["project_id"], 10)
        self.assertTrue(project_connection.committed)
        self.assertTrue(list_connection.closed)

    def test_run_all_rejects_all_companies_before_listing_projects(self):
        list_cursor = FakeCursor([])
        app, list_connection, owner_calls = self.build_app(list_cursor, mode="all_companies")

        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/ai-control/run-all")](
                {}, None, "all_companies", {"role": "директор"},
            )

        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(list_cursor.calls, [])
        self.assertEqual(owner_calls, [])
        self.assertTrue(list_connection.closed)

    def test_system_run_all_lists_all_companies_but_uses_exact_owner_per_project(self):
        list_cursor = FakeCursor([[{"id": 10, "company_id": 4, "name": "Объект A"}]])
        project_cursor = FakeCursor([{"company_count": 1, "project_count": 1}])
        project_connection = FakeConnection(project_cursor)
        app, _list_connection, owner_calls = self.build_app(
            list_cursor,
            extra_connections=[project_connection],
        )

        result = app.routes[("POST", "/ai-control/run-all")](
            {"reason": "scheduler"}, None, None, {"role": "директор", "aiControlSystem": True},
        )

        self.assertTrue(result["ok"])
        self.assertNotIn("WHERE company_id=%s", list_cursor.calls[0][0])
        self.assertEqual(owner_calls[0][1]["company_id"], 4)
        self.assertEqual(owner_calls[0][1]["project_id"], 10)
        self.assertTrue(project_connection.committed)

    def test_run_all_rolls_back_failed_project_and_reports_error(self):
        list_cursor = FakeCursor([[{"id": 10, "company_id": 4, "name": "Объект A"}]])
        project_cursor = FakeCursor([{"company_count": 1, "project_count": 1}])
        project_connection = FakeConnection(project_cursor)

        def fail(*_args):
            raise RuntimeError("project generation failed")

        app, _list_connection, _owner_calls = self.build_app(
            list_cursor,
            runner=fail,
            extra_connections=[project_connection],
        )

        result = app.routes[("POST", "/ai-control/run-all")](
            {}, "4", "company", {"role": "директор"},
        )

        self.assertTrue(result["ok"])
        self.assertFalse(result["results"][0]["ok"])
        self.assertIn("project generation failed", result["results"][0]["detail"])
        self.assertTrue(project_connection.rolled_back)
        self.assertFalse(project_connection.committed)

    def test_single_run_rejects_duplicate_name_across_companies(self):
        cursor = FakeCursor([{"company_count": 2, "project_count": 2}])
        app, _connection, _calls = self.build_app(cursor)

        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/ai-findings/generate")](
                {"projectName": "Объект A"}, "4", "company", {"role": "директор"},
            )

        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn("одинаковым названием", caught.exception.detail)

    def test_runner_failure_rolls_back_whole_single_run(self):
        cursor = FakeCursor([{"company_count": 1, "project_count": 1}])

        def fail(*_args):
            raise RuntimeError("generation failed")

        app, connection, _calls = self.build_app(cursor, runner=fail)

        with self.assertRaisesRegex(RuntimeError, "generation failed"):
            app.routes[("POST", "/ai-control/run")](
                {"projectName": "Объект A"}, "4", "company", {"role": "директор"},
            )

        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertTrue(connection.closed)

    def test_generate_rejects_role_not_allowed_in_selected_company(self):
        cursor = FakeCursor()
        app, _connection, owner_calls = self.build_app(cursor, actors=[actor(role="мастер")])

        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/ai-findings/generate")](
                {"projectName": "Объект A"}, "4", "company", {"role": "директор"},
            )

        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(owner_calls, [])


if __name__ == "__main__":
    unittest.main()
