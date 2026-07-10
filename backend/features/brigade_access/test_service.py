import unittest
from decimal import Decimal

from fastapi import HTTPException

from backend.features.brigade_access.service import (
    brigade_contract_project_reference,
    brigade_contract_visibility_filter,
    require_brigade_child_company,
    require_brigade_project_payment_link,
    require_positive_brigade_amount,
)


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


class BrigadeChildCompanyTests(unittest.TestCase):
    def test_accepts_matching_parent_and_child_company(self):
        self.assertEqual(require_brigade_child_company(4, 4), 4)

    def test_rejects_missing_or_mismatched_company(self):
        for child_company_id, contract_company_id in ((None, 4), (4, None), (3, 4)):
            with self.subTest(
                child_company_id=child_company_id,
                contract_company_id=contract_company_id,
            ), self.assertRaises(HTTPException) as raised:
                require_brigade_child_company(child_company_id, contract_company_id)

            self.assertEqual(raised.exception.status_code, 409)


class BrigadePaymentWriteRulesTests(unittest.TestCase):
    def test_requires_positive_finite_amount(self):
        self.assertEqual(require_positive_brigade_amount("12.5"), Decimal("12.50"))
        self.assertEqual(require_positive_brigade_amount("12.345"), Decimal("12.35"))

        for value in (None, "", "bad", "NaN", "Infinity", "-Infinity", 0, -1, "0.001", "0.009"):
            with self.subTest(value=value), self.assertRaises(HTTPException) as raised:
                require_positive_brigade_amount(value)

            self.assertEqual(raised.exception.status_code, 400)

    def test_exact_project_id_is_authoritative_over_stale_name(self):
        self.assertEqual(brigade_contract_project_reference(7, "Старое имя"), (7, ""))
        self.assertEqual(brigade_contract_project_reference(None, "  Школа  "), (None, "Школа"))

    def test_requires_explicit_project_payment_link_for_reversal(self):
        self.assertEqual(require_brigade_project_payment_link("15"), 15)

        for value in (None, "", 0, -1, "bad"):
            with self.subTest(value=value), self.assertRaises(HTTPException) as raised:
                require_brigade_project_payment_link(value)

            self.assertEqual(raised.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
