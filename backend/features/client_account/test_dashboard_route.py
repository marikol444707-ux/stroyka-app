import unittest

from backend.features.client_account import routes


class FakeApp:
    def __init__(self):
        self.handlers = {}

    def get(self, path, **_kwargs):
        def register(function):
            self.handlers[("GET", path)] = function
            return function
        return register


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.current = None

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self.current = []

    def fetchall(self):
        return []

    def fetchone(self):
        return None

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def close(self):
        pass


def register_handlers(connection):
    app = FakeApp()

    def require_roles(*roles_requested):
        return lambda: {"id": 1, "role": roles_requested[0] if roles_requested else ""}

    routes.register_client_account_routes(app, {
        "get_db": lambda: connection,
        "require_roles": require_roles,
    })
    return app.handlers


class DashboardRouteTests(unittest.TestCase):
    def test_dashboard_query_has_no_hardcoded_company_1(self):
        conn = FakeConnection()
        handlers = register_handlers(conn)
        handlers[("GET", "/account/dashboard")](current_user={"id": 10, "role": "account_owner", "platformAccountId": 3})
        sql = " ".join(call[0] for call in conn.cursor_instance.calls)
        self.assertNotIn("c.id<>1", sql)


if __name__ == '__main__':
    unittest.main()
