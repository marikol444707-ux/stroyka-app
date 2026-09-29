"""Synthetic authenticated brigade reversal against optional supplier ledger."""
import os
import unittest

from ..supplier_payments import test_engine_postgres as ledger
from ..supplier_access import test_postgres_chain as chain


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class BrigadeLedgerTests(unittest.TestCase):
    sql = chain.PostgresSupplyChainTests.sql
    api = chain.PostgresSupplyChainTests.api
    body = ledger.LedgerTests.body
    policy = ledger.LedgerTests.policy
    execute = ledger.LedgerTests.execute

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        ledger.LedgerTests.setUpClass.__func__(cls)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def setUp(self):
        ledger.LedgerTests.setUp(self)
        self.contract = self.sql('''INSERT INTO brigade_contracts
            (company_id,project_id,project_name,brigade_name,work_package)
            VALUES (2,%s,%s,'Synthetic brigade','') RETURNING id''',
            (self.fixture['projectId'], self.fixture['project']))[0][0]

    def link_payment(self, payment_id):
        return self.sql('''INSERT INTO brigade_payments
            (company_id,contract_id,project_payment_id,amount,paid_by)
            VALUES (2,%s,%s,10,'Synthetic accountant') RETURNING id''',
            (self.contract, payment_id))[0][0]

    def test_ledger_payment_and_reversal_cannot_be_reversed_as_brigade_expense(self):
        paid = self.execute(self.body())
        reversal = self.body()
        reversal.pop('amount')
        reversal.update(kind='reversal', reversesId=paid['operationId'])
        reversed_payment = self.execute(reversal)
        for operation in (paid, reversed_payment):
            with self.subTest(kind=operation['kind']):
                brigade_id = self.link_payment(operation['projectPaymentId'])
                before = self.sql('SELECT count(*) FROM project_payments')
                self.api('accountant', 'DELETE', '/brigade-payments/' + str(brigade_id), expected=409)
                self.assertEqual(self.sql('SELECT count(*) FROM project_payments'), before)
                self.assertEqual(self.sql('SELECT project_payment_id FROM brigade_payments WHERE id=%s',
                                         (brigade_id,)), [(operation['projectPaymentId'],)])
                self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',
                                         (self.invoice,)), [(20,)])

    def test_foreign_actor_denied_before_ledger_details(self):
        paid = self.execute(self.body())
        brigade_id = self.link_payment(paid['projectPaymentId'])
        self.api('stranger', 'DELETE', '/brigade-payments/' + str(brigade_id), expected=403)
        self.assertEqual(self.sql('SELECT count(*) FROM brigade_payments WHERE id=%s', (brigade_id,)), [(1,)])

    def test_unmanaged_payment_with_supplier_note_still_reverses(self):
        payment_id = self.sql('''INSERT INTO project_payments
            (company_id,project_name,work_package,amount,note,date,added_by)
            VALUES (2,%s,'',10,'Synthetic payment','2026-09-18','Synthetic accountant') RETURNING id''',
            (self.fixture['project'],))[0][0]
        brigade_id = self.link_payment(payment_id)
        result = self.api('accountant', 'DELETE', '/brigade-payments/' + str(brigade_id))
        self.assertEqual(self.sql('SELECT amount FROM project_payments WHERE id=%s',
                                 (result['projectPaymentReversalId'],)), [(-10,)])
        self.assertEqual(self.sql('SELECT count(*) FROM brigade_payments WHERE id=%s', (brigade_id,)), [(0,)])
