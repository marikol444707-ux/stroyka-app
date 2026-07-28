import unittest

from fastapi import HTTPException

from backend.features.pd_consents.routes import PdConsentModel, register_pd_consents_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def delete(self, path):
        return self._register("DELETE", path)

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

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.row

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, **_kwargs):
        return self._cursor

    def close(self):
        self.closed = True


def build(cursor):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_pd_consents_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "require_roles": lambda *roles: (lambda: None),
        "staff_manage_roles": ("директор", "зам_директора"),
    })
    return app, connection


class PdConsentsRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/pd-consents"), ("POST", "/pd-consents"), ("DELETE", "/pd-consents/{user_id}")]:
            self.assertIn(key, app.routes)

    def test_worker_cannot_sign_for_another_user(self):
        app, _conn = build(FakeCursor())
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/pd-consents")](
                PdConsentModel(userId=99), _current_user={"id": 42, "role": "мастер"}
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_worker_signs_own_consent(self):
        row = {"id": 1, "userId": 42, "signedAt": "2026-07-28", "scanUrl": "", "uploadedBy": "Тест"}
        cursor = FakeCursor(row=row)
        app, _conn = build(cursor)
        result = app.routes[("POST", "/pd-consents")](
            PdConsentModel(userId=42, signedAt="2026-07-28", uploadedBy="Тест"),
            _current_user={"id": 42, "role": "мастер"},
        )
        self.assertEqual(result["userId"], 42)
        self.assertIn("ON CONFLICT (user_id) DO UPDATE", cursor.calls[0][0])

    def test_delete_targets_exact_user(self):
        cursor = FakeCursor()
        app, _conn = build(cursor)
        result = app.routes[("DELETE", "/pd-consents/{user_id}")](user_id=42, _current_user={})
        self.assertEqual(result, {"ok": True})
        self.assertEqual(cursor.calls[0][1], (42,))


if __name__ == "__main__":
    unittest.main()
