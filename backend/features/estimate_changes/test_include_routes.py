import json
import unittest

from fastapi import HTTPException

from backend.features.estimate_changes.routes import register_estimate_changes_module
from backend.features.estimate_changes.service import estimate_change_visibility_filter


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
    def __init__(self, *, changes=None, estimate_status="Активная"):
        self.changes = changes or [{
            "id": 21,
            "company_id": 4,
            "project_id": 14,
            "description": "Дополнительная работа",
            "unit": "м2",
            "quantity": 2,
            "price": 100,
            "total": 200,
            "change_type": "Работа вне сметы",
            "estimate_id": 100,
            "section_name": "Основная",
            "estimate_item_name": "",
            "base_quantity": 0,
            "new_required_quantity": 0,
            "delta_quantity": 2,
            "reason": "Тест",
            "status": "Утверждено",
            "included_in_estimate_id": None,
        }]
        self.estimate_status = estimate_status
        self.calls = []
        self.result = []
        self.closed = False

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, tuple(params)))
        if "FROM estimates" in normalized and "COALESCE(is_template,FALSE)" in normalized:
            self.result = [{
                "id": 100,
                "company_id": 4,
                "project_id": 14,
                "project_name": "Alpha",
                "work_package": "Основная",
                "is_template": False,
            }]
        elif "FROM projects" in normalized:
            self.result = [{"id": 14, "company_id": 4, "name": "Alpha"}]
        elif "FROM estimates" in normalized and "sections_json" in normalized:
            self.result = [{
                "id": 100,
                "company_id": 4,
                "project_id": 14,
                "project_name": "Alpha",
                "name": "Смета",
                "version": "1.0",
                "sections_json": json.dumps([]),
                "smeta_type": "Заказчик",
                "work_package": "Основная",
                "status": self.estimate_status,
            }]
        elif "FROM estimates" in normalized and "smeta_type" in normalized:
            self.result = [{
                "id": 100,
                "company_id": 4,
                "project_id": 14,
                "project_name": "Alpha",
                "smeta_type": "Заказчик",
                "work_package": "Основная",
                "status": self.estimate_status,
            }]
        elif "FROM unexpected_works" in normalized and "WHERE id = ANY" in normalized:
            requested = set(params[0])
            self.result = [row for row in self.changes if row["id"] in requested]
        elif normalized.startswith("SELECT id FROM unexpected_works"):
            change_id, company_id, project_id = params[:3]
            row = next((item for item in self.changes if item["id"] == change_id), None)
            self.result = (
                [{"id": change_id}]
                if row and row["company_id"] == company_id and row["project_id"] == project_id
                else []
            )
        elif normalized.startswith("UPDATE estimates"):
            self.result = []
        elif normalized.startswith("INSERT INTO estimates"):
            self.result = [{"id": 101, "created_at": "2026-07-12"}]
        elif normalized.startswith("UPDATE unexpected_works") and "RETURNING id" in normalized:
            ids = next((value for value in params if isinstance(value, list)), [])
            self.result = [{"id": value} for value in ids]
        else:
            self.result = []

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return list(self.result)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, cursor_factory=None):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class EstimateChangeIncludeRouteTests(unittest.TestCase):
    def _register(self, connection, *, actors=None, context_error=None):
        app = FakeApp()
        selected_actors = actors or [{
            "id": 9,
            "name": "Директор выбранной компании",
            "role": "директор",
            "companyId": 4,
            "assignedProjects": [],
            "assignedPackages": [],
        }]

        def resolve_context(_cur, _user, _requested, _mode, **_kwargs):
            if context_error:
                raise context_error
            return {"mode": "company", "companyId": 4, "companyIds": [4]}

        def require_write_actor(company_actors, roles):
            normalized = list(company_actors or [])
            if len(normalized) != 1:
                raise HTTPException(status_code=409, detail="Выберите одну компанию")
            if normalized[0].get("role") not in set(roles):
                raise HTTPException(status_code=403, detail="Недостаточно прав")
            return normalized[0]

        register_estimate_changes_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, _context: selected_actors,
            "require_project_write_actor": require_write_actor,
            "require_project_row_company": lambda _actor, company_id: company_id,
            "resolve_project_parent": self._resolve_project,
            "require_project_parent_access": lambda _cur, _actor, project, _roles: project,
            "resolve_estimate_parent": self._resolve_estimate,
            "has_package_access": lambda _actor, _package: True,
            "visibility_filter": estimate_change_visibility_filter,
            "project_document_roles": ("директор",),
            "journal_write_roles": ("директор",),
            "project_write_roles": ("директор", "сметчик", "прораб"),
            "full_view_roles": ("директор", "сметчик"),
            "package_limit_roles": ("прораб",),
            "package_unrestricted_roles": ("прораб",),
            "customer_roles": ("заказчик",),
            "customer_statuses": ("Ожидает согласования", "Утверждено"),
            "worker_execution_roles": (),
            "approved_statuses": ("Утверждено", "Утверждено отдельной допработой"),
            "leadership_roles": ("директор", "зам_директора"),
            "estimate_write_roles": ("директор", "зам_директора", "прораб", "главный_инженер", "сметчик"),
            "log_audit": lambda **_kwargs: None,
        })
        return app

    @staticmethod
    def _resolve_project(cur, actor, **_kwargs):
        cur.execute("SELECT id,company_id,name FROM projects WHERE id=%s AND company_id=%s FOR UPDATE", (14, 4))
        return cur.fetchone()

    @staticmethod
    def _resolve_estimate(cur, actor, estimate_id, **_kwargs):
        cur.execute(
            "SELECT id,company_id,project_id,project_name,COALESCE(NULLIF(work_package,''),'Основная') AS work_package,COALESCE(is_template,FALSE) AS is_template FROM estimates WHERE id=%s AND company_id=%s FOR UPDATE",
            (estimate_id, actor["companyId"]),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Смета не найдена")
        return {
            "id": row["id"],
            "companyId": row["company_id"],
            "projectId": row["project_id"],
            "projectName": row["project_name"],
            "workPackage": row["work_package"],
        }

    @staticmethod
    def _call(app, path, payload, *, company_mode="company"):
        return app.routes[("POST", path)](
            100,
            payload,
            x_company_id="4" if company_mode == "company" else None,
            x_company_mode=company_mode,
            current_user={"id": 9, "name": "Глобальный директор", "role": "директор"},
        )

    def test_include_creates_owned_estimate_and_updates_only_owned_changes(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app = self._register(connection)

        response = self._call(app, "/estimates/{id}/include-changes", {"changeIds": [21]})

        insert_sql, insert_params = next(call for call in cursor.calls if call[0].startswith("INSERT INTO estimates"))
        self.assertIn("company_id,project_id", insert_sql)
        self.assertEqual(insert_params[:3], (4, 14, "Alpha"))
        update_sql, update_params = next(
            call for call in cursor.calls
            if call[0].startswith("UPDATE unexpected_works") and "included_in_estimate_id" in call[0]
        )
        self.assertIn("company_id=%s AND project_id=%s", update_sql)
        self.assertEqual(update_params[:4], (101, "Директор выбранной компании", 4, 14))
        self.assertEqual(response["includedChangeIds"], [21])
        self.assertTrue(connection.committed)

    def test_include_rejects_foreign_selected_change_before_estimate_write(self):
        cursor = FakeCursor(changes=[{
            "id": 21,
            "company_id": 8,
            "project_id": 88,
            "description": "Чужая работа",
        }])
        connection = FakeConnection(cursor)
        app = self._register(connection)

        with self.assertRaises(HTTPException) as raised:
            self._call(app, "/estimates/{id}/include-changes", {"changeIds": [21]})

        self.assertEqual(raised.exception.status_code, 403)
        self.assertFalse(any(sql.startswith("UPDATE estimates") for sql, _ in cursor.calls))
        self.assertFalse(any(sql.startswith("INSERT INTO estimates") for sql, _ in cursor.calls))
        self.assertTrue(connection.rolled_back)

    def test_include_rejects_invalid_selected_id_instead_of_auto_selecting(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app = self._register(connection)

        with self.assertRaises(HTTPException) as raised:
            self._call(app, "/estimates/{id}/include-changes", {"changeIds": ["bad"]})

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(cursor.calls, [])
        self.assertFalse(connection.committed)

    def test_reconcile_uses_server_actor_and_owner_constrained_update(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app = self._register(connection)

        response = self._call(
            app,
            "/estimates/{id}/reconcile-changes",
            {"changeIds": [21], "updatedBy": "Подмена"},
        )

        update_sql, update_params = next(
            call for call in cursor.calls
            if call[0].startswith("UPDATE unexpected_works") and "reason=CASE" in call[0]
        )
        self.assertIn("company_id=%s AND project_id=%s", update_sql)
        self.assertEqual(update_params[1], "Директор выбранной компании")
        self.assertNotIn("Подмена", update_params)
        self.assertEqual(response, {"ok": True, "includedChangeIds": [21]})
        self.assertTrue(connection.committed)

    def test_empty_reconcile_still_rejects_aggregate_company_mode(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app = self._register(connection, actors=[
            {"companyId": 4, "role": "директор"},
            {"companyId": 8, "role": "директор"},
        ])

        with self.assertRaises(HTTPException) as raised:
            self._call(app, "/estimates/{id}/reconcile-changes", {}, company_mode="all_companies")

        self.assertEqual(raised.exception.status_code, 409)
        self.assertTrue(connection.rolled_back)


if __name__ == "__main__":
    unittest.main()
