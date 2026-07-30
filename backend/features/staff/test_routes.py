import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.features.staff.routes import StaffModel, register_staff_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def put(self, path):
        return self._register("PUT", path)

    def delete(self, path):
        return self._register("DELETE", path)

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
        self.rowcount = 1

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
        self.committed = False
        self.rolled_back = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def build(cursor, audit_calls=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    audit_log = audit_calls if audit_calls is not None else []
    register_staff_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "require_roles": lambda *roles: (lambda: None),
        "staff_view_roles": ("директор", "прораб"),
        "staff_manage_roles": ("директор",),
        "staff_full_view_roles": ("директор", "бухгалтер"),
        "user_project_names": lambda user: ["Объект"],
        "safe_project_list": lambda v: v if isinstance(v, list) else [],
        "prepare_user_access_scope": lambda cur, role, project, projects, packages: (projects, packages),
        "date_or_none": lambda v: v or None,
        "log_audit": lambda *args: audit_log.append(args),
    })
    return app, connection


class StaffRoutesTest(unittest.TestCase):
    def test_all_urls_registered(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/staff"), ("POST", "/staff"), ("PUT", "/staff/{id}"), ("DELETE", "/staff/{id}"),
                    ("GET", "/staff/{staff_id}/profile"), ("POST", "/staff/{staff_id}/documents"),
                    ("DELETE", "/staff-documents/{doc_id}")]:
            self.assertIn(key, app.routes)

    def test_non_staff_role_gets_empty_list(self):
        cursor = FakeCursor()
        app, _conn = build(cursor)
        result = app.routes[("GET", "/staff")](current_user={"role": "мастер"})
        self.assertEqual(result, [])
        self.assertEqual(cursor.calls, [])

    def test_foreman_scoped_to_projects(self):
        cursor = FakeCursor(rows=[])
        app, _conn = build(cursor)
        app.routes[("GET", "/staff")](current_user={"role": "прораб"})
        self.assertIn("WHERE project = ANY(%s)", cursor.calls[0][0])

    def test_fire_disables_linked_users_and_revokes_sessions(self):
        revoked = []
        staff_row = {"name": "Мастер Тест", "role": "мастер", "project": "Объект",
                     "email_work": "m@t.ru", "email_personal": ""}
        cursor = FakeCursor(fetchone_results=[staff_row])
        cursor.rows = [{"id": 42}]
        audit = []
        app, connection = build(cursor, audit_calls=audit)
        with patch("backend.features.staff.routes._revoke_user_sessions",
                   lambda cur, uid: revoked.append(uid)):
            result = app.routes[("DELETE", "/staff/{id}")](id=5, _current_user={"name": "Тест", "role": "директор"})
        self.assertEqual(result["status"], "Уволен")
        self.assertEqual(result["disabledUsers"], 1)
        self.assertEqual(revoked, [42])
        update_users = [c for c in cursor.calls if c[0].startswith("UPDATE users SET active=FALSE")]
        self.assertEqual(len(update_users), 1)
        self.assertEqual(audit[0][2], "deactivate")
        self.assertTrue(connection.committed)

    def test_create_with_access_requires_role_and_email(self):
        cursor = FakeCursor(fetchone_results=[(7,)])
        app, connection = build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/staff")](
                StaffModel(name="Новый", role="мастер", password="12345"),
                _current_user={"name": "Тест"},
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("системная роль", ctx.exception.detail)
        self.assertTrue(connection.rolled_back)


if __name__ == "__main__":
    unittest.main()
