"""PostgreSQL integration regressions for company membership isolation.

Runs only against a dedicated throwaway PostgreSQL database supplied by CI.
Never point this test at production or a shared database.
"""
import os
import re
import unittest

import psycopg2
from fastapi import HTTPException
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor

from backend.features.company_context.service import (
    company_ids_for_context,
    effective_company_actors,
    effective_company_user,
    resolve_request_company_context,
    resolve_resource_company_actor,
)


RUN_POSTGRES = os.getenv("COMPANY_CONTEXT_RUN_POSTGRES_INTEGRATION") == "1"
TEST_DATABASE_URL = os.getenv("COMPANY_CONTEXT_TEST_DATABASE_URL", "")


@unittest.skipUnless(
    RUN_POSTGRES and TEST_DATABASE_URL,
    "set COMPANY_CONTEXT_RUN_POSTGRES_INTEGRATION=1 with a dedicated test database",
)
class CompanyMembershipPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = parse_dsn(TEST_DATABASE_URL).get("dbname", "")
        if not re.fullmatch(r"stroyka_company_context_test(?:_[a-z0-9_]+)?", configured):
            raise RuntimeError("company_context PostgreSQL tests require a dedicated stroyka_company_context_test* database")
        cls.db = psycopg2.connect(TEST_DATABASE_URL)
        cls.db.autocommit = True
        with cls.db.cursor() as cur:
            cur.execute("SELECT current_database()")
            if cur.fetchone()[0] != configured:
                raise RuntimeError("dedicated database identity changed")

    @classmethod
    def tearDownClass(cls):
        if not hasattr(cls, "db"):
            return
        with cls.db.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS user_company_roles")
            cur.execute("DROP TABLE IF EXISTS companies")
        cls.db.close()

    def setUp(self):
        with self.db.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS user_company_roles")
            cur.execute("DROP TABLE IF EXISTS companies")
            cur.execute("""
                CREATE TABLE companies (
                    id INTEGER PRIMARY KEY,
                    platform_account_id INTEGER,
                    name TEXT,
                    short_name TEXT,
                    active BOOLEAN,
                    plan TEXT,
                    trial_until DATE,
                    plan_expires_at DATE,
                    payment_status TEXT,
                    suspended_at TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE user_company_roles (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    company_id INTEGER,
                    staff_id INTEGER,
                    platform_account_id INTEGER,
                    role TEXT,
                    assigned_projects JSONB,
                    assigned_packages JSONB,
                    active BOOLEAN,
                    is_default BOOLEAN
                )
            """)
            cur.execute("""
                INSERT INTO companies (id, platform_account_id, name, active)
                VALUES
                    (7, 5, 'A', TRUE),
                    (8, 5, 'B', TRUE),
                    (9, 6, 'C', TRUE)
            """)
        self.user = {
            "id": 42,
            "role": "директор",
            "companyId": 7,
            "platformAccountId": 5,
        }

    def cursor(self, mapping=True):
        return self.db.cursor(cursor_factory=RealDictCursor) if mapping else self.db.cursor()

    def add_member(self, company=7, role="прораб", active=True, user_id=42, is_default=None):
        if is_default is None:
            is_default = company == 7
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_company_roles
                    (user_id, company_id, role, active, is_default, assigned_projects, assigned_packages)
                VALUES (%s, %s, %s, %s, %s, '[]'::jsonb, '[]'::jsonb)
                """,
                (user_id, company, role, active, is_default),
            )

    def selected(self, company=7, action="read", mapping=True):
        cur = self.cursor(mapping=mapping)
        self.addCleanup(cur.close)
        return resolve_request_company_context(
            cur,
            self.user,
            action_mode=action,
            x_company_mode="company",
            x_company_id=str(company),
        )

    def assert_forbidden(self, fn, expected=403):
        with self.assertRaises(HTTPException) as caught:
            fn()
        self.assertEqual(caught.exception.status_code, expected)

    def test_blank_roles_fail_closed_without_legacy_fallback(self):
        for role in (None, "", "   "):
            with self.subTest(role=role):
                with self.db.cursor() as cur:
                    cur.execute("TRUNCATE user_company_roles RESTART IDENTITY")
                self.add_member(role=role)
                for action in ("read", "create", "update", "delete"):
                    with self.subTest(action=action):
                        self.assert_forbidden(lambda: self.selected(action=action))

    def test_padded_privileged_role_is_denied_not_normalized(self):
        self.add_member(role=" директор ")
        self.assert_forbidden(self.selected)

    def test_inactive_membership_and_company_fail_closed(self):
        self.add_member(role="директор", active=False)
        self.assert_forbidden(self.selected)
        with self.db.cursor() as cur:
            cur.execute("TRUNCATE user_company_roles RESTART IDENTITY")
            cur.execute("UPDATE companies SET active=FALSE WHERE id=7")
        self.add_member(role="директор")
        self.assert_forbidden(self.selected)

    def test_all_companies_exports_only_verified_memberships(self):
        self.add_member(7, "прораб")
        self.add_member(8, None)
        cur = self.cursor()
        self.addCleanup(cur.close)
        context = resolve_request_company_context(
            cur,
            self.user,
            x_company_mode="all_companies",
            action_mode="read",
        )
        self.assertEqual(company_ids_for_context(context), [7])
        actors = effective_company_actors(self.user, context)
        self.assertEqual([(a["companyId"], a["role"]) for a in actors], [(7, "прораб")])

    def test_selected_lower_role_never_inherits_global_director(self):
        self.add_member(7, "прораб")
        context = self.selected()
        self.assertEqual(context["effectiveRole"], "прораб")
        cur = self.cursor()
        self.addCleanup(cur.close)
        self.assert_forbidden(lambda: resolve_resource_company_actor(
            cur,
            self.user,
            7,
            allowed_roles=("директор",),
        ))

    def test_revocation_and_role_change_apply_on_next_request(self):
        self.add_member(7, "директор")
        self.assertEqual(self.selected()["effectiveRole"], "директор")
        with self.db.cursor() as cur:
            cur.execute("UPDATE user_company_roles SET role='прораб' WHERE user_id=42")
        self.assertEqual(self.selected()["effectiveRole"], "прораб")
        with self.db.cursor() as cur:
            cur.execute("UPDATE user_company_roles SET active=FALSE WHERE user_id=42")
        self.assert_forbidden(self.selected)

    def test_tuple_cursor_obeys_same_policy(self):
        self.add_member(7, "прораб")
        self.add_member(8, "")
        context = self.selected(7, mapping=False)
        self.assertEqual(context["effectiveRole"], "прораб")
        self.assert_forbidden(lambda: self.selected(8, mapping=False))

    def test_foreign_user_and_cross_account_memberships_do_not_expand_scope(self):
        self.add_member(7, "прораб")
        self.add_member(8, "директор", user_id=99)
        self.add_member(9, "директор")
        self.assert_forbidden(lambda: self.selected(8))
        self.assert_forbidden(lambda: self.selected(9))

    def test_legacy_fallback_only_when_no_membership_rows_exist(self):
        context = self.selected()
        self.assertEqual(context["source"], "legacy")
        self.assertEqual(context["effectiveRole"], "директор")
        self.add_member(8, None)
        self.assert_forbidden(self.selected)

    def test_effective_user_rejects_explicit_empty_or_revoked_role(self):
        for context in (
            {"companyId": 7},
            {"companyId": 7, "role": ""},
            {"companyId": 7, "role": " директор "},
            {"companyId": 7, "role": "директор", "effectiveRole": ""},
            {"companyId": 7, "role": "директор", "active": False},
            {"companyId": 7, "role": "директор", "companyActive": False},
        ):
            with self.subTest(context=context):
                self.assert_forbidden(lambda: effective_company_user(self.user, context))


if __name__ == "__main__":
    unittest.main()
