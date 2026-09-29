"""Execute the real route with an isolated database and audited actor context."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend.features.supplier_access.supply_request_workflow import (
    SupplyRequestWorkflowViolation, validate_supply_request_transition,
)


class HttpError(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Database:
    def __init__(self):
        self.autocommit = True
        self.committed = self.rolled_back = False
        self.rowcount = 1
        self.events = []
        self.request = dict(project="Объект", company_id=202, status="Новая",
                            work_package="Основная", items_json=[], requested_by_id=4)

    def cursor(self, **kwargs):
        return self

    def execute(self, sql, params=()):
        if sql.lstrip().startswith("UPDATE"):
            self.events.append(("update", self.autocommit, params))

    def fetchone(self):
        return self.request.copy()

    def commit(self):
        self.events.append(("commit",))
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


class ReviewerFallbackRouteTests(unittest.TestCase):
    def run_route(self, reason, *, audit_fails=False, assigned=True, deny_company=False, changed=False):
        db = Database()
        db.rowcount = 0 if changed else 1
        self.db = db
        actor = dict(id=77, name="Руководитель", role="директор")
        def company_actor(*args, **kwargs):
            if deny_company:
                raise HttpError(403, "Чужая компания")
            return {"companyId": 202}, actor
        def audit(cur, **fields):
            self.audit_fields = fields
            db.events.append(("audit", db.autocommit))
            if audit_fails:
                raise RuntimeError("audit unavailable")
            return {"id": 1}
        node = next(n for n in ast.parse((Path(__file__).parents[2] / "main.py").read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == "update_supply_request")
        node.decorator_list = []
        node.args.defaults = [ast.Constant(None) for _ in node.args.defaults]
        for arg in node.args.args:
            arg.annotation = None
        ns = dict(get_db=lambda: db, psycopg2=SimpleNamespace(extras=SimpleNamespace(RealDictCursor=None)),
                  HTTPException=HttpError, resolve_resource_company_actor=company_actor,
                  PLATFORM_STAFF_ROLES=(), CLIENT_ACCOUNT_ROLES=(), SUPPLY_ROLES=("директор",),
                  WORKER_EXECUTION_ROLES=(), LEADERSHIP_ROLES=("директор", "зам_директора"),
                  require_project_or_warehouse_access=lambda *a: None,
                  _json_list_or_empty=lambda x: x or [], _supply_work_package=lambda x: x,
                  has_package_access=lambda *a: True,
                  _supply_project_has_active_reviewer=lambda *a: assigned,
                  validate_supply_request_transition=validate_supply_request_transition,
                  SupplyRequestWorkflowViolation=SupplyRequestWorkflowViolation,
                  SUPPLY_SELECT="SELECT response", log_audit=lambda *a, **kw: None,
                  _supply_response_for_role=lambda row, user: row)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), "route", "exec"), ns)
        with patch("backend.features.audit_ownership.runtime.insert_audit_event", side_effect=audit):
            ns["update_supply_request"](12, dict(action="confirm_prorab", reviewerAbsenceReason=reason,
                                                userId=999, userName="Spoofed"), _current_user=actor)

    def test_reason_and_real_actor_are_saved_before_commit(self):
        self.run_route("  Прораб в отпуске  ")
        self.assertEqual(self.audit_fields["user_id"], 77)
        self.assertEqual(self.audit_fields["company_id"], 202)
        self.assertIn("Прораб в отпуске", self.audit_fields["description"])
        self.assertEqual([e[0] for e in self.db.events], ["update", "audit", "commit"])
        self.assertFalse(self.db.events[0][1])
        self.assertFalse(self.db.events[1][1])

    def test_no_assignment_is_recorded_without_inventing_a_foreman(self):
        self.run_route(None, assigned=False)
        self.assertIn("не назначен", self.audit_fields["description"])
        self.assertEqual(self.db.events[0][2][1], 77)

    def test_missing_reason_does_not_write(self):
        with self.assertRaises(HttpError):
            self.run_route("  ")
        self.assertEqual(self.db.events, [])

    def test_audit_failure_rolls_back_confirmation(self):
        with self.assertRaises(RuntimeError):
            self.run_route("Отпуск", audit_fails=True)
        self.assertTrue(self.db.rolled_back)
        self.assertFalse(self.db.committed)

    def test_reason_does_not_grant_cross_company_access(self):
        with self.assertRaises(HttpError):
            self.run_route("Отпуск", deny_company=True)
        self.assertEqual(self.db.events, [])

    def test_concurrent_status_or_company_change_prevents_confirmation(self):
        with self.assertRaises(HttpError) as error:
            self.run_route("Отпуск", changed=True)
        self.assertEqual(error.exception.status_code, 409)
        self.assertTrue(self.db.rolled_back)
        self.assertFalse(self.db.committed)
        self.assertNotIn("audit", [e[0] for e in self.db.events])


if __name__ == "__main__":
    unittest.main()
