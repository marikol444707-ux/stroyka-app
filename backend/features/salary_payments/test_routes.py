import unittest

from fastapi import HTTPException

from backend.features.salary_payments.routes import register_salary_payments_module


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
    def __init__(self, effects=()):
        self.effects = list(effects)
        self.current = {}
        self.calls = []
        self.rowcount = -1
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params or ())))
        self.current = self.effects.pop(0) if self.effects else {}
        self.rowcount = self.current.get("rowcount", -1)

    def fetchall(self):
        return list(self.current.get("rows", ()))

    def fetchone(self):
        return self.current.get("row")

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def build(effects=(), context=None, actors=None):
    app = FakeApp()
    cursor = FakeCursor(effects)
    connection = FakeConnection(cursor)
    selected_context = context or {"mode": "company", "companyId": 4}
    selected_actors = actors if actors is not None else [
        {"companyId": 4, "role": "директор", "name": "Системный директор"}
    ]

    def resolve_context(_cur, _user, _project, _action, **_headers):
        return selected_context

    register_salary_payments_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: None,
        "resolve_work_company_context": resolve_context,
        "effective_company_actors": lambda _user, _context: selected_actors,
        "finance_roles": ("директор", "бухгалтер"),
    })
    return app, connection, cursor


def call(handler, *args, **kwargs):
    return handler(
        *args,
        x_company_id="4",
        x_company_mode="company",
        current_user={"id": 9, "name": "Клиентская подмена"},
        **kwargs,
    )


class SalaryPaymentsRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn, _cursor = build()
        self.assertEqual(set(app.routes), {
            ("GET", "/salary-payments"),
            ("POST", "/salary-payments"),
            ("DELETE", "/salary-payments/{id}"),
        })

    def test_list_reads_only_verified_rows_in_selected_company(self):
        app, conn, cursor = build([{"rows": [
            (1, 5, "Мастер", "2026-07", "40000", "Тест", "2026-07-28", "", "2026-07-28")
        ]}])
        rows = call(app.routes[("GET", "/salary-payments")])
        self.assertEqual(rows[0]["amount"], 40000.0)
        sql, params = cursor.calls[-1]
        self.assertIn("company_id=%s", sql)
        self.assertIn("company_scope_verified IS TRUE", sql)
        self.assertEqual(params, (4,))
        self.assertTrue(conn.closed)

    def test_create_locks_verified_staff_and_derives_names(self):
        app, conn, cursor = build([
            {"row": {"id": 5, "name": "Точный мастер"}},
            {"row": {"id": 3}},
        ])
        created = call(app.routes[("POST", "/salary-payments")], data={
            "staffId": 5,
            "staffName": "ПОДМЕНА",
            "month": "2026-07",
            "amount": 100,
            "paidBy": "ПОДМЕНА",
            "paidDate": "2000-01-01",
        })
        self.assertEqual(created, {"ok": True, "id": 3})
        staff_sql, staff_params = cursor.calls[0]
        insert_sql, insert_params = cursor.calls[1]
        self.assertIn("company_scope_verified IS TRUE", staff_sql)
        self.assertIn("FOR SHARE", staff_sql)
        self.assertEqual(staff_params, (5, 4))
        self.assertIn("company_id", insert_sql)
        self.assertIn("company_scope_verified", insert_sql)
        self.assertIn("Точный мастер", insert_params)
        self.assertIn("Системный директор", insert_params)
        self.assertNotIn("ПОДМЕНА", insert_params)
        self.assertEqual(conn.commits, 1)

    def test_create_rejects_foreign_staff_and_bad_month_with_rollback(self):
        app, conn, _cursor = build([{"row": None}])
        with self.assertRaises(HTTPException) as foreign:
            call(app.routes[("POST", "/salary-payments")], data={
                "staffId": 6, "month": "2026-07", "amount": 100,
            })
        self.assertEqual(foreign.exception.status_code, 404)
        self.assertEqual(conn.rollbacks, 1)

        app2, conn2, _cursor2 = build([{"row": {"id": 5, "name": "Мастер"}}])
        with self.assertRaises(HTTPException) as month:
            call(app2.routes[("POST", "/salary-payments")], data={
                "staffId": 5, "month": "июль", "amount": 100,
            })
        self.assertEqual(month.exception.status_code, 400)
        self.assertEqual(conn2.rollbacks, 1)

    def test_delete_locks_and_deletes_only_verified_company_row(self):
        app, conn, cursor = build([
            {"row": {"id": 3, "company_id": 4, "staff_id": 5}},
            {"rowcount": 1},
        ])
        result = call(app.routes[("DELETE", "/salary-payments/{id}")], id=3)
        self.assertEqual(result, {"ok": True})
        lookup_sql, lookup_params = cursor.calls[0]
        delete_sql, delete_params = cursor.calls[1]
        self.assertIn("company_scope_verified IS TRUE", lookup_sql)
        self.assertIn("FOR UPDATE", lookup_sql)
        self.assertEqual(lookup_params, (3, 4))
        self.assertIn("company_id=%s", delete_sql)
        self.assertIn("company_scope_verified IS TRUE", delete_sql)
        self.assertEqual(delete_params, (3, 4, 5))
        self.assertEqual(conn.commits, 1)

    def test_aggregate_mode_is_rejected_before_salary_read(self):
        app, _conn, cursor = build(context={"mode": "aggregate"})
        with self.assertRaises(HTTPException) as ctx:
            call(app.routes[("GET", "/salary-payments")])
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(cursor.calls, [])


if __name__ == "__main__":
    unittest.main()
