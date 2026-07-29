import unittest

from fastapi import HTTPException

from backend.features.interim_acts.routes import InterimActModel, register_interim_acts_module


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


def build(cursor, confirmed_total=1000.0, audit_calls=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    audit_log = audit_calls if audit_calls is not None else []
    register_interim_acts_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "require_roles": lambda *roles: (lambda: None),
        "contract_roles": ("директор", "мастер"),
        "finance_roles": ("директор",),
        "delete_roles": ("директор",),
        "worker_execution_roles": ("мастер",),
        "visible_project_names": lambda user: None,
        "package_access_filter": lambda user: ("", []),
        "require_project_access": lambda user, project: None,
        "has_package_access": lambda user, pkg: True,
        "require_row_project_access": lambda cur, table, row_id, user, col: None,
        "confirmed_execution_total_for_act": lambda cur, mid, mn, pr, wp, ps, pe: confirmed_total,
        "resolve_project_payment_actor": lambda cur, user, project, pkg, **kw: (3, {"name": "Тест", "role": "директор"}),
        "daily_work_act_source_type": "daily_work",
        "interim_act_locked_statuses": ("Подписан", "Оплачен", "Частично оплачен"),
        "log_audit": lambda *args: audit_log.append(args),
    })
    return app, connection


def act_model(**over):
    base = dict(masterId=5, masterName="Мастер", project="Объект",
                periodStart="2026-07-01", periodEnd="2026-07-28",
                totalAmount=500, workJournalIds=[11, 12])
    base.update(over)
    return InterimActModel(**base)


class InterimActsRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/interim-acts"), ("POST", "/interim-acts"), ("PUT", "/interim-acts/{id}"),
                    ("POST", "/interim-acts/{id}/pay"), ("DELETE", "/interim-acts/{id}")]:
            self.assertIn(key, app.routes)

    def test_create_rejects_amount_above_confirmed_work(self):
        app, _conn = build(FakeCursor(), confirmed_total=100.0)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/interim-acts")](act_model(totalAmount=500), _current_user={"role": "директор"})
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("100.00", ctx.exception.detail)

    def test_create_requires_exact_journal_match(self):
        cursor = FakeCursor(rows=[{"id": 11, "execution_total": 500}])
        app, _conn = build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/interim-acts")](act_model(), _current_user={"role": "директор"})
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("12", ctx.exception.detail)

    def test_pay_blocks_daily_control_act(self):
        act = (500, 0, "Объект", "", "Мастер", "daily_work")
        cursor = FakeCursor(fetchone_results=[act])
        app, connection = build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/interim-acts/{id}/pay")](
                id=7, data={"amount": 100}, x_company_id=None, x_company_mode=None, _current_user={}
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertTrue(connection.rolled_back)

    def test_pay_mirrors_negative_project_payment_and_sets_status(self):
        act = (500, 400, "Объект", "Основная", "Мастер", "")
        cursor = FakeCursor(fetchone_results=[act, (77,)])
        audit = []
        app, connection = build(cursor, audit_calls=audit)
        result = app.routes[("POST", "/interim-acts/{id}/pay")](
            id=7, data={"amount": 100}, x_company_id="3", x_company_mode="company", _current_user={}
        )
        self.assertEqual(result["status"], "Оплачен")
        self.assertEqual(result["projectPaymentId"], 77)
        self.assertTrue(connection.committed)
        insert = [c for c in cursor.calls if c[0].startswith("INSERT INTO project_payments")][0]
        self.assertEqual(insert[1][2], -100)
        self.assertEqual(audit[0][2], "pay")

    def test_pay_rejects_overpayment(self):
        act = (500, 450, "Объект", "Основная", "Мастер", "")
        cursor = FakeCursor(fetchone_results=[act])
        app, connection = build(cursor)
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/interim-acts/{id}/pay")](
                id=7, data={"amount": 100}, x_company_id="3", x_company_mode="company", _current_user={}
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("50.00", ctx.exception.detail)
        self.assertFalse(connection.committed)

    def test_delete_is_soft_cancel_with_audit(self):
        audit = []
        cursor = FakeCursor(fetchone_results=[("Основная", "Объект", "Мастер")])
        app, connection = build(cursor, audit_calls=audit)
        result = app.routes[("DELETE", "/interim-acts/{id}")](id=7, _current_user={})
        self.assertEqual(result, {"ok": True})
        self.assertIn("SET status='Аннулирован'", cursor.calls[1][0])
        self.assertEqual(audit[0][2], "cancel")
        self.assertTrue(connection.committed)


if __name__ == "__main__":
    unittest.main()
