import unittest

from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from backend.features.project_chat.routes import register_project_chat_module


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
        self.committed = False
        self.closed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def build(cursor, access_calls):
    app = FakeApp()
    connection = FakeConnection(cursor)

    def require_project_access(user, project_name):
        access_calls.append((user.get("id"), project_name))
        if project_name == "чужой":
            raise HTTPException(status_code=403, detail="Нет доступа к объекту")

    register_project_chat_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "require_project_access": require_project_access,
        "require_csrf_for_cookie_mutation": lambda: None,
    })
    return app, connection


class ProjectChatRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor(), [])
        self.assertIn(("GET", "/project-chat/{project_name}"), app.routes)
        self.assertIn(("POST", "/project-chat"), app.routes)

    def test_get_checks_access_before_reading(self):
        calls = []
        app, _conn = build(FakeCursor(rows=[]), calls)
        app.routes[("GET", "/project-chat/{project_name}")]("Объект", current_user={"id": 42})
        self.assertEqual(calls, [(42, "Объект")])

    def test_foreign_project_is_rejected_before_any_query(self):
        calls = []
        cursor = FakeCursor()
        app, _conn = build(cursor, calls)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/project-chat")]({"projectName": "чужой", "text": "привет"}, current_user={"id": 42})
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(cursor.calls, [])

    def test_post_csrf_dependency_is_enforced_but_get_remains_readable(self):
        cursor = FakeCursor(row=(15,))
        connection = FakeConnection(cursor)
        app = FastAPI()

        def get_current_user():
            return {"id": 42, "name": "Тест", "role": "прораб"}

        def csrf_guard(
            x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
        ):
            if x_csrf_token != "good-token":
                raise HTTPException(status_code=403, detail="CSRF token missing or invalid")

        register_project_chat_module(app, {
            "get_db": lambda: connection,
            "get_current_user": get_current_user,
            "require_project_access": lambda *_args, **_kwargs: None,
            "require_csrf_for_cookie_mutation": csrf_guard,
        })
        client = TestClient(app)

        self.assertEqual(200, client.get("/project-chat/Объект").status_code)
        self.assertEqual(
            403,
            client.post("/project-chat", json={"projectName": "Объект", "text": "привет"}).status_code,
        )
        self.assertEqual(
            403,
            client.post(
                "/project-chat",
                headers={"X-CSRF-Token": "bad-token"},
                json={"projectName": "Объект", "text": "привет"},
            ).status_code,
        )
        response = client.post(
            "/project-chat",
            headers={"X-CSRF-Token": "good-token"},
            json={"projectName": "Объект", "text": "привет"},
        )
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["ok"])

    def test_post_stores_author_snapshot(self):
        calls = []
        cursor = FakeCursor(row=(15,))
        app, connection = build(cursor, calls)
        result = app.routes[("POST", "/project-chat")](
            {"projectName": "Объект", "text": "привет", "photoUrl": ""},
            current_user={"id": 42, "name": "Тест", "role": "прораб"},
        )
        self.assertEqual(result, {"id": 15, "ok": True})
        self.assertTrue(connection.committed)
        sql, params = cursor.calls[0]
        self.assertIn("INSERT INTO project_chat", sql)
        self.assertEqual(params, ("Объект", 42, "Тест", "прораб", "привет", ""))


if __name__ == "__main__":
    unittest.main()
