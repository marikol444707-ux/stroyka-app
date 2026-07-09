import unittest

from fastapi import HTTPException

from backend.features.company_context.service import resolve_request_company_context


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


def membership(*, account_id=5, company_id=7, role="снабженец"):
    return {
        "membership_id": 101,
        "user_id": 42,
        "company_id": company_id,
        "platform_account_id": account_id,
        "role": role,
        "assigned_projects": [],
        "assigned_packages": [],
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


if __name__ == "__main__":
    unittest.main()
