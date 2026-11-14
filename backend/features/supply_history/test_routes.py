import inspect
import unittest

from fastapi import HTTPException

from backend.features.contracts.routes import ContractModel, register_contracts_module
from backend.features.supply_history.routes import SupplyHistoryModel, register_supply_history_module


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

    def rollback(self):
        self.rolled_back = True

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def contracts_build(cursor, visible=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_contracts_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "contract_roles": ("директор", "мастер"),
        "create_roles": ("директор",),
        "delete_roles": ("директор",),
        "worker_execution_roles": ("мастер",),
        "visible_project_names": lambda user: visible,
        "require_project_access": lambda user, project: None,
        "require_row_project_access": lambda cur, table, row_id, user, col: None,
    })
    return app, connection


def history_build(cursor, all_data=False):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_supply_history_module(app, {
        "resolve_work_company_context": lambda *args, **kwargs: {"mode": "company"},
        "effective_company_actors": lambda *args: [{"companyId": 3, "role": "директор"}],
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "require_roles": lambda *roles: (lambda: None),
        "write_roles": ("директор",),
        "worker_execution_roles": ("мастер",),
        "limit_offset_sql": lambda limit, offset: (" LIMIT 200", []),
        "ensure_supply_runtime_columns": lambda cur: None,
        "can_see_all_company_data": lambda user: all_data,
        "scoped_project_where": lambda user, col: (" WHERE project = ANY(%s)", [["Объект"]]),
        "current_supplier_ids": lambda cur, user: [],
        "user_project_names": lambda user: ["Объект"],
        "package_access_filter": lambda user: ("", []),
        "has_package_access": lambda user, pkg: pkg != "чужой",
        "require_project_or_warehouse_access": lambda user, project: None,
        "company_id_for_project_or_user": lambda cur, project, user: 3,
    })
    return app, connection


class ContractsAndSupplyHistoryTest(unittest.TestCase):
    def test_all_urls_registered(self):
        capp, _c = contracts_build(FakeCursor())
        happ, _h = history_build(FakeCursor())
        for key in [("GET", "/contracts"), ("POST", "/contracts"), ("DELETE", "/contracts/{id}")]:
            self.assertIn(key, capp.routes)
        for key in [("GET", "/supply-history"), ("POST", "/supply-history"), ("PUT", "/supply-history/{id}")]:
            self.assertIn(key, happ.routes)

    def test_worker_sees_only_own_contracts(self):
        cursor = FakeCursor(rows=[])
        app, _conn = contracts_build(cursor, visible=["Объект"])
        app.routes[("GET", "/contracts")](_current_user={"id": 42, "name": "Мастер", "role": "мастер"})
        sql, params = cursor.calls[0]
        self.assertIn("COALESCE(master_id,0)=%s", sql)
        self.assertIn(42, params)

    def test_contract_delete_is_soft(self):
        cursor = FakeCursor()
        app, connection = contracts_build(cursor)
        result = app.routes[("DELETE", "/contracts/{id}")](id=5, _current_user={})
        self.assertEqual(result, {"ok": True})
        self.assertIn("SET status='Аннулирован'", cursor.calls[0][0])
        self.assertTrue(connection.committed)

    def test_supplier_without_links_gets_empty_history(self):
        cursor = FakeCursor()
        app, connection = history_build(cursor)
        result = app.routes[("GET", "/supply-history")](limit=None, offset=0, current_user={"role": "поставщик"})
        self.assertEqual(result, [])
        self.assertFalse(connection.committed)
        self.assertTrue(connection.rolled_back)

    def test_get_history_reads_company_rows_without_writing(self):
        cursor = FakeCursor(rows=[{"id": 4, "companyId": 3, "materialName": "Цемент"}])
        schema_calls = []

        def ensure(_cur):
            schema_calls.append("schema")
            raise AssertionError("история снабжения не должна менять схему при чтении")

        app = FakeApp()
        connection = FakeConnection(cursor)
        readonly_user = lambda: {"role": "директор"}
        register_supply_history_module(app, {
            "resolve_work_company_context": lambda *args, **kwargs: {"mode": "company"},
            "effective_company_actors": lambda *args: [{"companyId": 3, "role": "директор"}],
            "get_db": lambda: connection,
            "get_current_user": lambda: (_ for _ in ()).throw(AssertionError("писатель сессии")),
            "get_current_user_readonly": readonly_user,
            "require_roles": lambda *roles: (lambda: None),
            "write_roles": ("директор",),
            "worker_execution_roles": ("мастер",),
            "limit_offset_sql": lambda limit, offset: (" LIMIT 200", []),
            "ensure_supply_runtime_columns": ensure,
            "can_see_all_company_data": lambda user: True,
            "scoped_project_where": lambda user, col: ("", []),
            "current_supplier_ids": lambda cur, user: [],
            "user_project_names": lambda user: ["Объект"],
            "package_access_filter": lambda user: ("", []),
            "has_package_access": lambda user, pkg: True,
            "require_project_or_warehouse_access": lambda user, project: None,
            "company_id_for_project_or_user": lambda cur, project, user: 3,
        })
        handler = app.routes[("GET", "/supply-history")]
        dependency = inspect.signature(handler).parameters["current_user"].default.dependency
        self.assertIs(dependency, readonly_user)
        result = handler(limit=None, offset=0, current_user={"role": "директор"})
        self.assertEqual(result, [{"id": 4, "companyId": 3, "materialName": "Цемент"}])
        self.assertEqual(schema_calls, [])
        self.assertFalse(connection.committed)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.autocommit)
        statements = [sql for sql, _params in cursor.calls]
        self.assertEqual(statements[0], "SET TRANSACTION READ ONLY")
        self.assertTrue(any("FROM supply_history" in sql and "company_id=%s" in sql for sql in statements))
        self.assertTrue(any(params == (3,) for _sql, params in cursor.calls))
        self.assertFalse(any(
            token in sql
            for sql in statements
            for token in ("INSERT", "UPDATE", "DELETE", "ALTER")
        ))

    def test_history_create_blocks_foreign_package(self):
        cursor = FakeCursor()
        app, _conn = history_build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/supply-history")](
                SupplyHistoryModel(supplierId=1, materialName="Цемент", quantity=5,
                                   pricePerUnit=100, totalPrice=500, workPackage="чужой"),
                _current_user={},
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_history_create_resolves_company(self):
        row = {"id": 9, "companyId": 3}
        cursor = FakeCursor(fetchone_results=[{"id": 1}, row])
        app, connection = history_build(cursor)
        result = app.routes[("POST", "/supply-history")](
            SupplyHistoryModel(supplierId=1, materialName="Цемент", quantity=5,
                               pricePerUnit=100, totalPrice=500, project="Объект"),
            _current_user={},
        )
        self.assertEqual(result["companyId"], 3)
        insert = [c for c in cursor.calls if c[0].startswith("INSERT INTO supply_history")][0]
        self.assertEqual(insert[1][0], 3)
        self.assertTrue(connection.committed)


class ReadOnlySessionLookupTests(unittest.TestCase):
    def test_readonly_lookup_does_not_touch_last_seen(self):
        from backend.features.supply_history.session_read import load_cookie_session_user

        cursor = FakeCursor(fetchone_results=[{
            "id": 7,
            "auth_session_id": 15,
            "role": "директор",
            "company_id": 3,
        }])
        connection = FakeConnection(cursor)
        seen = []
        user = load_cookie_session_user(
            cursor,
            connection,
            "hash",
            touch_session=False,
            enrich=lambda cur, row: seen.append(row) or row,
        )
        self.assertEqual(user["company_id"], 3)
        self.assertEqual(seen, [user])
        self.assertFalse(connection.committed)
        statements = [sql for sql, _params in cursor.calls]
        self.assertEqual(statements[0], "SET TRANSACTION READ ONLY")
        self.assertIn("FROM user_sessions", statements[1])
        self.assertFalse(any("UPDATE" in sql or "INSERT" in sql or "ALTER" in sql for sql in statements))

    def test_ordinary_lookup_still_refreshes_last_seen(self):
        from backend.features.supply_history.session_read import load_cookie_session_user

        cursor = FakeCursor(fetchone_results=[{"id": 7, "auth_session_id": 15}])
        connection = FakeConnection(cursor)
        load_cookie_session_user(cursor, connection, "hash", touch_session=True)
        self.assertTrue(connection.committed)
        update = [call for call in cursor.calls if call[0].startswith("UPDATE user_sessions")]
        self.assertEqual(update, [("UPDATE user_sessions SET last_seen_at=NOW() WHERE id=%s", (15,))])


if __name__ == "__main__":
    unittest.main()
