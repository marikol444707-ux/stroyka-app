import unittest
from pathlib import Path

import psycopg2
from fastapi import HTTPException

from backend.features.project_budget_adjustments.approval import (
    BudgetAdjustmentApprovalError,
)
from backend.features.project_budget_adjustments.runtime_routes import (
    register_project_budget_adjustment_runtime_module,
)


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorator(func):
            self.routes[("GET", path)] = func
            return func
        return decorator

    def post(self, path):
        def decorator(func):
            self.routes[("POST", path)] = func
            return func
        return decorator


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.closed = False

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_value = FakeCursor()
        self.session = None
        self.rollbacks = 0
        self.commits = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session = kwargs

    def cursor(self, **_kwargs):
        return self.cursor_value

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def stored_receipt(receipt_id):
    return {
        "id": receipt_id,
        "company_id": 10,
        "project_id": 20,
        "reconciliation_id": 7,
        "base_estimate_id": 100,
        "next_estimate_id": 101,
        "project_budget_before": "1000.00",
        "estimate_base_total": "250.00",
        "estimate_next_total": "275.50",
        "adjustment_amount": "25.50",
        "project_budget_after": "1025.50",
        "plan_sha256": "b" * 64,
        "approved_by_user_id": 9,
        "approved_by_name": "Director",
        "approved_by_role": "директор",
        "approved_at": "2026-08-07T12:00:00+00:00",
        "created_at": "2026-08-07T12:00:00+00:00",
    }


_DEFAULT_HISTORY = object()


class BudgetAdjustmentRuntimeRouteTests(unittest.TestCase):
    def build(
        self,
        *,
        actors=None,
        history=_DEFAULT_HISTORY,
        approval_result=None,
        approval_error=None,
    ):
        app = FakeApp()
        connection = FakeConnection()
        calls = []
        selected_actors = actors if actors is not None else [{
            "id": 9,
            "companyId": 10,
            "name": "Director",
            "role": "директор",
        }]

        def load_history(cur, project_id, company_id, *, before_id, limit):
            calls.append((cur, project_id, company_id, before_id, limit))
            return (
                [stored_receipt(55)]
                if history is _DEFAULT_HISTORY
                else history
            )

        def apply_adjustment(cur, **kwargs):
            calls.append(("approve", cur, kwargs))
            if approval_error:
                raise approval_error
            return approval_result or {
                "id": 55,
                "companyId": 10,
                "projectId": 20,
                "reconciliationId": 7,
                "planSha256": "b" * 64,
                "projectBudgetBefore": "1000.00",
                "adjustmentAmount": "25.50",
                "projectBudgetAfter": "1025.50",
                "idempotent": False,
            }

        register_project_budget_adjustment_runtime_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_work_company_context": (
                lambda _cur, _user, _requested, mode, **_kwargs: {
                    "mode": "company",
                    "companyId": 10,
                    "actionMode": mode,
                }
            ),
            "effective_company_actors": lambda _user, _context: selected_actors,
            "leadership_roles": ("директор", "зам_директора"),
            "load_budget_adjustment_history": load_history,
            "apply_budget_adjustment": apply_adjustment,
        })
        return app, connection, calls

    @staticmethod
    def call_history(app, *, project_id=20, limit=1, before_id=None):
        return app.routes[(
            "GET",
            "/projects/{project_id}/budget-adjustments",
        )](
            project_id,
            limit=limit,
            before_id=before_id,
            x_company_id="10",
            x_company_mode="company",
            current_user={"id": 9, "role": "system_owner"},
        )

    @staticmethod
    def call_approval(app, *, reconciliation_id=7, data=None):
        return app.routes[(
            "POST",
            "/estimate-reconciliations/{reconciliation_id}/budget-adjustment-approval",
        )](
            reconciliation_id,
            data=data if data is not None else {"planSha256": "b" * 64},
            x_company_id="10",
            x_company_mode="company",
            current_user={"id": 9, "role": "system_owner"},
        )

    def test_exact_approval_commits_once_in_serializable_transaction(self):
        app, connection, calls = self.build()

        result = self.call_approval(app)

        self.assertEqual(result["id"], 55)
        self.assertFalse(result["idempotent"])
        self.assertEqual(connection.session, {
            "readonly": False,
            "autocommit": False,
            "isolation_level": "SERIALIZABLE",
        })
        approval_call = next(call for call in calls if call[0] == "approve")
        self.assertIs(approval_call[1], connection.cursor_value)
        self.assertEqual(approval_call[2], {
            "reconciliation_id": 7,
            "company_id": 10,
            "expected_plan_sha256": "b" * 64,
            "actor": {
                "id": 9,
                "companyId": 10,
                "company_id": 10,
                "name": "Director",
                "role": "директор",
            },
        })
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertTrue(connection.cursor_value.closed)
        self.assertTrue(connection.closed)

    def test_idempotent_approval_rolls_back_without_commit(self):
        app, connection, _calls = self.build(approval_result={
            "id": 55,
            "planSha256": "b" * 64,
            "idempotent": True,
        })

        result = self.call_approval(app)

        self.assertTrue(result["idempotent"])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_invalid_approval_payload_fails_before_database(self):
        for data in (
            {},
            {"planSha256": "A" * 64},
            {"planSha256": "b" * 64, "companyId": 10},
        ):
            with self.subTest(data=data):
                app, connection, calls = self.build()
                with self.assertRaises(HTTPException) as raised:
                    self.call_approval(app, data=data)
                self.assertEqual(raised.exception.status_code, 422)
                self.assertIn(raised.exception.detail, {
                    "budget_adjustment_approval_payload_invalid",
                    "budget_adjustment_plan_hash_invalid",
                })
                self.assertIsNone(connection.session)
                self.assertEqual(calls, [])

    def test_invalid_identity_and_non_leader_never_reach_approval_kernel(self):
        invalid_app, invalid_connection, invalid_calls = self.build()
        with self.assertRaises(HTTPException) as invalid:
            self.call_approval(invalid_app, reconciliation_id=0)
        self.assertEqual(invalid.exception.status_code, 422)
        self.assertEqual(
            invalid.exception.detail,
            "budget_adjustment_identity_invalid",
        )
        self.assertIsNone(invalid_connection.session)
        self.assertEqual(invalid_calls, [])

        forbidden_app, forbidden_connection, forbidden_calls = self.build(
            actors=[{
                "id": 15,
                "companyId": 10,
                "name": "Estimator",
                "role": "сметчик",
            }]
        )
        with self.assertRaises(HTTPException) as forbidden:
            self.call_approval(forbidden_app)
        self.assertEqual(forbidden.exception.status_code, 403)
        self.assertEqual(
            forbidden.exception.detail,
            "budget_adjustment_role_forbidden",
        )
        self.assertFalse(any(
            call[0] == "approve" for call in forbidden_calls
        ))
        self.assertEqual(forbidden_connection.rollbacks, 1)

    def test_approval_maps_fixed_domain_and_write_conflicts(self):
        cases = (
            (BudgetAdjustmentApprovalError("budget_adjustment_not_found"),
             404, "budget_adjustment_not_found"),
            (BudgetAdjustmentApprovalError("budget_adjustment_role_forbidden"),
             403, "budget_adjustment_role_forbidden"),
            (BudgetAdjustmentApprovalError("budget_adjustment_plan_stale"),
             409, "budget_adjustment_plan_stale"),
            (psycopg2.errors.SerializationFailure(),
             409, "budget_adjustment_write_conflict"),
            (psycopg2.errors.UndefinedTable(),
             503, "budget_adjustment_schema_not_ready"),
        )
        for error, status, code in cases:
            with self.subTest(code=code):
                app, connection, _calls = self.build(approval_error=error)
                with self.assertRaises(HTTPException) as raised:
                    self.call_approval(app)
                self.assertEqual(raised.exception.status_code, status)
                self.assertEqual(raised.exception.detail, code)
                self.assertEqual(connection.commits, 0)
                self.assertEqual(connection.rollbacks, 1)

    def test_history_is_tenant_bound_newest_first_bounded_and_read_only(self):
        app, connection, calls = self.build(history=[
            stored_receipt(55),
            stored_receipt(54),
        ])

        result = self.call_history(app, limit=1, before_id=60)

        self.assertEqual(result["projectId"], 20)
        self.assertEqual([item["id"] for item in result["items"]], [55])
        self.assertEqual(result["nextBeforeId"], 55)
        self.assertEqual(set(result["items"][0]), {
            "id", "companyId", "projectId", "reconciliationId",
            "baseEstimateId", "nextEstimateId", "projectBudgetBefore",
            "estimateBaseTotal", "estimateNextTotal", "adjustmentAmount",
            "projectBudgetAfter", "planSha256", "approvedByUserId",
            "approvedByName", "approvedByRole", "approvedAt", "createdAt",
        })
        self.assertEqual(calls, [(connection.cursor_value, 20, 10, 60, 2)])
        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(connection.cursor_value.closed)
        self.assertTrue(connection.closed)

    def test_missing_or_foreign_project_is_not_found(self):
        app, connection, calls = self.build(history=None)

        with self.assertRaises(HTTPException) as raised:
            self.call_history(app)

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "budget_adjustment_project_not_found")
        self.assertEqual(len(calls), 1)
        self.assertEqual(connection.rollbacks, 1)

    def test_non_leadership_and_invalid_query_fail_before_history_read(self):
        app, connection, calls = self.build(actors=[{
            "id": 15,
            "companyId": 10,
            "name": "Estimator",
            "role": "сметчик",
        }])
        with self.assertRaises(HTTPException) as raised:
            self.call_history(app)
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, "budget_adjustment_role_forbidden")
        self.assertEqual(calls, [])
        self.assertEqual(connection.rollbacks, 1)

        for query in (
            {"project_id": 0},
            {"limit": 0},
            {"limit": 101},
            {"before_id": 0},
        ):
            with self.subTest(query=query):
                invalid_app, invalid_connection, invalid_calls = self.build()
                with self.assertRaises(HTTPException) as invalid:
                    self.call_history(invalid_app, **query)
                self.assertEqual(invalid.exception.status_code, 422)
                self.assertEqual(
                    invalid.exception.detail,
                    "budget_adjustment_history_query_invalid",
                )
                self.assertEqual(invalid_calls, [])
                self.assertIsNone(invalid_connection.session)

    def test_main_and_smoke_register_authenticated_history(self):
        root = Path(__file__).resolve().parents[3]
        main = (root / "backend/main.py").read_text(encoding="utf-8")
        smoke = (root / "scripts/prod-smoke-check.sh").read_text(encoding="utf-8")

        self.assertIn("register_project_budget_adjustment_runtime_module(app", main)
        self.assertIn("project budget adjustment history route", smoke)
        self.assertIn("$BASE_URL/projects/1/budget-adjustments", smoke)
        self.assertIn("estimate budget adjustment approval route", smoke)
        self.assertIn(
            "$BASE_URL/estimate-reconciliations/1/budget-adjustment-approval",
            smoke,
        )


if __name__ == "__main__":
    unittest.main()
