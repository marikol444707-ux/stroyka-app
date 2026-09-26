"""Security regressions for #69/#167: execute SELECT predicates, not canned rows.

The isolated SQLite adapter only translates parameter placeholders and boolean
result types. It executes the production SELECT/JOIN/WHERE/ORDER BY unchanged.
This suite is not a PostgreSQL concurrency or endpoint integration test.
"""
import sqlite3
import unittest

from fastapi import HTTPException

from backend.features.company_context.service import (
    build_company_context_response,
    company_ids_for_context,
    effective_company_actors,
    effective_company_user,
    resolve_request_company_context,
    resolve_resource_company_actor,
    user_company_memberships,
)


class SqlCursor:
    def __init__(self, connection, *, mapping=True):
        self.cursor = connection.cursor()
        self.mapping = mapping

    @property
    def description(self):
        return self.cursor.description

    def execute(self, query, params=()):
        self.cursor.execute(query.replace("%s", "?"), params)

    def _row(self, row):
        if row is None:
            return None
        names = [column[0] for column in self.description]
        values = [
            bool(value) if name in {"active", "company_active", "is_default"}
            and value is not None else value
            for name, value in zip(names, row)
        ]
        return dict(zip(names, values)) if self.mapping else tuple(values)

    def fetchall(self):
        return [self._row(row) for row in self.cursor.fetchall()]

    def fetchone(self):
        return self._row(self.cursor.fetchone())


class MembershipSecurityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE companies (
                id INTEGER PRIMARY KEY, platform_account_id INTEGER,
                name TEXT, short_name TEXT, active BOOLEAN,
                plan TEXT, trial_until TEXT, plan_expires_at TEXT,
                payment_status TEXT, suspended_at TEXT
            );
            CREATE TABLE user_company_roles (
                id INTEGER PRIMARY KEY, user_id INTEGER, company_id INTEGER,
                staff_id INTEGER, platform_account_id INTEGER, role TEXT,
                assigned_projects TEXT, assigned_packages TEXT,
                active BOOLEAN, is_default BOOLEAN
            );
            INSERT INTO companies (id, platform_account_id, name, active)
            VALUES (7, 5, 'A', TRUE), (8, 5, 'B', TRUE), (9, 6, 'C', TRUE);
        """)
        self.user = {"id": 42, "role": "директор", "companyId": 7, "platformAccountId": 5}
        self.cur = SqlCursor(self.db)

    def add_member(self, company=7, role="прораб", active=True, user_id=42):
        self.db.execute(
            "INSERT INTO user_company_roles "
            "(user_id,company_id,role,active,is_default,assigned_projects,assigned_packages) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, company, role, active, company == 7, '[]', '[]'),
        )

    def selected(self, company=7, action="read", **kwargs):
        return resolve_request_company_context(
            self.cur, self.user, action_mode=action,
            x_company_mode="company", x_company_id=str(company), **kwargs,
        )

    def assert_forbidden(self, function):
        with self.assertRaises(HTTPException) as caught:
            function()
        self.assertEqual(caught.exception.status_code, 403)

    def test_null_role_is_denied_for_read_and_write(self):
        self.add_member(role=None)
        for action in ("read", "create", "update", "delete"):
            with self.subTest(action=action):
                self.assert_forbidden(lambda: self.selected(action=action))

    def test_empty_role_is_denied(self):
        self.add_member(role="")
        self.assert_forbidden(self.selected)

    def test_whitespace_role_is_denied(self):
        self.add_member(role=" \t\n")
        self.assert_forbidden(self.selected)

    def test_inactive_membership_cannot_reenter_via_legacy_company(self):
        self.add_member(role="директор", active=False)
        self.assert_forbidden(self.selected)

    def test_inactive_company_cannot_reenter_via_legacy_company(self):
        self.add_member(role="директор")
        self.db.execute("UPDATE companies SET active=FALSE WHERE id=7")
        self.assert_forbidden(self.selected)

    def test_roleless_only_membership_does_not_appear_in_selector(self):
        self.add_member(role=None)
        result = build_company_context_response(self.cur, self.user)
        self.assertEqual(result["companies"], [])
        self.assertIsNone(result["defaultCompanyId"])

    def test_rejected_only_membership_cannot_be_exported_in_all_companies(self):
        self.add_member(role="", active=False)
        self.assert_forbidden(lambda: resolve_request_company_context(
            self.cur, self.user, x_company_mode="all_companies",
        ))

    def test_all_companies_exports_only_valid_memberships(self):
        self.add_member(7, "прораб")
        self.add_member(8, None)
        context = resolve_request_company_context(
            self.cur, self.user, x_company_mode="all_companies",
        )
        self.assertEqual(company_ids_for_context(context), [7])
        actors = effective_company_actors(self.user, context)
        self.assertEqual([(a["companyId"], a["role"]) for a in actors], [(7, "прораб")])
        self.assert_forbidden(lambda: self.selected(8))

    def test_valid_nondefault_company_survives_invalid_default(self):
        self.add_member(7, None)
        self.add_member(8, "снабженец")
        context = self.selected(8, "update")
        self.assertEqual(context["effectiveRole"], "снабженец")
        self.assertEqual(effective_company_user(self.user, context)["companyId"], 8)
        self.assert_forbidden(lambda: self.selected(7))

    def test_selected_lower_role_does_not_inherit_global_director(self):
        self.add_member(role="прораб")
        self.assertEqual(self.selected()["effectiveRole"], "прораб")
        self.assert_forbidden(lambda: resolve_resource_company_actor(
            self.cur, self.user, 7, allowed_roles=("директор",),
        ))

    def test_effective_actor_denies_missing_blank_and_revoked_roles(self):
        contexts = [
            {"companyId": 7},
            {"companyId": 7, "role": None},
            {"companyId": 7, "role": ""},
            {"companyId": 7, "role": " \t"},
            {"companyId": 7, "role": "директор", "effectiveRole": ""},
            {"companyId": 7, "role": "директор", "active": False},
            {"companyId": 7, "role": "директор", "companyActive": False},
        ]
        for context in contexts:
            with self.subTest(context=context):
                self.assert_forbidden(lambda: effective_company_user(self.user, context))

    def test_next_request_observes_membership_revocation(self):
        self.add_member(role="директор")
        self.assertEqual(self.selected()["effectiveRole"], "директор")
        self.db.execute("UPDATE user_company_roles SET active=FALSE WHERE user_id=42")
        self.assert_forbidden(self.selected)

    def test_next_request_observes_membership_role_change(self):
        self.add_member(role="директор")
        self.assertEqual(self.selected()["effectiveRole"], "директор")
        self.db.execute("UPDATE user_company_roles SET role='прораб' WHERE user_id=42")
        self.assertEqual(self.selected()["effectiveRole"], "прораб")

    def test_tuple_cursor_has_same_membership_policy(self):
        self.cur = SqlCursor(self.db, mapping=False)
        self.add_member(7, "прораб")
        self.add_member(8, "")
        self.assertEqual(self.selected()["effectiveRole"], "прораб")
        self.assert_forbidden(lambda: self.selected(8))

    def test_other_users_membership_does_not_grant_foreign_company(self):
        self.add_member(7, "прораб")
        self.add_member(8, "директор", user_id=99)
        self.assert_forbidden(lambda: self.selected(8))

    def test_cross_account_membership_stays_forbidden(self):
        self.add_member(9, "директор")
        self.assert_forbidden(lambda: self.selected(9))

    def test_legacy_compatibility_only_when_no_membership_rows_exist(self):
        context = self.selected()
        self.assertEqual(context["source"], "legacy")
        self.assertEqual(context["effectiveRole"], "директор")
        self.add_member(8, None)
        self.assert_forbidden(self.selected)

    def test_inactive_legacy_company_is_not_accepted(self):
        self.db.execute("UPDATE companies SET active=FALSE WHERE id=7")
        self.assert_forbidden(self.selected)

    def test_include_inactive_is_listing_not_permission(self):
        self.add_member(role="прораб", active=False)
        contexts = user_company_memberships(self.cur, self.user, include_inactive=True)
        self.assertEqual(len(contexts), 1)
        self.assertFalse(contexts[0]["active"])
        self.assert_forbidden(lambda: effective_company_user(self.user, contexts[0]))

    def test_explicit_account_overview_remains_read_only(self):
        self.user.update(role="account_test", companyId=None)
        context = self.selected(client_account_roles=("account_test",))
        self.assertEqual(context["source"], "account")
        self.assertTrue(context["readOnly"])
        self.assert_forbidden(lambda: self.selected(
            action="update", client_account_roles=("account_test",),
        ))

    def test_platform_summary_does_not_grant_working_company_actor(self):
        self.user["role"] = "platform_test"
        context = resolve_request_company_context(
            self.cur, self.user, x_company_mode="all_companies",
            platform_staff_roles=("platform_test",),
        )
        self.assertTrue(context["readOnly"])
        self.assertEqual(effective_company_actors(self.user, context), [])
        self.assert_forbidden(lambda: self.selected(platform_staff_roles=("platform_test",)))

    def test_body_and_header_conflict_stays_rejected(self):
        self.add_member(7, "директор")
        with self.assertRaises(HTTPException) as caught:
            resolve_resource_company_actor(
                self.cur, self.user, 7, claimed_company_id=8,
                x_company_mode="company", x_company_id="7",
            )
        self.assertEqual(caught.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
