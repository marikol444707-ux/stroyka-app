import unittest

from backend.features.pricelist_items.routes import PricelistItemModel, register_pricelist_items_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def post(self, path):
        return self._register("POST", path)

    def put(self, path):
        return self._register("PUT", path)

    def delete(self, path):
        return self._register("DELETE", path)

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator


class FakeCursor:
    def __init__(self, row=None):
        self.row = row
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.row

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, **_kwargs):
        return self._cursor

    def close(self):
        self.closed = True


def build(cursor):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_pricelist_items_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "manage_roles": ("директор",),
    })
    return app, connection


class PricelistItemsRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor())
        for key in [("POST", "/pricelist-items"), ("PUT", "/pricelist-items/{id}"), ("DELETE", "/pricelist-items/{id}")]:
            self.assertIn(key, app.routes)

    def test_create_returns_inserted_row(self):
        row = {"id": 5, "pricelistId": 2, "name": "Штукатурка", "unit": "м2", "price": 450.0,
               "category": "стены", "specialization": "отделка"}
        cursor = FakeCursor(row=row)
        app, _conn = build(cursor)
        result = app.routes[("POST", "/pricelist-items")](
            PricelistItemModel(pricelistId=2, name="Штукатурка", price=450), _current_user={}
        )
        self.assertEqual(result["name"], "Штукатурка")
        self.assertEqual(cursor.calls[0][1][:2], (2, "Штукатурка"))

    def test_update_and_delete_target_exact_id(self):
        cursor = FakeCursor()
        app, _conn = build(cursor)
        self.assertEqual(
            app.routes[("PUT", "/pricelist-items/{id}")](id=5, item=PricelistItemModel(pricelistId=2, name="Х", price=1), _current_user={}),
            {"ok": True},
        )
        self.assertEqual(cursor.calls[0][1][-1], 5)
        self.assertEqual(
            app.routes[("DELETE", "/pricelist-items/{id}")](id=5, _current_user={}),
            {"ok": True},
        )
        self.assertEqual(cursor.calls[1][1], (5,))


if __name__ == "__main__":
    unittest.main()
