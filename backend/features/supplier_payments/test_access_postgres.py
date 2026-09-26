"""Opt-in real membership/locking tests; no payment or runtime registration."""
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException
from psycopg2 import errors
from psycopg2.extras import RealDictCursor


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PaymentAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ..supplier_access.test_postgres_chain_support import build_fixture
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)

    def setUp(self):
        self.conn = self.main.get_db()
        self.conn.autocommit = False
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.addCleanup(self.cur.close)
        self.actor_id = self.fixture['users']['accountant']['id']
        self.project = self.fixture['project']
        self.deps = dict(
            resolve_resource_company_actor=self.main.resolve_resource_company_actor,
            finance_roles=self.main.FINANCE_ROLES,
            platform_staff_roles=self.main.PLATFORM_STAFF_ROLES,
            client_account_roles=self.main.CLIENT_ACCOUNT_ROLES,
            require_project_access=self.main.require_project_access,
            has_package_access=self.main.has_package_access,
        )

    def authorize(self, *, payer=None, company=2, actor=None, cur=None):
        from .access import build_payment_access
        return build_payment_access(self.deps)(
            cur or self.cur, self.actor_id if actor is None else actor,
            company, self.project, 'Основная', payer_company_id=payer)

    def denied(self, **kwargs):
        with self.assertRaises(HTTPException) as error:
            self.authorize(**kwargs)
        self.assertEqual(error.exception.status_code, 403)

    def payer_membership(self, role='бухгалтер'):
        self.cur.execute('''INSERT INTO user_company_roles
            (user_id,company_id,role,active,is_default,assigned_projects,assigned_packages)
            VALUES (%s,3,%s,TRUE,FALSE,'[]','[]') RETURNING id''', (self.actor_id, role))
        return self.cur.fetchone()['id']

    def test_returns_fresh_owner_actor_without_secrets_and_does_not_commit(self):
        self.cur.execute("UPDATE users SET name='Fresh trusted name' WHERE id=%s", (self.actor_id,))
        actor = self.authorize()
        self.assertEqual((actor['id'], actor['name'], actor['role'], actor['companyId']),
                         (self.actor_id, 'Fresh trusted name', 'бухгалтер', 2))
        self.assertTrue(actor['membershipId'])
        self.assertFalse({'password', 'two_factor_secret', 'token'} & actor.keys())
        self.conn.rollback()
        self.cur.execute('SELECT name FROM users WHERE id=%s', (self.actor_id,))
        self.assertNotEqual(self.cur.fetchone()['name'], 'Fresh trusted name')

    def test_all_existing_finance_membership_roles_are_accepted(self):
        for role in self.main.FINANCE_ROLES:
            with self.subTest(role=role):
                self.cur.execute('UPDATE user_company_roles SET role=%s WHERE user_id=%s AND company_id=2',
                                 (role, self.actor_id))
                self.assertEqual(self.authorize()['role'], role)

    def test_global_role_cannot_override_nonfinancial_or_empty_membership(self):
        for role in ('снабженец', ''):
            with self.subTest(role=role):
                self.cur.execute('UPDATE user_company_roles SET role=%s WHERE user_id=%s AND company_id=2',
                                 (role, self.actor_id))
                self.denied()

    def test_financial_membership_not_unrelated_global_role_controls_actor(self):
        self.cur.execute("UPDATE users SET role='прораб' WHERE id=%s", (self.actor_id,))
        self.assertEqual(self.authorize()['role'], 'бухгалтер')

    def test_revoked_membership_never_falls_back_to_legacy_company(self):
        self.authorize()
        self.cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2',
                         (self.actor_id,))
        self.denied()

    def test_missing_membership_never_falls_back_to_legacy_company(self):
        self.cur.execute('DELETE FROM user_company_roles WHERE user_id=%s', (self.actor_id,))
        self.denied()

    def test_disabled_user_and_disabled_owner_are_denied(self):
        self.cur.execute('UPDATE users SET active=FALSE WHERE id=%s', (self.actor_id,))
        self.denied()
        self.cur.execute('UPDATE users SET active=TRUE WHERE id=%s', (self.actor_id,))
        self.cur.execute('UPDATE companies SET active=FALSE WHERE id=2')
        self.denied()

    def test_supplier_and_platform_identity_denied_even_with_finance_membership(self):
        for role in ('поставщик', *self.main.PLATFORM_STAFF_ROLES):
            with self.subTest(role=role):
                self.cur.execute('UPDATE users SET role=%s WHERE id=%s', (role, self.actor_id))
                self.denied()

    def test_foreign_company_and_account_readonly_do_not_grant_authority(self):
        self.denied(company=3)
        self.cur.execute("UPDATE users SET role='account_owner',platform_account_id=1 WHERE id=%s", (self.actor_id,))
        self.cur.execute('DELETE FROM user_company_roles WHERE user_id=%s', (self.actor_id,))
        self.denied()

    def test_distinct_payer_requires_own_finance_membership(self):
        self.denied(payer=3)
        self.payer_membership('снабженец')
        self.denied(payer=3)
        self.cur.execute("UPDATE user_company_roles SET role='бухгалтер' WHERE user_id=%s AND company_id=3", (self.actor_id,))
        self.assertEqual(self.authorize(payer=3)['companyId'], 2)
        self.cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=3', (self.actor_id,))
        self.denied(payer=3)

    def test_disabled_payer_and_missing_user_are_denied(self):
        self.payer_membership()
        self.cur.execute('UPDATE companies SET active=FALSE WHERE id=3')
        self.denied(payer=3)
        self.denied(actor=2147483647)

    def test_project_and_package_checks_receive_membership_actor(self):
        seen = []
        def project_check(actor, project):
            seen.append((actor['companyId'], actor['role'], project))
            raise HTTPException(403, 'Project denied')
        self.deps['require_project_access'] = project_check
        self.denied()
        self.assertEqual(seen, [(2, 'бухгалтер', self.project)])
        self.deps['require_project_access'] = self.main.require_project_access
        self.deps['has_package_access'] = lambda actor, package: False
        self.denied()

    def test_locks_user_owner_and_payer_memberships_until_transaction_end(self):
        # The payer row must be committed so another connection can address it.
        self.payer_membership()
        self.conn.commit()
        self.addCleanup(self.remove_payer_membership)
        self.authorize(payer=3)
        other = self.main.get_db()
        other.autocommit = False
        try:
            with other.cursor() as cur:
                for sql, params in (
                    ('SELECT id FROM users WHERE id=%s FOR UPDATE NOWAIT', (self.actor_id,)),
                    ('SELECT id FROM companies WHERE id=%s FOR UPDATE NOWAIT', (2,)),
                    ('SELECT id FROM companies WHERE id=%s FOR UPDATE NOWAIT', (3,)),
                    ('SELECT id FROM user_company_roles WHERE user_id=%s AND company_id=2 FOR UPDATE NOWAIT', (self.actor_id,)),
                    ('SELECT id FROM user_company_roles WHERE user_id=%s AND company_id=3 FOR UPDATE NOWAIT', (self.actor_id,)),
                ):
                    with self.subTest(sql=sql, params=params), self.assertRaises(errors.LockNotAvailable):
                        cur.execute(sql, params)
                    other.rollback()
                self.conn.rollback()
                cur.execute('SELECT id FROM users WHERE id=%s FOR UPDATE NOWAIT', (self.actor_id,))
        finally:
            other.rollback()
            other.close()

    def remove_payer_membership(self):
        self.conn.rollback()
        with self.conn.cursor() as cur:
            cur.execute('DELETE FROM user_company_roles WHERE user_id=%s AND company_id=3', (self.actor_id,))
        self.conn.commit()

    def test_concurrent_revocation_committed_before_lock_is_observed(self):
        self.cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (self.actor_id,))
        other = self.main.get_db()
        other.autocommit = False
        def attempt():
            try:
                with other.cursor(cursor_factory=RealDictCursor) as cur:
                    self.denied(cur=cur)
            finally:
                other.rollback()
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(attempt)
                try:
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        self.cur.execute('SELECT cardinality(pg_blocking_pids(%s)) AS n', (other.get_backend_pid(),))
                        if self.cur.fetchone()['n']:
                            break
                        if pending.done():
                            pending.result()
                            self.fail('Authorization did not wait for revocation lock')
                        time.sleep(.01)
                    else:
                        self.fail('Authorization did not reach membership lock')
                finally:
                    self.conn.commit()
                pending.result(timeout=5)
        finally:
            other.close()
            self.cur.execute('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (self.actor_id,))
            self.conn.commit()

    def test_autocommit_connection_is_rejected(self):
        self.conn.rollback()
        self.conn.autocommit = True
        with self.assertRaises(RuntimeError):
            self.authorize()
