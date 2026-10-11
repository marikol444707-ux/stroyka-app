"""Contract tests for the opt-in Jev QA read-only HTTP boundary."""
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from starlette.requests import Request

from backend.features.company_context.routes import register_company_context_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorate(fn):
            self.routes[path] = fn
            return fn
        return decorate


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []
        self.closed = False

    def execute(self, sql, params=None):
        self.queries.append((sql, params))

    def fetchone(self):
        return {"transaction_read_only": "on"}

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, rows):
        self.cursor_obj = FakeCursor(rows)
        self.autocommit = True  # matches backend.db.get_db()
        self.rolled_back = False
        self.closed = False

    def cursor(self, **kwargs):
        return self.cursor_obj

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def request(headers=()):
    return Request({"type": "http", "method": "GET",
                    "path": "/users/qa-readonly-context",
                    "headers": list(headers), "query_string": b""})


QA_ENV = {
    "JEV_QA_READONLY_AUTH_ENABLED": "1",
    "QA_ENVIRONMENT": "qa",
    "APP_PUBLIC_URL": "https://qa.example.test",
    "QA_ALLOWED_ORIGIN": "https://qa.example.test",
}


class QAEndpointTests(unittest.TestCase):
    def setUp(self):
        self.conn = FakeConnection([{
            "user_id": 9, "user_name": "QA", "user_email": "qa@example.test",
            "company_id": 5, "membership_id": 12, "role": "прораб",
        }])
        self.app = FakeApp()
        register_company_context_module(self.app, {
            "get_db": lambda: self.conn,
            "get_current_user": lambda: None,
        })
        self.endpoint = self.app.routes["/users/qa-readonly-context"]

    def test_disabled_by_default_without_database_access(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                self.endpoint(request())
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(self.conn.cursor_obj.queries, [])

    def test_enabled_flag_does_not_expose_route_on_production(self):
        for overrides in (
            {"APP_PUBLIC_URL": "https://stroyka26.pro",
             "QA_ALLOWED_ORIGIN": "https://stroyka26.pro"},
            {"APP_PUBLIC_URL": "https://qa.stroyka26.pro",
             "QA_ALLOWED_ORIGIN": "https://qa.stroyka26.pro"},
            {"QA_ENVIRONMENT": "production"},
            {"QA_ALLOWED_ORIGIN": "https://different.example.test"},
            {"APP_PUBLIC_URL": "http://qa.example.test"},
            {"APP_PUBLIC_URL": ""},
        ):
            with self.subTest(overrides=overrides):
                with patch.dict("os.environ", QA_ENV | overrides, clear=True):
                    with self.assertRaises(HTTPException) as raised:
                        self.endpoint(request())
                self.assertEqual(raised.exception.status_code, 404)
                self.assertEqual(self.conn.cursor_obj.queries, [])

    def test_verified_cookie_uses_readonly_transaction_and_rollback(self):
        with patch.dict("os.environ", QA_ENV, clear=True), patch(
            "backend.features.company_context.routes.build_cookie_session_authentication",
            return_value={"authenticationKind": "cookie_session", "sessionHash": "a" * 64},
        ):
            result = self.endpoint(request())
        self.assertEqual(result["user"]["companyId"], 5)
        self.assertIs(self.conn.autocommit, False, "QA auth must disable default autocommit")
        sql = [entry[0] for entry in self.conn.cursor_obj.queries]
        self.assertEqual(sql[0], "SET TRANSACTION READ ONLY")
        self.assertEqual(sql[1], "SHOW transaction_read_only")
        self.assertTrue(sql[2].lstrip().startswith("SELECT "))
        self.assertFalse(any("UPDATE " in q.upper() or "INSERT " in q.upper() for q in sql))
        self.assertTrue(self.conn.rolled_back)
        self.assertTrue(self.conn.closed)
        self.assertTrue(self.conn.cursor_obj.closed)

    def test_multiple_companies_are_denied_and_connection_closed(self):
        self.conn.cursor_obj.rows = self.conn.cursor_obj.rows * 2
        with patch.dict("os.environ", QA_ENV, clear=True), patch(
            "backend.features.company_context.routes.build_cookie_session_authentication",
            return_value={"authenticationKind": "cookie_session", "sessionHash": "a" * 64},
        ):
            with self.assertRaises(HTTPException) as raised:
                self.endpoint(request())
        self.assertEqual(raised.exception.status_code, 401)
        self.assertTrue(self.conn.rolled_back)
        self.assertTrue(self.conn.closed)

    def test_bad_cookie_rejected_before_database(self):
        from backend.auth import CookieSessionAuthenticationError
        with patch.dict("os.environ", QA_ENV, clear=True), patch(
            "backend.features.company_context.routes.build_cookie_session_authentication",
            side_effect=CookieSessionAuthenticationError("cookie_session_authentication_required"),
        ):
            with self.assertRaises(HTTPException) as raised:
                self.endpoint(request())
        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(self.conn.cursor_obj.queries, [])

    def test_authorization_header_is_rejected_before_database(self):
        with patch.dict("os.environ", QA_ENV, clear=True):
            with self.assertRaises(HTTPException) as raised:
                self.endpoint(request([(b"authorization", b"Bearer fake")]))
        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(self.conn.cursor_obj.queries, [])


if __name__ == "__main__":
    unittest.main()
