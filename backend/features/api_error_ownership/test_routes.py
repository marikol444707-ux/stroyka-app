import unittest

from backend.features.api_error_ownership.routes import register_api_errors_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator


class FakeCursor:
    def __init__(self, rows=(), row=None):
        self.rows = list(rows)
        self.row = row
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.closed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class FakeClient:
    host = "10.0.0.1"


class FakeRequest:
    def __init__(self, headers=None):
        self.client = FakeClient()
        self.headers = dict(headers or {})


def make_deps(cursor, **overrides):
    connection = FakeConnection(cursor)
    deps = {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "leadership_roles": ("директор", "зам_директора"),
        "resolve_work_company_context": lambda cur, user, project, mode, **kw: {"mode": "company", "companyId": 7},
        "effective_company_actors": lambda actor, context: [{"companyId": 7, "role": "директор"}],
        "client_error_logging_enabled": True,
        "client_error_last_submit": {},
        "client_error_rate_limit_seconds": 30,
        "clip_api_error_text": lambda value, limit=700: str(value or "")[:limit],
        "request_user_snapshot": lambda request, cur=None: {
            "id": 42, "name": "Тест", "role": "директор",
            "user_id": 42, "user_name": "Тест", "user_role": "директор",
        },
        "utc_now_iso": lambda: "2026-07-27T00:00:00Z",
        "app_version": lambda: "testver",
        "count_table": lambda cur, table, where="", params=(): 3,
        "storage_backend": "local",
        "s3_enabled": lambda: False,
        "s3_missing_config_keys": lambda: [],
        "s3_endpoint_url": "",
        "s3_bucket": "",
        "s3_public_url": "",
        "s3_prefix": "uploads",
        "max_upload_bytes": 50 * 1024 * 1024,
        "upload_dir": "uploads",
        "limited_dir_stats": lambda path, max_entries=5000: {"files": 0},
        "latest_backup_status": lambda: {"ok": True},
    }
    deps.update(overrides)
    return deps, connection


def build(cursor, **overrides):
    app = FakeApp()
    deps, connection = make_deps(cursor, **overrides)
    register_api_errors_module(app, deps)
    return app, deps, connection


class RegisterApiErrorsModuleTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _deps, _conn = build(FakeCursor())
        self.assertIn(("POST", "/client-errors"), app.routes)
        self.assertIn(("GET", "/system-status"), app.routes)

    def test_client_errors_disabled_short_circuits(self):
        cursor = FakeCursor()
        app, _deps, connection = build(cursor, client_error_logging_enabled=False)
        result = app.routes[("POST", "/client-errors")]({"message": "boom"}, FakeRequest())
        self.assertEqual(result, {"ok": True, "disabled": True})
        self.assertEqual(cursor.calls, [])
        self.assertFalse(connection.committed)

    def test_client_errors_rate_limit_second_submit(self):
        cursor = FakeCursor()
        app, _deps, _conn = build(cursor)
        handler = app.routes[("POST", "/client-errors")]
        first = handler({"message": "boom", "path": "/app", "type": "Err"}, FakeRequest())
        second = handler({"message": "boom", "path": "/app", "type": "Err"}, FakeRequest())
        self.assertEqual(first, {"ok": True})
        self.assertEqual(second, {"ok": True, "rateLimited": True})

    def test_client_errors_write_keeps_payload_fields_and_owner(self):
        cursor = FakeCursor()
        app, _deps, connection = build(cursor)
        result = app.routes[("POST", "/client-errors")](
            {"message": "boom", "stack": "trace", "path": "/app/page", "type": "TypeError"},
            FakeRequest(headers={"x-company-id": "7", "x-company-mode": "company"}),
        )
        self.assertEqual(result, {"ok": True})
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)
        inserts = [c for c in cursor.calls if c[0].startswith("INSERT INTO api_errors")]
        self.assertEqual(len(inserts), 1)
        sql, params = inserts[0]
        self.assertIn("owner_scope", sql)
        self.assertEqual(params[0], "CLIENT")
        self.assertEqual(params[1], "/app/page")
        self.assertEqual(params[2], 499)
        self.assertEqual(params[3], "TypeError")
        self.assertEqual(params[4], "boom\ntrace")
        self.assertEqual(params[5], 42)
        self.assertEqual(params[6], "Тест")
        self.assertEqual(params[7], "директор")
        self.assertEqual(params[8], "company")
        self.assertEqual(params[9], 7)

    def test_system_status_scopes_counts_and_reports(self):
        cursor = FakeCursor(rows=[], row=[2])
        app, _deps, connection = build(cursor)
        result = app.routes[("GET", "/system-status")](
            api_errors_since=None,
            api_errors_hours=24,
            x_company_id="7",
            x_company_mode="company",
            current_user={"id": 1, "role": "директор"},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "testver")
        self.assertEqual(result["apiErrorsWindow"], "last_24h")
        self.assertEqual(result["counts"]["projects"], 3)
        self.assertEqual(result["counts"]["apiErrors"], 3)
        self.assertEqual(result["counts"]["apiErrorsShown"], 2)
        self.assertEqual(result["apiErrors"], [])
        self.assertEqual(result["recentAudit"], [])
        self.assertTrue(result["db"]["ok"])
        self.assertTrue(connection.closed)
        scoped = [c for c in cursor.calls if "owner_scope='company'" in c[0]]
        self.assertTrue(scoped, "queries must carry the company owner predicate")


if __name__ == "__main__":
    unittest.main()
