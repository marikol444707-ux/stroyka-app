import os
import subprocess
import sys
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.features.estimate_versions.routes import register_estimate_versions_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorator(handler):
            self.routes[("GET", path)] = handler
            return handler

        return decorator


class FakeCursor:
    def __init__(self, fetchone_values=(), rows=()):
        self.fetchone_values = list(fetchone_values)
        self.rows = list(rows)
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.fetchone_values.pop(0) if self.fetchone_values else None

    def fetchall(self):
        return list(self.rows)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.cursor_factory = None
        self.closed = False

    def cursor(self, cursor_factory=None):
        self.cursor_factory = cursor_factory
        return self.cursor_value

    def close(self):
        self.closed = True


class EstimateVersionRouteTests(unittest.TestCase):
    def test_module_imports_from_backend_working_directory(self):
        backend_dir = Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = ""
        env["PYTHONPYCACHEPREFIX"] = "/tmp/stroyka-pycache"

        result = subprocess.run(
            [sys.executable, "-c", "from features.estimate_versions.routes import register_estimate_versions_module"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def _register(self, connection, *, actors=None, worker_sections=None):
        app = FakeApp()
        calls = {"context": [], "visibility": [], "parent": [], "allowed": []}
        company_actors = list(actors or [{
            "id": 9,
            "companyId": 4,
            "role": "директор",
            "assignedProjects": [],
            "assignedPackages": [],
        }])

        def resolve_context(cur, user, requested_company_id, action_mode, **kwargs):
            calls["context"].append((cur, user, requested_company_id, action_mode, kwargs))
            return {"mode": kwargs.get("x_company_mode") or "company", "companyId": 4}

        def visibility_filter(company_memberships, *args, **kwargs):
            calls["visibility"].append((company_memberships, args, kwargs))
            company_ids = [int(actor["companyId"]) for actor in company_memberships]
            clauses = " OR ".join("e.company_id=%s" for _ in company_ids) or "FALSE"
            return "(" + clauses + ")", company_ids

        def resolve_parent(cur, actor, estimate_id, **kwargs):
            calls["parent"].append((cur, actor, estimate_id, kwargs))
            return {
                "id": estimate_id,
                "companyId": int(actor["companyId"]),
                "projectId": 17,
                "projectName": "Лицей",
                "workPackage": "Основная",
            }

        def allowed_items(cur, actor, scopes):
            calls["allowed"].append((cur, actor, scopes))
            return {("Лицей", "Основная"): [{"estimate_item_key": "allowed"}]}

        register_estimate_versions_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, _context: company_actors,
            "estimate_visibility_filter": visibility_filter,
            "resolve_estimate_parent": resolve_parent,
            "project_document_roles": (
                "директор",
                "зам_директора",
                "бухгалтер",
                "главный_инженер",
                "сметчик",
                "прораб",
                "мастер",
                "бригадир",
                "субподрядчик",
            ),
            "full_view_roles": ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик"),
            "package_limit_roles": ("мастер", "бригадир", "субподрядчик"),
            "active_only_roles": ("прораб", "мастер", "бригадир", "субподрядчик"),
            "customer_roles": ("заказчик",),
            "package_optional_roles": ("прораб",),
            "worker_execution_roles": ("мастер", "бригадир", "субподрядчик"),
            "worker_allowed_items_for_scopes": allowed_items,
            "sanitize_worker_sections": lambda sections, allowed, estimate_id=None: (
                worker_sections if worker_sections is not None else sections
            ),
            "sanitize_worker_total": lambda actor, total: 0 if actor.get("role") == "мастер" else float(total or 0),
        })
        return app, calls

    def test_list_versions_resolves_selected_company_before_reading_children(self):
        cursor = FakeCursor(
            fetchone_values=[{
                "id": 7,
                "company_id": 4,
                "project_id": 17,
                "project_name": "Лицей",
                "work_package": "Основная",
                "is_template": False,
            }],
            rows=[{
                "id": 31,
                "version_label": "2.0",
                "total": 1250,
                "comment": "До корректировки",
                "created_by": "Сметчик",
                "created_at": "2026-07-11",
            }],
        )
        connection = FakeConnection(cursor)
        app, calls = self._register(connection)

        response = app.routes[("GET", "/estimates/{id}/versions")](
            7,
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 1, "role": "system_owner"},
        )

        self.assertEqual(calls["context"][0][3], "read")
        self.assertEqual(calls["context"][0][4]["x_company_id"], "4")
        self.assertEqual(calls["parent"][0][1]["companyId"], 4)
        parent_sql, parent_params = cursor.calls[0]
        self.assertIn("FROM estimates e", parent_sql)
        self.assertIn("e.id=%s", parent_sql)
        self.assertIn("e.company_id=%s", parent_sql)
        self.assertEqual(parent_params, (7, 4))
        child_sql, child_params = cursor.calls[1]
        self.assertIn("FROM estimate_versions", child_sql)
        self.assertEqual(child_params, (7,))
        self.assertEqual(response[0]["id"], 31)
        self.assertEqual(response[0]["total"], 1250.0)
        self.assertTrue(connection.closed)

    def test_direct_version_returns_404_when_parent_is_not_visible(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app, calls = self._register(connection)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/estimate-version/{version_id}")](
                31,
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 9, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(calls["parent"], [])
        self.assertEqual(len(cursor.calls), 1)
        sql, params = cursor.calls[0]
        self.assertIn("JOIN estimates e ON e.id=ev.estimate_id", sql)
        self.assertIn("e.company_id=%s", sql)
        self.assertEqual(params, (31, 4))
        self.assertTrue(connection.closed)

    def test_direct_version_uses_effective_company_role_for_accountant_denial(self):
        cursor = FakeCursor(fetchone_values=[{
            "id": 31,
            "estimate_id": 7,
            "version_label": "2.0",
            "sections_json": "[]",
            "total": 1250,
            "comment": "",
            "created_by": "",
            "created_at": "2026-07-11",
            "project_name": "Лицей",
            "work_package": "Основная",
            "estimate_status": "Активная",
            "company_id": 5,
        }])
        connection = FakeConnection(cursor)
        app, calls = self._register(connection, actors=[
            {"id": 9, "companyId": 4, "role": "директор"},
            {"id": 9, "companyId": 5, "role": "бухгалтер "},
        ])

        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/estimate-version/{version_id}")](
                31,
                x_company_id=None,
                x_company_mode="all_companies",
                current_user={"id": 9, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(calls["parent"][0][1]["companyId"], 5)
        self.assertEqual(calls["parent"][0][1]["role"], "бухгалтер")
        self.assertEqual(cursor.calls[0][1], (31, 4, 5))

    def test_worker_detail_keeps_existing_section_and_total_sanitizing(self):
        cursor = FakeCursor(fetchone_values=[{
            "id": 31,
            "estimate_id": 7,
            "version_label": "2.0",
            "sections_json": '[{"name":"Раздел","items":[{"estimateItemKey":"hidden"}]}]',
            "total": 1250,
            "comment": "",
            "created_by": "",
            "created_at": "2026-07-11",
            "project_name": "Лицей",
            "work_package": "Основная",
            "estimate_status": "Активная",
            "company_id": 4,
        }])
        connection = FakeConnection(cursor)
        app, calls = self._register(
            connection,
            actors=[{
                "id": 12,
                "companyId": 4,
                "role": " мастер ",
                "assignedProjects": ["Лицей"],
                "assignedPackages": ["Основная"],
            }],
            worker_sections=[{"name": "Раздел", "items": []}],
        )

        response = app.routes[("GET", "/estimate-version/{version_id}")](
            31,
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 12, "role": "директор"},
        )

        self.assertEqual(response["total"], 0)
        self.assertEqual(response["sections"], [{"name": "Раздел", "items": []}])
        self.assertEqual(calls["allowed"][0][1]["role"], "мастер")
        self.assertEqual(calls["allowed"][0][2], [("Лицей", "Основная")])


if __name__ == "__main__":
    unittest.main()
