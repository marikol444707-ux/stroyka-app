import unittest

from fastapi import HTTPException

from backend.features.master_profiles.routes import register_master_profiles_module


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
        self.closed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def close(self):
        self.closed = True


def build(cursor, projects=("Объект",)):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_master_profiles_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "finance_roles": ("директор", "бухгалтер"),
        "worker_execution_roles": ("мастер",),
        "user_project_names": lambda user: list(projects),
    })
    return app, connection


PROFILE = {"id": 1, "userId": 42, "fullName": "Мастер Тест", "passport": "1234",
           "inn": "5678", "contractType": "ГПХ", "bankAccount": "408", "bankName": "Банк",
           "phone": "+7", "specialization": "электрик", "ogrnip": "9", "profileCompleted": True}


class MasterProfilesRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/master-profiles"), ("GET", "/master-profile/{user_id}"), ("POST", "/master-profile")]:
            self.assertIn(key, app.routes)

    def test_foreman_list_hides_sensitive_fields(self):
        app, _conn = build(FakeCursor(rows=[dict(PROFILE)]))
        rows = app.routes[("GET", "/master-profiles")](current_user={"id": 1, "role": "прораб"})
        self.assertEqual(rows[0]["fullName"], "Мастер Тест")
        for hidden in ("passport", "inn", "bankAccount", "bankName", "ogrnip"):
            self.assertNotIn(hidden, rows[0])

    def test_finance_list_keeps_all_fields(self):
        app, _conn = build(FakeCursor(rows=[dict(PROFILE)]))
        rows = app.routes[("GET", "/master-profiles")](current_user={"id": 1, "role": "директор"})
        self.assertEqual(rows[0]["passport"], "1234")

    def test_unknown_role_gets_empty_list(self):
        cursor = FakeCursor(rows=[dict(PROFILE)])
        app, _conn = build(cursor)
        rows = app.routes[("GET", "/master-profiles")](current_user={"id": 1, "role": "заказчик"})
        self.assertEqual(rows, [])
        self.assertEqual(cursor.calls, [])

    def test_profile_detail_forbidden_for_stranger(self):
        app, _conn = build(FakeCursor())
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("GET", "/master-profile/{user_id}")](user_id=42, current_user={"id": 1, "role": "мастер"})
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
