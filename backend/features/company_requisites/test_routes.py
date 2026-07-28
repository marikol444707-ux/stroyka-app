import unittest

from fastapi import HTTPException

from backend.features.company_requisites.routes import register_company_requisites_module


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
    def __init__(self, row=None):
        self.row = row
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def build(cursor, context=None, actors=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_company_requisites_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "resolve_work_company_context": lambda cur, user, claimed, mode, **kw: dict(context or {}),
        "effective_company_actors": lambda user, ctx: list(actors or []),
        "positive_int_or_none": lambda v: int(v) if v and int(v) > 0 else None,
        "finance_roles": ("директор", "бухгалтер"),
    })
    return app, connection


class CompanyRequisitesRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor())
        self.assertIn(("GET", "/company-requisites"), app.routes)
        self.assertIn(("POST", "/company-requisites"), app.routes)

    def test_get_requires_company_selection(self):
        app, connection = build(FakeCursor(), context={"mode": "all_companies"})
        result = app.routes[("GET", "/company-requisites")](
            x_company_id=None, x_company_mode="all_companies", _current_user={}
        )
        self.assertEqual(result, {"companyId": None, "requiresCompanySelection": True})
        self.assertTrue(connection.closed)

    def test_get_returns_mapped_requisites(self):
        row = {"id": 1, "company_id": 7, "full_name": "ООО Тест", "short_name": "Тест",
               "inn": "123", "kpp": "", "ogrn": "", "legal_address": "", "actual_address": "",
               "phone": "", "email": "", "director_name": "", "director_position": "",
               "basis": "", "bank_name": "", "bik": "", "rs": "", "ks": ""}
        app, _conn = build(FakeCursor(row=row), context={"mode": "company", "companyId": 7})
        result = app.routes[("GET", "/company-requisites")](
            x_company_id="7", x_company_mode="company", _current_user={}
        )
        self.assertEqual(result["companyId"], 7)
        self.assertEqual(result["fullName"], "ООО Тест")
        self.assertEqual(result["inn"], "123")

    def test_post_rejects_wrong_company_role(self):
        app, connection = build(
            FakeCursor(),
            context={"mode": "company", "companyId": 7},
            actors=[{"companyId": 7, "role": "мастер"}],
        )
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/company-requisites")](
                {"fullName": "X"}, x_company_id="7", x_company_mode="company", _current_user={}
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertTrue(connection.rolled_back)

    def test_post_upserts_for_finance_role(self):
        cursor = FakeCursor(row={"id": 3, "company_id": 7})
        app, connection = build(
            cursor,
            context={"mode": "company", "companyId": 7},
            actors=[{"companyId": 7, "role": "директор"}],
        )
        result = app.routes[("POST", "/company-requisites")](
            {"fullName": "ООО Тест", "inn": "123"},
            x_company_id="7", x_company_mode="company", _current_user={},
        )
        self.assertEqual(result, {"id": 3, "companyId": 7, "ok": True})
        self.assertTrue(connection.committed)
        sql, params = cursor.calls[0]
        self.assertIn("ON CONFLICT (company_id) DO UPDATE", sql)
        self.assertEqual(params[0], 7)
        self.assertEqual(params[1], "ООО Тест")


if __name__ == "__main__":
    unittest.main()
