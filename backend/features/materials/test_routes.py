import unittest

from fastapi import HTTPException

from backend.features.materials.routes import MaterialModel, register_materials_module


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


def build(cursor, projects=("Объект",), warehouse_data=False, audit_calls=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    audit_log = audit_calls if audit_calls is not None else []
    register_materials_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "require_roles": lambda *roles: (lambda: None),
        "main_warehouse_write_roles": ("кладовщик",),
        "material_price_history_roles": ("снабженец", "кладовщик"),
        "finance_roles": ("директор",),
        "user_project_names": lambda user: list(projects),
        "package_access_filter": lambda user: ("", []),
        "can_see_warehouse_data": lambda user: warehouse_data,
        "require_project_or_warehouse_access": lambda user, project: None,
        "has_package_access": lambda user, pkg: True,
        "limit_offset_sql": lambda limit, offset: ("", []),
        "norm_base_unit": lambda v: (v or "шт").strip(),
        "log_audit": lambda *args: audit_log.append(args),
    })
    return app, connection


ROW = {"id": 1, "name": "Цемент", "unit": "кг", "quantity": 100, "price": 12,
       "minQuantity": 10, "project": "", "category": "смеси", "workPackage": ""}


class MaterialsRoutesTest(unittest.TestCase):
    def test_all_urls_registered(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/materials"), ("POST", "/materials"),
                    ("PUT", "/materials/{id}"), ("DELETE", "/materials/{id}")]:
            self.assertIn(key, app.routes)

    def test_customer_and_supervisor_get_nothing(self):
        cursor = FakeCursor(rows=[dict(ROW)])
        app, _conn = build(cursor)
        for role in ("заказчик", "технадзор"):
            result = app.routes[("GET", "/materials")](
                search="", project_name="", limit=None, offset=0, current_user={"role": role}
            )
            self.assertEqual(result, [])
        self.assertEqual(cursor.calls, [])

    def test_worker_sees_zero_stock_and_prices(self):
        cursor = FakeCursor(rows=[dict(ROW)])
        app, _conn = build(cursor, projects=["Объект"])
        result = app.routes[("GET", "/materials")](
            search="", project_name="", limit=None, offset=0, current_user={"role": "мастер"}
        )
        self.assertEqual(result[0]["quantity"], 0)
        self.assertEqual(result[0]["minQuantity"], 0)
        self.assertEqual(result[0]["price"], 0)

    def test_storekeeper_sees_stock_and_prices(self):
        cursor = FakeCursor(rows=[dict(ROW)])
        app, _conn = build(cursor, warehouse_data=True)
        result = app.routes[("GET", "/materials")](
            search="", project_name="", limit=None, offset=0, current_user={"role": "кладовщик"}
        )
        self.assertEqual(result[0]["quantity"], 100)
        self.assertEqual(result[0]["price"], 12)

    def test_object_stock_creation_is_forbidden(self):
        app, _conn = build(FakeCursor())
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/materials")](
                MaterialModel(name="Цемент", project="Объект"), _current_user={"role": "кладовщик"}
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("через накладную", ctx.exception.detail)

    def test_main_warehouse_creation_writes_correct_audit(self):
        audit = []
        cursor = FakeCursor(fetchone_results=[dict(ROW)])
        app, connection = build(cursor, audit_calls=audit)
        result = app.routes[("POST", "/materials")](
            MaterialModel(name="Цемент", unit="кг", quantity=100),
            _current_user={"name": "Тест", "role": "кладовщик"},
        )
        self.assertEqual(result["name"], "Цемент")
        self.assertTrue(connection.committed)
        self.assertEqual(audit[0][3], "material")
        self.assertIn("Материал создан: Цемент", audit[0][5])
        self.assertNotIn("Акт исполнителя", audit[0][5])

    def test_object_quantity_change_is_forbidden(self):
        cursor = FakeCursor(fetchone_results=[{"project": "Объект", "quantity": 50, "work_package": "Основная"}])
        app, _conn = build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("PUT", "/materials/{id}")](
                id=1, m=MaterialModel(name="Цемент", project="Объект", quantity=80),
                _current_user={"role": "кладовщик"},
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("прямой правкой", ctx.exception.detail)

    def test_physical_delete_is_disabled(self):
        app, _conn = build(FakeCursor())
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("DELETE", "/materials/{id}")](id=1, _current_user={})
        self.assertEqual(ctx.exception.status_code, 405)


if __name__ == "__main__":
    unittest.main()
