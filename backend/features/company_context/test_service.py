import unittest

from fastapi import HTTPException

from backend.features.company_context.service import (
    assert_rows_company_scope,
    company_id_scope_filter,
    company_ids_for_context,
    effective_company_user,
    resolve_request_company_context,
    resolve_resource_company_actor,
)


class MembershipCursor:
    def __init__(self, memberships, companies=None):
        self.memberships = list(memberships)
        self.companies = list(companies or [])
        self.rows = []
        self.row = None
        self.execute_count = 0

    def execute(self, query, params=()):
        self.execute_count += 1
        if "FROM user_company_roles m" in query:
            user_id = int(params[0])
            self.rows = [row for row in self.memberships if int(row.get("user_id") or 0) == user_id]
            return
        if "FROM companies c" in query and "WHERE c.id=%s" in query:
            company_id = int(params[0])
            self.row = next((row for row in self.companies if int(row.get("company_id") or 0) == company_id), None)
            return
        raise AssertionError("Unexpected SQL in unit test: " + " ".join(str(query).split()))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.row


def membership(
    *,
    account_id=5,
    company_id=7,
    role="снабженец",
    assigned_projects=None,
    assigned_packages=None,
):
    return {
        "membership_id": 101,
        "user_id": 42,
        "company_id": company_id,
        "platform_account_id": account_id,
        "role": role,
        "assigned_projects": assigned_projects or [],
        "assigned_packages": assigned_packages or [],
        "active": True,
        "is_default": True,
        "company_name": "Тестовая компания",
        "short_name": "Тест",
        "company_active": True,
    }


def user(*, account_id=5):
    return {
        "id": 42,
        "role": "директор",
        "companyId": 7,
        "platformAccountId": account_id,
    }


class ResolveRequestCompanyContextTests(unittest.TestCase):
    def test_accepts_linked_rows_from_resource_company(self):
        assert_rows_company_scope(
            [{"company_id": 7}, {"companyId": 7}],
            expected_company_id=7,
            resource_label="поставки заявки",
        )

    def test_rejects_linked_row_from_another_company(self):
        with self.assertRaises(HTTPException) as error:
            assert_rows_company_scope(
                [{"company_id": 7}, {"company_id": 8}],
                expected_company_id=7,
                resource_label="поставки заявки",
            )

        self.assertEqual(error.exception.status_code, 409)

    def test_rejects_linked_row_without_company(self):
        with self.assertRaises(HTTPException) as error:
            assert_rows_company_scope(
                [{"company_id": 7}, {}],
                expected_company_id=7,
                resource_label="документы поставки",
            )

        self.assertEqual(error.exception.status_code, 409)

    def test_rejects_missing_resource_company(self):
        with self.assertRaises(HTTPException) as error:
            assert_rows_company_scope([], expected_company_id=None)

        self.assertEqual(error.exception.status_code, 409)

    def test_rejects_all_companies_for_resource_delete_before_querying_database(self):
        cur = MembershipCursor([])

        with self.assertRaises(HTTPException) as error:
            resolve_resource_company_actor(
                cur,
                user(),
                resource_company_id=7,
                action_mode="delete",
                x_company_mode="all_companies",
            )

        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(cur.execute_count, 0)

    def test_rejects_resource_actor_when_membership_role_is_not_allowed(self):
        cur = MembershipCursor([membership(role="поставщик")])

        with self.assertRaises(HTTPException) as error:
            resolve_resource_company_actor(
                cur,
                user(),
                resource_company_id=7,
                action_mode="update",
                allowed_roles=("директор", "снабженец"),
                forbidden_detail="Роль в выбранной компании не позволяет запрашивать КП",
            )

        self.assertEqual(error.exception.status_code, 403)
        self.assertIn("не позволяет запрашивать КП", error.exception.detail)

    def test_builds_effective_user_from_selected_company_membership(self):
        actor = effective_company_user(
            {"id": 42, "role": "директор", "assignedProjects": ["Чужой объект"]},
            {
                "companyId": 7,
                "platformAccountId": 5,
                "effectiveRole": "снабженец",
                "assignedProjects": ["Объект 7"],
                "assignedPackages": ["Электрика"],
            },
        )

        self.assertEqual(actor["id"], 42)
        self.assertEqual(actor["role"], "снабженец")
        self.assertEqual(actor["companyId"], 7)
        self.assertEqual(actor["company_id"], 7)
        self.assertEqual(actor["platformAccountId"], 5)
        self.assertEqual(actor["assignedProjects"], ["Объект 7"])
        self.assertEqual(actor["assignedPackages"], ["Электрика"])

    def test_resolves_resource_actor_with_effective_company_role(self):
        cur = MembershipCursor([membership(
            role="снабженец",
            assigned_projects=["Объект 7"],
            assigned_packages=["Электрика"],
        )])

        context, actor = resolve_resource_company_actor(
            cur,
            user(),
            resource_company_id=7,
            action_mode="update",
            x_company_mode="company",
            x_company_id="7",
            allowed_roles=("директор", "снабженец"),
        )

        self.assertEqual(context["companyId"], 7)
        self.assertEqual(actor["role"], "снабженец")
        self.assertEqual(actor["assignedProjects"], ["Объект 7"])
        self.assertEqual(actor["assignedPackages"], ["Электрика"])

    def test_rejects_resource_without_company_before_querying_database(self):
        cur = MembershipCursor([])

        with self.assertRaises(HTTPException) as error:
            resolve_resource_company_actor(
                cur,
                user(),
                resource_company_id=None,
                action_mode="update",
            )

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(cur.execute_count, 0)

    def test_rejects_resource_company_header_conflict_before_querying_database(self):
        cur = MembershipCursor([])

        with self.assertRaises(HTTPException) as error:
            resolve_resource_company_actor(
                cur,
                user(),
                resource_company_id=7,
                action_mode="update",
                x_company_mode="company",
                x_company_id="8",
            )

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(cur.execute_count, 0)

    def test_rejects_resource_company_body_conflict_before_querying_database(self):
        cur = MembershipCursor([])

        with self.assertRaises(HTTPException) as error:
            resolve_resource_company_actor(
                cur,
                user(),
                resource_company_id=7,
                claimed_company_id=8,
                action_mode="update",
            )

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(cur.execute_count, 0)

    def test_extracts_one_company_id_from_selected_context(self):
        self.assertEqual(company_ids_for_context({"mode": "company", "companyId": 7}), [7])

    def test_extracts_unique_company_ids_from_account_summary(self):
        self.assertEqual(company_ids_for_context({
            "mode": "all_companies",
            "companies": [
                {"companyId": 8},
                {"company_id": 7},
                {"companyId": 8},
                {"companyId": None},
            ],
        }), [7, 8])

    def test_builds_selected_company_filter(self):
        self.assertEqual(
            company_id_scope_filter({"mode": "company", "companyIds": [7]}),
            (" AND company_id=%s", [7]),
        )

    def test_builds_account_summary_filter(self):
        self.assertEqual(
            company_id_scope_filter({"mode": "all_companies", "companyIds": [7, 8]}),
            (" AND company_id = ANY(%s)", [[7, 8]]),
        )

    def test_denies_empty_company_scope(self):
        self.assertEqual(
            company_id_scope_filter({"mode": "all_companies", "companyIds": []}),
            (" AND FALSE", []),
        )

    def test_rejects_all_companies_for_mutation_without_querying_database(self):
        cur = MembershipCursor([])

        with self.assertRaises(HTTPException) as error:
            resolve_request_company_context(
                cur,
                user(),
                action_mode="create",
                x_company_mode="all_companies",
            )

        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(cur.execute_count, 0)

    def test_rejects_malformed_company_header(self):
        cur = MembershipCursor([])

        with self.assertRaises(HTTPException) as error:
            resolve_request_company_context(
                cur,
                user(),
                action_mode="create",
                x_company_mode="company",
                x_company_id="not-a-number",
            )

        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(cur.execute_count, 0)

    def test_rejects_unknown_company_mode(self):
        cur = MembershipCursor([])

        with self.assertRaises(HTTPException) as error:
            resolve_request_company_context(
                cur,
                user(),
                action_mode="create",
                x_company_mode="another_account",
                x_company_id="7",
            )

        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(cur.execute_count, 0)

    def test_rejects_header_and_resource_company_conflict(self):
        cur = MembershipCursor([])

        with self.assertRaises(HTTPException) as error:
            resolve_request_company_context(
                cur,
                user(),
                requested_company_id=8,
                action_mode="create",
                x_company_mode="company",
                x_company_id="7",
            )

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(cur.execute_count, 0)

    def test_resolves_selected_membership_and_returns_effective_role(self):
        cur = MembershipCursor([membership(role="снабженец")])

        context = resolve_request_company_context(
            cur,
            user(),
            requested_company_id=7,
            action_mode="create",
            x_company_mode="company",
            x_company_id="7",
        )

        self.assertEqual(context["companyId"], 7)
        self.assertEqual(context["platformAccountId"], 5)
        self.assertEqual(context["effectiveRole"], "снабженец")
        self.assertEqual(context["requestedMode"], "company")
        self.assertEqual(context["companyIds"], [7])

    def test_resolves_all_companies_to_memberships_inside_the_account(self):
        cur = MembershipCursor([
            membership(company_id=7, role="директор"),
            membership(company_id=8, role="директор"),
        ])

        context = resolve_request_company_context(
            cur,
            user(),
            action_mode="read",
            x_company_mode="all_companies",
        )

        self.assertEqual(context["mode"], "all_companies")
        self.assertTrue(context["readOnly"])
        self.assertEqual(context["companyIds"], [7, 8])

    def test_keeps_legacy_requests_without_headers_compatible(self):
        cur = MembershipCursor([membership(role="директор")])

        context = resolve_request_company_context(
            cur,
            user(),
            requested_company_id=7,
            action_mode="create",
        )

        self.assertEqual(context["companyId"], 7)
        self.assertEqual(context["effectiveRole"], "директор")
        self.assertEqual(context["requestedMode"], "legacy")
        self.assertEqual(context["companyIds"], [7])

    def test_keeps_users_company_id_fallback_compatible(self):
        cur = MembershipCursor([], companies=[{
            "company_id": 7,
            "platform_account_id": 5,
            "company_name": "Legacy company",
            "short_name": "Legacy",
            "company_active": True,
        }])

        context = resolve_request_company_context(
            cur,
            user(),
            action_mode="create",
        )

        self.assertEqual(context["companyId"], 7)
        self.assertEqual(context["source"], "legacy")
        self.assertEqual(context["effectiveRole"], "директор")
        self.assertEqual(context["requestedMode"], "legacy")
        self.assertEqual(context["companyIds"], [7])

    def test_rejects_company_without_membership(self):
        cur = MembershipCursor([membership(company_id=7)])

        with self.assertRaises(HTTPException) as error:
            resolve_request_company_context(
                cur,
                user(),
                action_mode="create",
                x_company_mode="company",
                x_company_id="8",
            )

        self.assertEqual(error.exception.status_code, 403)

    def test_rejects_membership_from_another_platform_account(self):
        cur = MembershipCursor([membership(account_id=6)])

        with self.assertRaises(HTTPException) as error:
            resolve_request_company_context(
                cur,
                user(account_id=5),
                requested_company_id=7,
                action_mode="create",
                x_company_mode="company",
                x_company_id="7",
            )

        self.assertEqual(error.exception.status_code, 403)

    def test_rejects_cross_account_default_membership_without_headers(self):
        cur = MembershipCursor([membership(account_id=6)])

        with self.assertRaises(HTTPException) as error:
            resolve_request_company_context(
                cur,
                user(account_id=5),
                action_mode="read",
            )

        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
