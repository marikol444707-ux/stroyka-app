import unittest

from backend.features.online_status.routes import register_online_status_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def _register(self, method, path):
        def decorator(func):
            self.routes[(method, path)] = func
            return func

        return decorator


class OnlineStatusRouteTests(unittest.TestCase):
    def build_app(self):
        app = FakeApp()
        storage = {}
        register_online_status_module(app, {
            "get_current_user": lambda: {},
            "online_users": storage,
        })
        return app, storage

    def test_registers_original_route_contract(self):
        app, _storage = self.build_app()
        self.assertEqual(set(app.routes), {
            ("POST", "/online"),
            ("GET", "/online"),
        })

    def test_update_online_stores_current_user_status(self):
        app, storage = self.build_app()
        result = app.routes[("POST", "/online")](
            {"lastSeen": "2026-07-17T12:00:00", "page": "projects"},
            current_user={"id": 7, "name": "Иван", "role": "прораб"},
        )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(storage["7"], {
            "userId": 7,
            "userName": "Иван",
            "userRole": "прораб",
            "lastSeen": "2026-07-17T12:00:00",
            "page": "projects",
        })

    def test_update_without_user_id_does_not_create_status(self):
        app, storage = self.build_app()
        result = app.routes[("POST", "/online")](
            {"lastSeen": "now", "page": "dashboard"},
            current_user={"name": "Без id"},
        )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(storage, {})

    def test_get_online_returns_all_stored_statuses(self):
        app, storage = self.build_app()
        storage["3"] = {"userId": 3, "userName": "Мастер"}
        storage["5"] = {"userId": 5, "userName": "Прораб"}
        result = app.routes[("GET", "/online")](_current_user={"id": 1})
        self.assertEqual(result, list(storage.values()))


if __name__ == "__main__":
    unittest.main()
