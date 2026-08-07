import json
import unittest

from backend.features.material_control_ownership.audit import (
    build_owner_readiness,
)


def project(project_id, company_id, name, *, archived=False):
    return {
        "project_id": project_id,
        "company_id": company_id,
        "project_name": name,
        "archived": archived,
    }


def estimate(
    estimate_id,
    company_id,
    project_id,
    project_name,
    *,
    kind="Заказчик",
    work_package="Основная",
):
    return {
        "estimate_id": estimate_id,
        "company_id": company_id,
        "project_id": project_id,
        "project_name": project_name,
        "estimate_kind": kind,
        "work_package": work_package,
    }


class MaterialControlOwnerAuditTests(unittest.TestCase):
    def test_same_name_cross_company_collision_is_safe_and_id_only(self):
        report = build_owner_readiness(
            [project(1, 10, "Школа"), project(2, 20, "Школа")],
            [
                estimate(101, 10, 1, "Школа"),
                estimate(102, 20, 2, "Школа"),
            ],
        )

        self.assertTrue(report["dataReady"])
        self.assertEqual(report["summary"]["validActiveEstimates"], 2)
        self.assertEqual(report["summary"]["nameCollisionGroups"], 1)
        self.assertEqual(report["nameCollisions"], [{
            "reasonCode": "project_name_cross_company_collision",
            "projectIds": [1, 2],
            "companyIds": [10, 20],
        }])
        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("Школа", serialized)

    def test_invalid_mismatched_and_duplicate_owners_use_fixed_codes(self):
        report = build_owner_readiness(
            [
                project(1, 10, "Школа"),
                project(2, 20, "Офис"),
                project(3, 10, "Архив", archived=True),
                project(4, None, "Без владельца"),
            ],
            [
                estimate(101, 10, 1, "Школа"),
                estimate(102, 10, 1, "Школа"),
                estimate(103, None, 1, "Школа"),
                estimate(104, 10, 2, "Офис"),
                estimate(105, 10, 999, "Нет"),
                estimate(106, 10, 3, "Архив"),
                estimate(107, 10, 1, "Другое имя", work_package="Этап 2"),
            ],
        )

        self.assertFalse(report["dataReady"])
        self.assertEqual(
            {item["reasonCode"] for item in report["issues"]},
            {
                "active_project_company_id_missing",
                "active_estimate_company_id_missing",
                "active_estimate_company_mismatch",
                "active_estimate_project_not_found",
                "active_estimate_project_archived",
                "active_estimate_project_name_mismatch",
                "active_estimate_scope_ambiguous",
            },
        )
        duplicate = next(
            item for item in report["issues"]
            if item["reasonCode"] == "active_estimate_scope_ambiguous"
        )
        self.assertEqual(duplicate["estimateIds"], [101, 102])
        for item in report["issues"]:
            self.assertLessEqual(
                set(item),
                {"reasonCode", "companyId", "projectId", "estimateId", "estimateIds"},
            )

    def test_issue_preview_is_bounded_without_losing_counts(self):
        estimates = [
            estimate(index, None, 1, "Школа")
            for index in range(1, 106)
        ]

        report = build_owner_readiness(
            [project(1, 10, "Школа")],
            estimates,
            max_issues=3,
        )

        self.assertEqual(report["issueCount"], 105)
        self.assertEqual(len(report["issues"]), 3)
        self.assertTrue(report["issuesTruncated"])


if __name__ == "__main__":
    unittest.main()
