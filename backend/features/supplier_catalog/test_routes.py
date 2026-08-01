import unittest

from fastapi import HTTPException

from backend.features.supplier_catalog.routes import register_supplier_catalog_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

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
    def __init__(self, rows=(), fetchone_results=()):
        self.rows = list(rows)
        self.fetchone_results = list(fetchone_results)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.fetchone_results.pop(0) if self.fetchone_results else None

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def build(cursor, own_ids=()):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_supplier_catalog_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "current_supplier_ids": lambda cur, user: list(own_ids),
        "supply_roles": ("снабженец",),
        "warehouse_roles": ("кладовщик",),
        "finance_roles": ("директор",),
        "worker_execution_roles": ("мастер",),
    })
    return app, connection


class SupplierCatalogTest(unittest.TestCase):
    def test_all_urls_registered(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/supplier-catalog"), ("POST", "/supplier-catalog"),
                    ("PUT", "/supplier-catalog/{id}"), ("DELETE", "/supplier-catalog/{id}")]:
            self.assertIn(key, app.routes)

    def test_supplier_sees_only_own_catalog(self):
        cursor = FakeCursor(rows=[])
        app, _conn = build(cursor, own_ids=[5])
        app.routes[("GET", "/supplier-catalog")](supplier_id=None, current_user={"role": "поставщик"})
        self.assertIn("WHERE supplier_id = ANY(%s)", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], ([5],))

    def test_worker_gets_empty_catalog(self):
        cursor = FakeCursor()
        app, _conn = build(cursor)
        result = app.routes[("GET", "/supplier-catalog")](supplier_id=None, current_user={"role": "мастер"})
        self.assertEqual(result, [])
        self.assertEqual(cursor.calls, [])

    def test_supplier_cannot_write_foreign_catalog(self):
        app, connection = build(FakeCursor(), own_ids=[5])
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/supplier-catalog")](
                {"supplierId": 9, "materialName": "Цемент"}, current_user={"role": "поставщик"}
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertFalse(connection.committed)

    def test_price_update_targets_exact_row(self):
        cursor = FakeCursor(fetchone_results=[(5,)])
        app, connection = build(cursor, own_ids=[5])
        result = app.routes[("PUT", "/supplier-catalog/{id}")](
            id=3, data={"price": 120, "inStock": True}, current_user={"role": "поставщик"}
        )
        self.assertEqual(result, {"ok": True})
        update = [c for c in cursor.calls if c[0].startswith("UPDATE supplier_catalog")][0]
        self.assertEqual(update[1][-1], 3)
        self.assertTrue(connection.committed)


if __name__ == "__main__":
    unittest.main()
