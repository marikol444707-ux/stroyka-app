import unittest

from fastapi import HTTPException

from backend.features.supplier_access.directory_routes import SupplierModel, register_supplier_directory_module


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
        self.rolled_back = False
        self.autocommit = True

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def row_get(row, key, index=None, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    if row is None:
        return default
    if index is not None:
        try:
            return row[index]
        except Exception:
            return default
    return default


def build(cursor, supplier_ids=(), find_match=None, alias_calls=None, audit_calls=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    alias_log = alias_calls if alias_calls is not None else []
    audit_log = audit_calls if audit_calls is not None else []
    register_supplier_directory_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "require_roles": lambda *roles: (lambda: None),
        "supply_roles": ("снабженец",),
        "warehouse_roles": ("кладовщик",),
        "finance_roles": ("директор",),
        "worker_execution_roles": ("мастер",),
        "leadership_roles": ("директор",),
        "current_supplier_ids": lambda cur, user: list(supplier_ids),
        "supplier_relation_metadata": lambda cur, rows: {},
        "supplier_find_match": lambda cur, payload, allow_name_match=False, allow_alias_name_match=True: find_match,
        "remember_supplier_alias": lambda cur, sid, payload, source="": alias_log.append((sid, source)),
        "remember_supplier_duplicate_alias": lambda cur, sid, rid, payload: alias_log.append(("dup", sid, rid)),
        "supplier_related_ids": lambda cur, sid: [sid, 99],
        "row_get": row_get,
        "log_audit": lambda *args, **kw: audit_log.append(args or kw),
    })
    return app, connection


class SupplierDirectoryTest(unittest.TestCase):
    def test_all_urls_registered(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/suppliers"), ("POST", "/suppliers"), ("PUT", "/suppliers/{id}"),
                    ("POST", "/suppliers/{id}/link-user"), ("POST", "/suppliers/{id}/link-duplicate"),
                    ("DELETE", "/suppliers/{id}"), ("PUT", "/suppliers/{id}/requisites")]:
            self.assertIn(key, app.routes)

    def test_supplier_role_sees_only_own_cards(self):
        cursor = FakeCursor(rows=[])
        app, _conn = build(cursor, supplier_ids=[5])
        app.routes[("GET", "/suppliers")](current_user={"role": "поставщик"})
        self.assertIn("WHERE id = ANY(%s)", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], ([5],))

    def test_worker_gets_empty_list(self):
        cursor = FakeCursor()
        app, _conn = build(cursor)
        result = app.routes[("GET", "/suppliers")](current_user={"role": "мастер"})
        self.assertEqual(result, [])
        self.assertEqual(cursor.calls, [])

    def test_create_merges_into_existing_match(self):
        alias = []
        cursor = FakeCursor(fetchone_results=[{"id": 7, "name": "ООО Поставка"}])
        app, _conn = build(cursor, find_match={"id": 7}, alias_calls=alias)
        result = app.routes[("POST", "/suppliers")](
            SupplierModel(name="ООО Поставка", phone="+7"), _current_user={"name": "Тест"}
        )
        self.assertEqual(result["id"], 7)
        update = cursor.calls[0]
        self.assertIn("UPDATE suppliers SET", update[0])
        self.assertEqual(alias[0][0], 7)

    def test_create_requires_name(self):
        app, _conn = build(FakeCursor())
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/suppliers")](SupplierModel(name="  "), _current_user={})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_link_user_rejects_non_supplier_role(self):
        cursor = FakeCursor(fetchone_results=[{"id": 3, "name": "ООО"}, {"id": 42, "name": "Тест", "email": "a@b", "role": "мастер"}])
        app, connection = build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/suppliers/{id}/link-user")](
                id=3, data={"userId": 42}, current_user={}
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertTrue(connection.rolled_back)

    def test_delete_blocked_when_documents_reference_supplier(self):
        cursor = FakeCursor(fetchone_results=[(3,), (1,), {"count": 2}])
        app, connection = build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("DELETE", "/suppliers/{id}")](id=3, _current_user={})
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("связанные документы", ctx.exception.detail)
        self.assertTrue(connection.rolled_back)

    def test_foreign_supplier_cannot_edit_requisites(self):
        cursor = FakeCursor()
        app, _conn = build(cursor, supplier_ids=[5])
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("PUT", "/suppliers/{id}/requisites")](
                id=9, data={"inn": "1"}, current_user={"role": "поставщик"}
            )
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
