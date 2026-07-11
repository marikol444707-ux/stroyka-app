import unittest
from decimal import Decimal

from fastapi import HTTPException

from backend.features.brigade_access.service import (
    brigade_contract_project_reference,
    brigade_contract_visibility_filter,
    grant_brigade_contractor_scope,
    require_brigade_child_company,
    require_brigade_project_payment_link,
    require_brigade_write_actor,
    require_positive_brigade_amount,
    resolve_brigade_contractor_user,
)


FULL_VIEW_ROLES = ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик")
CONTRACT_ROLES = (*FULL_VIEW_ROLES, "прораб", "мастер", "субподрядчик", "бригадир")
WORKER_ROLES = ("мастер", "субподрядчик", "бригадир")
PACKAGE_LIMIT_ROLES = ("прораб", *WORKER_ROLES)
WRITE_ROLES = ("директор", "зам_директора")


class SequencedCursor:
    def __init__(self, *, one=None, many=None):
        self.one = list(one or [])
        self.many = list(many or [])
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.one.pop(0) if self.one else None

    def fetchall(self):
        return self.many.pop(0) if self.many else []


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


class BrigadeContractWriteRulesTests(unittest.TestCase):
    def test_write_requires_one_selected_company_and_effective_role(self):
        with self.assertRaises(HTTPException) as raised:
            require_brigade_write_actor(
                [
                    {"companyId": 1, "role": "директор"},
                    {"companyId": 2, "role": "директор"},
                ],
                WRITE_ROLES,
            )
        self.assertEqual(raised.exception.status_code, 409)

        with self.assertRaises(HTTPException) as raised:
            require_brigade_write_actor(
                [{"companyId": 2, "role": "бухгалтер"}],
                WRITE_ROLES,
            )
        self.assertEqual(raised.exception.status_code, 403)

        actor = require_brigade_write_actor(
            [{"company_id": "2", "role": "зам_директора"}],
            WRITE_ROLES,
        )
        self.assertEqual(actor["companyId"], 2)
        self.assertEqual(actor["company_id"], 2)

    def test_contractor_id_is_resolved_only_inside_selected_company(self):
        cur = SequencedCursor(one=[{"id": 23, "name": "Иван"}, None])

        self.assertEqual(resolve_brigade_contractor_user(cur, 4, 23, "Иван"), 23)
        self.assertIn("u.company_id=%s", cur.calls[0][0])
        self.assertIn("m.company_id=%s", cur.calls[0][0])
        self.assertEqual(cur.calls[0][1], (23, 4, 4))

    def test_staff_id_collision_does_not_link_an_unrelated_user(self):
        cur = SequencedCursor(
            one=[
                {"id": 23, "name": "Директор"},
                {
                    "name": "Иван Иванов",
                    "email_work": "master@example.test",
                    "email_personal": "",
                },
            ],
            many=[[{"id": 41}]],
        )

        self.assertEqual(resolve_brigade_contractor_user(cur, 4, 23, "Иван Иванов"), 41)
        self.assertIn("LOWER(COALESCE(u.email,'')) = ANY(%s)", cur.calls[2][0])
        self.assertEqual(cur.calls[2][1], (4, 4, ["master@example.test"]))

    def test_contractor_from_another_company_is_rejected(self):
        cur = SequencedCursor(one=[None, None])

        with self.assertRaises(HTTPException) as raised:
            resolve_brigade_contractor_user(cur, 4, 23, "Чужой исполнитель")

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("s.company_id=%s", cur.calls[1][0])
        self.assertEqual(cur.calls[1][1], (23, 4))

    def test_company_staff_without_system_user_remains_unlinked(self):
        cur = SequencedCursor(
            one=[None, {"name": "Иван Иванов", "email_work": "", "email_personal": ""}],
            many=[[]],
        )

        self.assertIsNone(resolve_brigade_contractor_user(cur, 4, 23, "Иван Иванов"))

    def test_duplicate_contractor_name_inside_company_is_not_guessed(self):
        cur = SequencedCursor(many=[[{"id": 23}, {"id": 24}]])

        with self.assertRaises(HTTPException) as raised:
            resolve_brigade_contractor_user(cur, 4, None, "Иван Иванов")

        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("m.company_id=%s", cur.calls[0][0])
        self.assertEqual(cur.calls[0][1], (4, 4, "Иван Иванов"))

    def test_manual_brigade_name_can_remain_without_user_link(self):
        cur = SequencedCursor(many=[[]])

        self.assertIsNone(resolve_brigade_contractor_user(cur, 4, None, "Бригада Север"))

    def test_scope_grant_updates_membership_and_legacy_default_in_same_company(self):
        cur = SequencedCursor()

        result = grant_brigade_contractor_scope(
            cur,
            4,
            23,
            "Лицей",
            "Электрика",
            project_scoped_roles=("мастер", "бригадир"),
            package_required_roles=("мастер", "бригадир"),
        )

        self.assertEqual(result["companyId"], 4)
        self.assertEqual(result["userId"], 23)
        self.assertEqual(len(cur.calls), 2)
        membership_sql, membership_params = cur.calls[0]
        self.assertIn("UPDATE user_company_roles", membership_sql)
        self.assertIn("@> jsonb_build_array", membership_sql)
        self.assertIn("company_id=%s", membership_sql)
        self.assertEqual(membership_params[-3:-1], (23, 4))
        legacy_sql, legacy_params = cur.calls[1]
        self.assertIn("UPDATE users", legacy_sql)
        self.assertIn("company_id=%s", legacy_sql)
        self.assertEqual(legacy_params[-3:-1], (23, 4))


if __name__ == "__main__":
    unittest.main()
