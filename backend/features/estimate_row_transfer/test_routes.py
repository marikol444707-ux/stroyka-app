import copy
import os
import subprocess
import sys
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.features.estimate_row_transfer.routes import register_estimate_row_transfer_module
from backend.features.estimate_row_transfer.test_storage import reviewed_plan


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
    def __init__(self):
        self.closed = False

    def execute(self, _sql, _params=None):
        return None

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_value = FakeCursor()
        self.session = None
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session = kwargs

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def stored_plan(status="draft"):
    plan = reviewed_plan()
    return {
        "id": 5,
        "status": status,
        "canonicalPlan": plan,
        "approvedPlanSha256": plan["planSha256"] if status == "approved" else None,
        "createdBy": {"userId": 12, "name": "Сметчик", "role": "сметчик"},
        "approvedBy": (
            {"userId": 2, "name": "Директор", "role": "директор"}
            if status == "approved" else None
        ),
        "approvedAt": "2026-08-06" if status == "approved" else "",
        "createdAt": "2026-08-06",
        "updatedAt": "2026-08-06",
    }


class EstimateRowTransferRouteTests(unittest.TestCase):
    def test_module_imports_from_backend_working_directory(self):
        backend_root = Path(__file__).resolve().parents[2]
        environment = dict(os.environ)
        environment.update({
            "PYTHONPATH": ".",
            "PYTHONPYCACHEPREFIX": "/tmp/stroyka-transfer-import-test-pycache",
        })

        result = subprocess.run(
            [sys.executable, "-c", "import features.estimate_row_transfer"],
            cwd=backend_root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_deploy_checks_production_import_before_restart(self):
        deploy = (Path(__file__).resolve().parents[3] / "deploy.sh").read_text(
            encoding="utf-8"
        )

        import_gate = "import features.estimate_row_transfer"
        self.assertIn(import_gate, deploy)
        self.assertLess(deploy.index(import_gate), deploy.index("systemctl restart stroyka"))

    def _register(
        self,
        *,
        actor=None,
        stored=None,
        current_plan=None,
        reconciliation_scope=None,
        calls=None,
    ):
        app = FakeApp()
        connection = FakeConnection()
        calls = calls if calls is not None else []
        selected_actor = actor or {
            "id": 12, "companyId": 1, "company_id": 1,
            "name": "Сметчик", "role": "сметчик",
        }
        stored_value = stored
        scope_value = reconciliation_scope or {
            "companyId": 1,
            "projectId": 3,
            "workPackage": "Каркас",
        }

        def build_stub(_cur, _payload):
            calls.append("build")
            return copy.deepcopy(current_plan or reviewed_plan())

        def approve_stub(*_args, **_kwargs):
            calls.append("approve")
            if stored_value is not None:
                stored_value["status"] = "approved"
                stored_value["approvedPlanSha256"] = stored_value["canonicalPlan"]["planSha256"]
                stored_value["approvedBy"] = {
                    "userId": selected_actor["id"],
                    "name": selected_actor["name"],
                    "role": selected_actor["role"],
                }
            return True

        def require_actor(actors, roles):
            candidate = dict(list(actors)[0])
            if candidate["role"] not in set(roles):
                raise HTTPException(status_code=403, detail="Недостаточно прав")
            return candidate

        register_estimate_row_transfer_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_work_company_context": lambda *_args, **_kwargs: {"companyId": 1},
            "effective_company_actors": lambda _user, _context: [selected_actor],
            "require_project_write_actor": require_actor,
            "resolve_project_parent": lambda _cur, _actor, **_kwargs: {
                "id": 3, "companyId": 1, "name": "Alpha",
            },
            "require_project_parent_access": lambda _cur, _actor, project, _roles: project,
            "has_package_access": lambda _actor, _package: True,
            "estimate_write_roles": ("директор", "зам_директора", "сметчик"),
            "approval_roles": ("директор", "зам_директора"),
            "full_view_roles": ("директор", "зам_директора", "сметчик"),
            "package_limit_roles": ("прораб",),
            "load_reconciliation_scope": lambda _cur, _id: copy.deepcopy(scope_value),
            "build_current_plan": build_stub,
            "find_plan_id_by_hash": lambda *_args: None,
            "insert_draft": lambda _cur, _plan, _actor: calls.append("insert") or 5,
            "load_stored_plan": lambda _cur, _id, _company, **_kwargs: copy.deepcopy(stored_value),
            "approve_plan": approve_stub,
            "find_other_approved_plan": lambda *_args, **_kwargs: None,
        })
        return app, connection, calls

    @staticmethod
    def _draft_payload():
        return {
            "reconciliationId": 9,
            "entries": [{
                "sourceKind": "assignment", "sourceId": 41, "quantity": "3",
                "targetSectionIndex": 0, "targetItemIndex": 0,
                "targetItemKey": "new-row",
            }],
        }

    def test_writer_creates_only_an_inert_draft(self):
        app, connection, calls = self._register(stored=stored_plan())

        result = app.routes[("POST", "/estimate-row-transfer-plans")](
            self._draft_payload(), x_company_id="1", x_company_mode="company",
            current_user={"id": 999, "role": "директор"},
        )

        self.assertEqual(calls, ["build", "insert"])
        self.assertEqual(result["id"], 5)
        self.assertEqual(result["status"], "draft")
        self.assertEqual(result["planSha256"], reviewed_plan()["planSha256"])
        self.assertNotIn("canonicalPlan", result)
        self.assertEqual(connection.commits, 1)

    def test_stored_company_owner_mismatch_blocks_before_insert(self):
        plan = reviewed_plan()
        plan["companyId"] = 2
        app, connection, calls = self._register(current_plan=plan)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/estimate-row-transfer-plans")](
                self._draft_payload(), x_company_id="1", x_company_mode="company",
                current_user={"id": 12},
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(calls, ["build"])
        self.assertEqual(connection.rollbacks, 1)

    def test_cross_company_scope_blocks_before_impact_scan(self):
        app, connection, calls = self._register(
            reconciliation_scope={
                "companyId": 2,
                "projectId": 8,
                "workPackage": "Каркас",
            },
        )

        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/estimate-row-transfer-plans")](
                self._draft_payload(), x_company_id="1", x_company_mode="company",
                current_user={"id": 12},
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(calls, [])
        self.assertEqual(connection.rollbacks, 1)

    def test_main_registers_routes_with_leadership_only_approval(self):
        source = (Path(__file__).resolve().parents[2] / "main.py").read_text(encoding="utf-8")

        self.assertIn("register_estimate_row_transfer_module(app", source)
        self.assertIn('"approval_roles": LEADERSHIP_ROLES', source)
        self.assertNotIn("ensure_estimate_row_transfer_schema", source)

    def test_only_leadership_can_approve(self):
        app, connection, calls = self._register(stored=stored_plan())

        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/estimate-row-transfer-plans/{plan_id}/approval")](
                5, {"planSha256": reviewed_plan()["planSha256"]},
                x_company_id="1", x_company_mode="company", current_user={"id": 12},
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(calls, [])
        self.assertEqual(connection.rollbacks, 1)

    def test_drifted_plan_fails_before_approval_update(self):
        stored = stored_plan()
        drifted = reviewed_plan()
        drifted["entries"][0]["sourceAvailableQuantity"] = "5"
        app, connection, calls = self._register(
            actor={"id": 2, "companyId": 1, "name": "Директор", "role": "директор"},
            stored=stored,
            current_plan=drifted,
        )

        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/estimate-row-transfer-plans/{plan_id}/approval")](
                5, {"planSha256": stored["canonicalPlan"]["planSha256"]},
                x_company_id="1", x_company_mode="company", current_user={"id": 2},
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, "transfer_plan_stale")
        self.assertNotIn("approve", calls)
        self.assertEqual(calls, ["build"])
        self.assertEqual(connection.rollbacks, 1)

    def test_repeated_approval_of_same_hash_is_read_only(self):
        stored = stored_plan("approved")
        app, connection, calls = self._register(
            actor={"id": 2, "companyId": 1, "name": "Директор", "role": "директор"},
            stored=stored,
        )

        result = app.routes[("POST", "/estimate-row-transfer-plans/{plan_id}/approval")](
            5, {"planSha256": stored["canonicalPlan"]["planSha256"]},
            x_company_id="1", x_company_mode="company", current_user={"id": 2},
        )

        self.assertEqual(result["status"], "approved")
        self.assertEqual(calls, [])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_leadership_approves_only_the_unchanged_exact_plan(self):
        stored = stored_plan()
        app, connection, calls = self._register(
            actor={"id": 2, "companyId": 1, "name": "Директор", "role": "директор"},
            stored=stored,
        )

        result = app.routes[("POST", "/estimate-row-transfer-plans/{plan_id}/approval")](
            5, {"planSha256": stored["canonicalPlan"]["planSha256"]},
            x_company_id="1", x_company_mode="company", current_user={"id": 2},
        )

        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["approvedPlanSha256"], result["planSha256"])
        self.assertEqual(calls, ["build", "approve"])
        self.assertEqual(connection.commits, 1)

    def test_writer_can_read_only_inside_selected_company(self):
        app, connection, _calls = self._register(stored=stored_plan())

        result = app.routes[("GET", "/estimate-row-transfer-plans/{plan_id}")](
            5, x_company_id="1", x_company_mode="company", current_user={"id": 12},
        )

        self.assertEqual(result["id"], 5)
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()
