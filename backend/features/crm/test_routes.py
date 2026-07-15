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
    def __init__(self, fetchone_values=(), fetchall_values=()):
        self.fetchone_values = list(fetchone_values)
        self.fetchall_values = list(fetchall_values)
        self.calls = []
        self.rowcount = 1

    def execute(self, sql, params=()):
        self.calls.append((" ".join(str(sql).split()), tuple(params or ())))

    def fetchone(self):
        return self.fetchone_values.pop(0) if self.fetchone_values else None

    def fetchall(self):
        return self.fetchall_values.pop(0) if self.fetchall_values else []

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


def child_owner_row(record_id, company_id=4, project_id=21, lead_id=10):
    return {
        "id": record_id,
        "lead_id": lead_id,
        "company_id": company_id,
        "project_id": project_id,
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
            actor = next(
                (item for item in selected_actors if int(item.get("companyId") or 0) == int(company_id or 0)),
                None,
            )
            if not actor:
                raise HTTPException(status_code=404, detail="CRM-заявка не найдена")
            return selected_context, actor

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

    def test_summaries_only_query_companies_with_crm_role(self):
        cursor = FakeCursor(fetchall_values=[[lead_row(company_id=4)]])
        app, connection, resolver_calls, _ = self.build_app(
            cursor,
            context={"mode": "all_companies", "companyId": None},
            actors=[
                {"id": 9, "role": "директор", "companyId": 4},
                {"id": 9, "role": "рабочий", "companyId": 8},
            ],
        )

        response = app.routes[("GET", "/crm/lead-summaries")](
            x_company_id=None,
            x_company_mode="all_companies",
            current_user={"id": 9, "role": "директор"},
        )

        sql, params = next(call for call in cursor.calls if "FROM crm_leads" in call[0])
        self.assertIn("WHERE company_id = ANY(%s)", sql)
        self.assertIn("d.company_id=crm_leads.company_id", sql)
        self.assertIn("t.project_id IS NOT DISTINCT FROM crm_leads.project_id", sql)
        self.assertEqual(params, ([4],))
        self.assertEqual(response[0]["companyId"], 4)
        self.assertEqual(resolver_calls, [(None, "read", {"x_company_id": None, "x_company_mode": "all_companies"})])
        self.assertTrue(connection.closed)

    def test_details_hide_lead_from_another_company(self):
        cursor = FakeCursor(fetchone_values=[None])
        app, connection, _, _ = self.build_app(cursor)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/crm/leads/{lead_id}/details")](
                10,
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 9, "role": "директор"},
            )

        sql, params = next(call for call in cursor.calls if "FROM crm_leads" in call[0])
        self.assertIn("id=%s AND company_id = ANY(%s)", sql)
        self.assertEqual(params, (10, [4]))
        self.assertEqual(raised.exception.status_code, 404)
        self.assertTrue(connection.closed)

    def test_details_scope_children_to_exact_lead_owner(self):
        document = {"id": 31, "lead_id": 10, "company_id": 4, "project_id": 21}
        task = {"id": 41, "lead_id": 10, "company_id": 4, "project_id": 21}
        cursor = FakeCursor(
            fetchone_values=[lead_row()],
            fetchall_values=[[document], [task]],
        )
        app, connection, _, _ = self.build_app(cursor)

        response = app.routes[("GET", "/crm/leads/{lead_id}/details")](
            10,
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "директор"},
        )

        child_calls = [
            call for call in cursor.calls
            if call[0].startswith("SELECT * FROM crm_lead_documents")
            or call[0].startswith("SELECT * FROM crm_lead_tasks")
        ]
        self.assertEqual(len(child_calls), 2)
        for sql, params in child_calls:
            self.assertIn("company_id=%s", sql)
            self.assertIn("project_id IS NOT DISTINCT FROM %s", sql)
            self.assertEqual(params, (10, 4, 21))
        self.assertEqual(response["documents"][0]["leadId"], 10)
        self.assertEqual(response["tasks"][0]["leadId"], 10)
        self.assertTrue(connection.closed)

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

    def test_lead_update_uses_stored_owner_in_authorization_and_sql(self):
        cursor = FakeCursor(fetchone_values=[lead_row()])
        app, connection, _, resource_calls = self.build_app(cursor)

        response = app.routes[("PUT", "/crm/leads/{lead_id}")](
            10,
            {"name": "Обновлённый лид"},
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "директор"},
        )

        sql, params = next(call for call in cursor.calls if call[0].startswith("UPDATE crm_leads SET"))
        self.assertTrue(cursor.calls[0][0].endswith("FOR UPDATE"))
        self.assertIn("WHERE id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s", sql)
        self.assertEqual(params[-3:], (10, 4, 21))
        self.assertEqual(resource_calls[0][:2], (4, "update"))
        self.assertEqual(response, {"ok": True})
        self.assertEqual(connection.commits, 1)
        self.assertTrue(connection.closed)

    def test_lead_update_rejects_foreign_company_before_update(self):
        cursor = FakeCursor(fetchone_values=[lead_row(company_id=8)])
        app, connection, _, resource_calls = self.build_app(cursor)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("PUT", "/crm/leads/{lead_id}")](
                10,
                {"name": "Чужой лид"},
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 9, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(resource_calls[0][:2], (8, "update"))
        self.assertFalse(any(sql.startswith("UPDATE crm_leads SET") for sql, _ in cursor.calls))
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)

    def test_lead_delete_scopes_parent_and_children_to_exact_owner(self):
        cursor = FakeCursor(fetchone_values=[lead_row()])
        app, connection, _, resource_calls = self.build_app(cursor)

        response = app.routes[("DELETE", "/crm/leads/{lead_id}")](
            10,
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "директор"},
        )

        delete_calls = [call for call in cursor.calls if call[0].startswith("DELETE FROM crm_")]
        self.assertEqual(len(delete_calls), 3)
        for sql, params in delete_calls:
            self.assertIn("company_id=%s", sql)
            self.assertIn("project_id IS NOT DISTINCT FROM %s", sql)
            self.assertEqual(params, (10, 4, 21))
        self.assertEqual(resource_calls[0][:2], (4, "delete"))
        self.assertEqual(response, {"ok": True})
        self.assertEqual(connection.commits, 1)

    def test_lead_delete_stops_on_mismatched_child_owner(self):
        cursor = FakeCursor(fetchone_values=[lead_row(), {"exists": 1}])
        app, connection, _, _ = self.build_app(cursor)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("DELETE", "/crm/leads/{lead_id}")](
                10,
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 9, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertFalse(any(sql.startswith("DELETE FROM crm_") for sql, _ in cursor.calls))
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)

    def test_document_update_scopes_exact_stored_owner(self):
        updated = {**child_owner_row(31), "title": "Договор", "created_at": "2026-07-15"}
        cursor = FakeCursor(fetchone_values=[child_owner_row(31), updated])
        app, connection, _, resource_calls = self.build_app(cursor)

        response = app.routes[("PUT", "/crm/documents/{doc_id}")](
            31,
            {"title": "Договор"},
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "директор"},
        )

        sql, params = next(call for call in cursor.calls if call[0].startswith("UPDATE crm_lead_documents SET"))
        self.assertIn("FOR UPDATE OF child,lead", cursor.calls[0][0])
        self.assertIn("WHERE id=%s AND lead_id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s", sql)
        self.assertEqual(params[-4:], (31, 10, 4, 21))
        self.assertEqual(resource_calls[0][:2], (4, "update"))
        self.assertEqual(response["leadId"], 10)
        self.assertEqual(connection.commits, 1)

    def test_document_delete_scopes_exact_stored_owner(self):
        cursor = FakeCursor(fetchone_values=[child_owner_row(31)])
        app, connection, _, resource_calls = self.build_app(cursor)

        response = app.routes[("DELETE", "/crm/documents/{doc_id}")](
            31,
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "директор"},
        )

        sql, params = next(call for call in cursor.calls if call[0].startswith("DELETE FROM crm_lead_documents"))
        self.assertIn("id=%s AND lead_id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s", sql)
        self.assertEqual(params, (31, 10, 4, 21))
        self.assertEqual(resource_calls[0][:2], (4, "delete"))
        self.assertEqual(response, {"ok": True})

    def test_task_update_scopes_exact_stored_owner(self):
        updated = {**child_owner_row(41), "title": "Позвонить", "created_at": "2026-07-15"}
        cursor = FakeCursor(fetchone_values=[child_owner_row(41), updated])
        app, connection, _, resource_calls = self.build_app(cursor)

        response = app.routes[("PUT", "/crm/tasks/{task_id}")](
            41,
            {"title": "Позвонить", "status": "Закрыта"},
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "директор"},
        )

        sql, params = next(call for call in cursor.calls if call[0].startswith("UPDATE crm_lead_tasks SET"))
        self.assertIn("FOR UPDATE OF child,lead", cursor.calls[0][0])
        self.assertIn("WHERE id=%s AND lead_id=%s AND company_id=%s AND project_id IS NOT DISTINCT FROM %s", sql)
        self.assertEqual(params[-4:], (41, 10, 4, 21))
        self.assertIn("completed_at=NOW()", sql)
        self.assertEqual(resource_calls[0][:2], (4, "update"))
        self.assertEqual(response["leadId"], 10)
        self.assertEqual(connection.commits, 1)

    def test_task_delete_rejects_foreign_company_before_delete(self):
        cursor = FakeCursor(fetchone_values=[child_owner_row(41, company_id=8)])
        app, connection, _, resource_calls = self.build_app(cursor)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("DELETE", "/crm/tasks/{task_id}")](
                41,
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 9, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(resource_calls[0][:2], (8, "delete"))
        self.assertFalse(any(sql.startswith("DELETE FROM crm_lead_tasks") for sql, _ in cursor.calls))
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)

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
        lead_update_sql, lead_update_params = next(
            call for call in cursor.calls if call[0].startswith("UPDATE crm_leads SET document_status")
        )
        self.assertIn("company_id=%s", lead_update_sql)
        self.assertIn("project_id IS NOT DISTINCT FROM %s", lead_update_sql)
        self.assertEqual(lead_update_params, (10, 4, 21))
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
