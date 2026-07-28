import unittest

from fastapi import HTTPException

from backend.features.supplier_invoice_templates.routes import register_supplier_invoice_templates_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

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
        self.closed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def build(cursor, audit_calls):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_supplier_invoice_templates_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "warehouse_roles": ("кладовщик",),
        "supplier_invoice_template_row": lambda row: dict(row),
        "supplier_invoice_template_key": lambda name: name.lower().replace(" ", ""),
        "scan_invoice_supplier_name": lambda data: "",
        "find_supplier_by_name_key": lambda cur, name: None,
        "log_audit": lambda **kw: audit_calls.append(kw),
    })
    return app, connection


class SupplierInvoiceTemplatesRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor(), [])
        self.assertIn(("GET", "/supplier-invoice-templates"), app.routes)
        self.assertIn(("POST", "/supplier-invoice-templates/learn"), app.routes)

    def test_learn_requires_supplier_name(self):
        app, _conn = build(FakeCursor(), [])
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/supplier-invoice-templates/learn")]({}, current_user={"name": "Тест"})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_learn_inserts_new_template_and_writes_audit(self):
        saved = {"id": 5, "supplierId": None, "supplierName": "ООО Поставка",
                 "templateName": "Счет/накладная ООО Поставка"}
        cursor = FakeCursor(fetchone_results=[None, saved])
        audit_calls = []
        app, connection = build(cursor, audit_calls)
        result = app.routes[("POST", "/supplier-invoice-templates/learn")](
            {"supplierName": "ООО Поставка", "items": [{"name": "цемент"}]},
            current_user={"name": "Тест", "role": "кладовщик"},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["recognition"]["method"], "template")
        self.assertTrue(connection.committed)
        insert_calls = [c for c in cursor.calls if c[0].startswith("INSERT INTO supplier_invoice_templates")]
        self.assertEqual(len(insert_calls), 1)
        self.assertEqual(len(audit_calls), 1)
        self.assertEqual(audit_calls[0]["action"], "learn")


if __name__ == "__main__":
    unittest.main()
