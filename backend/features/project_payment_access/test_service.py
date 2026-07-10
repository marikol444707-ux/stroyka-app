import unittest

from backend.features.project_payment_access.service import project_payment_visibility_filter


FINANCE_ROLES = ("директор", "зам_директора", "бухгалтер")


class ProjectPaymentVisibilityFilterTests(unittest.TestCase):
    def test_finance_membership_sees_only_its_company(self):
        sql, params = project_payment_visibility_filter(
            [{"companyId": 4, "role": "бухгалтер"}],
            FINANCE_ROLES,
        )

        self.assertEqual(sql, "(pp.company_id=%s)")
        self.assertEqual(params, [4])

    def test_all_companies_keeps_each_membership_role_separate(self):
        sql, params = project_payment_visibility_filter(
            [
                {"companyId": 1, "role": "директор"},
                {
                    "companyId": 2,
                    "role": "заказчик",
                    "assignedProjects": ["Школа", "Школа"],
                },
                {"companyId": 3, "role": "мастер", "assignedProjects": ["Чужой объект"]},
            ],
            FINANCE_ROLES,
        )

        self.assertIn("pp.company_id=%s", sql)
        self.assertIn("pp.amount > 0", sql)
        self.assertIn("pp.project_name = ANY(%s)", sql)
        self.assertNotIn("Чужой объект", params)
        self.assertEqual(params, [1, 2, ["Школа"]])
        self.assertEqual(sql.count("%s"), len(params))

    def test_customer_without_projects_fails_closed(self):
        self.assertEqual(
            project_payment_visibility_filter(
                [{"companyId": 2, "role": "заказчик", "assignedProjects": []}],
                FINANCE_ROLES,
            ),
            ("FALSE", []),
        )

    def test_disallowed_membership_fails_closed(self):
        self.assertEqual(
            project_payment_visibility_filter(
                [{"companyId": 3, "role": "мастер", "assignedProjects": ["Объект 3"]}],
                FINANCE_ROLES,
            ),
            ("FALSE", []),
        )


if __name__ == "__main__":
    unittest.main()
