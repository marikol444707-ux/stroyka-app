import unittest
from decimal import Decimal

from fastapi import HTTPException

from .company_features import register_company_feature_routes


class FakeApp:
    def __init__(self):
        self.routes = {}

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator

    def get(self, path):
        return self._register("GET", path)

    def put(self, path):
        return self._register("PUT", path)


class FakeCursor:
    def __init__(self, rows=(), row=None, one_rows=()):
        self.rows = list(rows)
        self.one_rows = list(one_rows)
        self.row = row
        self.calls = []
        self.rowcount = 1

    def execute(self, sql, params=()):
        self.calls.append((" ".join(str(sql).split()), tuple(params or ())))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        if self.one_rows:
            return self.one_rows.pop(0)
        return self.row

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.committed = 0
        self.rolled_back = 0

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        pass


class CompanyFeatureRouteTests(unittest.TestCase):
    def build(self, cursor):
        app = FakeApp()
        conn = FakeConnection(cursor)
        audits = []
        register_company_feature_routes(app, {
            "get_db": lambda: conn,
            "require_roles": lambda *_roles: lambda: {"id": 1, "role": "platform_admin"},
            "manage_roles": ("system_owner", "platform_admin"),
            "write_audit": lambda *args, **kwargs: audits.append((args, kwargs)),
        })
        return app, conn, audits

    def test_feature_list_reports_enabled_company_monthly_revenue(self):
        cursor = FakeCursor(rows=[
            {"company_id": 8, "company_name": "ООО Тест", "company_active": True, "enabled": True, "monthly_fee": "12000.00"},
            {"company_id": 9, "company_name": "ООО Демо", "company_active": True, "enabled": False, "monthly_fee": "0.00"},
        ])
        app, _conn, _audits = self.build(cursor)

        response = app.routes[("GET", "/system/company-features/jev")](
            current_user={"id": 1, "role": "platform_admin"}
        )

        self.assertEqual(response["potentialMonthlyRevenue"], "12000.00")
        self.assertEqual([row["companyId"] for row in response["companies"]], [8, 9])
        self.assertTrue(response["companies"][0]["enabled"])

    def test_update_validates_price_and_writes_company_scoped_audit(self):
        cursor = FakeCursor(one_rows=[
            {"id": 8, "platform_account_id": 3, "name": "ООО Тест", "active": True},
            {"enabled": False, "monthly_fee": "0.00"},
            {"enabled": True, "monthly_fee": "12500.50", "updated_at": None},
        ])
        app, conn, audits = self.build(cursor)

        response = app.routes[("PUT", "/system/companies/{company_id}/features/jev")](
            8, {"enabled": True, "monthlyFee": "12500.50"},
            current_user={"id": 1, "role": "platform_admin"},
        )

        self.assertEqual(response["monthlyFee"], "12500.50")
        self.assertEqual(conn.committed, 1)
        self.assertEqual(len(audits), 1)
        update = next(call for call in cursor.calls if call[0].startswith("INSERT INTO public.platform_company_features"))
        self.assertEqual(update[1][:4], (8, "jev_procurement", True, Decimal("12500.50")))

    def test_update_rejects_invalid_monthly_fee_without_database_write(self):
        cursor = FakeCursor()
        app, conn, _audits = self.build(cursor)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("PUT", "/system/companies/{company_id}/features/jev")](
                8, {"enabled": True, "monthlyFee": "-1"},
                current_user={"id": 1, "role": "platform_admin"},
            )

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(cursor.calls, [])
        self.assertEqual(conn.committed, 0)

    def test_internal_company_cannot_be_charged(self):
        cursor = FakeCursor(one_rows=[{"id": 1, "platform_account_id": None, "name": "Стройка", "active": True}])
        app, conn, _audits = self.build(cursor)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("PUT", "/system/companies/{company_id}/features/jev")](
                1, {"enabled": True, "monthlyFee": "5000"},
                current_user={"id": 1, "role": "platform_admin"},
            )

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(conn.committed, 0)


if __name__ == "__main__":
    unittest.main()
