import json
import unittest
from decimal import Decimal

from backend.features.project_budget_adjustments.audit import (
    build_budget_adjustment_readiness,
)


def project(project_id, company_id, budget):
    return {
        "project_id": project_id,
        "company_id": company_id,
        "project_budget": budget,
    }


def reconciliation(
    reconciliation_id,
    *,
    company_id=10,
    project_id=20,
    status="Утверждена",
    smeta_type="Заказчик",
    work_package="Основная",
    base_estimate_id=100,
    next_estimate_id=101,
    base_company_id=10,
    base_project_id=20,
    base_smeta_type="Заказчик",
    base_work_package="Основная",
    next_company_id=10,
    next_project_id=20,
    next_smeta_type="Заказчик",
    next_work_package="Основная",
    next_status="Активная",
    base_total="100.00",
    next_total="125.50",
):
    return dict(locals())


class BudgetAdjustmentReadinessTests(unittest.TestCase):
    def test_valid_budgets_and_approved_source_are_ready(self):
        report = build_budget_adjustment_readiness(
            [
                project(20, 10, Decimal("0.00")),
                project(21, 10, Decimal("999999999999.99")),
            ],
            [reconciliation(7)],
        )

        self.assertTrue(report["dataReady"])
        self.assertTrue(report["budgetDataReady"])
        self.assertTrue(report["approvedSourcesReady"])
        self.assertEqual(report["summary"], {
            "projectsTotal": 2,
            "validProjectBudgets": 2,
            "reconciliationsTotal": 1,
            "approvedReconciliations": 1,
            "readyApprovedReconciliations": 1,
        })
        self.assertEqual(report["readyCandidates"], [{
            "reconciliationId": 7,
            "companyId": 10,
            "projectId": 20,
            "baseEstimateId": 100,
            "nextEstimateId": 101,
        }])
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["writesAttempted"], 0)

    def test_budget_failures_use_fixed_id_only_reason_codes(self):
        report = build_budget_adjustment_readiness(
            [
                project(1, 10, None),
                project(2, 10, Decimal("NaN")),
                project(3, 10, Decimal("-0.01")),
                project(4, 10, Decimal("1000000000000.00")),
                project(5, 10, Decimal("1.001")),
                project(True, 10, Decimal("1.00")),
                project(7, 0, Decimal("1.00")),
            ],
            [],
        )

        self.assertFalse(report["budgetDataReady"])
        self.assertEqual(report["issueCount"], 7)
        self.assertEqual(report["reasonCounts"], {
            "project_budget_missing": 1,
            "project_budget_negative": 1,
            "project_budget_non_finite": 1,
            "project_budget_out_of_range": 1,
            "project_budget_precision_exceeds_scale": 1,
            "project_company_id_invalid": 1,
            "project_id_invalid": 1,
        })
        for issue in report["issues"]:
            self.assertLessEqual(
                set(issue),
                {"reasonCode", "companyId", "projectId", "reconciliationId",
                 "baseEstimateId", "nextEstimateId"},
            )
        serialized = json.dumps(report, ensure_ascii=False, default=str)
        for forbidden in ("NaN", "-0.01", "1000000000000.00", "1.001"):
            self.assertNotIn(forbidden, serialized)

    def test_approved_source_must_match_owner_type_package_and_active_revision(self):
        rows = [
            reconciliation(1, next_company_id=11),
            reconciliation(2, next_smeta_type="Материалы"),
            reconciliation(3, next_work_package="Этап 2"),
            reconciliation(4, next_status="Черновик"),
            reconciliation(5, base_total="NaN"),
            reconciliation(6, next_total="-1"),
            reconciliation(True),
            reconciliation(8, base_estimate_id=0),
        ]

        report = build_budget_adjustment_readiness(
            [project(20, 10, Decimal("1000.00"))],
            rows,
        )

        self.assertFalse(report["approvedSourcesReady"])
        self.assertEqual(report["summary"]["readyApprovedReconciliations"], 0)
        self.assertEqual(report["reasonCounts"], {
            "reconciliation_base_estimate_id_invalid": 1,
            "reconciliation_base_total_invalid": 1,
            "reconciliation_id_invalid": 1,
            "reconciliation_next_not_active": 1,
            "reconciliation_next_total_invalid": 1,
            "reconciliation_owner_mismatch": 1,
            "reconciliation_package_mismatch": 1,
            "reconciliation_type_not_customer": 1,
        })

    def test_drafts_do_not_block_approved_source_readiness(self):
        report = build_budget_adjustment_readiness(
            [project(20, 10, Decimal("1000.00"))],
            [reconciliation(1, status="Черновик", next_company_id=99)],
        )

        self.assertTrue(report["dataReady"])
        self.assertEqual(report["summary"]["reconciliationsTotal"], 1)
        self.assertEqual(report["summary"]["approvedReconciliations"], 0)
        self.assertEqual(report["readyCandidates"], [])

    def test_issue_and_candidate_previews_are_bounded_without_losing_counts(self):
        report = build_budget_adjustment_readiness(
            [project(index, 10, None) for index in range(1, 106)]
            + [project(200 + index, 10, "0.00") for index in range(1, 106)],
            [
                reconciliation(index, project_id=200 + index,
                               base_project_id=200 + index,
                               next_project_id=200 + index)
                for index in range(1, 106)
            ],
            max_issues=3,
            max_candidates=2,
        )

        self.assertEqual(report["issueCount"], 105)
        self.assertEqual(len(report["issues"]), 3)
        self.assertTrue(report["issuesTruncated"])
        self.assertEqual(len(report["readyCandidates"]), 2)
        self.assertTrue(report["readyCandidatesTruncated"])


if __name__ == "__main__":
    unittest.main()
