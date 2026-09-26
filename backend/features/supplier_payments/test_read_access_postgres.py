"""Financial read authority; subscription write denial remains HTTP middleware."""
import datetime as dt
import os
import unittest

from fastapi import HTTPException

from . import test_access_postgres as access_tests
from ..supplier_access import test_postgres_chain as chain


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PaymentReadAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        access_tests.PaymentAccessTests.setUpClass.__func__(cls)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    setUp = access_tests.PaymentAccessTests.setUp
    payer_membership = access_tests.PaymentAccessTests.payer_membership
    api = chain.PostgresSupplyChainTests.api

    def authorize(self, operation='read', payer=None):
        from .access import build_payment_access
        factory = build_payment_access(self.deps) if operation is None else build_payment_access(self.deps, operation=operation)
        return factory(self.cur, self.actor_id, 2, self.project, 'Основная', payer_company_id=payer)

    def denied(self, **kwargs):
        with self.assertRaises(HTTPException) as error:
            self.authorize(**kwargs)
        self.assertEqual(error.exception.status_code, 403)

    def test_read_action_and_readonly_context_do_not_weaken_default_write(self):
        original = self.deps['resolve_resource_company_actor']
        seen = []
        def resolve(cur, user, company, operation, **kwargs):
            seen.append(operation)
            context, actor = original(cur, user, company, operation, **kwargs)
            return {**context, 'readOnly': True}, actor
        self.deps['resolve_resource_company_actor'] = resolve
        self.assertEqual(self.authorize()['companyId'], 2)
        self.denied(operation=None)
        self.denied(operation='update')
        self.assertEqual(seen, ['read', 'update', 'update'])

    def test_expired_subscription_allows_financial_read_but_http_write_denied(self):
        self.cur.execute('SELECT plan,plan_expires_at,payment_status FROM companies WHERE id=2')
        before = self.cur.fetchone()
        self.cur.execute("UPDATE companies SET plan='business',plan_expires_at=%s,payment_status='active' WHERE id=2",
                         (dt.date.today() - dt.timedelta(days=1),))
        self.conn.commit()
        try:
            self.assertEqual(self.authorize()['companyId'], 2)
            self.api('accountant', 'GET', '/supplier-invoices', **{'X-Company-Id': '2'})
            result = self.api('accountant', 'POST', '/supplier-invoices',
                              dict(companyId=2, amount=10), expected=403, **{'X-Company-Id': '2'})
            self.assertEqual(result['code'], 'subscription_read_only')
        finally:
            self.cur.execute('UPDATE companies SET plan=%s,plan_expires_at=%s,payment_status=%s WHERE id=2',
                             (before['plan'], before['plan_expires_at'], before['payment_status']))
            self.conn.commit()

    def test_nonfinancial_and_missing_memberships_still_denied(self):
        self.cur.execute("UPDATE user_company_roles SET role='снабженец' WHERE user_id=%s", (self.actor_id,))
        self.denied()
        self.cur.execute('DELETE FROM user_company_roles WHERE user_id=%s', (self.actor_id,))
        self.denied()

    def test_inactive_owner_company_still_denied(self):
        self.cur.execute('UPDATE companies SET active=FALSE WHERE id=2')
        self.denied()

    def test_revoked_member_still_denied(self):
        self.cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s', (self.actor_id,))
        self.denied()

    def test_payer_needs_active_company_and_financial_membership_for_read(self):
        self.denied(payer=3)
        self.payer_membership('снабженец')
        self.denied(payer=3)
        self.cur.execute("UPDATE user_company_roles SET role='бухгалтер' WHERE user_id=%s AND company_id=3", (self.actor_id,))
        self.assertEqual(self.authorize(payer=3)['companyId'], 2)
        self.cur.execute('UPDATE companies SET active=FALSE WHERE id=3')
        self.denied(payer=3)

    def test_project_and_package_checks_still_apply_to_read(self):
        def deny_project(*args):
            raise HTTPException(403, 'Synthetic project denial')
        self.deps['require_project_access'] = deny_project
        self.denied()
        self.deps['require_project_access'] = self.main.require_project_access
        self.deps['has_package_access'] = lambda *args: False
        self.denied()

    def test_unknown_operation_rejected_at_factory(self):
        from .access import build_payment_access
        for operation in ('', 'delete', None, 'READ'):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                build_payment_access(self.deps, operation=operation)
