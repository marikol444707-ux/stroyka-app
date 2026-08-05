import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.features.agent_jobs.routes import register_agent_jobs_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorator(func):
            self.routes[("GET", path)] = func
            return func

        return decorator


class FakeCursor:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.current = None
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self.current = self.responses.pop(0) if self.responses else None

    def fetchall(self):
        return list(self.current or [])

    def fetchone(self):
        return self.current

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.closed = False

    def cursor(self, **_kwargs):
        return self.cursor_value

    def close(self):
        self.closed = True


def actor(company_id=4, role="директор"):
    return {"id": 7, "companyId": company_id, "role": role}


class AgentJobRouteTests(unittest.TestCase):
    def test_backend_registers_agent_job_routes_with_leadership_roles(self):
        main_path = Path(__file__).resolve().parents[2] / "main.py"
        source = " ".join(main_path.read_text(encoding="utf-8").split())

        self.assertIn("register_agent_jobs_module(app", source)
        self.assertIn('"read_roles": LEADERSHIP_ROLES', source)

    def build_app(self, cursor, *, actors=None, mode="company"):
        app = FakeApp()
        conn = FakeConnection(cursor)
        selected = list(actors if actors is not None else [actor()])

        def resolve_context(_cur, _user, _requested, action_mode, **_kwargs):
            return {
                "mode": mode,
                "companyId": selected[0]["companyId"] if selected else None,
                "actionMode": action_mode,
            }

        register_agent_jobs_module(app, {
            "get_db": lambda: conn,
            "get_current_user": lambda: {},
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, _context: selected,
            "read_roles": ("директор", "зам_директора"),
        })
        return app, conn

    def test_list_uses_selected_company_and_returns_pagination(self):
        cursor = FakeCursor([[]])
        app, conn = self.build_app(cursor)

        result = app.routes[("GET", "/agent-jobs")](
            "", None, None, 25, "4", "company", {"id": 7},
        )

        self.assertEqual(result, {"items": [], "nextBeforeId": None})
        self.assertEqual(cursor.calls[0][1], (4, 26))
        self.assertTrue(cursor.closed)
        self.assertTrue(conn.closed)

    def test_list_rejects_all_companies_before_business_query(self):
        cursor = FakeCursor()
        app, _conn = self.build_app(
            cursor,
            actors=[actor(4), actor(8)],
            mode="all_companies",
        )

        with self.assertRaises(HTTPException) as caught:
            app.routes[("GET", "/agent-jobs")](
                "", None, None, 25, None, "all_companies", {"id": 7},
            )

        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(cursor.calls, [])

    def test_list_rejects_non_leadership_role_before_business_query(self):
        cursor = FakeCursor()
        app, _conn = self.build_app(cursor, actors=[actor(4, "мастер")])

        with self.assertRaises(HTTPException) as caught:
            app.routes[("GET", "/agent-jobs")](
                "", None, None, 25, "4", "company", {"id": 7},
            )

        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(cursor.calls, [])

    def test_detail_hides_a_job_from_another_company(self):
        cursor = FakeCursor([None])
        app, _conn = self.build_app(cursor)

        with self.assertRaises(HTTPException) as caught:
            app.routes[("GET", "/agent-jobs/{id}")](
                30, "4", "company", {"id": 7},
            )

        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(cursor.calls[0][1], (30, 4))


if __name__ == "__main__":
    unittest.main()
