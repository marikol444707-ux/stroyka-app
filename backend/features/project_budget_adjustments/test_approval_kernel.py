import unittest

from backend.features.project_budget_adjustments.approval import (
    BudgetAdjustmentApprovalError,
    apply_budget_adjustment,
)


PLAN_HASH = "b" * 64
ACTOR = {
    "id": 9,
    "companyId": 10,
    "name": "Director",
    "role": "директор",
}
PLAN = {
    "reconciliationId": 7,
    "companyId": 10,
    "projectId": 20,
    "baseEstimateId": 100,
    "nextEstimateId": 101,
    "projectBudgetBefore": "1000.00",
    "estimateBaseTotal": "250.00",
    "estimateNextTotal": "275.50",
    "adjustmentAmount": "25.50",
    "projectBudgetAfter": "1025.50",
    "planSha256": PLAN_HASH,
    "readyForApproval": True,
    "blockers": [],
}


def receipt(**changes):
    value = {
        "id": 55,
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
        "plan_sha256": PLAN_HASH,
        "approved_by_user_id": 9,
        "approved_by_name": "Director",
        "approved_by_role": "директор",
        "approved_at": "2026-08-07T12:00:00+00:00",
        "created_at": "2026-08-07T12:00:00+00:00",
    }
    value.update(changes)
    return value


class FakeApprovalBoundary:
    def __init__(self, existing=None):
        self.existing = existing
        self.events = []
        self.inserted = None
        self.budget = "1000.00"

    def lock_source(self, _cur, reconciliation_id, company_id):
        self.events.append("lock_source")
        return {"reconciliation_id": reconciliation_id, "company_id": company_id}

    def authorize_actor(self, _cur, actor, company_id):
        self.events.append("authorize_actor")
        return actor if actor["companyId"] == company_id else None

    def load_receipt(self, _cur, reconciliation_id, company_id):
        self.events.append("load_receipt")
        return self.existing

    def build_preview(self, _cur, _reconciliation_id, _company_id, **_kwargs):
        self.events.append("build_preview")
        return dict(PLAN)

    def insert_receipt(self, _cur, plan, actor):
        self.events.append("insert_receipt")
        self.inserted = receipt(
            plan_sha256=plan["planSha256"],
            approved_by_user_id=actor["id"],
        )
        return self.inserted

    def update_budget(self, _cur, plan):
        self.events.append("update_budget")
        if self.budget != plan["projectBudgetBefore"]:
            return False
        self.budget = plan["projectBudgetAfter"]
        return True

    def apply(self, expected_plan_sha256=PLAN_HASH):
        return apply_budget_adjustment(
            object(),
            reconciliation_id=7,
            company_id=10,
            expected_plan_sha256=expected_plan_sha256,
            actor=ACTOR,
            lock_source=self.lock_source,
            authorize_actor=self.authorize_actor,
            load_receipt=self.load_receipt,
            build_preview=self.build_preview,
            insert_receipt=self.insert_receipt,
            update_budget=self.update_budget,
        )


class BudgetAdjustmentApprovalKernelTests(unittest.TestCase):
    def test_exact_plan_inserts_receipt_then_updates_budget_once(self):
        boundary = FakeApprovalBoundary()

        result = boundary.apply()

        self.assertFalse(result["idempotent"])
        self.assertEqual(result["id"], 55)
        self.assertEqual(result["planSha256"], PLAN_HASH)
        self.assertEqual(result["projectBudgetAfter"], "1025.50")
        self.assertEqual(boundary.budget, "1025.50")
        self.assertEqual(boundary.events, [
            "lock_source", "authorize_actor", "load_receipt",
            "build_preview", "insert_receipt", "update_budget",
        ])

    def test_existing_exact_receipt_is_idempotent_and_stale_hash_is_rejected(self):
        exact = FakeApprovalBoundary(existing=receipt())
        result = exact.apply()
        self.assertTrue(result["idempotent"])
        self.assertEqual(exact.events, [
            "lock_source", "authorize_actor", "load_receipt",
        ])

        stale = FakeApprovalBoundary(existing=receipt())
        with self.assertRaises(BudgetAdjustmentApprovalError) as raised:
            stale.apply(expected_plan_sha256="c" * 64)
        self.assertEqual(raised.exception.code, "budget_adjustment_plan_stale")
        self.assertEqual(stale.events, [
            "lock_source", "authorize_actor", "load_receipt",
        ])


if __name__ == "__main__":
    unittest.main()
