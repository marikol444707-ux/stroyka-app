import unittest

from fastapi import HTTPException

from .routes import register_job_candidates_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def put(self, path):
        return self._register("PUT", path)


class FakeCursor:
    def __init__(self, result=None, rows=()):
        self.result = result
        self.rows = list(rows)
        self.calls = []
        self.rowcount = 1

    def execute(self, sql, params=()):
        self.calls.append((" ".join(str(sql).split()), tuple(params or ())))

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self.value = cursor
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, **_kwargs):
        return self.value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


class JobCandidateRouteTests(unittest.TestCase):
    def build(self, cursor, *, context=None, roles=None):
        app = FakeApp()
        conn = FakeConnection(cursor)
        resolve_calls = []

        def resolve(_cur, _user, _requested, action, **kwargs):
            resolve_calls.append((action, kwargs))
            return context or {"mode": "company", "companyId": 8}

        register_job_candidates_module(app, {
            "get_db": lambda: conn,
            "get_current_user": lambda: {"id": 9},
            "resolve_work_company_context": resolve,
            "effective_company_actors": lambda _user, ctx: [
                {"companyId": ctx.get("companyId", 8), "role": role}
                for role in (roles or ["директор"])
            ],
            "allowed_roles": ("директор", "менеджер_crm"),
        })
        return app, conn, resolve_calls

    def test_ingest_is_scoped_and_upserts_idempotently(self):
        cursor = FakeCursor({"id": 41, "inserted": False, "status": "Подходит"})
        app, conn, calls = self.build(cursor)
        response = app.routes[("POST", "/crm/job-candidates")](
            {"source": "eis", "sourceItemId": "EIS-1", "url": "https://example.org/1", "title": "Ремонт"},
            current_user={"name": "Директор"}, x_company_id="8", x_company_mode="company",
        )

        self.assertEqual(response, {"ok": True, "id": 41, "inserted": False, "status": "Подходит"})
        sql, params = cursor.calls[0]
        self.assertIn("ON CONFLICT DO UPDATE", sql)
        self.assertEqual(params[0], 8)
        self.assertEqual(sql.count("%s"), len(params))
        self.assertEqual(conn.commits, 1)
        self.assertEqual(calls[0][0], "write")

    def test_rejects_all_company_scope(self):
        cursor = FakeCursor()
        app, _conn, _calls = self.build(cursor, context={"mode": "all_companies"})
        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/crm/job-candidates")](current_user={"id": 9})
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(cursor.calls, [])

    def test_rejects_user_without_allowed_company_role(self):
        cursor = FakeCursor()
        app, _conn, _calls = self.build(cursor, roles=["наблюдатель"])
        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/crm/job-candidates")](current_user={"id": 9})
        self.assertEqual(raised.exception.status_code, 403)

    def test_import_report_is_one_company_scoped_transaction(self):
        cursor = FakeCursor({"id": 41, "inserted": True})
        app, conn, calls = self.build(cursor)
        response = app.routes[("POST", "/crm/job-candidates/import-report")](
            {"items": [{
                "source": "browser_agent", "sourceName": "B2B-Center", "sourceItemId": "B2B-Center:12",
                "url": "https://example.org/tender/12", "title": "Строительство школы",
            }]},
            current_user={"name": "Директор"}, x_company_id="8", x_company_mode="company",
        )

        self.assertEqual(response, {"ok": True, "received": 1, "created": 1, "updated": 0})
        sql, params = cursor.calls[0]
        self.assertIn("source_name", sql)
        self.assertEqual(sql.count("%s"), len(params))
        self.assertEqual(params[0], 8)
        self.assertEqual(conn.commits, 1)
        self.assertEqual(calls[0][0], "write")


if __name__ == "__main__":
    unittest.main()
