import unittest

from backend.features.online_presence import routes
from backend.features.online_presence.routes import register_online_presence_module


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


class OnlinePresenceRoutesTest(unittest.TestCase):
    def setUp(self):
        routes.online_users.clear()
        self.app = FakeApp()
        register_online_presence_module(self.app, {"get_current_user": lambda: {}})

    def test_registers_same_urls(self):
        self.assertIn(("POST", "/online"), self.app.routes)
        self.assertIn(("GET", "/online"), self.app.routes)

    def test_post_stores_presence_and_get_returns_it(self):
        post = self.app.routes[("POST", "/online")]
        get = self.app.routes[("GET", "/online")]
        result = post(
            {"lastSeen": "2026-07-27T12:00:00", "page": "/app"},
            current_user={"id": 42, "name": "Тест", "role": "директор"},
        )
        self.assertEqual(result, {"ok": True})
        listed = get(_current_user={"id": 1})
        self.assertEqual(listed, [{
            "userId": 42,
            "userName": "Тест",
            "userRole": "директор",
            "lastSeen": "2026-07-27T12:00:00",
            "page": "/app",
        }])

    def test_post_without_user_id_stores_nothing(self):
        post = self.app.routes[("POST", "/online")]
        result = post({"page": "/app"}, current_user={})
        self.assertEqual(result, {"ok": True})
        self.assertEqual(routes.online_users, {})


if __name__ == "__main__":
    unittest.main()
