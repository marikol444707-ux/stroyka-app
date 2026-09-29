"""Revoked explicit membership must never fall back to users.company_id."""
import os
import unittest

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from .service import user_company_memberships, resolve_resource_company_actor, build_company_context_response


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class MembershipFallbackPostgresTests(unittest.TestCase):
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
        self.user = self.fixture['users']['director']

    def revoke(self):
        self.cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s', (self.user['id'],))

    def test_revoked_membership_cannot_mutate_through_legacy_company(self):
        self.revoke()
        with self.assertRaises(HTTPException) as error:
            resolve_resource_company_actor(self.cur, self.user, 2, 'update', allowed_roles=('директор',))
        self.assertEqual(error.exception.status_code, 403)

    def test_revoked_memberships_hidden_from_company_response(self):
        self.revoke()
        response = build_company_context_response(self.cur, self.user)
        self.assertEqual(response['companies'], [])

    def test_inactive_company_explicit_membership_does_not_fallback(self):
        self.cur.execute('UPDATE companies SET active=FALSE WHERE id=2')
        self.assertEqual(user_company_memberships(self.cur, self.user), [])

    def test_explicit_other_company_record_also_disables_legacy_fallback(self):
        self.cur.execute('UPDATE user_company_roles SET company_id=3,active=FALSE WHERE user_id=%s', (self.user['id'],))
        self.assertEqual(user_company_memberships(self.cur, self.user), [])

    def test_genuinely_unmigrated_user_keeps_legacy_context(self):
        self.cur.execute('DELETE FROM user_company_roles WHERE user_id=%s', (self.user['id'],))
        context, actor = resolve_resource_company_actor(self.cur, self.user, 2, 'update', allowed_roles=('директор',))
        self.assertEqual((context['source'], actor['companyId']), ('legacy', 2))

    def test_active_membership_and_include_inactive_keep_existing_semantics(self):
        rows = user_company_memberships(self.cur, self.user)
        self.assertEqual([(r['companyId'], r['source']) for r in rows], [(2, 'membership')])
        self.revoke()
        rows = user_company_memberships(self.cur, self.user, include_inactive=True)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]['active'])
        self.assertEqual(rows[0]['source'], 'membership')

    def test_active_other_company_remains_usable_without_reviving_revoked_owner(self):
        self.revoke()
        self.cur.execute('''INSERT INTO user_company_roles(user_id,company_id,role,active,is_default)
                            VALUES(%s,3,'бухгалтер',TRUE,FALSE)''', (self.user['id'],))
        rows = user_company_memberships(self.cur, self.user)
        self.assertEqual([(r['companyId'],r['role']) for r in rows], [(3,'бухгалтер')])
