import json
import unittest

from fastapi import HTTPException

from backend.features.company_messages.routes import register_company_messages_module


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
    def __init__(self, rows=(), row=None, rowcount=0):
        self.rows = list(rows)
        self.row = row
        self.rowcount = rowcount
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
        self.cursor_factory = None
        self.committed = False
        self.closed = False

    def cursor(self, cursor_factory=None):
        self.cursor_factory = cursor_factory
        return self.cursor_value

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class CompanyMessagesRouteTests(unittest.TestCase):
    def _register(self, connection, context=None, effective_actor=None):
        app = FakeApp()
        resolver_calls = []

        def resolve_context(cur, user, requested_company_id, action_mode, **kwargs):
            resolver_calls.append((cur, user, requested_company_id, action_mode, kwargs))
            return context or {
                "mode": "company",
                "companyId": 4,
                "effectiveRole": "директор",
                "requestedMode": "company",
            }

        default_actor = {
            "id": 9,
            "name": "Директор выбранной компании",
            "role": "директор",
            "companyId": 4,
        }
        register_company_messages_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_request_company_context": resolve_context,
            "effective_company_user": lambda _user, _context: (
                default_actor if effective_actor is None else effective_actor
            ),
            "platform_staff_roles": (),
            "client_account_roles": (),
        })
        return app, resolver_calls

    def test_list_scopes_selected_company_and_marks_safely_derived_legacy_rows(self):
        cursor = FakeCursor(rows=(
            {
                "id": 1,
                "company_id": 4,
                "chat_type": "company",
                "project_id": None,
                "author_id": 9,
                "author_name": "Иван",
                "author_role": "директор",
                "text": "Новое",
                "photo_url": "",
                "created_at": "2026-07-11",
                "read_by": [9],
            },
            {
                "id": 2,
                "company_id": None,
                "chat_type": "company",
                "project_id": None,
                "author_id": 8,
                "author_name": "Петр",
                "author_role": "прораб",
                "text": "Старое",
                "photo_url": "",
                "created_at": "2026-07-10",
                "read_by": "[8]",
            },
        ))
        connection = FakeConnection(cursor)
        app, resolver_calls = self._register(connection)

        response = app.routes[("GET", "/messages")](
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "директор"},
        )

        self.assertEqual(resolver_calls[0][3], "read")
        self.assertEqual(resolver_calls[0][4]["x_company_id"], "4")
        sql, params = cursor.calls[0]
        self.assertRegex(sql, r"messages\.company_id=%s\s+OR \(\s+messages\.company_id IS NULL\s+AND EXISTS")
        self.assertIn("legacy_author.id=messages.author_id", sql)
        self.assertIn("legacy_author.company_id=%s", sql)
        self.assertIn("FROM user_company_roles other_membership", sql)
        self.assertIn("other_membership.company_id<>%s", sql)
        self.assertNotIn("OR messages.company_id IS NULL)", sql)
        self.assertEqual(params, (4, 4, 4))
        self.assertEqual(response[0]["companyId"], 4)
        self.assertFalse(response[0]["legacyUnscoped"])
        self.assertIsNone(response[1]["companyId"])
        self.assertTrue(response[1]["legacyUnscoped"])
        self.assertEqual(response[1]["readBy"], [8])
        self.assertTrue(connection.closed)

    def test_list_rejects_all_companies_before_query(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app, _ = self._register(connection, context={
            "mode": "all_companies",
            "companyId": None,
            "companyIds": [4, 5],
        })

        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/messages")](
                x_company_id=None,
                x_company_mode="all_companies",
                current_user={"id": 9, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(cursor.calls, [])

    def test_create_stores_resolved_company_and_server_actor(self):
        inserted = {
            "id": 3,
            "company_id": 4,
            "chat_type": "company",
            "project_id": None,
            "author_id": 9,
            "author_name": "Директор выбранной компании",
            "author_role": "директор",
            "text": "Сообщение",
            "photo_url": "",
            "created_at": "2026-07-11",
            "read_by": [9],
        }
        cursor = FakeCursor(row=inserted)
        connection = FakeConnection(cursor)
        app, resolver_calls = self._register(connection)

        response = app.routes[("POST", "/messages")](
            {
                "chatType": "company",
                "projectId": None,
                "authorId": 999,
                "authorName": "Подмена",
                "authorRole": "system_owner",
                "text": "Сообщение",
                "photoUrl": "",
            },
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "name": "Глобальное имя", "role": "директор"},
        )

        self.assertEqual(resolver_calls[0][3], "create")
        sql, params = cursor.calls[0]
        self.assertIn("INSERT INTO messages (company_id,chat_type,project_id,author_id,author_name,author_role,text,photo_url,read_by)", sql)
        self.assertEqual(params[:6], (4, "company", None, 9, "Директор выбранной компании", "директор"))
        self.assertEqual(json.loads(params[-1]), [9])
        self.assertEqual(response["companyId"], 4)
        self.assertEqual(response["author_name"], "Директор выбранной компании")
        self.assertTrue(connection.committed)

    def test_create_rejects_project_payload_on_company_chat_route(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app, _ = self._register(connection)

        for data in (
            {"chatType": "project", "text": "x"},
            {"chatType": "company", "projectId": 17, "text": "x"},
        ):
            with self.subTest(data=data), self.assertRaises(HTTPException) as raised:
                app.routes[("POST", "/messages")](
                    data,
                    x_company_id="4",
                    x_company_mode="company",
                    current_user={"id": 9, "role": "директор"},
                )
            self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(cursor.calls, [])

    def test_create_rejects_unresolved_server_actor_before_insert(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app, _ = self._register(connection, effective_actor={
            "id": None,
            "name": "",
            "role": "директор",
            "companyId": 4,
        })

        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/messages")](
                {"chatType": "company", "text": "Сообщение"},
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 9, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(cursor.calls, [])
        self.assertFalse(connection.committed)

    def test_mutations_reject_all_companies_before_message_sql(self):
        for method, path, data in (
            ("POST", "/messages", {"chatType": "company", "text": "x"}),
            ("POST", "/messages/mark-read", {"chatType": "company"}),
        ):
            with self.subTest(path=path):
                cursor = FakeCursor()
                connection = FakeConnection(cursor)
                app, _ = self._register(connection, context={
                    "mode": "all_companies",
                    "companyId": None,
                    "companyIds": [4, 5],
                })

                with self.assertRaises(HTTPException) as raised:
                    app.routes[(method, path)](
                        data,
                        x_company_id=None,
                        x_company_mode="all_companies",
                        current_user={"id": 9, "role": "директор"},
                    )

                self.assertEqual(raised.exception.status_code, 400)
                self.assertEqual(cursor.calls, [])
                self.assertFalse(connection.committed)

    def test_mark_read_scopes_company_and_ignores_claimed_user(self):
        cursor = FakeCursor(rowcount=3)
        connection = FakeConnection(cursor)
        app, resolver_calls = self._register(connection)

        response = app.routes[("POST", "/messages/mark-read")](
            {"userId": 999, "chatType": "company"},
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "директор"},
        )

        self.assertEqual(resolver_calls[0][3], "update")
        sql, params = cursor.calls[0]
        self.assertRegex(sql, r"messages\.company_id=%s\s+OR \(\s+messages\.company_id IS NULL\s+AND EXISTS")
        self.assertIn("legacy_author.id=messages.author_id", sql)
        self.assertIn("legacy_author.company_id=%s", sql)
        self.assertIn("FROM user_company_roles other_membership", sql)
        self.assertIn("other_membership.company_id<>%s", sql)
        self.assertNotIn("OR messages.company_id IS NULL)", sql)
        self.assertIn("chat_type=%s", sql)
        self.assertEqual(params[1:5], (4, 4, 4, "company"))
        self.assertEqual(json.loads(params[0]), [9])
        self.assertEqual(json.loads(params[-1]), [9])
        self.assertEqual(response, {"ok": True, "updated": 3})
        self.assertTrue(connection.committed)


if __name__ == "__main__":
    unittest.main()
