import unittest

from fastapi import HTTPException

from backend.features.supplier_documents.routes import register_supplier_documents_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

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


def build(cursor, own_ids=(), related=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_supplier_documents_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "current_supplier_ids": lambda cur, user: list(own_ids),
        "supplier_related_ids": lambda cur, sid: related or [sid],
    })
    return app, connection


class SupplierDocumentsTest(unittest.TestCase):
    def test_all_urls_registered(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/supplier-documents"), ("POST", "/supplier-documents"),
                    ("DELETE", "/supplier-documents/{id}")]:
            self.assertIn(key, app.routes)

    def test_supplier_reads_only_own_documents(self):
        cursor = FakeCursor(rows=[])
        app, _conn = build(cursor, own_ids=[5])
        app.routes[("GET", "/supplier-documents")](supplier_id=None, current_user={"role": "поставщик"})
        self.assertIn("WHERE supplier_id = ANY(%s)", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], ([5],))

    def test_read_widens_to_duplicate_group_for_admin(self):
        cursor = FakeCursor(rows=[])
        app, _conn = build(cursor, related=[7, 99])
        app.routes[("GET", "/supplier-documents")](supplier_id=7, current_user={"role": "директор"})
        self.assertEqual(cursor.calls[0][1], ([7, 99],))

    def test_supplier_cannot_upload_for_foreign_card(self):
        app, connection = build(FakeCursor(), own_ids=[5])
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/supplier-documents")](
                {"supplierId": 9, "title": "Договор"}, current_user={"role": "поставщик"}
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertFalse(connection.committed)

    def test_foreign_role_cannot_delete(self):
        app, _conn = build(FakeCursor())
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("DELETE", "/supplier-documents/{id}")](id=1, current_user={"role": "мастер"})
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
