import unittest

from backend.features.brigade_access.service import brigade_contract_visibility_filter


FULL_VIEW_ROLES = ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик")
CONTRACT_ROLES = (*FULL_VIEW_ROLES, "прораб", "мастер", "субподрядчик", "бригадир")
WORKER_ROLES = ("мастер", "субподрядчик", "бригадир")
PACKAGE_LIMIT_ROLES = ("прораб", *WORKER_ROLES)


class BrigadeContractVisibilityFilterTests(unittest.TestCase):
    def test_finance_membership_sees_only_its_company(self):
        sql, params = brigade_contract_visibility_filter(
            [{"companyId": 4, "role": "бухгалтер"}],
            allowed_roles=CONTRACT_ROLES,
            full_view_roles=FULL_VIEW_ROLES,
            worker_roles=WORKER_ROLES,
            package_limit_roles=PACKAGE_LIMIT_ROLES,
        )

        self.assertEqual(sql, "(bc.company_id=%s)")
        self.assertEqual(params, [4])

    def test_foreman_is_limited_to_assigned_projects_without_required_package(self):
        sql, params = brigade_contract_visibility_filter(
            [{"companyId": 2, "role": "прораб", "assignedProjects": ["Школа"]}],
            allowed_roles=CONTRACT_ROLES,
            full_view_roles=FULL_VIEW_ROLES,
            worker_roles=WORKER_ROLES,
            package_limit_roles=PACKAGE_LIMIT_ROLES,
            package_optional_roles=("прораб",),
        )

        self.assertIn("bc.company_id=%s", sql)
        self.assertIn("bc.project_name = ANY(%s)", sql)
        self.assertNotIn("brigade_contract_items", sql)
        self.assertEqual(params, [2, ["Школа"]])

    def test_worker_scope_keeps_company_identity_project_and_package_together(self):
        sql, params = brigade_contract_visibility_filter(
            [{
                "id": 42,
                "name": "Иван Иванов",
                "companyId": 3,
                "role": "мастер",
                "assignedProjects": ["Лицей"],
                "assignedPackages": ["Электрика"],
            }],
            allowed_roles=CONTRACT_ROLES,
            full_view_roles=FULL_VIEW_ROLES,
            worker_roles=WORKER_ROLES,
            package_limit_roles=PACKAGE_LIMIT_ROLES,
            package_optional_roles=("прораб",),
        )

        self.assertIn("bc.company_id=%s", sql)
        self.assertIn("bc.project_name = ANY(%s)", sql)
        self.assertIn("bc.contractor_id", sql)
        self.assertIn("brigade_contract_items", sql)
        self.assertEqual(params, [3, ["Лицей"], 42, "Иван Иванов", ["Электрика"]])
        self.assertEqual(sql.count("%s"), len(params))

    def test_worker_without_package_fails_closed(self):
        self.assertEqual(
            brigade_contract_visibility_filter(
                [{
                    "id": 42,
                    "name": "Иван Иванов",
                    "companyId": 3,
                    "role": "мастер",
                    "assignedProjects": ["Лицей"],
                    "assignedPackages": [],
                }],
                allowed_roles=CONTRACT_ROLES,
                full_view_roles=FULL_VIEW_ROLES,
                worker_roles=WORKER_ROLES,
                package_limit_roles=PACKAGE_LIMIT_ROLES,
                package_optional_roles=("прораб",),
            ),
            ("FALSE", []),
        )

    def test_item_scope_filters_the_outer_item_instead_of_only_contract_existence(self):
        sql, params = brigade_contract_visibility_filter(
            [{
                "id": 42,
                "name": "Иван Иванов",
                "companyId": 3,
                "role": "мастер",
                "assignedProjects": ["Лицей"],
                "assignedPackages": ["Электрика"],
            }],
            allowed_roles=CONTRACT_ROLES,
            full_view_roles=FULL_VIEW_ROLES,
            worker_roles=WORKER_ROLES,
            package_limit_roles=PACKAGE_LIMIT_ROLES,
            package_optional_roles=("прораб",),
            item_alias="bci",
        )

        self.assertIn("bci.work_package", sql)
        self.assertNotIn("SELECT 1 FROM brigade_contract_items", sql)
        self.assertEqual(params, [3, ["Лицей"], 42, "Иван Иванов", ["Электрика"]])

    def test_disallowed_role_fails_closed(self):
        self.assertEqual(
            brigade_contract_visibility_filter(
                [{"companyId": 3, "role": "кладовщик", "assignedProjects": ["Лицей"]}],
                allowed_roles=CONTRACT_ROLES,
                full_view_roles=FULL_VIEW_ROLES,
                worker_roles=WORKER_ROLES,
                package_limit_roles=PACKAGE_LIMIT_ROLES,
            ),
            ("FALSE", []),
        )


if __name__ == "__main__":
    unittest.main()
