import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.features.agent_jobs.routes import (
    AgentJobCancelPayload,
    register_agent_jobs_module,
)


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorator(func):
            self.routes[("GET", path)] = func
            return func

        return decorator

    def post(self, path):
        def decorator(func):
            self.routes[("POST", path)] = func
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
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

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
        self.assertIn('"cancel_roles": LEADERSHIP_ROLES', source)
        self.assertIn('"insert_audit_event": insert_agent_job_audit_event', source)

    def build_app(self, cursor, *, actors=None, mode="company", audit=None):
        app = FakeApp()
        conn = FakeConnection(cursor)
        selected = list(actors if actors is not None else [actor()])
        audit_calls = []

        def insert_audit_event(_cur, **kwargs):
            audit_calls.append(kwargs)
            if audit is not None:
                return audit(_cur, **kwargs)
            return {
                "id": 91,
                "owner": {
                    "scope": "company",
                    "companyId": kwargs.get("company_id"),
                    "projectId": kwargs.get("project_id"),
                },
            }

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
            "cancel_roles": ("директор", "зам_директора"),
            "insert_audit_event": insert_audit_event,
        })
        return app, conn, audit_calls

    def test_list_uses_selected_company_and_returns_pagination(self):
        cursor = FakeCursor([[]])
        app, conn, _audit_calls = self.build_app(cursor)

        result = app.routes[("GET", "/agent-jobs")](
            "", None, None, 25, "4", "company", {"id": 7},
        )

        self.assertEqual(result, {"items": [], "nextBeforeId": None})
        self.assertEqual(cursor.calls[0][1], (4, 26))
        self.assertTrue(cursor.closed)
        self.assertTrue(conn.closed)

    def test_list_rejects_all_companies_before_business_query(self):
        cursor = FakeCursor()
        app, _conn, _audit_calls = self.build_app(
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
        app, _conn, _audit_calls = self.build_app(cursor, actors=[actor(4, "мастер")])

        with self.assertRaises(HTTPException) as caught:
            app.routes[("GET", "/agent-jobs")](
                "", None, None, 25, "4", "company", {"id": 7},
            )

        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(cursor.calls, [])

    def test_detail_hides_a_job_from_another_company(self):
        cursor = FakeCursor([None])
        app, _conn, _audit_calls = self.build_app(cursor)

        with self.assertRaises(HTTPException) as caught:
            app.routes[("GET", "/agent-jobs/{id}")](
                30, "4", "company", {"id": 7},
            )

        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(cursor.calls[0][1], (30, 4))

    def test_cancel_is_company_scoped_audited_and_public_only(self):
        row = {
            "id": 41,
            "company_id": 4,
            "project_id": 12,
            "job_type": "director.daily_brief",
            "status": "cancelled",
            "payload_json": {"must": "stay hidden"},
            "result_json": {"must": "stay hidden"},
            "locked_by": None,
            "lease_token": None,
        }
        cursor = FakeCursor([row])
        app, conn, audit_calls = self.build_app(cursor)

        result = app.routes[("POST", "/agent-jobs/{id}/cancel")](
            41,
            AgentJobCancelPayload(reasonCode="duplicate"),
            "4",
            "company",
            {"id": 7, "name": "Директор"},
        )

        self.assertTrue(result["cancelled"])
        self.assertEqual(result["reasonCode"], "duplicate")
        self.assertEqual(result["job"]["status"], "cancelled")
        self.assertNotIn("payload_json", result["job"])
        self.assertNotIn("result_json", result["job"])
        self.assertNotIn("locked_by", result["job"])
        self.assertNotIn("lease_token", result["job"])
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)
        self.assertEqual(len(audit_calls), 1)
        self.assertEqual(audit_calls[0]["company_id"], 4)
        self.assertEqual(audit_calls[0]["project_id"], 12)
        self.assertEqual(audit_calls[0]["entity_type"], "agent_job")
        self.assertEqual(audit_calls[0]["entity_id"], 41)

    def test_cancel_rejects_running_job_without_audit(self):
        cursor = FakeCursor([None, {"status": "running"}])
        app, conn, audit_calls = self.build_app(cursor)

        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/agent-jobs/{id}/cancel")](
                41,
                AgentJobCancelPayload(reasonCode="user_request"),
                "4",
                "company",
                {"id": 7, "name": "Директор"},
            )

        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(conn.commits, 0)
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(audit_calls, [])

    def test_cancel_hides_job_from_another_company(self):
        cursor = FakeCursor([None, None])
        app, conn, audit_calls = self.build_app(cursor)

        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/agent-jobs/{id}/cancel")](
                41,
                None,
                "4",
                "company",
                {"id": 7, "name": "Директор"},
            )

        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(audit_calls, [])

    def test_cancel_rolls_back_when_audit_fails(self):
        cursor = FakeCursor([{
            "id": 41,
            "company_id": 4,
            "project_id": None,
            "job_type": "director.daily_brief",
            "status": "cancelled",
        }])

        def broken_audit(_cur, **_kwargs):
            raise RuntimeError("audit unavailable")

        app, conn, _audit_calls = self.build_app(cursor, audit=broken_audit)

        with self.assertRaises(RuntimeError):
            app.routes[("POST", "/agent-jobs/{id}/cancel")](
                41,
                None,
                "4",
                "company",
                {"id": 7, "name": "Директор"},
            )

        self.assertEqual(conn.commits, 0)
        self.assertEqual(conn.rollbacks, 1)

    def test_cancel_rejects_non_leadership_before_business_query(self):
        cursor = FakeCursor()
        app, conn, audit_calls = self.build_app(cursor, actors=[actor(4, "мастер")])

        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/agent-jobs/{id}/cancel")](
                41,
                None,
                "4",
                "company",
                {"id": 7, "name": "Мастер"},
            )

        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(cursor.calls, [])
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(audit_calls, [])

    def test_cancel_rejects_all_companies_before_business_query(self):
        cursor = FakeCursor()
        app, conn, audit_calls = self.build_app(
            cursor,
            actors=[actor(4), actor(8)],
            mode="all_companies",
        )

        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/agent-jobs/{id}/cancel")](
                41,
                None,
                None,
                "all_companies",
                {"id": 7, "name": "Директор"},
            )

        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(cursor.calls, [])
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(audit_calls, [])


if __name__ == "__main__":
    unittest.main()
