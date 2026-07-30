import unittest

from unittest.mock import patch

from fastapi import HTTPException

from backend.features.clients.routes import ClientModel, register_clients_module
from backend.features.crm.lead_routes import register_crm_leads_module


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


def clients_build(cursor):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_clients_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "admin_roles": ("директор",),
        "worker_execution_roles": ("мастер",),
    })
    return app, connection


def leads_build(cursor):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_crm_leads_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "admin_roles": ("директор",),
        "resolve_work_company_context": lambda cur, user, project, mode, **kw: {"mode": "company", "companyId": 3},
        "effective_company_actors": lambda user, ctx: [{"companyId": 3, "role": "директор"}],
        "resolve_crm_create_owner": lambda cur, user, cid, cmode: {"companyId": 3},
    })
    return app, connection


class ClientsAndCrmLeadsTest(unittest.TestCase):
    def test_all_urls_registered(self):
        capp, _c = clients_build(FakeCursor())
        lapp, _l = leads_build(FakeCursor())
        for key in [("GET", "/clients"), ("POST", "/clients"), ("PUT", "/clients/{id}"), ("DELETE", "/clients/{id}")]:
            self.assertIn(key, capp.routes)
        for key in [("GET", "/crm-leads"), ("POST", "/crm-leads"), ("PUT", "/crm-leads/{id}"), ("DELETE", "/crm-leads/{id}")]:
            self.assertIn(key, lapp.routes)

    def test_client_create_maps_model_fields(self):
        cursor = FakeCursor(fetchone_results=[{"id": 4, "name": "ООО Клиент"}])
        app, _conn = clients_build(cursor)
        result = app.routes[("POST", "/clients")](
            ClientModel(name="ООО Клиент", phone="+7"), _current_user={}
        )
        self.assertEqual(result["name"], "ООО Клиент")
        self.assertEqual(cursor.calls[0][1][:2], ("ООО Клиент", "+7"))

    def test_leads_read_carries_company_scope(self):
        cursor = FakeCursor(rows=[])
        app, _conn = leads_build(cursor)
        with patch("backend.features.crm.lead_routes.restrict_crm_read_context",
                   lambda ctx, actors, allowed_roles: ctx), \
             patch("backend.features.crm.lead_routes.company_id_scope_filter",
                   lambda ctx, col: (" AND crm_leads.company_id=%s", [3])):
            app.routes[("GET", "/crm-leads")](
                x_company_id="3", x_company_mode="company",
                current_user={"role": "директор"},
            )
        sql, params = cursor.calls[0]
        self.assertIn("crm_leads.company_id=%s", sql)
        self.assertEqual(params, (3,))

    def test_lead_create_uses_resolved_owner_company(self):
        cursor = FakeCursor(fetchone_results=[{"id": 15}])
        app, connection = leads_build(cursor)
        result = app.routes[("POST", "/crm-leads")](
            {"name": "Лид"}, x_company_id="3", x_company_mode="company", _current_user={"name": "Тест"},
        )
        self.assertEqual(result, {"ok": True, "id": 15})
        insert = cursor.calls[0]
        self.assertEqual(insert[1][0], 3)
        self.assertTrue(connection.committed)


if __name__ == "__main__":
    unittest.main()
