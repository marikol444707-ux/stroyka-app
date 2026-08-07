import unittest

from backend.features.project_budget_adjustments.approval import (
    BudgetAdjustmentApprovalError,
    apply_budget_adjustment,
    normalize_budget_adjustment_approval_payload,
)


VALID_HASH = "a" * 64
VALID_ACTOR = {
    "id": 9,
    "companyId": 10,
    "name": "Director",
    "role": "директор",
}


class NoQueryCursor:
    def execute(self, *_args, **_kwargs):
        raise AssertionError("invalid approval input must not query PostgreSQL")


def approval_error(**changes):
    values = {
        "reconciliation_id": 7,
        "company_id": 10,
        "expected_plan_sha256": VALID_HASH,
        "actor": VALID_ACTOR,
    }
    values.update(changes)
    with unittest.TestCase().assertRaises(BudgetAdjustmentApprovalError) as raised:
        apply_budget_adjustment(NoQueryCursor(), **values)
    return raised.exception.code


class BudgetAdjustmentApprovalInputTests(unittest.TestCase):
    def test_normalizes_only_the_exact_public_approval_payload(self):
        self.assertEqual(
            normalize_budget_adjustment_approval_payload({
                "planSha256": VALID_HASH,
            }),
            {"planSha256": VALID_HASH},
        )
        for payload, code in (
            (None, "budget_adjustment_approval_payload_invalid"),
            ([], "budget_adjustment_approval_payload_invalid"),
            ({}, "budget_adjustment_approval_payload_invalid"),
            ({"planSha256": VALID_HASH, "companyId": 10},
             "budget_adjustment_approval_payload_invalid"),
            ({"planSha256": "A" * 64},
             "budget_adjustment_plan_hash_invalid"),
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(BudgetAdjustmentApprovalError) as raised:
                    normalize_budget_adjustment_approval_payload(payload)
                self.assertEqual(raised.exception.code, code)

    def test_rejects_invalid_source_identity_before_querying(self):
        for reconciliation_id, company_id in (
            (0, 10), (True, 10), ("7", 10), (7, 0), (7, True),
        ):
            with self.subTest(
                reconciliation_id=reconciliation_id,
                company_id=company_id,
            ):
                self.assertEqual(
                    approval_error(
                        reconciliation_id=reconciliation_id,
                        company_id=company_id,
                    ),
                    "budget_adjustment_identity_invalid",
                )

    def test_requires_exact_lowercase_plan_hash_before_querying(self):
        for value in (None, "", "a" * 63, "A" * 64, "g" * 64, True):
            with self.subTest(value=value):
                self.assertEqual(
                    approval_error(expected_plan_sha256=value),
                    "budget_adjustment_plan_hash_invalid",
                )

    def test_requires_same_company_leadership_actor_before_querying(self):
        cases = (
            ({}, "budget_adjustment_actor_invalid"),
            ({**VALID_ACTOR, "id": True}, "budget_adjustment_actor_invalid"),
            ({**VALID_ACTOR, "name": " "}, "budget_adjustment_actor_invalid"),
            ({**VALID_ACTOR, "companyId": 11}, "budget_adjustment_role_forbidden"),
            ({**VALID_ACTOR, "role": "сметчик"}, "budget_adjustment_role_forbidden"),
        )
        for actor, code in cases:
            with self.subTest(actor=actor):
                self.assertEqual(approval_error(actor=actor), code)


if __name__ == "__main__":
    unittest.main()
