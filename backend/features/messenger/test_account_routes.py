import unittest
from unittest.mock import patch

from fastapi import HTTPException

from . import routes as routes_module


register_messenger_module = routes_module.register_messenger_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def patch(self, path):
        return self._register("PATCH", path)

    def _register(self, method, path):
        def decorator(func):
            self.routes[(method, path)] = func
            return func
        return decorator


class FakeCursor:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.current = None
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self.current = self.responses.pop(0) if self.responses else None

    def fetchall(self):
        return list(self.current or [])

    def fetchone(self):
        if isinstance(self.current, list):
            return self.current[0] if self.current else None
        return self.current

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
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


def actor(company_id=4, role="director"):
    return {"companyId": company_id, "company_id": company_id, "role": role}


class MessengerAccountRouteTests(unittest.TestCase):
    def build_app(self, cursor, *, mode="company", actors=None):
        app = FakeApp()
        conn = FakeConnection(cursor)
        selected_actors = list(actors or [actor()])

        def resolve_context(_cur, _user, requested_company_id, action_mode, **kwargs):
            selected_company_id = requested_company_id
            if selected_company_id is None and kwargs.get("x_company_id"):
                selected_company_id = int(kwargs["x_company_id"])
            if selected_company_id is None and mode == "company":
                selected_company_id = selected_actors[0]["companyId"]
            return {
                "mode": mode,
                "companyId": selected_company_id,
                "companyIds": [item["companyId"] for item in selected_actors],
                "actionMode": action_mode,
            }

        dependencies = {
            "get_db": lambda: conn,
            "get_current_user": lambda: {},
            "require_roles": lambda *_roles: lambda: {},
            "create_warehouse_invoice_record": lambda *_args, **_kwargs: None,
            "warehouse_roles": (),
            "leadership_roles": ("director", "deputy"),
            "supply_work_package": lambda *_args, **_kwargs: "",
            "hash_password": lambda value: value,
            "prepare_user_access_scope": lambda value: value,
            "safe_project_list": lambda value: value,
            "role_requires_2fa": lambda _role: False,
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, _context: selected_actors,
            "user_project_names": lambda _user: [],
        }
        with patch.object(routes_module, "ensure_messenger_schema"):
            register_messenger_module(app, dependencies)
        return app, conn

    def test_list_filters_every_owner_lookup_by_selected_company(self):
        cursor = FakeCursor([[
            {
                "id": 9,
                "provider": "max",
                "user_id": 12,
                "staff_id": None,
                "external_user_id": "max-12",
                "chat_id": "chat-12",
                "display_name": "Employee",
                "verified_at": None,
                "enabled": True,
                "employee_name": "Employee",
                "employee_role": "master",
                "company_ids": [4],
            }
        ]])
        app, _conn = self.build_app(cursor)

        result = app.routes[("GET", "/messenger-accounts")]("4", "company", {"id": 1})

        self.assertEqual(result["items"][0]["companyIds"], [4])
        self.assertIn("visible_ucr.company_id=ANY(%s)", cursor.calls[0][0])
        self.assertIn("visible_staff.company_id=ANY(%s)", cursor.calls[0][0])
        self.assertIn("ma.staff_id IS NULL", cursor.calls[0][0])
        self.assertIn("ma.user_id IS NULL", cursor.calls[0][0])
        self.assertIn("COALESCE(u.active,TRUE)=TRUE", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], ([4], [4], [4], [4], [4]))

    def test_list_all_companies_keeps_only_leadership_companies(self):
        cursor = FakeCursor([[]])
        app, _conn = self.build_app(
            cursor,
            mode="all_companies",
            actors=[actor(4), actor(8, "master"), actor(9, "deputy")],
        )

        app.routes[("GET", "/messenger-accounts")](None, "all_companies", {"id": 1})

        self.assertEqual(cursor.calls[0][1], ([4, 9], [4, 9], [4, 9], [4, 9], [4, 9]))

    def test_create_requires_target_membership_in_selected_company(self):
        cursor = FakeCursor([
            {"id": 12, "name": "Employee", "role": "master", "company_ids": [4]},
            None,
            [],
            {
                "id": 9,
                "provider": "max",
                "user_id": 12,
                "staff_id": None,
                "external_user_id": "max-12",
                "chat_id": "chat-12",
                "display_name": "Employee",
                "verified_at": None,
                "enabled": True,
            },
        ])
        app, conn = self.build_app(cursor)

        result = app.routes[("POST", "/messenger-accounts")](
            {"provider": "max", "userId": 12, "externalUserId": "max-12", "chatId": "chat-12"},
            "4",
            "company",
            {"id": 1},
        )

        self.assertEqual(cursor.calls[0][1], (12, 4))
        self.assertIn("ucr.company_id=%s", cursor.calls[0][0])
        self.assertIn("pg_advisory_xact_lock", cursor.calls[1][0])
        self.assertEqual(result["account"]["companyIds"], [4])
        self.assertTrue(conn.committed)

    def test_create_rejects_reassignment_of_existing_identity(self):
        cursor = FakeCursor([
            {"id": 12, "name": "Employee", "role": "master", "company_ids": [4]},
            None,
            [{"id": 9, "user_id": 11, "staff_id": None}],
        ])
        app, conn = self.build_app(cursor)

        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/messenger-accounts")](
                {"provider": "max", "userId": 12, "externalUserId": "max-11"},
                "4",
                "company",
                {"id": 1},
            )

        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(len(cursor.calls), 3)
        self.assertTrue(conn.rolled_back)

    def test_create_rejects_all_companies_before_target_query(self):
        cursor = FakeCursor()
        app, conn = self.build_app(cursor, mode="all_companies", actors=[actor(4), actor(9)])

        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/messenger-accounts")](
                {"provider": "max", "userId": 12, "externalUserId": "max-12"},
                None,
                "all_companies",
                {"id": 1},
            )

        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(cursor.calls, [])
        self.assertTrue(conn.rolled_back)


if __name__ == "__main__":
    unittest.main()
