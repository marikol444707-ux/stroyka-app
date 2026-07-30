import unittest

from fastapi import HTTPException

from backend.features.own_expenses import routes
from backend.features.own_expenses.routes import register_own_expenses_module


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

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def build(cursor, invoice_results=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_own_expenses_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "own_expense_roles": ("директор", "мастер"),
        "own_expense_review_roles": ("директор",),
        "finance_roles": ("директор",),
        "leadership_roles": ("директор",),
        "worker_execution_roles": ("мастер",),
        "warehouse_roles": ("кладовщик",),
        "own_expense_no_project_category": "personal_no_project",
        "require_project_access": lambda user, project: None,
        "user_project_names": lambda user: ["Объект"],
        "safe_project_list": lambda value: value if isinstance(value, list) else [],
        "safe_float": lambda v, d=None: float(v) if v not in (None, "") else d,
        "supply_work_package": lambda v=None: (v or "Основная"),
        "create_warehouse_invoice_record": lambda payload, employee: dict(invoice_results or {"ok": True, "id": 1}),
    })
    return app, connection


class OwnExpensesRoutesTest(unittest.TestCase):
    def test_all_urls_registered(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/own-expenses"), ("POST", "/own-expenses"),
                    ("PUT", "/own-expenses/{id}"), ("DELETE", "/own-expenses/{id}"),
                    ("POST", "/telegram/own-expenses"), ("POST", "/telegram/warehouse-invoices")]:
            self.assertIn(key, app.routes)

    def test_worker_sees_only_own_expenses(self):
        cursor = FakeCursor(rows=[])
        app, _conn = build(cursor)
        app.routes[("GET", "/own-expenses")](
            project_name="", employee_name="", current_user={"id": 42, "name": "Мастер", "role": "мастер"}
        )
        sql, params = cursor.calls[0]
        self.assertIn("(employee_id=%s OR employee_name=%s)", sql)
        self.assertIn(42, params)

    def test_create_syncs_finance_mirror(self):
        cursor = FakeCursor(fetchone_results=[(9,), None, (33,)])
        app, connection = build(cursor)
        result = app.routes[("POST", "/own-expenses")](
            {"description": "бензин", "amount": 500, "projectName": "Объект"},
            current_user={"id": 42, "name": "Мастер", "role": "мастер"},
        )
        self.assertEqual(result, {"ok": True, "id": 9, "expenseId": 33})
        self.assertTrue(connection.committed)
        inserts = [c[0] for c in cursor.calls if c[0].startswith("INSERT INTO")]
        self.assertEqual(len(inserts), 2)
        self.assertIn("INSERT INTO expenses", inserts[1])

    def test_no_project_expense_gets_personal_category(self):
        cursor = FakeCursor(fetchone_results=[(9,), None, (33,)])
        app, _conn = build(cursor)
        app.routes[("POST", "/own-expenses")](
            {"description": "обед", "amount": 300},
            current_user={"id": 42, "name": "Мастер", "role": "мастер"},
        )
        own_insert = [c for c in cursor.calls if c[0].startswith("INSERT INTO own_expenses")][0]
        self.assertIn("personal_no_project", own_insert[1])

    def test_telegram_expense_unknown_employee_404(self):
        cursor = FakeCursor(fetchone_results=[None, None])
        app, _conn = build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/telegram/own-expenses")](
                {"telegramId": "123", "description": "бензин", "amount": 100}, _bot={"role": "telegram_bot"}
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_telegram_expense_redirects_warehouse_payload(self):
        app, _conn = build(FakeCursor())
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/telegram/own-expenses")](
                {"telegramId": "123", "description": "накладная цемент", "amount": 100,
                 "documentType": "warehouse_invoice"},
                _bot={"role": "telegram_bot"},
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("складская накладная", ctx.exception.detail)

    def test_telegram_warehouse_requires_warehouse_role(self):
        users_row = (42, "Мастер", "мастер", "Объект", [], [])
        cursor = FakeCursor(fetchone_results=[users_row])
        app, _conn = build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/telegram/warehouse-invoices")](
                {"telegramId": "123"}, _bot={"role": "telegram_bot"}
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_reject_removes_finance_mirror(self):
        row = ("Объект", "Мастер", "бензин", 500, "2026-07-28", "")
        cursor = FakeCursor(fetchone_results=[row])
        app, connection = build(cursor)
        result = app.routes[("PUT", "/own-expenses/{id}")](
            id=9, data={"status": "Отклонено", "approvedBy": "Тест"}, _current_user={}
        )
        self.assertEqual(result, {"ok": True})
        deletes = [c[0] for c in cursor.calls if c[0].startswith("DELETE FROM expenses")]
        self.assertEqual(len(deletes), 1)
        self.assertTrue(connection.committed)


if __name__ == "__main__":
    unittest.main()
