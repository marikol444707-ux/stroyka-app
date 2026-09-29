import unittest

from fastapi import HTTPException

from backend.features.materials.routes import MaterialModel, register_materials_module
from backend.features.company_context.service import effective_company_actors


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
        self._schema_query = 'to_regclass' in sql
        self._authorization_query = sql.startswith('SELECT id FROM ') and sql.endswith('FOR SHARE')
        if self._schema_query or self._authorization_query:
            return
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        if getattr(self, '_schema_query', False):
            return {'present': False}
        if getattr(self, '_authorization_query', False):
            return {'id': 1}
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

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def build(cursor, projects=("Объект",), warehouse_data=False, audit_calls=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    audit_log = audit_calls if audit_calls is not None else []
    register_materials_module(app, {
        "resolve_work_company_context": lambda cur, user, *args, **kwargs: {
            "mode": "company", "companyId": 2, "membershipId": 1,
            "source": "membership", "active": True, "companyActive": True,
            "role": user.get("role", "кладовщик"),
        },
        "effective_company_actors": effective_company_actors,
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
        "log_audit": lambda *args, **kwargs: audit_log.append(args),
    })
    return app, connection


ROW = {"id": 1, "companyId": 2, "name": "Цемент", "unit": "кг", "quantity": 100, "price": 12,
       "minQuantity": 10, "project": "", "category": "смеси", "workPackage": ""}


class MaterialsRoutesTest(unittest.TestCase):
    def test_all_urls_registered(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/materials"), ("POST", "/materials"),
                    ("PUT", "/materials/{id}"), ("DELETE", "/materials/{id}")]:
            self.assertIn(key, app.routes)

    def test_read_is_company_scoped(self):
        cursor = FakeCursor(rows=[dict(ROW)])
        app, _ = build(cursor, warehouse_data=True)
        app.routes[("GET", "/materials")](current_user={"role": "кладовщик"})
        self.assertIn("company_id=%s", cursor.calls[0][0])
        self.assertIn(2, cursor.calls[0][1])

    def test_create_explicitly_persists_company(self):
        cursor = FakeCursor(fetchone_results=[dict(ROW)])
        app, _ = build(cursor)
        app.routes[("POST", "/materials")](MaterialModel(name="Цемент"), _current_user={"id": 1, "role": "кладовщик"})
        self.assertIn("company_id", cursor.calls[0][0])
        self.assertIn(2, cursor.calls[0][1])

    def test_update_foreign_id_is_scoped(self):
        cursor = FakeCursor(fetchone_results=[None])
        app, conn = build(cursor)
        with self.assertRaises(HTTPException) as caught:
            app.routes[("PUT", "/materials/{id}")](1, MaterialModel(name="Цемент"), _current_user={"id": 1, "role": "кладовщик"})
        self.assertEqual(caught.exception.status_code, 404)
        self.assertIn("company_id=%s", cursor.calls[0][0])
        self.assertFalse(conn.committed)

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
                MaterialModel(name="Цемент", project="Объект"), _current_user={"id": 1, "role": "кладовщик"}
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("через накладную", ctx.exception.detail)

    def test_main_warehouse_creation_writes_correct_audit(self):
        audit = []
        cursor = FakeCursor(fetchone_results=[dict(ROW)])
        app, connection = build(cursor, audit_calls=audit)
        result = app.routes[("POST", "/materials")](
            MaterialModel(name="Цемент", unit="кг", quantity=100),
            _current_user={"id": 1, "name": "Тест", "role": "кладовщик"},
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
                _current_user={"id": 1, "role": "кладовщик"},
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("прямой правкой", ctx.exception.detail)

    def test_update_locks_material_before_validating_quantity(self):
        cursor = FakeCursor(fetchone_results=[{
            "project": "Объект", "quantity": 50, "work_package": "Основная",
        }])
        app, connection = build(cursor)
        result = app.routes[("PUT", "/materials/{id}")](
            id=1, m=MaterialModel(name="Цемент", project="Объект", quantity=50),
            _current_user={"id": 1, "role": "кладовщик"},
        )
        self.assertEqual(result, {"ok": True})
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)
        self.assertTrue(cursor.calls[0][0].endswith("WHERE id=%s AND company_id=%s FOR UPDATE"))
        self.assertEqual(cursor.calls[0][1], (1, 2))

    def test_object_metadata_update_never_assigns_quantity(self):
        # Even an accepted rounding difference must not overwrite document stock.
        for quantity in (50, 50.0000005):
            with self.subTest(quantity=quantity):
                cursor = FakeCursor(fetchone_results=[{
                    "project": "Объект", "quantity": 50, "work_package": "Основная",
                }])
                app, connection = build(cursor)
                result = app.routes[("PUT", "/materials/{id}")](
                    id=1, m=MaterialModel(name="Новое имя", unit=" кг ",
                        project="Объект", quantity=quantity, price=12,
                        minQuantity=10, category="смеси", workPackage=" Отделка "),
                    _current_user={"id": 1, "role": "кладовщик"},
                )
                self.assertEqual(result, {"ok": True})
                sql, params = cursor.calls[1]
                assignments = sql.split(" SET ", 1)[1].split(" WHERE ", 1)[0]
                columns = [part.split("=", 1)[0].strip() for part in assignments.split(",")]
                self.assertNotIn("quantity", columns)
                self.assertEqual(params, (
                    "Новое имя", "кг", 12, 10, "Объект", "смеси", "Отделка", 1, 2,
                ))
                self.assertTrue(connection.committed)

    def test_project_changes_involving_object_stock_remain_forbidden(self):
        for old_project, new_project in (("Объект", "Другой"), ("Объект", ""), ("", "Объект")):
            with self.subTest(old_project=old_project, new_project=new_project):
                cursor = FakeCursor(fetchone_results=[{
                    "project": old_project, "quantity": 50, "work_package": "Основная",
                }])
                app, connection = build(cursor)
                with self.assertRaises(HTTPException) as ctx:
                    app.routes[("PUT", "/materials/{id}")](
                        id=1, m=MaterialModel(name="Цемент", project=new_project, quantity=50),
                        _current_user={"id": 1, "role": "кладовщик"},
                    )
                self.assertEqual(ctx.exception.status_code, 400)
                self.assertEqual(len(cursor.calls), 1)
                self.assertFalse(connection.committed)
                self.assertTrue(connection.closed)

    def test_main_and_unassigned_quantity_updates_remain_allowed(self):
        for project in ("", None):
            with self.subTest(project=project):
                cursor = FakeCursor(fetchone_results=[{
                    "project": project, "quantity": 50, "work_package": "Основная",
                }])
                app, connection = build(cursor)
                result = app.routes[("PUT", "/materials/{id}")](
                    id=1, m=MaterialModel(name="Цемент", quantity=80),
                    _current_user={"id": 1, "role": "кладовщик"},
                )
                self.assertEqual(result, {"ok": True})
                self.assertIn("unit=%s,quantity=%s,price=%s", cursor.calls[1][0])
                self.assertEqual(cursor.calls[1][1], (
                    "Цемент", "шт", 80, 0, 0, "", "", "Основная", 1, 2,
                ))
                self.assertTrue(connection.committed)

    def test_physical_delete_is_disabled(self):
        app, _conn = build(FakeCursor())
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("DELETE", "/materials/{id}")](id=1, _current_user={"id": 1, })
        self.assertEqual(ctx.exception.status_code, 405)

    def test_metadata_failure_rolls_back_and_closes_connection(self):
        class FailingCursor(FakeCursor):
            def execute(self, sql, params=()):
                super().execute(sql, params)
                if sql.strip().startswith('UPDATE materials'):
                    raise RuntimeError('synthetic database failure')
        cursor = FailingCursor(fetchone_results=[{'project': 'Объект', 'quantity': 50, 'work_package': 'Основная'}])
        app, connection = build(cursor)
        with self.assertRaises(RuntimeError):
            app.routes[("PUT", "/materials/{id}")](id=1, m=MaterialModel(name='Цемент', project='Объект', quantity=50), _current_user={"id": 1, })
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)
        self.assertFalse(connection.committed)


if __name__ == "__main__":
    unittest.main()
