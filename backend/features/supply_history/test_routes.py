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

    def cursor(self, **_kwargs):
        return self._cursor

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
        app, _conn = history_build(cursor)
        result = app.routes[("GET", "/supply-history")](limit=None, offset=0, current_user={"role": "поставщик"})
        self.assertEqual(result, [])

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
        cursor = FakeCursor(fetchone_results=[row])
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


if __name__ == "__main__":
    unittest.main()
