import copy
import unittest
from decimal import Decimal

from backend.features.project_budget_adjustments.plan import (
    BudgetAdjustmentPlanError,
    build_budget_adjustment_plan,
    calculate_plan_sha256,
)


def source(**changes):
    payload = {
        "reconciliationId": 7,
        "companyId": 10,
        "projectId": 20,
        "baseEstimateId": 100,
        "nextEstimateId": 101,
        "projectBudgetBefore": "1000.00",
        "estimateBaseTotal": "250.00",
        "estimateNextTotal": "275.50",
    }
    payload.update(changes)
    return payload


class BudgetAdjustmentPlanTests(unittest.TestCase):
    def test_builds_exact_positive_delta_plan_and_hash(self):
        plan = build_budget_adjustment_plan(source())

        self.assertEqual(plan, {
            "planVersion": 1,
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
            "noOp": False,
            "readyForApproval": True,
            "blockers": [],
            "planSha256": plan["planSha256"],
        })
        self.assertEqual(
            plan["planSha256"],
            "bc6ba21cb278830bf87ce83c1e5ae945893fb8a8cf62ee0d68f473e54feb4fbb",
        )
        self.assertEqual(calculate_plan_sha256(plan), plan["planSha256"])

    def test_allows_negative_delta_when_project_budget_stays_non_negative(self):
        plan = build_budget_adjustment_plan(source(
            projectBudgetBefore="1000.00",
            estimateBaseTotal="400.00",
            estimateNextTotal="150.00",
        ))

        self.assertEqual(plan["adjustmentAmount"], "-250.00")
        self.assertEqual(plan["projectBudgetAfter"], "750.00")
        self.assertTrue(plan["readyForApproval"])

    def test_rejects_negative_after_budget(self):
        with self.assertRaisesRegex(
            BudgetAdjustmentPlanError,
            "budget_adjustment_negative_after",
        ) as error:
            build_budget_adjustment_plan(source(
                projectBudgetBefore="100.00",
                estimateBaseTotal="400.00",
                estimateNextTotal="150.00",
            ))

        self.assertEqual(error.exception.code, "budget_adjustment_negative_after")

    def test_rejects_after_budget_outside_numeric_range(self):
        with self.assertRaisesRegex(
            BudgetAdjustmentPlanError,
            "budget_adjustment_after_out_of_range",
        ):
            build_budget_adjustment_plan(source(
                projectBudgetBefore="999999999999.99",
                estimateBaseTotal="0.00",
                estimateNextTotal="0.01",
            ))

    def test_zero_delta_is_hashed_read_only_noop(self):
        plan = build_budget_adjustment_plan(source(
            estimateBaseTotal="250.00",
            estimateNextTotal="250.00",
        ))

        self.assertEqual(plan["adjustmentAmount"], "0.00")
        self.assertEqual(plan["projectBudgetAfter"], "1000.00")
        self.assertTrue(plan["noOp"])
        self.assertFalse(plan["readyForApproval"])
        self.assertEqual(plan["blockers"], ["budget_adjustment_zero_delta"])
        self.assertEqual(calculate_plan_sha256(plan), plan["planSha256"])

    def test_signed_zero_is_canonical(self):
        plan = build_budget_adjustment_plan(source(
            projectBudgetBefore="-0.00",
            estimateBaseTotal="-0.00",
            estimateNextTotal="0.00",
        ))

        self.assertEqual(plan["projectBudgetBefore"], "0.00")
        self.assertEqual(plan["estimateBaseTotal"], "0.00")
        self.assertEqual(plan["adjustmentAmount"], "0.00")

    def test_equivalent_money_inputs_have_the_same_canonical_hash(self):
        first = build_budget_adjustment_plan(source())
        second = build_budget_adjustment_plan(source(
            projectBudgetBefore=1000,
            estimateBaseTotal=Decimal("250.0"),
            estimateNextTotal=275.5,
        ))

        self.assertEqual(first, second)

    def test_hash_changes_for_every_authoritative_id_or_amount(self):
        original = build_budget_adjustment_plan(source())
        changes = {
            "reconciliationId": 8,
            "companyId": 11,
            "projectId": 21,
            "baseEstimateId": 102,
            "nextEstimateId": 103,
            "projectBudgetBefore": "1001.00",
            "estimateBaseTotal": "251.00",
            "estimateNextTotal": "276.50",
        }

        for key, value in changes.items():
            with self.subTest(key=key):
                changed = build_budget_adjustment_plan(source(**{key: value}))
                self.assertNotEqual(original["planSha256"], changed["planSha256"])

    def test_rejects_unknown_missing_and_invalid_identity_fields(self):
        invalid = [
            {**source(), "extra": True},
            {key: value for key, value in source().items() if key != "projectId"},
            source(reconciliationId=True),
            source(companyId=0),
            source(projectId="20"),
            source(baseEstimateId=-1),
            source(nextEstimateId=100),
        ]

        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(BudgetAdjustmentPlanError):
                    build_budget_adjustment_plan(payload)

    def test_rejects_invalid_or_inexact_authoritative_money(self):
        invalid_values = [None, True, "NaN", "Infinity", "-0.01",
                          "1000000000000.00", "1.001"]
        for key in (
            "projectBudgetBefore",
            "estimateBaseTotal",
            "estimateNextTotal",
        ):
            for value in invalid_values:
                with self.subTest(key=key, value=value):
                    with self.assertRaises(BudgetAdjustmentPlanError):
                        build_budget_adjustment_plan(source(**{key: value}))

    def test_money_fields_use_distinct_fixed_error_codes(self):
        expected = {
            "projectBudgetBefore": "budget_adjustment_project_budget_invalid",
            "estimateBaseTotal": "budget_adjustment_base_total_invalid",
            "estimateNextTotal": "budget_adjustment_next_total_invalid",
        }

        for key, code in expected.items():
            with self.subTest(key=key):
                with self.assertRaises(BudgetAdjustmentPlanError) as error:
                    build_budget_adjustment_plan(source(**{key: None}))
                self.assertEqual(error.exception.code, code)

    def test_hash_function_ignores_only_the_supplied_hash_field(self):
        plan = build_budget_adjustment_plan(source())
        altered = copy.deepcopy(plan)
        altered["planSha256"] = "0" * 64

        self.assertEqual(calculate_plan_sha256(altered), plan["planSha256"])


if __name__ == "__main__":
    unittest.main()
