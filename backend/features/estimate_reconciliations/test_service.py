import unittest

from backend.features.estimate_reconciliations.service import reconciliation_visibility_filter


class ReconciliationVisibilityFilterTests(unittest.TestCase):
    def test_full_view_role_is_scoped_by_company(self):
        sql, params = reconciliation_visibility_filter(
            [{"companyId": 7, "role": "директор"}],
            ("директор",),
            ("директор",),
            (),
        )

        self.assertEqual(sql, "((p.company_id=%s))")
        self.assertEqual(params, [7])

    def test_assigned_role_is_scoped_by_project_and_package(self):
        sql, params = reconciliation_visibility_filter(
            [{
                "companyId": 8,
                "role": "сметчик",
                "assignedProjects": '["Объект А"]',
                "assignedPackages": '["Фасад"]',
            }],
            ("сметчик",),
            (),
            ("сметчик",),
        )

        self.assertIn("p.company_id=%s", sql)
        self.assertIn("p.name = ANY(%s)", sql)
        self.assertIn("r.work_package", sql)
        self.assertEqual(params, [8, ["Объект А"], ["Фасад"]])

    def test_customer_only_sees_approved_reconciliations(self):
        sql, params = reconciliation_visibility_filter(
            [{"companyId": 9, "role": "заказчик", "assignedProjects": ["Объект Б"]}],
            ("заказчик",),
            (),
            (),
            customer_roles=("заказчик",),
        )

        self.assertIn("r.status='Утверждена'", sql)
        self.assertEqual(params, [9, ["Объект Б"]])

    def test_role_outside_document_scope_returns_false(self):
        sql, params = reconciliation_visibility_filter(
            [{"companyId": 10, "role": "рабочий"}],
            ("директор",),
            ("директор",),
            (),
        )

        self.assertEqual((sql, params), ("FALSE", []))


if __name__ == "__main__":
    unittest.main()
