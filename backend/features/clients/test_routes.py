import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from backend.features.clients.routes import ClientModel, register_clients_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path): return self._register("GET", path)
    def post(self, path): return self._register("POST", path)
    def put(self, path): return self._register("PUT", path)
    def delete(self, path): return self._register("DELETE", path)

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

    def fetchall(self): return list(self.rows)
    def fetchone(self): return self.fetchone_results.pop(0) if self.fetchone_results else None
    def close(self): pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self, **_kwargs): return self._cursor
    def commit(self): self.committed = True
    def rollback(self): self.rolled_back = True
    def close(self): pass


def build(cursor, *, context=None, actors=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    selected = context or {"mode": "company", "companyId": 3}
    company_actors = actors if actors is not None else [
        {"id": 8, "companyId": 3, "role": "директор"},
    ]
    register_clients_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: None,
        "require_roles": lambda *_roles: (lambda: None),
        "resolve_work_company_context": lambda *_args, **_kwargs: selected,
        "effective_company_actors": lambda *_args: company_actors,
        "admin_roles": ("директор", "зам_директора"),
    })
    return app, connection


REQUEST = SimpleNamespace(headers={"x-company-id": "3", "x-company-mode": "company"})


class ClientsRoutesTest(unittest.TestCase):
    def test_all_urls_registered(self):
        app, _connection = build(FakeCursor())
        for key in (("GET", "/clients"), ("POST", "/clients"),
                    ("PUT", "/clients/{id}"), ("DELETE", "/clients/{id}")):
            self.assertIn(key, app.routes)

    def test_list_is_scoped_to_selected_company(self):
        cursor = FakeCursor(rows=[{"id": 4, "company_id": 3, "name": "ООО Заказчик"}])
        app, _connection = build(cursor)
        rows = app.routes[("GET", "/clients")](
            current_user={"role": "директор"}, request=REQUEST,
        )
        self.assertEqual(rows[0]["companyId"], 3)
        sql, params = cursor.calls[0]
        self.assertIn("WHERE company_id=%s", sql)
        self.assertEqual(params, (3,))

    def test_all_companies_mode_does_not_return_a_combined_directory(self):
        app, _connection = build(FakeCursor(), context={"mode": "all", "companyId": None}, actors=[])
        result = app.routes[("GET", "/clients")](
            current_user={"role": "директор"}, request=SimpleNamespace(headers={}),
        )
        self.assertEqual(result, [])

    def test_create_uses_server_selected_company_and_structured_requisites(self):
        cursor = FakeCursor(fetchone_results=[{
            "id": 4, "company_id": 3, "name": "ООО Заказчик", "inn": "2632090186",
        }])
        app, connection = build(cursor)
        row = app.routes[("POST", "/clients")](
            ClientModel(name="ООО Заказчик", inn="2632090186", directorName="Иванов И.И."),
            current_user={"role": "директор"}, request=REQUEST,
        )
        self.assertEqual(row["companyId"], 3)
        insert_sql, insert_params = cursor.calls[0]
        self.assertIn("company_id", insert_sql)
        self.assertEqual(insert_params[0], 3)
        self.assertEqual(insert_params[1], "ООО Заказчик")
        self.assertIn("2632090186", insert_params)
        self.assertTrue(connection.committed)

    def test_update_locks_row_to_selected_company(self):
        cursor = FakeCursor(fetchone_results=[{"id": 4, "company_id": 3}])
        app, connection = build(cursor)
        result = app.routes[("PUT", "/clients/{id}")](
            4, ClientModel(name="ООО Заказчик"),
            current_user={"role": "директор"}, request=REQUEST,
        )
        self.assertEqual(result, {"ok": True})
        self.assertIn("WHERE id=%s AND company_id=%s", cursor.calls[-1][0])
        self.assertEqual(cursor.calls[-1][1][-2:], (4, 3))
        self.assertTrue(connection.committed)

    def test_cross_company_update_is_hidden(self):
        cursor = FakeCursor(fetchone_results=[None])
        app, connection = build(cursor)
        with self.assertRaises(HTTPException) as raised:
            app.routes[("PUT", "/clients/{id}")](
                99, ClientModel(name="Чужой"),
                current_user={"role": "директор"}, request=REQUEST,
            )
        self.assertEqual(raised.exception.status_code, 404)
        self.assertFalse(connection.committed)


if __name__ == "__main__":
    unittest.main()
