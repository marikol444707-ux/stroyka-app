import os
import subprocess
import sys
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.features.estimate_chat.routes import register_estimate_chat_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._route("GET", path)

    def post(self, path):
        return self._route("POST", path)

    def delete(self, path):
        return self._route("DELETE", path)

    def _route(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler

        return decorator


class FakeCursor:
    def __init__(self, fetchone_values=(), rows=()):
        self.fetchone_values = list(fetchone_values)
        self.rows = list(rows)
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.fetchone_values.pop(0) if self.fetchone_values else None

    def fetchall(self):
        return list(self.rows)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self, cursor_factory=None):
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class EstimateChatRouteTests(unittest.TestCase):
    def test_module_imports_from_backend_working_directory(self):
        backend_dir = Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = ""
        env["PYTHONPYCACHEPREFIX"] = "/tmp/stroyka-pycache"

        result = subprocess.run(
            [sys.executable, "-c", "from features.estimate_chat.routes import register_estimate_chat_module"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def _register(self, connection, *, actors=None, ai_answer="Ответ ИИ"):
        app = FakeApp()
        calls = {"context": [], "visibility": [], "parent": [], "ai": []}
        company_actors = list(actors or [{
            "id": 9,
            "companyId": 4,
            "role": "директор",
            "assignedProjects": [],
            "assignedPackages": [],
        }])

        def resolve_context(cur, user, requested_company_id, action_mode, **kwargs):
            calls["context"].append((cur, user, requested_company_id, action_mode, kwargs))
            if action_mode == "write" and kwargs.get("x_company_mode") == "all_companies":
                raise HTTPException(status_code=409, detail="Выберите одну компанию")
            return {
                "mode": kwargs.get("x_company_mode") or "company",
                "companyId": int(kwargs.get("x_company_id") or 4),
            }

        def visibility_filter(company_memberships, *args, **kwargs):
            calls["visibility"].append((company_memberships, args, kwargs))
            company_ids = [int(actor["companyId"]) for actor in company_memberships]
            clauses = " OR ".join("e.company_id=%s" for _ in company_ids) or "FALSE"
            return "(" + clauses + ")", company_ids

        def resolve_parent(cur, actor, estimate_id, **kwargs):
            calls["parent"].append((cur, actor, estimate_id, kwargs))
            return {
                "id": estimate_id,
                "companyId": int(actor["companyId"]),
                "projectId": 17,
                "projectName": "Лицей",
                "workPackage": "Основная",
            }

        def generate_answer(prompt, instructions):
            calls["ai"].append((prompt, instructions))
            return ai_answer

        register_estimate_chat_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, _context: company_actors,
            "estimate_visibility_filter": visibility_filter,
            "resolve_estimate_parent": resolve_parent,
            "project_document_roles": (
                "директор",
                "зам_директора",
                "бухгалтер",
                "главный_инженер",
                "сметчик",
                "прораб",
                "мастер",
                "бригадир",
                "субподрядчик",
                "заказчик",
            ),
            "full_view_roles": ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик"),
            "package_limit_roles": ("мастер", "бригадир", "субподрядчик"),
            "active_only_roles": ("прораб", "мастер", "бригадир", "субподрядчик"),
            "customer_roles": ("заказчик",),
            "package_optional_roles": ("прораб",),
            "worker_execution_roles": ("мастер", "бригадир", "субподрядчик"),
            "clear_roles": ("директор", "зам_директора", "бухгалтер", "прораб", "главный_инженер", "сметчик"),
            "generate_answer": generate_answer,
        })
        return app, calls

    @staticmethod
    def _estimate_row(company_id=4, estimate_id=7):
        return {
            "id": estimate_id,
            "company_id": company_id,
            "project_id": 17,
            "project_name": "Лицей",
            "work_package": "Основная",
            "is_template": False,
        }

    def test_history_verifies_visible_parent_before_reading_messages(self):
        cursor = FakeCursor(
            fetchone_values=[self._estimate_row()],
            rows=[{"id": 11, "role": "user", "content": "Вопрос", "created_at": "2026-07-11"}],
        )
        connection = FakeConnection(cursor)
        app, calls = self._register(connection)

        response = app.routes[("GET", "/estimates/{estimate_id}/chat-history")](
            7,
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "system_owner"},
        )

        self.assertEqual(calls["context"][0][3], "read")
        self.assertEqual(calls["parent"][0][1]["companyId"], 4)
        self.assertIn("FROM estimates e", cursor.calls[0][0])
        self.assertIn("FROM estimate_chat_messages", cursor.calls[1][0])
        self.assertEqual(response, [{"id": 11, "role": "user", "content": "Вопрос", "createdAt": "2026-07-11"}])
        self.assertEqual(connection.commits, 0)
        self.assertTrue(connection.closed)

    def test_direct_history_returns_404_without_visible_parent(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app, calls = self._register(connection)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/estimates/{estimate_id}/chat-history")](
                7,
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 9, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(calls["parent"], [])
        self.assertEqual(len(cursor.calls), 1)

    def test_effective_worker_role_cannot_read_chat_in_all_companies(self):
        cursor = FakeCursor(fetchone_values=[self._estimate_row(company_id=5)])
        connection = FakeConnection(cursor)
        app, calls = self._register(connection, actors=[
            {"id": 9, "companyId": 4, "role": "директор"},
            {"id": 9, "companyId": 5, "role": " мастер ", "assignedProjects": ["Лицей"], "assignedPackages": ["Основная"]},
        ])

        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/estimates/{estimate_id}/chat-history")](
                7,
                x_company_id=None,
                x_company_mode="all_companies",
                current_user={"id": 9, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(calls["parent"][0][1]["companyId"], 5)
        self.assertEqual(calls["parent"][0][1]["role"], "мастер")
        self.assertEqual(len(cursor.calls), 1)

    def test_all_companies_cannot_send_message(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app, calls = self._register(connection)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/estimate-chat")](
                {"estimateId": 7, "message": "Вопрос"},
                x_company_id=None,
                x_company_mode="all_companies",
                current_user={"id": 9, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(calls["context"][0][3], "write")
        self.assertEqual(cursor.calls, [])
        self.assertEqual(connection.commits, 0)

    def test_send_verifies_parent_then_stores_user_and_assistant_messages(self):
        cursor = FakeCursor(fetchone_values=[
            self._estimate_row(),
            {"id": 21, "created_at": "2026-07-11"},
            {"id": 22, "created_at": "2026-07-11"},
        ])
        connection = FakeConnection(cursor)
        app, calls = self._register(connection)

        response = app.routes[("POST", "/estimate-chat")](
            {
                "estimateId": 7,
                "message": "  Сколько стоит раздел?  ",
                "context": "Смета",
                "history": [{"role": "assistant", "content": "Ранее"}],
            },
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "директор"},
        )

        self.assertEqual(calls["context"][0][3], "write")
        self.assertEqual(calls["parent"][0][2], 7)
        self.assertTrue(calls["parent"][0][3]["for_update"])
        self.assertIn("INSERT INTO estimate_chat_messages", cursor.calls[1][0])
        self.assertEqual(cursor.calls[1][1], (7, "user", "Сколько стоит раздел?"))
        self.assertEqual(cursor.calls[2][1], (7, "assistant", "Ответ ИИ"))
        self.assertIn("КОНТЕКСТ СМЕТЫ", calls["ai"][0][0])
        self.assertEqual(response, {"response": "Ответ ИИ", "userMessageId": 21, "assistantMessageId": 22})
        self.assertEqual(connection.commits, 2)

    def test_clear_requires_effective_clear_role(self):
        cursor = FakeCursor(fetchone_values=[self._estimate_row()])
        connection = FakeConnection(cursor)
        app, calls = self._register(connection, actors=[{
            "id": 20,
            "companyId": 4,
            "role": "заказчик",
            "assignedProjects": ["Лицей"],
        }])

        with self.assertRaises(HTTPException) as raised:
            app.routes[("DELETE", "/estimates/{estimate_id}/chat-history")](
                7,
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 20, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(calls["parent"][0][1]["role"], "заказчик")
        self.assertFalse(any("DELETE FROM estimate_chat_messages" in sql for sql, _params in cursor.calls))
        self.assertEqual(connection.commits, 0)

    def test_clear_selected_company_deletes_only_verified_parent_chat(self):
        cursor = FakeCursor(fetchone_values=[self._estimate_row()])
        connection = FakeConnection(cursor)
        app, calls = self._register(connection)

        response = app.routes[("DELETE", "/estimates/{estimate_id}/chat-history")](
            7,
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "директор"},
        )

        self.assertEqual(response, {"ok": True})
        self.assertEqual(calls["context"][0][3], "write")
        self.assertTrue(calls["parent"][0][3]["for_update"])
        self.assertIn("DELETE FROM estimate_chat_messages", cursor.calls[1][0])
        self.assertEqual(cursor.calls[1][1], (7,))
        self.assertEqual(connection.commits, 1)


if __name__ == "__main__":
    unittest.main()
