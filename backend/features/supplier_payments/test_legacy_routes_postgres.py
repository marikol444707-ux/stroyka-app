"""Authenticated old routes against real ledger rows; internal seed, no new API."""
import os
import unittest

from . import test_engine_postgres as engine_tests
from ..supplier_access import test_postgres_chain as chain


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class LegacyLedgerRoutesTests(unittest.TestCase):
    def test_customer_never_sees_ledger_but_finance_gets_authoritative_kind(self):
        from uuid import uuid4
        paid = self.execute(self.body())
        reverse_body = self.body()
        reverse_body.pop('amount')
        reverse_body.update(kind='reversal', reversesId=paid['operationId'])
        reversed_payment = self.execute(reverse_body)
        legacy = self.api('accountant', 'POST', '/project-payments', dict(
            projectName=self.fixture['project'], amount=7, note='Акт ' + str(uuid4()), date='2026-09-18'))
        finance = {r['id']: r for r in self.api('accountant', 'GET', '/project-payments')}
        for result, kind in ((paid, 'payment'), (reversed_payment, 'reversal')):
            self.assertEqual(finance[result['projectPaymentId']].get('sourceKind'), 'supplier_payment_ledger')
            self.assertEqual(finance[result['projectPaymentId']].get('operationKind'), kind)
        self.assertIsNone(finance[legacy['id']].get('sourceKind'))
        uid = self.fixture['users']['foreman']['id']
        self.sql("UPDATE users SET role='заказчик' WHERE id=%s", (uid,))
        self.sql("UPDATE user_company_roles SET role='заказчик' WHERE user_id=%s", (uid,))
        try:
            visible = {r['id'] for r in self.api('foreman', 'GET', '/project-payments')}
            self.assertIn(legacy['id'], visible)
            self.assertFalse({paid['projectPaymentId'], reversed_payment['projectPaymentId']} & visible)
        finally:
            self.sql("UPDATE users SET role='прораб' WHERE id=%s", (uid,))
            self.sql("UPDATE user_company_roles SET role='прораб' WHERE user_id=%s", (uid,))

    def test_distinct_payer_requires_current_finance_membership(self):
        def payer_policy(*args):
            context = self.policy(*args)
            context['documents'][0]['payerCompanyId'] = 3
            return context
        paid = self.execute(self.body(), policy=payer_policy)
        reverse = self.body()
        reverse.pop('amount')
        reverse.update(kind='reversal', reversesId=paid['operationId'])
        undone = self.execute(reverse, policy=payer_policy)
        ids = {paid['projectPaymentId'], undone['projectPaymentId']}
        self.assertFalse(ids & {r['id'] for r in self.api('accountant', 'GET', '/project-payments')})
        self.assertFalse(ids & {r['id'] for r in self.api('stranger', 'GET', '/project-payments')})
        uid = self.actor
        membership = self.sql('''INSERT INTO user_company_roles(user_id,company_id,platform_account_id,
            role,active,is_default) VALUES(%s,3,1,'бухгалтер',TRUE,FALSE) RETURNING id''', (uid,))[0][0]
        try:
            self.assertTrue(ids <= {r['id'] for r in self.api('accountant', 'GET', '/project-payments')})
            self.sql('UPDATE user_company_roles SET active=FALSE WHERE id=%s', (membership,))
            self.assertFalse(ids & {r['id'] for r in self.api('accountant', 'GET', '/project-payments')})
        finally:
            self.sql('DELETE FROM user_company_roles WHERE id=%s', (membership,))

    sql = chain.PostgresSupplyChainTests.sql
    api = chain.PostgresSupplyChainTests.api
    setUp = engine_tests.LedgerTests.setUp
    body = engine_tests.LedgerTests.body
    policy = engine_tests.LedgerTests.policy
    execute = engine_tests.LedgerTests.execute

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        engine_tests.LedgerTests.setUpClass.__func__(cls)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def test_ledger_reversal_is_denied_without_changing_balances(self):
        paid = self.execute(self.body())
        before = self.sql('SELECT count(*) FROM project_payments')
        self.api('accountant', 'DELETE', '/project-payments/' + str(paid['projectPaymentId']), expected=409)
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments'), before)
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (self.invoice,)), [(30,)])
        self.api('stranger', 'DELETE', '/project-payments/' + str(paid['projectPaymentId']), expected=403)

    def test_equal_legitimate_installments_remain_separate_in_list(self):
        first = self.execute(self.body())
        second = self.execute(self.body())
        rows = self.api('accountant', 'GET', '/project-payments')
        ids = {row['id'] for row in rows}
        self.assertTrue({first['projectPaymentId'], second['projectPaymentId']} <= ids)

    def test_client_supplied_tag_or_reason_cannot_claim_ledger_source(self):
        payload = dict(projectName=self.fixture['project'], amount=7, note='supplier_payment_ledger',
                       date='2026-09-18', sourceKind='supplier_payment_ledger', operationKind='reversal',
                       operationId=123)
        created = self.api('accountant', 'POST', '/project-payments', payload)
        row = next(r for r in self.api('accountant', 'GET', '/project-payments') if r['id'] == created['id'])
        self.assertIsNone(row['sourceKind'])
        self.assertIsNone(row['operationId'])
        self.assertIsNone(row['operationKind'])

    def test_unmanaged_expense_keeps_legacy_reversal_and_deduplication(self):
        from uuid import uuid4
        note = 'Synthetic unrelated expense ' + str(uuid4())
        payload = dict(projectName=self.fixture['project'], amount=7, note=note, date='2026-09-18')
        first = self.api('accountant', 'POST', '/project-payments', payload)
        self.assertEqual(self.api('accountant', 'POST', '/project-payments', payload)['id'], first['id'])
        duplicate = self.sql('''INSERT INTO project_payments
            (company_id,project_name,work_package,amount,note,date,added_by)
            SELECT company_id,project_name,work_package,amount,note,date,added_by
            FROM project_payments WHERE id=%s RETURNING id''', (first['id'],))[0][0]
        visible = {row['id'] for row in self.api('accountant', 'GET', '/project-payments')}
        self.assertEqual(visible & {first['id'], duplicate}, {duplicate})
        result = self.api('accountant', 'DELETE', '/project-payments/' + str(first['id']))
        self.assertTrue(result['reversed'])
        again = self.api('accountant', 'DELETE', '/project-payments/' + str(first['id']))
        self.assertEqual(again['reversalId'], result['reversalId'])


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PreledgerClassificationTests(unittest.TestCase):
    setUpClass = classmethod(chain.PostgresSupplyChainTests.setUpClass.__func__)
    api = chain.PostgresSupplyChainTests.api
    sql = chain.PostgresSupplyChainTests.sql

    def test_preledger_get_preserves_legacy_without_creating_schema(self):
        self.assertEqual(self.sql("SELECT to_regclass('public.supplier_payment_operations')"), [(None,)])
        paid = self.api('accountant', 'POST', '/project-payments', dict(
            projectName=self.fixture['project'], amount=30, note='Оплата бригаде по акту', date='2026-09-18'))
        row = next(r for r in self.api('accountant', 'GET', '/project-payments') if r['id'] == paid['id'])
        self.assertEqual(row['amount'], 30)
        self.assertIsNone(row['sourceKind'])
        self.assertEqual(self.sql("SELECT to_regclass('public.supplier_payment_operations')"), [(None,)])
