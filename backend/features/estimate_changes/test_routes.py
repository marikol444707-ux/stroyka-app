import os
import subprocess
import sys
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.features.estimate_changes.routes import register_estimate_changes_module
from backend.features.estimate_changes.service import estimate_change_visibility_filter


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorator(handler):
            self.routes[("GET", path)] = handler
            return handler

        return decorator

    def post(self, path):
        def decorator(handler):
            self.routes[("POST", path)] = handler
            return handler

        return decorator


class FakeCursor:
    def __init__(self, row=None):
        self.row = row or {"id": 77}
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
        self.cursor_value = cursor
        self.cursor_factory = None
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, cursor_factory=None):
        self.cursor_factory = cursor_factory
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class EstimateChangeCreateRouteTests(unittest.TestCase):
    def test_module_imports_from_backend_working_directory(self):
        backend_dir = Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = ""
        env["PYTHONPYCACHEPREFIX"] = "/tmp/stroyka-pycache"

        result = subprocess.run(
            [sys.executable, "-c", "from features.estimate_changes.routes import register_estimate_changes_module"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def _register(
        self,
        connection,
        *,
        context=None,
        context_error=None,
        actors=None,
        project=None,
        estimates=None,
        package_allowed=True,
    ):
        app = FakeApp()
        calls = {
            "context": [],
            "project": [],
            "projectAccess": [],
            "estimate": [],
            "package": [],
        }
        selected_context = context or {
            "mode": "company",
            "companyId": 4,
            "companyIds": [4],
            "effectiveRole": "директор",
        }
        selected_actors = actors or [{
            "id": 9,
            "name": "Директор выбранной компании",
            "role": "директор",
            "companyId": 4,
            "assignedProjects": [],
            "assignedPackages": [],
        }]
        selected_project = project or {"id": 14, "companyId": 4, "name": "Alpha"}
        estimate_rows = estimates or {
            100: {
                "id": 100,
                "companyId": 4,
                "projectId": 14,
                "projectName": "Alpha",
                "workPackage": "Основная",
            },
            101: {
                "id": 101,
                "companyId": 4,
                "projectId": 14,
                "projectName": "Alpha",
                "workPackage": "Основная",
            },
        }

        def resolve_context(cur, user, requested_company_id, action_mode, **kwargs):
            calls["context"].append((cur, user, requested_company_id, action_mode, kwargs))
            if context_error:
                raise context_error
            return selected_context

        def require_write_actor(company_actors, allowed_roles):
            normalized = list(company_actors or [])
            if len(normalized) != 1:
                raise HTTPException(status_code=409, detail="Выберите одну компанию")
            actor = normalized[0]
            if actor.get("role") not in set(allowed_roles or ()):
                raise HTTPException(status_code=403, detail="Роль не может создать допработу")
            return actor

        def resolve_project(cur, actor, **kwargs):
            calls["project"].append((cur, actor, kwargs))
            return selected_project

        def require_project_access(cur, actor, parent, full_roles):
            calls["projectAccess"].append((cur, actor, parent, tuple(full_roles)))
            return parent

        def resolve_estimate(cur, actor, estimate_id, **kwargs):
            calls["estimate"].append((cur, actor, estimate_id, kwargs))
            row = estimate_rows.get(estimate_id)
            if not row:
                raise HTTPException(status_code=404, detail="Смета не найдена")
            return row

        def has_package(actor, package):
            calls["package"].append((actor, package))
            return package_allowed

        register_estimate_changes_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, _context: selected_actors,
            "require_project_write_actor": require_write_actor,
            "resolve_project_parent": resolve_project,
            "require_project_parent_access": require_project_access,
            "resolve_estimate_parent": resolve_estimate,
            "has_package_access": has_package,
            "visibility_filter": estimate_change_visibility_filter,
            "project_document_roles": (
                "директор",
                "зам_директора",
                "бухгалтер",
                "прораб",
                "главный_инженер",
                "сметчик",
                "мастер",
                "субподрядчик",
                "бригадир",
                "кладовщик",
                "снабженец",
                "технадзор",
                "заказчик",
                "стройконтроль",
            ),
            "journal_write_roles": (
                "директор",
                "зам_директора",
                "прораб",
                "главный_инженер",
                "мастер",
                "субподрядчик",
                "бригадир",
            ),
            "full_view_roles": (
                "директор",
                "зам_директора",
                "бухгалтер",
                "главный_инженер",
                "сметчик",
            ),
            "package_limit_roles": ("прораб", "мастер", "субподрядчик", "бригадир"),
            "package_unrestricted_roles": ("прораб",),
            "customer_roles": ("заказчик",),
            "customer_statuses": (
                "Ожидает согласования",
                "Утверждено",
                "Утверждено отдельной допработой",
                "Включено в новую смету",
            ),
            "worker_execution_roles": ("мастер", "субподрядчик", "бригадир"),
        })
        return app, calls

    def _create(self, app, payload, current_user=None, company_id="4", company_mode="company"):
        return app.routes[("POST", "/unexpected-works")](
            payload,
            x_company_id=company_id,
            x_company_mode=company_mode,
            current_user=current_user or {"id": 9, "name": "Глобальный директор", "role": "директор"},
        )

    def test_create_stores_server_resolved_company_and_project(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app, calls = self._register(connection)

        response = self._create(app, {
            "projectName": "Клиентское название",
            "projectId": 14,
            "companyId": 999,
            "description": "Дополнительная работа",
            "quantity": 2,
            "price": 100,
            "total": 200,
            "estimateId": 100,
            "includedInEstimateId": 101,
        })

        self.assertEqual(calls["context"][0][3], "create")
        self.assertEqual(calls["context"][0][4]["x_company_id"], "4")
        self.assertEqual(calls["project"][0][2], {
            "project_id": 14,
            "project_name": "Клиентское название",
        })
        self.assertEqual([item[2] for item in calls["estimate"]], [100, 101])
        sql, params = cursor.calls[-1]
        self.assertIn("INSERT INTO unexpected_works", sql)
        self.assertIn("project_name,project_id,company_id", sql)
        self.assertEqual(params[:3], ("Alpha", 14, 4))
        self.assertEqual(response, {"id": 77, "ok": True})
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)

    def test_create_uses_effective_worker_role_for_money_and_identity(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        worker = {
            "id": 15,
            "name": "Мастер выбранной компании",
            "role": "мастер",
            "companyId": 4,
            "assignedProjects": ["Alpha"],
            "assignedPackages": ["Общестрой"],
        }
        app, _ = self._register(connection, actors=[worker])

        self._create(
            app,
            {
                "projectName": "Alpha",
                "sectionName": "Общестрой",
                "price": 500,
                "total": 1000,
                "status": "Утверждено",
                "addedBy": "Подмена",
                "addedByRole": "директор",
            },
            current_user={"id": 15, "name": "Глобальное имя", "role": "директор"},
        )

        _sql, params = cursor.calls[-1]
        self.assertEqual(params[6:11], (0.0, 0.0, "Мастер выбранной компании", "мастер", "Ожидает согласования"))

    def test_create_rejects_all_companies_before_insert(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app, _ = self._register(
            connection,
            context={"mode": "all_companies", "companyId": None, "companyIds": [4, 5]},
            actors=[
                {"id": 9, "role": "директор", "companyId": 4},
                {"id": 9, "role": "директор", "companyId": 5},
            ],
        )

        with self.assertRaises(HTTPException) as raised:
            self._create(app, {"projectName": "Alpha"}, company_id=None, company_mode="all_companies")

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(cursor.calls, [])
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_create_rejects_unavailable_company_before_insert(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app, _ = self._register(
            connection,
            context_error=HTTPException(status_code=403, detail="Нет доступа к выбранной компании"),
        )

        with self.assertRaises(HTTPException) as raised:
            self._create(app, {"projectName": "Alpha"}, company_id="99")

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(cursor.calls, [])
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_create_rejects_cross_project_estimate_before_insert(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app, _ = self._register(connection, estimates={
            100: {
                "id": 100,
                "companyId": 4,
                "projectId": 99,
                "projectName": "Other",
                "workPackage": "Основная",
            },
        })

        with self.assertRaises(HTTPException) as raised:
            self._create(app, {"projectName": "Alpha", "estimateId": 100})

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(cursor.calls, [])
        self.assertTrue(connection.rolled_back)

    def test_create_rejects_cross_project_included_estimate_before_insert(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app, _ = self._register(connection, estimates={
            101: {
                "id": 101,
                "companyId": 4,
                "projectId": 99,
                "projectName": "Other",
                "workPackage": "Основная",
            },
        })

        with self.assertRaises(HTTPException) as raised:
            self._create(app, {"projectName": "Alpha", "includedInEstimateId": 101})

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(cursor.calls, [])
        self.assertTrue(connection.rolled_back)

    def test_create_rejects_effective_role_without_package_access(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        worker = {
            "id": 15,
            "name": "Мастер",
            "role": "мастер",
            "companyId": 4,
            "assignedProjects": ["Alpha"],
            "assignedPackages": ["Электрика"],
        }
        app, calls = self._register(connection, actors=[worker], package_allowed=False)

        with self.assertRaises(HTTPException) as raised:
            self._create(app, {"projectName": "Alpha", "sectionName": "Общестрой"})

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(calls["package"][0][1], "Общестрой")
        self.assertEqual(cursor.calls, [])
        self.assertTrue(connection.rolled_back)

    def test_create_rejects_invalid_explicit_estimate_id(self):
        for invalid_id in ("not-an-id", 1.5, "1.5", True, 0, -1):
            with self.subTest(invalid_id=invalid_id):
                cursor = FakeCursor()
                connection = FakeConnection(cursor)
                app, _ = self._register(connection)

                with self.assertRaises(HTTPException) as raised:
                    self._create(app, {"projectName": "Alpha", "estimateId": invalid_id})

                self.assertEqual(raised.exception.status_code, 400)
                self.assertEqual(cursor.calls, [])
                self.assertFalse(connection.rolled_back)
                self.assertFalse(connection.closed)


if __name__ == "__main__":
    unittest.main()
