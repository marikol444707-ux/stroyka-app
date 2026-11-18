import unittest

from fastapi import HTTPException

from backend.features.auth_session.routes import register_auth_session_module


class FakeApp:
    def get(self, path):
        def decorator(handler):
            self.handler = handler
            self.path = path
            return handler
        return decorator


class FakeCursor:
    def __init__(self, row=None):
        self.row = row
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.autocommit = True
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


class Request:
    def __init__(self, cookies=None):
        self.cookies = cookies or {}


def build(cursor, *, opened):
    app = FakeApp()
    connection = FakeConnection(cursor)

    def get_db():
        opened.append(connection)
        return connection

    def public_user(row, include_token=False, two_factor_passed=False):
        payload = {
            "id": row.get("id"),
            "name": row.get("name") or "",
            "email": row.get("email") or "",
            "role": row.get("role") or "",
            "companyId": row.get("company_id"),
            "company_id": row.get("company_id"),
            "twoFactorPassed": two_factor_passed,
        }
        if include_token:
            payload["authToken"] = "server-token"
        return payload

    register_auth_session_module(app, {
        "get_db": get_db,
        "session_cookie_name": "stroyka_session",
        "session_token_hash": lambda token: "hash:" + token,
        "public_user": public_user,
        "user_requires_2fa": lambda user: user.get("role") == "директор" or bool(user.get("two_factor_required")),
        "enrich_worker_project_links": lambda cur, user: user,
        "cursor_factory": None,
    })
    return app.handler, connection


class AuthSessionRouteTests(unittest.TestCase):
    def test_valid_cookie_returns_the_stored_user_without_secrets_or_writes(self):
        opened = []
        cursor = FakeCursor({
            "id": 7,
            "name": "Иван",
            "email": "foreman@example.test",
            "role": "прораб",
            "company_id": 4,
            "active": True,
            "password": "secret-hash",
            "two_factor_secret": "totp",
            "auth_session_two_factor_passed": False,
        })
        handler, connection = build(cursor, opened=opened)
        result = handler(Request({"stroyka_session": "real-cookie"}))
        self.assertEqual(result["id"], 7)
        self.assertEqual(result["role"], "прораб")
        self.assertEqual(result["companyId"], 4)
        self.assertNotIn("authToken", result)
        self.assertNotIn("password", result)
        self.assertNotIn("two_factor_secret", result)
        self.assertEqual(cursor.calls[0][0], "SET TRANSACTION READ ONLY")
        self.assertEqual(cursor.calls[1][1], ("hash:real-cookie",))
        self.assertNotIn("real-cookie", cursor.calls[1][0])
        self.assertFalse(any(
            token in sql
            for sql, _params in cursor.calls
            for token in ("UPDATE", "INSERT", "DELETE", "ALTER")
        ))
        self.assertFalse(connection.committed)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.autocommit)
        self.assertTrue(connection.closed)

    def test_missing_tampered_and_bearer_cookies_stay_logged_out(self):
        opened = []
        cursor = FakeCursor(None)
        handler, connection = build(cursor, opened=opened)
        with self.assertRaises(HTTPException) as missing:
            handler(Request({}))
        self.assertEqual(missing.exception.status_code, 401)
        self.assertEqual(opened, [])

        with self.assertRaises(HTTPException) as tampered:
            handler(Request({"stroyka_session": "tampered"}))
        self.assertEqual(tampered.exception.status_code, 401)
        self.assertEqual(tampered.exception.detail, "Сессия недействительна. Войдите заново.")
        self.assertFalse(connection.committed)
        self.assertTrue(connection.rolled_back)

    def test_two_factor_session_without_confirmation_is_rejected(self):
        cursor = FakeCursor({
            "id": 3,
            "role": "директор",
            "company_id": 4,
            "active": True,
            "auth_session_two_factor_passed": False,
        })
        handler, connection = build(cursor, opened=[])
        with self.assertRaises(HTTPException) as raised:
            handler(Request({"stroyka_session": "director-cookie"}))
        self.assertEqual(raised.exception.status_code, 401)
        self.assertIn("2FA", raised.exception.detail)
        self.assertFalse(connection.committed)

    def test_confirmed_director_keeps_the_company_from_the_session(self):
        cursor = FakeCursor({
            "id": 3,
            "name": "Мария",
            "role": "директор",
            "company_id": 9,
            "active": True,
            "auth_session_two_factor_passed": True,
        })
        handler, _connection = build(cursor, opened=[])
        result = handler(Request({"stroyka_session": "director-cookie"}))
        self.assertEqual(result["companyId"], 9)
        self.assertEqual(result["role"], "директор")
        self.assertNotIn("authToken", result)

    def test_user_without_a_role_is_not_invented(self):
        cursor = FakeCursor({
            "id": 8,
            "name": "Без роли",
            "role": "",
            "company_id": 4,
            "active": True,
        })
        handler, connection = build(cursor, opened=[])
        with self.assertRaises(HTTPException) as raised:
            handler(Request({"stroyka_session": "cookie"}))
        self.assertEqual(raised.exception.status_code, 401)
        self.assertFalse(connection.committed)


if __name__ == "__main__":
    unittest.main()
