import unittest

from fastapi import HTTPException

from backend.features.audit_ownership.routes import register_audit_log_module


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
        self.cursor_value = cursor
        self.committed = False
        self.closed = False

    def cursor(self, cursor_factory=None):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class AuditRoutesTests(unittest.TestCase):
    def _register(self, connection, *, context=None, actors=None):
        app = FakeApp()
        resolver_calls = []

        def resolve_context(cur, user, requested_company_id, action_mode, **kwargs):
            resolver_calls.append((action_mode, requested_company_id, kwargs))
            return context or {"mode": "company", "companyId": 4, "companyIds": [4]}

        register_audit_log_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, _context: actors or [
                {"id": 9, "name": "Директор", "role": "директор", "companyId": 4},
            ],
            "allowed_roles": ("директор", "зам_директора", "бухгалтер"),
        })
        return app, resolver_calls

    def test_list_filters_selected_company_and_excludes_platform_legacy(self):
        cursor = FakeCursor(rows=({
            "id": 1, "user_id": 9, "user_name": "Директор", "user_role": "директор",
            "action": "update", "entity_type": "ui", "entity_id": None,
            "description": "Изменение", "project_name": "", "owner_scope": "company",
            "company_id": 4, "project_id": None, "created_at": "2026-07-14",
        },))
        app, resolver_calls = self._register(FakeConnection(cursor))

        result = app.routes[("GET", "/audit-log")](
            limit=20, offset=0, search="", user_name="", user_role="", action="",
            entity_type="", project_name="", date_from="", date_to="",
            x_company_id="4", x_company_mode="company",
            current_user={"id": 9, "role": "директор"},
        )

        self.assertEqual(resolver_calls[0][0], "read")
        sql, params = cursor.calls[0]
        self.assertIn("owner_scope='company'", sql)
        self.assertIn("company_id = ANY(%s)", sql)
        self.assertEqual(params[-3:], ([4], 20, 0))
        self.assertEqual(result[0]["companyId"], 4)

    def test_all_companies_keeps_only_leadership_memberships(self):
        cursor = FakeCursor(rows=())
        app, _ = self._register(
            FakeConnection(cursor),
            context={"mode": "all_companies", "companyIds": [4, 5]},
            actors=[
                {"role": "директор", "companyId": 4},
                {"role": "мастер", "companyId": 5},
            ],
        )

        app.routes[("GET", "/audit-log")](
            limit=20, offset=0, search="", user_name="", user_role="", action="",
            entity_type="", project_name="", date_from="", date_to="",
            x_company_id=None, x_company_mode="all_companies",
            current_user={"id": 9, "role": "директор"},
        )

        self.assertEqual(cursor.calls[0][1][-3], [4])

    def test_list_rejects_role_without_auditable_company(self):
        cursor = FakeCursor()
        app, _ = self._register(
            FakeConnection(cursor),
            actors=[{"role": "мастер", "companyId": 4}],
        )

        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/audit-log")](
                limit=20, offset=0, search="", user_name="", user_role="", action="",
                entity_type="", project_name="", date_from="", date_to="",
                x_company_id="4", x_company_mode="company",
                current_user={"id": 9, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(cursor.calls, [])

    def test_create_stores_selected_company_and_server_actor(self):
        cursor = FakeCursor(row={"id": 18})
        connection = FakeConnection(cursor)
        app, resolver_calls = self._register(connection)

        result = app.routes[("POST", "/audit-log")](
            {"action": "Открыт раздел", "entityType": "ui", "description": "Снабжение"},
            x_company_id="4", x_company_mode="company",
            current_user={"id": 9, "name": "Глобальное имя", "role": "директор"},
        )

        self.assertEqual(resolver_calls[0][0], "create")
        sql, params = cursor.calls[-1]
        self.assertIn("owner_scope,company_id,project_id", sql)
        self.assertEqual(params[:4], (9, "Директор", "директор", "Открыт раздел"))
        self.assertEqual(params[-3:], ("company", 4, None))
        self.assertEqual(result, {"id": 18, "ok": True})
        self.assertTrue(connection.committed)

    def test_create_rejects_all_companies_mode(self):
        cursor = FakeCursor()
        app, _ = self._register(
            FakeConnection(cursor),
            context={"mode": "all_companies", "companyIds": [4, 5]},
        )

        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/audit-log")](
                {"action": "x"}, x_company_id=None, x_company_mode="all_companies",
                current_user={"id": 9, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(cursor.calls, [])


if __name__ == "__main__":
    unittest.main()
