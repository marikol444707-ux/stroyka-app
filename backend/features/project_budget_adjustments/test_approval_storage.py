import unittest

from backend.features.project_budget_adjustments.approval import (
    BudgetAdjustmentApprovalError,
)
from backend.features.project_budget_adjustments.approval_storage import (
    load_authorized_budget_actor,
    load_budget_adjustment_receipt,
    lock_budget_adjustment_source,
)


class FakeCursor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.current = None

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self.current = self.responses.pop(0)

    def fetchone(self):
        return self.current

    def fetchall(self):
        return self.current


class BudgetAdjustmentApprovalStorageTests(unittest.TestCase):
    def test_locks_tenant_source_in_deterministic_order_before_reload(self):
        cursor = FakeCursor([
            {"project_id": 20, "base_estimate_id": 101, "next_estimate_id": 100},
            {"id": 20},
            [{"id": 100}, {"id": 101}, {"id": 102}],
            {"id": 7},
        ])
        reloaded = {"reconciliation_id": 7, "company_id": 10}
        loader_calls = []

        result = lock_budget_adjustment_source(
            cursor,
            7,
            10,
            source_loader=lambda cur, rid, cid: (
                loader_calls.append((cur, rid, cid)) or reloaded
            ),
        )

        self.assertEqual(result, reloaded)
        self.assertEqual(loader_calls, [(cursor, 7, 10)])
        self.assertEqual(len(cursor.calls), 4)
        resolve_sql, resolve_params = cursor.calls[0]
        self.assertIn("FROM public.estimate_reconciliations r", resolve_sql)
        self.assertIn("project.company_id=%s", resolve_sql)
        self.assertNotIn("FOR UPDATE", resolve_sql)
        self.assertEqual(resolve_params, (7, 10))
        self.assertIn("FROM public.projects", cursor.calls[1][0])
        self.assertIn("FOR UPDATE", cursor.calls[1][0])
        self.assertIn("FROM public.estimates", cursor.calls[2][0])
        self.assertIn("ORDER BY id", cursor.calls[2][0])
        self.assertIn("FOR UPDATE", cursor.calls[2][0])
        self.assertEqual(cursor.calls[2][1], (10, 20, 10001))
        self.assertIn("FROM public.estimate_reconciliations", cursor.calls[3][0])
        self.assertIn("FOR UPDATE", cursor.calls[3][0])

    def test_missing_foreign_or_oversized_source_fails_closed(self):
        missing = FakeCursor([None])
        self.assertIsNone(lock_budget_adjustment_source(missing, 7, 10))
        self.assertEqual(len(missing.calls), 1)

        oversized = FakeCursor([
            {"project_id": 20, "base_estimate_id": 100, "next_estimate_id": 101},
            {"id": 20},
            [{"id": 100}, {"id": 101}, {"id": 102}],
        ])
        with self.assertRaises(BudgetAdjustmentApprovalError) as raised:
            lock_budget_adjustment_source(
                oversized, 7, 10, max_locked_estimates=2
            )
        self.assertEqual(
            raised.exception.code,
            "budget_adjustment_estimate_lock_limit_exceeded",
        )

    def test_authorizes_one_active_exact_membership_and_loads_owned_receipt(self):
        actor_cursor = FakeCursor([[{
            "id": 9,
            "name": "Stored Director",
            "role": "директор",
        }]])
        actor = load_authorized_budget_actor(
            actor_cursor,
            {"id": 9, "companyId": 10, "name": "Director", "role": "директор"},
            10,
        )
        self.assertEqual(actor, {
            "id": 9,
            "companyId": 10,
            "name": "Stored Director",
            "role": "директор",
        })
        self.assertIn("FROM public.user_company_roles actor", actor_cursor.calls[0][0])
        self.assertIn("FOR KEY SHARE", actor_cursor.calls[0][0])
        self.assertEqual(actor_cursor.calls[0][1], (9, 10, "директор"))

        receipt_cursor = FakeCursor([{"id": 55, "company_id": 10}])
        stored = load_budget_adjustment_receipt(receipt_cursor, 7, 10)
        self.assertEqual(stored["id"], 55)
        self.assertIn("reconciliation_id=%s", receipt_cursor.calls[0][0])
        self.assertIn("company_id=%s", receipt_cursor.calls[0][0])
        self.assertEqual(receipt_cursor.calls[0][1], (7, 10))


if __name__ == "__main__":
    unittest.main()
