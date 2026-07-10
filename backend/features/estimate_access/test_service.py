import unittest

from fastapi import HTTPException

from backend.features.estimate_access.service import (
    estimate_visibility_filter,
    resolve_estimate_parent,
)


FULL_VIEW_ROLES = ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик")
PACKAGE_LIMIT_ROLES = ("мастер", "бригадир", "субподрядчик")
ACTIVE_ONLY_ROLES = ("прораб", "мастер", "бригадир", "субподрядчик")
CUSTOMER_ROLES = ("заказчик",)
PACKAGE_OPTIONAL_ROLES = ("прораб",)


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class EstimateAccessTests(unittest.TestCase):
    def test_visibility_keeps_each_company_role_scope(self):
        sql, params = estimate_visibility_filter(
            [
                {"companyId": 1, "role": "директор"},
                {
                    "companyId": 2,
                    "role": "мастер",
                    "assignedProjects": ["Лицей"],
                    "assignedPackages": ["Общестрой"],
                },
            ],
            FULL_VIEW_ROLES,
            PACKAGE_LIMIT_ROLES,
            ACTIVE_ONLY_ROLES,
            CUSTOMER_ROLES,
            PACKAGE_OPTIONAL_ROLES,
        )

        self.assertEqual(params, [1, 2, ["Лицей"], ["Общестрой"]])
        self.assertEqual(sql.count("%s"), len(params))
        self.assertIn("e.company_id=%s", sql)
        self.assertIn("e.project_name = ANY(%s)", sql)
        self.assertIn("e.work_package", sql)

    def test_visibility_fails_closed_without_project_or_package(self):
        self.assertEqual(
            estimate_visibility_filter(
                [{"companyId": 2, "role": "мастер", "assignedProjects": ["Лицей"]}],
                FULL_VIEW_ROLES,
                PACKAGE_LIMIT_ROLES,
                ACTIVE_ONLY_ROLES,
                CUSTOMER_ROLES,
                PACKAGE_OPTIONAL_ROLES,
            ),
            ("FALSE", []),
        )
        self.assertEqual(
            estimate_visibility_filter(
                [], FULL_VIEW_ROLES, PACKAGE_LIMIT_ROLES, ACTIVE_ONLY_ROLES, CUSTOMER_ROLES
            ),
            ("FALSE", []),
        )

    def test_customer_visibility_requires_active_customer_estimate(self):
        sql, params = estimate_visibility_filter(
            [{"companyId": 3, "role": "заказчик", "assignedProjects": ["Лицей"]}],
            FULL_VIEW_ROLES,
            PACKAGE_LIMIT_ROLES,
            ACTIVE_ONLY_ROLES,
            CUSTOMER_ROLES,
        )

        self.assertEqual(params, [3, ["Лицей"]])
        self.assertIn("e.status='Активная'", sql)
        self.assertIn("e.smeta_type", sql)

    def test_foreman_without_package_keeps_existing_all_package_behavior(self):
        sql, params = estimate_visibility_filter(
            [{"companyId": 3, "role": "прораб", "assignedProjects": ["Лицей"]}],
            FULL_VIEW_ROLES,
            (*PACKAGE_LIMIT_ROLES, "прораб"),
            ACTIVE_ONLY_ROLES,
            CUSTOMER_ROLES,
            PACKAGE_OPTIONAL_ROLES,
        )

        self.assertEqual(params, [3, ["Лицей"]])
        self.assertNotIn("work_package", sql)
        self.assertIn("e.status='Активная'", sql)

    def test_resolver_scopes_estimate_and_project_by_company(self):
        cur = FakeCursor([
            {
                "id": 7,
                "company_id": 2,
                "project_id": 19,
                "project_name": "Лицей",
                "work_package": "Общестрой",
                "is_template": False,
            },
            {"id": 19, "company_id": 2, "name": "Лицей"},
        ])

        estimate = resolve_estimate_parent(cur, {"companyId": 2}, 7, for_update=True)

        self.assertEqual(estimate["projectId"], 19)
        self.assertEqual(estimate["projectName"], "Лицей")
        self.assertEqual(cur.calls[0][1], (7, 2))
        self.assertIn("id=%s AND company_id=%s", cur.calls[1][0])
        self.assertTrue(cur.calls[0][0].endswith(" FOR UPDATE"))

    def test_resolver_rejects_cross_company_estimate(self):
        cur = FakeCursor([])
        with self.assertRaises(HTTPException) as error:
            resolve_estimate_parent(cur, {"companyId": 2}, 7)
        self.assertEqual(error.exception.status_code, 404)

    def test_project_identity_mismatch_is_rejected(self):
        cur = FakeCursor([
            (7, 2, 19, "Лицей", "Общестрой", False),
            (19, 2, "Другой объект"),
        ])
        with self.assertRaises(HTTPException) as error:
            resolve_estimate_parent(cur, {"companyId": 2}, 7)
        self.assertEqual(error.exception.status_code, 409)

    def test_company_template_requires_explicit_permission(self):
        template = (8, 2, None, "", "Основная", True)
        with self.assertRaises(HTTPException) as error:
            resolve_estimate_parent(FakeCursor([template]), {"companyId": 2}, 8)
        self.assertEqual(error.exception.status_code, 409)
        self.assertTrue(
            resolve_estimate_parent(
                FakeCursor([template]),
                {"companyId": 2},
                8,
                allow_template=True,
            )["isTemplate"]
        )


if __name__ == "__main__":
    unittest.main()
