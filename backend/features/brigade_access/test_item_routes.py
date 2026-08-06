import unittest

from fastapi import HTTPException

from backend.features.brigade_access.item_routes import register_brigade_contract_items_module


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


CONTRACT = {"id": 7, "companyId": 3, "projectName": "Объект", "brigadeName": "Бригада", "workPackage": "Основная"}


def build(cursor, actors=None, recalc_calls=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    recalc_log = recalc_calls if recalc_calls is not None else []
    register_brigade_contract_items_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "contract_roles": ("директор", "мастер"),
        "leadership_roles": ("директор",),
        "finance_roles": ("директор",),
        "worker_execution_roles": ("мастер",),
        "brigade_contract_read_scope": lambda conn, user, roles, **kw: ("bc.company_id=%s", [3], list(actors or [])),
        "resolve_brigade_contract_actor": lambda cur, user, cid, roles, **kw: (dict(CONTRACT), {"name": "Тест", "role": "директор"}, {"id": 9}),
        "positive_int_or_none": lambda v: int(v) if v else None,
        "has_package_access": lambda user, pkg: True,
        "row_get": row_get,
        "recalc_brigade_contract_total": lambda cur, cid: recalc_log.append(cid),
    })
    return app, connection


class BrigadeContractItemsTest(unittest.TestCase):
    def test_all_urls_registered(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/brigade-contract-items-all"), ("GET", "/brigade-contract-items/{contract_id}"),
                    ("POST", "/brigade-contract-items"), ("PUT", "/brigade-contract-items/{id}"),
                    ("DELETE", "/brigade-contract-items/{id}")]:
            self.assertIn(key, app.routes)

    def test_worker_sees_zero_smeta_price_and_clamped_done(self):
        row = (1, 7, "Штукатурка", "м2", 100, 450, 300, 150, "Раздел", "Основная", "k1", "Объект", 3)
        cursor = FakeCursor(rows=[row])
        app, _conn = build(cursor, actors=[{"companyId": 3, "role": "мастер"}])
        result = app.routes[("GET", "/brigade-contract-items-all")](
            project_name=None, x_company_id="3", x_company_mode="company", _current_user={}
        )
        self.assertEqual(result[0]["priceSmeta"], 0)
        self.assertEqual(result[0]["doneQuantity"], 100)
        self.assertEqual(result[0]["rawDoneQuantity"], 150)
        self.assertTrue(result[0]["hasInvalidDoneQuantity"])

    def test_item_status_derivation(self):
        row = (1, 7, "Раздел", "Штукатурка", "м2", 100, 450, 300, 60, "Основная", "k1", 3)
        cursor = FakeCursor(rows=[row])
        app, _conn = build(cursor, actors=[{"companyId": 3, "role": "директор"}])
        result = app.routes[("GET", "/brigade-contract-items/{contract_id}")](
            contract_id=7, x_company_id="3", x_company_mode="company", _current_user={}
        )
        self.assertEqual(result[0]["status"], "В работе")
        self.assertEqual(result[0]["priceSmeta"], 450.0)

    def test_create_rejects_foreign_package(self):
        cursor = FakeCursor()
        app, connection = build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/brigade-contract-items")](
                {"contractId": 7, "workPackage": "Другой"},
                x_company_id="3", x_company_mode="company", _current_user={},
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertTrue(connection.rolled_back)

    def test_create_marks_generic_item_as_manual_without_lineage_coordinates(self):
        cursor = FakeCursor(fetchone_results=[(14,)])
        app, connection = build(cursor)

        result = app.routes[("POST", "/brigade-contract-items")](
            {
                "contractId": 7,
                "estimateSection": "Дополнительные работы",
                "name": "Уборка",
                "unit": "ч",
                "quantity": 3,
                "priceSmeta": 500,
                "priceBrigade": 350,
                "doneQuantity": 2,
            },
            x_company_id="3", x_company_mode="company", _current_user={},
        )

        insert = next(call for call in cursor.calls if call[0].startswith("INSERT INTO brigade_contract_items"))
        self.assertIn("source_type", insert[0])
        self.assertEqual(insert[1][4], "")
        self.assertEqual(insert[1][9], 0)
        self.assertEqual(insert[1][10:], ("manual", None, None, None, None))
        self.assertEqual(result["id"], 14)
        self.assertTrue(connection.committed)

    def test_create_rejects_client_supplied_estimate_lineage(self):
        for payload in (
            {"contractId": 7, "estimateItemKey": "estimate:0:1"},
            {"contractId": 7, "sourceType": "estimate"},
            {"contractId": 7, "source_estimate_version_id": 12},
        ):
            with self.subTest(payload=payload):
                cursor = FakeCursor()
                app, connection = build(cursor)

                with self.assertRaises(HTTPException) as ctx:
                    app.routes[("POST", "/brigade-contract-items")](
                        payload,
                        x_company_id="3", x_company_mode="company", _current_user={},
                    )

                self.assertEqual(ctx.exception.status_code, 400)
                self.assertFalse(any(call[0].startswith("INSERT INTO brigade_contract_items") for call in cursor.calls))
                self.assertTrue(connection.rolled_back)

    def test_update_preserves_server_done_quantity_and_recalcs_total(self):
        recalc = []
        cursor = FakeCursor(fetchone_results=[(7, "Основная", 40), (7,)])
        app, connection = build(cursor, recalc_calls=recalc)
        result = app.routes[("PUT", "/brigade-contract-items/{id}")](
            id=4, data={"quantity": 100, "doneQuantity": 250, "priceBrigade": 300, "priceSmeta": 450},
            x_company_id="3", x_company_mode="company", _current_user={},
        )
        self.assertEqual(result["ok"], True)
        update = [c for c in cursor.calls if c[0].startswith("UPDATE brigade_contract_items")][0]
        self.assertEqual(update[1][3], 40)
        self.assertNotIn("estimate_item_key", update[0])
        self.assertEqual(recalc, [7])
        self.assertTrue(connection.committed)

    def test_update_ignores_compatibility_key_and_rejects_source_coordinates(self):
        cursor = FakeCursor(fetchone_results=[(7, "Основная", 0), (7,)])
        app, connection = build(cursor)
        app.routes[("PUT", "/brigade-contract-items/{id}")](
            id=4,
            data={"quantity": 10, "estimateItemKey": "tampered"},
            x_company_id="3", x_company_mode="company", _current_user={},
        )
        update = next(call for call in cursor.calls if call[0].startswith("UPDATE brigade_contract_items"))
        self.assertNotIn("estimate_item_key", update[0])
        self.assertNotIn("tampered", update[1])

        cursor = FakeCursor(fetchone_results=[(7, "Основная", 0)])
        app, connection = build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("PUT", "/brigade-contract-items/{id}")](
                id=4,
                data={"quantity": 10, "sourceItemKey": "tampered"},
                x_company_id="3", x_company_mode="company", _current_user={},
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertFalse(any(call[0].startswith("UPDATE brigade_contract_items") for call in cursor.calls))
        self.assertTrue(connection.rolled_back)

    def test_delete_recalcs_total(self):
        recalc = []
        cursor = FakeCursor(fetchone_results=[(7, "Основная"), (7,)])
        app, connection = build(cursor, recalc_calls=recalc)
        result = app.routes[("DELETE", "/brigade-contract-items/{id}")](
            id=4, x_company_id="3", x_company_mode="company", _current_user={}
        )
        self.assertEqual(result["ok"], True)
        self.assertEqual(recalc, [7])
        self.assertTrue(connection.committed)


if __name__ == "__main__":
    unittest.main()
