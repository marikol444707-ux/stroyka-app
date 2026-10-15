"""Real SQL regression for Jev QA cookie-only tenant isolation.

Uses ONLY a dedicated disposable GitHub CI database, never a QA/production DB.
Fixture tables are created and removed inside that disposable database.
"""
import os
import re
import unittest

import psycopg2
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor

from backend.features.company_context.qa_readonly import (
    QAReadOnlyAuthRejected, resolve_qa_identity_read_only,
)

_ENABLED = os.getenv("COMPANY_CONTEXT_RUN_POSTGRES_INTEGRATION") == "1"
_DSN = os.getenv("COMPANY_CONTEXT_TEST_DATABASE_URL", "")
_CLAIMS = {"authenticationKind": "cookie_session", "sessionHash": "a" * 64}
_TABLES = ("user_company_roles", "user_sessions", "users", "companies", "platform_accounts")


@unittest.skipUnless(_ENABLED and _DSN, "requires isolated CI PostgreSQL database")
class QAReadOnlySessionPostgresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        name = parse_dsn(_DSN).get("dbname", "")
        if not re.fullmatch(r"stroyka_company_context_test(?:_[a-z0-9_]+)?", name):
            raise RuntimeError("refusing non-disposable PostgreSQL database")
        cls.db = psycopg2.connect(_DSN)
        cls.db.autocommit = True
        with cls.db.cursor() as cur:
            cur.execute("SELECT current_database()")
            if cur.fetchone()[0] != name:
                raise RuntimeError("database identity mismatch")
            for table in _TABLES:
                cur.execute("SELECT to_regclass(%s)", ("public." + table,))
                if cur.fetchone()[0] is not None:
                    raise RuntimeError("fixture would overwrite an existing table")
            cur.execute("CREATE TABLE public.platform_accounts (id integer PRIMARY KEY, active boolean, status text)")
            cur.execute("CREATE TABLE public.companies (id integer PRIMARY KEY, platform_account_id integer, active boolean)")
            cur.execute("CREATE TABLE public.users (id integer PRIMARY KEY, name text, email text, active boolean, role text, two_factor_required boolean, two_factor_enabled boolean, platform_account_id integer)")
            cur.execute("""CREATE TABLE public.user_sessions
                (user_id integer, session_hash text, revoked_at timestamptz,
                 expires_at timestamptz, two_factor_passed boolean)""")
            cur.execute("""CREATE TABLE public.user_company_roles
                (id integer PRIMARY KEY, user_id integer, company_id integer,
                 platform_account_id integer, role text, active boolean)""")
            cur.execute("INSERT INTO public.platform_accounts VALUES (3, TRUE, 'active')")
            cur.execute("INSERT INTO public.companies VALUES (5, 3, TRUE), (6, 3, TRUE)")
            cur.execute("INSERT INTO public.users VALUES (9, 'QA', 'qa@example.test', TRUE, 'прораб', FALSE, FALSE, 3)")
            cur.execute("""INSERT INTO public.user_sessions VALUES
                (9, %s, NULL, clock_timestamp() + interval '1 hour', TRUE)""",
                (_CLAIMS["sessionHash"],))
            cur.execute("""INSERT INTO public.user_company_roles VALUES
                (12, 9, 5, 3, 'прораб', TRUE)""")

    @classmethod
    def tearDownClass(cls):
        if not hasattr(cls, "db"):
            return
        try:
            with cls.db.cursor() as cur:
                for table in _TABLES:
                    cur.execute("DROP TABLE IF EXISTS public." + table)
        finally:
            cls.db.close()

    def _resolve(self):
        # Same per-request autocommit transition as the QA-only HTTP route.
        self.db.autocommit = False
        try:
            with self.db.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                return resolve_qa_identity_read_only(cur, _CLAIMS)
        finally:
            self.db.rollback()
            self.db.autocommit = True

    def test_exact_active_company_membership_from_real_postgres(self):
        result = self._resolve()
        self.assertEqual(result["user"]["id"], 9)
        self.assertEqual(result["user"]["companyId"], 5)
        self.assertEqual(result["companies"][0]["membershipId"], 12)
        self.assertEqual(len(result["companies"]), 1)
        self.assertNotIn("sessionHash", repr(result))

    def test_foreign_second_company_fails_closed(self):
        with self.db.cursor() as cur:
            cur.execute("""INSERT INTO public.user_company_roles VALUES
                (13, 9, 6, 3, 'прораб', TRUE)""")
        try:
            with self.assertRaises(QAReadOnlyAuthRejected):
                self._resolve()
        finally:
            with self.db.cursor() as cur:
                cur.execute("DELETE FROM public.user_company_roles WHERE id=13")

    def test_expired_and_revoked_sessions_are_rejected(self):
        changes = (
            ("expires_at=clock_timestamp() - interval '1 hour'",),
            ("revoked_at=clock_timestamp()",),
        )
        for (change,) in changes:
            with self.subTest(change=change):
                with self.db.cursor() as cur:
                    cur.execute("UPDATE public.user_sessions SET " + change)
                try:
                    with self.assertRaises(QAReadOnlyAuthRejected):
                        self._resolve()
                finally:
                    with self.db.cursor() as cur:
                        cur.execute("""UPDATE public.user_sessions SET
                            expires_at=clock_timestamp() + interval '1 hour',
                            revoked_at=NULL, two_factor_passed=TRUE""")

    def test_non_2fa_foreman_login_session_is_accepted(self):
        # Real /login records FALSE for roles that do not require 2FA.
        with self.db.cursor() as cur:
            cur.execute("UPDATE public.user_sessions SET two_factor_passed=FALSE")
        try:
            self.assertEqual(self._resolve()["user"]["companyId"], 5)
        finally:
            with self.db.cursor() as cur:
                cur.execute("UPDATE public.user_sessions SET two_factor_passed=TRUE")

    def test_required_or_enabled_2fa_still_rejects_unverified_session(self):
        with self.db.cursor() as cur:
            cur.execute("UPDATE public.user_sessions SET two_factor_passed=FALSE")
        try:
            for column in ("two_factor_required", "two_factor_enabled"):
                with self.subTest(column=column):
                    with self.db.cursor() as cur:
                        cur.execute("UPDATE public.users SET " + column + "=TRUE WHERE id=9")
                    try:
                        with self.assertRaises(QAReadOnlyAuthRejected):
                            self._resolve()
                    finally:
                        with self.db.cursor() as cur:
                            cur.execute("UPDATE public.users SET " + column + "=FALSE WHERE id=9")
            for role in ("директор", "platform_admin"):
                with self.subTest(role=role):
                    with self.db.cursor() as cur:
                        cur.execute("UPDATE public.users SET role=%s WHERE id=9", (role,))
                    try:
                        with self.assertRaises(QAReadOnlyAuthRejected):
                            self._resolve()
                    finally:
                        with self.db.cursor() as cur:
                            cur.execute("UPDATE public.users SET role='прораб' WHERE id=9")
        finally:
            with self.db.cursor() as cur:
                cur.execute("UPDATE public.user_sessions SET two_factor_passed=TRUE")

    def test_2fa_passed_platform_account_or_supplier_identity_cannot_reuse_membership(self):
        # The fixture intentionally retains an active ordinary company membership.
        # Passed 2FA does not turn a global support/account/supplier role into it.
        for role in ("platform_support", "platform_admin", "system_owner",
                     "billing_admin", "account_owner", "account_admin", "поставщик"):
            with self.subTest(role=role):
                with self.db.cursor() as cur:
                    cur.execute("UPDATE public.users SET role=%s WHERE id=9", (role,))
                    cur.execute("UPDATE public.user_sessions SET two_factor_passed=TRUE")
                try:
                    with self.assertRaises(QAReadOnlyAuthRejected):
                        self._resolve()
                finally:
                    with self.db.cursor() as cur:
                        cur.execute("UPDATE public.users SET role='прораб' WHERE id=9")

    def test_known_account_mismatch_rejected_and_legacy_null_preserved(self):
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO public.platform_accounts VALUES (4, TRUE, 'active')")
            cur.execute("UPDATE public.users SET platform_account_id=4 WHERE id=9")
        try:
            with self.assertRaises(QAReadOnlyAuthRejected):
                self._resolve()
            with self.db.cursor() as cur:
                cur.execute("UPDATE public.users SET platform_account_id=NULL WHERE id=9")
            self.assertEqual(self._resolve()["user"]["companyId"], 5)
        finally:
            with self.db.cursor() as cur:
                cur.execute("UPDATE public.users SET platform_account_id=3 WHERE id=9")
                cur.execute("DELETE FROM public.platform_accounts WHERE id=4")

    def test_inactive_company_and_membership_are_rejected(self):
        for table in ("companies", "user_company_roles"):
            with self.subTest(table=table):
                with self.db.cursor() as cur:
                    cur.execute("UPDATE public." + table + " SET active=FALSE")
                try:
                    with self.assertRaises(QAReadOnlyAuthRejected):
                        self._resolve()
                finally:
                    with self.db.cursor() as cur:
                        cur.execute("UPDATE public." + table + " SET active=TRUE")


if __name__ == "__main__":
    unittest.main()
