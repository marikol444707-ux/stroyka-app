import unittest

import psycopg2.extras
from fastapi import HTTPException

from .routes import register_crm_module


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

    def post(self, path):
        return self._register("POST", path)

    def put(self, path):
        return self._register("PUT", path)

    def delete(self, path):
        return self._register("DELETE", path)


class FakeCursor:
    def __init__(self, fetchone_values=()):
        self.fetchone_values = list(fetchone_values)
        self.calls = []
        self.rowcount = 1

    def execute(self, sql, params=()):
        self.calls.append((" ".join(str(sql).split()), tuple(params or ())))

    def fetchone(self):
        return self.fetchone_values.pop(0) if self.fetchone_values else None

    def fetchall(self):
        return []

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.cursor_kwargs = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self, **kwargs):
        self.cursor_kwargs.append(kwargs)
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def lead_row(company_id=4, project_id=21):
    return {
        "id": 10,
        "companyId": company_id,
        "projectId": project_id,
        "name": "Лид",
        "budget": 0,
        "area": 0,
        "documentsCount": 0,
        "openTasksCount": 0,
    }


class CrmRouteOwnershipTests(unittest.TestCase):
    def build_app(self, route_cursor, *, context=None, actors=None):
        schema_connection = FakeConnection(FakeCursor())
        route_connection = FakeConnection(route_cursor)
        connections = [schema_connection, route_connection]
        resolver_calls = []
        resource_calls = []
        selected_context = context or {"mode": "company", "companyId": 4}
        selected_actors = actors or [{"id": 9, "name": "Директор", "role": "директор", "companyId": 4}]

        def resolve_context(cur, user, requested_company_id, action_mode, **kwargs):
            resolver_calls.append((requested_company_id, action_mode, kwargs))
            return selected_context

        def resolve_resource(cur, user, company_id, action_mode, **kwargs):
            resource_calls.append((company_id, action_mode, kwargs))
            return selected_context, selected_actors[0]

        app = FakeApp()
        register_crm_module(app, {
            "get_db": lambda: connections.pop(0),
            "require_roles": lambda *_roles: lambda: {},
            "leadership_roles": ("директор", "зам_директора"),
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, _context: selected_actors,
            "resolve_resource_company_actor": resolve_resource,
        })
        return app, route_connection, resolver_calls, resource_calls

    def test_create_stores_selected_company_and_server_actor(self):
        cursor = FakeCursor(fetchone_values=[{"id": 77}])
        app, connection, resolver_calls, _ = self.build_app(cursor)

        response = app.routes[("POST", "/crm/leads")](
            {"name": "Новый лид", "companyId": 999, "createdBy": "Подмена"},
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "name": "Директор", "role": "директор"},
        )

        sql, params = next(call for call in cursor.calls if call[0].startswith("INSERT INTO crm_leads"))
        self.assertIn("company_id,name", sql)
        self.assertEqual(sql.count("%s"), len(params))
        self.assertEqual(params[0], 4)
        self.assertEqual(params[8], "Директор")
        self.assertEqual(resolver_calls, [(None, "create", {"x_company_id": "4", "x_company_mode": "company"})])
        self.assertEqual(response, {"ok": True, "id": 77})
        self.assertIs(connection.cursor_kwargs[0].get("cursor_factory"), psycopg2.extras.RealDictCursor)
        self.assertEqual(connection.commits, 1)

    def test_create_rejects_all_companies_before_insert(self):
        cursor = FakeCursor()
        app, connection, _, _ = self.build_app(
            cursor,
            context={"mode": "all_companies", "companyId": None},
            actors=[
                {"role": "директор", "companyId": 4},
                {"role": "директор", "companyId": 8},
            ],
        )

        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/crm/leads")](
                {"name": "Новый лид"},
                x_company_id=None,
                x_company_mode="all_companies",
                current_user={"id": 9, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertFalse(any(sql.startswith("INSERT INTO crm_leads") for sql, _ in cursor.calls))
        self.assertEqual(connection.rollbacks, 1)

    def test_document_inherits_exact_parent_owner(self):
        inserted = {
            "id": 31,
            "company_id": 4,
            "project_id": 21,
            "lead_id": 10,
            "created_at": "2026-07-15",
        }
        cursor = FakeCursor(fetchone_values=[lead_row(), inserted])
        app, connection, _, resource_calls = self.build_app(cursor)

        response = app.routes[("POST", "/crm/leads/{lead_id}/documents")](
            10,
            {"title": "Договор", "companyId": 999},
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "директор"},
        )

        sql, params = next(call for call in cursor.calls if call[0].startswith("INSERT INTO crm_lead_documents"))
        self.assertIn("company_id,project_id,lead_id", sql)
        self.assertEqual(sql.count("%s"), len(params))
        self.assertEqual(params[:3], (4, 21, 10))
        self.assertEqual(resource_calls[0][:2], (4, "create"))
        self.assertEqual(response["leadId"], 10)
        self.assertEqual(connection.commits, 1)

    def test_task_inherits_exact_parent_owner(self):
        inserted = {
            "id": 41,
            "company_id": 4,
            "project_id": 21,
            "lead_id": 10,
            "created_at": "2026-07-15",
        }
        cursor = FakeCursor(fetchone_values=[lead_row(), inserted])
        app, connection, _, resource_calls = self.build_app(cursor)

        response = app.routes[("POST", "/crm/leads/{lead_id}/tasks")](
            10,
            {"title": "Позвонить", "companyId": 999},
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "директор"},
        )

        sql, params = next(call for call in cursor.calls if call[0].startswith("INSERT INTO crm_lead_tasks"))
        self.assertIn("company_id,project_id,lead_id", sql)
        self.assertEqual(sql.count("%s"), len(params))
        self.assertEqual(params[:3], (4, 21, 10))
        self.assertEqual(resource_calls[0][:2], (4, "create"))
        self.assertEqual(response["leadId"], 10)
        self.assertEqual(connection.commits, 1)

    def test_child_write_rejects_unowned_legacy_lead_and_closes_connection(self):
        cursor = FakeCursor(fetchone_values=[lead_row(company_id=None, project_id=None)])
        app, connection, _, resource_calls = self.build_app(cursor)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/crm/leads/{lead_id}/tasks")](
                10,
                {"title": "Позвонить"},
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 9, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(resource_calls, [])
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
