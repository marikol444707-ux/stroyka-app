import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.features.demo_requests.routes import register_demo_requests_module


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
        self.closed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def close(self):
        self.closed = True


def build(cursor):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_demo_requests_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "leadership_roles": ("директор",),
    })
    return app, connection


class DemoRequestsRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor())
        self.assertIn(("GET", "/demo-requests"), app.routes)
        self.assertIn(("POST", "/demo-request"), app.routes)
        self.assertIn(("PUT", "/demo-requests/{id}"), app.routes)

    def test_public_create_returns_id_and_message(self):
        cursor = FakeCursor(fetchone_results=[{"id": 11}])
        app, connection = build(cursor)
        result = app.routes[("POST", "/demo-request")]({"companyName": "ООО Тест", "phone": "+7"})
        self.assertEqual(result["id"], 11)
        self.assertTrue(result["ok"])
        sql, params = cursor.calls[0]
        self.assertIn("INSERT INTO demo_requests", sql)
        self.assertEqual(params[0], "ООО Тест")
        self.assertEqual(params[7], "landing")
        self.assertTrue(connection.closed)

    def test_update_missing_request_raises_404(self):
        cursor = FakeCursor(fetchone_results=[None])
        app, _conn = build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("PUT", "/demo-requests/{id}")](id=99, data={"status": "Обработана"}, current_user={})
        self.assertEqual(ctx.exception.status_code, 404)

    def test_update_writes_platform_audit(self):
        before = {"id": 5, "status": "Новая", "company_name": "ООО Тест", "assigned_company_id": None}
        after = {"id": 5, "status": "Обработана", "company_name": "ООО Тест", "assigned_company_id": 7}
        cursor = FakeCursor(fetchone_results=[before, after])
        app, connection = build(cursor)
        with patch("backend.features.demo_requests.routes.write_platform_audit") as audit:
            result = app.routes[("PUT", "/demo-requests/{id}")](
                id=5, data={"status": "Обработана"}, current_user={"id": 1, "role": "директор"}
            )
        self.assertEqual(result, {"ok": True})
        audit.assert_called_once()
        args, kwargs = audit.call_args
        self.assertEqual(args[2], "demo_request_updated")
        self.assertEqual(kwargs["details"]["beforeStatus"], "Новая")
        self.assertEqual(kwargs["details"]["afterStatus"], "Обработана")
        update_sql = [c for c in cursor.calls if c[0].startswith("UPDATE demo_requests")]
        self.assertEqual(len(update_sql), 1)
        self.assertIn("processed_at=%s", update_sql[0][0])
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
